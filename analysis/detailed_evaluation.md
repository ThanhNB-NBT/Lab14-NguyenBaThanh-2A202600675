# Detailed Evaluation Report

- **Version:** Agent_V2_Optimized
- **Judge mode:** nvidia
- **Judge models:** nvidia/llama-3.3-nemotron-super-49b-v1,nvidia/nemotron-3-nano-30b-a3b
- **Release decision:** APPROVE
- **Reason:** V2 đạt ngưỡng chất lượng, retrieval, agreement, hiệu năng và chi phí.

## Metrics
| Metric | Baseline | Candidate | Delta |
|---|---:|---:|---:|
| avg_score | 1.90/5 | 4.84/5 | 2.94/5 |
| pass_rate | 7.27% | 100.00% | 92.73% |
| hit_rate | 98.18% | 100.00% | 1.82% |
| mrr | 0.9606 | 1.0000 | 0.0394 |
| precision_at_k | 36.97% | 38.18% | 1.21% |
| recall_at_k | 97.27% | 100.00% | 2.73% |
| agreement_rate | 59.09% | 90.00% | 30.91% |
| avg_latency_seconds | 0.1433s | 0.0913s | -0.0520s |
| p95_latency_seconds | 0.1527s | 0.0992s | -0.0535s |
| duration_seconds | 171.9653s | 168.9562s | -3.0091s |
| total_tokens | 7651 | 9608 | 1957 |
| avg_tokens_per_case | 139.11 | 174.69 | 35.58 |
| estimated_cost_usd | $0.00153020 | $0.00192160 | $0.00039140 |

## Release Gate Checks
| Check | Result |
|---|---:|
| quality_score_delta | PASS |
| quality_pass_rate | PASS |
| retrieval_hit_rate_non_regression | PASS |
| retrieval_mrr_non_regression | PASS |
| judge_agreement | PASS |
| performance_latency | PASS |
| cost_budget | PASS |

## Candidate Case Distribution
- **status:** {'pass': 55}
- **type:** {'fact': 15, 'procedural': 15, 'ambiguous': 15, 'prompt-injection': 1, 'goal-hijacking': 1, 'out-of-context': 1, 'conflicting-info': 1, 'privacy-edge': 1, 'multi-hop': 5}
- **failure_cluster:** {'pass': 54, 'judge_disagreement': 1}

## Slowest Candidate Cases
- `TC-021` | 0.1080s | score 5.00 | Khách nói 'mã khuyến mãi' nhưng thiếu thông tin. Agent nên trả lời thế nào?
- `TC-008` | 0.1007s | score 5.00 | Nếu gặp vấn đề về hoàn tiền khi hủy chuyến, các bước xử lý chuẩn là gì?
- `TC-028` | 0.1006s | score 5.00 | Tôi cần khiếu nại phí phụ thu. Phải làm như thế nào?
- `TC-955` | 0.0992s | score 5.00 | Sau chuyến xe tài xế thái độ kém và có tính phí sai, nên ưu tiên xử lý theo tài liệu nào?
- `TC-032` | 0.0991s | score 5.00 | Nếu gặp vấn đề về chính sách vật nuôi, các bước xử lý chuẩn là gì?

## Lowest Score Candidate Cases
- `TC-004` | score 3.50 | hit_rate 1.00 | Tôi cần báo cáo mất đồ trên xe. Phải làm như thế nào?
- `TC-006` | score 3.50 | hit_rate 1.00 | Khách nói 'báo cáo mất đồ trên xe' nhưng thiếu thông tin. Agent nên trả lời thế nào?
- `TC-005` | score 4.00 | hit_rate 1.00 | Nếu gặp vấn đề về báo cáo mất đồ trên xe, các bước xử lý chuẩn là gì?
- `TC-024` | score 4.00 | hit_rate 1.00 | Khách nói 'đánh giá tài xế' nhưng thiếu thông tin. Agent nên trả lời thế nào?
- `TC-020` | score 4.50 | hit_rate 1.00 | Nếu gặp vấn đề về mã khuyến mãi, các bước xử lý chuẩn là gì?
