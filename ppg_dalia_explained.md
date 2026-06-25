# Giải thích chi tiết notebook `ppg_dalia.ipynb`

Tài liệu này giải thích toàn bộ luồng của notebook `ppg_dalia.ipynb` theo đúng thứ tự cell. Mục tiêu là giúp hiểu notebook đang làm gì, vì sao làm như vậy, dữ liệu đi qua các bước nào, các công nghệ được dùng là gì, và kết quả cuối cùng liên quan thế nào tới firmware TinyML trên ESP32-S3.

Notebook này là phần nền tảng offline của đồ án. Nó không chạy trên ESP32 trực tiếp. Nó chạy trên máy tính để:

1. Tải và đọc bộ dữ liệu PPG-DaLiA.
2. Cắt tín hiệu PPG thành các cửa sổ thời gian.
3. Tiền xử lý tín hiệu PPG.
4. Trích đặc trưng từ từng cửa sổ.
5. Ghép mỗi cửa sổ với nhịp tim tham chiếu.
6. Huấn luyện model dự đoán HR từ vector đặc trưng.
7. Đánh giá baseline truyền thống như Random Forest.
8. Huấn luyện model MLP nhỏ phù hợp TinyML.
9. Export model sang TFLite FP32 và TFLite INT8.
10. Xuất model INT8 thành file `.c/.h` để firmware ESP32 có thể nhúng vào chương trình.

## Bức Tranh Tổng Thể

Luồng dữ liệu chính của notebook là:

```text
PPG-DaLiA .pkl
  -> đọc subject, tín hiệu BVP/PPG, label HR
  -> cắt cửa sổ 8 giây, trượt 2 giây
  -> tiền xử lý tín hiệu trong từng cửa sổ
  -> trích 16 đặc trưng
  -> tạo bảng feature_df
  -> bỏ dòng không có HR label
  -> train/evaluate model offline
  -> train MLP bằng Keras
  -> export TFLite FP32 + INT8
  -> export C array cho ESP32 firmware
```

Trong đồ án, notebook này trả lời câu hỏi: "Có thể dùng một vector đặc trưng nhỏ từ PPG để dự đoán HR bằng một model đủ nhẹ cho vi điều khiển hay không?"

Notebook này chưa phải là phần đo năng lượng. Đo năng lượng nằm ở `ppg_hr_macro_analysis.ipynb`, `ppg_hr_micro_power_analysis.ipynb` và firmware DAQ. Nhưng `ppg_dalia.ipynb` tạo ra model TinyML và logic đặc trưng nền tảng để firmware target node dùng trong Slow Path.

## Cell 0 - Giới Thiệu Notebook

Cell này là markdown mở đầu:

```markdown
# PPG-Dalia practice (feature-based baseline)
```

Nó nói notebook dùng để thực hành với dataset PPG-DaLiA trên Kaggle. Các việc chính gồm tải dataset, khám phá cấu trúc, trích feature theo cửa sổ thời gian, train baseline model và đánh giá nhanh.

Về mặt đồ án, đây là notebook "offline training". Nó không làm việc với dữ liệu MAX30102 thật từ prototype, mà dùng PPG-DaLiA để xây dựng pipeline học máy ban đầu. PPG-DaLiA là dữ liệu đo PPG cổ tay có nhãn HR, phù hợp để huấn luyện model dự đoán nhịp tim.

## Cell 1 - Cài Package Cần Thiết

Cell này import `sys`, `subprocess`, rồi định nghĩa:

```python
REQUIRED_PACKAGES = [
    "numpy",
    "pandas",
    "matplotlib",
    "scipy",
    "scikit-learn",
    "joblib",
    "kaggle",
]
```

Sau đó chạy:

```python
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *REQUIRED_PACKAGES])
```

Ý nghĩa:

- `sys.executable` đảm bảo pip chạy đúng trong Python environment hiện tại.
- `pip install -q` cài package ở chế độ ít log.
- `numpy`: tính toán mảng số.
- `pandas`: bảng dữ liệu.
- `matplotlib`: vẽ biểu đồ.
- `scipy`: xử lý tín hiệu, lọc, PSD, peak detection.
- `scikit-learn`: chia train/test, scaler, model baseline, metric.
- `joblib`: lưu model sklearn.
- `kaggle`: tải dataset từ Kaggle.

Cell này có tính tiện lợi khi chạy notebook trên máy mới. Nếu environment đã đủ package thì vẫn chạy được, nhưng sẽ mất thời gian kiểm tra/cài.

## Cell 2 - Import Thư Viện Và Thiết Lập Seed

Cell này import toàn bộ thư viện chính dùng xuyên suốt notebook:

```python
import os
import re
import json
import math
import pickle
import random
import warnings
from pathlib import Path
```

Nhóm này phục vụ thao tác hệ thống, regex, lưu JSON, đọc pickle, random seed và đường dẫn.

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
```

Đây là bộ ba cơ bản cho phân tích dữ liệu Python:

- `numpy`: xử lý tín hiệu dạng array.
- `pandas`: lưu feature thành bảng.
- `matplotlib`: plot histogram, scatter, learning curve.

```python
from scipy import signal
from scipy.signal import butter, filtfilt, welch, find_peaks
```

Các hàm xử lý tín hiệu:

- `signal.detrend`: bỏ xu hướng tuyến tính chậm trong tín hiệu.
- `butter`: thiết kế bộ lọc Butterworth.
- `filtfilt`: lọc hai chiều để giảm lệch pha.
- `welch`: ước lượng phổ công suất PSD.
- `find_peaks`: tìm đỉnh tín hiệu.

```python
from sklearn.model_selection import GroupShuffleSplit, GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
```

Các thành phần sklearn:

- `GroupShuffleSplit`: chia train/test theo subject, tránh rò rỉ dữ liệu cùng người.
- `GroupKFold`: cross-validation theo subject.
- `StandardScaler`: chuẩn hóa feature về trung bình 0, độ lệch chuẩn 1.
- `MAE`, `RMSE`, `R2`: metric đánh giá model hồi quy.
- `RandomForestRegressor`: baseline học máy truyền thống.
- `Ridge`: baseline tuyến tính có regularization.
- `MLPRegressor`: MLP của sklearn để so sánh nhanh.

Sau đó:

```python
warnings.filterwarnings("ignore")
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
```

`SEED` giúp kết quả chia dữ liệu và train model có tính lặp lại. Với notebook nghiên cứu, seed rất quan trọng vì nếu mỗi lần chạy ra split khác nhau thì metric khó so sánh.

Cuối cell in ra Python version và working directory để biết notebook đang chạy ở đâu.

## Cell 3 - Cấu Hình Dataset Kaggle

Cell này tạo các đường dẫn:

```python
DATA_DIR = Path("./data")
KAGGLE_SLUG = "ameersifat53/ppg-dalia-dataset"
PPG_DALIA_DIR = DATA_DIR / "ppg-dalia"
```

Ý nghĩa:

- Dataset sẽ nằm trong `./data/ppg-dalia`.
- `KAGGLE_SLUG` là định danh dataset trên Kaggle.

Hàm:

```python
def check_kaggle_auth():
```

kiểm tra hai kiểu xác thực Kaggle:

- Biến môi trường bắt đầu bằng `KAGGLE`.
- File `~/.kaggle/kaggle.json`.

Nếu Kaggle auth chưa cấu hình, cell sau sẽ không tải được dataset. Notebook không tự sửa auth, chỉ in gợi ý để người chạy biết nguyên nhân.

## Cell 4 - Tải Dataset Từ Kaggle

Hàm:

```python
def download_ppg_dalia_from_kaggle(slug=KAGGLE_SLUG, output_dir=PPG_DALIA_DIR):
```

tạo command:

```text
kaggle datasets download -d ameersifat53/ppg-dalia-dataset -p data/ppg-dalia --unzip
```

Ý nghĩa:

- `datasets download`: tải dataset Kaggle.
- `-d slug`: chọn dataset.
- `-p output_dir`: thư mục đích.
- `--unzip`: tự giải nén.

Trong `try/except`, nếu tải lỗi thì notebook in ra nguyên nhân thường gặp: Kaggle auth chưa đúng hoặc cần tải thủ công.

Cell này là bước lấy dữ liệu đầu vào. Nếu dữ liệu đã có sẵn trong thư mục, việc chạy lại có thể không cần thiết.

## Cell 5 - In Cây Thư Mục Dataset

Hàm:

```python
def print_tree(root: Path, max_depth=3, max_entries=120):
```

duyệt file và thư mục con bằng `root.rglob("*")`, sau đó in ra dạng cây.

Các tham số:

- `max_depth`: giới hạn độ sâu để không in quá nhiều.
- `max_entries`: giới hạn số dòng.

Sau đó notebook tìm:

```python
subject_candidates = sorted([p for p in PPG_DALIA_DIR.rglob("S*") if p.is_dir()])
```

Ý nghĩa:

- Trong PPG-DaLiA, dữ liệu thường được tổ chức theo subject như `S1`, `S2`, ...
- Cell này giúp kiểm tra dataset có giải nén đúng cấu trúc không.

Đây là bước khám phá dữ liệu. Trước khi viết code load `.pkl`, cần biết file thật đang nằm ở đâu.

## Cell 6 - Lọc File Subject `.pkl`

Cell này lấy các file:

```python
subject_pkl_files = sorted(
    [fp for fp in PPG_DALIA_DIR.rglob("S*.pkl") if re.match(r"S\d+\.pkl$", fp.name)]
)
```

Điểm quan trọng là regex:

```python
r"S\d+\.pkl$"
```

Nó chỉ nhận file có tên như:

```text
S1.pkl
S2.pkl
S10.pkl
```

Nó tránh lấy nhầm các file khác bắt đầu bằng `S` nhưng không phải subject data. Biến:

```python
candidate_files = subject_pkl_files
```

là danh sách file sẽ đưa vào pipeline load dữ liệu ở các cell sau.

## Cell 7 - Các Hàm Tiền Xử Lý Tín Hiệu PPG

Cell này định nghĩa các hàm xử lý tín hiệu cơ bản. Đây là phần cực kỳ quan trọng vì mọi feature đều dựa trên tín hiệu sau tiền xử lý.

### `safe_nan_to_num`

```python
def safe_nan_to_num(x):
    x = np.asarray(x, dtype=np.float32)
    return np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
