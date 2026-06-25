# 03. Firmware target ESP32-S3

File: `C:\ml\esp32_projects\ppg_hr_tinyml\main\ppg_hr_tinyml.cpp`

## 1. Vai trò của firmware

Firmware target là trung tâm của đồ án. Nó thực hiện bốn lớp công việc:

1. Thu nhận: cấu hình và đọc MAX30102.
2. Xử lý tín hiệu: buffer, lọc, peak, autocorrelation, FFT và đặc trưng.
3. Quyết định: quality gate và scheduler.
4. AI: chạy mô hình MLP INT8 bằng TensorFlow Lite Micro.

Ngoài ra nó còn:

- xuất log;
- xử lý lỗi I2C/FIFO;
- phát GPIO profiling;
- đổi profile 50/100 sps.

## 2. Các thư viện

### ESP-IDF

Các header `driver/gpio.h`, `driver/i2c.h`, `esp_timer.h`, FreeRTOS cung cấp:

- GPIO;
- I2C;
- timer microsecond;
- task và notification;
- vùng critical section.

### ESP-DSP

`dsps_fft2r.h` cung cấp FFT real/complex tối ưu cho ESP32. Firmware dùng FFT 256 điểm để tính các đặc trưng miền tần số.

### TensorFlow Lite Micro

Các lớp:

- `tflite::Model`
- `MicroMutableOpResolver`
- `MicroInterpreter`
- `TfLiteTensor`

cho phép chạy mô hình TFLite mà không cần hệ điều hành hay cấp phát động lớn.

### Model C array

`ppg_hr_mlp_int8.h` khai báo mảng byte của model. File `.c` chứa toàn bộ nội dung `.tflite` dưới dạng:

```cpp
const unsigned char ppg_hr_mlp_int8_tflite[] = {...};
```

Khi build, model trở thành dữ liệu trong firmware flash.

## 3. Chế độ chạy

```cpp
RUN_MODE_FIXED_NORMAL = 0
RUN_MODE_FIXED_HIGH   = 1
RUN_MODE_ADAPTIVE     = 2
```

Macro `RUN_MODE` quyết định binary đang chạy theo mode nào.

### Fixed Normal

- TinyML không khởi tạo.
- State là NORMAL.
- MAX30102 50 sps.
- Không chuyển trạng thái.

### Fixed High

- TinyML được khởi tạo.
- State là HIGH.
- MAX30102 100 sps.
- Không chuyển trạng thái.

### Adaptive

- TinyML được khởi tạo.
- Firmware hiện khởi động ở HIGH.
- Sau đó scheduler có thể chuyển HIGH/NORMAL.

Điểm dễ nhầm: adaptive không khởi động từ NORMAL trong mã hiện tại. `initial_state` mặc định là HIGH và chỉ đổi thành NORMAL cho Fixed Normal.

## 4. Cấu hình dữ liệu

```cpp
kFeatureCount = 16
kModelFs = 64 Hz
kWindowSec = 8
kStrideSec = 2
kWindowSamplesModel = 512
kPsdFftSize = 256
```

Mảng ring tối đa được cấp cho 100 Hz:

```cpp
kWindowSamplesSensor = 100 × 8 = 800
```

Khi NORMAL chỉ dùng 400 mẫu gần nhất. Khi HIGH dùng đủ 800 mẫu.

## 5. Tensor arena

```cpp
kTensorArenaSize = 16 KB
```

Tensor arena là vùng RAM tĩnh cho:

- input/output tensor;
- intermediate activations;
- metadata runtime.

Log mẫu cho biết runtime dùng khoảng 1548 byte, nhưng firmware vẫn dành 16 KB để có dư địa và tránh lỗi cấp phát.

Không nên hiểu 16 KB là kích thước mô hình. Model nằm trong flash; tensor arena là RAM runtime.

## 6. I2C và chân phần cứng

