# 05. Notebook PPG-DaLiA và mô hình TinyML

File chính: `ppg_dalia.ipynb`

## 1. Mục đích notebook

Notebook thực hiện hai nhánh:

1. Baseline feature-based bằng Random Forest và một số mô hình scikit-learn.
2. TinyML track bằng Keras MLP, sau đó chuyển FP32 và INT8.

Sản phẩm cuối cần cho firmware:

- thứ tự 16 đặc trưng;
- scaler mean/scale;
- HR mean/std;
- model INT8;
- mảng C chứa model;
- kết quả test sau lượng tử hóa.

## 2. PPG-DaLiA

Mỗi subject có file `S*.pkl`. Notebook ưu tiên đọc:

```python
obj["signal"]["wrist"]["BVP"]
obj["label"]
```

BVP cổ tay có tần số 64 Hz. Nhãn HR là chuỗi có tần số/thời điểm khác, nên notebook nội suy nhãn.

## 3. Chọn file subject

Notebook chỉ lấy đúng file subject `S*.pkl`, tránh đọc nhầm:

- activity CSV;
- questionnaire;
- file con khác.

Đây là bước vệ sinh dữ liệu.

## 4. Tiền xử lý offline

`preprocess_ppg()`:

1. Đổi NaN/Inf thành 0.
2. Detrend tuyến tính bằng SciPy.
3. Butterworth band-pass 0,7-5 Hz, bậc 3.
4. `filtfilt`, lọc hai chiều zero-phase.
5. Robust z-score bằng median/MAD.

### Robust z-score

```text
median = trung vị
MAD = median(|x - median|)
scale = 1,4826 × MAD
x_norm = (x - median) / scale
```

Nếu MAD quá nhỏ, fallback sang standard deviation.

Lợi ích: ít bị outlier lớn chi phối hơn mean/std.

## 5. Chia cửa sổ

`segment_signal()`:

```text
window = 8 × 64 = 512 mẫu
stride = 2 × 64 = 128 mẫu
```

Vòng lặp:

```python
for start in range(0, len(sig) - win + 1, step)
```

Không padding cửa sổ cuối thiếu mẫu.

## 6. Gắn HR tham chiếu

Notebook xây trục thời gian cho nhãn HR trải đều trên toàn thời lượng BVP:

```python
t_hr = linspace(0, total_duration, len(hr), endpoint=False)
```

Tâm cửa sổ:

```text
t_center = (start + end) / 2 / fs
```

Sau đó:

```python
hr_ref = interp(t_center, t_hr, hr_array)
```

Giả định quan trọng: nhãn HR trong pickle trải đều và đồng bộ với BVP. Nếu cấu trúc dataset có quy ước timestamp khác, cần kiểm tra lại tài liệu dataset.

## 7. Trích đặc trưng offline

Ngoài `n_samples` và `duration_sec`, notebook tính đúng 16 đặc trưng dùng cho mô hình.

### Nhóm thống kê

- mean;
- std;
- peak-to-peak;
- RMS;
- mean absolute value;
- mean absolute slope.

### Nhóm peak/HR

SciPy `find_peaks`:

```text
distance = fs × 0,33
prominence = max(0,05; 0,15 × std)
```

Sau đó tính:

- số peak;
- peak/giây;
- HR trung bình từ IBI;
- HR std;
- prominence trung bình.

### Autocorrelation

Chọn lag trong 40-180 BPM:

- `ac_best`;
- `ac_best_hr`.

### Miền tần số

Welch PSD với `nperseg <= 256`:

- tỷ lệ năng lượng 0,7-3,5 Hz so với 0-8 Hz;
- spectral entropy;
- dominant BPM trong HR band.

## 8. Bảng feature

Mỗi row chứa:

- subject;
- source file;
- start/end;
- HR reference;
- metadata cửa sổ;
- 16 feature.

File xuất:

```text
artifacts/ppg_dalia_feature_baseline/feature_table.csv
```

Số row rất lớn vì cửa sổ chồng lấn.

## 9. Vì sao phải chia theo subject?

Các cửa sổ cùng một người có đặc điểm rất giống nhau. Nếu random split theo row:

- cửa sổ của cùng người có thể nằm cả train và test;
- mô hình “nhớ” đặc điểm cá nhân;
- điểm test lạc quan giả.

`GroupShuffleSplit` giữ toàn bộ một subject ở một phía.

Output hiện tại cho TinyML:

- fit: S10, S11, S12, S14, S15, S2, S5, S7, S8, S9;
- validation: S13, S3;
- test: S1, S4, S6.

## 10. Random Forest baseline

