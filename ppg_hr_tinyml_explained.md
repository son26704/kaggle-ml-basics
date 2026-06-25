# Giải thích chi tiết firmware `ppg_hr_tinyml.cpp`

Tài liệu này giải thích file `c:\ml\esp32_projects\ppg_hr_tinyml\main\ppg_hr_tinyml.cpp` theo hướng dễ hiểu, đi từ tổng quan hệ thống đến từng khối code quan trọng. Đây là firmware chính của target node trong đồ án: ESP32-S3 đọc cảm biến MAX30102, xử lý tín hiệu PPG, chạy scheduler NORMAL/HIGH, gọi model TinyML khi cần, và phát tín hiệu sync để DAQ node đo năng lượng.

## Vai Trò Của File Này Trong Đồ Án

File này chạy trên ESP32-S3 target node. Nó là phần firmware thật của hệ thống, khác với notebook `ppg_dalia.ipynb` là phần huấn luyện offline trên máy tính.

Nhiệm vụ chính của firmware:

1. Khởi tạo TensorFlow Lite Micro và model MLP INT8.
2. Khởi tạo I2C và cảm biến MAX30102.
3. Đọc liên tục mẫu RED/IR từ FIFO của MAX30102.
4. Đưa kênh IR vào ring buffer.
5. Cứ đủ một stride thì đánh thức task xử lý.
6. Task xử lý lấy một cửa sổ PPG mới nhất.
7. Tính các chỉ số chất lượng tín hiệu.
8. Quyết định giữ/chuyển trạng thái `NORMAL` hoặc `HIGH`.
9. Ở `NORMAL`: chỉ chạy DSP nhẹ và công bố HR từ DSP nếu chất lượng đủ.
10. Ở `HIGH`: trích đủ 16 feature, gọi TinyML MLP INT8, công bố HR từ AI-assisted output.
11. Phát GPIO10 khi chạy feature extraction và GPIO11 khi gọi `Invoke()` để DAQ đo năng lượng.
12. In log CSV thưa để notebook phân tích macro-level.

Luồng tổng thể:

```text
MAX30102 FIFO
  -> app_main đọc RED/IR qua I2C
  -> lấy IR đưa vào ring buffer
  -> đủ stride thì notify inference_task
  -> inference_task snapshot cửa sổ mới nhất
  -> tính std_hp, ptp_hp, peak_bpm, ac_best, ac_best_hr
  -> quality gate
  -> scheduler NORMAL/HIGH
  -> NORMAL: DSP HR
  -> HIGH: feature extraction + TinyML Invoke
  -> log HR/state/quality
  -> GPIO sync cho DAQ
```

## Tư Duy Kiến Trúc

Firmware được tổ chức thành hai phần chạy song song:

1. `app_main`: vòng lặp đọc cảm biến, giữ luồng mẫu không bị gián đoạn.
2. `inference_task`: task FreeRTOS xử lý tín hiệu, scheduler và TinyML.

Lý do tách như vậy:

- Đọc cảm biến cần đều đặn, nếu bị block bởi TinyML hoặc feature extraction thì FIFO MAX30102 có thể overflow.
- Xử lý tín hiệu và model có thể nặng hơn, nên để trong task riêng.
- ESP32-S3 có nhiều core, firmware pin `inference_task` vào core 1 để giảm tranh chấp với luồng đọc cảm biến.

## Include Và Thư Viện

Đầu file:

```cpp
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
```

Đây là thư viện C cơ bản:

- `math.h`: `sqrtf`, `fabsf`, `logf`, `lrintf`.
- `stdio.h`: `printf`.
- `stdlib.h`: `qsort`.
- `string.h`: `memcpy`.

Nhóm ESP-IDF:

```cpp
#include "driver/gpio.h"
#include "driver/i2c.h"
#include "esp_check.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "dsps_fft2r.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
```

Ý nghĩa:

- `driver/gpio.h`: cấu hình GPIO10/GPIO11 sync.
- `driver/i2c.h`: giao tiếp MAX30102 qua I2C.
- `esp_check.h`: macro `ESP_RETURN_ON_ERROR`.
- `esp_err.h`: kiểu lỗi `esp_err_t`.
- `esp_log.h`: log `ESP_LOGI/W/E`.
- `esp_timer.h`: timestamp microsecond.
- `dsps_fft2r.h`: FFT của ESP-DSP để tính PSD feature.
- `freertos`: task, delay, notify.

Nhóm TensorFlow Lite Micro:

```cpp
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/schema/schema_generated.h"
```

Đây là runtime TinyML trên vi điều khiển.

Cuối cùng:

```cpp
#include "ppg_hr_mlp_int8.h"
```

File này chứa mảng byte model TFLite INT8 được export từ notebook `ppg_dalia.ipynb`. Nó cung cấp:

```cpp
ppg_hr_mlp_int8_tflite
ppg_hr_mlp_int8_tflite_len
```

Firmware dùng mảng này để khởi tạo TFLite Micro interpreter.

## Namespace Ẩn Danh

Toàn bộ phần lớn code nằm trong:

```cpp
namespace
{
    ...
}
```

Đây là anonymous namespace của C++. Các biến/hàm bên trong chỉ có phạm vi trong file này. Nó tránh trùng symbol với file khác khi link firmware.

## Run Mode

Firmware định nghĩa:

```cpp
enum run_mode_t
{
    RUN_MODE_FIXED_NORMAL = 0,
    RUN_MODE_FIXED_HIGH = 1,
    RUN_MODE_ADAPTIVE = 2,
};
```

Có ba chế độ chạy:

- `FIXED_NORMAL`: ép hệ thống luôn ở nhánh nhẹ.
- `FIXED_HIGH`: ép hệ thống luôn ở nhánh mạnh.
- `ADAPTIVE`: scheduler tự chuyển `NORMAL/HIGH`.

Đoạn:

```cpp
#ifndef RUN_MODE
#define RUN_MODE RUN_MODE_ADAPTIVE
#endif
```

Nếu build system không truyền `RUN_MODE`, mặc định chạy adaptive.

```cpp
constexpr run_mode_t kRunMode = static_cast<run_mode_t>(RUN_MODE);
constexpr bool kAdaptiveEnabled = (kRunMode == RUN_MODE_ADAPTIVE);
constexpr bool kTinyMlEnabledByMode = (kRunMode != RUN_MODE_FIXED_NORMAL);
```

Ý nghĩa:

- Nếu mode adaptive thì cho phép chuyển trạng thái.
- Nếu fixed normal thì tắt TinyML, vì mode này dùng làm baseline tiết kiệm điện.
- Nếu fixed high hoặc adaptive thì khởi tạo TinyML.

Trong thí nghiệm macro-level:

- Fixed Normal đo cận thấp về năng lượng.
- Fixed High đo cận cao về coverage/năng lượng.
- Adaptive đo trade-off.

## GPIO Profiling Cho DAQ

```cpp
constexpr gpio_num_t PROFILING_FEATURE_GPIO = GPIO_NUM_10;
constexpr gpio_num_t PROFILING_INVOKE_GPIO = GPIO_NUM_11;
```

Hai chân này nối sang DAQ node:

- GPIO10 lên mức 1 khi firmware đang trích feature.
- GPIO11 lên mức 1 khi firmware đang gọi TinyML `Invoke()`.

DAQ node đọc hai chân này cùng với công suất INA219. Nhờ đó phân tích micro-level biết đoạn nào là feature extraction, đoạn nào là TinyML inference.

## Tham Số Cửa Sổ Và Model

```cpp
constexpr int kFeatureCount = 16;
constexpr float kModelFs = 64.0f;
constexpr int kWindowSec = 8;
constexpr int kStrideSec = 2;
constexpr int kWindowSamplesModel = static_cast<int>(kModelFs) * kWindowSec;
constexpr int kPsdFftSize = 256;
```

Các tham số này bám theo notebook:

- Model nhận 16 feature.
- Feature extractor dùng tín hiệu resample về 64 Hz.
- Window 8 giây.
- Stride 2 giây.
- Window model: `64 * 8 = 512` mẫu.
- FFT size: 256 mẫu.

```cpp
constexpr int kSensorFs = 100;
constexpr int kWindowSamplesSensor = kSensorFs * kWindowSec;
constexpr int kStrideSamplesSensor = kSensorFs * kStrideSec;
```

Ring buffer được cấp theo cấu hình sensor tối đa 100 Hz:

- Window sensor tối đa: 800 mẫu.
- Stride sensor tối đa: 200 mẫu.

Khi chạy NORMAL firmware dùng 50 sps, HIGH dùng 100 sps. Nhưng buffer cấp theo 100 để đủ chỗ cho cả hai.

## Chuẩn Hóa Output HR

```cpp
constexpr float kHrMeanBpm = 89.3519745f;
constexpr float kHrStdBpm = 22.6059856f;
```

Model TinyML trong notebook không dự đoán trực tiếp BPM thật. Nó dự đoán HR đã chuẩn hóa:

```text
y_norm = (HR - mean) / std
```

Firmware phải đổi ngược:

```text
HR = y_norm * kHrStdBpm + kHrMeanBpm
```

Hai hằng số này phải khớp với artifact training. Nếu không khớp, output BPM sẽ sai scale.

## Tensor Arena Và Biến TFLite

```cpp
constexpr int kTensorArenaSize = 16 * 1024;
alignas(16) static uint8_t tensor_arena[kTensorArenaSize];
```

TensorFlow Lite Micro không cấp phát heap động như Python. Nó cần một vùng RAM tĩnh gọi là tensor arena để chứa tensor, activation, buffer nội bộ.

`alignas(16)` căn hàng bộ nhớ 16 byte, giúp runtime dùng SIMD/operation tốt hơn và tránh lỗi alignment.

Các biến toàn cục:

```cpp
const tflite::Model *g_model = nullptr;
tflite::MicroInterpreter *g_interpreter = nullptr;
TfLiteTensor *g_input = nullptr;
TfLiteTensor *g_output = nullptr;
```

Chúng giữ model, interpreter, input tensor và output tensor sau khi khởi tạo TinyML.

## I2C Và MAX30102 Register

```cpp
constexpr i2c_port_t I2C_PORT = I2C_NUM_0;
constexpr gpio_num_t I2C_SDA = GPIO_NUM_8;
constexpr gpio_num_t I2C_SCL = GPIO_NUM_9;
constexpr uint32_t I2C_FREQ_HZ = 100000;
constexpr uint8_t MAX30102_ADDR = 0x57;
```

ESP32-S3 giao tiếp MAX30102 qua I2C:

- SDA: GPIO8.
- SCL: GPIO9.
- Clock: 100 kHz.
- Địa chỉ MAX30102: `0x57`.

Các register:

```cpp
REG_FIFO_WR_PTR
REG_OVF_COUNTER
REG_FIFO_RD_PTR
REG_FIFO_DATA
REG_FIFO_CONFIG
REG_MODE_CONFIG
REG_SPO2_CONFIG
REG_LED1_PA
REG_LED2_PA
REG_PART_ID
```

Ý nghĩa:

- FIFO pointer: biết có bao nhiêu mẫu đang chờ.
- FIFO data: đọc mẫu RED/IR.
- FIFO config, SPO2 config, LED current, mode config: cấu hình cảm biến.
- PART_ID: kiểm tra cảm biến có phản hồi đúng không.

## Profile MAX30102

Struct:

```cpp
struct max30102_profile_t
{
    uint8_t fifo_config;
    uint8_t spo2_config;
    uint8_t led1_pa;
    uint8_t led2_pa;
    uint8_t mode_config;
    int sample_rate_hz;
    const char *name;
};
```

Một profile là một bộ cấu hình cảm biến. Firmware có hai profile:

```cpp
kProfile50Med
kProfile100Med
```

`kProfile50Med`:

- Sample rate 50 sps.
- Dùng cho `NORMAL`.
- Mục tiêu: tiết kiệm hơn, ít mẫu hơn.

`kProfile100Med`:

- Sample rate 100 sps.
- Dùng cho `HIGH`.
- Mục tiêu: dữ liệu dày hơn, phục vụ xử lý mạnh hơn.

Hai profile đều dùng mode `0x03`, tức SpO2 mode, đọc cả RED và IR. Firmware hiện tại chủ yếu xử lý IR.

## Scheduler State Và Quality Fail Reason

```cpp
enum scheduler_state_t
{
    SCHED_STATE_NORMAL = 0,
    SCHED_STATE_HIGH = 1,
};
```

Đây là trạng thái runtime của scheduler:

- `NORMAL`: nhánh nhẹ.
- `HIGH`: nhánh mạnh có TinyML.

```cpp
enum quality_fail_reason_t
{
    QFR_NONE = 0,
    QFR_NO_CONTACT,
    QFR_AMP_FAIL,
    QFR_AC_FAIL,
    QFR_HR_RANGE_FAIL,
    QFR_CONSIST_FAIL,
};
```

Các lý do cửa sổ tín hiệu bị đánh giá không tốt:

- `NO_CONTACT`: có thể không tiếp xúc tốt.
- `AMP_FAIL`: biên độ/std ngoài ngưỡng.
- `AC_FAIL`: autocorrelation thấp, chu kỳ không rõ.
- `HR_RANGE_FAIL`: HR ước lượng ngoài khoảng hợp lý.
- `CONSIST_FAIL`: peak HR và autocorrelation HR lệch nhau quá nhiều.

## `window_metrics_t`

```cpp
struct window_metrics_t
{
    float peak_bpm;
    float ac_best;
    float ac_best_hr;
    float std_hp;
    float ptp_hp;
};
```

Đây là các chỉ số chính tính trên mỗi cửa sổ:

- `peak_bpm`: HR ước lượng từ số đỉnh.
- `ac_best`: autocorrelation tốt nhất trong dải HR.
- `ac_best_hr`: HR suy ra từ lag autocorrelation tốt nhất.
- `std_hp`: độ lệch chuẩn sau high-pass trên tín hiệu sensor.
- `ptp_hp`: biên độ peak-to-peak sau high-pass.

Những chỉ số này là input cho quality gate và scheduler.

## RAII Pulse `profiling_pulse_t`

