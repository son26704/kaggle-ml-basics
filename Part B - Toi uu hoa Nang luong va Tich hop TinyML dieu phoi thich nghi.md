# Phần B: Tối ưu hóa năng lượng và tích hợp TinyML điều phối thích nghi

## 1. Đặt lại bài toán sau Phần A

Sau Phần A, prototype đã chứng minh được ba điều kiện tiên quyết: ESP32-S3 đọc được dữ liệu quang từ MAX30102, INA219 ghi được telemetry năng lượng, và BPM cơ bản có thể suy ra từ tín hiệu PPG trong điều kiện nghỉ. Tuy nhiên, chính lúc chuyển từ “đọc được tín hiệu” sang “đo được một hệ thống đeo thực tế” thì các giới hạn kỹ thuật mới lộ ra rõ ràng.

Giới hạn thứ nhất là **độ bền vững của DSP-only**. Peak detection và autocorrelation cho kết quả hợp lý khi ngón tay giữ yên, nhưng nhanh chóng suy giảm khi có rung tay, thay đổi lực ép, nhấc ngón tay hoặc tạo nhiễu cơ học tuần hoàn. Giới hạn thứ hai là **chi phí năng lượng của toàn hệ thống**. Nếu chỉ nâng sample rate và chạy pipeline nặng mọi lúc, hệ thống có thể tăng khả năng bám HR, nhưng sẽ đánh đổi trực tiếp thời lượng pin. Giới hạn thứ ba là **độ tin cậy của đầu ra**. Trong bối cảnh cảm biến sinh hiệu, một giá trị HR “đẹp nhưng sai” còn nguy hiểm hơn việc tạm thời không xuất ra giá trị nào.

Vì vậy, bài toán của Phần B không còn là “dùng AI để chính xác hơn”, mà là thiết kế một cơ chế **adaptive scheduling nhận thức năng lượng**. Hệ thống phải biết khi nào tín hiệu đủ tốt để chỉ dùng DSP nhẹ, khi nào phải chuyển sang chế độ nặng hơn với sample rate cao hơn và TinyML hỗ trợ, và khi nào nên chấp nhận drop window để bảo toàn độ tin cậy của đầu ra.

Kiến trúc cuối cùng của đề tài vì thế được xây theo hai trạng thái:

- `NORMAL`: đọc ở `50 Hz`, ưu tiên DSP và quality gate bảo thủ.
- `HIGH`: đọc ở `100 Hz`, trích feature đầy đủ và kích hoạt TinyML để hỗ trợ trong cửa sổ tín hiệu khó.

Điểm quan trọng là Phần B không đi thẳng từ ý tưởng sang kết quả cuối. Toàn bộ quá trình phải đi qua nhiều vòng thử-sai, trong đó mỗi lần thu log và sửa firmware đều thay đổi cách hiểu của tôi về chính hệ thống đang xây.

---

## 2. Giai đoạn 1: Dựng nền bằng scheduler rule-based

### 2.1. Vì sao phải bắt đầu từ luật trước khi dùng AI

Trước khi huấn luyện mô hình, tôi cần một cách quan sát được tín hiệu thật trên phần cứng, hiểu được khi nào cửa sổ tốt, khi nào cửa sổ xấu, và khi nào bộ điều phối nên phản ứng. Vì vậy, bước đầu tiên là xây một scheduler dựa trên luật trong project `ina219_max30102_test.c`.

Ở giai đoạn này, các ngưỡng cơ bản như `SCHED_STD_MIN`, `SCHED_PTP_MIN`, `SCHED_PTP_MAX`, `SCHED_AC_MIN`, `SCHED_AC_HARD`, `SCHED_AC_EASY` được dùng để quyết định:

- cửa sổ có đủ biên độ hay không,
- tín hiệu có đủ tính chu kỳ hay không,
- và có nên chuyển trạng thái hay không.

Điểm quan trọng về phương pháp là: firmware không được tinh chỉnh “mù” trên board. Toàn bộ log được đẩy ra file CSV, rồi phân tích offline trong `max30102_log_analysis.ipynb`. Quy trình này giúp tôi đồng bộ logic giữa notebook và firmware, thay vì vừa sửa ngưỡng vừa đoán nguyên nhân bằng trực giác.

