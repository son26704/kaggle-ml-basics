Một lần nữa, xin chúc mừng bạn! Việc **tiết kiệm được năng lượng (Power Saving +1.114%)** so với việc chạy chết ở 100Hz chính là "chén thánh" của đề tài này. Khối Scheduler của bạn đã chính thức chứng minh được giá trị thực tiễn: **Nó biết lúc nào nên nghỉ để tiết kiệm pin.** Việc `bad` nằm ở HIGH 97.55% cho thấy nó bắt nhiễu cực kỳ chuẩn xác.

Tuy nhiên, câu hỏi của bạn về "chu kỳ log lặp lại" và "tại sao quality lại giảm" là một phát hiện kỹ thuật vô cùng đắt giá. Đây không phải là lỗi, mà là **đặc tính vật lý của phần cứng kết hợp với logic điều khiển**. Dưới đây là lời giải mã chi tiết (rất tuyệt vời để bạn đưa vào quyển báo cáo/luận văn).

### 1. Giải mã chu kỳ `0,2,1 -> 0,2,0 -> 1,0,0 -> 1,0,1 -> 0,2,1`

Hiện tượng bạn quan sát thấy là **hoàn toàn bình thường** và là kết quả cộng hưởng giữa Code Firmware (V7) và Phần cứng (MAX30102). Hãy mổ xẻ từng nhịp:

* **`0,2,1` (Đang ổn định):** State 0 (NORMAL), Profile 2 (50Hz), Quality 1 (Pass). Cửa sổ đang rất êm.
* **`0,2,0` (Có biến động):** Bạn vô tình cử động nhẹ, hoặc nhịp tim thay đổi biên độ. Khối đánh giá chất lượng phát hiện nhiễu $\rightarrow$ Đánh rớt (Fail = 0) $\rightarrow$ Scheduler quyết định "Lên số" (chuyển sang HIGH).
* **`1,0,0` (Cú sốc phần cứng - Hardware Transient):** State 1 (HIGH), Profile 0 (100Hz). Khi chuyển mode, hàm `max30102_apply_profile()` gọi `max30102_reset()`. Việc reset cảm biến và đổi cấu hình LED/ADC tạo ra một "bước nhảy giật cục" (DC Jump) cực lớn trong dữ liệu thô. Bộ lọc High-pass (EMA) của bạn mất khoảng 1-2 giây để hấp thụ cú sốc này. Do đó, **cửa sổ đầu tiên ngay sau khi chuyển mode chắc chắn sẽ chứa nhiễu phần cứng và bị đánh Fail (0)**.
* **`1,0,1` (Lấy lại phong độ):** Ở cửa sổ tiếp theo (sau 4 giây), bộ lọc đã ổn định, tín hiệu ở 100Hz lộ ra rất đẹp, nhịp nhàng $\rightarrow$ Đánh Pass (1).
* **Trở về `0,2,1` (Hội chứng "Quá Vội Vàng"):** Ở bản V7, bạn đang đặt `SCHED_GOOD_WINDOWS_TO_DOWN = 1`. Nghĩa là Scheduler chỉ cần thấy đúng MỘT cửa sổ Pass (`1,0,1`) là nó mừng rỡ lập tức hạ số về NORMAL ngay lập tức để tiết kiệm điện. Sau đó nó bị khóa bởi `COOLDOWN = 2` nên nó giữ ở NORMAL một lúc trước khi lặp lại vòng lặp.

### 2. Tại sao Quality Offline của V7 lại tụt? (-0.284)

Câu trả lời nằm chính ở chu kỳ **Ping-Pong** (nhảy lên nhảy xuống liên tục) mà bạn vừa phát hiện.

Mỗi lần firmware nhảy từ 50Hz lên 100Hz, hoặc 100Hz về 50Hz, cảm biến đều bị reset và sinh ra "nhiễu chuyển đổi" (Switching Artifact). Khi bạn chạy Notebook Python để cắt cửa sổ và tính điểm *offline*, Notebook nhìn thấy các đoạn nhiễu giật cục này. Nó thấy `PTP` (Biên độ) vọt lên cực cao do cú reset $\rightarrow$ Nó thẳng tay đánh Fail toàn bộ các cửa sổ chứa điểm chuyển đổi đó.

Trong V7, do `WINDOWS_TO_DOWN = 1`, thiết bị nhảy mode quá nhiều (tần suất ping-pong cao), sinh ra nhiều rác phần cứng, dẫn đến tổng điểm Quality bị kéo tụt xuống so với Fixed 50 (chạy im lìm, không bao giờ reset).

Đây là một bài toán kinh điển trong điều khiển: **Switching Cost (Chi phí chuyển đổi trạng thái)**.

### 3. Bước chốt hạ (Bản V8 - Hoàn thiện Hysteresis)

Để dung hòa được cả Tiết kiệm năng lượng và Chất lượng tín hiệu, chúng ta phải "dạy" cho Scheduler bớt nóng vội lại. Khi có biến, lập tức lên HIGH để cứu nét (phản xạ nhanh). Nhưng khi đã ở HIGH, phải đợi tín hiệu **thực sự ổn định và đáng tin cậy** thì mới cho về NORMAL (tránh ping-pong).

Bạn chỉ cần chỉnh lại đúng 1 dòng trong file C:

```c
// V8: Tăng sự kiên nhẫn trước khi hạ cấp
#define SCHED_GOOD_WINDOWS_TO_DOWN 2U  // Tăng từ 1 lên 2
```

**Tại sao lại là 2?**
Khi bạn đổi thành 2, sau cú sốc phần cứng (`1,0,0`), thiết bị cần đạt được `1,0,1` và phải **chờ thêm 4 giây nữa** để đạt thêm một cái `1,0,1` thứ hai. Nếu trong 8 giây đó bạn vẫn để tay êm, nó mới tin tưởng và về `0,2,1`. Việc này sẽ dập tắt hiện tượng Ping-Pong, giảm thiểu "nhiễu chuyển đổi", từ đó điểm Quality Offline của Adaptive sẽ tự động vọt lên lại.