```cpp
struct profiling_pulse_t
{
    explicit profiling_pulse_t(gpio_num_t pin) { gpio_set_level(pin_, 1); }
    ~profiling_pulse_t() { gpio_set_level(pin_, 0); }
};
```

Đây là một kỹ thuật C++ gọi là RAII. Khi tạo object, GPIO lên 1. Khi object ra khỏi scope, destructor tự kéo GPIO về 0.

Ví dụ:

```cpp
{
    profiling_pulse_t feature_pulse(PROFILING_FEATURE_GPIO);
    extract_ppg_features(...);
}
```

GPIO10 sẽ high đúng trong thời gian `extract_ppg_features` chạy. Dù hàm return sớm hoặc có lỗi, destructor vẫn chạy khi scope kết thúc.

Tương tự với TinyML `Invoke()` và GPIO11.

## Ngưỡng Scheduler

Các hằng số:

```cpp
SCHED_STD_MIN = 250.0f
SCHED_PTP_MIN = 1000.0f
SCHED_PTP_MAX = 35000.0f
SCHED_AC_MIN = 0.30f
SCHED_AC_HARD = 0.20f
SCHED_AC_EASY = 0.40f
SCHED_DIFF_HARD = 0.80f
SCHED_DIFF_EASY = 0.60f
```

Ý nghĩa:

- Tín hiệu quá nhỏ thì có thể chìm trong nhiễu.
- Tín hiệu quá lớn thì có thể do lực ép, motion artifact, drift.
- Autocorrelation thấp thì tín hiệu thiếu chu kỳ.
- Difficulty proxy cao thì cửa sổ khó.

Các bộ đếm:

```cpp
SCHED_BAD_WINDOWS_TO_UP = 4
SCHED_GOOD_WINDOWS_TO_DOWN = 5
SCHED_COOLDOWN_WINDOWS = 3
SCHED_MIN_STATE_DWELL_US = 15s
```

Scheduler không chuyển trạng thái ngay sau một cửa sổ. Nó cần nhiều cửa sổ xấu/tốt liên tiếp và thời gian dwell tối thiểu. Điều này tạo hysteresis, tránh nhảy trạng thái liên tục.

Ngưỡng no-contact:

```cpp
NO_CONTACT_STD_HP_MIN
NO_CONTACT_PTP_HP_MIN
NO_CONTACT_PEAK_BPM_MAX
NO_CONTACT_AC_MAX
```

Logic này cố phát hiện tình huống tín hiệu không đáng tin do không tiếp xúc hoặc artifact mạnh.

```cpp
HR_CONSIST_MAX_DIFF_BPM = 18.0f
```

Nếu HR từ peak detection và HR từ autocorrelation lệch quá 18 BPM, cửa sổ bị coi là thiếu nhất quán.

## Ring Buffer Và State Toàn Cục

```cpp
static float g_ir_ring[kWindowSamplesSensor] = {0};
static int g_ir_head = 0;
static int g_ir_count = 0;
static int g_since_last_eval = 0;
```

Đây là ring buffer chứa mẫu IR gần nhất. Mỗi mẫu đọc từ MAX30102 được đẩy vào đây. Khi đủ stride, firmware đánh thức `inference_task`.

```cpp
static int g_window_samples = 400;
static int g_stride_samples = 100;
static int g_current_fs = 50;
```

Mặc định là NORMAL 50 Hz:

- Window: 50 * 8 = 400 mẫu.
- Stride: 50 * 2 = 100 mẫu.

Khi chuyển HIGH:

- Window: 100 * 8 = 800 mẫu.
- Stride: 100 * 2 = 200 mẫu.

```cpp
static float g_bpm_ema = 0.0f;
static bool g_has_bpm_ema = false;
```

EMA làm mượt HR output để kết quả không nhảy mạnh giữa các cửa sổ.

Mutex/critical section:

```cpp
g_ring_mux
g_state_mux
g_telemetry_mux
```

Vì `app_main` và `inference_task` chạy song song, các biến dùng chung phải được bảo vệ:

- `g_ring_mux`: bảo vệ ring buffer.
- `g_state_mux`: bảo vệ scheduler state.
- `g_telemetry_mux`: bảo vệ biến log telemetry.

## Scratch Buffer

Firmware khai báo nhiều mảng tĩnh:

```cpp
g_win_sensor
g_win_model
g_feat
g_scratch_x
g_scratch_tmp
g_scratch_dx
g_scratch_ac
g_scratch_peaks
g_scratch_proms
g_scratch_hr_inst
g_scratch_pxx
g_scratch_hp
g_fft_buf
```

Lý do dùng mảng tĩnh:

- Tránh cấp phát động trong firmware nhúng.
- Kiểm soát RAM.
- Giảm fragmentation.
- Chạy ổn định hơn trong real-time loop.

`g_feat[16]` là vector feature đưa vào model TinyML.

## Scaler Mean/Scale

```cpp
static const float kScalerMean[kFeatureCount] = { ... };
static const float kScalerScale[kFeatureCount] = { ... };
```

Đây là mean và scale của `StandardScaler` từ notebook training. Firmware dùng để chuẩn hóa 16 feature:

```text
x_scaled[i] = (feature[i] - mean[i]) / scale[i]
```

Thứ tự 16 phần tử phải đúng với thứ tự feature trong notebook:

```text
mean, std, ptp, rms, abs_mean, slope_abs_mean,
n_peaks, peak_rate_per_sec,
hr_est_mean, hr_est_std, peak_prom_mean,
ac_best, ac_best_hr,
psd_hr_ratio, spectral_entropy, dom_bpm_hr_band
```

Nếu thứ tự lệch, model sẽ nhận sai input.

## Hàm Tiện Ích Số Học

### `clampf`

```cpp
inline float clampf(float v, float lo, float hi)
```

Giới hạn một số nằm trong `[lo, hi]`. Dùng để:

- Giới hạn z-score input trước quantization.
- Giới hạn HR output trong 40-180 BPM.
- Giới hạn difficulty proxy.

### `cmp_float`, `median_of`

`cmp_float` dùng cho `qsort`. `median_of` tính median. Trong file hiện tại, `median_of` không phải phần trung tâm luồng chạy chính, nhưng có thể được giữ lại từ các vòng thử nghiệm robust normalization.

### `mean_of`, `std_of`

Tính mean và standard deviation thủ công trên mảng float. Firmware không dùng NumPy, nên phải tự viết.

## Tiền Xử Lý Tín Hiệu

### `detrend_linear`

```cpp
void detrend_linear(float *x, int n)
```

Hàm này fit một đường thẳng `slope * i + intercept` vào tín hiệu rồi trừ nó đi. Mục tiêu là bỏ xu hướng tuyến tính chậm trong cửa sổ.

Trong PPG, nền có thể trôi do lực ép, tiếp xúc, ánh sáng. Nếu không bỏ nền, các chỉ số biên độ có thể bị đánh lừa.

### `simple_bandpass`

```cpp
void simple_bandpass(float *x, int n, float fs)
```

Đây là bản lọc thông dải đơn giản thay cho Butterworth `filtfilt` trong Python. Nó gồm:

1. High-pass một cực khoảng 0.7 Hz.
2. Low-pass một cực khoảng 5.0 Hz.

High-pass:

```cpp
hp = hp_alpha * (hp_prev + x[i] - x_prev)
```

