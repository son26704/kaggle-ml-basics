Thật tuyệt vời! Việc chuyển sang Dual-Core đã phát huy tác dụng ngay lập tức: **Lỗi `FIFO overflow=24` (tràn bộ đệm) đã biến mất hoàn toàn** trong suốt quá trình chạy bình thường. Lõi 0 (Core 0) đã làm rất tốt việc đọc I2C liên tục, trong khi Lõi 1 (Core 1) xử lý AI.

Hiện tại, bạn đang gặp 2 hiện tượng vật lý và phần cứng rất thú vị. Hãy cùng "bắt bệnh" và xử lý triệt để:

---

### 1. Tại sao ấn mạnh tay thì Nhịp tim (BPM) lại tăng vọt và chạm trần (163.43)?

Bạn đã tự đưa ra giả thuyết rất chuẩn xác: **"Do ấn mạnh"**.
Bản chất của cảm biến PPG (MAX30102) là đo **sự thay đổi thể tích mạch máu** (Photoplethysmography).
* **Khi chạm nhẹ:** Mạch máu giãn nở tự nhiên, tạo ra đồ thị hình sin mượt mà với 1 đỉnh duy nhất cho mỗi nhịp đập. Bộ đếm đỉnh (`peak_rate`) đo được khoảng 1.0 - 1.5 đỉnh/giây (tương đương 60 - 90 BPM).
* **Khi ấn mạnh:** Bạn ép xẹp các mao mạch. Máu khó lưu thông hơn, tín hiệu đập chính bị suy giảm, đồng thời nhiễu cơ học và "nút thắt tâm trương" (Dicrotic Notch) bị khuếch đại lên trông giống như một đỉnh thứ hai.
* **Hậu quả ở Firmware:** Bộ đếm đỉnh bị lừa, đếm thành 2-3 đỉnh/giây (`peak_rate` vọt lên 2.750 như trong log). Mô hình TinyML thấy feature `peak_rate` quá cao liền dự đoán nhịp tim vọt lên 140-160 BPM. Giá trị `y_q = 127` chính là giới hạn kịch trần của kiểu dữ liệu `int8_t` (tương đương 163.43 BPM).

**Giải pháp:** Đây không phải lỗi code, đây là **đặc tính sinh lý**. Lời khuyên cho thiết bị Wearable thực tế là phải thiết kế cơ khí (vỏ case, dây đeo) sao cho cảm biến chỉ áp vừa đủ nhẹ lên da, không thít chặt.

---

### 2. Tại sao LED đột ngột tắt và hệ thống bị treo?

Hãy nhìn kỹ vào đoạn log cuối cùng của bạn:
`E (120638) PPG_TINYML: max30102_fifo_pending(491): read ovf fail`
`W (122638) PPG_TINYML: No new MAX30102 samples for >3s`

Điều thú vị ở đây là sau khi báo lỗi đọc 1 lần, hệ thống **không báo lỗi I2C nữa**, mà chỉ báo "Không có mẫu mới" (No new samples).
**Lý do:** I2C không hề bị đứt dây hay treo cứng. Cảm biến vẫn phản hồi I2C (ACK), nhưng số lượng mẫu trong bộ đệm (`pending`) liên tục trả về `0`. Tại sao?
Vì hiện tượng sụt áp nhỏ hoặc nhiễu điện trên dây cắm breadboard đã khiến chip MAX30102 bị **Reset cứng (Brown-out reset)**. Khi MAX30102 bị reset, thanh ghi `MODE_CONFIG` sẽ trở về giá trị mặc định là `0x00` (Chế độ Ngủ - Sleep Mode). Cảm biến đi ngủ nên LED tắt và không thèm đo dữ liệu mới nữa!

**Cách khắc phục (Auto-Wakeup Firmware):**
Hiện tại, code của bạn chỉ gọi hàm `max30102_recover()` khi I2C bị lỗi đọc (NACK). Nhưng ở đây I2C vẫn đọc được, chỉ là đọc ra số 0. Chúng ta cần "đá" cho cảm biến tỉnh dậy nếu thấy nó lười biếng quá 3 giây.

Bạn hãy sửa đoạn code trong `app_main()` (Vòng lặp `while (true)`) lại như sau:

```cpp
        // ... (phần đầu vòng lặp giữ nguyên)
        if (pending == 0)
        {
            int64_t now = esp_timer_get_time();
            // Nếu quá 3 giây mà không có data -> Chắc chắn cảm biến đã đi ngủ hoặc bị reset
            if (now - last_activity_us > 3000000)
            {
                ESP_LOGW(TAG, "No new MAX30102 samples for >3s. Sensor might be sleeping/reset!");
                
                // ÉP CẢM BIẾN KHỞI ĐỘNG LẠI TỪ ĐẦU
                max30102_recover(); 
                
                last_activity_us = esp_timer_get_time(); // Reset lại bộ đếm thời gian
            }
            vTaskDelay(pdMS_TO_TICKS(2));
            continue;
        }
        // ... (phần for loop đọc data giữ nguyên)
```

### Tổng kết

Chỉ cần thêm dòng `max30102_recover();` vào đúng chỗ `pending == 0` trễ quá 3 giây, thiết bị của bạn sẽ trở nên cực kỳ "trâu bò" (Robust). Bất kể dây lỏng, nhiễu điện hay cảm biến lăn ra ngủ, ESP32 sẽ tự động cấu hình lại thanh ghi và bật LED sáng trở lại để chạy tiếp mà không cần bạn phải bấm nút Reset trên board.
