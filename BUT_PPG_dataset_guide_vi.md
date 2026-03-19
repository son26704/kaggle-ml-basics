# BUT PPG Dataset (v2.0.0) – Hướng dẫn đầy đủ cho người mới

Nguồn chính thức: https://physionet.org/content/butppg/2.0.0/

---

## 1) Dataset này là gì?

**BUT PPG** (Brno University of Technology Smartphone PPG Database) là bộ dữ liệu tín hiệu sinh lý dùng để:

1. **Đánh giá chất lượng tín hiệu PPG** (tốt/xấu để ước lượng nhịp tim).
2. **Ước lượng nhịp tim (HR)** từ tín hiệu PPG smartphone.

Theo mô tả chính thức, dữ liệu gồm:
- **3,888 đoạn tín hiệu**, mỗi đoạn dài **10 giây**.
- PPG lấy từ smartphone (30 Hz).
- ECG tham chiếu (1000 Hz) để tính HR “ground truth”.
- Từ bản ghi ID `112001` trở đi có thêm ACC (gia tốc kế, 100 Hz).
- Có nhãn chất lượng PPG và HR tham chiếu.

---

## 2) Dataset thuộc loại bài toán gì trong ML?

Dataset này có thể dùng cho **nhiều loại bài toán**:

### (A) Binary Classification (phổ biến nhất)
- Mục tiêu: dự đoán `Quality`.
- Nhãn:
  - `1` = tín hiệu PPG đủ tốt để ước lượng HR.
  - `0` = tín hiệu kém, HR không đáng tin.

=> Đây là **bài toán phân loại nhị phân**.

### (B) Regression
- Mục tiêu: dự đoán `HR` (beats per minute).
- Nhãn số thực/số nguyên: cột `HR`.

=> Đây là **bài toán hồi quy**.

### (C) Multi-task Learning (nâng cao)
- Dự đoán đồng thời:
  - `Quality` (classification), và
  - `HR` (regression).

=> Thường dùng khi muốn mô hình “biết tự tin hay không” trước khi xuất HR.

### (D) Bài toán phụ (research)
- Dùng PPG + ACC để cải thiện robustness khi có chuyển động.
- Có thể thử dự đoán thêm BP/SpO2/Glycaemia (khó hơn nhiều, cần cẩn trọng vì nhãn dạng snapshot).

---

## 3) Cách gán nhãn (labeling) của BUT PPG

Điểm mạnh của bộ dữ liệu này là cách gán nhãn tương đối chặt chẽ:

1. ECG được dùng làm tham chiếu để tính HR thật (reference HR).
2. Mỗi đoạn PPG được các chuyên gia annotate HR từ PPG.
3. Nếu đa số annotator cho kết quả gần HR tham chiếu (sai số ≤ 5 bpm) thì đoạn đó được xem là **quality = 1**.
4. Nếu không đạt điều kiện trên thì **quality = 0**.

Nghĩa là: nhãn `Quality` không phải cảm tính hoàn toàn, mà dựa trên tiêu chí gắn với độ tin cậy của HR.

---

## 4) Cấu trúc thư mục và file bạn đang có

Trong thư mục gốc:
- `RECORDS.txt`: danh sách toàn bộ record và modality.
- `quality-hr-ann.csv`: bảng nhãn chính (`ID, Quality, HR`).
- `subject-info.csv`: metadata (giới tính, tuổi, vị trí đo, motion, BP, glycaemia, SpO2).
- `ANNOTATORS`: mô tả loại annotation (`csv` cho quality/HR, `qrs` cho QRS từ ECG).
- `SHA256SUMS.txt`: checksum kiểm tra integrity.
- `LICENSE.txt`: giấy phép CC BY 4.0.

Mỗi record ID là thư mục riêng (ví dụ `100001/`) chứa:
- `*_PPG.dat`, `*_PPG.hea`
- `*_ECG.dat`, `*_ECG.hea`
- `*.qrs` (annotation QRS)
- Với ID từ `112001` trở đi có thêm:
  - `*_ACC.dat`, `*_ACC.hea`

---

## 5) Ý nghĩa định danh ID

ID có dạng 6 chữ số, ví dụ `113027`:
- 3 số đầu: subject (người đo).
- 3 số cuối: thứ tự lần đo của subject đó.

=> Khi tách train/val/test, nên tách **theo subject** (group split), không tách random theo record để tránh rò rỉ dữ liệu cùng người.

---

## 6) Định dạng tín hiệu (WFDB)

Dữ liệu thô dùng **WFDB format**:
- `.dat`: samples tín hiệu.
- `.hea`: header mô tả số kênh, sampling rate, đơn vị…

Ví dụ thực tế từ file của bạn:
- `100001_PPG.hea`: 1 kênh, 30 Hz, 300 mẫu (10 giây).
- `100001_ECG.hea`: 1 kênh, 1000 Hz, 10000 mẫu (10 giây).
- `112001_ACC.hea`: 3 kênh, 100 Hz, 1000 mẫu (10 giây) với kênh `ACC_X/Y/Z`.

---