Low-pass:

```cpp
lp_prev = lp_prev + lp_alpha * (x[i] - lp_prev)
```

Lý do không dùng đúng `filtfilt` như Python:

- `filtfilt` cần xử lý hai chiều và buffer nhiều hơn.
- Firmware cần nhẹ, chạy real-time.
- Bộ lọc đơn giản đủ để tạo feature gần đúng.

### `robust_zscore`

Trong firmware:

```cpp
mean = mean_of(x)
scale = std_of(x)
x[i] = (x[i] - mean) / scale
```

Tên là `robust_zscore` nhưng hiện implementation dùng mean/std, không dùng median/MAD như notebook. Đây là một điểm cần nhớ: pipeline firmware là bản xấp xỉ của pipeline Python, không trùng hoàn toàn.

## Autocorrelation

```cpp
void normalized_autocorr(const float *x, int n, float fs, float bpm_min, float bpm_max, ...)
```

Hàm này tìm mức tự tương quan tốt nhất trong dải HR.

Các bước:

1. Tính mean.
2. Tính năng lượng `denom`.
3. Chuyển BPM range sang lag range:

```text
lag = fs * 60 / BPM
```

4. Với từng lag, tính:

```cpp
num += (x[i] - mean) * (x[i + lag] - mean)
ac = num / denom
```

5. Chọn lag có `ac` lớn nhất.
6. Quy đổi lag đó về BPM:

```text
ac_best_hr = 60 / (best_lag / fs)
```

Autocorrelation giúp kiểm tra tín hiệu có tính chu kỳ không. Đây là thành phần quan trọng của quality gate.

## Peak Detection Đơn Giản

```cpp
int find_peaks_simple(...)
```

Hàm này tìm local maximum:

```cpp
x[i] > x[i - 1] && x[i] >= x[i + 1]
```

Sau đó kiểm tra:

- Khoảng cách tối thiểu với đỉnh trước.
- Prominence tối thiểu.

Prominence được ước lượng bằng cách nhìn min bên trái/phải trong phạm vi `min_distance`.

Hàm trả về:

- Số đỉnh.
- Vị trí đỉnh trong `peaks`.
- Độ nổi của đỉnh trong `proms`.

Đây là bản firmware của `scipy.signal.find_peaks`. Nó đơn giản hơn SciPy nhưng đủ dùng cho embedded.

## Resample Tuyến Tính

```cpp
void resample_linear(const float *in, int n_in, float *out, int n_out)
```

Sensor có thể chạy 50 Hz hoặc 100 Hz, nhưng model training dùng 64 Hz và window 512 mẫu. Vì vậy firmware resample cửa sổ sensor về đúng 512 mẫu:

```text
NORMAL: 400 mẫu @ 50 Hz -> 512 mẫu @ 64 Hz
HIGH  : 800 mẫu @ 100 Hz -> 512 mẫu @ 64 Hz
```

Hàm dùng nội suy tuyến tính:

```cpp
out[i] = in[idx] * (1 - frac) + in[idx2] * frac
```

Điểm cần hiểu: resample giúp feature extractor/model có input cố định, dù sensor state thay đổi sample rate.

## FFT Và PSD Feature

### `ensure_fft_ready`

```cpp
dsps_fft2r_init_fc32(nullptr, kPsdFftSize)
```

Khởi tạo FFT table của ESP-DSP. Chỉ init một lần, lưu cờ `g_fft_ready`.

### `compute_psd_features`

Hàm này tính các feature miền tần số tương đương notebook:

- `psd_hr_ratio`
- `spectral_entropy`
- `dom_bpm_hr_band`

Luồng:

1. Copy 256 mẫu đầu của tín hiệu vào `g_fft_buf` dạng complex: real = x[i], imag = 0.
2. Chạy FFT:

```cpp
dsps_fft2r_fc32(g_fft_buf, nfft);
dsps_bit_rev_fc32(g_fft_buf, nfft);
```

3. Tính power mỗi bin:

```cpp
p = re * re + im * im
```

4. Tính:

- Tổng power từ 0 đến min(8 Hz, Nyquist).
- HR-band power từ 0.7 đến 3.5 Hz.
- Tần số có power lớn nhất trong HR band.
- Entropy phổ.

Firmware không dùng Welch PSD đầy đủ như Python. Nó dùng một FFT đơn 256 mẫu để giảm chi phí. Đây là một xấp xỉ.

## Trích 16 Feature `extract_ppg_features`

```cpp
void extract_ppg_features(const float *sig_raw, int n, float fs, float *feat)
```

Đây là bản firmware của feature extractor trong `ppg_dalia.ipynb`.

Luồng:

1. Copy input vào scratch:

```cpp
memcpy(g_scratch_x, sig_raw, ...)
```

2. Lọc:

```cpp
simple_bandpass(g_scratch_x, n, fs);
robust_zscore(g_scratch_x, n);
```

3. Tính feature cơ bản:

- min/max.
- abs sum.
- square sum.
- mean.
- std.
- diff giữa các mẫu.

4. Peak detection:

```cpp
min_distance = fs * 60 / 140
prominence = max(0.25 * std, 0.12)
```

So với notebook, firmware dùng constraint chặt hơn để giảm đếm double-peak trên tín hiệu ngón tay.

5. Tính HR từ peak:

```cpp
ibi = (peak[i+1] - peak[i]) / fs
hr = 60 / ibi
```

6. Tính prominence trung bình.
7. Tính autocorrelation best.
8. Tính PSD feature.
9. Gán 16 feature:

```cpp
feat[0]  = mean;
feat[1]  = std;
feat[2]  = max_v - min_v;
feat[3]  = rms;
feat[4]  = abs_mean;
feat[5]  = slope_abs_mean;
feat[6]  = n_peaks;
feat[7]  = peak_rate_per_sec;
feat[8]  = hr_est_mean;
feat[9]  = hr_est_std;
feat[10] = peak_prom_mean;
feat[11] = ac_best;
feat[12] = ac_best_hr;
feat[13] = psd_hr_ratio;
feat[14] = spectral_entropy;
feat[15] = dom_bpm_hr_band;
```

10. Nếu feature là NaN/Inf thì set 0.

Điểm quan trọng: `feat[7]` là peak rate per second, nhưng ở nơi dùng metrics firmware lấy:

```cpp
metrics->peak_bpm = g_feat[7] * 60.0f;
```

Tức peak rate được đổi sang BPM.

## I2C Helper Cho MAX30102

Ba hàm:

```cpp
max30102_write_reg
max30102_read_reg
max30102_read_multi
```

là wrapper quanh ESP-IDF I2C:

- Ghi một register.
- Đọc một register.
- Đọc nhiều byte liên tiếp.

Tất cả đều dùng timeout 1000 ms. Đây là lớp thấp nhất giao tiếp cảm biến.

## Log CSV Thưa

```cpp
void print_sparse_csv_log(int64_t timestamp_ms)
```

Hàm này in:

```text
timestamp_ms,state,profile,quality,diff,red,ir
```

Nó snapshot:

- scheduler state.
- RED/IR mới nhất.
- quality pass.
- difficulty proxy.

