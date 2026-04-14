# Mapping Hình Và Bảng Cho Báo Cáo Part A / Part B

## Part A

### Hình A.1. Sơ đồ khối tổng thể của hệ thống prototype
- Nguồn: nên tái sử dụng sơ đồ khối bạn đã vẽ trước đó trong bản PDF cũ.
- Nếu cần vẽ lại: xem [report_diagram_guides.md](report_diagram_guides.md).
- Ghi chú: đây là hình sơ đồ, không lấy từ artifact phân tích.

### Hình A.2. Dạng sóng PPG điển hình trong điều kiện đặt tay ổn định
- Dùng trực tiếp: `artifacts/report_assets/part_a_ppg_waveform_stable.png`
- Nguồn dữ liệu: log ổn định của MAX30102 ở cấu hình 50 sps.

### Hình A.3. Hai cấu hình đo năng lượng được sử dụng trong quá trình nghiên cứu
- Không có artifact ảnh sẵn.
- Cần vẽ lại dưới dạng sơ đồ phương pháp.
- Tham khảo ASCII và hướng dẫn tại:
  [report_diagram_guides.md](report_diagram_guides.md)

## Part B

### Hình B.1. Lưu đồ điều phối hai trạng thái NORMAL và HIGH
- Không có artifact ảnh sẵn.
- Cần vẽ lại dưới dạng lưu đồ.
- Tham khảo ASCII và hướng dẫn tại:
  [report_diagram_guides.md](report_diagram_guides.md)

### Hình B.2. Biểu đồ công suất theo thời gian của một phiên adaptive điển hình
- Dùng trực tiếp:
  `artifacts/ppg_hr_macro_analysis_v6/adaptive_log_adaptive_4_timeseries_v6.png`

### Hình B.3. Biểu đồ so sánh công suất trung bình giữa ba chế độ vận hành
- Ưu tiên dùng hình mới đã tạo riêng cho báo cáo:
  `artifacts/report_assets/part_b_power_comparison_v6.png`
- Có thể thay thế bằng dashboard tổng hợp nếu muốn giữ nguyên hình từ notebook:
  `artifacts/ppg_hr_macro_analysis_v6/macro_summary_dashboard_v6.png`

### Hình B.4. Biểu đồ trade-off giữa công suất tiêu thụ và HR coverage
- Dùng trực tiếp:
  `artifacts/report_assets/part_b_tradeoff_v6.png`

### Bảng B.1. Kết quả macro-level của ba chế độ vận hành
- Nên nhập lại thành bảng Word, không chèn ảnh.
- Số liệu dùng:
  - Fixed Normal: `261.78 mW`, `46.23%`
  - Adaptive: `273.21 mW`, `65.81%`
  - Fixed High: `286.94 mW`, `89.31%`
- Nếu cần bảng phụ về occupancy trạng thái adaptive:
  - Adaptive state 0: `263.35 mW`
  - Adaptive state 1: `283.11 mW`

## Gợi ý tái sử dụng hình cũ từ PDF

- Các hình mô tả phần cứng, hình cảm biến MAX30102, INA219, hoặc hình giải thích dữ liệu/dataset trong báo cáo tiến độ cũ có thể tiếp tục tái sử dụng nếu chúng vẫn đúng về mặt nội dung.
- Các hình định lượng liên quan đến kết quả năng lượng và trade-off nên ưu tiên dùng artifact mới từ bộ log cuối, không nên dùng lại hình cũ.