```

Hàm này:

- Ép input thành `np.float32`.
- Thay `NaN`, `+inf`, `-inf` bằng `0.0`.

Vì tín hiệu thực tế hoặc dataset có thể có giá trị lỗi, bước này giúp pipeline không bị crash khi tính mean, std, filter hoặc train model.

### `detrend_signal`

```python
def detrend_signal(x):
    if len(x) < 3:
        return x.copy()
    return signal.detrend(x).astype(np.float32)
```

`detrend` loại bỏ xu hướng tuyến tính trong cửa sổ. Với PPG, tín hiệu có thể trôi nền do thay đổi tiếp xúc, lực ép, ánh sáng, vị trí cảm biến. Detrend giúp giảm ảnh hưởng của thành phần nền chậm.

Nếu tín hiệu quá ngắn, hàm trả về bản copy vì detrend không có ý nghĩa.

### `butter_bandpass_filter`

```python
def butter_bandpass_filter(x, fs, lowcut=0.7, highcut=5.0, order=3):
```

Đây là bộ lọc thông dải Butterworth. Nó giữ lại dải tần từ `0.7 Hz` đến `5.0 Hz`.

Quy đổi sang nhịp tim:

```text
0.7 Hz * 60 = 42 BPM
5.0 Hz * 60 = 300 BPM
```

Dải này bao phủ phần nhịp tim người thường quan tâm, đồng thời loại bớt drift rất chậm và nhiễu cao tần.

Các bước bên trong:

```python
nyq = 0.5 * fs
low = lowcut / nyq
high = highcut / nyq
```

Butterworth trong SciPy cần tần số chuẩn hóa theo Nyquist frequency.

```python
low = max(0.001, low)
high = min(0.99, high)
```

Giới hạn để tránh tần số lọc không hợp lệ.

```python
b, a = butter(order, [low, high], btype="band")
```

Tạo hệ số bộ lọc.

```python
return filtfilt(b, a, x).astype(np.float32)
```

`filtfilt` lọc tiến và lùi. Ưu điểm là giảm phase shift, tức đỉnh tín hiệu ít bị lệch vị trí hơn. Điều này quan trọng khi dùng peak detection hoặc autocorrelation.

### `robust_zscore`

```python
def robust_zscore(x):
```

Hàm này chuẩn hóa tín hiệu bằng median và MAD:

```python
med = np.median(x)
mad = np.median(np.abs(x - med))
scale = 1.4826 * mad
```

MAD ít bị ảnh hưởng bởi outlier hơn standard deviation. PPG có thể có spike hoặc đoạn nhiễu mạnh, nên robust normalization ổn định hơn z-score thường.

Nếu MAD quá nhỏ, hàm fallback sang `np.std`. Nếu vẫn quá nhỏ thì dùng scale `1.0` để tránh chia cho 0.

### `preprocess_ppg`

```python
def preprocess_ppg(sig, fs):
    x_raw = safe_nan_to_num(sig)
    x_dt = detrend_signal(x_raw)
    x_bp = butter_bandpass_filter(x_dt, fs=fs, lowcut=0.7, highcut=5.0, order=3)
    x_norm = robust_zscore(x_bp)
    return x_raw, x_dt, x_bp, x_norm
```

Đây là pipeline tiền xử lý hoàn chỉnh:

```text
raw signal
  -> thay NaN/inf
  -> detrend
  -> bandpass 0.7-5 Hz
  -> robust z-score
```

Output gồm 4 phiên bản để có thể debug:

- `x_raw`: tín hiệu gốc đã sạch NaN.
- `x_dt`: tín hiệu đã detrend.
- `x_bp`: tín hiệu đã lọc dải.
- `x_norm`: tín hiệu đã chuẩn hóa, dùng chính cho feature extraction.

Trong firmware ESP32, pipeline có thể không giống 100% vì tài nguyên hạn chế, nhưng logic chung là giống: làm sạch, bỏ nền, chuẩn hóa, rồi trích đặc trưng.

## Cell 8 - Trích Đặc Trưng Từ Một Cửa Sổ PPG

Cell này định nghĩa feature extractor. Đây là lõi của notebook và là cầu nối trực tiếp sang firmware.

### `normalized_autocorr`

```python
def normalized_autocorr(x):
```

Hàm tính autocorrelation chuẩn hóa của tín hiệu.

Autocorrelation trả lời câu hỏi: "Nếu dịch tín hiệu đi một độ trễ nào đó, nó còn giống chính nó không?"

PPG có tính chu kỳ theo nhịp tim. Nếu tín hiệu có nhịp rõ, autocorrelation sẽ có đỉnh tại độ trễ tương ứng chu kỳ tim.

Các bước:

```python
x = x - np.mean(x)
denom = np.sum(x * x)
```

Trừ mean để bỏ offset, rồi tính năng lượng tín hiệu.

```python
if denom < 1e-8:
    return np.zeros(len(x), dtype=np.float32)