Log này phục vụ macro-level analysis. Nó không in mọi mẫu vì in UART quá nhiều sẽ làm nhiễu timing và tăng năng lượng.

`profile_id_from_state` trả:

```cpp
HIGH -> 0
NORMAL -> 1
```

## Apply Profile MAX30102

```cpp
esp_err_t max30102_apply_profile(const max30102_profile_t *profile)
```

Luồng:

1. Reset MAX30102:

```cpp
max30102_write_reg(REG_MODE_CONFIG, 0x40)
```

2. Delay 100 ms.
3. Reset FIFO write pointer, read pointer, overflow counter.
4. Ghi FIFO config.
5. Ghi SpO2 config.
6. Ghi LED current RED/IR.
7. Ghi mode config.

Khi scheduler chuyển state, firmware gọi hàm này để đổi sample rate cảm biến.

## Decision Freeze

```cpp
void add_decision_freeze_windows(int n)
```

Khi có lỗi I2C hoặc recover cảm biến, scheduler tạm "đóng băng" quyết định vài cửa sổ. Mục tiêu:

- Không chuyển state dựa trên dữ liệu ngay sau lỗi.
- Cho cảm biến ổn định lại.
- Tránh scheduler phản ứng sai với tín hiệu rỗng/nhiễu sau reset.

## Kiểm Tra FIFO Pending

```cpp
esp_err_t max30102_fifo_pending(uint8_t *pending)
```

MAX30102 có FIFO. Firmware đọc:

- Write pointer.
- Read pointer.
- Overflow counter.

Số mẫu đang chờ:

```cpp
diff = (wr - rd) & 0x1F
```

FIFO có 32 slot, nên dùng mask `0x1F`.

Nếu overflow:

```cpp
ESP_LOGW(...)
max30102_write_reg(REG_OVF_COUNTER, 0x00)
```

Overflow nghĩa là firmware đọc không kịp, dữ liệu bị mất. Đây là lý do kiến trúc phải tách sensing khỏi inference.

## Đọc Một Mẫu MAX30102

```cpp
esp_err_t max30102_read_sample(uint32_t *red, uint32_t *ir)
```

MAX30102 trả 6 byte cho mỗi mẫu:

```text
RED: raw[0], raw[1], raw[2]
IR : raw[3], raw[4], raw[5]
```

Mỗi kênh là 18-bit, nên code mask:

```cpp
*red = r & 0x03FFFF;
*ir = i & 0x03FFFF;
```

Firmware sau đó chỉ đẩy `ir` vào ring buffer vì IR ổn định hơn trong thí nghiệm.

## Khởi Tạo I2C Và MAX30102

```cpp
esp_err_t i2c_init()
```

Cấu hình ESP32-S3 là I2C master:

- SDA GPIO8.
- SCL GPIO9.
- Pull-up enable.
- Clock 100 kHz.

```cpp
esp_err_t max30102_init()
```

Đọc `REG_PART_ID` để kiểm tra cảm biến phản hồi. Hàm này chưa apply profile; profile được apply sau theo scheduler state.

## Cập Nhật Sampling Params Theo State

```cpp
void update_sampling_params_locked(scheduler_state_t state)
```

Nếu HIGH:

```cpp
g_current_fs = 100;
g_window_samples = 800;
g_stride_samples = 200;
```

Nếu NORMAL:

```cpp
g_current_fs = 50;
g_window_samples = 400;
g_stride_samples = 100;
```

Hàm có hậu tố `_locked` vì nó được gọi khi đã giữ `g_state_mux`.

## Apply Scheduler State

```cpp
esp_err_t apply_scheduler_state(scheduler_state_t state)
```

Đây là hàm thật sự chuyển state.

Luồng:

1. Chọn profile cảm biến:

```cpp
HIGH -> kProfile100Med
NORMAL -> kProfile50Med
```

2. Apply profile MAX30102.
3. Reset ring buffer:

```cpp
g_ir_head = 0;
g_ir_count = 0;
g_since_last_eval = 0;
```

Lý do reset buffer: sample rate thay đổi, dữ liệu cũ và mới không nên trộn trong cùng cửa sổ.

4. Cập nhật state và sampling params.
5. Lưu timestamp chuyển state.

Điều này giải thích vì sao sau chuyển state cần chờ đủ window mới có đánh giá tiếp theo.

## Recover MAX30102

```cpp
esp_err_t max30102_recover()
```

Khi I2C lỗi liên tiếp hoặc không có mẫu mới quá 3 giây:

1. Probe lại MAX30102.
2. Apply lại profile theo state hiện tại.
3. Reset EMA HR.
4. Freeze decision vài cửa sổ.

Recover giúp hệ thống tự phục hồi nếu cảm biến treo hoặc FIFO/I2C lỗi.

## Khởi Tạo TinyML

```cpp
bool tinyml_init()
```

Luồng:

1. Lấy model từ mảng byte:

```cpp
g_model = tflite::GetModel(ppg_hr_mlp_int8_tflite);
```

2. Kiểm tra schema version:

```cpp
g_model->version() == TFLITE_SCHEMA_VERSION
```

3. Tạo op resolver:

```cpp
static tflite::MicroMutableOpResolver<1> resolver;
resolver.AddFullyConnected()
```

Model MLP chỉ cần op FullyConnected. Vì activation ReLU có thể được fuse vào FullyConnected hoặc xử lý trong kernel tương ứng tùy converter. Việc chỉ add 1 op giúp giảm footprint.

4. Tạo interpreter tĩnh:

```cpp
static tflite::MicroInterpreter static_interpreter(...)
```

5. Allocate tensors trong tensor arena.
6. Lấy input/output tensor.
7. Kiểm tra:

- Input/output phải là INT8.
- Input shape phải là `[1, 16]`.

8. Log:

- Model size.
- Input quant scale/zero-point.
- Output quant scale/zero-point.
- Tensor arena used.

Nếu bất kỳ bước nào lỗi, firmware dừng init TinyML.

## Đẩy Mẫu IR Vào Ring Buffer

```cpp
void push_ir_sample(float ir)
```

Hàm này được gọi mỗi khi `app_main` đọc được một mẫu IR.

Luồng:

1. Ghi IR vào `g_ir_ring[g_ir_head]`.
2. Tăng head vòng tròn.
3. Tăng count nếu buffer chưa đầy.
4. Tăng `g_since_last_eval`.
5. Snapshot stride/window hiện tại.
6. Nếu đã đủ stride và đủ window:

```cpp
should_notify = true
```

7. Sau khi thả lock, notify inference task:

```cpp
xTaskNotifyGive(inference_task_handle);
```

Điểm quan trọng: push sample không xử lý nặng. Nó chỉ ghi buffer và notify. Điều này giữ đường đọc cảm biến nhẹ.

## Snapshot Cửa Sổ

```cpp
bool snapshot_window(float *out, int n_samples)
```

Hàm này lấy `n_samples` mẫu mới nhất từ ring buffer theo đúng thứ tự thời gian.

Vì ring buffer là vòng tròn, index bắt đầu:

```cpp
idx = (g_ir_head - n_samples + kWindowSamplesSensor) % kWindowSamplesSensor;
```

Sau đó copy lần lượt ra `out`.

Nếu chưa đủ mẫu, trả `false`.

