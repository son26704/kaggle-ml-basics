Đây là bản **Báo cáo Tiến độ (Phần B)** được biên soạn chi tiết, học thuật và chuyên sâu, tiếp nối trực tiếp từ Phần A (Báo cáo Prototype Phần cứng) của bạn. 

Báo cáo này được viết theo văn phong nghiên cứu khoa học, giải thích rõ ràng *tại sao* bạn lại đưa ra các quyết định kỹ thuật, kèm theo các trích dẫn logic từ code/notebook để giáo viên dễ dàng đối chiếu.

***

# BÁO CÁO TIẾN ĐỘ: TỐI ƯU HÓA NĂNG LƯỢNG VÀ TÍCH HỢP AI (TINYML) CHO THIẾT BỊ ĐEO

**Tiếp nối Phần A:** *Xây dựng hệ thống Prototype phần cứng (ESP32-S3 + MAX30102 + INA219).*

## 1. Đặt vấn đề và Mục tiêu Giai đoạn B

Từ kết quả của Giai đoạn A, phần cứng đã có khả năng đọc tín hiệu PPG (Photoplethysmography) từ cảm biến MAX30102 và đo lường công suất tiêu thụ theo thời gian thực qua INA219. Tuy nhiên, nếu chỉ sử dụng các thuật toán xử lý tín hiệu số (DSP) truyền thống như dò đỉnh (Peak Detection), thiết bị sẽ gặp sai số cực kỳ lớn khi người dùng vận động (Motion Artifacts). Ngược lại, nếu liên tục chạy các mô hình Trí tuệ nhân tạo (AI) phức tạp để lọc nhiễu, thời lượng pin của thiết bị đeo (Wearable) sẽ bị vắt kiệt nhanh chóng.

Do đó, mục tiêu của Giai đoạn B là **thiết kế một hệ thống Điều phối Thích nghi nhận thức năng lượng (Energy-Aware Adaptive Scheduler)** kết hợp với mô hình học máy nhúng (TinyML). Hệ thống này phải đạt được sự cân bằng (Trade-off): Chỉ đánh thức AI khi tín hiệu bị nhiễu do chuyển động, và sử dụng thuật toán cơ bản tiết kiệm điện khi người dùng ở trạng thái tĩnh.

---

## 2. Quá trình Phân tích Dữ liệu và Huấn luyện Mô hình (Python)
*(Tham chiếu file: `ppg_dalia.ipynb` và `max30102_log_analysis.ipynb`)*

### 2.1. Lựa chọn và Xử lý Tập dữ liệu (PPG-DaLiA)
Để mô hình có khả năng học cách bóc tách nhịp tim trong môi trường nhiễu vận động, em đã lựa chọn tập dữ liệu mở **PPG-DaLiA**. Tập dữ liệu này ghi lại sóng PPG và nhịp tim thực tế (Ground Truth từ ECG) của người dùng trong các hoạt động hàng ngày (ngồi, đi bộ, lái xe...).

Quá trình trích xuất đặc trưng (Feature Extraction) được thiết kế dựa trên phương pháp cửa sổ thời gian (Windowing) với:
* **Kích thước cửa sổ (Window Size):** 8 giây (đảm bảo chứa đủ ít nhất 5-6 nhịp đập để tính toán tần số).
* **Bước nhảy (Stride):** 2 giây.

Thay vì đưa trực tiếp sóng thô vào mô hình (yêu cầu cấu trúc Deep Learning nặng nề như CNN/LSTM), em đã trích xuất **16 đặc trưng** ở cả miền thời gian và miền tần số (Time/Frequency domain) để làm đầu vào. Các đặc trưng tiêu biểu bao gồm: Biên độ đỉnh-đáy (`ptp`), Độ lệch chuẩn (`std`), Tính chu kỳ (`ac_best`), Tỉ lệ công suất dải nhịp tim (`psd_hr_ratio`).

*Đoạn mã trích xuất đặc trưng (Cell 10, `ppg_dalia.ipynb`):*
```python
# Trích xuất đặc trưng từ cửa sổ 8s
features = {
    'mean': np.mean(ppg_band),
    'std': np.std(ppg_band),
    'ptp': np.ptp(ppg_band),
    'ac_best': best_ac,          # Autocorrelation (Tính chu kỳ)
    'psd_hr_ratio': psd_hr_ratio # Tỉ lệ công suất dải tần số tim
    # ... (tổng cộng 16 features)
}
```

