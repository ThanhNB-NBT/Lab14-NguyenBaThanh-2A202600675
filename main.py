import asyncio
import json
import os
import time

from agent.main_agent import MainAgent
from engine.llm_judge import LLMJudge
from engine.retrieval_eval import RetrievalEvaluator
from engine.runner import BenchmarkRunner


def load_env_file(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()


def percentile(values, pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * pct))
    return ordered[index]


# Giữ đúng cấu trúc main.py gốc, chỉ thay phần giả lập bằng evaluator thật.
class ExpertEvaluator:
    def __init__(self):
        self.retrieval_evaluator = RetrievalEvaluator()

    async def score(self, case, resp):
        return await self.retrieval_evaluator.score(case, resp)


class MultiModelJudge:
    def __init__(self):
        self.judge = LLMJudge()

    async def evaluate_multi_judge(self, q, a, gt, case=None, response=None):
        return await self.judge.evaluate_multi_judge(q, a, gt, case=case, response=response)


def summarize_results(agent_version: str, results: list[dict], duration_seconds: float) -> dict:
    total = len(results)
    pass_count = sum(1 for r in results if r["status"] == "pass")
    fail_count = total - pass_count
    latencies = [r["latency"] for r in results]
    total_tokens = sum(r.get("tokens_used", 0) for r in results)
    total_cost = sum(r.get("estimated_cost_usd", 0.0) for r in results)

    judge_mode = os.getenv("LLM_PROVIDER", "deterministic").strip().lower()
    if judge_mode == "nvidia":
        judge_models = os.getenv("NVIDIA_JUDGE_MODELS", "")
    elif judge_mode == "ollama" or os.getenv("USE_OLLAMA_JUDGE", "0") == "1":
        judge_models = os.getenv("OLLAMA_JUDGE_MODELS", "")
    else:
        judge_models = "coverage-judge-local,safety-judge-local"

    return {
        "metadata": {
            "version": agent_version,
            "total": total,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "judge_mode": judge_mode,
            "judge_models": judge_models,
            "rate_limit_rpm": int(os.getenv("LLM_RATE_LIMIT_RPM", "40")),
        },
        "metrics": {
            "avg_score": sum(r["judge"]["final_score"] for r in results) / total,
            "pass_rate": pass_count / total,
            "fail_count": fail_count,
            "hit_rate": sum(r["ragas"]["retrieval"]["hit_rate"] for r in results) / total,
            "mrr": sum(r["ragas"]["retrieval"]["mrr"] for r in results) / total,
            "precision_at_k": sum(r["ragas"]["retrieval"]["precision_at_k"] for r in results) / total,
            "recall_at_k": sum(r["ragas"]["retrieval"]["recall_at_k"] for r in results) / total,
            "agreement_rate": sum(r["judge"]["agreement_rate"] for r in results) / total,
            "avg_latency_seconds": sum(latencies) / total,
            "p95_latency_seconds": percentile(latencies, 0.95),
            "duration_seconds": duration_seconds,
            "total_tokens": total_tokens,
            "avg_tokens_per_case": total_tokens / total,
            "estimated_cost_usd": total_cost,
        },
    }


def build_release_gate(v1_summary: dict, v2_summary: dict) -> dict:
    v1 = v1_summary["metrics"]
    v2 = v2_summary["metrics"]

    thresholds = {
        "score_delta_min": float(os.getenv("RELEASE_SCORE_DELTA_MIN", "0.2")),
        "pass_rate_min": float(os.getenv("RELEASE_PASS_RATE_MIN", "1.0")),
        "agreement_rate_min": float(os.getenv("RELEASE_AGREEMENT_RATE_MIN", "0.95")),
        "p95_latency_max": float(os.getenv("RELEASE_P95_LATENCY_MAX", "2.0")),
        "cost_max_usd": float(os.getenv("RELEASE_COST_MAX_USD", "0.05")),
    }
    deltas = {
        "avg_score": v2["avg_score"] - v1["avg_score"],
        "pass_rate": v2["pass_rate"] - v1["pass_rate"],
        "hit_rate": v2["hit_rate"] - v1["hit_rate"],
        "mrr": v2["mrr"] - v1["mrr"],
        "agreement_rate": v2["agreement_rate"] - v1["agreement_rate"],
        "p95_latency_seconds": v2["p95_latency_seconds"] - v1["p95_latency_seconds"],
        "estimated_cost_usd": v2["estimated_cost_usd"] - v1["estimated_cost_usd"],
    }

    checks = {
        "quality_score_delta": deltas["avg_score"] >= thresholds["score_delta_min"],
        "quality_pass_rate": v2["pass_rate"] >= thresholds["pass_rate_min"],
        "retrieval_hit_rate_non_regression": v2["hit_rate"] >= v1["hit_rate"],
        "retrieval_mrr_non_regression": v2["mrr"] >= v1["mrr"],
        "judge_agreement": v2["agreement_rate"] >= thresholds["agreement_rate_min"],
        "performance_latency": v2["p95_latency_seconds"] <= thresholds["p95_latency_max"],
        "cost_budget": v2["estimated_cost_usd"] <= thresholds["cost_max_usd"],
    }
    decision = "APPROVE" if all(checks.values()) else "ROLLBACK"

    return {
        "decision": decision,
        "thresholds": thresholds,
        "deltas": deltas,
        "checks": checks,
        "reason": (
            "V2 đạt ngưỡng chất lượng, retrieval, agreement, hiệu năng và chi phí."
            if decision == "APPROVE"
            else "V2 không đạt ít nhất một ngưỡng release gate."
        ),
    }


