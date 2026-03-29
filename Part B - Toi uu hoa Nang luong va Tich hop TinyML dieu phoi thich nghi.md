# Phần B: Tối ưu hóa Năng lượng và Tích hợp TinyML điều phối thích nghi

## 1. Đặt bài toán kỹ thuật sau Phần A

Sau Phần A, hệ thống phần cứng đã đạt được ba nền tảng quan trọng: vi điều khiển ESP32-S3 hoạt động ổn định, cảm biến MAX30102 đọc được tín hiệu PPG theo thời gian thực, và INA219 cho phép đo công suất tiêu thụ của toàn hệ thống. Tuy nhiên, chính giai đoạn tích hợp phần cứng này cũng làm lộ ra giới hạn cốt lõi của cách tiếp cận DSP thuần túy. Khi ngón tay giữ yên, sóng PPG tương đối ổn định, chu kỳ tim rõ, nên các thuật toán đơn giản như dò đỉnh và tự tương quan có thể cho ra nhịp tim hợp lý. Nhưng khi người dùng rung tay, thay đổi lực tì, hoặc gõ nhịp bằng ngón tay, tín hiệu bị nhiễu cơ học mạnh, dẫn đến đỉnh giả, baseline drift, biến dạng biên độ và sai số nhịp tim tăng đột biến.

Nếu giải bài toán này bằng hướng ngược lại, tức chạy một mô hình học máy mạnh ở chế độ luôn bật, thì hệ thống sẽ đổi độ bền pin lấy độ bền thuật toán. Đây là một đánh đổi không phù hợp với wearable. Một thiết bị đeo đo sinh hiệu không chỉ cần "đo được", mà còn phải duy trì được thời lượng sử dụng đủ dài để có ý nghĩa thực tế. Vì lý do đó, mục tiêu của Phần B không phải đơn giản là tăng độ chính xác bằng mọi giá, mà là thiết kế một **bộ điều phối thích nghi nhận thức năng lượng**: chỉ dùng pipeline nặng khi tín hiệu thực sự khó, và quay về pipeline nhẹ khi điều kiện đo thuận lợi.

Từ góc nhìn kiến trúc hệ thống, đây là một bài toán tối ưu đa mục tiêu:

- Mục tiêu 1: giảm công suất trung bình của node đo.
- Mục tiêu 2: duy trì khả năng xuất nhịp tim trong điều kiện có motion artifact.
- Mục tiêu 3: không phát ra giá trị HR "đẹp nhưng sai", tức ưu tiên độ tin cậy của đầu ra hơn là tăng coverage một cách giả tạo.

Chính ba mục tiêu này dẫn đến lựa chọn cuối cùng của đề tài: **adaptive scheduling hai mức**, trong đó trạng thái `NORMAL` dùng DSP ở 50 Hz, còn trạng thái `HIGH` tăng cảm biến lên 100 Hz và kích hoạt TinyML để hỗ trợ trong các cửa sổ tín hiệu khó.

---

## 2. Giai đoạn 1: Xây dựng và tinh chỉnh bộ điều phối rule-based

### 2.1. Lý do phải bắt đầu từ scheduler dựa trên luật

Trước khi tích hợp AI, tôi không đi thẳng vào huấn luyện mô hình. Lý do là TinyML không thể cứu được một pipeline nhúng chưa hiểu rõ đặc tính tín hiệu của chính phần cứng mà nó chạy trên đó. Bước đầu tiên bắt buộc phải làm là xây dựng một scheduler dựa trên luật đủ đơn giản để:

1. ghi log được toàn hệ thống,
2. tạo được tiêu chí phân loại "cửa sổ tốt" và "cửa sổ xấu",
3. giúp quan sát tín hiệu ngoài đời thật trước khi đưa học máy vào.

Phiên bản firmware ở giai đoạn này nằm trong `C:\ml\esp32_projects\ina219_max30102_test\main\ina219_max30102_test.c`. Đây là một cột mốc rất quan trọng, vì nó vừa là công cụ ghi dữ liệu, vừa là bản prototype đầu tiên của ý tưởng adaptive scheduling.

Trong file này, các macro điều phối được khai báo như sau:

```cpp
#define SCHED_STD_MIN 250.0f
#define SCHED_PTP_MIN 1000.0f
#define SCHED_PTP_MAX 120000.0f
#define SCHED_AC_MIN 0.40f
#define SCHED_AC_HARD 0.30f
#define SCHED_AC_EASY 0.45f
#define SCHED_DIFF_HARD 0.70f
#define SCHED_DIFF_EASY 0.55f
```

Các ngưỡng này thể hiện trực tiếp triết lý ban đầu: chất lượng cửa sổ được quyết định bởi ba tiêu chí rẻ về tính toán:

- biên độ đủ lớn, đo bằng `std` và `ptp`,
- tín hiệu có chu kỳ tim, đo bằng `ac_best`,
- và một difficulty proxy để quyết định khi nào cần nâng cấp trạng thái.

### 2.2. Thu thập log thô và phân tích offline

Từ firmware rule-based, tôi xuất log hỗn hợp gồm:

- dòng CSV telemetry: timestamp, state, profile, quality, raw PPG, bus voltage, current, power,
- các sự kiện state switch,
- và các chỉ báo chất lượng cửa sổ.

