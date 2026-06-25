# 06. Phân tích macro-level và micro-level

## Phần A. Macro-level

File:

- `ppg_hr_macro_analysis.ipynb`
- `ppg_hr_macro_analysis_lib.py`

## 1. Macro-level trả lời câu hỏi gì?

Nó so sánh toàn phiên:

- Fixed Normal;
- Adaptive;
- Fixed High.

Hai chỉ số chính:

- average power;
- HR coverage.

Nó không phân tách từng burst.

## 2. Nguồn log thật sự của notebook macro

Notebook v6 đọc:

```text
log/pgg_hr_log_v6/
```

Các log này đến từ phiên firmware cũ, khi target tự đọc INA219 và dòng sparse gồm:

```text
timestamp,state,profile,quality,diff,red,ir,bus_v,current_ma,power_mw
```

Vì vậy kết quả macro hiện tại không được tính từ cặp `target.csv`/`daq.csv` v7.

## 3. Parse log

Thư viện dùng regex nhận diện:

- telemetry row;
- `DSP_HR`;
- `AI_ASSIST_HR`;
- `DSP_HOLD`;
- `NO_CONTACT`;
- `Low quality`;
- state transition.

Một file `.csv` ở đây thực chất là console log hỗn hợp.

## 4. Timeline quyết định

`build_decision_timeline()` lấy union timestamp của:

- các output HR;
- các dropout.

Nếu tại cùng timestamp có AI và DSP, ưu tiên `AI_ASSIST_HR`.

Mỗi event được gán interval đến event tiếp theo:

```text
interval_i = timestamp_(i+1) - timestamp_i
```

Event cuối kéo dài đến `end_ms` của phiên.

## 5. HR coverage

```text
covered_s = tổng interval có chosen HR
dropped_s = tổng interval không có HR
coverage = covered_s / (covered_s + dropped_s)
```

Đây là coverage có trọng số thời gian, không đơn thuần số dòng HR / số cửa sổ.

### Ví dụ

Ba quyết định:

```text
t=10 s: HR hợp lệ
t=12 s: dropout
t=18 s: HR hợp lệ
end=20 s
```

Interval:

- 10-12: covered 2 s.
- 12-18: dropped 6 s.
- 18-20: covered 2 s.

Coverage:

```text
4 / 10 = 40%
```

## 6. Average power

`time_weighted_mean()`:

1. Sort telemetry.
2. Mỗi power row giữ trọng số đến timestamp row sau.
3. Row cuối kéo dài đến end.
4. Dùng weighted average.

```text
P_avg = Σ P_i Δt_i / Σ Δt_i
```

Cách này tốt hơn mean thường khi khoảng lấy mẫu không đều.

## 7. State occupancy

Từ log chuyển state, `build_state_segments()` tạo các đoạn state theo thời gian rồi tính:

```text
state_0_pct
state_1_pct
```

Adaptive v6 hiện khoảng:

```text
state 0 ≈ 50,25%
state 1 ≈ 49,75%
```

## 8. Gộp nhiều run

Mode-level:

- average power được gộp có trọng số theo run duration;
- coverage được gộp bằng tổng covered / tổng coverage time;
- không chỉ lấy trung bình đơn giản phần trăm từng run.

## 9. Kết quả macro

```text
Fixed Normal: 261,78 mW; coverage 46,23%
Adaptive:     273,21 mW; coverage 65,81%
Fixed High:   286,94 mW; coverage 89,31%
```

Tính:

```text
Adaptive tăng coverage so Fixed Normal:
65,81 - 46,23 = 19,58 điểm phần trăm

Adaptive tiết kiệm so Fixed High:
(286,94 - 273,21) / 286,94 × 100 ≈ 4,79%
```

## 10. State-aware power

Notebook lọc telemetry adaptive theo state rồi lấy mean:

Output notebook hiện tại:

```text
state 0 = 263,37 mW
state 1 = 282,91 mW
```

Tài liệu mapping/báo cáo lại dùng:

```text
263,35 mW
283,11 mW
```

Cần thống nhất nguồn trước khi bảo vệ.

## 11. Giới hạn macro

1. Dữ liệu v6 target tự đo power, khác kiến trúc dual-MCU cuối.
2. Coverage không phải accuracy.
3. Số run ít: Adaptive 4, Fixed High 2, Fixed Normal 2.
4. Điều kiện giữa run có thể không hoàn toàn giống nhau.
5. Không có confidence interval.
6. Không randomize thứ tự thí nghiệm được ghi rõ.
7. Pin/nguồn/nhiệt độ/cách đặt tay có thể ảnh hưởng.

## Phần B. Micro-level

File:

- `ppg_hr_micro_power_analysis.ipynb`
- `ppg_hr_micro_analysis_lib.py`

## 12. Micro-level trả lời câu hỏi gì?

Khi Slow Path chạy, năng lượng dư nằm ở:

- feature/DSP/tail;
- hay `TinyML Invoke()`?

## 13. Dữ liệu đầu vào

Mỗi run v7:

```text
run_dir/
    target.csv
    daq.csv
```

`target.csv` cung cấp:

- mode;
- state;
- loại cửa sổ;
- metric;
- `invoke_time_us`.

`daq.csv` cung cấp:

- timestamp;
- power;
- feature GPIO;
- infer GPIO.

## 14. Parse target

Parser tự nhận encoding:

- nếu có UTF-16 BOM thì decode UTF-16;
- nếu không decode UTF-8 và bỏ byte lỗi.

Sau đó regex nhận:

- mode;
- telemetry;
- state transition;
- DSP_HOLD;
- DSP_HR;
- low quality;
- no contact;
- AI assist;
- Invoke time.

`invoke_time_us` được gắn vào window gần nhất đã parse.

## 15. Parse DAQ

Pandas đọc 6 cột bằng tên truyền sẵn. Header nếu có sẽ biến thành NaN và bị drop.

```text
active = feature_pin_state > 0 OR infer_pin_state > 0
```

Khoảng mẫu:

```text
dt[i] = timestamp[i+1] - timestamp[i]
```

Row cuối dùng median dt.

## 16. Phát hiện burst

Lấy index mọi row active.

Hai active row thuộc cùng burst nếu:

```text
idx_current - idx_previous <= 3
```

Điều này cho phép giữa feature và infer có tối đa vài row inactive mà vẫn coi là một burst.

`max_gap_rows=3` tương ứng khoảng 10 ms với dt 3,3 ms. Đây là heuristic.

## 17. Ghép target và DAQ

Với Adaptive và Fixed High:

```python
matched_windows = windows[state == 1]
```

Burst thứ `i` ghép với window HIGH thứ `i`.

Biến:

```text
alignment_ok = số window HIGH == số burst
```

Nếu bằng nhau, đây là sanity check tốt nhưng chưa chứng minh timestamp khớp từng cặp.

## 18. Baseline

Với mỗi burst:

1. Lấy tối đa 20 row trước seed.
2. Chỉ giữ row inactive.
3. Nếu không có, dùng tối đa 50 global quiet row.
4. Nếu vẫn không có, dùng median toàn run.

Baseline là median, bền hơn mean trước outlier.

## 19. Ước lượng noise

```text
MAD = median(|P - median(P)|)
noise = 1,4826 × MAD
```

Ngưỡng settle:

```text
baseline + max(8 mW, 3 × noise)
```

Tức công suất phải xuống đủ gần baseline, không chỉ GPIO về 0.

## 20. Mở rộng power tail

Từ cuối seed, tiếp tục đi tới khi gặp hai row liên tiếp:

- inactive;
- và power không vượt settle threshold.

Vùng tích phân vì vậy bao gồm tail.

Code còn có thể mở rộng ngược đầu burst nếu row trước inactive nhưng power đã cao hơn threshold.

## 21. Tổng năng lượng burst