### 2.2. Baseline wander và lỗi “inverted logic”

Phát hiện quan trọng đầu tiên là logic biên độ thô bị đảo nghĩa trong nhiều cửa sổ xấu. Trên lý thuyết, biên độ lớn thường được hiểu là tín hiệu mạnh. Nhưng ở dữ liệu thật, nhiều cửa sổ nhiễu nặng do chuyển động hoặc ấn ngón tay quá mạnh lại có `std` và `ptp` cao hơn cửa sổ tốt. Nếu dùng tín hiệu thô, scheduler sẽ vô tình để nhiều cửa sổ xấu pass quality gate.

Notebook `max30102_log_analysis.ipynb` chỉ ra rõ điều này trong các cell baseline-wander và so sánh `raw vs detrended`. Kết luận kỹ thuật là: metric chất lượng phải được tính trên tín hiệu đã bỏ nền chậm, chứ không phải trên biên độ thô.

Điều đó dẫn đến việc triển khai `scheduler_highpass_ema(...)` trong firmware, với ý tưởng dùng EMA như một bộ bám nền low-pass và lấy phần high-pass bằng `x[i] - lp`. Khi quality metric được tính trên high-pass signal, logic của scheduler mới khớp hơn với bản chất vật lý của tín hiệu PPG.

### 2.3. Goldilocks zone thay cho logic “càng to càng tốt”

Sau khi xử lý baseline wander, tôi vẫn thấy một vấn đề: biên độ không thể được đánh giá theo kiểu một chiều. Tín hiệu quá nhỏ thường là tiếp xúc yếu, nhưng tín hiệu quá lớn cũng có thể là hard press hoặc finger tapping. Do đó `SCHED_PTP_MAX` được đưa vào để tạo một vùng chấp nhận kiểu **Goldilocks**:

- không quá nhỏ,
- không quá lớn,
- đủ để có khả năng là dao động PPG thật.

Khi kết hợp `amplitude_ok` với `periodic_ok`, scheduler bắt đầu có khả năng phân biệt tốt hơn giữa:

- cửa sổ tín hiệu tốt,
- cửa sổ nhiễu biên độ lớn nhưng vô nghĩa sinh lý,
- và cửa sổ no-contact.

### 2.4. Ý nghĩa của giai đoạn nền tảng

Bước rule-based này có giá trị lớn hơn việc đơn thuần dựng một state machine. Nó giúp tôi thu hẹp đúng phần việc cần giao cho TinyML. Nếu không có bước này, mô hình học máy sẽ phải gánh luôn cả lỗi signal conditioning và quality gate. Sau giai đoạn 1, hệ thống đã có:

- pipeline log ổn định,
- quality metric có ý nghĩa vật lý hơn,
- state machine ban đầu,
- và quan trọng nhất là một ngôn ngữ định lượng để mô tả “cửa sổ tốt / xấu”.

---

## 3. Giai đoạn 2: Dataset, feature engineering và tối ưu hóa TinyML

### 3.1. Vì sao chọn feature-based MLP thay vì raw CNN

Dataset dùng để huấn luyện là `PPG-DaLiA`, một bộ dữ liệu công khai có PPG và nhịp tim chuẩn từ ECG. Tôi không chọn hướng đưa raw waveform vào CNN vì ba lý do thực dụng:

- tài nguyên ESP32-S3 hạn chế về RAM và compute;
- khó đảm bảo pipeline Python và firmware đồng bộ từng bước;
- khó lượng tử hóa và giải thích hơn trong bối cảnh luận văn.

Thay vào đó, tôi xây một pipeline **feature-based TinyML**. Tín hiệu đầu vào được detrend, band-pass, robust z-score, sau đó trích 16 đặc trưng thời gian và tần số trong `extract_ppg_features(...)` của `ppg_hr_tinyml.cpp`.

Các nhóm feature chính gồm:

- biên độ và năng lượng: `std`, `ptp`, `rms`, `abs_mean`, `peak_prom_mean`;
- cấu trúc thời gian: `n_peaks`, `peak_rate_per_sec`, `slope_abs_mean`;
- gợi ý từ DSP: `hr_est_mean`, `hr_est_std`, `ac_best`, `ac_best_hr`;
- miền tần số: `psd_hr_ratio`, `spectral_entropy`, `dom_bpm_hr_band`.

