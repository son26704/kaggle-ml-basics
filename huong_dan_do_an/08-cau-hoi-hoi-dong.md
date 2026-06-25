# 08. Câu hỏi hội đồng và ý chính trả lời

Tài liệu chỉ đưa ý chính. Khi trả lời, nên theo cấu trúc:

```text
Kết luận ngắn -> cơ chế kỹ thuật -> số liệu -> giới hạn
```

## Nhóm A. Bài toán và đóng góp

### 1. Bài toán cốt lõi là gì?

- Cân bằng HR coverage và năng lượng.
- Không chạy pipeline mạnh liên tục.
- Điều phối theo chất lượng PPG.

### 2. Đóng góp khác gì chỉ làm mô hình dự đoán HR?

- Có prototype phần cứng.
- Có scheduler runtime.
- Có Fast/Slow Path.
- Có hệ đo năng lượng.
- Có phân tích macro và burst.

### 3. Tính mới nằm ở đâu?

- Tích hợp quality-aware scheduling với PPG-TinyML trên prototype.
- Đánh giá trade-off toàn node.
- Chỉ ra bottleneck năng lượng nằm ngoài Invoke.
- Tránh tuyên bố mới ở cấp thuật toán ML nếu chưa so với literature rộng.

### 4. Vì sao Adaptive nằm giữa hai baseline lại được coi là thành công?

- Mục tiêu là điểm vận hành trung gian.
- Fixed Normal tối thiểu power, Fixed High tối đa coverage.
- Adaptive không thể đồng thời vượt cả hai nếu không thay đổi frontier.

## Nhóm B. PPG và cảm biến

### 5. PPG đo trực tiếp nhịp tim không?

- Đo biến thiên quang liên quan thể tích máu.
- HR được suy ra từ tính tuần hoàn.
- Không đo điện tim trực tiếp như ECG.

### 6. Vì sao dùng kênh IR?

- Thực nghiệm thấy ổn định hơn.
- MAX30102 cung cấp RED/IR.
- Pipeline hiện dùng IR; cần tránh khẳng định IR luôn tốt hơn trong mọi tình huống.

### 7. Vì sao motion artifact nguy hiểm?

- Tạo dao động không do tim.
- Có thể biên độ lớn và tuần hoàn giả.
- Làm peak/PSD/autocorrelation sai.

### 8. Vì sao không chỉ đặt ngưỡng biên độ?

- Không tiếp xúc/di chuyển có thể tạo biên độ rất lớn.
- Cần vùng Goldilocks và periodicity/consistency.

### 9. 50 sps và 100 sps khác gì?

- 100 sps nhiều mẫu hơn, tải sensor/I2C/CPU cao hơn.
- 50 sps đủ cho HR band cơ bản.
- Firmware dùng 50 ở NORMAL, 100 ở HIGH.

### 10. Tại sao resample về 64 Hz?

- Model được huấn luyện trên PPG-DaLiA 64 Hz.
- Giữ input 512 mẫu.
- Tạo interface cố định giữa sensor profile và feature pipeline.

### 11. Resampling có gây mất thông tin?

- Có thể.
- HR band thấp hơn Nyquist 32 Hz rất nhiều.
- Nội suy tuyến tính đơn giản; chưa phải resampler chống alias chuẩn.

## Nhóm C. DSP và quality gate

### 12. `std_hp` và `ptp_hp` là gì?

- Tính trên tín hiệu sau trừ nền chậm.
- std đo mức dao động.
- ptp đo biên độ max-min.

### 13. Autocorrelation dùng để làm gì?

- Đo tín hiệu lặp lại theo chu kỳ.
- Lag tốt nhất đổi thành HR.
- Score cao cho thấy periodicity rõ.

### 14. Vì sao so peak HR với autocorrelation HR?

- Hai estimator độc lập tương đối.
- Chênh lớn gợi ý peak giả hoặc tín hiệu không ổn định.

### 15. Difficulty proxy có phải AI không?

- Không.
- Heuristic `1 - ac_best`, hoặc 1 nếu amplitude fail.

### 16. Vì sao cần 4 bad và 5 good?

- Hysteresis.
- Tránh một cửa sổ nhiễu làm đổi state.
- Đi xuống thận trọng hơn để bảo đảm ổn định.

### 17. Cooldown và dwell khác gì?

- Cooldown tính theo số cửa sổ sau chuyển.
- Dwell tính theo thời gian tối thiểu giữ state.

### 18. Vì sao no-contact lại quay về NORMAL?

- Không có tín hiệu hữu ích thì pipeline mạnh không đem lại lợi ích.
- Tiết kiệm năng lượng.

## Nhóm D. AI và dữ liệu

### 19. PPG-DaLiA gồm gì?

- BVP cổ tay, activity và HR reference.
- Nhiều subject/hoạt động.
- Dùng để đánh giá HR trong điều kiện đời thực.

### 20. Vì sao chia theo subject?

- Tránh leakage giữa cửa sổ cùng người.
- Đánh giá tổng quát sang người chưa thấy.

### 21. Tại sao MLP thay vì CNN?