### 2.2. Huấn luyện Mô hình và Giải quyết Hiện tượng Domain Shift
Ban đầu, em sử dụng mô hình Random Forest làm Baseline, cho ra sai số MAE khoảng 8.44 BPM. Tuy nhiên, Random Forest không tối ưu để đưa xuống vi điều khiển do tốn nhiều bộ nhớ RAM để lưu các nhánh cây quyết định. 

Em đã chuyển sang thiết kế một Mạng nơ-ron nhân tạo đa tầng (MLP - Multilayer Perceptron) nhỏ gọn với 3 lớp ẩn (32-16-8 nơ-ron). Đặc biệt, trong quá trình thử nghiệm, em phát hiện ra hiện tượng **Domain Shift**: Tập DaLiA được thu thập ở cổ tay (Wristband), trong khi phần cứng thực tế đo ở đầu ngón tay (Fingertip). Sóng PPG ở ngón tay thường có biên độ nảy mạnh hơn và xuất hiện các đỉnh phụ (Dicrotic Notch) rõ rệt.

Để mô hình không bị "ngợp" trước dữ liệu mới, bắt buộc phải áp dụng **Chuẩn hóa Z-Score (Robust Z-score)** cho toàn bộ 16 đặc trưng đầu vào, kết hợp với chuẩn hóa giá trị nhịp tim mục tiêu (Target Normalization) trước khi cho mô hình học.

*Kiến trúc MLP (Cell 22, `ppg_dalia.ipynb`):*
```python
model = Sequential([
    Dense(32, activation='relu', input_shape=(16,), kernel_regularizer=l2(0.01)),
    BatchNormalization(),
    Dropout(0.2),
    Dense(16, activation='relu', kernel_regularizer=l2(0.01)),
    BatchNormalization(),
    Dropout(0.1),
    Dense(8, activation='relu'),
    Dense(1, activation='linear') # Đầu ra dự đoán nhịp tim đã chuẩn hóa
])
```

### 2.3. Lượng tử hóa (Quantization) cho TinyML
Để triển khai mô hình MLP lên ESP32-S3, mô hình Float32 (14.37 KB) được lượng tử hóa xuống Int8 (chỉ còn **7.79 KB**). Quá trình này giúp mô hình chạy nhanh hơn và tiết kiệm năng lượng, nhưng thường gây suy giảm độ chính xác. Nhờ kỹ thuật Target Normalization đã áp dụng ở trên, sai số MAE của mô hình Int8 gần như không đổi so với Float32 (8.65 vs 8.63 BPM).

---

## 3. Triển khai Hệ thống Nhúng và Điều phối Thích nghi (C++/FreeRTOS)
*(Tham chiếu file: `ppg_hr_tinyml.cpp`)*

Phần này giải quyết mục tiêu cốt lõi của đề tài: Tích hợp mô hình AI vào vi điều khiển và xây dựng "bộ não" điều phối.

### 3.1. Kiến trúc Đa luồng (Dual-Core Architecture)
Ban đầu, khi chạy cả tác vụ đọc I2C từ cảm biến và tác vụ chạy mô hình AI trên cùng một lõi CPU, hệ thống đã gặp lỗi tràn bộ đệm (`MAX30102 FIFO overflow`) do quá trình suy luận của AI tốn nhiều thời gian, làm nghẽn bus I2C.

Em đã thiết kế lại kiến trúc tận dụng khả năng Dual-Core của ESP32-S3 bằng FreeRTOS:
* **Core 0 (Sensor Loop):** Chạy vòng lặp vô tận chỉ để đọc I2C liên tục, đẩy dữ liệu vào một Ring Buffer (được bảo vệ bằng Mutex).
* **Core 1 (AI_Task):** Nằm chờ tín hiệu (Task Notification). Khi Core 0 gom đủ 1 cửa sổ 8 giây, Core 1 thức dậy, lấy dữ liệu, trích xuất 16 đặc trưng C++ (chính xác về mặt toán học tương đương với mã Python) và chạy mô hình TensorFlow Lite.