Đây là thiết kế quan trọng về mặt học thuật: TinyML không thay thế DSP, mà học cách **kết hợp những tín hiệu gợi ý do DSP tạo ra** để suy ra HR trong điều kiện nhiễu.

### 3.2. Từ Random Forest sang MLP

Trong notebook `ppg_dalia.ipynb`, Random Forest và MLP đều được thử làm baseline. `MLP_small` cho kết quả tốt hơn một chút so với `RF`, nhưng điểm quan trọng hơn là MLP phù hợp với triển khai nhúng hơn nhiều. Một mạng fully connected nhỏ có thể xuất sang TFLite Micro, lượng tử hóa INT8 và chạy ổn định trên ESP32-S3, trong khi Random Forest không mang lại lợi thế tương xứng ở lớp triển khai.

### 3.3. Breakthrough quan trọng nhất: target normalization

Điểm đột phá không nằm ở việc đổi mô hình, mà ở **chuẩn hóa đầu ra HR** bằng Z-score. Trong notebook, nhãn HR được chuẩn hóa bởi:

```python
hr_mean = float(np.mean(y_train_vec))
hr_std = float(np.std(y_train_vec) + 1e-6)
```

sau đó de-normalize lại ở phía firmware bằng:

```cpp
*y_bpm = clampf(y_norm * kHrStdBpm + kHrMeanBpm, 40.0f, 180.0f);
```

với:

- `kHrMeanBpm = 89.3519745f`
- `kHrStdBpm = 22.6059856f`

Lợi ích của bước này là output của mạng nằm trong không gian dễ lượng tử hóa hơn, nên bản INT8 gần như giữ được chất lượng của bản FP32. Kết quả notebook cho thấy:

- `Keras_MLP MAE = 8.6395`
- `TFLite_FP32 MAE = 8.6395`
- `TFLite_INT8 MAE = 8.6512`

trong khi model size giảm từ `14.37 KB` xuống `7.79 KB`, đúng mức phù hợp cho triển khai edge.

### 3.4. Domain shift giữa dữ liệu huấn luyện và phần cứng thật

Một quan sát thực nghiệm rất quan trọng là `PPG-DaLiA` thu ở cổ tay, trong khi phần cứng của tôi đo ở đầu ngón tay. Đây là một **domain shift có thật**. PPG ở đầu ngón tay thường có biên độ lớn hơn, nhạy hơn với lực ép, và xuất hiện nhiều periodic artifact kiểu finger tapping hơn.

Điều đó giải thích vì sao TinyML không thể được dùng như “hộp đen thay mọi thứ”. Nó phải được đặt trong một khung điều phối có quality gate và state machine đi kèm. Nói cách khác, mô hình chỉ là một phần của lời giải; phần còn lại nằm ở cách hệ thống quyết định khi nào có quyền tin vào mô hình.

---

## 4. Giai đoạn 3: Tích hợp dual-core và sửa lỗi hệ thống thời gian thực

### 4.1. Bug gốc: inference chặn sensor loop

Khi đưa mô hình từ notebook lên phần cứng thật, vấn đề lớn nhất không còn là MAE mà là **tính sống còn của pipeline real-time**. Ở phiên bản đầu, việc đọc cảm biến và suy luận TinyML từng nằm trong cùng một luồng. Khi inference kéo dài, MAX30102 không được phục vụ FIFO đúng nhịp, dẫn đến:

- `FIFO overflow`,
- lỗi đọc pointer,
- mất đồng bộ I2C,
- và hiện tượng ngoài đời là sensor/LED “đứng”.

Đây là khoảng cách rất điển hình giữa một mô hình “chạy được” và một hệ thống “vận hành được”.

### 4.2. Kiến trúc dual-core FreeRTOS

Cách sửa đúng không phải là vi chỉnh vài vòng lặp, mà là đổi kiến trúc:

- **Core 0**: đọc sensor, duy trì ring buffer, đọc power monitor;
- **Core 1**: chạy `inference_task`, đánh giá chất lượng cửa sổ, quyết định state và gọi TinyML khi cần.