```

Nếu tín hiệu gần như phẳng, autocorrelation không có nghĩa, trả về zero.

```python
ac = np.correlate(x, x, mode="full")
ac = ac[len(x)-1:] / denom
```

`np.correlate(..., mode="full")` tạo correlation cả lag âm và dương. Notebook chỉ lấy nửa từ lag 0 trở đi. Chia cho `denom` để `ac[0]` xấp xỉ 1.

### `spectral_entropy_from_psd`

```python
def spectral_entropy_from_psd(psd):
```

Hàm này đo độ phân tán năng lượng trong phổ tần số.

- Nếu phổ tập trung mạnh vào một vài tần số, entropy thấp.
- Nếu phổ trải rộng lung tung, entropy cao.

Với PPG, entropy cao có thể gợi ý tín hiệu nhiễu hoặc không có chu kỳ rõ.

Code:

```python
psd = np.maximum(psd, 1e-12)
psd = psd / np.sum(psd)
return -sum(psd * log(psd)) / log(len(psd))
```

Nó chuẩn hóa PSD thành phân phối xác suất, rồi tính entropy chuẩn hóa về khoảng tương đối ổn định.

### `bandpower`

```python
def bandpower(freqs, psd, fmin, fmax):
```

Hàm tính năng lượng phổ trong một dải tần.

```python
mask = (freqs >= fmin) & (freqs <= fmax)
```

Lấy các tần số trong dải.

```python
return integrator(psd[mask], freqs[mask])
```

Tích phân PSD theo tần số bằng `np.trapezoid` hoặc fallback `np.trapz`.

### `extract_ppg_features`

```python
def extract_ppg_features(sig_raw, fs):
```

Hàm này nhận một cửa sổ tín hiệu PPG và tần số lấy mẫu, trả về dictionary các feature.

Đầu tiên:

```python
x_raw, _, _, x = preprocess_ppg(sig_raw, fs)
n = len(x)
```

`x` là tín hiệu đã tiền xử lý và chuẩn hóa. Hầu hết feature được tính trên `x`, không phải raw.

#### Feature cơ bản

```python
feats["n_samples"] = float(n)
feats["duration_sec"] = float(n / fs)
```

Hai feature này mô tả cửa sổ. Sau này bị drop vì cửa sổ cố định nên không mang thông tin dự đoán.

```python
dx = np.diff(x)
```

`dx` là sai khác giữa các mẫu liên tiếp, dùng để đo độ dốc.

```python
feats["mean"] = np.mean(x)
feats["std"] = np.std(x)
feats["ptp"] = np.ptp(x)
feats["rms"] = sqrt(mean(x**2))
feats["abs_mean"] = mean(abs(x))
feats["slope_abs_mean"] = mean(abs(dx))
```

Ý nghĩa:

- `mean`: trung bình tín hiệu sau chuẩn hóa.
- `std`: mức dao động.
- `ptp`: peak-to-peak, biên độ cực đại - cực tiểu.
- `rms`: năng lượng hiệu dụng.
- `abs_mean`: biên độ tuyệt đối trung bình.
- `slope_abs_mean`: tín hiệu thay đổi nhanh hay chậm.

#### Peak-based feature

```python
min_distance = max(1, int(fs * 0.33))
```

Khoảng cách tối thiểu giữa hai đỉnh là `0.33s`. Điều này tương ứng nhịp tối đa khoảng:

```text
60 / 0.33 ≈ 181 BPM
```

Nó tránh việc nhiễu nhỏ bị đếm thành nhiều đỉnh quá sát nhau.

```python
prominence = max(0.05, 0.15 * np.std(x))
peaks, peak_props = find_peaks(x, distance=min_distance, prominence=prominence)
```

`prominence` yêu cầu đỉnh phải nổi bật đủ so với xung quanh. Nếu prominence quá thấp, nhiễu bị đếm nhầm. Nếu quá cao, đỉnh thật có thể bị bỏ sót.

Feature:

```python
n_peaks
peak_rate_per_sec
```

Nếu có ít nhất hai đỉnh:

```python
ibi = np.diff(peaks) / fs
hr_inst = 60.0 / ibi
hr_est_mean = mean(hr_inst)
hr_est_std = std(hr_inst)
```

`IBI` là inter-beat interval, khoảng thời gian giữa hai đỉnh. HR tức thời = `60 / IBI`.

- `hr_est_mean`: HR ước lượng bằng peak detection.
- `hr_est_std`: độ dao động của HR tức thời. Nếu cao, tín hiệu hoặc peak detection có thể không ổn định.

Nếu không đủ đỉnh thì set `0.0`.

`peak_prom_mean` là độ nổi trung bình của đỉnh, giúp model biết đỉnh có rõ hay không.

#### Autocorrelation feature

```python
lag_min = int(fs * 60 / 180)
lag_max = min(int(fs * 60 / 40), len(ac) - 1)
```

Notebook tìm lag tương ứng HR từ 40 đến 180 BPM.

Công thức:

```text
lag = fs * period_sec
period_sec = 60 / BPM
```

Với `fs = 64 Hz`:

- 180 BPM -> period 0.333s -> lag khoảng 21 mẫu.
- 40 BPM -> period 1.5s -> lag khoảng 96 mẫu.

Sau đó:

```python
ac_band = ac[lag_min:lag_max + 1]
best_idx = np.argmax(ac_band)
best_lag = lag_min + best_idx
```

Tìm lag có autocorrelation cao nhất trong dải HR hợp lý.

Feature:

```python
ac_best
ac_best_hr = 60.0 / (best_lag / fs)
```

- `ac_best`: mức tự tương quan tốt nhất, càng cao càng có chu kỳ rõ.
- `ac_best_hr`: HR suy ra từ chu kỳ autocorrelation tốt nhất.

#### Frequency-domain feature

```python
nperseg = min(256, len(x))
if nperseg >= 32:
    freqs, psd = welch(x, fs=fs, nperseg=nperseg)
```

`welch` ước lượng PSD, tức năng lượng tín hiệu theo tần số. Với cửa sổ 8 giây ở 64 Hz, có 512 mẫu, `nperseg=256` là hợp lý.

```python
total_power = bandpower(freqs, psd, 0.0, min(8.0, fs / 2))
hr_power = bandpower(freqs, psd, 0.7, 3.5)
psd_hr_ratio = hr_power / total_power
```

`0.7-3.5 Hz` tương ứng 42-210 BPM. `psd_hr_ratio` cho biết bao nhiêu năng lượng phổ nằm trong dải nhịp tim.

```python
spectral_entropy = spectral_entropy_from_psd(psd)
```

Entropy phổ cao thường là phổ nhiễu/phân tán, entropy thấp hơn nghĩa là có tần số trội rõ.

```python
dom_bpm_hr_band = f_hr[np.argmax(p_hr)] * 60.0
```

Tần số trội trong dải HR được đổi sang BPM.

#### Làm sạch feature cuối hàm

```python
for k, v in list(feats.items()):
    if np.isnan(v) or np.isinf(v):
        feats[k] = 0.0
```

Đảm bảo không có `NaN` hoặc `inf` lọt vào bảng feature. Model sklearn/TensorFlow thường không xử lý tốt NaN.

Kết quả của hàm này là một dictionary feature cho một cửa sổ PPG.

## Cell 9 - Load Dữ Liệu Subject, Cắt Cửa Sổ, Ghép HR

Cell này làm cầu nối từ file dataset sang các cửa sổ feature.

### `_squeeze_to_1d`

```python
def _squeeze_to_1d(x):
```

PPG-DaLiA có thể lưu tín hiệu dạng `(N,)`, `(N,1)`, `(1,N)` hoặc matrix. Hàm này ép mọi dạng về vector 1 chiều `float32`.

Nếu input là 2D:

- Nếu shape `(N,1)`, lấy cột đầu.
- Nếu shape `(1,N)`, lấy hàng đầu.
- Nếu có nhiều cột, lấy cột đầu.

Việc ép dạng nhất quán là cần thiết vì các hàm xử lý tín hiệu phía sau đều giả định input là vector 1D.

### `load_subject_signal_and_hr`

```python
def load_subject_signal_and_hr(file_path: Path):
```

Hàm trả về:

```python
(subject_id, ppg_signal, fs_ppg, hr_ref)
```

Với file `.pkl`:

```python
obj = pickle.load(f, encoding="latin1")
```

`encoding="latin1"` thường cần khi đọc pickle Python 2 hoặc pickle cũ.

Nếu cấu trúc là dict và có key `"signal"`:

```python
wrist = obj.get("signal", {}).get("wrist", {})
ppg = wrist.get("BVP", None)
hr = obj.get("label", None)
fs_ppg = 64.0
```

Trong PPG-DaLiA:

- `signal/wrist/BVP` là tín hiệu PPG cổ tay.
- `label` là HR reference.
- `fs_ppg = 64 Hz` là tần số lấy mẫu BVP trong dataset.

Nếu không có BVP, hàm báo lỗi. Nếu có subject id trong pickle thì dùng subject thật, nếu không thì dùng tên file.

Hàm cũng có fallback cho `.csv`: tìm cột có tên chứa `bvp` hoặc `ppg`, và cột HR chứa `hr` hoặc `heart`.

Trong luồng hiện tại, phần `.pkl` là phần chính.

### `segment_signal`

```python
def segment_signal(sig, fs, win_sec=8.0, stride_sec=2.0):
```

Hàm cắt tín hiệu dài thành nhiều cửa sổ.

```python
win = int(win_sec * fs)
step = int(stride_sec * fs)
```

Với `fs = 64 Hz`:

- Window 8 giây -> `512` mẫu.
- Stride 2 giây -> `128` mẫu.

Vòng lặp:

```python
for start in range(0, len(sig) - win + 1, step):
    end = start + win
    segments.append((start, end, sig[start:end]))
