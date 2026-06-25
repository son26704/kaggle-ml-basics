# 01. Nền tảng từ đầu

## 1. Đồ án thuộc lĩnh vực nào?

Đồ án nằm ở giao điểm của ba lĩnh vực.

### 1.1 AIoT

AIoT là sự kết hợp giữa:

- IoT: thiết bị vật lý có cảm biến, vi điều khiển và khả năng thu thập dữ liệu.
- AI: thuật toán học máy biến dữ liệu cảm biến thành thông tin có ích.

Trong đồ án:

- MAX30102 tạo dữ liệu PPG.
- ESP32-S3 đọc dữ liệu và xử lý tại chỗ.
- Mô hình MLP dự đoán nhịp tim.
- Scheduler quyết định khi nào nên dùng mức xử lý mạnh.

Thiết bị không cần gửi toàn bộ PPG lên máy chủ. Đây là xử lý tại biên, hay edge computing.

### 1.2 Hệ nhúng

Hệ nhúng là hệ thống máy tính chuyên dụng nằm trong một sản phẩm. Nó bị giới hạn về:

- RAM.
- flash.
- tốc độ CPU.
- năng lượng.
- giao tiếp phần cứng.
- khả năng quan sát và gỡ lỗi.

ESP32-S3 trong đồ án phải đồng thời:

- giao tiếp I2C với MAX30102;
- đọc FIFO cảm biến;
- lưu cửa sổ PPG;
- chạy DSP;
- chạy scheduler;
- chạy TensorFlow Lite Micro;
- xuất log UART;
- phát GPIO đồng bộ cho DAQ.

Do đó, một mô hình tốt trên máy tính chưa chắc chạy tốt trên vi điều khiển.

### 1.3 Trí tuệ nhân tạo ứng dụng

AI ứng dụng quan tâm đến toàn bộ chuỗi:

1. Dữ liệu có đại diện cho bài toán không?
2. Nhãn có đúng không?
3. Chia train/test có rò rỉ dữ liệu không?
4. Mô hình có tổng quát sang người mới không?
5. Tiền xử lý offline có giống firmware không?
6. Mô hình sau lượng tử hóa còn chính xác không?
7. Mô hình có thực sự cải thiện hệ thống hay chỉ cải thiện một chỉ số offline?

Đồ án dùng AI như một khối hỗ trợ trong `Slow Path`, không thay thế toàn bộ DSP.

## 2. Nhịp tim và BPM

Nhịp tim là số lần tim co bóp trong một phút. Đơn vị thường dùng là BPM, viết tắt của beats per minute.

Nếu khoảng thời gian giữa hai nhịp liên tiếp là `T` giây:

```text
HR = 60 / T
```

Ví dụ, hai nhịp cách nhau 0,8 giây:

```text
HR = 60 / 0,8 = 75 BPM
```

Đây là cơ sở của phương pháp phát hiện đỉnh: tìm các đỉnh tuần hoàn trên PPG, đo khoảng cách giữa đỉnh, rồi đổi sang BPM.

## 3. PPG là gì?

PPG, photoplethysmography, là phương pháp quang học quan sát sự thay đổi thể tích máu trong mô.

Một cảm biến PPG cơ bản có:

- LED chiếu ánh sáng vào mô.
- photodiode nhận ánh sáng phản xạ hoặc truyền qua.
- mạch khuếch đại và ADC biến tín hiệu quang thành số.

Khi tim bơm máu:

1. lượng máu tại vùng đo thay đổi;
2. mức hấp thụ/phản xạ ánh sáng thay đổi;
3. photodiode tạo dòng điện thay đổi;
4. ADC tạo chuỗi số;
5. chuỗi số chứa thành phần tuần hoàn liên quan đến nhịp tim.

### 3.1 Thành phần DC và AC

PPG thô thường gồm:

- DC: mức nền lớn do mô, da, vị trí cảm biến, ánh sáng môi trường và tiếp xúc.
- AC: dao động nhỏ hơn liên quan đến thay đổi thể tích máu theo nhịp tim.

Mục tiêu xử lý tín hiệu là giảm ảnh hưởng DC và giữ thành phần AC hữu ích.

### 3.2 Vì sao PPG dễ nhiễu?

PPG rất nhạy với:

- ngón tay hoặc cổ tay di chuyển;
- lực ép thay đổi;
- cảm biến trượt;
- ánh sáng môi trường;
- tưới máu ngoại vi yếu;
- LED quá yếu;
- LED quá mạnh gây bão hòa ADC;
- dây và nguồn không ổn định.

Nhiễu chuyển động có thể tạo dao động lớn hơn cả tín hiệu tim. Vì vậy, biên độ lớn không đồng nghĩa chất lượng tốt.

## 4. MAX30102 là gì?

MAX30102 là cảm biến tích hợp cho PPG và pulse oximetry. Nó có:

- LED đỏ;
- LED hồng ngoại IR;
- photodiode;
- ADC;
- FIFO;
- giao tiếp I2C;
- thanh ghi cấu hình tần số lấy mẫu, độ rộng xung LED, dòng LED và chế độ đo.