Task AI được pin sang Core 1 bằng `xTaskCreatePinnedToCore(...)`, trong khi sensor loop tiếp tục được ưu tiên giữ nhịp ở Core 0. Việc này giải quyết đúng nguyên nhân gốc: đọc sensor không còn bị block bởi suy luận.

### 4.3. Decision freeze, recovery path và smoothing

Sau khi xử lý bug block, firmware còn được bổ sung thêm các cơ chế phòng thủ:

- `decision freeze` để scheduler tạm thời không tự tin quá mức ngay sau khi recover hoặc ngay sau lỗi I2C;
- `max30102_recover()` để đưa cảm biến về trạng thái sạch khi cần;
- EMA riêng cho DSP (`kEmaAlpha = 0.35`) và cho AI (`kAiEmaAlpha = 0.15`) để tránh đầu ra HR nhảy gắt.

Cùng với đó, `SCHED_PTP_MAX` được siết lại xuống `35000.0f` ở firmware cuối nhằm chặn tốt hơn periodic motion artifact trên đầu ngón tay. Đây là một ví dụ rõ của việc knowledge từ notebook phải quay ngược trở lại firmware dưới dạng luật bảo thủ hơn.

---

## 5. Giai đoạn 4: Chuỗi debug năng lượng V2-V6

Đây là phần thay đổi nhiều nhất so với bản Part B ban đầu. Ban đầu tôi từng cho rằng chỉ cần có adaptive scheduler và TinyML là đủ để chứng minh lợi ích năng lượng. Thực tế không đơn giản như vậy. Cách nối nguồn, cách đọc INA219 và chính cách log power đã ảnh hưởng trực tiếp đến kết luận thực nghiệm.

### 5.1. Từ đo nhánh cảm biến sang đo whole-system power

Ở giai đoạn đầu, INA219 đo nhánh cảm biến. Cách này tốt cho việc hiểu MAX30102, nhưng không thể dùng để trả lời câu hỏi macro-level: `DSP-only`, `AI-assisted`, và `adaptive` khác nhau bao nhiêu khi xét trên **toàn bộ node**.

Vì vậy, wiring cuối cùng được chuyển sang:

`PC USB VBUS -> INA219 shunt -> ESP32 VIN 5V`

sau đó:

- `ESP32 3V3 -> MAX30102`
- `ESP32 3V3 -> INA219 logic`

Đây là bước thay đổi phương pháp luận lớn nhất của phần đánh giá năng lượng.

### 5.2. V2: khoảng cách power biến mất và adaptive spike bất thường

Ở bộ log `V2`, hai hiện tượng xảy ra cùng lúc:

- `fixed_normal` và `fixed_high` gần như không tách power rõ;
- `adaptive` có những đoạn power cao kéo dài ngay cả sau khi log đã báo quay về `NORMAL`.

Khi đó còn có một yếu tố phần cứng gây nhiễu: đường cấp nguồn đi qua module `CP2102 USB-to-TTL`, tạo thêm nghi ngờ về sụt áp và parasitic overhead. Kết quả `V2` đủ để kết luận rằng cách đo lúc đó chưa đáng tin, nhưng chưa đủ để chỉ ra nguyên nhân nằm ở firmware hay wiring.

### 5.3. V3: khởi động ở HIGH và phát hiện mẫu `+8.56 s`

Để giảm warm-up artifact, firmware được sửa một dòng:

```cpp
scheduler_state_t initial_state = SCHED_STATE_HIGH;
```

Bộ `V3` cho thấy một pattern rất mạnh: sau mỗi lần chuyển vào `NORMAL`, khoảng `8.56 s` sau đó xuất hiện warning đầu tiên và power tăng mạnh. Mốc thời gian này trùng chính xác với lúc **cửa sổ 8 giây đầu tiên đầy**, nghĩa là bất thường không do warning text gây ra, mà do chính khối xử lý cửa sổ bắt đầu chạy.

Phân tích này loại dần các giả thuyết về `UART spam`, `state ping-pong` hay `cache miss` đơn thuần, và đẩy trọng tâm điều tra về path xử lý feature.