Sau đó, dữ liệu được phân tích offline trong `max30102_log_analysis.ipynb`. Đây là notebook quan trọng nhất ở giai đoạn scheduler vì nó cho phép so sánh logic firmware với tín hiệu thực. Thay vì điều chỉnh ngưỡng trực tiếp trên board theo kiểu thử-sai mù, tôi chuyển sang quy trình:

1. log dữ liệu thật từ phần cứng,
2. cắt cửa sổ 8 giây, stride 2 giây,
3. tính các chỉ số quality như firmware,
4. so sánh phân phối giữa các điều kiện `good` và `bad`,
5. mô phỏng chính sách chuyển trạng thái trên notebook trước khi đưa ngược về firmware.

Cell 15 của notebook là điểm bắt đầu của cách làm này. Ở cell đó, notebook in thống kê phân vị cho `ir_raw_std`, `ir_raw_ptp`, `ac_best`, và `difficulty_score_norm`. Từ kết quả này, tôi nhận ra ngay một vấn đề: chỉ nhìn vào biên độ là chưa đủ, vì nhiều cửa sổ nhiễu mạnh lại có biên độ rất lớn, trong khi một số cửa sổ "tốt" nhưng tiếp xúc nhẹ lại có biên độ thấp hơn kỳ vọng.

### 2.3. Vấn đề "inverted logic": vì sao cửa sổ xấu lại dễ pass

Đây là phát hiện quan trọng đầu tiên trong Phần B. Ở giai đoạn đầu, scheduler có xu hướng ưu tiên cửa sổ có biên độ lớn. Trên lý thuyết, điều này hợp lý vì tiếp xúc yếu thường làm tín hiệu nhỏ, dễ nhiễu. Nhưng dữ liệu thực tế lại cho thấy biên độ lớn không đồng nghĩa với tín hiệu tốt. Khi người dùng ấn ngón tay quá mạnh hoặc tạo dao động chậm do chuyển động, biên độ thô có thể tăng rất mạnh dù thông tin nhịp tim thật bị méo.

Notebook đã ghi nhận hiện tượng này rõ ràng. Trong phần "Baseline-wander check" (Cell 11) và "Raw vs detrended gate comparison" (Cell 18), notebook chỉ ra rằng các metric biên độ thô đang bị nhiễu bởi xu hướng nền chậm. Đây chính là **baseline wander**. Khi nền tín hiệu dâng lên hoặc hạ xuống chậm theo chuyển động, các đại lượng như `std_raw` và `ptp_raw` tăng lên, làm firmware hiểu nhầm rằng cửa sổ "mạnh" và có thể pass quality gate.

Cell 18 mô tả phép thử dưới dạng mã:

```python
def moving_average_highpass(x, fs_hz, ma_sec=1.0):
    x = np.asarray(x, dtype=np.float32)
    k = max(3, int(fs_hz * ma_sec))
    if (k % 2) == 0:
        k += 1
    kernel = np.ones(k, dtype=np.float32) / float(k)
    trend = np.convolve(x, kernel, mode="same")
    return (x - trend).astype(np.float32)
```

Điểm cần nhấn mạnh ở đây là notebook không chỉ "đánh giá chất lượng", mà còn đóng vai trò như một phòng thí nghiệm để kiểm chứng giả thuyết vật lý: khi bỏ thành phần nền chậm khỏi tín hiệu, các metric chất lượng trở nên phù hợp hơn với trực giác sinh lý.

### 2.4. High-Pass EMA: sửa lỗi từ gốc thay vì vá ở ngưỡng

Sau khi xác định nguyên nhân, tôi không chọn cách tiếp tục "vặn số" cho các ngưỡng thô. Nếu bản chất metric đầu vào đã sai, thì việc đổi ngưỡng chỉ là vá lỗi cục bộ. Hướng sửa đúng là làm cho metric phản ánh thành phần dao động liên quan đến nhịp tim thay vì mức nền.

Trong firmware rule-based, điều này được triển khai bằng `scheduler_highpass_ema(...)`:

```cpp
static void scheduler_highpass_ema(const float *x, float *y, uint32_t n, float fs_hz)
{
    float fs = (fs_hz > 1.0f) ? fs_hz : 50.0f;
    float dt = 1.0f / fs;
    float alpha = dt / (SCHED_HP_TAU_SEC + dt);
    float lp = x[0];
    for (uint32_t i = 0; i < n; i++)
    {
        lp += alpha * (x[i] - lp);
        y[i] = x[i] - lp;
    }
}
```

Ý nghĩa kỹ thuật của đoạn mã này là:

- EMA đóng vai trò low-pass tracker cho nền chậm,
- phần high-pass thu được bằng `x[i] - lp`,
- metric chất lượng sau đó được tính trên tín hiệu đã bỏ nền này.

Đây là một quyết định mang tính hệ thống. Thay vì cố làm classifier phức tạp hơn, tôi sửa thẳng tầng signal conditioning. Khi metric đầu vào tốt hơn, scheduler mới có cơ hội ra quyết định tốt hơn.

### 2.5. Tạo quality gate theo "Goldilocks zone"

Sau khi có high-pass filtering, tôi tiếp tục thấy rằng không thể dùng logic biên độ một phía. Một cửa sổ tốt không phải là cửa sổ có biên độ "càng lớn càng tốt", mà là cửa sổ có biên độ nằm trong một khoảng hợp lý:

- quá nhỏ: khả năng tiếp xúc yếu, loose contact,
- quá lớn: khả năng bị hard press, finger tapping, hoặc periodic motion artifact,
- vừa phải: có khả năng là dao động PPG thật.

