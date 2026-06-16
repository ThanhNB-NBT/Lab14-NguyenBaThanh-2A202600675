import asyncio
import time
from typing import Dict, List


class BenchmarkRunner:
    def __init__(self, agent, evaluator, judge, batch_size: int = 12):
        self.agent = agent
        self.evaluator = evaluator
        self.judge = judge
        self.batch_size = batch_size

    def _cluster_failure(self, test_case: Dict, response: Dict, ragas_scores: Dict, judge_result: Dict) -> str:
        # Thứ tự phân cụm quan trọng: lỗi retrieval là tín hiệu root-cause,
        # nên phân loại trước khi chấm chất lượng câu trả lời.
        retrieval = ragas_scores["retrieval"]
        if retrieval["hit_rate"] < 1.0:
            if not test_case.get("expected_retrieval_ids") and response.get("retrieved_ids"):
                return "out_of_scope_retrieval"
            return "retrieval_miss"
        if judge_result["final_score"] < 3:
            if test_case.get("type") in {"prompt-injection", "goal-hijacking"}:
                return "safety_guardrail_gap"
            return "answer_quality_gap"
        if judge_result["agreement_rate"] < 0.5:
            return "judge_disagreement"
        return "pass"

    async def run_single_test(self, test_case: Dict) -> Dict:
        # Mỗi dòng benchmark chứa đủ chuỗi xử lý: phản hồi agent,
        # retrieval metrics, đồng thuận judge, cost và latency.
        start_time = time.perf_counter()
        response = await self.agent.query(test_case["question"])
        latency = time.perf_counter() - start_time

        ragas_scores = await self.evaluator.score(test_case, response)
        try:
            judge_result = await self.judge.evaluate_multi_judge(
                test_case["question"],
                response["answer"],
                test_case["expected_answer"],
                case=test_case,
                response=response,
            )
        except TypeError as exc:
            if "unexpected keyword argument" not in str(exc):
                raise
            judge_result = await self.judge.evaluate_multi_judge(
                test_case["question"],
                response["answer"],
                test_case["expected_answer"],
            )
        status = "pass" if judge_result["final_score"] >= 3 and ragas_scores["retrieval"]["hit_rate"] >= 1 else "fail"
        cluster = self._cluster_failure(test_case, response, ragas_scores, judge_result)

        return {
            "case_id": test_case.get("id"),
            "category": test_case.get("category"),
            "difficulty": test_case.get("difficulty"),
            "type": test_case.get("type"),
            "test_case": test_case["question"],
            "expected_answer": test_case["expected_answer"],
            "expected_retrieval_ids": test_case.get("expected_retrieval_ids", []),
            "agent_response": response["answer"],
            "retrieved_ids": response.get("retrieved_ids", []),
            "latency": round(latency, 4),
            "ragas": ragas_scores,
            "judge": judge_result,
            "tokens_used": response.get("metadata", {}).get("tokens_used", 0),
            "estimated_cost_usd": response.get("metadata", {}).get("estimated_cost_usd", 0.0),
            "failure_cluster": cluster,
            "status": status,
        }

    async def run_all(self, dataset: List[Dict]) -> List[Dict]:
        # Chạy async theo batch có giới hạn để đạt tiêu chí hiệu năng
        # nhưng vẫn tránh vượt rate limit local/API.
        results = []
        for i in range(0, len(dataset), self.batch_size):
            batch = dataset[i : i + self.batch_size]
            tasks = [self.run_single_test(case) for case in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
        return results