### 5.4. Sửa lỗi thứ nhất: tách fast path cho NORMAL

Trong phiên bản trước đó, `NORMAL` vẫn vô tình chạy gần như toàn bộ feature pipeline dành cho TinyML. Điều này làm cho `fixed_normal` tiêu tốn quá gần `fixed_high`, và cũng giải thích tại sao các spike trong `NORMAL` xuất hiện rất đều sau khi cửa sổ đầu tiên đầy.

Tôi đã sửa firmware theo hướng:

```cpp
const bool need_full_features = (state_snapshot == SCHED_STATE_HIGH);
if (!compute_window_metrics(&metrics, need_full_features))
    continue;
```

và chỉ cho `HIGH` mới đi vào `extract_ppg_features(...)`. Sau patch này, `NORMAL` giảm chi phí tính toán rõ rệt và spike của `fixed_normal` gần như biến mất.

### 5.5. V4-V5: spike còn lại chuyển sang HIGH

Sau patch trên, hiện tượng bất thường không biến mất hoàn toàn mà **dịch chuyển sang `HIGH`**. Đây là một bước quan trọng về mặt chẩn đoán: patch đầu không vô ích, mà đã giúp cô lập phần còn lại của vấn đề.

Khi đọc kỹ `compute_window_metrics()`, tôi phát hiện ở `HIGH` vẫn còn một dạng tính toán trùng lặp: vừa chạy một fast path DSP để tính `peak/ac`, vừa gọi `extract_ppg_features()` để làm gần như cùng lượng pre-processing thêm lần nữa. Sau khi bỏ phần tính lặp này, power ở `HIGH` tốt hơn, nhưng chưa hết hoàn toàn.

### 5.6. Chẩn đoán cuối cùng ở V5: aliasing của phép đo power

Bộ `V5` là chỗ kết luận bắt đầu rõ ràng. Khi số lượng run đủ nhiều, một sự thật hiện ra:

- có những `HIGH episode` rất giống nhau về `reason=2`, `std_hp`, `ptp_hp`, `ac`, nhưng có episode bị spike mạnh, có episode lại không;
- `fixed_normal` đôi lúc vẫn xuất hiện một spike lẻ;
- còn `adaptive` thì tỷ lệ sample `>300 mW` vẫn cao bất thường.

Điều này khiến tôi đi đến kết luận quan trọng: firmware đúng là có compute burst thật trong `HIGH`, nhưng **cách đọc INA219 gần như tức thời và chu kỳ log 2 giây đang phase-lock vào burst đó**, làm các sample power bị phóng đại thành “plateau spike”.

Nói cách khác, phần còn lại không còn là bug state machine thuần túy, mà là bug ở **telemetry method**.

### 5.7. Sửa lỗi thứ hai: power-window averaging

Firmware cuối cùng được sửa theo hướng lấy mẫu INA219 dày hơn và chỉ publish giá trị trung bình theo cửa sổ log:

```cpp
constexpr int64_t kPowerReadPeriodUs = 250LL * 1000LL;

struct power_window_accumulator_t
{
    float bus_sum = 0.0f;
    float current_sum = 0.0f;
    float power_sum = 0.0f;
    int count = 0;
};
```

Sau đó `maybe_sample_power(...)` tích lũy nhiều lần đọc INA219 trong 2 giây, còn `publish_power_average(...)` chỉ ghi ra trung bình trước khi in CSV sparse log. Đây là sửa lỗi đúng bản chất, vì nó biến power telemetry từ một **mẫu tức thời dễ bắt trúng burst** thành một **ước lượng gần hơn với power trung bình của cửa sổ hoạt động**.

### 5.8. V6: xác nhận cuối cùng

Bộ log `V6` là bộ đầu tiên xác nhận rõ rằng hướng sửa trên là đúng.

Các kết quả định lượng chính từ notebook [ppg_hr_macro_analysis.ipynb](ppg_hr_macro_analysis.ipynb) là:

- `adaptive`: `273.21 mW`, `65.81%` coverage, `2.03 h`
- `fixed_high`: `286.94 mW`, `89.31%` coverage, `1.93 h`
- `fixed_normal`: `261.78 mW`, `46.23%` coverage, `2.12 h`

