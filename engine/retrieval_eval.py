from typing import Dict, List


class RetrievalEvaluator:
    def calculate_hit_rate(self, expected_ids: List[str], retrieved_ids: List[str], top_k: int = 3) -> float:
        # expected IDs rỗng nghĩa là hành vi đúng là không retrieve tài liệu nào.
        if not expected_ids:
            return 1.0 if not retrieved_ids else 0.0
        top_retrieved = retrieved_ids[:top_k]
        return 1.0 if any(doc_id in top_retrieved for doc_id in expected_ids) else 0.0

    def calculate_mrr(self, expected_ids: List[str], retrieved_ids: List[str]) -> float:
        # MRR thưởng cho việc đặt nguồn đúng đầu tiên càng sớm càng tốt trong danh sách rank.
        if not expected_ids:
            return 1.0 if not retrieved_ids else 0.0
        for index, doc_id in enumerate(retrieved_ids):
            if doc_id in expected_ids:
                return 1.0 / (index + 1)
        return 0.0

    def calculate_precision_at_k(self, expected_ids: List[str], retrieved_ids: List[str], top_k: int = 3) -> float:
        top_retrieved = retrieved_ids[:top_k]
        if not top_retrieved:
            return 1.0 if not expected_ids else 0.0
        if not expected_ids:
            return 0.0
        hits = sum(1 for doc_id in top_retrieved if doc_id in expected_ids)
        return hits / len(top_retrieved)

    def calculate_recall_at_k(self, expected_ids: List[str], retrieved_ids: List[str], top_k: int = 3) -> float:
        if not expected_ids:
            return 1.0 if not retrieved_ids else 0.0
        top_retrieved = set(retrieved_ids[:top_k])
        return len(set(expected_ids) & top_retrieved) / len(set(expected_ids))

    async def score(self, test_case: Dict, response: Dict, top_k: int = 3) -> Dict:
        # Runner dùng format giống RAGAS, nhưng công thức minh bạch
        # và deterministic để chấm offline.
        expected_ids = test_case.get("expected_retrieval_ids", [])
        retrieved_ids = response.get("retrieved_ids", response.get("metadata", {}).get("sources", []))
        hit_rate = self.calculate_hit_rate(expected_ids, retrieved_ids, top_k)
        mrr = self.calculate_mrr(expected_ids, retrieved_ids)
        precision = self.calculate_precision_at_k(expected_ids, retrieved_ids, top_k)
        recall = self.calculate_recall_at_k(expected_ids, retrieved_ids, top_k)

        return {
            "faithfulness": hit_rate,
            "relevancy": (precision + recall) / 2,
            "retrieval": {
                "hit_rate": hit_rate,
                "mrr": mrr,
                "precision_at_k": precision,
                "recall_at_k": recall,
                "expected_ids": expected_ids,
                "retrieved_ids": retrieved_ids,
                "top_k": top_k,
            },
        }

    async def evaluate_batch(self, dataset: List[Dict], responses: List[Dict]) -> Dict:
        scores = [await self.score(case, response) for case, response in zip(dataset, responses)]
        total = len(scores) or 1
        return {
            "avg_hit_rate": sum(score["retrieval"]["hit_rate"] for score in scores) / total,
            "avg_mrr": sum(score["retrieval"]["mrr"] for score in scores) / total,
            "avg_precision_at_k": sum(score["retrieval"]["precision_at_k"] for score in scores) / total,
            "avg_recall_at_k": sum(score["retrieval"]["recall_at_k"] for score in scores) / total,
        }