Đó là lý do `SCHED_PTP_MAX` được đưa vào như một cổng trên của vùng chấp nhận, tạo thành vùng **Goldilocks**: không quá yếu, không quá mạnh.

Trong `scheduler_compute_window_metrics(...)`, logic này xuất hiện rất rõ:

```cpp
float std = sqrtf(var);
float ptp = hp_max - hp_min;
float ac_best = scheduler_compute_ac_best(hp_buf, ctx->sample_count, ctx->current_fs_hz);

bool amplitude_ok = (std >= SCHED_STD_MIN) && (ptp >= SCHED_PTP_MIN) && (ptp <= SCHED_PTP_MAX);
bool periodic_ok = (ac_best >= SCHED_AC_MIN);
*quality_pass = (amplitude_ok && periodic_ok) ? 1U : 0U;
```

Điểm đáng chú ý là `periodic_ok` và `amplitude_ok` được xét đồng thời. Điều này cho thấy scheduler không còn nhìn tín hiệu theo kiểu "to là tốt", mà bắt đầu kết hợp cả:

- năng lượng dao động,
- và tính chu kỳ.

Cell 10 của notebook, phần "Firmware-synced quality gates (Goldilocks, V7)", chính là bản mirror của tư duy này ở offline side.

### 2.6. Vì sao không bê nguyên threshold thống kê từ notebook vào firmware

Cell 19 trong notebook có phần gợi ý threshold từ các metric detrended:

- `SCHED_STD_MIN ~ 9048.71`
- `SCHED_PTP_MIN ~ 69465.88`
- `SCHED_AC_MIN ~ 0.1588`

Tôi **không** dùng trực tiếp bộ ngưỡng này trong firmware cuối, dù về mặt thống kê nó xuất hiện như một ứng viên. Lý do là ngưỡng percentile-based có thể cho kết quả đẹp trên một tập log cụ thể nhưng không ổn định khi đưa lên hệ thống thật. Thực tế, chính cell 19 cho thấy bộ ngưỡng này làm `bad` pass ratio lên tới `1.0`, nghĩa là gần như mất hoàn toàn khả năng loại bỏ cửa sổ xấu. Điều đó xác nhận rằng threshold tuning cho embedded system không thể chỉ dựa trên thống kê một chiều; nó phải dựa trên hiểu biết vật lý về cơ chế tạo nhiễu.

Đây là một quyết định engineering quan trọng: notebook dùng để định hướng, nhưng firmware phải giữ được tính bảo thủ và khả năng tổng quát hóa.

### 2.7. Kết quả của giai đoạn scheduler nền tảng

Đến cuối giai đoạn này, tôi đã có:

- một pipeline log phần cứng đáng tin cậy,
- một scheduler hai trạng thái rule-based đầu tiên,
- một bộ metric chất lượng tính trên high-pass signal,
- và quan trọng nhất là hiểu đúng bản chất của motion artifact trên phần cứng thật.

Nếu bỏ qua bước này và đi thẳng vào TinyML, mô hình học máy sẽ phải "gánh" cả lỗi xử lý tín hiệu nền. Nhờ tách riêng giai đoạn rule-based, tôi giảm được phạm vi mà TinyML phải giải quyết: mô hình chỉ cần học phần khó còn lại, thay vì phải sửa cả pipeline sensor.

---

## 3. Giai đoạn 2: Dataset, feature engineering và tối ưu hóa TinyML

### 3.1. Vì sao chọn PPG-DaLiA và vì sao không dùng raw CNN

Sau khi scheduler rule-based đủ trưởng thành, bước tiếp theo là xây dựng "bộ não" cho trạng thái `HIGH`. Dataset được dùng là **PPG-DaLiA**, một bộ dữ liệu công khai có PPG kèm nhịp tim chuẩn từ ECG. Trong repo, toàn bộ quá trình này nằm trong `ppg_dalia.ipynb`.

Một lựa chọn hiển nhiên trên giấy là đưa sóng thô vào CNN hoặc một mô hình sequence-based. Tôi không chọn hướng đó vì bốn lý do:

1. **Ràng buộc bộ nhớ và compute của ESP32-S3**  
   Mô hình raw-signal thường yêu cầu nhiều tham số hơn, tensor lớn hơn, và inference cost cao hơn.

2. **Khó đồng bộ giữa Python và C++**  
   Với feature-based pipeline, tôi có thể đảm bảo rằng logic trích đặc trưng trên notebook và trên firmware gần như tương đương từng bước.

3. **Dễ chuẩn hóa và lượng tử hóa**  
   16 feature scalar dễ scale bằng Z-score hơn nhiều so với raw waveform.

4. **Dễ giải thích hơn trong bối cảnh luận văn**  
   Giáo sư có thể nhìn từng nhóm feature và hiểu tại sao mô hình có thể suy ra HR từ tín hiệu nhiễu.

Đây là quyết định cân bằng giữa hiệu năng học máy và khả năng deploy, chứ không phải chọn mô hình có độ phức tạp tối đa.

### 3.2. Từ Random Forest sang MLP

Trong notebook, mô hình baseline ban đầu được so sánh ở Cell 17:

| Model | MAE | RMSE | R2 |
|---|---:|---:|---:|
| MLP_small | 8.3755 | 12.5889 | 0.7180 |
| RF | 8.4491 | 12.8953 | 0.7041 |
| Ridge | 9.5959 | 13.5009 | 0.6756 |

