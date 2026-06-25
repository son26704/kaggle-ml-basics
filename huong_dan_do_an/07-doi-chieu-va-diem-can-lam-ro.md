# 07. Đối chiếu báo cáo, mã nguồn và artifact

## 1. Mục đích

Tài liệu này phân biệt ba lớp:

- báo cáo mô tả;
- firmware thực tế;
- notebook/artifact hiện tại.

Các sai khác không nhất thiết làm đồ án vô hiệu, nhưng phải được biết trước khi bảo vệ.

## 2. Bảng đối chiếu chính

| Chủ đề | Báo cáo | Mã/artifact thực tế | Cần làm rõ |
|---|---|---|---|
| Tần số cảm biến | Nhiều đoạn ghi cấu hình chính 100 Hz | NORMAL 50 sps, HIGH 100 sps | Scheduler thích nghi cả acquisition rate |
| LED current | Phụ lục ghi `0x24` | Firmware dùng `0x18` cả RED/IR | Chốt cấu hình nào tạo log cuối |
| Sample averaging | Phụ lục ghi 4 | `FIFO_CONFIG=0x00`, averaging 1 | Cập nhật báo cáo hoặc firmware |
| Target log | Mô tả như CSV có nhiều field | v7 là console log hỗn hợp; sparse row chỉ 7 cột | Mô tả parser thực tế |
| Macro power | Báo cáo nhấn mạnh dual-MCU | Notebook macro v6 dùng target tự đo INA219 | Nêu rõ macro và micro dùng hai thế hệ log |
| State power | 263,35 / 283,11 mW | Notebook output 263,37 / 282,91 mW | Chọn một nguồn và regenerate |
| Model/scaler | Ngầm hiểu artifact notebook là model firmware | C array và scaler firmware khác artifact hiện tại | Xác định commit/lần train đã flash |
| Tiền xử lý | Mô tả đồng bộ feature | Offline và firmware dùng filter/normalization/PSD khác nhau | Đây là hạn chế deployment |
| Năng lượng AI | Có thể đọc như phân rã đo được | `E_AI` là ước lượng peak × time | Dùng từ “ước lượng” nhất quán |
| HR accuracy prototype | Coverage được đánh giá | Không có HR ground truth trên prototype | Không đồng nhất coverage với accuracy |

## 3. Tần số lấy mẫu

Firmware:

```text
NORMAL = 50 sps, 400 mẫu/cửa sổ
HIGH = 100 sps, 800 mẫu/cửa sổ
```

Cả hai resample về 512 mẫu.

Do đó thiết kế đang thích nghi hai thứ:

1. chất lượng thu nhận;
2. độ phức tạp xử lý.

Nếu báo cáo nói chỉ thích nghi pipeline xử lý thì chưa mô tả đủ firmware.

## 4. Cấu hình MAX30102

Firmware cuối đọc được:

```text
LED1_PA = 0x18
LED2_PA = 0x18
FIFO_CONFIG = 0x00
```

Phụ lục ghi:

```text
LED current = 0x24
sample averaging = 4
```

Trước bảo vệ nên:

1. xác nhận binary/log cuối được tạo từ source nào;
2. nếu source hiện tại là source cuối, sửa phụ lục;
3. nếu báo cáo đúng, tìm commit firmware thật đã flash.

Không nên giải thích bằng suy đoán.

## 5. Model firmware khác artifact hiện tại

Hash `ppg_hr_mlp_int8.c` trong project ESP32 khác hash artifact workspace.

Firmware log model:

```text
model size = 7976 byte
input scale = 0,04944235; zp = -40
output scale = 0,02073984; zp = -31
```

Artifact notebook hiện tại có scaler/target:

```text
target mean = 89,397438
target std = 23,228987
```

Firmware:

```text
target mean = 89,3519745
target std = 22,6059856
```

Kết luận: firmware đang dùng một lần train/export khác.

### Rủi ro

Không thể lấy MAE của artifact hiện tại và mặc định đó chính xác là MAE của binary đang flash nếu chưa xác minh model/scaler cùng phiên bản.

### Việc nên làm

- Lưu model, scaler, metadata theo version.
- Thêm SHA-256 model vào log build.
- Tạo `model_manifest.json`.
- Regenerate firmware từ artifact được dùng trong báo cáo.
- Chạy test vector host và firmware để so output.

## 6. Mismatch tiền xử lý

| Bước | Notebook | Firmware |
|---|---|---|
| Detrend | SciPy linear detrend | custom linear detrend ở Fast Path; full feature không gọi riêng detrend trước filter |
| Bandpass | Butterworth bậc 3, `filtfilt` | high-pass + low-pass một cực |
| Normalization | median/MAD | mean/std |
| Peak | SciPy `find_peaks` | custom local maximum/prominence |
| Peak threshold | 0,15 std; distance 0,33 s | 0,25 std; max HR 140 |
| PSD | Welch | FFT 256 điểm |
| Windowing FFT | Welch tự chia/áp window | không thấy window phổ rõ ràng |

Đây là vấn đề nghiêm túc nhất về AI deployment. Cùng tên feature không đảm bảo cùng distribution.

### Cách trả lời trung thực

- Pipeline firmware được viết lại để phù hợp tài nguyên nhúng.
- Việc giữ 16 feature cùng ý nghĩa giúp tương thích cấu trúc.
- Tuy nhiên chưa có kiểm thử equivalence đầy đủ giữa Python và C++.
- Đây là giới hạn và hướng tiếp theo là tạo golden test vectors, so từng feature.

## 7. Macro và micro dùng hai thế hệ hệ đo

### Macro v6

Target tự đọc INA219 và log power. Kết quả:

- 261,78;
- 273,21;
- 286,94 mW.