```

Mỗi segment gồm:

- `start`: index bắt đầu trong tín hiệu gốc.
- `end`: index kết thúc.
- `sig[start:end]`: dữ liệu cửa sổ.

Window 8s đủ dài để chứa nhiều chu kỳ tim. Stride 2s tạo overlap lớn, giúp có nhiều mẫu train hơn và mô phỏng việc hệ thống cập nhật HR theo chu kỳ ngắn.

### `interpolate_hr_for_window`

```python
def interpolate_hr_for_window(ppg_len, fs_ppg, hr_array, start, end):
```

PPG và HR label không nhất thiết có cùng tần số hoặc cùng số mẫu. Hàm này lấy HR reference tại tâm cửa sổ PPG.

```python
total_duration = ppg_len / fs_ppg
t_hr = np.linspace(0.0, total_duration, num=len(hr_array), endpoint=False)
```

Tạo trục thời gian cho HR label.

```python
t_center = ((start + end) / 2.0) / fs_ppg
hr_ref = np.interp(t_center, t_hr, hr_array)
```

Lấy thời điểm giữa cửa sổ PPG, rồi nội suy HR tại thời điểm đó.

Đây là bước biến bài toán thành supervised learning: mỗi cửa sổ PPG có một nhãn HR.

## Cell 10 - Tạo Bảng Feature `feature_df`

Cell này chạy pipeline trên toàn bộ subject.

```python
rows = []
errors = []
DEBUG_MAX_SUBJECTS = None
run_files = candidate_files if DEBUG_MAX_SUBJECTS is None else candidate_files[:DEBUG_MAX_SUBJECTS]
```

`DEBUG_MAX_SUBJECTS` cho phép chạy thử vài subject. Khi bằng `None`, chạy full dataset.

Với mỗi file:

```python
sid, ppg, fs_ppg, hr = load_subject_signal_and_hr(fp)
segments = segment_signal(ppg, fs=fs_ppg, win_sec=8.0, stride_sec=2.0)
```

Load subject, rồi cắt thành cửa sổ 8s/stride 2s.

Với mỗi cửa sổ:

```python
feats = extract_ppg_features(seg, fs=fs_ppg)
```

Trích các feature đã định nghĩa ở cell 8.

Sau đó tạo item:

```python
item = {
    "subject_id": str(sid),
    "source_file": str(fp),
    "start": int(start),
    "end": int(end),
    "hr_ref": interpolate_hr_for_window(...)
}
```

Các metadata:

- `subject_id`: dùng để chia train/test theo người.
- `source_file`: trace lại file gốc.
- `start`, `end`: vị trí cửa sổ.
- `hr_ref`: nhãn HR tại tâm cửa sổ.

```python
item.update(feats)
rows.append(item)
```

Gộp metadata và feature thành một dòng.

Cuối cell:

```python
feature_df = pd.DataFrame(rows)
```

`feature_df` là bảng dữ liệu chính của notebook. Mỗi dòng là một cửa sổ PPG. Mỗi cột là metadata, HR label hoặc feature.

Cell cũng lưu lỗi vào `errors` thay vì dừng toàn bộ notebook. Điều này thực dụng vì nếu một subject/file lỗi, các file còn lại vẫn chạy.

## Cell 11 - Chọn Feature Dùng Cho Training

Cell này kiểm tra:

```python
assert len(feature_df) > 0
```

Nếu không có feature nào, dừng ngay vì dataset/load pipeline sai.

```python
DROP_COLS = ["subject_id", "source_file", "start", "end", "hr_ref", "n_samples", "duration_sec"]
feature_cols = [c for c in feature_df.columns if c not in DROP_COLS]
```

Các cột bị drop:

- `subject_id`, `source_file`, `start`, `end`: metadata, không phải feature tín hiệu.
- `hr_ref`: target, không được đưa vào input.
- `n_samples`, `duration_sec`: gần như hằng số vì window cố định, không có giá trị học.

`feature_cols` sau cell này chính là danh sách feature đầu vào của model.

```python
model_df = feature_df.dropna(subset=["hr_ref"]).copy()
```

Chỉ giữ các cửa sổ có nhãn HR. Nếu HR label thiếu, không thể train supervised model.

Cell in số dòng dùng được, số feature, và danh sách feature.

Với notebook hiện tại, feature đầu vào TinyML về sau là 16 feature:

```text
mean, std, ptp, rms, abs_mean, slope_abs_mean,
n_peaks, peak_rate_per_sec,
hr_est_mean, hr_est_std, peak_prom_mean,
ac_best, ac_best_hr,
psd_hr_ratio, spectral_entropy, dom_bpm_hr_band
```

## Cell 12 - Train Baseline Random Forest Theo Subject-Aware Split

Cell này train model baseline đầu tiên.

Điều kiện:

```python
if len(model_df) >= 50:
```

Nếu dữ liệu quá ít thì không train.

```python
groups = model_df["subject_id"].values
y = model_df["hr_ref"].values.astype(np.float32)
X = model_df[feature_cols].astype(np.float32).values
```

- `X`: matrix feature.
- `y`: HR label.
- `groups`: subject id.

```python
X = np.nan_to_num(...)
```

Làm sạch NaN/inf lần nữa ở cấp bảng.

### Vì sao dùng GroupShuffleSplit?

```python
splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
train_idx, test_idx = next(splitter.split(X, y, groups=groups))
```

Nếu chia random từng cửa sổ, cửa sổ của cùng subject có thể xuất hiện cả train và test. Vì các cửa sổ cùng người rất giống nhau, model sẽ được lợi không công bằng. Đây gọi là data leakage.

`GroupShuffleSplit` đảm bảo subject trong test không nằm trong train. Metric vì vậy phản ánh khả năng generalize sang người mới tốt hơn.

### Chuẩn hóa feature

```python
scaler = StandardScaler()
X_train_sc = scaler.fit_transform(X_train)
X_test_sc = scaler.transform(X_test)
```

Scaler chỉ fit trên train, sau đó transform test. Đây là đúng quy trình để tránh rò rỉ thống kê từ test.

Random Forest không quá cần scaling, nhưng việc scale vẫn giữ pipeline nhất quán với MLP/TinyML về sau.

### Model Random Forest

```python
reg = RandomForestRegressor(
    n_estimators=400,
    random_state=SEED,
    n_jobs=-1,
    max_depth=None,
    min_samples_leaf=2,
)
```

Ý nghĩa:

- `n_estimators=400`: dùng 400 cây quyết định.
- `n_jobs=-1`: dùng toàn bộ CPU.
- `max_depth=None`: cây có thể phát triển sâu.
- `min_samples_leaf=2`: mỗi lá ít nhất 2 mẫu, giảm overfit nhẹ.

Random Forest là baseline mạnh cho dữ liệu tabular feature. Nhưng nó không phù hợp để nhúng trực tiếp lên ESP32 trong đồ án vì model lớn, khó export TinyML gọn.

### Metric

```python
mae = mean_absolute_error(y_test, pred)
rmse = sqrt(mean_squared_error(y_test, pred))
r2 = r2_score(y_test, pred)
```

- MAE: sai số tuyệt đối trung bình, đơn vị BPM.
- RMSE: phạt mạnh lỗi lớn.
- R2: mức giải thích phương sai.

Baseline ngu:

```python
baseline_pred = np.full_like(y_test, fill_value=np.mean(y_train))
```

Đây là model luôn đoán HR trung bình của train. Nếu model học máy không tốt hơn baseline này thì pipeline feature/model không có giá trị.

Kết quả đã chạy trong notebook:

```text
Model    -> MAE=8.4416, RMSE=12.8923, R2=0.7042
Baseline -> MAE=18.0302, RMSE=23.7099, R2=-0.0004
```

Điều này cho thấy feature có thông tin dự đoán HR khá rõ.

## Cell 13 - Tạo Difficulty Proxy

Cell này tạo điểm khó của cửa sổ:

```python
out["difficulty_score"] = (
    0.4 * out["hr_est_std"].fillna(0.0) +
    0.3 * (1.0 - np.clip(out["ac_best"].fillna(0.0), 0.0, 1.0)) +
    0.3 * out["spectral_entropy"].fillna(0.0)
)
```

Ý nghĩa từng thành phần:

- `hr_est_std`: nếu HR tức thời từ peak detection dao động nhiều, tín hiệu khó.
- `1 - ac_best`: nếu autocorrelation thấp, chu kỳ không rõ, tín hiệu khó.
- `spectral_entropy`: phổ càng phân tán, tín hiệu càng khó.

Trọng số:

- 40% cho độ bất ổn HR từ peak.
- 30% cho autocorrelation kém.
- 30% cho entropy phổ.

Sau đó chuẩn hóa:

```python
difficulty_score_norm = (score - min) / (max - min)
```

về khoảng 0-1.

Cell này không trực tiếp train model chính, nhưng giúp tư duy về scheduler: cửa sổ "khó" thì cần inference nhiều hơn, cửa sổ dễ thì có thể giảm tần suất xử lý.

Biểu đồ histogram cho biết phân bố độ khó trong dataset.

## Cell 14 - Cross-Validation Theo Subject

Cell này dùng:

```python
gkf = GroupKFold(n_splits=5)
```

Mục tiêu là đánh giá model qua 5 fold mà vẫn tách theo subject.

Mỗi fold:

1. Chia subject train/test.
2. Fit `StandardScaler` trên train.
3. Train RandomForest.
4. Tính MAE, RMSE, R2.

Kết quả `cv_df` cho thấy metric có ổn định giữa các fold không. Nếu một fold lỗi rất lớn, có thể có subject đặc biệt khó hoặc domain shift giữa người.

Cell này quan trọng cho nghiên cứu vì một split duy nhất có thể may mắn hoặc xui. Cross-validation cho cái nhìn chắc hơn.

## Cell 15 - Mô Phỏng Offline Scheduling

Cell này mô phỏng ý tưởng "không inference mọi cửa sổ".

Nó train Random Forest giống trước, sau đó tạo `test_sched` và dự đoán HR:

```python
test_sched["pred_hr"] = rf_sched.predict(X_test_sched_sc)
```

Sau đó tính difficulty:

```python
test_sched = make_difficulty_proxy(test_sched)
```

Chia cửa sổ test thành 3 nhóm:

```python
pd.qcut(..., q=3, labels=["easy", "medium", "hard"])
```

`qcut` chia theo phân vị, nên mỗi bin có số lượng gần tương đương.

Logic keep:

```python
keep_mask[easy_idx[::3]] = True
keep_mask[med_idx[::2]] = True
keep_mask[hard_idx] = True
```

Ý nghĩa:

- Easy: chỉ inference 1/3 cửa sổ.
- Medium: inference 1/2 cửa sổ.
- Hard: inference tất cả cửa sổ.

Đây là mô phỏng adaptive scheduling ở mức offline. Nó chưa dùng firmware, chưa đo năng lượng. Nó chỉ kiểm tra ý tưởng: nếu giảm inference ở cửa sổ dễ, tỷ lệ inference giảm bao nhiêu và sai số trên các cửa sổ được giữ là bao nhiêu.

Kết quả đã chạy:

```text
Full inference windows : 11797
Kept inference windows : 7209
Inference ratio        : 0.6111
Full MAE               : 8.4491
Kept MAE               : 9.6776
```

Nghĩa là chỉ giữ khoảng 61% cửa sổ để inference. MAE trên nhóm giữ lại cao hơn, vì nhóm hard được giữ nhiều hơn. Cell này chủ yếu dùng để phát triển trực giác scheduling, không phải kết quả cuối cùng của báo cáo.

## Cell 16 - Kiểm Tra Difficulty Có Liên Quan Đến Sai Số Không

Cell này kiểm tra xem `difficulty_score_norm` có tương quan với lỗi dự đoán không.

Sau khi train RF:

```python
test_view["abs_error"] = np.abs(test_view["hr_ref"] - test_view["pred_hr"])
```

Tính correlation:

```python
corr = test_view[["difficulty_score_norm", "abs_error"]].corr().iloc[0, 1]
```

Nếu correlation dương, cửa sổ được đánh giá khó thường có lỗi cao hơn. Điều đó ủng hộ việc dùng difficulty/quality làm căn cứ scheduler.

Cell cũng vẽ scatter:

```text
x = difficulty_score_norm
y = absolute HR error
```

và thống kê lỗi theo bin `easy/medium/hard`.

Cell này là cầu nối tư duy giữa machine learning offline và quality gate trong firmware. Nó giúp trả lời: "Các chỉ số tín hiệu có thể dự báo cửa sổ khó không?"

## Cell 17 - So Sánh Ridge, MLP Nhỏ, Random Forest

Cell này tạo `model_zoo`:

```python
model_zoo = {
    "Ridge": Ridge(alpha=1.0),
    "MLP_small": MLPRegressor(...),
    "RF": RandomForestRegressor(...),
}
```

Mục tiêu là so sánh nhanh ba họ model trên cùng feature:

- `Ridge`: tuyến tính, rất nhẹ nhưng khả năng biểu diễn hạn chế.
- `MLP_small`: neural network nhỏ từ sklearn.
- `RF`: mạnh trên tabular, nhưng khó triển khai nhúng.

Tất cả dùng cùng train/test split và scaler, rồi tính MAE/RMSE/R2.

Cell này giúp chọn hướng model. Random Forest có thể tốt offline, nhưng TinyML deployment cần neural network dạng dense/MLP vì TensorFlow Lite Micro hỗ trợ tốt hơn.

## Cell 18 - Vẽ True vs Predicted Và Feature Importance

Cell này trực quan hóa baseline Random Forest.

```python
plt.scatter(y_test, pred)
plt.plot([lo, hi], [lo, hi], "r--")
```

Nếu model hoàn hảo, điểm sẽ nằm trên đường chéo `y = x`. Điểm càng lệch xa đường chéo, dự đoán càng sai.

Tiếp theo:

```python
imp_df = pd.DataFrame({
    "feature": feature_cols,
    "importance": reg.feature_importances_
})
```

Random Forest có thuộc tính `feature_importances_`, cho biết feature nào được dùng nhiều để giảm lỗi trong các cây.

Biểu đồ top feature giúp hiểu model đang dựa vào gì:

- Có dựa vào autocorrelation không?
- Có dựa vào PSD không?
- Có dựa quá nhiều vào peak detection không?

Điều này hữu ích khi port sang firmware: feature quan trọng cao nên được ưu tiên giữ nếu cần giảm chi phí tính toán.

## Cell 19 - Mở Đầu TinyML Track

Cell markdown này chuyển từ baseline sklearn sang hướng triển khai thật:

```markdown
## TinyML track: MLP -> TFLite (FP32 + INT8)
```

Mục tiêu phần này:

- Train MLP bằng TensorFlow/Keras.
- Export TFLite FP32.
- Quantize sang INT8.
- So sánh Keras, FP32 TFLite và INT8 TFLite.
- Xuất test vectors để firmware có thể kiểm tra runtime.

Đây là phần trực tiếp tạo model cho ESP32-S3.

## Cell 20 - Kiểm Tra TensorFlow Và Chuẩn Bị Dữ Liệu TinyML

Đầu cell:

```python
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    HAS_TF = True
except Exception:
    HAS_TF = False
