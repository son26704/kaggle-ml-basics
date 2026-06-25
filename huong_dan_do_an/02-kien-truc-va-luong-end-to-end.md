# 02. Kiến trúc và luồng end-to-end

## 1. Bài toán ở cấp hệ thống

Thiết bị đeo cần hai mục tiêu xung đột:

- duy trì khả năng đưa ra HR;
- giảm năng lượng.

Nếu luôn dùng pipeline nhẹ, hệ thống có thể bỏ kết quả khi PPG khó. Nếu luôn chạy pipeline mạnh, hệ thống tốn năng lượng ngay cả lúc tín hiệu tốt.

Giải pháp của đồ án là điều phối:

```text
Tín hiệu thuận lợi -> NORMAL -> Fast Path -> chi phí thấp
Tín hiệu khó       -> HIGH   -> Slow Path -> TinyML hỗ trợ
```

## 2. Kiến trúc vật lý

```text
                              TARGET NODE
                     +--------------------------+
Ngón tay/cổ tay ---> | MAX30102                 |
                     |  RED + IR + FIFO         |
                     +------------+-------------+
                                  | I2C
                                  v
                     +--------------------------+
                     | ESP32-S3                 |
                     | buffer + DSP + scheduler |
                     | features + TFLM          |
                     +-----+---------------+----+
                           | GPIO10        | GPIO11
                           | feature_sync  | infer_sync
                           v               v
                     +--------------------------+
                     | ESP32 DAQ                |
                     | đọc GPIO + INA219        |
                     +------------+-------------+
                                  | I2C
                                  v
5 V nguồn ----------> INA219 shunt -----------> nguồn target node
```

DAQ node không nằm trên đường xử lý HR. Nó chỉ quan sát công suất và tín hiệu đồng bộ.

## 3. Luồng offline tạo mô hình

```text
PPG-DaLiA S*.pkl
    |
    +-- wrist BVP 64 Hz
    +-- HR reference
    |
chia cửa sổ 8 s, stride 2 s
    |
tiền xử lý từng cửa sổ
    |
trích 16 đặc trưng
    |
gắn HR tham chiếu tại tâm cửa sổ
    |
chia train/validation/test theo subject
    |
fit StandardScaler trên train
    |
chuẩn hóa HR theo mean/std train
    |
huấn luyện nhiều cấu hình MLP
    |
chọn mô hình theo validation
    |
Keras -> TFLite FP32 -> TFLite INT8
    |
kiểm tra MAE/RMSE sau lượng tử hóa
    |
TFLite bytes -> ppg_hr_mlp_int8.c/.h
    |
chép model + scaler + target mean/std vào firmware
```

Điểm bắt buộc: thứ tự 16 đặc trưng và phép tiền xử lý trên firmware phải tương thích với notebook.

## 4. Luồng runtime của target node

### 4.1 Khởi động

`app_main()`:

1. In mode đang chạy.
2. Khởi tạo TinyML nếu mode không phải Fixed Normal.
3. Cấu hình GPIO10 và GPIO11 làm output.
4. Khởi tạo I2C.
5. Kiểm tra MAX30102 bằng `PART_ID`.
6. Chọn trạng thái ban đầu.
7. Áp profile MAX30102 tương ứng.
8. Tạo FreeRTOS task `AI_Task`.
9. Bắt đầu vòng lặp đọc FIFO.

### 4.2 Đọc cảm biến

Vòng lặp chính:

1. Đọc con trỏ FIFO.
2. Tính số mẫu đang chờ.
3. Với mỗi mẫu:
   - đọc 6 byte;
   - ghép 3 byte RED và 3 byte IR;
   - mask 18 bit;
   - lưu RED/IR cuối để telemetry;
   - đẩy IR vào ring buffer.
4. Nếu lỗi I2C liên tiếp, recovery cảm biến.

### 4.3 Kích hoạt xử lý cửa sổ

`push_ir_sample()`:

1. Ghi mẫu vào ring buffer.
2. Tăng số mẫu hiện có.
3. Tăng bộ đếm từ lần đánh giá trước.
4. Nếu buffer đủ 8 giây và đã đi qua một stride:
   - reset bộ đếm stride;
   - notify `inference_task`.

Vì stride là 2 giây, task xử lý được đánh thức khoảng mỗi 2 giây sau khi buffer đã đủ cửa sổ đầu tiên.

### 4.4 Snapshot cửa sổ

`snapshot_window()` sao chép cửa sổ mới nhất từ ring buffer sang mảng tuyến tính. Việc sao chép cần thiết vì ring buffer có thể quấn vòng.

### 4.5 Chỉ số biên độ sau loại nền