### Micro v7

DAQ node riêng đọc INA219 và target không tự đo.

Điều này giải thích tại sao baseline micro khoảng 253-254 mW không khớp hoàn toàn average macro.

Không nên gộp hai bộ số như cùng một protocol đo mà không giải thích.

## 8. `target.csv` không phải CSV chuẩn

File chứa:

```text
I (...) log...
W (...) log...
timestamp,state,...
```

Parser dựa trên regex. Tên `.csv` chỉ phản ánh trong file có dòng CSV, không phản ánh toàn bộ file.

Phụ lục nên gọi:

```text
target console log
```

hoặc tách:

- event log;
- telemetry CSV.

## 9. Coverage

Trong báo cáo, coverage được mô tả tỷ lệ cửa sổ có HR. Mã macro thực tế tính coverage có trọng số interval giữa decision event.

Hai cách gần nhau nếu stride đều 2 giây, nhưng không hoàn toàn giống khi:

- event thiếu;
- interval cuối khác;
- log delay;
- decision timestamp không đều.

Nên mô tả đúng implementation:

```text
tỷ lệ thời gian decision interval có HR hợp lệ
```

## 10. State power discrepancy

Nguồn mapping:

```text
263,35 / 283,11
```

Notebook output lưu:

```text
263,37 / 282,91
```

Chênh lệch nhỏ nhưng hội đồng có thể hỏi vì bảng và code không khớp.

Nên chạy lại notebook, xuất CSV nguồn, rồi cập nhật cả báo cáo và hình từ cùng artifact.

## 11. Random Forest so với MLP

RF:

```text
MAE 8,44; RMSE 12,89
```

MLP INT8 artifact:

```text
MAE 8,11; RMSE 12,61
```

Mức cải thiện:

- MAE khoảng 0,33 BPM;
- RMSE khoảng 0,28 BPM.

Không có confidence interval hoặc repeated group split để chứng minh khác biệt có ý nghĩa thống kê.

Nên trình bày lựa chọn MLP dựa trên:

- khả năng export INT8;
- runtime TFLM;
- footprint;
- accuracy không kém baseline.

## 12. `quality_ok` và HR consistency

Trong code:

```text
quality_ok = amplitude_ok AND periodic_ok AND hr_range_ok
```

`hr_consistent` được tính riêng.

Sparse telemetry `quality` chỉ phản ánh `quality_ok`, không phản ánh consistency/no-contact đầy đủ. Vì vậy một dòng `quality=1` chưa chắc output DSP được xuất.

## 13. No-contact trong HIGH

Khi HIGH và no-contact:

```cpp
good_windows = SCHED_GOOD_WINDOWS_TO_DOWN;
```

Sau cooldown/dwell, hệ thống có thể về NORMAL. Đây là quyết định hợp lý về năng lượng, nhưng cần giải thích vì tên `good_windows` không phản ánh đúng semantic no-contact.

## 14. Adaptive khởi động HIGH

Báo cáo có thể khiến người đọc nghĩ NORMAL là mặc định. Firmware adaptive hiện:

```text
initial_state = HIGH
```

Lý do có thể là warm-up/đảm bảo coverage ban đầu, nhưng code không ghi chú rõ. Nếu bị hỏi, cần xác nhận chủ ý thiết kế.

## 15. Energy estimate và peak power

`E_AI` dùng peak excess toàn burst, không phải power đo đúng lúc infer.

Nếu peak xuất hiện trong feature extraction, công thức có thể đánh giá cao AI. Vì vậy tỷ lệ 2,28-2,45% nhiều khả năng không phải under-estimate đơn giản.

Nên gọi:

```text
estimated AI-energy contribution under a peak-power assumption
```

## 16. Power tail

Tail được xác định bằng threshold:

```text
baseline + max(8 mW, 3 × robust noise)
```

và hai row yên tĩnh liên tiếp.

Đây là định nghĩa thuật toán, không phải ranh giới vật lý tuyệt đối của CPU. Kết quả phụ thuộc:

- baseline window 20;
- threshold 8 mW;
- sigma multiplier 3;
- settle count 2.

Nên có sensitivity analysis nếu muốn kết luận định lượng mạnh.

## 17. Những tuyên bố an toàn

Có thể nói:

- Hệ thống triển khai được scheduler hai state trên ESP32-S3.
- Hai state tạo miền công suất khác nhau.
- Adaptive nằm giữa hai fixed mode trên bộ log v6.
- MLP INT8 chạy được với latency vài trăm µs.
- Trong phương pháp ước lượng hiện tại, AI chiếm tỷ lệ nhỏ của burst.

## 18. Những tuyên bố nên tránh

Không nên nói:

- Thiết bị đo HR chính xác lâm sàng.
- MAE trên MAX30102 là 8,11 BPM.
- TinyML tiêu thụ chính xác 33 µJ.
- Scheduler tối ưu năng lượng.
- Adaptive tốt hơn tuyệt đối hai baseline.
- MLP tốt hơn RF có ý nghĩa thống kê.
- Toàn bộ pipeline Python và C++ tương đương.

## 19. Checklist trước khi chốt báo cáo

- [ ] Chốt source firmware đã tạo log cuối.
- [ ] Chốt model/scaler đã flash.
- [ ] So hash model.
- [ ] Đồng bộ LED current và sample averaging.
- [ ] Đồng bộ state-aware power.
- [ ] Mô tả macro v6 và micro v7 là hai protocol.
- [ ] Dùng từ “ước lượng” cho AI energy.
- [ ] Nêu rõ coverage không phải accuracy.
- [ ] Thêm pipeline mismatch vào giới hạn.
- [ ] Kiểm thử feature Python/C++ bằng golden vector.
