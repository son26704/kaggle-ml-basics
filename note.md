Đọc cả firmware và notebook mới, tôi thấy vấn đề chính không phải là “PPG không dùng được”, mà là:

> **logic scheduler trên firmware hiện tại chưa tương thích với logic mà notebook đã chứng minh offline.**

Cụ thể, firmware adaptive đang dùng:

* window theo **số mẫu cố định** `SCHED_WINDOW_SAMPLES = 200`
* quality/difficulty tính chỉ từ **raw std + raw ptp**
* rule chuyển state chỉ có **2 state: normal/high**
* threshold cố định `SCHED_STD_MIN`, `SCHED_PTP_MIN`, `SCHED_DIFF_HARD`, `SCHED_DIFF_EASY` 

Trong khi notebook offline của bạn kết luận tốt hơn dựa trên:

* window **8 giây, stride 2 giây**
* quality gate có `ir_raw_ptp`, `peak_rate_per_sec`, `ac_best`, `spectral_entropy`
* difficulty proxy dùng `hr_est_std`, `ac_best`, `spectral_entropy`
* policy chọn 50 ↔ 100 dựa trên các tín hiệu đó

Hai thế giới này hiện đang **không cùng bài toán**.

---

# 1) Vấn đề lớn nhất hiện tại là gì?

Tôi thấy có 3 vấn đề cốt lõi.

## Vấn đề A — Firmware dùng proxy “quá nghèo”

Trong code hiện tại, `scheduler_compute_window_metrics()` chỉ dùng:

* `std`
* `ptp`

để ra:

* `quality_pass`
* `difficulty_proxy`

và difficulty được định nghĩa gần như:

* biên độ càng thấp → càng khó 

Điều này giải thích rất hợp lý kết quả “không ổn”:

* **good** có thể bị đẩy sang `100sps_med` quá nhiều nếu biên độ hơi thấp
* **bad** có thể vẫn ở `50sps_med` nếu biên độ lớn nhưng tín hiệu thực ra nhiễu/méo

Mà notebook của bạn đã chỉ ra đúng điều đó từ dữ liệu thật:

* bad windows có `ir_raw_ptp` rất lớn
* nhưng `ac_best` thấp
* quality kém vì **chu kỳ xấu**, không phải vì biên độ nhỏ

Nói ngắn gọn:

> bad signal của bạn thường là **to nhưng xấu**, còn firmware hiện tại lại đang coi “to” là tốt.

Đây là nguyên nhân số 1.

---

## Vấn đề B — Window firmware không cùng nghĩa với window notebook

Firmware dùng:

```c
#define SCHED_WINDOW_SAMPLES 200U
```

Nghĩa là:

* nếu profile đang là 50 sps → window khoảng 4 giây
* nếu là 100 sps → window khoảng 2 giây
* nếu fs thực tế lệch, thời lượng window lại khác nữa 

Trong khi notebook đang phân tích với:

* **8 giây / stride 2 giây**

Nên threshold offline bạn chọn:

* không thể bê thẳng sang firmware được

Vì firmware đang ra quyết định trên cửa sổ **ngắn hơn rất nhiều**.

---

## Vấn đề C — Adaptive log on-device đang cho thấy policy chưa tốt hơn baseline

Kết quả notebook của bạn cho thấy:

* **adaptive / good**:

  * quality pass chỉ ~0.9167
  * power ~17.87 mW
* trong khi **fixed_50 / good**:

  * quality pass = 1.0
  * power ~16.22 mW

Tức là ở điều kiện tốt:

* adaptive đang **tệ hơn fixed_50 cả về quality lẫn power**

Đây là dấu hiệu rất mạnh rằng:

> policy hiện tại chưa nên đưa vào “kết quả cuối”, mà phải quay lại hiệu chỉnh.

---

# 2) Chẩn đoán chính xác hơn từ kết quả của bạn

Từ notebook hiện tại, có mấy tín hiệu rất rõ:

## Với data thật

* good:

  * `ac_best` cao
  * `ir_raw_ptp` nhỏ vừa phải
* bad:

  * `ir_raw_ptp` rất lớn
  * `ac_best` thấp

Điều này nói rằng:

* **amplitude lớn không có nghĩa là quality tốt**
* ngược lại, PPG đẹp thường có:

  * chu kỳ rõ (`ac_best`)
  * peak rate hợp lý
  * entropy không quá méo

Firmware hiện tại chưa dùng các yếu tố đó.

## Adaptive occupancy hiện tại

* good: phần lớn thời gian ở `high(100sps)` ~88%
* bad: phần lớn thời gian ở `normal(50sps)` ~91%

Đây gần như là **ngược kỳ vọng**.

Điều đó xác nhận rằng rule hiện tại đang “đọc sai bản chất” của tín hiệu.

---

# 3) Hướng đi đúng bây giờ

Bạn **không nên** cố vá threshold cũ mãi.

Bạn nên đổi chiến lược sang:

## Giai đoạn kế tiếp = “Firmware policy v1.5”

với mục tiêu:

* vẫn chỉ dùng **feature đơn giản**
* nhưng phải **đồng pha với notebook hơn**

Tôi khuyên chia làm 2 bước.

---

# 4) Bước sửa firmware quan trọng nhất: thêm `ac_best` hoặc một proxy tuần hoàn đơn giản

Nếu chỉ giữ `std` + `ptp`, bạn sẽ tiếp tục bị lẫn giữa:

* biên độ lớn do nhiễu
* biên độ lớn do PPG tốt

Cần thêm một chỉ số tuần hoàn.

## Tối thiểu nên thêm 1 trong 2 cái:

### Cách 1 — thêm `ac_best` gần đúng

Tính autocorrelation normalized trên IR window, rồi lấy đỉnh tốt nhất trong dải HR hợp lý.

Đây là cách gần nhất với notebook, và là lựa chọn tôi khuyên.

### Cách 2 — nếu chưa muốn autocorr đầy đủ

Dùng một proxy đơn giản hơn:

* số peak hợp lệ
* peak interval variance
* hoặc zero-crossing / periodicity score

Nhưng về lâu dài, `ac_best` vẫn là đẹp nhất.

---

# 5) Policy firmware nên sửa thành gì

Hiện tại bạn có 2 state:

* `50sps_med`
* `100sps_med`

Giữ 2 state là đúng.
**Đừng đưa 25sps_low vào adaptive on-device lúc này.**

## Policy v1.5 tôi khuyên

Default vẫn là `50sps_med`.

### Upshift sang `100sps_med` nếu:

* `quality_pass == 0`
* hoặc `ac_best < AC_LOW`
* hoặc `difficulty_proxy > HARD_T`

### Downshift về `50sps_med` nếu:

* `quality_pass == 1`
* và `ac_best > AC_HIGH`
* và điều này giữ liên tiếp `N` window

### Hysteresis

* lên nhanh: 1 window fail là đủ
* xuống chậm: cần 3–4 window tốt liên tiếp

---

# 6) Sửa “difficulty_proxy” thế nào

Tôi khuyên bỏ công thức hiện tại kiểu:

* std_score + ptp_score → difficulty

và thay bằng công thức nhẹ hơn nhưng hợp lý hơn:

## Gợi ý công thức mới

```text
difficulty = w1 * normalized_hr_variability
           + w2 * (1 - ac_best)
           + w3 * saturation_or_instability_score
```

Nếu chưa có HR variability on-device, bản tối giản là:

```text
difficulty = 0.7 * (1 - ac_best) + 0.3 * low_amplitude_penalty
```

Trong đó:

* `low_amplitude_penalty` chỉ là phần phụ
* yếu tố chính là `ac_best`

Vì từ log thật của bạn, yếu tố tách tốt nhất giữa good/bad là **periodicity**, không phải amplitude.

---

# 7) Bước notebook tiếp theo nên làm gì

Trước khi sửa firmware lớn, bạn nên thêm một thí nghiệm trong notebook:

## So sánh “proxy firmware cũ” với “proxy firmware mới”

Tạo 2 cột:

* `difficulty_old_fw_like`
  = chỉ từ `ir_raw_std`, `ir_raw_ptp`

* `difficulty_new_fw_like`
  = từ `ac_best` + `ir_raw_ptp` nhẹ

rồi so:

* correlation với `condition`
* correlation với `quality_pass`
* correlation với `difficulty_score_norm` hiện tại

Mục tiêu là kiểm chứng trước trên notebook:

* proxy nào phân tách good/bad tốt hơn

---

## Cell nên thêm ngay

```python
quality_df["difficulty_old_fw_like"] = 1.0 - 0.5 * (
    np.clip(quality_df["ir_raw_std"] / 4000.0, 0, 1) +
    np.clip(quality_df["ir_raw_ptp"] / 12000.0, 0, 1)
)

quality_df["difficulty_new_fw_like"] = (
    0.7 * (1.0 - np.clip(quality_df["ac_best"], 0, 1)) +
    0.3 * (1.0 - np.clip(quality_df["ir_raw_ptp"] / 6000.0, 0, 1))
)

cmp = quality_df.groupby("condition")[[
    "difficulty_old_fw_like",
    "difficulty_new_fw_like",
    "difficulty_score_norm",
    "ac_best",
    "ir_raw_ptp"
]].agg(["mean", "std"])

display(cmp)
```

Nếu `difficulty_new_fw_like` tách good/bad rõ hơn, đó là bằng chứng để sửa firmware.

---

# 8) Sửa firmware cụ thể theo mức độ

## Mức 1 — ít sửa nhất

Giữ toàn bộ structure hiện tại, chỉ thay:

* `scheduler_compute_window_metrics()`
* threshold
* downshift hysteresis

### Cần làm

* thêm buffer 200 mẫu IR
* tính `ac_best`
* quality pass = (`ac_best > ngưỡng`) AND (`ptp > ngưỡng tối thiểu`)

Đây là bản tôi khuyên làm ngay.

---

## Mức 2 — sửa đúng hơn nữa

Đổi:

```c
SCHED_WINDOW_SAMPLES = 200
```

thành window theo **thời gian**, không theo số mẫu.

Ví dụ:

* normal 50 sps → 8 giây = 400 mẫu
* high 100 sps → 8 giây = 800 mẫu

Như vậy firmware mới đồng nghĩa với notebook.

### Nhưng:

Cái này sửa nhiều hơn, nên tôi xếp sau Mức 1.

---

# 9) Lộ trình sửa cụ thể tôi khuyên

## Vòng sửa 1

1. Giữ 2-state: `50 ↔ 100`
2. Bỏ `std+ptp-only`
3. Thêm `ac_best`
4. quality gate mới:

   * `ptp > min_ptp`
   * `ac_best > min_ac`
5. downshift chậm hơn:

   * từ 2 window lên **3 hoặc 4 window**
6. cooldown sau switch:

   * tăng lên **2 window**

## Vòng sửa 2

7. nếu vẫn chưa ổn, mới đổi window thành 8 giây thực
8. so lại fixed_50 vs adaptive_v1.5

---

# 10) Kết quả bạn nên hướng tới sau lần sửa tới

Tôi không kỳ vọng adaptive sẽ thắng mọi metric.
Mục tiêu hợp lý hơn là:

## Điều kiện good

* quality gần fixed_50
* power không cao hơn fixed_50 quá nhiều
* ideally thấp hơn hoặc ngang

## Điều kiện bad

* quality tốt hơn fixed_50
* power thấp hơn fixed_100

Nếu đạt được như vậy, adaptive đã có giá trị.

---

# 11) Chốt: bước tiếp theo nên làm gì

Tôi khuyên bạn làm theo đúng thứ tự này:

### Việc 1

Trong notebook, tạo và so sánh:

* `difficulty_old_fw_like`
* `difficulty_new_fw_like`

### Việc 2

Sửa firmware:

* thêm `ac_best` hoặc periodicity proxy tương đương
* tăng `downshift_good_windows`
* tăng `cooldown_windows`

### Việc 3

Thu lại 3 chế độ:

* fixed_50
* fixed_100
* adaptive_v1.5

### Việc 4

Chạy lại notebook và so:

* adaptive vs fixed_50
* adaptive vs fixed_100

---

# 12) Kết luận ngắn gọn

Hiện tại “chưa ổn” là vì:

* firmware đang dùng **proxy sai bản chất**
* notebook cho thấy **quality phụ thuộc periodicity**, không chỉ amplitude
* adaptive hiện đang **upshift sai chỗ và downshift sai chỗ**

Hướng sửa đúng là:

> **thay amplitude-only gate bằng periodicity-aware gate**, rồi chạy lại adaptive.