Điểm mấu chốt ở đây không chỉ là `MLP_small` nhỉnh hơn `RF`, mà là **MLP phù hợp hơn cho Edge deployment**. Random Forest trên notebook có thể hoạt động khá tốt, nhưng khi đưa sang vi điều khiển, việc lưu cây quyết định, điều hướng nhánh và bảo đảm inference ổn định sẽ bất lợi hơn nhiều so với một mạng fully connected nhỏ.

Vì vậy, pipeline được chuyển sang Keras MLP để chuẩn bị cho TFLite Micro.

### 3.3. Bộ đặc trưng 16 chiều: thiết kế để đồng bộ Python và firmware

Trong firmware cuối, hàm `extract_ppg_features(...)` ở `ppg_hr_tinyml.cpp` là điểm nối trực tiếp giữa tín hiệu cảm biến và mô hình. Trước khi tính feature, tín hiệu đi qua ba bước:

```cpp
memcpy(g_scratch_x, sig_raw, sizeof(float) * static_cast<size_t>(n));
detrend_linear(g_scratch_x, n);
simple_bandpass(g_scratch_x, n, fs);
robust_zscore(g_scratch_x, n);
```

Đây là một pipeline có chủ đích:

- `detrend_linear`: bỏ xu thế tuyến tính còn sót,
- `simple_bandpass`: giữ dải quan tâm liên quan đến nhịp tim,
- `robust_zscore`: chuẩn hóa biên độ trong cửa sổ để giảm sensitivity với lực tì.

Sau đó, 16 feature được ghi vào `feat[0] ... feat[15]`:

```cpp
feat[6]  = static_cast<float>(n_peaks);
feat[7]  = static_cast<float>(n_peaks) / (static_cast<float>(n) / fs);
feat[8]  = hr_est_mean;
feat[9]  = hr_est_std;
feat[10] = peak_prom_mean;
feat[11] = ac_best;
feat[12] = ac_best_hr;
feat[13] = psd_hr_ratio;
feat[14] = spectral_entropy;
feat[15] = dom_bpm_hr_band;
```

Về mặt ý nghĩa, các feature này có thể chia thành bốn nhóm:

- **Biên độ và năng lượng**  
  `std`, `ptp`, `rms`, `abs_mean`, `peak_prom_mean`

- **Cấu trúc hình thái theo thời gian**  
  `n_peaks`, `peak_rate_per_sec`, `slope_abs_mean`

- **Ước lượng nhịp tim theo DSP**  
  `hr_est_mean`, `hr_est_std`, `ac_best`, `ac_best_hr`

- **Đặc trưng miền tần số**  
  `psd_hr_ratio`, `spectral_entropy`, `dom_bpm_hr_band`

Thiết kế này phản ánh rõ chiến lược của đề tài: TinyML không thay thế DSP hoàn toàn, mà học cách **kết hợp các "gợi ý" từ DSP** để phục hồi HR trong vùng có nhiễu.

### 3.4. Vì sao `ac_best`, `hr_est_std` và `psd_hr_ratio` đặc biệt quan trọng

Notebook cho thấy importance ranking của mô hình baseline gồm các feature nổi bật như:

- `peak_rate_per_sec`
- `n_peaks`
- `hr_est_mean`
- `ac_best_hr`
- `hr_est_std`
- `psd_hr_ratio`
- `ac_best`
- `spectral_entropy`

Điều này rất quan trọng về mặt diễn giải. Nó cho thấy mô hình không "đoán mò", mà đang khai thác:

- nhịp đập biểu kiến trong cửa sổ,
- mức độ ổn định của nhịp đập đó,
- độ tuần hoàn của tín hiệu,
- và mức tập trung năng lượng vào dải tần tim.

Nói cách khác, MLP đang học từ các dấu hiệu vật lý hợp lý, chứ không phải từ những proxy khó giải thích.

### 3.5. Breakthrough: target normalization

Điểm đột phá lớn nhất của giai đoạn TinyML không nằm ở thay đổi model architecture, mà nằm ở **chuẩn hóa đầu ra mục tiêu**. Trong Cell 21 của `ppg_dalia.ipynb`, nhãn HR được chuẩn hóa bằng Z-score trước khi huấn luyện:

```python
hr_mean = float(np.mean(y_train_vec))
hr_std = float(np.std(y_train_vec) + 1e-6)

y_train_norm = ((y_train_vec - hr_mean) / hr_std).astype(np.float32).reshape(-1, 1)
y_test_norm = ((y_test_vec - hr_mean) / hr_std).astype(np.float32)
```

Kết quả huấn luyện sau đó được de-normalize trở lại:

```python
keras_pred = (keras_pred_norm * hr_std + hr_mean).astype(np.float32)
```

Ý nghĩa của bước này là:

- mô hình học trong không gian đầu ra có phân bố dễ tối ưu hơn,
- output của mạng nằm trong dải nhỏ, thuận lợi cho lượng tử hóa INT8,
- sai số lượng tử hóa ở output không bùng lên khi chuyển từ float sang int8.

Trong firmware cuối, đúng logic này được tái hiện ở `run_tinyml_on_features(...)`:

```cpp
const int8_t y_q_local = g_output->data.int8[0];
const float y_norm = dequantize_int8(y_q_local, g_output->params.scale, g_output->params.zero_point);
*y_bpm = clampf(y_norm * kHrStdBpm + kHrMeanBpm, 40.0f, 180.0f);
```