```

Nếu máy không có TensorFlow, notebook vẫn có thể chạy phần sklearn, nhưng bỏ qua TinyML.

Tạo thư mục artifact:

```python
TINYML_ARTIFACT_DIR = Path("./artifacts/ppg_dalia_tinyml")
```

Các file model, scaler, metadata, test vector sẽ lưu ở đây.

Nếu đủ dữ liệu và có TensorFlow:

```python
tinyml_df = model_df.copy().reset_index(drop=True)
tinyml_feature_cols = feature_cols.copy()
```

Tạo dữ liệu:

```python
X_all = tinyml_df[tinyml_feature_cols].astype(np.float32).values
y_all = tinyml_df["hr_ref"].astype(np.float32).values.reshape(-1, 1)
groups_all = tinyml_df["subject_id"].values
```

Tiếp tục dùng subject-aware split:

```python
split = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
```

Sau đó chuẩn hóa feature:

```python
tiny_scaler = StandardScaler()
X_train = tiny_scaler.fit_transform(X_train_raw).astype(np.float32)
X_test = tiny_scaler.transform(X_test_raw).astype(np.float32)
```

Cell này mới chỉ chuẩn bị split ban đầu. Cell 21 sẽ chia train tiếp thành fit/val để chọn model tốt nhất.

## Cell 21 - Train Nhiều Candidate MLP Và Export TFLite

Đây là cell dài nhất và quan trọng nhất của notebook.

### Điều kiện chạy

```python
if len(model_df) >= 50 and HAS_TF:
```

Chỉ chạy khi có đủ dữ liệu và TensorFlow.

### Hàm `build_tinyml_mlp`

```python
def build_tinyml_mlp(input_dim: int, config: dict):
```

Hàm này tạo model Keras theo config.

Input:

```python
inputs = keras.Input(shape=(input_dim,), name="ppg_features")
```

`input_dim` là số feature, ở đây là 16.

Với mỗi layer:

```python
x = layers.Dense(
    units,
    activation="relu",
    kernel_initializer="he_normal",
    kernel_regularizer=reg,
)(x)
```

Giải thích:

- `Dense`: fully-connected layer.
- `units`: số neuron.
- `relu`: activation phổ biến, nhẹ và dễ triển khai.
- `he_normal`: initializer phù hợp ReLU.
- `kernel_regularizer=l2`: phạt trọng số lớn để giảm overfit.

Nếu có dropout:

```python
x = layers.Dropout(dropout_rate)(x)
```

Dropout chỉ dùng khi train, giúp giảm overfit. Khi convert sang inference, dropout không hoạt động.

Output:

```python
outputs = layers.Dense(1, activation="linear", name="hr_pred_norm")(x)
```

Model dự đoán một số thực: HR đã được chuẩn hóa. Activation linear phù hợp regression.

Compile:

```python
optimizer=Adam(...)
loss=Huber(...)
metrics=[MeanAbsoluteError]
```

Huber loss ít nhạy với outlier hơn MSE. HR label/tín hiệu PPG có thể có đoạn nhiễu, nên Huber là lựa chọn hợp lý.

### Hàm `denorm_hr`

```python
def denorm_hr(y_norm, mean, std):
    return y_norm * std + mean