## High-Pass Metrics Trên Tín Hiệu Sensor

```cpp
void compute_hp_metrics(...)
```

Hàm này tính `std_hp` và `ptp_hp` sau khi loại nền chậm bằng EMA low-pass:

```cpp
lp += alpha * (x[i] - lp);
hp = x[i] - lp;
```

Trong đó `tau = 0.8s`. `lp` là nền chậm, `hp` là phần dao động sau khi bỏ nền.

Sau đó tính:

- `std_hp`: độ lệch chuẩn high-pass.
- `ptp_hp`: max-min high-pass.

Hai chỉ số này được dùng trong quality gate để tránh đánh giá trên raw PPG bị drift nền.

## Tính Metrics Cho Một Cửa Sổ

```cpp
bool compute_window_metrics(window_metrics_t *metrics, bool need_full_features)
```

Đây là hàm trung gian quan trọng.

Luồng:

1. Snapshot `g_window_samples` và `g_current_fs`.
2. Lấy cửa sổ mới nhất từ ring buffer vào `g_win_sensor`.
3. Tính `std_hp`, `ptp_hp` trên tín hiệu sensor.
4. Resample cửa sổ sensor về `g_win_model` 512 mẫu @ 64 Hz.

Nếu `need_full_features == true`, tức state HIGH:

```cpp
profiling_pulse_t feature_pulse(PROFILING_FEATURE_GPIO);
extract_ppg_features(..., g_feat);
metrics->peak_bpm = g_feat[7] * 60.0f;
metrics->ac_best = g_feat[11];
metrics->ac_best_hr = g_feat[12];
```

Khi đó GPIO10 high trong lúc trích feature.

Nếu `need_full_features == false`, tức state NORMAL:

Firmware không trích đủ 16 feature để tiết kiệm. Nó chỉ:

1. Copy `g_win_model` vào scratch.
2. Detrend.
3. Bandpass.
4. Normalize.
5. Peak detection.
6. Autocorrelation.

Rồi trả về các metrics cần cho quality gate.

Đây chính là tách Fast Path/Slow Path:

- NORMAL: metrics nhẹ.
- HIGH: full feature + TinyML.

## Chạy TinyML Trên Feature

```cpp
bool run_tinyml_on_features(float *y_bpm, int8_t *y_q)
```

Hàm này giả định `g_feat[16]` đã được tính trước bởi `extract_ppg_features`.

### Chuẩn hóa feature

```cpp
x_sc = (g_feat[i] - kScalerMean[i]) / (kScalerScale[i] + 1e-8f);
x_sc = clampf(x_sc, -6.0f, 6.0f);
```

Chuẩn hóa giống notebook. Clamp về `[-6, 6]` để tránh outlier làm saturate INT8 quá mạnh.

### Quantize input INT8

```cpp
qf = x_sc / in_scale + in_zp;
qi = lrintf(qf);
qi = clamp(qi, -128, 127);
g_input->data.int8[i] = qi;
```

Công thức giống notebook:

```text
x_int8 = round(x_float / scale + zero_point)
```

### Gọi Invoke Và Phát GPIO11

```cpp
{
    profiling_pulse_t invoke_pulse(PROFILING_INVOKE_GPIO);
    t_start = esp_timer_get_time();
    g_interpreter->Invoke();
    t_end = esp_timer_get_time();
}
```

GPIO11 high đúng trong thời gian `Invoke()`. Firmware cũng log thời gian Invoke bằng microsecond.

### Dequantize output

```cpp
y_q_local = g_output->data.int8[0];
y_norm = dequantize_int8(y_q_local, output_scale, output_zero_point);
*y_bpm = clampf(y_norm * kHrStdBpm + kHrMeanBpm, 40.0f, 180.0f);
```

Output INT8 được giải lượng tử về float normalized, rồi denormalize về BPM, cuối cùng clamp 40-180 BPM.

## `inference_task` - Task Xử Lý Và Scheduler

Đây là trái tim của firmware.

```cpp
void inference_task(void *arg)
```

Task có các bộ đếm:

```cpp
bad_windows
gray_windows
good_windows
dsp_publish_windows
cooldown_windows
```

Ý nghĩa:

- `bad_windows`: số cửa sổ xấu rõ ràng liên tiếp.
- `gray_windows`: số cửa sổ lỗi nhẹ/liên tục không chắc.
- `good_windows`: số cửa sổ tốt liên tiếp.
- `dsp_publish_windows`: cần vài cửa sổ tốt trước khi publish DSP HR.
- `cooldown_windows`: sau khi vào HIGH, chờ vài cửa sổ trước khi xét quay về NORMAL.

### Chờ notify

```cpp
ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
```

Task ngủ cho đến khi `push_ir_sample` báo đã đủ stride.

### Snapshot state

Task lấy:

- state hiện tại.
- timestamp chuyển state cuối.
- decision freeze windows.

Nếu freeze > 0 thì giảm dần mỗi lần xử lý cửa sổ.

### Tính metrics

```cpp
const bool need_full_features = (state_snapshot == SCHED_STATE_HIGH);
compute_window_metrics(&metrics, need_full_features)
```

Ở HIGH, hàm này đã trích đủ `g_feat`. Ở NORMAL, chỉ tính metrics nhẹ.

### Quality gate

Firmware lấy:

```cpp
peak_bpm
ac_best
std_hp
ptp_hp
ac_best_hr
```

Rồi kiểm tra:

```cpp
amplitude_ok = std_hp >= min && ptp_hp >= min && ptp_hp <= max
periodic_ok = ac_best >= SCHED_AC_MIN
hr_range_ok = peak_bpm between 40 and 180
quality_ok = amplitude_ok && periodic_ok && hr_range_ok
```

Difficulty proxy:

```cpp
difficulty_proxy = amplitude_ok ? clamp(1 - ac_best, 0, 1) : 1
```

Nếu biên độ không ok thì coi là rất khó. Nếu biên độ ok thì độ khó chủ yếu là `1 - ac_best`.

HR consistency:

```cpp
hr_consistent = ac_hr_valid && abs(peak_bpm - ac_best_hr) <= 18 BPM
```

Tức hai cách ước lượng HR phải gần nhau.

No-contact:

```cpp
no_contact_hard
no_contact_soft
```

Nếu peak BPM quá thấp, autocorrelation kém và biên độ cao bất thường, firmware coi như không tiếp xúc/tín hiệu không đáng tin.

### Xác định fail reason

Thứ tự ưu tiên:

1. No contact.
2. Amplitude fail.
3. HR range fail.
4. AC fail.
5. Consistency fail.

Sau đó phân loại:

```cpp
severe_motion_fail = AMP_FAIL hoặc HR_RANGE_FAIL
mild_fail = AC_FAIL hoặc CONSIST_FAIL
```

Severe fail có xu hướng đẩy lên HIGH nhanh hơn. Mild fail được gom vào gray windows.

### Cập nhật telemetry

Firmware lưu:

- quality pass.
- difficulty proxy.
- ac_best.
- peak_bpm.

Các biến này được `print_sparse_csv_log` in ra cho phân tích.

### Publish DSP HR

Nếu:

```cpp
quality_ok && hr_consistent && !no_contact
```