Trong đó:

- `kHrMeanBpm = 89.3519745f`
- `kHrStdBpm  = 22.6059856f`

Đây là chỗ mà Python training pipeline và C++ inference pipeline khớp nhau một cách có chủ đích.

### 3.6. Giữ gần nguyên độ chính xác sau lượng tử hóa

Cell 22 của notebook xác nhận rằng quyết định target normalization là đúng. Các kết quả đã đo được như sau:

| Model | MAE | RMSE |
|---|---:|---:|
| Keras_MLP | 8.6395 | 13.0471 |
| TFLite_FP32 | 8.6395 | 13.0471 |
| TFLite_INT8 | 8.6512 | 13.0395 |

Kích thước mô hình:

- FP32: `14.37 KB`
- INT8: `7.79 KB`
- tỉ lệ nén: `1.845x`

Trong log khởi tạo firmware, `tinyml_init()` cũng in:

```cpp
ESP_LOGI(TAG, "Model size: %u bytes", ppg_hr_mlp_int8_tflite_len);
ESP_LOGI(TAG, "Input quant: scale=%.8f, zp=%d", g_input->params.scale, g_input->params.zero_point);
ESP_LOGI(TAG, "Output quant: scale=%.8f, zp=%d", g_output->params.scale, g_output->params.zero_point);
ESP_LOGI(TAG, "Tensor arena used: %u / %u bytes", ...);
```

Ở hệ thống hiện tại, các giá trị tương ứng là:

- model size log: `7976 bytes`
- tensor arena: `16 KB`
- input quantization: `scale=0.04944235`, `zero_point=-40`
- output quantization: `scale=0.02073984`, `zero_point=-31`

Về mặt luận văn, đây là một bằng chứng rất mạnh: mô hình đã được nén xuống mức phù hợp với ESP32-S3 mà gần như không hi sinh độ chính xác so với pipeline float.

### 3.7. Domain shift: cổ tay trong dataset, đầu ngón tay trên phần cứng

Một quan sát thực nghiệm quan trọng là dataset PPG-DaLiA thu ở cổ tay, trong khi prototype thật đo ở đầu ngón tay. Hai miền đo này không hoàn toàn tương đương:

- PPG ở đầu ngón tay thường có biên độ lớn hơn,
- đỉnh phụ và biến dạng do áp lực tiếp xúc xuất hiện rõ hơn,
- periodic artifact do finger tapping dễ "trông giống có chu kỳ" hơn so với wrist motion.

Điều này giải thích vì sao mô hình dù giữ được MAE tốt trên notebook vẫn cần sự hỗ trợ của scheduler và các quality gate chặt chẽ ở firmware cuối. TinyML trong đề tài không được dùng như một hộp đen thay thế mọi thứ; nó được đặt vào một khung điều phối để bù cho domain shift và giới hạn triển khai thực tế.

---

## 4. Giai đoạn 3: Tích hợp dual-core và sửa lỗi hệ thống ngoài đời thật

### 4.1. Bug gốc: inference chặn sensor loop

Khi chuyển từ notebook sang firmware thật, vấn đề lớn nhất không còn là MAE, mà là **tính sống còn của pipeline thời gian thực**. Phiên bản đầu tiên đặt việc đọc cảm biến và suy luận TinyML trong cùng một luồng điều khiển. Khi inference kéo dài, việc phục vụ FIFO của MAX30102 bị chậm, dẫn đến:

- tràn FIFO,
- lỗi đọc con trỏ ghi/đọc,
- mất đồng bộ I2C,
- và trong thực tế là cảm giác "sensor/LED bị đứng".

Đây là ví dụ điển hình của khác biệt giữa "model chạy được" và "hệ thống chạy được".

Firmware cuối trong `ppg_hr_tinyml.cpp` có đoạn giám sát FIFO rất rõ:

```cpp
esp_err_t max30102_fifo_pending(uint8_t *pending)
{
    ESP_RETURN_ON_ERROR(max30102_read_reg(REG_FIFO_WR_PTR, &wr), TAG, "read wr ptr fail");
    ESP_RETURN_ON_ERROR(max30102_read_reg(REG_FIFO_RD_PTR, &rd), TAG, "read rd ptr fail");
    ESP_RETURN_ON_ERROR(max30102_read_reg(REG_OVF_COUNTER, &ovf), TAG, "read ovf fail");

    if (ovf > 0)
    {
        ESP_LOGW(TAG, "MAX30102 FIFO overflow=%u, wr=%u rd=%u", ...);
        max30102_write_reg(REG_OVF_COUNTER, 0x00);
    }
}
```

Các log `max30102_fifo_pending(...): read rd ptr fail`, `read wr ptr fail`, và `MAX30102 FIFO overflow=...` chính là dấu vết trực tiếp của bug này.

### 4.2. Quyết định chuyển sang kiến trúc dual-core FreeRTOS

Để sửa bug, tôi không tối ưu vi mô từng lệnh inference. Tôi đổi kiến trúc toàn hệ thống:

- **Core 0**: ưu tiên đọc sensor, duy trì ring buffer, đọc power monitor.
- **Core 1**: chỉ làm inference và điều phối.

Task AI được pin cố định sang Core 1:

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

Việc tách này giải quyết đúng nguyên nhân:

- sensor loop không còn bị inference chặn cứng,
- FIFO được rút dữ liệu đều hơn,
- và trạng thái cảm biến khi đổi profile ít bị rơi vào lockup hơn.