```text
SDA = GPIO8
SCL = GPIO9
I2C clock = 100 kHz
MAX30102 address = 0x57
feature sync = GPIO10
infer sync = GPIO11
```

I2C 100 kHz khá bảo thủ, ưu tiên ổn định hơn tốc độ.

## 7. Profile MAX30102

### NORMAL

```cpp
kProfile50Med:
fifo_config = 0x00
spo2_config = 0x23
LED1 = 0x18
LED2 = 0x18
mode = 0x03
sample_rate = 50
```

### HIGH

```cpp
kProfile100Med:
fifo_config = 0x00
spo2_config = 0x27
LED1 = 0x18
LED2 = 0x18
mode = 0x03
sample_rate = 100
```

`mode = 0x03` là SpO2 mode, tạo hai slot RED và IR.

`spo2_config` thay đổi sample-rate nhưng giữ:

- ADC range tương ứng 4096 nA;
- pulse width 411 µs, 18-bit.

`fifo_config = 0x00` cho thấy firmware hiện tại không cấu hình sample averaging 4. Đây là một sai khác với phụ lục báo cáo.

## 8. Kiểu dữ liệu chính

### `max30102_profile_t`

Đóng gói các thanh ghi và tên profile để `apply_scheduler_state()` có thể chọn profile bằng state.

### `scheduler_state_t`

Hai trạng thái:

```text
0 = NORMAL
1 = HIGH
```

### `quality_fail_reason_t`

Mã nguyên nhân:

- none;
- no contact;
- amplitude fail;
- autocorrelation fail;
- HR range fail;
- consistency fail.

Mã này xuất trong log `reason=...`.

### `window_metrics_t`

Chứa năm giá trị mà scheduler cần:

- `peak_bpm`;
- `ac_best`;
- `ac_best_hr`;
- `std_hp`;
- `ptp_hp`.

## 9. `profiling_pulse_t` và RAII

Constructor đưa GPIO lên 1. Destructor đưa GPIO về 0.

Ví dụ:

```cpp
{
    profiling_pulse_t pulse(GPIO);
    do_work();
}
```

Dù `do_work()` có return sớm, destructor vẫn chạy khi ra khỏi scope. Cách này giảm nguy cơ chân sync bị kẹt ở mức 1.

## 10. Các ngưỡng scheduler

### Quality

```text
std_hp min = 250
ptp_hp min = 1000
ptp_hp max = 35000
ac min = 0.30
```

### Phân tầng dễ/khó

```text
ac hard = 0.20
ac easy = 0.40
difficulty hard = 0.80
difficulty easy = 0.60
```

`difficulty_proxy` được định nghĩa đơn giản:

```text
nếu amplitude_ok:
    difficulty = clamp(1 - ac_best, 0, 1)
ngược lại:
    difficulty = 1
```

Nó không phải đầu ra của một mô hình học máy.

### Hysteresis thời gian

```text
4 bad/gray -> lên HIGH
5 good     -> xuống NORMAL
cooldown   = 3 cửa sổ
dwell      = 15 giây
```

Hysteresis nghĩa là điều kiện đi lên và đi xuống khác nhau. Nó tránh rung trạng thái.

## 11. Biến toàn cục và đồng bộ

### Ring buffer

- `g_ir_ring`: lưu IR.
- `g_ir_head`: vị trí ghi tiếp theo.
- `g_ir_count`: số mẫu hợp lệ.
- `g_since_last_eval`: số mẫu từ lần notify gần nhất.

### State

- `g_sched_state`: state đang áp dụng thật.
- `g_desired_state`: state task AI yêu cầu.
- `g_switch_pending`: main loop chưa áp profile mới.

Việc tách desired/current có lý do: task AI không trực tiếp reset và cấu hình cảm biến trong lúc đang xử lý; nó gửi yêu cầu, main loop áp dụng ở thời điểm FIFO không có mẫu chờ.

### Critical section

Ba mutex kiểu spinlock:

- `g_ring_mux`;
- `g_state_mux`;
- `g_telemetry_mux`.

Chúng bảo vệ dữ liệu được truy cập từ cả main task và AI task.

## 12. Scaler và chuẩn hóa nhãn

Firmware chứa:

- `kScalerMean[16]`;
- `kScalerScale[16]`;
- `kHrMeanBpm`;
- `kHrStdBpm`.

Đây là tham số của lần huấn luyện đã dùng để tạo model đang nhúng. Chúng phải đi theo đúng model.

Không được tùy ý thay file model mới mà giữ scaler cũ.

## 13. Các hàm tiện ích số

### `clampf`

Giới hạn giá trị trong `[lo, hi]`.

### `mean_of`, `std_of`

Tính trung bình và độ lệch chuẩn theo mẫu số `n`, tức population standard deviation.

### `median_of`

Sắp xếp mảng tại chỗ bằng `qsort`. Hàm hiện không nằm trên đường xử lý chính được quan sát.

### `detrend_linear`

Fit đường:

```text
x(t) ≈ slope × t + intercept
```

rồi trừ đường đó khỏi tín hiệu. Nó loại xu hướng tuyến tính toàn cửa sổ.

### `simple_bandpass`

Thực hiện nối tiếp:

- high-pass một cực, cutoff khoảng 0,7 Hz;
- low-pass một cực, cutoff khoảng 5 Hz.

Đây là IIR đơn giản, không giống Butterworth bậc 3 zero-phase trong notebook.

### `robust_zscore`

Tên hàm dễ gây hiểu nhầm. Firmware hiện dùng mean/std thông thường:

```text
(x - mean) / std
```

Trong notebook, `robust_zscore()` dùng median/MAD. Hai cách không tương đương.

## 14. Autocorrelation

`normalized_autocorr()`:

1. Trừ mean.
2. Tính tổng bình phương làm mẫu số.
3. Chỉ duyệt lag ứng với 40-180 BPM.
4. Chọn lag có correlation cao nhất.
5. Đổi lag sang BPM.

```text
lag_min = fs × 60 / 180
lag_max = fs × 60 / 40
HR = 60 / (lag / fs)
```

`ac_best` đo mức lặp lại chu kỳ. `ac_best_hr` là BPM suy ra từ chu kỳ tốt nhất.

## 15. Peak detection

Một điểm là peak khi:

```text
x[i] > x[i-1] và x[i] >= x[i+1]
```

Sau đó kiểm tra:

- khoảng cách tối thiểu;
- prominence tối thiểu.

Firmware dùng BPM tối đa 140 để tạo khoảng cách tối thiểu. Điều này giúp hạn chế đếm hai đỉnh trong cùng một nhịp.

Trong full feature:

```text
min_distance ≈ fs × 60 / 140
prominence = max(0.25 × std, 0.12)
```

Notebook dùng ngưỡng khác. Đây là nguồn domain/pipeline mismatch.

## 16. Resampling

`resample_linear()` ánh xạ đều vị trí đầu ra vào trục đầu vào và nội suy giữa hai mẫu gần nhất.

Nó không có anti-aliasing filter chuyên biệt. Khi giảm 100 Hz xuống 64 Hz, bộ lọc trước đó và dải PPG thấp giúp giảm rủi ro, nhưng về lý thuyết một resampler chuẩn nên có lọc chống alias.

## 17. FFT và đặc trưng phổ

`compute_psd_features()`:

1. Lấy 256 mẫu đầu của cửa sổ đã xử lý.
2. Chạy FFT 256 điểm.
3. Tính `re² + im²`.
4. Tính tổng công suất 0-8 Hz.
5. Tính công suất dải HR 0,7-3,5 Hz.
6. Tính tỷ lệ HR-band/total.
7. Tính spectral entropy.
8. Tìm tần số mạnh nhất trong dải HR và đổi sang BPM.

