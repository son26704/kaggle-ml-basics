Tôi đọc cả firmware mới và notebook mới của bạn. Vấn đề chính không nằm ở notebook nữa, mà nằm ở **cách định nghĩa profile và logic scheduler trên firmware**. File firmware hiện tại cho thấy bạn đang dùng ba profile với `spo2_config = 0x27 / 0x23 / 0x25`, `fifo_config = 0x50 / 0x30 / 0x50`, và scheduler on-device chỉ dùng `std` + `ptp` để tạo `quality_pass` và `difficulty_proxy`, rồi chuyển giữa `50sps_med` và `100sps_med`. 

## Kết luận ngắn gọn

Hiện tại “chưa ổn” là do **ba lỗi thiết kế chồng nhau**:

1. **Ba profile của bạn đang cho ra gần như cùng effective sample rate ~25 Hz**, nên so sánh fixed/adaptive bị méo.
2. **Scheduler trên firmware không giống policy notebook**; notebook dùng proxy dựa trên `ac_best`, `hr_est_std`, `spectral_entropy`, còn firmware chỉ dùng amplitude (`std`, `ptp`).
3. **Window trên firmware đang là 200 samples cố định**, nên nếu sau này profile thật sự khác sample rate thì “một window” sẽ không còn là cùng độ dài thời gian nữa. 

Từ đây, hướng đi đúng là:

> **dừng tinh chỉnh notebook thêm**, quay lại sửa firmware để profile thật sự khác nhau và scheduler on-device bám gần notebook hơn.

---

# 1) Phân tích vì sao log hiện tại nhìn “kỳ”

Từ notebook của bạn:

* tất cả fixed modes đều đang ra `fs_mean_hz ≈ 25`
* adaptive good lại ở state high quá nhiều
* adaptive bad lại ở state normal quá nhiều

Đây là tín hiệu rất mạnh rằng:

* profile chưa được cấu hình “tách nhau” đúng cách
* và rule chuyển state đang **đảo ngược trực giác** trong thực tế

## Vì sao mọi profile lại ra ~25 Hz?

Nhìn vào code firmware:

* `PROFILE_100SPS_MED`: `spo2_config = 0x27`, `fifo_config = 0x50`
* `PROFILE_50SPS_MED`: `spo2_config = 0x25`, `fifo_config = 0x50`
* `PROFILE_25SPS_LOW`: `spo2_config = 0x23`, `fifo_config = 0x30` 

Có hai vấn đề ở đây.

### Vấn đề A — `25sps_low` thực ra không phải 25 sps

MAX30102 không có chế độ 25 sps “thật” theo kiểu bạn đang đặt tên. Tức là tên profile đang gây hiểu nhầm. Điều này làm bạn nghĩ là đang đánh giá 25/50/100, nhưng thực tế không phải vậy.

### Vấn đề B — FIFO averaging đang kéo effective output rate xuống

Bạn đang dùng:

* `0x50` cho FIFO config ở 50sps_med và 100sps_med
* `0x30` cho profile low

Kết quả notebook ~25 Hz ở mọi profile rất phù hợp với giả thuyết:

* **sample averaging / decimation đang làm output ra cùng nhịp 25 Hz**
* nên ba profile của bạn không còn tách biệt như kỳ vọng

Nói cách khác:

> Bạn đang so “ba tên profile khác nhau”, nhưng tín hiệu log ra lại gần như cùng nhịp thời gian.

Đây là nguyên nhân gốc đầu tiên.

---

# 2) Vì sao adaptive đang hành xử ngược kỳ vọng

Firmware hiện tại tính:

* `quality_pass = (std >= SCHED_STD_MIN && ptp >= SCHED_PTP_MIN)`
* `difficulty_proxy = 1 - quality_score`
* `quality_score` chỉ từ `std_score` và `ptp_score` 

Trong khi notebook lại đánh giá “difficulty” bằng các feature giàu thông tin hơn:

* `ac_best`
* `hr_est_std`
* `spectral_entropy`

Đây là hai proxy **khác bản chất**.

## Hệ quả

* good run có thể có biên độ nhỏ hơn mong đợi ⇒ firmware cho là “khó” ⇒ đẩy lên high
* bad run có thể biên độ lớn do motion artifact ⇒ firmware tưởng là “tốt” ⇒ giữ normal

Đó chính là lý do bạn thấy:

* **good** lại ở high nhiều
* **bad** lại ở normal nhiều

### Điểm mấu chốt