Đây là một bước tiến từ tư duy "chạy tuần tự một thuật toán" sang tư duy "thiết kế hệ thống thời gian thực".

### 4.3. Cơ chế snapshot, notification và switch pending

Trong kiến trúc cuối, pipeline chạy theo chuỗi:

1. Core 0 thu mẫu vào ring buffer.
2. Khi đủ stride/cửa sổ, Core 0 đánh thức AI task bằng notification.
3. Core 1 snapshot cửa sổ hiện tại qua `compute_window_features(...)`.
4. Core 1 ra quyết định:
   giữ `NORMAL`, chuyển sang `HIGH`, hay từ `HIGH` hạ xuống `NORMAL`.
5. Việc đổi profile thật của MAX30102 không diễn ra tùy tiện trong AI task, mà đi qua cơ chế `g_switch_pending` và `g_desired_state`.

Đây là một chi tiết nhỏ nhưng quan trọng về độ ổn định. Việc đổi profile cảm biến được trì hoãn đến lúc sensor loop thấy điều kiện an toàn hơn, thay vì đổi ngay trong ngữ cảnh đang xử lý cửa sổ.

### 4.4. Decision freeze và recovery path

Một bổ sung đáng chú ý khác là cơ chế "đóng băng quyết định" sau lỗi. Trong code:

```cpp
constexpr int DECISION_FREEZE_ON_ERROR_WINDOWS = 2;
constexpr int DECISION_FREEZE_ON_RECOVER_WINDOWS = 4;
```

và:

```cpp
if (max30102_fifo_pending(&pending) != ESP_OK)
{
    consecutive_i2c_errors++;
    add_decision_freeze_windows(DECISION_FREEZE_ON_ERROR_WINDOWS);
    if (consecutive_i2c_errors >= 5)
    {
        max30102_recover();
        consecutive_i2c_errors = 0;
    }
    vTaskDelay(pdMS_TO_TICKS(5));
    continue;
}
```

Ý nghĩa của decision freeze là: sau một biến cố I2C hoặc sau khi recover, không nên tin ngay quality gate của một vài cửa sổ kế tiếp, vì bản thân trạng thái sensor đang ở pha chuyển tiếp. Đây là một sửa lỗi mang tính hệ thống rất thực dụng: scheduler không chỉ thông minh ở trạng thái bình thường, mà còn biết "khi nào không nên tin chính mình".

### 4.5. Tích hợp TinyML vào scheduler cuối

Hàm `compute_window_features(...)` là cầu nối giữa sensor và model:

```cpp
compute_hp_metrics(g_win_sensor, window_samples_snapshot, static_cast<float>(fs_snapshot), std_hp, ptp_hp);
resample_linear(g_win_sensor, window_samples_snapshot, g_win_model, kWindowSamplesModel);
extract_ppg_features(g_win_model, kWindowSamplesModel, kModelFs, g_feat);
*peak_bpm = g_feat[7] * 60.0f;
*ac_best = g_feat[11];
```

Điểm đáng chú ý là cùng một cửa sổ sensor thô được dùng cho hai mục đích:

- tính quality gate từ high-pass metrics,
- và tạo feature vector cho TinyML.

Điều này giúp scheduler và model cùng nhìn vào cùng một thực tại tín hiệu, thay vì hai pipeline tách rời.

Ở `run_tinyml_on_features(...)`, các feature được chuẩn hóa lại bằng mean/scale cố định trước khi quantize sang INT8:

```cpp
float x_sc = (g_feat[i] - kScalerMean[i]) / (kScalerScale[i] + 1e-8f);
x_sc = clampf(x_sc, -6.0f, 6.0f);
float qf = x_sc / in_scale + static_cast<float>(in_zp);
```

Đây là một chi tiết rất quan trọng để báo cáo nêu rõ: firmware không "copy số" từ notebook một cách thủ công, mà thực thi đúng pipeline chuẩn hóa đã được học từ training stage.

### 4.6. Hai EMA khác nhau cho DSP và AI

Trong `inference_task(...)`, đầu ra DSP và AI đều được làm mượt, nhưng bằng hai hệ số khác nhau:

```cpp
constexpr float kEmaAlpha = 0.35f;   // DSP
constexpr float kAiEmaAlpha = 0.15f; // AI
```

Đây là một quyết định giao giữa engineering và human factors:

- DSP trong trạng thái tốt thường ổn định hơn, nên có thể phản ứng nhanh hơn.
- AI trong trạng thái nhiễu có phương sai cao hơn, nên cần smoothing mạnh hơn để tránh HR nhảy gắt.

Nếu không có bước này, người dùng có thể thấy HR nhảy kiểu `82 -> 97 -> 88 -> 104` trong vài cửa sổ liên tiếp, khiến trải nghiệm hiển thị bị "cơ khí" và làm giảm niềm tin vào hệ thống.

### 4.7. Siết `SCHED_PTP_MAX` để chặn periodic motion artifacts

Một cải tiến quan trọng ở firmware cuối là giảm `SCHED_PTP_MAX` xuống:

```cpp
constexpr float SCHED_PTP_MAX = 35000.0f;
```

so với bản rule-based trước đó:

```cpp
#define SCHED_PTP_MAX 120000.0f
```

Lý do không phải vì "thích chặt hơn", mà vì các thử nghiệm thực tế cho thấy một số periodic motion artifacts, đặc biệt là finger tapping, vừa có:

- biên độ rất lớn,
- vừa có tính chu kỳ,
- và có thể đánh lừa cả `ac_best`.

Nếu giữ upper bound quá rộng, scheduler sẽ xem nhiều cửa sổ tapping là "có chu kỳ hợp lệ". Khi siết `SCHED_PTP_MAX`, hệ thống bắt đầu chặn được nhiều trường hợp hard press/tapping hơn. Đây là chỗ domain shift giữa wrist data và fingertip data biểu hiện rõ nhất: tín hiệu ở đầu ngón tay mang nhiều biến thiên cơ học hơn và cần gate bảo thủ hơn.

### 4.8. Logic quality gate và chuyển trạng thái ở phiên bản cuối

Hạt nhân của scheduler cuối nằm trong `inference_task(...)`:

```cpp
const bool amplitude_ok = (std_hp >= SCHED_STD_MIN) && (ptp_hp >= SCHED_PTP_MIN) && (ptp_hp <= SCHED_PTP_MAX);
const bool periodic_ok = (ac_best >= SCHED_AC_MIN);
const bool hr_range_ok = (peak_bpm >= 40.0f) && (peak_bpm <= 180.0f);
const bool quality_ok = amplitude_ok && periodic_ok && hr_range_ok;
```

Sau đó, scheduler còn kiểm tra thêm:

- `hr_consistent` giữa peak-based HR và autocorr HR,
- `no_contact_hard` và `no_contact_soft`,
- `difficulty_proxy`,
- dwell time,
- decision freeze.

Điều này cho thấy phiên bản cuối không còn là một scheduler threshold đơn giản nữa, mà là một **state machine có bộ nhớ**, biết cân bằng giữa:

- tốc độ phản ứng,
- độ chắc chắn của quyết định,
- và ổn định hệ thống sau khi chuyển trạng thái.

---

## 5. Giai đoạn 4: Đánh giá macro-level về năng lượng và độ tin cậy

### 5.1. Mục tiêu của đánh giá macro-level

Sau khi firmware cuối hoạt động ổn định, bước cuối cùng không phải là chỉnh thêm ngưỡng, mà là chứng minh rằng adaptive scheduling thực sự tạo ra lợi ích ở cấp hệ thống. Phần này được thực hiện trong `ppg_hr_macro_analysis.ipynb` và thư viện `ppg_hr_macro_analysis_lib.py`.

Ba chế độ được so sánh là:

- `fixed_normal`: luôn chạy DSP ở 50 Hz,
- `fixed_high`: luôn chạy profile cao và TinyML hỗ trợ,
- `adaptive`: tự chuyển giữa hai chế độ theo scheduler.

Protocol đo chuẩn gồm ba pha:

1. Rest 1, 60 giây
2. Motion, 60 giây
3. Rest 2, 60 giây

Việc đánh giá không chỉ dùng power, mà còn dùng **HR coverage**, tức tỉ lệ thời gian hệ thống xuất được một HR hợp lệ thay vì drop cửa sổ do low quality. Đây là chỉ số phù hợp hơn MAE trong bối cảnh embedded deployment, vì người dùng thực sự quan tâm thiết bị có "sống" hay không trong pha nhiễu.

### 5.2. Kết quả KPI tổng

Từ notebook hiện tại, các KPI đã xác minh là:

| Mode | Avg Power (mW) | HR Coverage (%) | Battery Life (h) |
|---|---:|---:|---:|
| adaptive | 16.83 | 59.76 | 32.98 |
| fixed_high | 18.65 | 96.22 | 29.75 |
| fixed_normal | 16.65 | 28.90 | 33.33 |

Với giả định pin `150 mAh, 3.7 V`, adaptive giảm công suất trung bình khoảng `9.78%` so với fixed high và kéo dài thời lượng pin khoảng `10.83%`.

Từ góc nhìn năng lượng, kết quả này xác nhận ý tưởng ban đầu là đúng: không cần giữ AI luôn bật để đạt lợi ích rõ rệt. Adaptive mode đã tiến gần fixed normal về công suất hơn là fixed high, dù vẫn có khả năng phục hồi HR trong pha khó.

### 5.3. So sánh ở pha motion: nơi adaptive phải chứng minh giá trị

Ở pha `Motion`, các coverage hiện tại là:

- `adaptive`: `57.99%`
- `fixed_high`: `95.75%`
- `fixed_normal`: `2.05%`

So sánh này rất quan trọng. Nếu chỉ nhìn coverage tổng, người đọc có thể thấy adaptive thấp hơn fixed high và cho rằng scheduler còn yếu. Nhưng cách diễn giải đúng phải là:

- `fixed_normal` gần như tê liệt khi có motion artifact,
- `fixed_high` giữ coverage rất cao nhưng trả giá bằng power cao nhất,
- `adaptive` đứng ở giữa: tiết kiệm năng lượng nhưng vẫn cứu được phần lớn khoảng trống mà DSP-only không xử lý nổi.

Tính theo tỉ lệ, adaptive giữ motion coverage cao hơn fixed normal khoảng `28.3x`. Đây là bằng chứng định lượng mạnh nhất cho giá trị thực của tầng TinyML hỗ trợ.

### 5.4. Vì sao coverage của adaptive chỉ khoảng 60%, và vì sao đó không phải thất bại

Coverage của adaptive thấp hơn fixed high khoảng `36.5` điểm phần trăm. Tôi xem đây không phải là thất bại, mà là hậu quả trực tiếp của hai quyết định thiết kế có chủ đích.