```text
P_excess[i] = max(P[i] - baseline, 0)
E_total = Σ P_excess[i] × dt[i] / 1000
```

Đơn vị đầu ra µJ.

Clipping ở 0 bỏ phần power thấp hơn baseline, tránh negative energy.

## 22. Feature/infer width quan sát

```text
feature_pin_width_us =
    Σ dt của row feature=1

infer_pin_width_us =
    Σ dt của row infer=1
```

Đây là độ rộng theo sampling DAQ, không phải độ rộng GPIO chính xác.

## 23. Ước lượng AI energy

Sau khi ghép với target:

```text
E_AI = peak_excess_power_mW × invoke_time_us / 1000
```

### Giả định

Trong toàn bộ Invoke, excess power bằng excess power cực đại của burst.

Đây có xu hướng là upper-bound hoặc ít nhất là ước lượng bảo thủ, vì peak burst có thể đến từ feature extraction chứ không phải Invoke.

Không được gọi đây là “đo trực tiếp năng lượng TinyML”.

## 24. DSP/tail energy

```text
E_DSP = max(0, E_total - E_AI)
```

Thực tế phần này gộp:

- DSP;
- feature extraction;
- memory/cache;
- sensor/CPU state;
- power tail;
- sai số baseline;
- mọi overhead khác.

Tên chính xác hơn là “non-AI residual energy”.

## 25. Kết quả micro

### Adaptive HIGH

```text
38 burst
baseline khoảng 253 mW
dt median 3299 µs
Invoke mean 380,46 µs
feature observed 7200,21 µs
tail mean 18583,05 µs
integration 28994,95 µs
E_total mean 1460,10 µJ
E_AI mean 33,35 µJ
weighted AI fraction 2,2839%
```

### Fixed High

```text
35 burst
baseline khoảng 254 mW
dt median 3298 µs
Invoke mean 373,94 µs
feature observed 6961,80 µs
tail mean 16574,89 µs
integration 25609,89 µs
E_total mean 1393,12 µJ
E_AI mean 34,08 µJ
weighted AI fraction 2,4464%
```

## 26. Mean fraction và weighted fraction

Artifact có cả:

- mean của fraction từng burst;
- tỷ lệ tổng năng lượng AI / tổng năng lượng burst.

Adaptive:

```text
mean per-burst fraction ≈ 2,2108%
weighted fraction ≈ 2,2839%
```

Báo cáo dùng weighted fraction 2,28%.

## 27. Vì sao TinyML chỉ chiếm ít?

Invoke khoảng 0,38 ms. Toàn burst khoảng 26-29 ms.

Tỷ lệ thời gian thô:

```text
0,38 / 29 ≈ 1,3%
```

Nếu Invoke có power cao hơn các pha khác, tỷ lệ năng lượng có thể lên khoảng 2-2,5%.

Feature extraction, FFT và tail kéo dài hơn nhiều nên chi phối tổng burst.

## 28. Điều kết luận được

- Slow Path tạo burst công suất đo được.
- Tổng burst lớn hơn rất nhiều ước lượng riêng Invoke.
- Tối ưu DSP/tail có tiềm năng lớn hơn chỉ tối ưu model latency.

## 29. Điều chưa kết luận được

- Chính xác TinyML tiêu thụ 33,35 µJ trong mọi điều kiện.
- DSP riêng tiêu thụ chính xác 1426,75 µJ.
- Power peak thuộc về Invoke.
- Kết quả tổng quát sang board, nguồn hoặc model khác.

## 30. Cách giải thích công thức trước hội đồng

Ý chính:

1. DAQ quá chậm để resolve xung Invoke.
2. Tổng burst vẫn đo được bằng timestamp và power.
3. Firmware đo chính xác latency Invoke.
4. Dùng peak excess power nhân latency để ước lượng phần AI.
5. Phần còn lại là residual.
6. Vì AI chỉ khoảng 2,3-2,45%, kết luận định tính “AI không chi phối” khá vững; giá trị tuyệt đối vẫn có sai số.
