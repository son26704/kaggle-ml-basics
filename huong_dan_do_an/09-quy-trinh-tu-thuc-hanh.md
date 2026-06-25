# 09. Quy trình tự thực hành và tái lập

## 1. Mục tiêu

Sau khi làm hết tài liệu này, bạn phải tự:

- build hai firmware;
- nhận diện wiring;
- đọc log;
- chạy notebook;
- giải thích một burst;
- kiểm tra model/scaler;
- trình bày giới hạn.

## 2. Bước 1 - Vẽ lại hệ thống bằng tay

Không nhìn báo cáo, tự vẽ:

- nguồn 5 V;
- INA219;
- target ESP32-S3;
- MAX30102;
- DAQ ESP32;
- I2C;
- GPIO10/11 sang GPIO4/5;
- hai cổng UART về máy tính.

Nếu không vẽ được, quay lại tài liệu 01-02.

## 3. Bước 2 - Đọc firmware target theo thứ tự

Không đọc từ dòng 1 đến cuối một cách thụ động. Theo thứ tự:

1. enum mode/state.
2. profile MAX30102.
3. scheduler constants.
4. `app_main`.
5. `max30102_fifo_pending`.
6. `max30102_read_sample`.
7. `push_ir_sample`.
8. `compute_window_metrics`.
9. `inference_task`.
10. `run_tinyml_on_features`.
11. `apply_scheduler_state`.

Với mỗi hàm, ghi:

```text
Input:
Output:
Biến global bị đọc:
Biến global bị ghi:
Chạy ở task nào:
Có ảnh hưởng power không:
```

## 4. Bước 3 - Tự decode một log target

Mở:

```text
log/pgg_hr_log_v7/adaptive/adaptive_1/target.csv
```

Tìm các mốc:

1. boot;
2. model init;
3. HIGH;
4. cửa sổ no-contact;
5. DSP_HOLD;
6. Invoke;
7. AI_ASSIST;
8. chuyển NORMAL;
9. bốn cửa sổ xấu;
10. chuyển HIGH.

Tự lập timeline hai cột:

```text
timestamp | giải thích
```

## 5. Bước 4 - Tự tính một peak BPM

Chọn cửa sổ log có:

```text
peak_bpm = 82,5
```

Vì cửa sổ 8 giây:

```text
số peak = 82,5 × 8 / 60 = 11 peak
```

Làm lại với 75, 90 và 97,5 BPM để hiểu độ phân giải.

## 6. Bước 5 - Tự giải thích quantization

Từ log model:

```text
input scale = 0,04944235
input zero point = -40
```

Giả sử một feature sau standardize là 1,0:

```text
q = round(1 / 0,04944235 - 40)
  ≈ round(-19,78)
  = -20
```

Làm với feature -2 và 5. Kiểm tra clamp [-128,127].

## 7. Bước 6 - Chạy notebook PPG-DaLiA theo khối

Không Run All ngay. Chạy:

1. import/dependency;
2. locate dataset;
3. preprocessing function;
4. feature extraction;
5. tạo `feature_df`;
6. kiểm tra subject;
7. RF baseline;
8. TinyML split;
9. candidate training;
10. conversion;
11. INT8 verification;
12. export.

Sau mỗi bước ghi shape:

```text
feature_df:
model_df:
X_fit:
X_val:
X_test:
```

## 8. Bước 7 - Kiểm tra không leakage

In subject list của fit/val/test. Bảo đảm giao ba tập rỗng.

Nếu cùng subject xuất hiện ở hai tập, kết quả phải bị xem lại.

## 9. Bước 8 - Kiểm tra artifact-model

Tạo một manifest gồm:

```text
model SHA-256
model byte size
feature columns
feature scaler SHA-256
target mean/std
input quant scale/zp
output quant scale/zp
training date
git commit
```

So với log firmware.

Mục tiêu là trả lời chắc chắn:

```text
Binary đang flash dùng chính xác model nào?
```

## 10. Bước 9 - Golden feature test

Đây là việc kỹ thuật nên ưu tiên nhất.

### Quy trình đề xuất

1. Chọn 5-10 cửa sổ PPG 512 mẫu.
2. Lưu raw float vào file/header.
3. Chạy Python, xuất 16 feature.
4. Chạy cùng vector trong C++ host hoặc ESP32.
5. So từng feature:

```text
absolute error
relative error
```

6. Nếu lệch lớn, xác định do filter, peak hay PSD.

### Hai lựa chọn sửa

- Port chính xác pipeline Python sang C++.
- Viết pipeline Python mô phỏng đúng firmware rồi retrain model.

Lựa chọn thứ hai thường thực tế hơn cho embedded deployment.

## 11. Bước 10 - Tự phân tích DAQ

Mở `daq.csv`.

Tự tính 10 khoảng:

```text
dt_i = timestamp_(i+1) - timestamp_i
```

Tính median và so khoảng 3299 µs.

Tìm row `feature=1` hoặc `infer=1`. Quan sát power trước/trong/sau.

## 12. Bước 11 - Tự tính năng lượng một burst

Chọn burst đơn giản:

1. baseline median trước burst;
2. excess power từng row;
3. nhân dt;
4. cộng;
5. đổi sang µJ.

Sau đó lấy `invoke_time_us` target:

```text
E_AI = peak excess × invoke time / 1000
```

So với output `burst_summary_v7.csv`.

## 13. Bước 12 - Sensitivity analysis

Chạy micro analysis với các bộ tham số:

```text
baseline_window: 10, 20, 40
min_excess: 5, 8, 12 mW
settle_count: 1, 2, 3
merge_gap: 1, 3, 5 row
```

Nếu tỷ lệ AI vẫn quanh vài phần trăm, kết luận định tính mạnh hơn.

## 14. Bước 13 - Reproduce macro

Chạy notebook macro và xác nhận:

```text
261,78
273,21
286,94
46,23
65,81
89,31
```

Sau đó kiểm tra state power hiện tại và chọn số chính thức.

## 15. Bước 14 - Phân biệt protocol

Tạo bảng:

| Protocol | Firmware | Power source | Log | Dùng cho |
|---|---|---|---|---|
| v6 | target tự đo | INA219 trên target | một console log | macro |
| v7 | DAQ riêng | INA219 trên ESP32 DAQ | target.csv + daq.csv | micro |

Đưa bảng này vào ghi chú bảo vệ.

## 16. Bước 15 - Thử ba mode

Build target ba lần với:

```text
RUN_MODE=0
RUN_MODE=1
RUN_MODE=2
```

Với mỗi mode, xác nhận log:

- model có init không;
- profile ban đầu;
- state có chuyển không;
- GPIO có pulse không.

## 17. Bước 16 - Kiểm tra wiring và nguồn

Trước cấp nguồn:

- common ground;
- đúng SDA/SCL;
- đúng VIN+/VIN-;
- không cấp nhầm 5 V vào GPIO;
- target và DAQ không cùng đi qua shunt nếu chỉ muốn đo target;
- kiểm tra địa chỉ I2C.

## 18. Bước 17 - Hiệu chuẩn INA219

Dùng tải biết trước hoặc đồng hồ:

1. đo bus voltage bằng multimeter;
2. đo current bằng ammeter;
3. so INA219;
4. tính bias và gain;
5. lặp ở nhiều mức tải.

Ghi sai số thiết bị vào báo cáo.

## 19. Bước 18 - Thí nghiệm HR có ground truth

Để khắc phục hạn chế lớn nhất:

1. Đồng thời đeo/đo bằng thiết bị tham chiếu.
2. Đồng bộ thời gian bằng marker.
3. Thu PPG MAX30102 và HR reference.
4. Tính MAE/RMSE/Bland-Altman.
5. Phân theo trạng thái đứng yên/chuyển động.
6. So DSP, AI và final output.

Nếu không có ECG, ít nhất dùng chest strap tin cậy và nêu giới hạn.

## 20. Bước 19 - Luyện bảo vệ

Chuẩn bị ba phiên bản:

### 30 giây

- bài toán;
- giải pháp;
- kết quả chính;
- giới hạn.

### 2 phút

- kiến trúc;
- scheduler;
- TinyML;
- đo năng lượng;
- kết quả.

### 5 phút kỹ thuật

- full data flow;
- quality equations;
- model pipeline;
- energy method;
- caveat.

## 21. Bước 20 - Tự phản biện

Tự trả lời:

1. Nếu bỏ TinyML thì coverage thay đổi thế nào?
2. Nếu giữ 100 sps nhưng bỏ feature/AI thì power ra sao?
3. Nếu chỉ đổi 50/100 sps thì đóng góp scheduler còn gì?
4. Kết quả có lặp lại ở người khác không?
5. Nếu model sai nhưng luôn output, coverage có tăng giả không?
6. Nếu baseline power drift, energy burst sai thế nào?
7. Nếu mất một burst DAQ, ghép index sai ra sao?
8. Nếu feature C++ lệch Python, scaler còn ý nghĩa không?

## 22. Thứ tự ưu tiên sửa trước bảo vệ

### Mức 1 - Bắt buộc

1. Chốt model/scaler firmware.
2. Chốt source tạo log.
3. Sửa sai khác MAX30102 trong báo cáo.
4. Đồng bộ state power.
5. Nói rõ coverage không phải accuracy.

### Mức 2 - Rất nên làm

1. Golden feature test.
2. Sensitivity analysis micro.
3. Bảng protocol v6/v7.
4. Manifest artifact.

### Mức 3 - Nếu còn thời gian

1. Thu HR ground truth prototype.
2. Thiết bị đo power nhanh hơn.
3. Repeated statistical trials.
4. Retrain theo firmware-exact preprocessing.

## 23. Tiêu chí bạn đã hiểu đồ án

Bạn đã hiểu khi có thể, không nhìn tài liệu:

- vẽ hệ thống;
- giải thích một mẫu đi qua toàn pipeline;
- nói rõ 16 feature;
- giải thích state transition;
- tính quantization đơn giản;
- tính một burst energy;
- chỉ ra ba mismatch;
- nói giới hạn mà không làm mất giá trị đồ án;
- phân biệt kết quả offline, macro và micro.