#### (1) Strict quality gating

Scheduler của firmware cuối được thiết kế để **drop cửa sổ không chắc chắn**, thay vì cố ép ra một HR. Điều này thể hiện qua các nhánh:

- `QFR_AMP_FAIL`
- `QFR_AC_FAIL`
- `QFR_HR_RANGE_FAIL`
- `QFR_CONSIST_FAIL`
- `QFR_NO_CONTACT`

Nói cách khác, hệ thống chấp nhận hy sinh coverage để bảo vệ độ tin cậy của output. Trong bối cảnh biomedical sensing, đây là đánh đổi hợp lý hơn so với việc hiển thị liên tục nhưng thiếu căn cứ.

#### (2) Hardware switching cost

Adaptive mode phải chịu một chi phí mà fixed high không có: chuyển từ 50 Hz sang 100 Hz và đổi profile sensor. Chính trong các cửa sổ ngay sau lúc chuyển trạng thái, sensor pipeline dễ bị nhiễu chuyển tiếp, FIFO dễ rung, và decision freeze cũng làm hệ thống bảo thủ hơn. Do đó, một phần coverage mất đi là "chi phí điều phối", không phải dấu hiệu TinyML thất bại.

Notebook macro đã thêm hẳn phần narrative để giải thích điều này, và đó là cách trình bày tôi sẽ giữ trong báo cáo: adaptive không được thiết kế để thắng fixed high ở coverage tuyệt đối; nó được thiết kế để tìm một điểm Pareto hợp lý giữa coverage và năng lượng.

### 5.5. Câu trade-off của luận văn

Nếu cần cô đọng thông điệp của toàn bộ Phần B trong một câu có tính kết luận, thì kết quả hiện tại cho phép phát biểu:

> Adaptive mode đánh đổi khoảng `36.5` điểm coverage so với fixed high để đổi lấy khoảng `10.8%` cải thiện thời lượng pin, đồng thời duy trì khả năng quan sát nhịp tim trong pha motion cao hơn fixed normal khoảng `28.3` lần.

Đây là câu kết nối trực tiếp giữa ba tầng công việc của đề tài:

- tầng xử lý tín hiệu,
- tầng TinyML,
- và tầng đánh giá hệ thống.

---

## 6. Kết luận kỹ thuật của Phần B

Nhìn lại toàn bộ hành trình, đóng góp quan trọng nhất của Phần B không nằm ở việc "gắn một mô hình AI lên ESP32", mà nằm ở việc thiết kế được một hệ thống thích nghi hoàn chỉnh, trong đó mỗi tầng đều được tinh chỉnh dựa trên bằng chứng thực nghiệm:

- **Tầng signal processing**  
  Chuyển từ metric biên độ thô sang high-pass conditioned metric để xử lý baseline wander.

- **Tầng decision logic**  
  Phát triển quality gate kiểu Goldilocks, thêm upper bound cho biên độ và thêm các luật consistency/no-contact để tăng tính bảo thủ.

- **Tầng TinyML**  
  Chọn feature-based MLP thay vì raw CNN, giữ pipeline Python-C++ đồng bộ, và dùng target normalization để đưa INT8 xuống mức triển khai được mà không đánh đổi đáng kể về sai số.

- **Tầng hệ thống nhúng**  
  Chuyển sang dual-core FreeRTOS, tách sensor loop khỏi inference, thêm decision freeze, recovery path và output smoothing để giải quyết các lỗi chỉ xuất hiện trong vận hành thật.

- **Tầng đánh giá**  
  Chứng minh adaptive scheduling mang lại lợi ích thật ở cấp hệ thống chứ không chỉ ở cấp mô hình: power giảm, battery life tăng, và motion coverage vượt xa DSP-only.

Điểm quan trọng nhất về mặt học thuật là: kết quả cuối cùng không đến từ một thay đổi đơn lẻ, mà từ một chuỗi tối ưu liên tiếp, trong đó mỗi quyết định sau đều dựa trên bài học rút ra từ lỗi của quyết định trước. Chính chuỗi thử nghiệm, phản biện và sửa lỗi này mới là phần có giá trị nhất của Phần B.

---

## 7. Tài liệu và mã nguồn được dùng làm căn cứ trong phần này

- Firmware rule-based giai đoạn đầu: `C:\ml\esp32_projects\ina219_max30102_test\main\ina219_max30102_test.c`
- Firmware tích hợp cuối: `C:\ml\esp32_projects\ppg_hr_tinyml\main\ppg_hr_tinyml.cpp`
- Phân tích scheduler và quality gate: `max30102_log_analysis.ipynb`
  - Cell 10: firmware-synced Goldilocks gate
  - Cell 11: baseline-wander check
  - Cell 18: raw vs detrended gate diagnostics
  - Cell 19: suggested threshold candidates
  - Cell 20-21: compact summary và occupancy
- Huấn luyện TinyML: `ppg_dalia.ipynb`
  - Cell 17: so sánh Ridge, RF, MLP_small
  - Cell 21: Keras MLP và target normalization
  - Cell 22: so sánh Keras, TFLite FP32, TFLite INT8
- Đánh giá macro-level:
  - `ppg_hr_macro_analysis.ipynb`
  - `ppg_hr_macro_analysis_lib.py`
  - các figure trong `artifacts/ppg_hr_macro_analysis`