```

Trong training, target HR được chuẩn hóa:

```python
y_norm = (y - hr_mean) / hr_std
```

Do đó khi đánh giá phải đưa output về BPM:

```python
y_bpm = y_norm * hr_std + hr_mean
```

### Chia train thành fit/val/test theo subject

Cell đã có train/test từ cell 20. Ở cell 21, train được chia tiếp:

```python
split_val = GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=SEED + 11)
fit_idx, val_idx = next(split_val.split(X_train_raw, y_train_full_vec, groups=train_groups_all))
```

Kết quả:

- `fit`: dùng để train trọng số.
- `val`: dùng để chọn model, early stopping.
- `test`: giữ riêng đến cuối để đánh giá sau chọn model.

Điểm quan trọng: vẫn chia theo subject. Validation subject không trùng fit subject.

### Chuẩn hóa feature và target

```python
tiny_scaler = StandardScaler()
X_fit = tiny_scaler.fit_transform(X_fit_raw).astype(np.float32)
X_val = tiny_scaler.transform(X_val_raw).astype(np.float32)
X_test = tiny_scaler.transform(X_test_raw).astype(np.float32)
```

Scaler fit trên `X_fit`, rồi áp dụng cho val/test.

Target HR:

```python
hr_mean = mean(y_fit_vec)
hr_std = std(y_fit_vec) + 1e-6
y_fit_norm = (y_fit_vec - hr_mean) / hr_std
```

Lý do normalize target:

- Neural network train ổn định hơn khi output có scale gần 0.
- Quantization INT8 cũng dễ hơn khi output distribution hợp lý.

### Candidate configs

Cell định nghĩa nhiều kiến trúc MLP:

```python
baseline_64_32
mlp_128_128_64_do015
mlp_192_128_64_do020
mlp_256_128_64_do025
mlp_128_128_64_32_do020
```

Mỗi config có:

- `layers`: số neuron từng layer.
- `dropout`: dropout rate.
- `l2`: regularization.
- `lr`: learning rate.
- `batch_size`: batch size.
- `huber_delta`: tham số Huber loss.

Notebook không chọn một model theo cảm tính, mà train nhiều candidate rồi chấm điểm.

### Hàm `run_candidate`

Hàm này train một model candidate.

```python
tf.keras.backend.clear_session()
tf.keras.utils.set_random_seed(SEED + iteration)
```

Clear session để tránh graph/model cũ chiếm RAM. Set seed để kết quả ổn định hơn.

Callbacks:

```python
EarlyStopping(monitor="val_mae", patience=25, restore_best_weights=True)
```

Dừng train nếu validation MAE không cải thiện sau 25 epoch. `restore_best_weights=True` lấy lại trọng số tốt nhất.

```python
ReduceLROnPlateau(monitor="val_mae", factor=0.5, patience=8, min_lr=1e-5)
```

Nếu val MAE đứng yên, giảm learning rate một nửa để tinh chỉnh.

Train:

```python
model.fit(..., epochs=250, batch_size=..., callbacks=...)
```

Sau train, dự đoán fit/val rồi denormalize về BPM:

```python
fit_pred = denorm_hr(...)
val_pred = denorm_hr(...)
```

Metric:

```python
train_mae
val_mae
val_rmse
overfit_gap = val_mae - train_mae
params = model.count_params()
```

Selection score:

```python
selection_score = val_mae + max(0, overfit_gap - 1.0) * 0.25 + params / 1.0e7
```

Nó ưu tiên:

- `val_mae` thấp.
- Không overfit quá nhiều.
- Ít tham số hơn.

Đây là tiêu chí phù hợp TinyML: không chỉ cần chính xác, mà còn cần model nhỏ.

### Stage 2 nếu model chưa đủ tốt

```python
if best_bundle["result"]["val_mae"] > 7.0:
```

Nếu validation MAE vẫn cao hơn 7 BPM, notebook thử thêm model rộng hơn:

- `stage2_256_192_96_do030`
- `stage2_192_192_128_64_do025`

Đây là bước tìm kiến trúc mạnh hơn khi candidate ban đầu chưa đạt.

### Chọn model tốt nhất

```python
tinyml_candidates_df = pd.DataFrame(candidate_results).sort_values(...)
best_config = best_bundle["config"]
tinyml_model = build_tinyml_mlp(...)
tinyml_model.set_weights(best_bundle["weights"])
```

Notebook lưu lại trọng số tốt nhất, rebuild model rồi gán weights.

Đánh giá test:

```python
keras_pred_norm = tinyml_model.predict(X_test)
keras_pred = denorm_hr(keras_pred_norm, hr_mean, hr_std)
keras_mae, keras_rmse, keras_r2
```

Kết quả đã chạy:

```text
Selected: mlp_192_128_64_do020
Validation MAE=4.6383
Test MAE=8.1217, RMSE=12.6226, R2=0.7165
```

Lưu ý: đây là kết quả trong notebook hiện tại. Nếu báo cáo dùng số khác, cần kiểm tra lại phiên chạy/artifact.

### Vẽ learning curves

Cell tạo `hist_df` từ history:

```python
hist_df["train_mae_bpm"] = hist_df["mae"] * hr_std
hist_df["val_mae_bpm"] = hist_df["val_mae"] * hr_std
```

Vì model train trên target normalized, MAE trong history cũng ở đơn vị normalized. Nhân với `hr_std` để ra BPM.

Biểu đồ gồm:

- Train/val Huber loss.
- Train/val MAE BPM.

Nếu train giảm nhưng val tăng, model overfit. Nếu cả hai cao, model underfit hoặc feature chưa đủ.

### Lưu Keras model

```python
tinyml_model_path = TINYML_ARTIFACT_DIR / "ppg_hr_mlp.keras"
tinyml_model.save(tinyml_model_path)
```

File `.keras` là model Keras đầy đủ, dùng để reload hoặc convert lại.

### Convert TFLite FP32

```python
converter_fp32 = tf.lite.TFLiteConverter.from_keras_model(tinyml_model)
tflite_fp32 = converter_fp32.convert()
```

FP32 TFLite vẫn dùng float32, dễ kiểm tra độ đúng so với Keras, nhưng chưa tối ưu kích thước/năng lượng cho vi điều khiển.

### Representative dataset cho INT8

```python
def representative_dataset():
    n_rep = min(512, len(X_fit))
    idx = np.linspace(0, len(X_fit) - 1, n_rep, dtype=int)
    for i in idx:
        yield [X_fit[i:i+1].astype(np.float32)]