Tỷ lệ chiếm trạng thái của adaptive là:

- `State 0`: `50.25%`
- `State 1`: `49.75%`

So với `fixed_high`, adaptive giảm công suất trung bình khoảng `4.79%` và tăng thời lượng tương đương khoảng `5.03%`. Quan trọng hơn, khi nhìn theo state thay vì nhìn theo mode tổng, ta thấy:

- `adaptive/state=0 = 263.35 mW`
- `fixed_normal = 261.78 mW`
- `adaptive/state=1 = 283.11 mW`
- `fixed_high = 286.94 mW`

Tức là `adaptive` đã bám hai baseline đúng như mong đợi về nghiệp vụ.

Một chỉ báo rất mạnh khác là **adaptive spike rate**. Ở `V5`, tỷ lệ sample `adaptive > 300 mW` còn khoảng `18.1%`. Sang `V6`, con số này giảm xuống còn khoảng `2.9%`. Đồng thời, toàn bộ `V6` không còn:

- `Recovering MAX30102`
- `I2C fail`
- `FIFO overflow`

Điều này xác nhận rằng các anomaly kiểu hệ thống ở các vòng trước không còn chi phối kết quả cuối.

---

## 6. Kết quả macro-level cuối cùng

Các figure cuối cùng được xuất trực tiếp từ notebook `V6` và dùng làm bằng chứng trong báo cáo:

![Tổng hợp KPI V6](artifacts/ppg_hr_macro_analysis_v6/macro_summary_dashboard_v6.png)

Hình trên cho thấy ba điều:

1. `fixed_normal` là baseline tiết kiệm năng lượng nhất nhưng coverage thấp nhất.
2. `fixed_high` là baseline coverage tốt nhất nhưng power cao nhất.
3. `adaptive` nằm giữa hai baseline, đúng bản chất một điểm trade-off thay vì cố thắng tuyệt đối ở một trục duy nhất.

Quan sát theo state còn quan trọng hơn khi đánh giá scheduler:

![So sánh power theo state ở V6](artifacts/ppg_hr_macro_analysis_v6/state_aware_power_comparison_v6.png)

Đây là bằng chứng rất mạnh cho claim kỹ thuật của đề tài. Nếu `adaptive/state=0` không bám `fixed_normal`, hoặc `adaptive/state=1` không bám `fixed_high`, thì adaptive scheduling chỉ là một label logic chứ chưa thực sự điều phối được chi phí hệ thống. Ở `V6`, điều này đã xảy ra đúng.

Về mặt tiến hóa của chính quá trình debug, hình dưới đây quan trọng không kém kết quả cuối:

![So sánh V5 và V6](artifacts/ppg_hr_macro_analysis_v6/v5_vs_v6_comparison.png)

Hình này cho phép lập luận rằng việc sửa firmware và sửa phương pháp đo năng lượng không chỉ làm đồ thị “đẹp hơn”, mà thực sự làm cho kết quả trở nên **đúng nghiệp vụ hơn**: power gap giữa các baseline hiện ra rõ, còn tỷ lệ spike bất thường giảm mạnh.

Cuối cùng, một run adaptive đại diện ở `V6` cho thấy state transition và đường power đã hợp lý hơn nhiều so với các vòng debug trước:

![Adaptive representative run V6](artifacts/ppg_hr_macro_analysis_v6/adaptive_log_adaptive_4_timeseries_v6.png)

Ở figure này, power thay đổi theo state nhưng không còn xuất hiện các plateau bất thường kéo dài kiểu `V2` hoặc `V5`. Một số điểm power cao ngay sau transition vẫn có thể xuất hiện, nhưng đó là hệ quả tất yếu của averaging window cắt ngang biên state, không còn là dấu hiệu scheduler chạy sai.

---

## 7. Diễn giải học thuật của coverage gap

Coverage của `adaptive` ở `V6` là `65.81%`, thấp hơn `fixed_high` (`89.31%`) nhưng cao hơn đáng kể so với `fixed_normal` (`46.23%`). Khoảng cách này không nên được diễn giải là thất bại của adaptive scheduling, mà là kết quả trực tiếp của hai lựa chọn thiết kế có chủ đích.

