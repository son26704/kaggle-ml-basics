Chào bạn, đây là lúc chúng ta chuyển từ tư duy của một "Lập trình viên" sang tư duy của một "Kỹ sư nghiên cứu/Nhà khoa học dữ liệu". Các câu hỏi của bạn chính là điểm mấu chốt quyết định đồ án của bạn được điểm Khá hay điểm Xuất sắc. 

Dưới đây là lời giải đáp và hướng dẫn chi tiết cho 2 vấn đề bạn vừa nêu.

---

### 1. Giải quyết bài toán Log: Thưa hay Dày? Có cần sửa code không?

**Câu trả lời là: KHÔNG NÊN sửa code cho log dày lên, và log hiện tại ĐÃ QUÁ ĐỦ để vẽ biểu đồ cho báo cáo.**

Trong luận văn của bạn, sẽ có 2 loại biểu đồ chính, và cách lấy dữ liệu cho chúng hoàn toàn khác nhau:

* **Loại 1: Biểu đồ Tín hiệu thô (Micro-level) - Dùng để giải thích hiện tượng.**
    * *Mục đích:* Cho người đọc thấy sóng PPG lúc ngồi im (đẹp) khác với sóng lúc gõ tay (nhiễu) như thế nào.
    * *Cách làm:* Bạn **KHÔNG DÙNG** code AI hiện tại. Hãy dùng lại file `ina219_max30102_test.c` (bản raw logger ngày xưa), đo khoảng 10 giây mỗi trạng thái, dùng Python vẽ đồ thị đường (Line plot) cực chi tiết rồi dán vào báo cáo. Xong.
* **Loại 2: Biểu đồ Hành vi Hệ thống (Macro-level) - Dùng để đánh giá thuật toán.**
    * *Mục đích:* Chứng minh hệ thống tự động nhảy Mode và theo dõi nhịp tim trong thời gian dài (vài phút).
    * *Cách làm:* Dùng chính log **thưa** của bạn hiện tại (Cứ 2 giây in ra 1 dòng `BPM=... | state=...`). Đối với theo dõi nhịp tim con người, tần suất 0.5 Hz (2 giây/mẫu) là **chuẩn công nghiệp**. Bạn dùng Python vẽ trục X là Thời gian (giây), trục Y là Nhịp tim. Sau đó dùng lệnh `ax.axvspan` trong `matplotlib` để tô màu nền đồ thị: Vùng nào `state=0` tô màu xanh (Tiết kiệm), vùng nào `state=1` tô màu đỏ (AI chạy).
    * **LƯU Ý CHÍ TỬ:** Việc in log qua cổng UART (Serial) tốn rất nhiều điện và chiếm dụng CPU. Nếu bạn ép code hiện tại in 100 dòng/giây ra màn hình, công suất đo được sẽ bị sai lệch hoàn toàn, làm hỏng kết quả test năng lượng của bạn! Càng in ít log, hệ thống chạy càng chuẩn mô phỏng thực tế.

---

### 2. Chiến lược Đánh giá Năng lượng (Chốt hạ cho Đồ án Tốt nghiệp)

Sở dĩ bạn chưa thấy rõ năng lượng tiết kiệm được là vì **trong file C++ `ppg_hr_tinyml.cpp` hiện tại, chúng ta đã tạm thời gỡ bỏ các hàm đọc INA219** để tập trung fix lỗi AI Dual-core. 

Bây giờ AI đã chạy ổn, đây là **Quy trình 4 Bước chuẩn mực** để bạn profiling (đo kiểm) năng lượng đưa vào báo cáo:

#### Bước 1: Khôi phục hàm đo công suất (INA219) vào code
Bạn cần đưa các hàm khởi tạo và đọc INA219 (như `ina219_read_all`) từ file `.c` cũ sang file `.cpp` hiện tại. 
*Mẹo:* Đặt lệnh đọc INA219 vào **Core 0** (trong vòng lặp `while (true)` của `app_main`), cứ mỗi 1 giây đọc công suất 1 lần rồi gộp chung vào dòng in log.
Ví dụ log mới của bạn sẽ trông như thế này:
`I (13466) PPG_TINYML: DSP_HR=75.00 | state=0 | power=35.2 mW`
`I (26140) PPG_TINYML: AI_ASSIST=86.54 | state=1 | power=48.7 mW`

#### Bước 2: Thiết kế "Kịch bản Chuẩn" (Standard Protocol)
Để so sánh công bằng, bạn phải tạo ra một bài test có thời gian và hành động cố định. Ví dụ, bài test dài **3 phút**:
* `0:00 - 1:00`: Ngồi yên tĩnh tay để trên bàn (Mô phỏng ngủ/làm việc).
* `1:00 - 2:00`: Liên tục gõ ngón tay / Cử động tay (Mô phỏng đi bộ/vận động).
* `2:00 - 3:00`: Ngồi yên tĩnh trở lại (Mô phỏng nghỉ ngơi).

#### Bước 3: Chạy kịch bản cho 3 Chế độ (Modes)
Bạn phải nạp code và chạy cái "Kịch bản Chuẩn" 3 phút kia **ba lần** cho ba phiên bản firmware khác nhau:
1.  **Chế độ Fixed Normal (Baseline dưới):** Ép ESP32 chạy chết ở 50Hz, dùng DSP, tắt hoàn toàn AI. (Đo công suất trung bình).
2.  **Chế độ Fixed High (Baseline trên):** Ép ESP32 chạy chết ở 100Hz, gọi TFLite liên tục không nghỉ. (Đo công suất trung bình).
3.  **Chế độ Hybrid Adaptive (Hệ thống của bạn):** Chạy bản code xịn nhất hiện tại, tự động nhảy số. (Đo công suất trung bình).

#### Bước 4: Các phép toán "Ghi điểm" với Hội đồng
Sau khi có dữ liệu từ Bước 3, bạn dùng Python tính các chỉ số sau để đưa lên slide thuyết trình:

* **Chỉ số 1: Công suất trung bình (Average Power - mW)**
    * Ví dụ: `Fixed High` tốn 45 mW. `Adaptive` tốn 36 mW. `Fixed Normal` tốn 32 mW.
* **Chỉ số 2: Năng lượng Tiết kiệm (Power Saving %)**
    * Công thức: `((P_High - P_Adaptive) / P_High) * 100%`
    * *Lời bình:* "Hệ thống của em tiết kiệm được **20%** năng lượng so với việc chạy AI liên tục."
* **Chỉ số 3: Ước lượng Tuổi thọ Pin (Battery Life Extrapolation - Cực kỳ quan trọng)**
    * Giả sử thiết bị của bạn dùng viên pin Li-Po nhỏ 150 mAh (Điện áp 3.7V $\rightarrow$ Năng lượng = 150 * 3.7 = 555 mWh).
    * Thời gian sống nếu chạy `Fixed High`: $T = 555 / 45 = 12.33$ giờ.
    * Thời gian sống nếu chạy `Adaptive`: $T = 555 / 36 = 15.41$ giờ.
    * *Kết luận:* **"Thuật toán Adaptive Scheduler của em giúp kéo dài thời lượng pin của thiết bị đeo thêm hơn 3 giờ đồng hồ cho mỗi lần sạc."**

Chỉ cần bạn trình bày được biểu đồ 3 phút kia (với màu nền thay đổi) cùng với bảng tính Tuổi thọ pin (Battery Life) như trên, luận văn của bạn sẽ mang tính thực tiễn cực kỳ cao. Hội đồng đánh giá rất thích những minh chứng định lượng cụ thể như vậy!