`std` và `ptp` **không phân biệt được “PPG đẹp” với “artifact lớn”**.
Motion artifact thường làm biên độ tăng mạnh, nên amplitude-only gate rất dễ sai.

---

# 3) Window 200 samples cố định là một quả bom hẹn giờ

Hiện tại:

```c
#define SCHED_WINDOW_SAMPLES 200U
```

Bạn push IR samples cho đến đủ 200 thì mới đánh giá window. 

Khi mọi profile hiện tại vô tình đều ra ~25 Hz, điều này tương đương khoảng 8 giây.
Nhưng nếu bạn sửa profile đúng:

* 50 Hz → 200 samples = 4 giây
* 100 Hz → 200 samples = 2 giây

Lúc đó:

* threshold cũ mất tác dụng
* difficulty giữa state không còn so sánh được
* hysteresis trở nên vô nghĩa

Nên từ bây giờ bạn phải chốt:

> scheduler phải dùng **window theo thời gian**, không phải theo số mẫu cố định.

---

# 4) Hướng sửa đúng tiếp theo

Tôi khuyên làm theo đúng 4 bước này.

---

## Bước 1 — sửa lại profile để thật sự tách biệt

### Mục tiêu v2 profile

Tạm thời chỉ dùng 3 profile rõ ràng và “có thật”:

* `50sps_low`
* `50sps_med`
* `100sps_med`

Tôi **không khuyên giữ tên `25sps_low` nữa** ở giai đoạn này.

### Vì sao

* 25 sps đang làm bạn rối cả notebook lẫn firmware
* điều bạn cần lúc này là **một profile low-power thật** và **một profile high-fidelity thật**
* low-power có thể đến từ **LED current thấp hơn**, không nhất thiết từ sps thấp hơn

### Gợi ý profile mới

* `50sps_low`: sample rate 50, LED thấp
* `50sps_med`: sample rate 50, LED vừa
* `100sps_med`: sample rate 100, LED vừa

### Đồng thời:

* tắt sample averaging hoặc đặt cùng một averaging cho tất cả profile
* để notebook thấy đúng 50 Hz và 100 Hz thật

---

## Bước 2 — thêm debug dump register sau apply profile

Bạn cần in ra:

* `REG_FIFO_CONFIG`
* `REG_SPO2_CONFIG`
* `REG_LED1_PA`
* `REG_LED2_PA`
* `REG_MODE_CONFIG`

để chắc chắn profile applied đúng.

### Thêm hàm này

```c
static void max30102_dump_profile_regs(const char *name)
{
    uint8_t fifo_cfg = 0, spo2_cfg = 0, led1 = 0, led2 = 0, mode = 0;
    max30102_read_reg(REG_FIFO_CONFIG, &fifo_cfg);
    max30102_read_reg(REG_SPO2_CONFIG, &spo2_cfg);
    max30102_read_reg(REG_LED1_PA, &led1);
    max30102_read_reg(REG_LED2_PA, &led2);
    max30102_read_reg(REG_MODE_CONFIG, &mode);

    ESP_LOGI(TAG,
             "[%s] FIFO=0x%02X SPO2=0x%02X LED1=0x%02X LED2=0x%02X MODE=0x%02X",
             name, fifo_cfg, spo2_cfg, led1, led2, mode);
}
```

và gọi ngay sau `max30102_apply_profile(active_profile);`

---

## Bước 3 — đổi scheduler on-device từ amplitude-only sang “shape-aware”

Bạn chưa cần đưa MLP lên ESP32.
Nhưng bạn phải thêm ít nhất **1 feature hình dạng tuần hoàn** để phân biệt PPG tốt với motion artifact.

## Bộ feature on-device v2 tôi khuyên dùng

* `raw_std`
* `raw_ptp`
* `ac_best`

Nếu làm được thêm:

* `ddx_std`

### Rule mới

Thay vì:

* chỉ dùng `std` + `ptp`

hãy dùng:

* `quality_pass = (raw_std > T_STD) && (raw_ptp > T_PTP) && (ac_best > T_AC)`
* `difficulty_proxy = weighted combination của std_score, ptp_score, ac_score`

Ví dụ:

```c
float std_score = clamp_unit(std / T_STD_REF);
float ptp_score = clamp_unit(ptp / T_PTP_REF);
float ac_score  = clamp_unit(ac_best / T_AC_REF);

float quality_score = 0.25f * std_score + 0.25f * ptp_score + 0.50f * ac_score;
difficulty = 1.0f - quality_score;
```

