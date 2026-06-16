import json
from collections import Counter
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
SUMMARY_PATH = ROOT_DIR / "reports" / "summary.json"
BENCHMARK_PATH = ROOT_DIR / "reports" / "benchmark_results.json"
DETAIL_JSON_PATH = ROOT_DIR / "reports" / "detailed_metrics.json"
DETAIL_MD_PATH = ROOT_DIR / "analysis" / "detailed_evaluation.md"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def money(value: float) -> str:
    return f"${value:.8f}"


def metric_row(name: str, baseline: float, candidate: float, formatter=str) -> dict:
    return {
        "metric": name,
        "baseline": baseline,
        "candidate": candidate,
        "delta": candidate - baseline,
        "display": {
            "baseline": formatter(baseline),
            "candidate": formatter(candidate),
            "delta": formatter(candidate - baseline),
        },
    }


def collect_case_stats(results: list[dict]) -> dict:
    by_status = Counter(r.get("status", "unknown") for r in results)
    by_type = Counter(r.get("type", "unknown") for r in results)
    by_cluster = Counter(r.get("failure_cluster", "unknown") for r in results)
    slowest = sorted(results, key=lambda r: r.get("latency", 0), reverse=True)[:5]
    lowest_score = sorted(results, key=lambda r: r["judge"]["final_score"])[:5]
    return {
        "status": dict(by_status),
        "type": dict(by_type),
        "failure_cluster": dict(by_cluster),
        "slowest_cases": [
            {
                "case_id": r["case_id"],
                "latency": r["latency"],
                "score": r["judge"]["final_score"],
                "question": r["test_case"],
            }
            for r in slowest
        ],
        "lowest_score_cases": [
            {
                "case_id": r["case_id"],
                "score": r["judge"]["final_score"],
                "hit_rate": r["ragas"]["retrieval"]["hit_rate"],
                "question": r["test_case"],
            }
            for r in lowest_score
        ],
    }


def build_detail() -> dict:
    summary = load_json(SUMMARY_PATH)
    benchmark = load_json(BENCHMARK_PATH)
    baseline_summary = benchmark["baseline"]["summary"]
    candidate_summary = benchmark["candidate"]["summary"]
    baseline = baseline_summary["metrics"]
    candidate = candidate_summary["metrics"]
    gate = summary.get("regression", {})

    metric_rows = [
        metric_row("avg_score", baseline["avg_score"], candidate["avg_score"], lambda v: f"{v:.2f}/5"),
        metric_row("pass_rate", baseline["pass_rate"], candidate["pass_rate"], pct),
        metric_row("hit_rate", baseline["hit_rate"], candidate["hit_rate"], pct),
        metric_row("mrr", baseline["mrr"], candidate["mrr"], lambda v: f"{v:.4f}"),
        metric_row("precision_at_k", baseline["precision_at_k"], candidate["precision_at_k"], pct),
        metric_row("recall_at_k", baseline["recall_at_k"], candidate["recall_at_k"], pct),
        metric_row("agreement_rate", baseline["agreement_rate"], candidate["agreement_rate"], pct),
        metric_row("avg_latency_seconds", baseline["avg_latency_seconds"], candidate["avg_latency_seconds"], lambda v: f"{v:.4f}s"),
        metric_row("p95_latency_seconds", baseline["p95_latency_seconds"], candidate["p95_latency_seconds"], lambda v: f"{v:.4f}s"),
        metric_row("duration_seconds", baseline["duration_seconds"], candidate["duration_seconds"], lambda v: f"{v:.4f}s"),
        metric_row("total_tokens", baseline["total_tokens"], candidate["total_tokens"], lambda v: f"{v:.0f}"),
        metric_row("avg_tokens_per_case", baseline["avg_tokens_per_case"], candidate["avg_tokens_per_case"], lambda v: f"{v:.2f}"),
        metric_row("estimated_cost_usd", baseline["estimated_cost_usd"], candidate["estimated_cost_usd"], money),
    ]

    return {
        "metadata": summary["metadata"],
        "release_gate": gate,
        "metrics": metric_rows,
        "baseline_case_stats": collect_case_stats(benchmark["baseline"]["results"]),
        "candidate_case_stats": collect_case_stats(benchmark["candidate"]["results"]),
    }


def write_markdown(detail: dict) -> None:
    gate = detail["release_gate"]
    lines = [
        "# Detailed Evaluation Report",
        "",
        f"- **Version:** {detail['metadata']['version']}",
        f"- **Judge mode:** {detail['metadata'].get('judge_mode')}",
        f"- **Judge models:** {detail['metadata'].get('judge_models')}",
        f"- **Release decision:** {gate.get('decision', 'N/A')}",
        f"- **Reason:** {gate.get('reason', 'N/A')}",
        "",
        "## Metrics",
        "| Metric | Baseline | Candidate | Delta |",
        "|---|---:|---:|---:|",
    ]
    for row in detail["metrics"]:
        display = row["display"]
        lines.append(f"| {row['metric']} | {display['baseline']} | {display['candidate']} | {display['delta']} |")

    lines.extend(["", "## Release Gate Checks", "| Check | Result |", "|---|---:|"])
    for name, passed in gate.get("checks", {}).items():
        lines.append(f"| {name} | {'PASS' if passed else 'FAIL'} |")

    lines.extend(["", "## Candidate Case Distribution"])
    for key, values in detail["candidate_case_stats"].items():
        if key in {"slowest_cases", "lowest_score_cases"}:
            continue
        lines.append(f"- **{key}:** {values}")

    lines.extend(["", "## Slowest Candidate Cases"])
    for case in detail["candidate_case_stats"]["slowest_cases"]:
        lines.append(f"- `{case['case_id']}` | {case['latency']:.4f}s | score {case['score']:.2f} | {case['question']}")

    lines.extend(["", "## Lowest Score Candidate Cases"])
    for case in detail["candidate_case_stats"]["lowest_score_cases"]:
        lines.append(f"- `{case['case_id']}` | score {case['score']:.2f} | hit_rate {case['hit_rate']:.2f} | {case['question']}")

    DETAIL_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    DETAIL_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_detail(detail: dict) -> None:
    gate = detail["release_gate"]
    print("\n📌 --- DETAILED EVALUATION REPORT ---")
    print(f"Release decision: {gate.get('decision', 'N/A')}")
    print(f"Reason: {gate.get('reason', 'N/A')}")
    print("\nMetrics:")
    for row in detail["metrics"]:
        display = row["display"]
        print(f"- {row['metric']}: baseline={display['baseline']} | candidate={display['candidate']} | delta={display['delta']}")

    print("\nRelease Gate Checks:")
    for name, passed in gate.get("checks", {}).items():
        print(f"- {name}: {'PASS' if passed else 'FAIL'}")

    print(f"\nĐã ghi: {DETAIL_JSON_PATH}")
    print(f"Đã ghi: {DETAIL_MD_PATH}")


def main() -> None:
    if not SUMMARY_PATH.exists() or not BENCHMARK_PATH.exists():
        raise SystemExit("Thiếu reports. Hãy chạy 'python main.py' trước.")
    detail = build_detail()
    DETAIL_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DETAIL_JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(detail, f, ensure_ascii=False, indent=2)
    write_markdown(detail)
    print_detail(detail)


if __name__ == "__main__":
    main()