```

INT8 quantization cần một tập dữ liệu mẫu để TensorFlow biết phân bố activation. Nó dùng tập này để tính scale/zero-point cho tensor.

Nếu representative dataset không giống dữ liệu thật, quantization có thể làm sai số tăng.

### Convert TFLite INT8

```python
converter_int8.optimizations = [tf.lite.Optimize.DEFAULT]
converter_int8.representative_dataset = representative_dataset
converter_int8.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter_int8.inference_input_type = tf.int8
converter_int8.inference_output_type = tf.int8
```

Ý nghĩa:

- Bật tối ưu/quantization mặc định.
- Chỉ dùng op INT8 built-in.
- Input/output đều INT8.

Đây là dạng phù hợp hơn cho TensorFlow Lite Micro trên ESP32-S3.

Lưu:

```python
ppg_hr_mlp_int8.tflite
```

### Lưu metadata

```python
target_norm_meta = {
    "hr_mean": hr_mean,
    "hr_std": hr_std,
    "best_config": best_config,
    "validation_mae": best_result["val_mae"],
    "test_mae": keras_mae,
}
```

Firmware cần `hr_mean` và `hr_std` để biến output normalized của model về BPM.

Cell cũng lưu:

- `tinyml_feature_columns.json`: thứ tự feature.
- `tinyml_scaler.pkl`: scaler Python.
- `tinyml_target_norm.json`: thông tin normalize HR.
- `tinyml_candidate_results.csv`: bảng kết quả candidate.
- `tinyml_best_history.csv`: history model tốt nhất.

Thứ tự feature cực kỳ quan trọng. Nếu firmware đưa feature sai thứ tự so với training, model output sẽ sai.

## Cell 22 - Kiểm Tra TFLite FP32/INT8 Và Xuất Test Vector

Cell này đánh giá model sau khi convert sang TFLite.

### Hàm `tflite_predict_regression`

```python
interpreter = tf.lite.Interpreter(model_path=str(model_path))
interpreter.allocate_tensors()
```

Tạo TFLite interpreter trên máy tính để chạy thử model `.tflite`.

Lấy input/output details:

```python
in_detail = interpreter.get_input_details()[0]
out_detail = interpreter.get_output_details()[0]
```

Các thông tin quan trọng:

- dtype input/output: float32 hay int8.
- tensor index.
- quantization scale/zero-point.

Nếu input là INT8:

```python
x_q = np.clip(np.round(x / in_scale + in_zero), -128, 127).astype(np.int8)
```

Đây là công thức lượng tử hóa:

```text
x_int8 = round(x_float / scale + zero_point)
```

Nếu output là INT8:

```python
y = (y.astype(np.float32) - out_zero) * out_scale
```

Đây là công thức giải lượng tử:

```text
y_float = (y_int8 - zero_point) * scale
```

Hàm trả về:

- `preds`: output normalized float.
- info dtype/quantization.

### Đánh giá FP32 và INT8

```python
pred_fp32_norm = tflite_predict_regression(tflite_fp32_path, X_test)
pred_int8_norm = tflite_predict_regression(tflite_int8_path, X_test)
```

Sau đó denormalize:

```python
pred_fp32 = pred_fp32_norm * hr_std + hr_mean
pred_int8 = pred_int8_norm * hr_std + hr_mean
```

Metric:

```python
fp32_mae, fp32_rmse
int8_mae, int8_rmse
```

Kết quả đã chạy trong notebook cho thấy INT8 size khoảng `48.22 KB`, FP32 khoảng `144.08 KB`, nén gần `3x`.

Thông tin quantization đã in:

```text
INT8 input scale ≈ 0.06454043, zero_point = -52
INT8 output scale ≈ 0.02245928, zero_point = -37
```

Firmware phải dùng đúng scale/zero-point này hoặc để TFLite Micro xử lý tensor quantization đúng cách.

### Xuất test vector

```python
n_export = min(16, len(X_test))
x_export = X_test[:n_export]
y_export = y_test_vec[:n_export]
```

Lấy tối đa 16 mẫu test.

```python
x_export_q = np.clip(np.round(x_export / in_scale + in_zero), -128, 127).astype(np.int8)
```

Tạo input INT8 tương ứng.

Lưu:

- `tinyml_x_test_fp32.npy`
- `tinyml_x_test_int8.npy`
- `tinyml_y_test.npy`
- `tinyml_model_compare.csv`

Các file này dùng để debug firmware: cùng một vector input, Python và ESP32 có cho output tương tự không?

## Cell 23 - Lưu Artifact Baseline Feature-Based

Cell này tạo:

```python
ARTIFACT_DIR = Path("./artifacts/ppg_dalia_feature_baseline")
```

Lưu bảng feature:

```python
feature_df.to_csv("feature_table.csv")
```

Lưu danh sách feature:

```python
feature_columns.json
```

Nếu có scaler và Random Forest:

```python
joblib.dump(scaler, "scaler.joblib")
joblib.dump(reg, "rf_hr_regressor.joblib")
```

Ý nghĩa:

- `feature_table.csv`: dữ liệu đã xử lý, không cần trích lại từ raw mỗi lần.
- `feature_columns.json`: thứ tự feature baseline.
- `scaler.joblib`: scaler sklearn.
- `rf_hr_regressor.joblib`: model Random Forest baseline.

Random Forest này chủ yếu phục vụ phân tích offline, không phải model nhúng chính.

## Cell 24 - Xuất TFLite INT8 Thành `.c/.h` Cho Firmware

Đây là cell cuối và là bước đưa model vào firmware C/C++.

### Hàm `write_c_array_files`

```python
def write_c_array_files(tflite_path, header_path, source_path, var_name):
```

Đọc bytes của file `.tflite`:

```python
data = tflite_path.read_bytes()
```

Tạo include guard cho header:

```python
guard = header_path.name.replace(".", "_").upper()
```

Header sinh ra có dạng:

```c
#ifndef PPG_HR_MLP_INT8_H
#define PPG_HR_MLP_INT8_H

#ifdef __cplusplus
extern "C" {
#endif

extern const unsigned char ppg_hr_mlp_int8_tflite[];
extern const unsigned int ppg_hr_mlp_int8_tflite_len;

#ifdef __cplusplus
}
#endif

#endif
```

Ý nghĩa:

- Firmware C/C++ có thể include header.
- `extern "C"` giúp C++ không đổi tên symbol.
- Array model được khai báo là `const unsigned char`.

Source `.c` chứa:

```c
const unsigned char ppg_hr_mlp_int8_tflite[] = {
  0x..., 0x..., ...
};