Firmware của đồ án đọc cả RED và IR nhưng chỉ đưa IR vào pipeline chính.

### 4.1 FIFO

FIFO là vùng đệm nằm trong cảm biến. MAX30102 tự lấy mẫu và đẩy mẫu vào FIFO. ESP32 không cần đọc đúng tại từng thời điểm ADC chuyển đổi; nó có thể hỏi số mẫu đang chờ rồi đọc lần lượt.

Nếu ESP32 đọc quá chậm, FIFO có thể tràn. Firmware kiểm tra:

- con trỏ ghi;
- con trỏ đọc;
- bộ đếm overflow.

### 4.2 Tần số lấy mẫu

Tần số 50 sps nghĩa là khoảng 50 mẫu mỗi giây. Tần số 100 sps nghĩa là khoảng 100 mẫu mỗi giây.

Trong firmware hiện tại:

- `NORMAL`: profile 50 sps.
- `HIGH`: profile 100 sps.

Một cửa sổ 8 giây tương ứng:

- 400 mẫu ở 50 sps.
- 800 mẫu ở 100 sps.

Sau đó cả hai được nội suy về 512 mẫu, tức biểu diễn 8 giây ở 64 Hz, để khớp pipeline mô hình.

## 5. ESP32 và ESP32-S3

ESP32 là họ vi điều khiển của Espressif. ESP32-S3 là biến thể có tài nguyên và tập lệnh phù hợp hơn cho một số tác vụ xử lý tín hiệu/AI.

Trong hệ thống:

- ESP32-S3 là target node: đối tượng cần đánh giá.
- ESP32 thường là DAQ node: thiết bị đo công suất của target.

Hai node tách rời nhằm tránh việc target tự gánh toàn bộ chi phí đo và làm sai lệch phép đo.

## 6. I2C là gì?

I2C là bus nối tiếp đồng bộ thường dùng để giao tiếp cảm biến. Hai dây chính:

- SDA: dữ liệu.
- SCL: clock.

Mỗi thiết bị có địa chỉ:

- MAX30102: `0x57`.
- INA219: `0x40`.

ESP32 là master, chủ động đọc/ghi thanh ghi của cảm biến.

Pull-up trên SDA/SCL là cần thiết vì I2C dùng kiểu ngõ ra open-drain. Firmware bật pull-up nội, nhưng trong phần cứng thực tế thường vẫn nên có điện trở pull-up phù hợp trên module.

## 7. UART và log

UART truyền chuỗi ký tự giữa ESP32 và máy tính. Baud rate 115200 nghĩa là khoảng 115200 bit mỗi giây, không phải 115200 byte mỗi giây.

Một byte UART thường cần khoảng 10 bit gồm start, 8 data và stop. Do đó thông lượng lý tưởng xấp xỉ:

```text
115200 / 10 ≈ 11520 byte/giây
```

Việc `printf` một dòng dài có thể chặn task vài mili-giây. Đây là lý do DAQ thực tế chỉ đạt chu kỳ khoảng 3,3 ms dù có thêm delay 1 ms.

## 8. INA219 đo gì?

INA219 đo:

- điện áp bus;
- điện áp trên điện trở shunt;
- dòng điện suy ra từ shunt và calibration;
- công suất.

Trong cấu hình đồ án, đường 5 V đi qua INA219 trước khi cấp cho target. Vì vậy giá trị đo đại diện cho công suất đầu vào của:

- board ESP32-S3;
- MAX30102;
- regulator trên board;
- CPU, RAM và ngoại vi đang hoạt động.

Nó không chỉ đo riêng CPU hay riêng TinyML.

## 9. Công suất và năng lượng

Công suất là tốc độ tiêu thụ năng lượng:

```text
P = V × I
```

Nếu `V` tính bằng volt và `I` tính bằng milliampere thì `P` có đơn vị milliwatt.

Năng lượng là tích phân công suất theo thời gian:

```text
E = ∫ P(t) dt
```

Với dữ liệu rời rạc:

```text
E ≈ Σ P_i × Δt_i
```

Nếu `P` là mW và `Δt` là µs:

```text
mW × µs / 1000 = µJ
```

Đây là lý do mã micro-level dùng:

```python
excess_power_mw * interval_us / 1000.0
```

## 10. DSP là gì?

DSP trong đồ án là các phép xử lý số trên chuỗi PPG:

- loại xu hướng nền;
- lọc thông dải;
- chuẩn hóa;
- tìm đỉnh;
- tự tương quan;
- FFT và PSD;
- tính đặc trưng thống kê.

DSP không nhất thiết là một chip riêng. Ở đây, đó là thuật toán chạy trên ESP32-S3.

## 11. Cửa sổ và stride

Không xử lý từng mẫu độc lập. Hệ thống gom PPG thành cửa sổ 8 giây.

Stride 2 giây nghĩa là cứ 2 giây tạo một lần đánh giá mới. Hai cửa sổ liên tiếp chồng lấn 6 giây.

Lợi ích:

- có đủ chu kỳ tim để ước lượng ổn định;
- cập nhật kết quả thường xuyên hơn độ dài cửa sổ.

Đánh đổi:

- cửa sổ dài tăng độ trễ;
- cửa sổ chồng lấn làm nhiều mẫu được xử lý lại;
- các điểm đánh giá liên tiếp không độc lập thống kê.

## 12. Fast Path và Slow Path

### Fast Path

Fast Path chỉ làm các phép cần thiết để:

- đánh giá chất lượng;
- tìm đỉnh cơ bản;
- tính autocorrelation;
- xuất HR DSP nếu đủ tin cậy.

Nó không trích đầy đủ 16 đặc trưng và không gọi mô hình.

### Slow Path

Slow Path:

- trích đầy đủ 16 đặc trưng;
- chuẩn hóa theo scaler huấn luyện;
- lượng tử hóa đầu vào;
- gọi MLP INT8;
- giải lượng tử hóa đầu ra;
- làm mượt HR.

## 13. Scheduler là gì?

Scheduler ở đây không phải scheduler của hệ điều hành. Nó là bộ điều phối cấp ứng dụng quyết định trạng thái:

```text
NORMAL <-> HIGH
```

Nó dùng chất lượng hiện tại và lịch sử nhiều cửa sổ. Các bộ đếm, cooldown và dwell time tránh chuyển trạng thái liên tục do một nhiễu ngắn.

## 14. Machine learning và MLP

MLP là mạng nơ-ron truyền thẳng gồm:

- 16 giá trị đầu vào;
- nhiều lớp Dense ẩn dùng ReLU;
- một đầu ra tuyến tính dự đoán HR đã chuẩn hóa.

Trong notebook hiện tại, cấu hình được chọn là:

```text
16 -> 192 -> 128 -> 64 -> 1
```

Trong huấn luyện có Dropout và L2. Khi suy luận, Dropout không hoạt động.

## 15. Chuẩn hóa và lượng tử hóa

### 15.1 StandardScaler

Mỗi đặc trưng được chuẩn hóa:

```text
x_scaled = (x - mean_train) / std_train
```

Mean và scale phải lấy từ tập train, không được tính lại trên test hoặc trên từng cửa sổ firmware.

### 15.2 Chuẩn hóa nhãn

HR cũng được chuẩn hóa khi huấn luyện:

```text
y_norm = (HR - HR_mean) / HR_std
```

Sau suy luận:

```text
HR = y_norm × HR_std + HR_mean
```

### 15.3 INT8

Số thực được ánh xạ sang số nguyên 8 bit:

```text
q = round(x / scale + zero_point)
```

Giải lượng tử hóa:

```text
x ≈ (q - zero_point) × scale
```

INT8 giảm kích thước và thường tăng tốc trên vi điều khiển, nhưng yêu cầu scaler, thứ tự đặc trưng và tham số lượng tử hóa khớp tuyệt đối.

## 16. MAE, RMSE và R²

### MAE

```text
MAE = trung bình |HR_dự_đoán - HR_tham_chiếu|
```

Dễ hiểu: sai trung bình bao nhiêu BPM.

### RMSE

```text
RMSE = sqrt(trung bình sai_số²)
```

RMSE phạt sai số lớn mạnh hơn MAE.

### R²

R² đo mức mô hình giải thích biến thiên của nhãn so với dự đoán hằng bằng trung bình. R² không thay thế MAE/RMSE và có thể âm nếu mô hình rất kém.

## 17. HR coverage

Trong notebook macro, coverage là tỷ lệ thời gian giữa các quyết định mà hệ thống có một output HR hợp lệ:

```text
Coverage = tổng thời lượng interval có HR / tổng thời lượng interval quyết định
```

Điều này khác với:

- accuracy;
- tỷ lệ HR nằm trong sai số cho phép;
- tỷ lệ mẫu cảm biến hợp lệ.

Một hệ thống có thể coverage 100% nhưng HR sai.

## 18. Baseline, burst và power tail

- Baseline: công suất yên tĩnh trước burst.
- Burst: vùng xử lý được đánh dấu bởi `feature_sync` hoặc `infer_sync`.
- Excess power: phần công suất vượt baseline.
- Power tail: công suất vẫn cao sau khi chân sync đã về 0.

Tổng năng lượng burst phải bao gồm power tail; nếu chỉ tích phân lúc GPIO bằng 1 sẽ đánh giá thiếu.

## 19. Câu tự kiểm tra

1. Vì sao biên độ PPG lớn chưa chắc là tín hiệu tốt?
2. Vì sao hai cửa sổ dài 8 giây nhưng stride 2 giây lại chồng lấn?
3. Công suất khác năng lượng ở điểm nào?
4. Vì sao DAQ nên dùng MCU riêng?
5. Vì sao scaler phải lấy từ train?
6. Vì sao coverage không chứng minh độ chính xác HR?
7. Vì sao TinyML có thể chỉ chiếm tỷ lệ nhỏ dù là phần nghe có vẻ phức tạp nhất?