### Vì sao tăng trọng số cho `ac_best`

Vì `ac_best` mới là thứ phân biệt:

* tín hiệu có chu kỳ thật
* hay chỉ là nhiễu lớn

---

## Bước 4 — đổi sang window theo thời gian

Bạn cần bỏ `SCHED_WINDOW_SAMPLES = 200` và thay bằng:

* `WINDOW_SEC = 4` hoặc `6`
* `window_samples = fs_est * WINDOW_SEC` tùy state/profile

Trong firmware, cách dễ nhất là:

* khi apply profile:

  * gán `current_fs_hz`
  * tính lại `samples_per_window = current_fs_hz * WINDOW_SEC`

Ví dụ:

* 50 Hz, 4 s → 200 mẫu
* 100 Hz, 4 s → 400 mẫu

Như vậy hai state mới được so công bằng.

---

# 5) Notebook cần sửa gì sau khi bạn sửa firmware

Sau khi sửa profile, bạn phải **thu log lại**.
Notebook hiện tại không cần viết lại nhiều, chỉ cần:

* update mapping profile mới
* bỏ `25sps_low`
* so sánh:

  * `50sps_low`
  * `50sps_med`
  * `100sps_med`

## Policy v2 nên là

* **default**: `50sps_med`
* **high-fidelity**: `100sps_med`
* **optional low-power candidate**: `50sps_low`

Tức là low-power bây giờ đến từ **LED current**, không phải “25 sps”.

Đây là hướng an toàn và thực tế hơn.

---

# 6) Bước đo tiếp theo nên làm thế nào

Sau khi sửa firmware, bạn nên thu lại đúng 9 file đầu tiên:

### Mỗi profile 3 run good

* `50sps_low_good_01..03`
* `50sps_med_good_01..03`
* `100sps_med_good_01..03`

### Rồi 9 file bad

* `50sps_low_bad_01..03`
* `50sps_med_bad_01..03`
* `100sps_med_bad_01..03`

### Cuối cùng mới 3 adaptive run

* `adaptive_50_100_good_01..03`
* `adaptive_50_100_bad_01..03`

Tức là bạn cần **18 fixed + 6 adaptive** ở vòng kế tiếp là đẹp.

---

# 7) Scheduler v2 mà tôi khuyên bạn chốt

## State

* `NORMAL = 50sps_med`
* `HIGH = 100sps_med`

## Optional low-power candidate

* `LOW = 50sps_low`
* nhưng chưa dùng cho adaptive v2 cho đến khi fixed logs cho thấy nó ổn

## Rule

### NORMAL → HIGH

Nếu:

* `quality_pass == 0`
  hoặc
* `difficulty_proxy >= TH_HARD`

### HIGH → NORMAL

Nếu:

* `quality_pass == 1`
  và
* `difficulty_proxy <= TH_EASY`
  liên tiếp `K = 2 hoặc 3 windows`

---

# 8) Điều gì đang “ổn” từ notebook hiện tại

Để bạn yên tâm: notebook không hỏng.

Nó đang làm tốt việc:

* parse log
* dựng feature windows
* tạo quality gate
* tính power/quality map
* mô phỏng policy

Cái chưa ổn là **firmware chưa tạo ra experiment đủ sạch và đúng bản chất**.

Cho nên:

> đừng đổi notebook nhiều nữa ở vòng này.
> Tập trung sửa firmware/profiles/scheduler proxy.

---

# 9) Tôi chốt hướng đi cụ thể cho bạn

## Việc làm ngay

1. **Bỏ profile `25sps_low`**
2. **Tạo 3 profile mới: `50sps_low`, `50sps_med`, `100sps_med`**
3. **Đảm bảo effective fs thật sự ra đúng 50 / 100**
4. **Đổi window sang time-based**
5. **Thêm `ac_best` vào scheduler on-device**

## Việc làm sau đó

6. Thu lại fixed logs
7. Chạy notebook cũ gần như nguyên trạng
8. Chỉ khi fixed logs tốt mới chạy adaptive logs mới

---

# 10) Tôi khuyên bạn sửa firmware tiếp như thế nào

Bước tiếp theo hợp lý nhất là:

* tôi viết cho bạn **bản firmware v2**
  bao gồm:
* profile mới `50sps_low / 50sps_med / 100sps_med`
* dump register
* window theo thời gian
* tính `ac_best` nhẹ trên IR
* scheduler 2-state `50 ↔ 100`