async def run_benchmark_with_results(agent_version: str):
    print(f"🚀 Khởi động Benchmark cho {agent_version}...")

    if not os.path.exists("data/golden_set.jsonl"):
        print("❌ Thiếu data/golden_set.jsonl. Hãy chạy 'python data/synthetic_gen.py' trước.")
        return None, None

    with open("data/golden_set.jsonl", "r", encoding="utf-8") as f:
        dataset = [json.loads(line) for line in f if line.strip()]

    if not dataset:
        print("❌ File data/golden_set.jsonl rỗng. Hãy tạo ít nhất 1 test case.")
        return None, None

    started = time.perf_counter()
    runner = BenchmarkRunner(
        MainAgent(version=agent_version),
        ExpertEvaluator(),
        MultiModelJudge(),
        batch_size=int(os.getenv("EVAL_BATCH_SIZE", "12")),
    )
    results = await runner.run_all(dataset)
    duration_seconds = time.perf_counter() - started

    return results, summarize_results(agent_version, results, duration_seconds)


async def run_benchmark(version):
    _, summary = await run_benchmark_with_results(version)
    return summary


async def main():
    load_env_file()
    v1_results, v1_summary = await run_benchmark_with_results("Agent_V1_Base")

    # V2 dùng cùng dataset/evaluator/judge, chỉ thay version agent để so sánh regression công bằng.
    v2_results, v2_summary = await run_benchmark_with_results("Agent_V2_Optimized")

    if not v1_summary or not v2_summary:
        print("❌ Không thể chạy Benchmark. Kiểm tra lại data/golden_set.jsonl.")
        return

    release_gate = build_release_gate(v1_summary, v2_summary)
    v2_summary["baseline_metrics"] = v1_summary["metrics"]
    v2_summary["regression"] = release_gate

    print("\n📊 --- KẾT QUẢ SO SÁNH (REGRESSION) ---")
    print(f"V1 Score: {v1_summary['metrics']['avg_score']:.2f}")
    print(f"V2 Score: {v2_summary['metrics']['avg_score']:.2f}")
    print(f"Delta: {release_gate['deltas']['avg_score']:+.2f}")
    print(f"Hit Rate: {v2_summary['metrics']['hit_rate']:.2%}; MRR: {v2_summary['metrics']['mrr']:.2f}")
    print(f"Agreement: {v2_summary['metrics']['agreement_rate']:.2%}")
    print(f"p95 latency: {v2_summary['metrics']['p95_latency_seconds']:.3f}s")
    print(f"Cost ước tính: ${v2_summary['metrics']['estimated_cost_usd']:.6f}")
    print(f"Judge mode: {v2_summary['metadata']['judge_mode']} ({v2_summary['metadata']['judge_models']})")

    os.makedirs("reports", exist_ok=True)
    with open("reports/summary.json", "w", encoding="utf-8") as f:
        json.dump(v2_summary, f, ensure_ascii=False, indent=2)
    with open("reports/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "baseline": {"summary": v1_summary, "results": v1_results},
                "candidate": {"summary": v2_summary, "results": v2_results},
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    if release_gate["decision"] == "APPROVE":
        print("✅ QUYẾT ĐỊNH: CHẤP NHẬN BẢN CẬP NHẬT (APPROVE)")
    else:
        print("❌ QUYẾT ĐỊNH: TỪ CHỐI (ROLLBACK)")


if __name__ == "__main__":
    asyncio.run(main())