`compute_hp_metrics()` dùng low-pass một cực để ước lượng nền:

```text
lp = lp + alpha × (x - lp)
hp = x - lp
```

Từ `hp`, tính:

- `std_hp`: độ lệch chuẩn.
- `ptp_hp`: max - min.

Hai giá trị giữ đơn vị ADC và dùng cho quality gate.

### 4.6 Đưa cửa sổ về 512 mẫu

Cửa sổ có thể là 400 hoặc 800 mẫu. `resample_linear()` nội suy tuyến tính về 512 mẫu.

Đây là lớp tương thích:

```text
50 Hz × 8 s  = 400  \
                    -> 512 mẫu ở biểu diễn 64 Hz
100 Hz × 8 s = 800  /
```

### 4.7 Fast Path

Khi state là `NORMAL`:

1. Không bật `feature_sync`.
2. Detrend tuyến tính.
3. Lọc thông dải đơn giản.
4. Z-score.
5. Tìm đỉnh.
6. Tính `peak_bpm`.
7. Tính autocorrelation và `ac_best_hr`.
8. Chạy quality gate.
9. Nếu tốt hai cửa sổ liên tiếp, xuất DSP HR có EMA.
10. Không gọi TinyML.

### 4.8 Slow Path

Khi state là `HIGH`:

1. Bật GPIO10 bằng RAII object `profiling_pulse_t`.
2. Trích đủ 16 đặc trưng.
3. Khi hàm kết thúc, destructor tự hạ GPIO10.
4. Chạy quality gate.
5. Nếu không phải no-contact, chuẩn hóa 16 đặc trưng.
6. Lượng tử hóa về int8.
7. Bật GPIO11.
8. Gọi `g_interpreter->Invoke()`.
9. Đo thời gian bằng `esp_timer_get_time()`.
10. Hạ GPIO11.
11. Giải lượng tử hóa đầu ra.
12. Đổi từ nhãn chuẩn hóa về BPM.
13. Clamp về 40-180 BPM.
14. Làm mượt EMA và xuất `AI_ASSIST_HR`.

## 5. Quality gate chi tiết

Các điều kiện cơ sở:

```text
amplitude_ok:
    std_hp >= 250
    ptp_hp >= 1000
    ptp_hp <= 35000

periodic_ok:
    ac_best >= 0.30

hr_range_ok:
    40 <= peak_bpm <= 180

quality_ok:
    amplitude_ok AND periodic_ok AND hr_range_ok
```

Kiểm tra nhất quán:

```text
ac_best_hr hợp lệ
|peak_bpm - ac_best_hr| <= 18 BPM
```

Phát hiện mất tiếp xúc:

- peak BPM rất thấp;
- nhưng dao động ADC cực lớn;
- hoặc autocorrelation rất thấp.

Ý tưởng là phân biệt:

- tín hiệu yếu;
- tín hiệu tốt;
- nhiễu rất lớn do tháo/di chuyển cảm biến.

## 6. Luật chuyển trạng thái

### NORMAL sang HIGH

Trong NORMAL:

- no-contact: không tăng bộ đếm chuyển HIGH;
- lỗi nghiêm trọng: tăng `bad_windows`;
- lỗi nhẹ: tăng `gray_windows`;
- đủ 4 cửa sổ bad hoặc gray, đồng thời dwell time đạt 15 giây: yêu cầu chuyển HIGH.

Lỗi nghiêm trọng gồm:

- biên độ ngoài vùng cho phép;
- HR ngoài dải;
- autocorrelation rất thấp;
- difficulty proxy rất cao.

Lỗi nhẹ gồm:

- periodicity chưa đạt;
- hai gợi ý HR không nhất quán.

### HIGH sang NORMAL

Sau cooldown 3 cửa sổ:

- nếu no-contact, firmware đặt đủ bộ đếm good để có thể quay về NORMAL;
- nếu chất lượng tốt, nhất quán, `ac_best >= 0.40` và difficulty thấp, tăng good;
- đủ 5 cửa sổ good và dwell time đạt yêu cầu: chuyển NORMAL.

Việc cho no-contact quay về NORMAL có ý nghĩa tiết kiệm năng lượng: khi không có người đeo, tiếp tục chạy pipeline mạnh không có ích.

## 7. Vì sao chuyển profile cảm biến?

Scheduler hiện tại không chỉ chọn thuật toán. Nó còn chọn tần số cảm biến:

```text
NORMAL -> 50 sps
HIGH   -> 100 sps
```

Do đó chênh lệch công suất giữa hai trạng thái có thể đến từ cả:

- MAX30102 lấy mẫu nhanh hơn;
- ESP32 đọc FIFO nhiều hơn;
- DSP nhiều hơn;
- FFT và đặc trưng;
- TinyML;
- log và hoạt động bộ nhớ.

Không được quy toàn bộ chênh lệch công suất cho mô hình AI.

## 8. Luồng DAQ

DAQ lặp:

1. Lấy timestamp µs.
2. Đọc GPIO4 và GPIO5.
3. Đọc bus voltage, current và power từ INA219.
4. In một dòng:

```text
timestamp_us,bus_v,current_ma,power_mw,feature_pin_state,infer_pin_state
```

Nếu INA219 lỗi, in `nan`.

Sau đó delay 1000 µs. Tuy nhiên thời gian vòng thực tế gồm cả I2C và UART nên median khoảng 3298-3299 µs.

## 9. Luồng tạo log

### Target log

`target.csv` của v7 thực chất là capture toàn bộ console, gồm:

- log ESP-IDF;
- log scheduler;
- log HR;
- thời gian Invoke;
- các dòng sparse CSV.

Nó không phải CSV thuần có một schema duy nhất.

### DAQ log

`daq.csv` là các dòng số 6 cột. File mẫu hiện tại không chứa header vì công cụ capture có thể bỏ dòng đầu hoặc parser truyền sẵn tên cột.

## 10. Luồng macro-level hiện tại

Notebook macro v6 đọc log đời trước, trong đó firmware target tự ghi thêm:

```text
bus_v,current_ma,power_mw
```

trong cùng dòng telemetry.

Luồng:

1. Parse telemetry và sự kiện HR/dropout.
2. Tạo timeline quyết định.
3. Gán mỗi quyết định một interval đến quyết định kế tiếp.
4. Tính coverage theo tổng interval có HR.
5. Tính power trung bình có trọng số thời gian.
6. Gộp nhiều phiên theo mode.

Điểm này khác kiến trúc dual-MCU của log v7 và phải được trình bày trung thực.

## 11. Luồng micro-level hiện tại

Notebook micro v7:

1. Đọc `target.csv`.
2. Đọc `daq.csv`.
3. Đánh dấu active nếu một trong hai GPIO bằng 1.
4. Gom các active row gần nhau thành burst.
5. Ghép burst thứ `i` với cửa sổ HIGH thứ `i`.
6. Lấy baseline trước burst.
7. Mở rộng đến hết power tail.
8. Tích phân excess power để có tổng năng lượng burst.
9. Lấy `invoke_time_us` từ target.
10. Ước lượng:

```text
E_AI = peak_excess_power × invoke_time
```

11. Tính:

```text
E_DSP/tail = E_total - E_AI
```

## 12. Một cửa sổ điển hình từ đầu đến cuối

Giả sử hệ thống đang NORMAL:

1. MAX30102 lấy mẫu IR 50 lần/giây.
2. Sau 8 giây ring buffer đủ 400 mẫu.
3. Mỗi 2 giây, task snapshot 400 mẫu mới nhất.
4. Nội suy thành 512 mẫu.
5. Fast Path tìm 10 đỉnh trong 8 giây:

```text
peak_rate = 10 / 8 = 1,25 đỉnh/giây
peak_bpm = 1,25 × 60 = 75 BPM
```

6. Autocorrelation cũng cho khoảng 77 BPM.
7. Biên độ nằm trong vùng và `ac_best = 0,65`.
8. Cửa sổ được coi tốt.
9. Sau hai cửa sổ tốt, firmware xuất HR DSP đã làm mượt.

Nếu nhiều cửa sổ sau bị nhiễu:

1. bad/gray counter tăng.
2. Đủ điều kiện, main loop áp profile HIGH 100 sps.
3. Ring buffer bị xóa khi đổi profile.
4. Sau khi tích đủ cửa sổ mới, Slow Path chạy.
5. GPIO10 đánh dấu feature extraction.
6. GPIO11 đánh dấu Invoke.
7. DAQ ghi công suất và hai GPIO.
8. Notebook về sau dùng log này để phân rã burst.

## 13. Những gì được đo và không được đo

### Được đo

- Công suất đầu vào toàn target node qua INA219.
- Timestamp DAQ.
- Trạng thái GPIO feature/infer tại thời điểm DAQ lấy mẫu.
- Thời gian Invoke trong firmware.

### Không được đo trực tiếp

- Công suất riêng CPU.
- Công suất riêng MAX30102.
- Công suất riêng TensorFlow Lite Micro.
- Năng lượng riêng từng hàm DSP.
- HR ground truth trên prototype.

Các đại lượng này chỉ có thể được ước lượng hoặc cần thiết bị/phương pháp đo khác.