- Input chỉ 16 feature.
- Dense đủ phù hợp.
- Operator đơn giản.
- RAM/latency nhỏ.
- CNN hợp hơn nếu dùng raw waveform.

### 22. Tại sao dùng feature thủ công?

- Giảm kích thước input/model.
- Dễ diễn giải.
- Phù hợp MCU.
- Đánh đổi là DSP feature có thể tốn năng lượng và tạo mismatch.

### 23. Tại sao Huber loss?

- Bền hơn MSE trước outlier HR.
- Vẫn mượt để tối ưu.

### 24. Dropout có chạy trên ESP32 không?

- Không.
- Dropout chỉ dùng khi train.
- Model inference không random drop neuron.

### 25. StandardScaler làm gì?

- Đưa feature về scale tương đối đồng đều.
- Mean/scale fit trên train.
- Firmware phải dùng đúng hằng số.

### 26. Lượng tử hóa INT8 là gì?

- Ánh xạ float sang int8 bằng scale/zero-point.
- Giảm flash/RAM và thường tăng tốc.
- Có thể gây quantization error.

### 27. Vì sao INT8 hơi tốt hơn FP32?

- Sai khác rất nhỏ.
- Nhiễu lượng tử hóa tình cờ giảm error trên test.
- Không kết luận INT8 vốn chính xác hơn.

### 28. MLP tốt hơn RF có đáng kể không?

- Chênh nhỏ.
- Chưa có kiểm định thống kê.
- Lợi thế chính là deployability trên TFLM.

### 29. MAE 8,11 BPM có tốt không?

- Phụ thuộc use case.
- Chưa đủ để gọi clinical grade.
- Là offline trên PPG-DaLiA.
- Không phải MAE prototype MAX30102.

### 30. Domain shift là gì?

- Train trên sensor/vị trí/phân bố khác deployment.
- PPG-DaLiA wrist BVP khác MAX30102 prototype.
- Cần validation/calibration trên phần cứng thật.

### 31. Tiền xử lý Python và firmware có giống nhau không?

- Cùng mục tiêu và 16 feature.
- Implementation chưa tương đương tuyệt đối.
- Đây là giới hạn cần golden-vector validation.

## Nhóm E. TinyML runtime

### 32. TensorFlow Lite Micro khác TensorFlow Lite thế nào?

- Dành cho MCU, không OS.
- Arena tĩnh.
- Chỉ đăng ký operator cần thiết.
- Không file system/dynamic runtime đầy đủ.

### 33. Tensor arena là gì?

- RAM làm việc cho tensor và activation.
- Không phải model flash.
- Firmware cấp 16 KB, runtime dùng khoảng 1,5 KB trong log.

### 34. Tại sao resolver chỉ có FullyConnected?

- Model sau convert chỉ cần operator Dense/FullyConnected.
- Giảm code footprint.

### 35. Mô hình nằm ở đâu?

- `.tflite` được chuyển thành mảng byte C.
- Link vào firmware flash.
- Interpreter đọc trực tiếp model.

### 36. Vì sao đo Invoke bằng `esp_timer_get_time()`?

- Độ phân giải microsecond.
- Đo trực tiếp khoảng gọi runtime.
- Không đo feature extraction.

## Nhóm F. Hệ nhúng và FreeRTOS

### 37. Vì sao có main loop và AI task riêng?

- Main loop thu mẫu liên tục.
- AI task xử lý khi đủ cửa sổ.
- Giảm việc block đọc FIFO.

### 38. Ring buffer là gì?

- Bộ đệm vòng dung lượng cố định.
- Giữ cửa sổ mới nhất mà không dịch toàn mảng mỗi mẫu.

### 39. Vì sao dùng task notification thay queue?

- Chỉ cần báo có việc.
- Dữ liệu nằm sẵn trong ring buffer.
- Nhẹ hơn gửi 400/800 mẫu qua queue.

### 40. Có nguy cơ race condition không?

- Có vì hai task dùng chung ring/state/telemetry.
- Firmware dùng critical section.
- Critical section dài khi snapshot copy cả cửa sổ có thể ảnh hưởng latency; cần cân nhắc.

### 41. Tại sao đổi state phải xóa ring buffer?

- Mẫu cũ và mới có sample rate khác.
- Không thể trộn trực tiếp.
- Đổi lại có khoảng warm-up 8 giây.

### 42. Recovery hoạt động thế nào?

- Lỗi I2C liên tiếp hoặc không có mẫu.
- Probe và áp lại profile.
- reset EMA;
- freeze scheduler vài cửa sổ.

## Nhóm G. Đo năng lượng

### 43. Vì sao đo ở 5 V input?

- Đo toàn node, gồm board và sensor.
- Phù hợp mục tiêu system-level.
- Bao gồm tổn hao regulator.

### 44. INA219 đo công suất như thế nào?

- Đo shunt voltage và bus voltage.
- Dùng calibration để suy dòng/power.

### 45. Vì sao dùng DAQ riêng?

- Giảm overhead đo trên target.
- Ghi power độc lập.
- Nhận GPIO sync.

