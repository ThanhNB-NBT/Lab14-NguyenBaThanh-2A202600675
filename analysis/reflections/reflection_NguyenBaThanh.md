# Reflection - Nguyễn Bá Thành

## Vai trò đóng góp
Em phụ trách hoàn thiện pipeline AI Evaluation Factory cho agent RAG hỗ trợ khách hàng:

- Thiết kế golden dataset 55 cases với `expected_retrieval_ids`, gồm easy/medium/hard,
  5 red-team cases (prompt-injection, goal-hijacking, out-of-context, conflicting-info,
  privacy-edge) và 5 multi-hop cases.
- Xây dựng retrieval evaluator tính Hit Rate, MRR, Precision@K và Recall@K theo công thức
  minh bạch, deterministic.
- Xây dựng async benchmark runner chạy V1/V2 theo batch, ghi đầy đủ latency, token và cost.
- Cài đặt **multi-judge** dùng hai LLM judge khác họ qua NVIDIA API
  (`llama-3.3-nemotron-super-49b-v1` + `nemotron-3-nano-30b-a3b`), có arbiter hòa giải
  khi hai judge lệch > 1 điểm.
- Thêm regression release gate quyết định `APPROVE` / `ROLLBACK` dựa trên 7 ngưỡng:
  score delta, pass rate, hit rate, MRR, agreement, p95 latency và cost.

Kết quả cuối: V2 đạt avg_score **4.84/5**, pass_rate **100%**, Hit Rate **100%**, MRR **1.00**,
agreement **~90%**, cost **$0.0019** → gate ra **APPROVE**.

## Bài học kỹ thuật

**Multi-judge với hai LLM thật sự khác họ thì không bao giờ đồng thuận tuyệt đối.**
Hai judge chấm thang 1-5 (số nguyên) chỉ cần lệch 1 điểm (ví dụ 4 vs 5) là agreement của case
đó tụt còn 0.5. Vì vậy agreement thực tế chỉ ~0.59 khi câu trả lời còn nhiễu, và ~0.90 khi
câu trả lời sạch. Em học được rằng ngưỡng agreement phải được **calibrate theo dữ liệu thật**,
không thể đặt 0.95 một cách duy ý chí — ngưỡng 0.95 ban đầu gần như bất khả thi. Cuối cùng
em chọn 0.75: đủ chặt để bắt regression (khi trả lời nhiễu kéo agreement về ~0.59 thì gate
FAIL) nhưng vẫn khả thi cho judge đa dạng. Cơ chế **arbiter** là phần quan trọng: thay vì
tin mù một judge, khi hai bên lệch lớn thì lấy điểm hòa giải nên kết luận đáng tin hơn.

**Hit Rate vs MRR.** Hit Rate chỉ cho biết có tìm thấy tài liệu đúng trong top-k hay không;
MRR phản ánh cả vị trí — đặt tài liệu đúng càng sớm càng tốt. V2 đạt Hit Rate 100% và
MRR 1.00 nghĩa là tài liệu đúng luôn nằm ở vị trí số 1.

**Precision@K thấp (~0.38) không phải lỗi.** Phần lớn case chỉ có 1 tài liệu kỳ vọng trong
khi retriever trả về top-3/4, nên precision tối đa chỉ ~1/3. Recall@K 100% và MRR 1.0 mới là
chỉ số phản ánh đúng chất lượng retrieval ở bộ dữ liệu này.

## Quá trình debug thực tế (bài học lớn nhất)

Pipeline khi chạy thật với NVIDIA API đã bộc lộ 3 vấn đề mà bản deterministic offline không
hề thấy:

1. **Judge timeout.** Model judge ban đầu `nemotron-3-ultra-550b` (550 tỷ tham số, có reasoning)
   phản hồi > 120s, vượt timeout 60s và làm sập cả benchmark. Bài học: model càng lớn/càng
   "reasoning" chưa chắc phù hợp làm judge — phải đo latency trước khi chọn.

2. **Rate limit 429.** Model `deepseek-v4-flash` có quota theo key rất thấp, cạn sau vài lần gọi.
   Bài học: lỗi 429 là tạm thời, code phải **retry với exponential backoff** (tôn trọng header
   Retry-After) thay vì crash. Em đã thêm cơ chế này vào judge và đổi sang model NVIDIA ổn định hơn.

3. **Lỗi thật của agent lộ ra nhờ judge (TC-039).** Case privacy bị cả hai judge chấm 2.0 vì
   câu trả lời ghép nhầm nội dung "mất đồ trên xe" (DOC-002, điểm chỉ 0.36 so với doc top).
   Nguyên nhân: hàm tổng hợp ghép mọi tài liệu có điểm tuyệt đối >= 2. Em sửa thành chỉ ghép
   tài liệu thứ hai khi điểm >= 70% điểm của tài liệu top → TC-039 chuyển sang 5.0, pass_rate
   lên 100%. **Đây là minh chứng rõ nhất cho giá trị của pipeline đánh giá**: chính hai judge đã
   chỉ ra một bug mà nếu không có benchmark thì rất khó phát hiện.

## Trade-off chi phí và chất lượng

Dùng hai judge LLM thật tăng độ tin cậy so với rubric offline nhưng latency và chi phí cao hơn,
và phụ thuộc rate limit của API. Cách giảm chi phí mà ít giảm chất lượng: chỉ gọi judge nặng
cho các case có retrieval miss, score gần ngưỡng, hoặc hai judge nhẹ bị bất đồng — các case
rõ ràng đúng/sai thì dùng judge nhẹ hơn hoặc rubric offline. Ngoài ra batch_size và
rate_limit_rpm cần đặt thấp để tránh 429 khi key có quota giới hạn.

## Hướng cải tiến
- Thêm embedding retriever và reranker để giảm lỗi lexical miss ở hard cases ngoài golden set.
- Tính **Cohen's Kappa** thật bên cạnh agreement_rate để đo độ đồng thuận chuẩn xác hơn
  (hiện engine mới chỉ tính agreement_rate, chưa tính Kappa).
- Cắt top-k động theo ngưỡng điểm để cải thiện Precision@K.
- Lưu citation theo chunk-level thay vì document-level để truy vết hallucination chi tiết hơn.
- Bổ sung judge thứ ba làm tie-breaker khi arbiter còn lệch lớn.
- Đưa `python check_lab.py` và release gate vào CI để chặn regression trước khi nộp/merge.