### 3.2. Thuật toán Điều phối Thích nghi (Adaptive Scheduler)
Thay vì dùng AI liên tục, em xây dựng một lớp lọc chất lượng (Quality Gate) dựa trên các chỉ số tính toán tức thời (ít tốn kém CPU) là Biên độ (`ptp_hp`, `std_hp`) và Tính chu kỳ (`ac_best`).

Luồng hoạt động của Scheduler:
1. **Trạng thái NORMAL (50sps - Tiết kiệm điện):** Nếu ngón tay tĩnh, sóng PPG có chu kỳ rõ ràng (`ac_best > 0.45`). ESP32 tắt cấu hình AI, giảm tần số lấy mẫu xuống 50Hz, và sử dụng hàm đếm đỉnh truyền thống (`find_peaks_simple`) để tính nhịp tim `DSP_HR`.
2. **Trạng thái HIGH (100sps - Bật AI):** Khi người dùng rung tay/gõ ngón tay, biên độ sóng vọt lên hoặc chu kỳ bị vỡ (`ptp_hp > 35000` hoặc `ac_best < 0.30`). Scheduler lập tức tăng tốc độ cảm biến lên 100Hz và đánh thức tác vụ AI. Mô hình TFLite sẽ dự đoán nhịp tim `AI_ASSIST_HR` từ tín hiệu nhiễu.
3. **Phát hiện tuột tay (No Contact):** Nếu biên độ quá lớn hoặc quá nhỏ vô lý, thiết bị cảnh báo tuột tay và ngừng tính toán để không xuất rác dữ liệu.

*Logic chuyển đổi trạng thái (Trích xuất từ hàm `inference_task`, `ppg_hr_tinyml.cpp`):*
```cpp
// Đánh giá chất lượng cửa sổ hiện tại (Quality Gate)
const bool amplitude_ok = (std_hp >= SCHED_STD_MIN) && (ptp_hp >= SCHED_PTP_MIN) && (ptp_hp <= SCHED_PTP_MAX);
const bool periodic_ok = (ac_best >= SCHED_AC_MIN);
const bool hr_range_ok = (peak_bpm >= 40.0f) && (peak_bpm <= 180.0f);
const bool quality_ok = amplitude_ok && periodic_ok && hr_range_ok;

// Nếu ở NORMAL mà bị nhiễu (severe_motion_fail), đánh dấu bad_windows để chuẩn bị nhảy lên HIGH
if (severe_motion_fail || (ac_best <= SCHED_AC_HARD) || (difficulty_proxy >= SCHED_DIFF_HARD)) {
    bad_windows++;
    gray_windows = 0;
}

// Nếu đã bật AI (HIGH) mà tín hiệu ổn định lại (good_windows >= 5), hạ cấp về NORMAL
if (quality_ok && hr_consistent && ac_best >= SCHED_AC_EASY && difficulty_proxy <= SCHED_DIFF_EASY) {
    good_windows++;
}
```

### 3.3. Bộ lọc làm mượt dữ liệu (EMA Filter)
Khi chuyển đổi giữa DSP và AI, hoặc khi chịu nhiễu cơ học mạnh, đầu ra của mô hình thường có xu hướng giật cục. Em đã thiết kế một bộ lọc Trung bình động hàm mũ (Exponential Moving Average) để làm mượt chỉ số hiển thị cho người dùng, tạo cảm giác liền mạch giống với các smartwatch thương mại.

---

## 4. Nghiệm thu và Đánh giá (Macro-Level Analysis)
*(Tham chiếu file: `ppg_hr_macro_analysis.ipynb`)*

Để chứng minh tính hiệu quả của thiết kế, em đã thu thập log hoạt động của thiết bị với mạch INA219 (đo công suất liên tục) trong 3 kịch bản: `fixed_normal` (50Hz không AI), `fixed_high` (100Hz full AI), và `adaptive` (chuyển đổi thông minh). Giao thức đo chuẩn kéo dài 3 phút: Ngồi im (1 phút) -> Rung/vận động tay (1 phút) -> Ngồi im (1 phút).

Sử dụng script Python để phân tích log, hệ thống ghi nhận các kết quả xuất sắc:

1. **Hiệu năng Năng lượng (Energy Savings):**
   * Công suất trung bình của `fixed_high` là **18.65 mW**.
   * Công suất trung bình của `adaptive` là **16.83 mW**.
   * 👉 Hệ thống Adaptive **tiết kiệm được 9.78% điện năng**. Giả định với viên pin 150mAh 3.7V, Scheduler giúp kéo dài tuổi thọ thiết bị từ 29.75 giờ lên **32.98 giờ** (Tăng hơn 3 tiếng sử dụng).

2. **Độ tin cậy và Kháng nhiễu (Reliability vs Motion Artifacts):**
   * Trong giai đoạn Vận động (Motion phase), chế độ `fixed_normal` gần như tê liệt hoàn toàn với tỉ lệ hiển thị nhịp tim (Coverage) chỉ đạt **2.05%** (do tín hiệu quá nhiễu, hàm DSP từ chối xuất kết quả).
   * Chế độ `adaptive` đã tự động phát hiện nhiễu, đánh thức AI và cứu vãn được **57.99%** dữ liệu nhịp tim trong lúc vận động. (Cao gấp 28 lần so với việc không có AI).
   * Sự sụt giảm độ phủ của `adaptive` (~60%) so với `fixed_high` (~96%) là một sự **đánh đổi có chủ ý (Trade-off)**. Để đổi lấy việc tiết kiệm pin, hệ thống chấp nhận mất một vài giây dữ liệu do nhiễu phần cứng (Switching Cost) khi chuyển đổi tần số từ 50Hz lên 100Hz.

*Kết quả phân tích (Từ Notebook):*
```text
=== TỔNG HỢP KPI 3 CHẾ ĐỘ ===
               Avg Power (mW)  HR Coverage (%)
Mode                                          
ADAPTIVE                16.83            59.76
FIXED_NORMAL            15.82            28.90
FIXED_HIGH              18.65            96.22
```

## 5. Kết luận Giai đoạn B và Hạn chế

Dự án đã hoàn thành thiết kế nguyên mẫu một hệ thống thiết bị đeo nhúng AI có khả năng tối ưu hóa năng lượng. Mọi yếu tố từ xử lý luồng I2C đa lõi, tính toán đặc trưng bằng C++, nhúng mô hình TFLite Micro, đến thuật toán chuyển đổi trạng thái (Scheduler) đều hoạt động ổn định trên phần cứng ESP32-S3.

**Hạn chế và Hướng nghiên cứu mở:**
* Hiện tượng Dịch chuyển miền (Domain Shift) giữa dữ liệu học ở cổ tay (DaLiA) và thực tế đo ở ngón tay (MAX30102) làm cho mô hình có xu hướng dự đoán nhịp tim cao hơn một chút khi gặp áp lực nhấn ngón tay lớn (Contact pressure artifact).
* Hướng phát triển trong tương lai có thể là thu thập thêm một tập dữ liệu nhỏ trực tiếp từ thiết bị prototype để tinh chỉnh (Fine-tuning) lại các lớp cuối của mạng nơ-ron bằng phương pháp Học chuyển giao (Transfer Learning).

*(Hết báo cáo).*

***

**LƯU Ý DÀNH CHO BẠN (Góp ý để kết nối Phần A và Phần B mượt hơn):**

Để giáo viên đọc báo cáo của bạn một cách mạch lạc nhất, bạn nên:
1. Ở phần cuối của **Báo cáo Phần A**, bạn nên thêm 1 câu chốt: *"Tuy thuật toán dò đỉnh (Peak Detection) ở Phần A hoạt động tốt khi ngồi tĩnh, nhưng nó hoàn toàn thất bại khi người dùng cử động tay. Điều này đặt ra yêu cầu phải ứng dụng Machine Learning (Giai đoạn B) để xử lý nhiễu."*
2. Bạn nên đính kèm **2 bức ảnh đồ thị** được xuất ra từ Notebook `ppg_hr_macro_analysis.ipynb` (đồ thị có tô nền xanh/đỏ) vào Mục 4 của Báo cáo Phần B này. Trăm nghe không bằng một thấy, giáo viên nhìn biểu đồ màu sắc sẽ hiểu ngay lập tức hệ thống Adaptive của bạn hoạt động thông minh như thế nào.