Pipeline:

1. Group split 80/20.
2. Fit StandardScaler trên train.
3. Transform train/test.
4. Random Forest:
   - 400 trees;
   - `min_samples_leaf=2`;
   - random seed cố định.
5. Tính MAE, RMSE, R².

Random Forest không cần StandardScaler về mặt thuật toán, nhưng dùng scaler không làm hỏng logic và giữ pipeline đồng nhất.

Kết quả:

```text
MAE  = 8,4416 BPM
RMSE = 12,8923 BPM
R²   = 0,7042
```

Baseline dự đoán mean train có MAE khoảng 18 BPM.

## 11. GroupKFold

Notebook còn chạy 5-fold cross-validation theo subject. Mean:

```text
MAE ≈ 8,40
RMSE ≈ 13,49
R² ≈ 0,615
```

Độ biến thiên giữa fold khá lớn. Điều này cho thấy khả năng tổng quát phụ thuộc subject.

Không nên chỉ báo một split mà bỏ qua độ biến thiên này khi bị hỏi sâu.

## 12. Offline scheduling simulation

Notebook tạo `difficulty_proxy`, chia easy/medium/hard rồi:

- easy: giữ mỗi cửa sổ thứ 3;
- medium: giữ mỗi cửa sổ thứ 2;
- hard: giữ tất cả.

Đây là mô phỏng heuristic để minh họa giảm tỷ lệ inference. Nó không phải scheduler firmware hiện tại và không phải bằng chứng thực nghiệm phần cứng.

## 13. Model zoo

Notebook so sánh:

- Ridge;
- MLPRegressor nhỏ;
- Random Forest.

MLP nhỏ từng cho MAE gần Random Forest. Phần TinyML sau đó dùng Keras và tìm kiến trúc lớn hơn.

## 14. Chia fit/validation/test cho TinyML

Quy trình:

1. Group split 20% subject làm test.
2. Trong phần train còn lại, group split 15% làm validation.
3. Fit scaler chỉ trên fit.
4. Transform validation/test bằng scaler fit.
5. Tính HR mean/std chỉ trên nhãn fit.

Đây là quy trình đúng để tránh leakage từ validation/test.

## 15. Kiến trúc MLP

Hàm `build_tinyml_mlp()`:

```text
Input 16
Dense + ReLU
Dropout
Dense + ReLU
Dropout
...
Dense 1 linear
```

Loss: Huber. Optimizer: Adam. Metric theo dõi: MAE trên nhãn đã chuẩn hóa.

### Vì sao Huber?

Huber:

- giống MSE khi sai số nhỏ;
- giống MAE khi sai số lớn.

Nó giảm ảnh hưởng của outlier so với MSE thuần.

## 16. Các candidate

Notebook thử:

- 64-32;
- 128-128-64;
- 192-128-64;
- 256-128-64;
- 128-128-64-32.

Cấu hình được chọn:

```text
192-128-64
dropout 0,20
L2 = 1e-4
learning rate = 8e-4
batch = 128
```

Số tham số: 36.289.

## 17. Early stopping và learning-rate schedule

- Tối đa 250 epoch.
- Early stopping patience 25 theo `val_mae`.
- ReduceLROnPlateau patience 8.
- Khôi phục best weights.

Selection score:

```text
val_mae
+ phạt overfit gap vượt 1 BPM
+ phạt nhẹ số tham số
```

Trong kết quả hiện tại, validation MAE thấp hơn train MAE. Điều này có thể do:

- validation subjects dễ hơn fit subjects;
- dropout làm metric train trong epoch khó hơn inference validation;
- phân bố subject khác nhau.

Không nên kết luận “không overfit” chỉ từ dấu của gap.

## 18. Kết quả Keras

Mô hình được chọn:

```text
Validation MAE ≈ 4,638 BPM
Test MAE       ≈ 8,122 BPM
Test RMSE      ≈ 12,623 BPM
```

Khoảng cách validation-test lớn cho thấy test subjects khó hơn validation subjects.

## 19. Chuyển TFLite FP32

```python
tf.lite.TFLiteConverter.from_keras_model(model)
```

FP32 TFLite giữ gần như đúng dự đoán Keras:

```text
MAE 8,1217
RMSE 12,6226
```

## 20. Post-training integer quantization

Converter INT8:

```python
optimizations = [Optimize.DEFAULT]
representative_dataset = representative_dataset
supported_ops = TFLITE_BUILTINS_INT8
input_type = int8
output_type = int8
```

Representative dataset lấy tối đa 512 mẫu trải đều trong tập fit đã chuẩn hóa. Nó giúp converter ước lượng dynamic range.