Lưu ý:

- không thấy áp cửa sổ Hann trong firmware;
- notebook dùng Welch;
- firmware dùng periodogram từ một đoạn 256 mẫu.

Hai biểu diễn phổ không hoàn toàn giống nhau.

## 18. Mười sáu đặc trưng

Theo đúng index:

| Index | Đặc trưng |
|---:|---|
| 0 | mean |
| 1 | std |
| 2 | peak-to-peak |
| 3 | RMS |
| 4 | mean absolute value |
| 5 | mean absolute slope |
| 6 | number of peaks |
| 7 | peak rate per second |
| 8 | mean instantaneous HR |
| 9 | std instantaneous HR |
| 10 | mean peak prominence |
| 11 | best autocorrelation |
| 12 | HR from autocorrelation |
| 13 | PSD HR-band ratio |
| 14 | spectral entropy |
| 15 | dominant BPM |

Sau khi tính, NaN/Inf được đổi thành 0.

## 19. Giao tiếp MAX30102

### Đọc/ghi thanh ghi

- `max30102_write_reg`
- `max30102_read_reg`
- `max30102_read_multi`

### Áp profile

`max30102_apply_profile()`:

1. reset cảm biến;
2. chờ 100 ms;
3. xóa con trỏ FIFO;
4. ghi FIFO config;
5. ghi SpO2 config;
6. ghi dòng LED;
7. ghi mode.

### Đọc FIFO

`max30102_fifo_pending()` dùng chênh lệch con trỏ modulo 32. Nếu overflow, log cảnh báo và xóa counter.

`max30102_read_sample()` đọc 6 byte và mask 18 bit:

```text
RED = first 3 bytes & 0x03FFFF
IR  = next 3 bytes & 0x03FFFF
```

## 20. Đổi state

`apply_scheduler_state()`:

1. Chọn profile 50 hoặc 100 sps.
2. Reset/config MAX30102.
3. Xóa ring buffer.
4. Cập nhật sample rate, window samples, stride samples.
5. Ghi thời điểm chuyển.

Xóa ring buffer tạo một khoảng chờ khoảng 8 giây để tích đủ cửa sổ mới. Đây là chi tiết quan trọng khi giải thích timeline.

## 21. Recovery

Nếu lỗi I2C nhiều lần hoặc hơn 3 giây không có mẫu:

1. probe MAX30102;
2. áp lại profile hiện tại;
3. reset EMA;
4. đóng băng quyết định vài cửa sổ.

Decision freeze tránh scheduler hiểu dữ liệu ngay sau lỗi/recovery là thay đổi chất lượng thật.

## 22. Khởi tạo TinyML

`tinyml_init()`:

1. Đọc schema model.
2. Tạo resolver chỉ chứa `FullyConnected`.
3. Tạo `MicroInterpreter`.
4. `AllocateTensors()`.
5. Lấy input/output.
6. Kiểm tra input/output đều int8.
7. Kiểm tra input có 16 phần tử.
8. In model size, quantization và arena usage.

Resolver chỉ cần FullyConnected vì mô hình sau chuyển đổi chỉ chứa operator Dense/FullyConnected phù hợp.

## 23. Ring buffer và FreeRTOS notification

Main loop là producer mẫu. `inference_task` là consumer cửa sổ.

`xTaskNotifyGive()` nhẹ hơn queue vì chỉ cần báo “có cửa sổ để xử lý”, không truyền toàn bộ dữ liệu. Task tự snapshot ring buffer.

Nếu task xử lý chậm hơn tốc độ notification, notification có thể cộng dồn theo counter, nhưng các cửa sổ snapshot vẫn là cửa sổ mới nhất; đây không phải hàng đợi lưu mọi cửa sổ lịch sử.

## 24. Fast Path chi tiết

`compute_window_metrics(..., false)`:

1. Snapshot.
2. Tính `std_hp`, `ptp_hp` trên dữ liệu ADC.
3. Resample.
4. Detrend.
5. Bandpass.
6. Z-score.
7. Peak detection.
8. `peak_bpm = số đỉnh / 8 × 60`.
9. Autocorrelation.

Điểm hạn chế: `peak_bpm` ở Fast Path dùng số đỉnh trên toàn cửa sổ, không dùng trung bình khoảng IBI. Với 8 giây, độ phân giải tự nhiên là:

```text
60 / 8 = 7,5 BPM
```

Vì vậy log thường thấy 75, 82,5, 90, 97,5 BPM.

## 25. Slow Path chi tiết

`compute_window_metrics(..., true)`:

1. Bật feature GPIO.
2. `extract_ppg_features()`.
3. Lấy metric scheduler trực tiếp từ vector feature.

`run_tinyml_on_features()`:

1. Standardize từng feature.
2. Clamp z-score vào [-6, 6].
3. Quantize bằng scale/zero-point lấy từ tensor input.
4. Saturate vào [-128, 127].
5. Bật infer GPIO.
6. Invoke.
7. Đo thời gian.
8. Dequantize output.
9. Denormalize HR.
10. Clamp 40-180.

## 26. Xuất HR và EMA

### DSP

Phải có hai cửa sổ tốt liên tiếp. EMA:

```text
EMA = 0.35 × HR_mới + 0.65 × EMA_cũ
```

### AI

EMA:

```text
EMA = 0.15 × AI_mới + 0.85 × EMA_cũ
```

AI bị làm mượt mạnh hơn. Log `AI_ASSIST_HR` là EMA chung, còn `raw_ai` là dự đoán AI trước EMA.

Điểm cần hiểu: cùng một biến `g_bpm_ema` được dùng cho cả DSP và AI. Vì vậy output AI có thể phụ thuộc lịch sử output DSP trước đó.

## 27. Log sparse

Cứ khoảng 2 giây:

```text
timestamp_ms,state,profile,quality,diff,red,ir
```

Trong firmware v6 cũ còn có bus voltage/current/power. Firmware hiện tại đã bỏ INA219 khỏi target.

`profile_id_from_state()` trả:

- HIGH -> 0;
- NORMAL -> 1.

Con số này là ID kỹ thuật, không phải sample rate.

## 28. Những điểm mạnh

- Tách main loop và AI task.
- Có recovery và decision freeze.
- Có hysteresis/cooldown/dwell.
- GPIO profiling dùng RAII.
- Không gọi TinyML ở Fast Path.
- Model INT8 và tensor arena tĩnh.
- Chia subject trong notebook, giảm data leakage.

## 29. Những điểm cần thận trọng

1. Tiền xử lý notebook và firmware chưa giống hoàn toàn.
2. Model/scaler trong firmware khác artifact hiện tại.
3. Fast Path peak BPM có độ phân giải 7,5 BPM.
4. Ring buffer bị xóa khi đổi state.
5. Adaptive khởi động ở HIGH.
6. HIGH thay cả sample rate lẫn pipeline, nên chênh lệch năng lượng không chỉ do AI.
7. HR trên prototype chưa có ground truth đồng bộ.
8. `quality_ok` không bao gồm `hr_consistent`; nhưng xuất DSP và luật good có kiểm tra consistency.

## 30. Cách trình bày firmware trong 90 giây

Các ý chính:

- Main loop chuyên thu mẫu và quản lý cảm biến.
- AI task xử lý cửa sổ 8 giây mỗi stride 2 giây.
- NORMAL dùng 50 sps và DSP nhẹ.
- HIGH dùng 100 sps, 16 đặc trưng và MLP INT8.
- Quality gate dùng amplitude, periodicity và HR consistency.
- Scheduler dùng bộ đếm cùng cooldown/dwell.
- GPIO10/11 đánh dấu feature và inference cho DAQ.
- TinyML chỉ là một phần của Slow Path.