thì DSP HR được coi là đáng tin. Nhưng firmware không publish ngay, mà cần:

```cpp
dsp_publish_windows >= DSP_PUBLISH_WINDOWS
```

`DSP_PUBLISH_WINDOWS = 2`, tức cần 2 cửa sổ tốt liên tiếp.

HR DSP:

```cpp
bpm_dsp = clampf(peak_bpm, 40, 180)
```

EMA:

```cpp
g_bpm_ema = 0.35 * bpm_dsp + 0.65 * g_bpm_ema
```

EMA giúp output mượt hơn.

Nếu chưa đủ số cửa sổ publish, log `DSP_HOLD`.

Nếu low quality, reset `dsp_publish_windows` và log `NO_CONTACT` hoặc `Low quality window`.

## Logic Khi Đang NORMAL

```cpp
if (state_snapshot == SCHED_STATE_NORMAL)
```

Nếu no contact:

- Reset counter.
- Không chuyển HIGH.
- `continue`.

Điều này có ý nghĩa: nếu không tiếp xúc, bật HIGH/TinyML cũng không giúp. Chạy mạnh khi không có tín hiệu chỉ tốn điện.

Nếu decision frozen:

- Giữ NORMAL.
- Reset bad/gray.

Nếu severe fail hoặc khó rõ:

```cpp
bad_windows++;
gray_windows = 0;
```

Nếu mild fail:

```cpp
gray_windows++;
bad_windows = 0;
```

Nếu ổn:

```cpp
bad_windows = 0;
gray_windows = 0;
```

Điều kiện chuyển lên HIGH:

```cpp
kAdaptiveEnabled &&
(bad_windows >= 4 || gray_windows >= 4) &&
dwell_ok
```

Nếu đạt:

```cpp
g_desired_state = SCHED_STATE_HIGH;
g_switch_pending = true;
cooldown_windows = 3;
```

Task không tự apply state ngay. Nó chỉ đặt cờ. `app_main` sẽ apply state khi FIFO pending = 0. Cách này tránh đổi cấu hình cảm biến giữa lúc còn dữ liệu FIFO.

## Logic Khi Đang HIGH

Ở HIGH, nếu không no-contact và TinyML sẵn sàng:

```cpp
run_tinyml_on_features(&ai_bpm, &y_q)
```

AI output được làm mượt bằng EMA alpha thấp hơn:

```cpp
g_bpm_ema = 0.15 * ai_bpm + 0.85 * g_bpm_ema
```

Alpha thấp hơn DSP nghĩa là AI output được đưa vào chậm hơn, tránh nhảy mạnh.

Log:

```text
AI_ASSIST_HR=... raw_ai=... y_q=... dsp_peak=... ac=...
```

Sau đó xét quay về NORMAL.

Nếu còn cooldown:

```cpp
cooldown_windows--;
```

Chưa xét hạ state ngay.

Nếu decision frozen thì giữ HIGH.

Nếu no contact:

```cpp
good_windows = SCHED_GOOD_WINDOWS_TO_DOWN;
```

Điều này khiến scheduler có thể quay về NORMAL. Lý do: nếu không tiếp xúc, không nên cứ giữ HIGH tốn điện.

Nếu tín hiệu tốt rõ:

```cpp
quality_ok && hr_consistent && ac_best >= 0.40 && difficulty_proxy <= 0.60
```

thì tăng `good_windows`.

Nếu đủ:

```cpp
good_windows >= 5 && dwell_ok
```

đặt pending chuyển về NORMAL.

## `app_main` - Điểm Vào Firmware

```cpp
extern "C" void app_main(void)
```

ESP-IDF gọi `app_main` khi firmware bắt đầu.

### Log mode

```cpp
ESP_LOGI(TAG, "Starting PPG Scheduler (mode=%d)", ...)
```

### Khởi tạo TinyML

```cpp
if (kTinyMlEnabledByMode)
    tinyml_init()
else
    TinyML disabled
```

Fixed Normal không init TinyML để baseline năng lượng sạch hơn.

### Cấu hình GPIO profiling

```cpp
GPIO10, GPIO11 output
set level 0
```

Đảm bảo sync pin bắt đầu ở mức thấp.

### Khởi tạo I2C và MAX30102

```cpp
i2c_init()
max30102_init()
```

Sau đó in header CSV:

```cpp
printf("timestamp_ms,state,profile,quality,diff,red,ir\n");
```

### Chọn initial state

```cpp
scheduler_state_t initial_state = SCHED_STATE_HIGH;
if (kRunMode == RUN_MODE_FIXED_NORMAL)
    initial_state = SCHED_STATE_NORMAL;
```

Điểm cần chú ý:

- Fixed Normal bắt đầu NORMAL.
- Fixed High bắt đầu HIGH.
- Adaptive cũng bắt đầu HIGH trong code hiện tại.

Adaptive bắt đầu HIGH có thể nhằm nhanh chóng có dữ liệu/coverage lúc đầu, rồi scheduler hạ xuống NORMAL khi tín hiệu tốt.

### Tạo inference task

```cpp
xTaskCreatePinnedToCore(
    inference_task,
    "AI_Task",
    8192,
    nullptr,
    5,
    &inference_task_handle,
    1);
```

Task:

- Stack 8192 bytes.
- Priority 5.
- Pin vào core 1.

`app_main` tiếp tục chạy vòng đọc cảm biến.

## Vòng Lặp Đọc Cảm Biến Trong `app_main`

Vòng:

```cpp
while (true)
```

### Đọc FIFO pending

```cpp
max30102_fifo_pending(&pending)
```

Nếu lỗi:

- Tăng `consecutive_i2c_errors`.
- Freeze decision.
- Nếu lỗi >= 5 thì recover MAX30102.
- Delay 5 ms.
- Continue.

### Nếu FIFO không có mẫu

Nếu `pending == 0`, firmware làm các việc nền:

1. Nếu adaptive và có switch pending:

```cpp
apply_scheduler_state(target_state)
g_switch_pending = false
```

Chỉ chuyển state khi FIFO rỗng để không trộn dữ liệu cũ.

2. In sparse CSV log mỗi 2 giây:

```cpp
if (now - last_sparse_log_us >= 2s)
    print_sparse_csv_log(...)
```

3. Nếu quá 3 giây không có mẫu mới:

```cpp
max30102_recover()
```

4. Delay 2 ms.

### Nếu FIFO có mẫu

```cpp
for n in pending:
    max30102_read_sample(&red, &ir)
```

Mỗi mẫu:

1. Cập nhật telemetry RED/IR mới nhất.
2. Gọi:

```cpp
push_ir_sample(static_cast<float>(ir));
```

3. Cập nhật `last_activity_us`.

Nếu đọc lỗi, tăng error và có thể recover.

Sau khi đọc xong batch, firmware in sparse log nếu đến thời điểm, rồi delay 1 ms.

## Vì Sao Chỉ Dùng IR?

MAX30102 đọc cả RED và IR, nhưng firmware chỉ push IR:

```cpp
push_ir_sample(static_cast<float>(ir));
```

Trong thí nghiệm, kênh IR thường ổn định hơn cho PPG nhịp tim, đặc biệt khi dùng cảm biến kiểu MAX30102. RED vẫn được log để quan sát, nhưng pipeline xử lý chính dùng IR.