const unsigned int ppg_hr_mlp_int8_tflite_len = ...;
```

Mỗi byte của file `.tflite` được viết thành hex. Khi compile firmware, model trở thành một mảng byte nằm trong chương trình.

### Export model INT8

```python
int8_header_path = TINYML_ARTIFACT_DIR / "ppg_hr_mlp_int8.h"
int8_source_path = TINYML_ARTIFACT_DIR / "ppg_hr_mlp_int8.c"
write_c_array_files(tflite_int8_path, ..., "ppg_hr_mlp_int8_tflite")
```

Kết quả:

- `ppg_hr_mlp_int8.h`
- `ppg_hr_mlp_int8.c`

Đây là hai file firmware target node cần dùng.

### Export scaler cho firmware

```python
tiny_scaler_export = {
    "feature_mean": tiny_scaler.mean_.tolist(),
    "feature_scale": tiny_scaler.scale_.tolist(),
    "target_mean": hr_mean,
    "target_std": hr_std,
}
```

Firmware cần chuẩn hóa feature giống Python:

```text
x_scaled[i] = (x_raw_feature[i] - feature_mean[i]) / feature_scale[i]
```

Sau khi model output normalized:

```text
hr_bpm = y_norm * target_std + target_mean
```

Cell cũng in sẵn C arrays:

```c
const float kScalerMean[16] = { ... };
const float kScalerScale[16] = { ... };
const float kHrMeanBpm = ...;
const float kHrStdBpm = ...;
```

Các hằng số này có thể copy vào firmware C++.

Đây là bước bắt buộc để đảm bảo pipeline training và pipeline firmware đồng nhất. Nếu firmware dùng mean/scale sai, model sẽ nhận input lệch phân phối và dự đoán sai.

## Các Artifact Được Tạo Ra

Sau khi notebook chạy thành công, các artifact chính là:

### `artifacts/ppg_dalia_feature_baseline`

- `feature_table.csv`: toàn bộ bảng cửa sổ + feature + HR label.
- `feature_columns.json`: danh sách feature.
- `scaler.joblib`: scaler sklearn dùng cho baseline.
- `rf_hr_regressor.joblib`: Random Forest baseline.

### `artifacts/ppg_dalia_tinyml`

- `ppg_hr_mlp.keras`: model Keras.
- `ppg_hr_mlp_fp32.tflite`: model TFLite float32.
- `ppg_hr_mlp_int8.tflite`: model TFLite INT8.
- `ppg_hr_mlp_int8.h`: header khai báo model array.
- `ppg_hr_mlp_int8.c`: source chứa bytes model.
- `tinyml_feature_columns.json`: thứ tự 16 feature.
- `tinyml_scaler.pkl`: scaler Python.
- `tinyml_scaler_export.json`: mean/scale/target norm để đưa sang firmware.
- `tinyml_target_norm.json`: mean/std của HR target.
- `tinyml_model_compare.csv`: so sánh Keras/FP32/INT8.
- `tinyml_x_test_fp32.npy`, `tinyml_x_test_int8.npy`, `tinyml_y_test.npy`: test vector.

## Những Công Nghệ Chính Trong Notebook

### PPG/BVP

PPG là tín hiệu quang thể tích. Trong PPG-DaLiA, tín hiệu được gọi là `BVP` ở cổ tay. Nó dao động theo nhịp tim nhưng bị ảnh hưởng bởi chuyển động, tiếp xúc, ánh sáng và nhiễu.

### DSP

Notebook dùng các kỹ thuật xử lý tín hiệu:

- Detrend.
- Bandpass Butterworth.
- Robust z-score.
- Peak detection.
- Autocorrelation.
- Welch PSD.
- Spectral entropy.

Các bước này biến tín hiệu thô thành feature có ý nghĩa vật lý.

### Feature-Based Machine Learning

Thay vì đưa toàn bộ chuỗi 512 mẫu vào model, notebook trích 16 feature. Cách này phù hợp TinyML vì input nhỏ, model đơn giản hơn, dễ debug hơn.

### Subject-Aware Split

Việc chia train/test theo subject là điểm nghiên cứu quan trọng. Nếu không chia theo subject, kết quả có thể quá lạc quan vì model thấy dữ liệu cùng người ở cả train và test.

### Random Forest Baseline

Random Forest dùng để kiểm tra feature có đủ thông tin không. Nó mạnh trên dữ liệu tabular nhưng không phải lựa chọn nhúng chính.

### Keras MLP

MLP là model neural network dense. Nó phù hợp hơn để convert sang TFLite/TFLite Micro.

### TFLite INT8

INT8 quantization giảm kích thước model và phù hợp vi điều khiển. Notebook dùng representative dataset để quantize activation.

### C Array Export

ESP32 firmware không đọc file `.tflite` từ disk như máy tính. Model cần được compile vào firmware dưới dạng mảng byte C.

## Liên Hệ Với Firmware `ppg_hr_tinyml.cpp`

Notebook này tạo ra model và scaler. Firmware target node cần tái hiện các phần sau:

1. Thu cửa sổ PPG.
2. Tiền xử lý tương đương.
3. Trích đúng 16 feature, đúng thứ tự.
4. Chuẩn hóa bằng `feature_mean` và `feature_scale`.
5. Đưa input vào TensorFlow Lite Micro.
6. Gọi `Invoke()`.
7. Giải chuẩn hóa output:

```text
HR = output_norm * target_std + target_mean
```

Nếu bất kỳ bước nào lệch so với notebook, ví dụ sai thứ tự feature hoặc sai scaler, model trên ESP32 sẽ không còn tương đương model offline.

## Các Điểm Cần Cẩn Thận Khi Review

1. Kết quả trong báo cáo và kết quả notebook hiện tại có thể khác nhau nếu notebook đã chạy lại với split/model khác. Cần thống nhất phiên kết quả cuối cùng.
2. PPG-DaLiA là PPG cổ tay, còn prototype MAX30102 của bạn có thể đo ở ngón tay. Đây là domain shift.
3. Feature extractor Python dùng `filtfilt`, `welch`, `find_peaks`; firmware ESP32 có thể phải dùng bản xấp xỉ nhẹ hơn.
4. Random Forest baseline không phải TinyML deployment chính.
5. INT8 model chỉ đúng nếu input đã được scale đúng như lúc train.
6. Test MAE offline không đồng nghĩa với chất lượng lâm sàng trên phần cứng thật.
7. Scheduler trong đồ án không đơn giản là "cứ tín hiệu xấu thì model chạy"; nó cần quality gate, hysteresis và kiểm soát năng lượng ở firmware.

## Tóm Luồng Theo Cell

```text
Cell 0  : mô tả mục tiêu notebook
Cell 1  : cài package
Cell 2  : import thư viện, set seed
Cell 3  : cấu hình Kaggle/data path
Cell 4  : tải dataset
Cell 5  : in cây thư mục dataset
Cell 6  : lọc file S*.pkl
Cell 7  : định nghĩa tiền xử lý PPG
Cell 8  : định nghĩa trích đặc trưng PPG
Cell 9  : load subject, segment tín hiệu, nội suy HR label
Cell 10 : chạy toàn dataset để tạo feature_df
Cell 11 : chọn feature_cols và model_df
Cell 12 : train Random Forest baseline
Cell 13 : tạo difficulty proxy
Cell 14 : GroupKFold cross-validation
Cell 15 : mô phỏng offline adaptive inference
Cell 16 : kiểm tra difficulty liên quan sai số
Cell 17 : so sánh Ridge/MLP/RF
Cell 18 : vẽ true-vs-pred và feature importance
Cell 19 : mở đầu TinyML track
Cell 20 : kiểm tra TensorFlow, chuẩn bị split TinyML
Cell 21 : train nhiều MLP candidate, chọn model, export TFLite
Cell 22 : chạy thử TFLite FP32/INT8, xuất test vector
Cell 23 : lưu artifact baseline
Cell 24 : xuất INT8 TFLite thành C array và scaler cho firmware
```