Thứ nhất, firmware ưu tiên **độ tin cậy của output**. Khi quality gate nghi ngờ cửa sổ không đủ chắc chắn, hệ thống chấp nhận drop thay vì cố ép ra một HR. Trong cảm biến sinh hiệu, đánh đổi này hợp lý hơn việc “có số mọi lúc” nhưng sai.

Thứ hai, adaptive phải gánh **chi phí chuyển trạng thái** mà `fixed_high` không có. Khi đổi giữa `50 Hz` và `100 Hz`, ring buffer, sensor profile và logic quyết định phải đi qua một giai đoạn chuyển tiếp. Điều này tạo ra một vùng mà hệ thống cần bảo thủ hơn, và coverage vì thế không thể bằng một baseline luôn bật `HIGH`.

Do đó, câu trade-off của luận văn ở phiên bản cuối có thể phát biểu như sau:

> Adaptive mode giữ được coverage cao hơn Fixed Normal khoảng 19.6 điểm phần trăm, trong khi vẫn giảm công suất trung bình khoảng 4.8% so với Fixed High ở mức whole-system power.

Trong bối cảnh đề tài này, đó là một kết quả hợp lý và đáng bảo vệ hơn so với việc tối đa hóa coverage bằng mọi giá.

---

## 8. Kết luận kỹ thuật của Phần B

Giá trị thực của Phần B không nằm ở việc “gắn một mô hình AI lên ESP32”, mà nằm ở chuỗi tối ưu liên tiếp, trong đó mỗi lần sửa đều được dẫn dắt bởi log thật và phân tích định lượng.

Toàn bộ hành trình có thể tóm gọn theo đúng logic kỹ thuật như sau:

- Rule-based scheduler được xây trước để hiểu tín hiệu thật và hình thành quality gate có ý nghĩa.
- TinyML được triển khai theo hướng feature-based, đồng bộ chặt giữa Python và C++ để đảm bảo deploy được trên edge.
- Kiến trúc dual-core được đưa vào khi bug thời gian thực xuất hiện, vì mô hình tốt nhưng sensor loop bị block thì hệ thống vẫn thất bại.
- Chuỗi log `V2 -> V6` cho thấy đánh giá năng lượng trên embedded system không chỉ là vấn đề firmware, mà còn là vấn đề **đo đúng cái cần đo**.
- Khi phương pháp đo được sửa đúng và firmware được tối ưu đúng chỗ, `V6` cuối cùng cho kết quả phù hợp cả về kỹ thuật lẫn nghiệp vụ: hai baseline tách rõ, adaptive nằm giữa, không còn lỗi hệ thống, và power-state behavior khớp với ý tưởng scheduler ban đầu.

Đó cũng là lý do tôi xem kết quả `V6` là mốc kết thúc hợp lý của Phần B: hệ thống đã đạt mức ổn định đủ để các con số macro-level có thể được dùng như bằng chứng chính thức trong luận văn.

---

## 9. Tài liệu và mã nguồn được dùng làm căn cứ trong phần này

- Firmware rule-based ban đầu: `C:\ml\esp32_projects\ina219_max30102_test\main\ina219_max30102_test.c`
- Firmware tích hợp cuối: `C:\ml\esp32_projects\ppg_hr_tinyml\main\ppg_hr_tinyml.cpp`
- Notebook phân tích scheduler: `max30102_log_analysis.ipynb`
- Notebook huấn luyện TinyML: `ppg_dalia.ipynb`
- Notebook phân tích macro-level cuối: `ppg_hr_macro_analysis.ipynb`
- Thư viện phân tích macro-level: `ppg_hr_macro_analysis_lib.py`
- Artifact V6:
  - `artifacts/ppg_hr_macro_analysis_v6/macro_summary_dashboard_v6.png`
  - `artifacts/ppg_hr_macro_analysis_v6/state_aware_power_comparison_v6.png`
  - `artifacts/ppg_hr_macro_analysis_v6/v5_vs_v6_comparison.png`
  - `artifacts/ppg_hr_macro_analysis_v6/adaptive_log_adaptive_4_timeseries_v6.png`