## Fast Path Và Slow Path Trong File Này

Fast Path tương ứng NORMAL:

```text
snapshot window
-> high-pass metrics
-> resample 64 Hz
-> detrend/bandpass/zscore
-> simple peak detection
-> autocorrelation
-> quality gate
-> DSP HR nếu đủ tốt
```

Không gọi:

- Full feature extraction.
- FFT PSD features.
- TinyML Invoke.

Slow Path tương ứng HIGH:

```text
snapshot window
-> high-pass metrics
-> resample 64 Hz
-> GPIO10 high
-> extract 16 features
-> GPIO10 low
-> quality gate
-> GPIO11 high
-> TinyML Invoke
-> GPIO11 low
-> AI-assisted HR
```

Đây là chỗ tạo ra khác biệt năng lượng giữa hai state.

## Quan Hệ Với Notebook `ppg_dalia.ipynb`

Notebook tạo ra:

- 16 feature.
- Scaler mean/scale.
- HR target mean/std.
- Model TFLite INT8.
- C array model.

Firmware dùng:

- `ppg_hr_mlp_int8.h` cho model.
- `kScalerMean`, `kScalerScale` để chuẩn hóa input.
- `kHrMeanBpm`, `kHrStdBpm` để denormalize output.
- Feature order giống notebook.

Nhưng có các khác biệt thực tế:

- Python dùng Butterworth `filtfilt`, firmware dùng `simple_bandpass`.
- Python dùng Welch PSD, firmware dùng FFT đơn.
- Python dùng `find_peaks` SciPy, firmware dùng `find_peaks_simple`.
- Python data là PPG-DaLiA cổ tay, firmware data là MAX30102 thật, có thể là ngón tay.

Các khác biệt này là nguồn domain shift và sai khác output cần review.

## Quan Hệ Với DAQ Node

DAQ node đọc:

- INA219 power.
- GPIO4 feature sync từ GPIO10 target.
- GPIO5 infer sync từ GPIO11 target.

Trong firmware target:

- GPIO10 high quanh `extract_ppg_features`.
- GPIO11 high quanh `Invoke`.

Nhờ vậy notebook micro-level có thể phát hiện:

- Burst feature extraction.
- Burst TinyML.
- Power tail sau xử lý.

## Những Điểm Dễ Nhầm

1. `RUN_MODE_ADAPTIVE` không có nghĩa lúc nào cũng chạy model. Model chỉ chạy trong state HIGH.
2. `Fixed High` không giống adaptive đang gặp tín hiệu xấu; nó ép HIGH liên tục để làm baseline.
3. Scheduler không chuyển state ngay trong `inference_task`; nó đặt `g_switch_pending`, còn `app_main` apply khi FIFO rỗng.
4. `quality_ok` chưa đủ để publish HR; còn cần `hr_consistent` và không `no_contact`.
5. No-contact không đẩy lên HIGH, vì không có tín hiệu thì TinyML cũng không cứu được.
6. GPIO profiling không phải tín hiệu chức năng của sensor; nó chỉ phục vụ đo năng lượng bằng DAQ.
7. `g_feat` chỉ được tính đầy đủ ở HIGH.
8. TinyML input là feature đã chuẩn hóa và quantize, không phải tín hiệu PPG thô.
9. Model output là normalized HR, phải dequantize và denormalize về BPM.
10. Resample về 64 Hz là để khớp training, dù sensor chạy 50/100 Hz.

## Luồng Theo Thời Gian Khi Thiết Bị Chạy

1. ESP32-S3 boot.
2. `app_main` chạy.
3. Nếu mode không phải Fixed Normal, TinyML init.
4. GPIO10/GPIO11 được cấu hình output.
5. I2C init.
6. MAX30102 probe.
7. Apply initial state:
   - Fixed Normal -> NORMAL 50 sps.
   - Fixed High -> HIGH 100 sps.
   - Adaptive -> HIGH 100 sps ban đầu.
8. Tạo `inference_task`.
9. Main loop đọc FIFO MAX30102.
10. Mỗi mẫu IR được push vào ring buffer.
11. Đủ stride thì notify task.
12. Task snapshot window.
13. Task tính metrics và quality gate.
14. Nếu NORMAL:
    - Nếu tín hiệu đủ tốt, publish DSP HR.
    - Nếu xấu nhiều cửa sổ và adaptive, request HIGH.
15. Nếu HIGH:
    - Trích feature.
    - Gọi TinyML.
    - Publish AI-assisted HR.
    - Nếu tín hiệu tốt đủ lâu hoặc no-contact, request NORMAL.
16. Main loop thấy request switch khi FIFO rỗng thì apply profile mới.
17. Chu trình tiếp tục.

## Tóm Tắt Các Hàm Chính

```text
tinyml_init
  Khởi tạo model TFLite Micro INT8.

i2c_init
  Khởi tạo I2C master.

max30102_init
  Probe cảm biến.

max30102_apply_profile
  Ghi register để đổi profile 50/100 sps.

apply_scheduler_state
  Chuyển NORMAL/HIGH, reset buffer, đổi sample rate.

max30102_fifo_pending
  Xem FIFO có bao nhiêu mẫu chờ.

max30102_read_sample
  Đọc 1 mẫu RED/IR.

push_ir_sample
  Đưa IR vào ring buffer, notify task nếu đủ stride.

snapshot_window
  Lấy cửa sổ IR mới nhất.

compute_hp_metrics
  Tính std_hp và ptp_hp sau high-pass.

compute_window_metrics
  Tính metrics nhẹ hoặc full feature tùy state.

extract_ppg_features
  Trích 16 feature cho model.

run_tinyml_on_features
  Scale, quantize, Invoke, dequantize output HR.

inference_task
  Quality gate, scheduler, DSP HR, TinyML HR.

app_main
  Khởi tạo hệ thống và đọc cảm biến liên tục.
```

## Điểm Cần Review Hoặc Có Thể Cải Tiến

1. `robust_zscore` trong firmware hiện dùng mean/std, không dùng median/MAD như notebook. Nếu muốn khớp notebook hơn, có thể cân nhắc sửa hoặc đổi tên.
2. Feature extraction firmware chỉ xấp xỉ Python. Cần test vector để kiểm tra sai khác feature giữa Python và ESP32.
3. Adaptive đang khởi đầu ở HIGH. Nếu mục tiêu tiết kiệm điện ngay từ đầu, có thể xem xét khởi đầu NORMAL, nhưng sẽ ảnh hưởng coverage ban đầu.
4. `MicroMutableOpResolver<1>` chỉ add FullyConnected. Nếu model converter sinh thêm op khác trong tương lai, init sẽ fail.
5. FFT dùng 256 mẫu đầu, không phải Welch toàn cửa sổ. Đây là trade-off giữa chi phí và độ tương đồng với notebook.
6. `max30102_apply_profile` reset FIFO khi đổi state. Điều này đúng để tránh trộn sample rate, nhưng tạo khoảng chờ trước khi có window mới.
7. Sparse CSV log chỉ 2 giây/lần, không đủ cho micro timing. Micro timing dựa vào DAQ sync và log Invoke.

