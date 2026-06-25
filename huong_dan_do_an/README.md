# Bộ tài liệu học và bảo vệ đồ án PPG - TinyML thích nghi

## Mục đích

Bộ tài liệu này giải thích toàn bộ đồ án theo hướng người đọc bắt đầu từ số 0. Nội dung không giả định người đọc đã biết AIoT, hệ nhúng, xử lý tín hiệu, cảm biến PPG, TinyML, ESP32, TensorFlow Lite Micro hay đo năng lượng.

Đây không phải bản tóm tắt báo cáo. Mục tiêu là giúp người thực hiện:

1. Hiểu bài toán thực tế mà đồ án đang giải quyết.
2. Hiểu từng linh kiện và từng công nghệ được sử dụng.
3. Theo được đường đi của dữ liệu từ ngón tay đến kết quả nhịp tim.
4. Đọc được hai firmware chính.
5. Đọc được notebook huấn luyện và các notebook phân tích.
6. Phân biệt kết quả đo trực tiếp, kết quả suy ra và kết quả ước lượng.
7. Nhận ra các điểm chưa đồng nhất giữa báo cáo, firmware và artifact.
8. Chuẩn bị trả lời hội đồng thuộc các hướng AIoT, hệ nhúng và AI ứng dụng.

## Thứ tự nên đọc

Đọc theo đúng thứ tự sau:

1. [01 - Nền tảng từ đầu](01-nen-tang-tu-dau.md)
2. [02 - Kiến trúc và luồng end-to-end](02-kien-truc-va-luong-end-to-end.md)
3. [03 - Firmware target ESP32-S3](03-firmware-target-esp32s3.md)
4. [04 - Firmware DAQ ESP32 và INA219](04-firmware-daq-ina219.md)
5. [05 - Notebook PPG-DaLiA và mô hình TinyML](05-notebook-ppg-dalia-va-tinyml.md)
6. [06 - Phân tích macro-level và micro-level](06-phan-tich-macro-va-micro.md)
7. [07 - Đối chiếu báo cáo, mã nguồn và artifact](07-doi-chieu-va-diem-can-lam-ro.md)
8. [08 - Câu hỏi hội đồng và ý chính trả lời](08-cau-hoi-hoi-dong.md)
9. [09 - Quy trình tự thực hành và tái lập](09-quy-trinh-tu-thuc-hanh.md)

## Các file nguồn quan trọng

### Firmware

- Target node: `C:\ml\esp32_projects\ppg_hr_tinyml\main\ppg_hr_tinyml.cpp`
- Mô hình nhúng của target: `C:\ml\esp32_projects\ppg_hr_tinyml\main\ppg_hr_mlp_int8.c`
- DAQ node: `C:\ml\esp32_projects\ina219_daq\main\main.cpp`

### Notebook và thư viện

- `ppg_dalia.ipynb`: tạo dữ liệu đặc trưng, huấn luyện, lượng tử hóa và xuất mô hình.
- `ppg_hr_macro_analysis.ipynb`: phân tích công suất và HR coverage ở mức toàn phiên.
- `ppg_hr_micro_power_analysis.ipynb`: phân tích năng lượng từng burst.
- `ppg_hr_macro_analysis_lib.py`: hàm đọc log và tính chỉ số macro.
- `ppg_hr_micro_analysis_lib.py`: hàm đọc hai log, phát hiện burst và tính năng lượng.

### Dữ liệu và artifact

- `data/ppg-dalia/`: tập dữ liệu PPG-DaLiA.
- `artifacts/ppg_dalia_tinyml/`: mô hình, scaler, metadata và kết quả đánh giá offline.
- `log/pgg_hr_log_v6/`: log được notebook macro hiện tại sử dụng.
- `log/pgg_hr_log_v7/`: log target/DAQ tách rời được notebook micro sử dụng.
- `artifacts/ppg_hr_macro_analysis_v6/`: hình kết quả macro.
- `artifacts/ppg_hr_micro_analysis_v7/`: bảng và hình kết quả micro.

## Bốn câu phải luôn nhớ

1. Đồ án không chỉ làm một mô hình AI dự đoán nhịp tim. Trọng tâm là điều phối mức xử lý theo chất lượng tín hiệu.
2. `NORMAL` và `HIGH/ENHANCED` vừa là hai trạng thái phần mềm, vừa thay đổi cấu hình cảm biến và lượng tính toán.
3. HR coverage chỉ cho biết hệ thống có xuất kết quả hay không; nó không chứng minh kết quả đó chính xác về y sinh.
4. Năng lượng TinyML trong báo cáo là giá trị ước lượng từ thời gian `Invoke()` và công suất đỉnh dư, không phải phép đo trực tiếp riêng phần cứng AI.

## Quy ước tên

Trong firmware, trạng thái mạnh được gọi là `HIGH` hoặc `SCHED_STATE_HIGH`. Trong báo cáo, trạng thái này thường được đổi tên thành `ENHANCED`. Hai tên chỉ cùng một trạng thái.

Tương tự:

- `Fixed High` trong log/notebook tương ứng `Fixed Enhanced` trong báo cáo.
- `Fast Path` tương ứng nhánh xử lý nhẹ ở `NORMAL`.
- `Slow Path` tương ứng nhánh xử lý đầy đủ và TinyML ở `HIGH/ENHANCED`.

## Cách dùng bộ tài liệu

Không nên chỉ đọc thụ động. Sau mỗi tài liệu:

1. Mở file mã nguồn được nhắc tới.
2. Tìm đúng tên hằng số hoặc hàm.
3. Tự mô tả đầu vào, đầu ra và lý do tồn tại của hàm.
4. Mở một log thật để nhận diện dữ liệu mà hàm tạo ra.
5. Trả lời lại các câu hỏi cuối tài liệu mà không nhìn đáp án.