## 7) Thống kê nhanh từ chính dữ liệu local của bạn

### Quy mô
- Tổng record: **3,888**.
- Trong `RECORDS.txt`:
  - PPG records: **3,888**
  - ECG records: **3,888**
  - ACC records: **3,840**

### Subject-level
- Số subject: **50**.
- Giới tính: **25 nữ, 25 nam**.
- Tuổi subject: min **19**, max **76**, mean khoảng **33.90**.

### Nhãn Quality (mất cân bằng lớp)
- `Quality = 0`: **3,058** (~78.7%)
- `Quality = 1`: **830** (~21.3%)

=> Đây là **imbalanced classification** khá rõ.

### HR tham chiếu
- Min: **38 bpm**
- Max: **161 bpm**
- Mean: **78.15 bpm**

Theo quality:
- `Quality=0`: mean HR ~ **79.01**
- `Quality=1`: mean HR ~ **74.96**

### Ear vs Finger
- Ear (`0`): **1,962** record
- Finger (`1`): **1,926** record

Tỉ lệ quality tốt theo vị trí đo:
- Ear: ~**10.6%** quality=1
- Finger: ~**32.3%** quality=1

=> Dữ liệu cho thấy finger dễ có tín hiệu “đủ tốt” hơn ear (trong bộ này).

### Motion distribution (theo `subject-info.csv`)
Mã motion:
- `0`: rest
- `1`: higher pressure
- `2`: moving on lens
- `3`: walking
- `4`: coughing
- `5`: laughing
- `6`: changing light
- `7`: talking

Số lượng:
- motion 0: 2724
- motion 1: 144
- motion 2: 156
- motion 3: 156
- motion 4: 144
- motion 5: 144
- motion 6: 288
- motion 7: 144

Tỉ lệ quality=1 theo motion (xấp xỉ):
- motion 0: 24.4%
- motion 1: 20.1%
- motion 2: 14.1%
- motion 3: 12.2%
- motion 4: 13.2%
- motion 5: 15.3%
- motion 6: 11.1%
- motion 7: 16.0%

=> Càng có nhiễu/chuyển động, tỉ lệ quality tốt thường giảm.

### Về các cột sinh lý phụ
Trong `subject-info.csv`:
- `Blood pressure`, `Glycaemia`, `SpO2` có dữ liệu ở **3840/3888** record.
- 48 record đầu (ID < 112001) thiếu các cột này.

---

## 8) Insight quan trọng khi làm ML với bộ này

1. **Không chỉ là regression HR**: đây là bộ rất phù hợp cho pipeline 2 bước:
   - bước 1: lọc quality,
   - bước 2: mới ước lượng HR.

2. **Mất cân bằng lớp nặng** cho quality:
   - nên dùng stratified/group split, class weight, focal loss, hoặc metric như PR-AUC/F1.

3. **Subject leakage là rủi ro lớn**:
   - nếu random split theo record, model có thể học đặc trưng cá nhân thay vì học quy luật chung.
   - nên split theo subject ID (GroupKFold / GroupShuffleSplit).

4. **Dataset shift giữa phần cũ và phần mới**:
   - ID `<112001`: chủ yếu finger, ít record.
   - ID `>=112001`: nhiều record, thêm ACC, thêm nhãn sinh lý phụ.
   - cần thống nhất chiến lược khi train/eval.

5. **ACC là feature giá trị** cho bài toán quality:
   - vì chất lượng PPG rất nhạy với motion artifact.

6. **BP/SpO2/Glycaemia không phải mục tiêu chính** trong paper gốc:
   - có thể dùng exploratory, nhưng cần kiểm tra kỹ tính nhất quán và nguy cơ confounding.

---

## 9) Gợi ý lộ trình cho người mới (dễ làm, đúng bản chất)

### Bước 1: Bài toán classification `Quality`
- Input: PPG 10 giây (thêm ACC nếu muốn).
- Output: 0/1.
- Baseline: feature thống kê + RandomForest / XGBoost.
- Deep learning: 1D-CNN đơn giản.

### Bước 2: Bài toán regression `HR`
- Chỉ ước lượng HR khi model quality dự đoán là tốt.
- Metric: MAE, RMSE, và có thể báo cáo theo từng nhóm motion.

### Bước 3: Multi-task
- Một backbone, 2 head (`quality`, `HR`) để tối ưu chung.

---

## 10) Kết luận ngắn

- BUT PPG là bộ dữ liệu **đa mục tiêu**, trọng tâm là:
  1) **PPG quality assessment** (classification),
  2) **HR estimation** (regression).
- Label quality được xây theo quy trình có tham chiếu ECG + đồng thuận annotator.
- Với người mới, cách làm thực dụng nhất là: **quality trước, HR sau**, và **split theo subject**.

---

## 11) Trích dẫn và license

- Dataset DOI (v2.0.0): https://doi.org/10.13026/tn53-8153
- License file: Creative Commons Attribution 4.0 (CC BY 4.0)
- Khi dùng dữ liệu/publication, cần trích dẫn theo hướng dẫn trên PhysioNet.