### 46. Vì sao DAQ chỉ khoảng 3,3 ms/mẫu?

- I2C;
- conversion;
- format float;
- UART 115200;
- delay 1 ms.

### 47. Tại sao không đo trực tiếp Invoke bằng GPIO?

- Invoke 0,38 ms;
- DAQ sample 3,3 ms;
- nhiều xung bị bỏ lỡ.

### 48. `E_AI` được tính thế nào?

- peak excess power × exact Invoke time.
- Là ước lượng, không phải đo trực tiếp.

### 49. Vì sao cần power tail?

- Công suất không về baseline ngay khi GPIO hạ.
- CPU/cache/peripheral/regulator có thể còn trạng thái cao.
- Bỏ tail sẽ underestimate.

### 50. Kết luận 2,28-2,45% đáng tin đến đâu?

- Định tính tương đối đáng tin: AI nhỏ so tổng burst.
- Con số tuyệt đối phụ thuộc giả định peak, baseline, sampling.
- Cần thiết bị nhanh hơn để xác nhận.

## Nhóm H. Kết quả và phương pháp nghiên cứu

### 51. Vì sao không so accuracy giữa ba mode?

- Prototype không có HR ground truth đồng bộ.
- Chỉ có coverage.
- Đây là giới hạn lớn.

### 52. Coverage có thể bị “gaming” không?

- Có: luôn xuất một con số sẽ đạt 100%.
- Phải đi kèm accuracy/quality.
- Trong đồ án coverage chỉ là capability metric.

### 53. Số run có đủ không?

- Còn ít.
- Phù hợp proof-of-concept.
- Chưa đủ kết luận tổng quát.

### 54. Có kiểm định thống kê không?

- Chưa.
- Nên thêm repeated trials, variance, CI và paired comparison.

### 55. Thí nghiệm có công bằng không?

- Cần cùng nguồn, cảm biến, đối tượng, điều kiện và thời lượng.
- Log hiện có nhiều run nhưng protocol cần ghi rõ.
- Nên randomize thứ tự mode.

### 56. Tại sao macro và micro power khác?

- Khác phiên bản log/hệ đo.
- Macro v6 target tự đo.
- Micro v7 DAQ riêng.
- Chỉ so trong cùng protocol.

### 57. Adaptive có tiết kiệm pin bao nhiêu?

- So Fixed High khoảng 4,79% power trong bộ log v6.
- Battery life thực phụ thuộc pin, regulator, duty cycle và sleep.
- Không suy trực tiếp thành ngày sử dụng nếu chưa đo.

### 58. Tối ưu tiếp ở đâu?

- Đồng bộ Python/C++ feature.
- Giảm FFT/feature cost.
- Giảm tail.
- adaptive acquisition.
- sensor/MCU low-power mode.
- hệ đo nhanh hơn.

## Nhóm I. Câu hỏi phản biện mạnh

### 59. Nếu MLP train trên wrist nhưng deploy fingertip, kết quả có ý nghĩa gì?

- Offline chứng minh feasibility trên dataset chuẩn.
- Deployment hiện là proof-of-concept.
- Chưa chứng minh accuracy trên fingertip.
- Cần dataset prototype có ECG/reference.

### 60. Nếu scaler firmware khác artifact, số liệu MAE còn dùng được không?

- Chỉ dùng được nếu xác minh model/scaler firmware thuộc artifact đánh giá.
- Hiện cần version reconciliation.
- Không nên né điểm này.

### 61. Tại sao báo cáo ghi LED 0x24 nhưng code 0x18?

- Đây là inconsistency cần chốt source tạo log.
- Trả lời bằng phiên bản/commit thật, không đoán.

### 62. Tại sao gọi residual là DSP energy?

- Tên rút gọn.
- Thực chất gồm DSP, feature, tail và overhead.
- Nên gọi DSP/feature/tail residual.

### 63. Peak power nhân thời gian Invoke có cơ sở gì?

- DAQ không resolve được pulse.
- Dùng peak excess làm giả định upper-bound đơn giản.
- Mục tiêu phân biệt cấp độ lớn, không metrology chính xác.

### 64. Scheduler có “thích nghi thông minh” không?

- Rule-based, không học online.
- Thích nghi theo feedback chất lượng.
- Không nên gọi reinforcement learning hoặc AI scheduler.

### 65. Đồ án thuộc AI hay chủ yếu hệ nhúng?

- Là hệ thống AIoT.
- AI cung cấp Slow Path.
- Đóng góp mạnh ở tích hợp, scheduling và đo hệ thống.
- Không phải nghiên cứu kiến trúc neural network mới.

## Mười câu cần luyện trước tiên

1. Bài toán cốt lõi và đóng góp.
2. Luồng dữ liệu end-to-end.
3. NORMAL khác HIGH thế nào.
4. Quality gate dùng gì.
5. Vì sao chia subject.
6. Vì sao MLP INT8.
7. Coverage khác accuracy.
8. DAQ đo gì và giới hạn.
9. Vì sao TinyML chỉ khoảng 2%.
10. Ba giới hạn lớn nhất.