## 21. Kiểm tra INT8

Notebook tự chạy `tf.lite.Interpreter`:

1. Quantize input.
2. Invoke.
3. Dequantize output.
4. Denormalize HR.
5. Tính MAE/RMSE.

Kết quả artifact hiện tại:

```text
TFLite INT8 MAE  = 8,1111 BPM
TFLite INT8 RMSE = 12,6063 BPM
```

INT8 hơi tốt hơn FP32 trong split này là nhiễu lượng tử hóa tình cờ có lợi, không có nghĩa INT8 về nguyên lý chính xác hơn FP32.

## 22. Export C

`write_c_array_files()` đọc toàn bộ `.tflite` và viết:

- header khai báo;
- source chứa byte hex;
- biến length.

Firmware link hai file này như source bình thường.

## 23. Artifact quan trọng

```text
ppg_hr_mlp.keras
ppg_hr_mlp_fp32.tflite
ppg_hr_mlp_int8.tflite
ppg_hr_mlp_int8.c
ppg_hr_mlp_int8.h
tinyml_feature_columns.json
tinyml_scaler.pkl
tinyml_scaler_export.json
tinyml_target_norm.json
tinyml_model_compare.csv
tinyml_candidate_results.csv
```

## 24. Điều kiện để firmware khớp notebook

Phải đồng thời đúng:

1. 16 feature cùng thứ tự.
2. Tiền xử lý feature tương đương.
3. Scaler mean/scale đúng lần train.
4. HR mean/std đúng lần train.
5. C array đúng file TFLite.
6. Input quant scale/zp lấy từ model runtime.
7. Output giải lượng tử hóa đúng.

Chỉ cần một thành phần lệch, MAE offline không còn đại diện cho firmware.

## 25. Pipeline mismatch hiện tại

### Offline

- Butterworth bậc 3.
- `filtfilt`.
- median/MAD.
- SciPy `find_peaks`.
- Welch PSD.

### Firmware

- high-pass/low-pass một cực.
- causal filter.
- mean/std.
- peak detector tự viết.
- FFT periodogram.

Mặc dù tên feature giống nhau, giá trị phân bố có thể khác. Đây là domain shift do implementation.

## 26. Dataset-to-sensor domain shift

PPG-DaLiA BVP được thu từ thiết bị wrist-worn khác MAX30102 fingertip/prototype. Khác biệt gồm:

- bước sóng và quang học;
- vị trí đeo;
- gain/ADC;
- sampling hardware;
- motion pattern;
- người dùng;
- preprocessing.

StandardScaler giúp chuẩn hóa một phần nhưng không xóa domain shift.

Muốn chứng minh hệ thống tốt hơn, cần:

- dữ liệu MAX30102 có HR ground truth;
- fine-tune/calibrate trên domain mới;
- hoặc chứng minh feature distribution và sai số trên prototype.

## 27. Ý nghĩa đúng của kết quả offline

Kết quả offline chứng minh:

- vector 16 feature có thông tin về HR trên PPG-DaLiA;
- MLP có thể học quan hệ;
- mô hình chịu được lượng tử hóa INT8;
- model có thể export.

Nó chưa chứng minh:

- HR firmware chính xác 8,11 BPM trên MAX30102;
- AI tốt hơn DSP trên prototype;
- scheduler cải thiện accuracy;
- thiết bị đạt yêu cầu y tế.

## 28. Nếu hội đồng hỏi “tại sao MLP tốt hơn RF rất ít?”

Ý chính:

- Chênh lệch 0,33 BPM MAE nhỏ.
- Mục tiêu chọn MLP không chỉ là accuracy.
- MLP có thể chuyển TFLite INT8 và chạy trực tiếp bằng TFLM.
- RF baseline hiện không được triển khai trên firmware.
- Cần lặp nhiều split hoặc kiểm định để khẳng định ưu thế thống kê.
- Nên nói “MLP đạt kết quả tương đương/nhỉnh hơn và phù hợp triển khai hơn”, không phóng đại.

## 29. Nếu hội đồng hỏi “mô hình TinyML có thật sự tiny?”

Phân biệt:

- model byte trong log firmware khoảng 7.976 byte của model đang nhúng;
- candidate artifact hiện tại có thể là phiên bản khác và file C lớn vì mỗi byte được viết thành chuỗi hex;
- tensor arena dùng khoảng 1.548 byte;
- mạng chỉ dùng FullyConnected;
- inference khoảng vài trăm µs.

“Tiny” phải đánh giá bằng flash, RAM, latency và energy trên target, không chỉ số layer.
