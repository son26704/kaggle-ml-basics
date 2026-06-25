# 04. Firmware DAQ ESP32 và INA219

File: `C:\ml\esp32_projects\ina219_daq\main\main.cpp`

## 1. DAQ là gì?

DAQ là data acquisition, hệ thống thu nhận dữ liệu đo. Trong đồ án, DAQ node có nhiệm vụ:

- đo công suất target;
- đọc hai chân sync;
- gắn timestamp;
- gửi dữ liệu về máy tính.

Nó không ước lượng HR và không tham gia scheduler.

## 2. Vì sao cần MCU thứ hai?

Nếu target tự đọc INA219 và in log:

- CPU target phải chạy thêm I2C;
- UART target phải in thêm dữ liệu;
- thời gian và công suất của phép đo bị cộng vào đối tượng đang đo;
- tải phần mềm có thể làm thay đổi chính kết quả.

DAQ tách rời giảm observer effect. Tuy nhiên INA219 vẫn nằm trên đường nguồn và có shunt, nên hệ đo không hoàn toàn “vô hình”.

## 3. Kết nối

### I2C INA219

```text
ESP32 GPIO21 -> SDA
ESP32 GPIO22 -> SCL
INA219 address = 0x40
I2C = 400 kHz
```

### GPIO sync

```text
Target GPIO10 feature_sync -> DAQ GPIO4
Target GPIO11 infer_sync   -> DAQ GPIO5
GND hai board phải nối chung
```

Nếu không nối chung ground, mức logic GPIO không có tham chiếu điện áp chung và kết quả có thể sai.

## 4. Đường nguồn

```text
Nguồn 5 V -> INA219 VIN+ -> shunt -> INA219 VIN- -> target VIN
```

INA219 đo dòng đi qua shunt. DAQ ESP32 nên được cấp riêng, không đi qua shunt đang đo target.

## 5. Các thanh ghi INA219

Firmware dùng:

- `0x00`: configuration.
- `0x02`: bus voltage.
- `0x03`: power.
- `0x04`: current.
- `0x05`: calibration.

INA219 trả giá trị 16-bit big-endian, nên code ghép:

```cpp
(raw[0] << 8) | raw[1]
```

## 6. Khởi tạo I2C

`i2c_init()`:

1. Chọn master.
2. Cấu hình SDA/SCL.
3. Bật pull-up.
4. Chọn clock 400 kHz.
5. `i2c_param_config`.
6. `i2c_driver_install`.

400 kHz giúp giảm thời gian truyền so với 100 kHz, nhưng tổng chu kỳ vẫn bị UART và thời gian chuyển đổi INA219 chi phối.

## 7. Ghi thanh ghi

`ina219_write_reg16()` gửi ba byte:

```text
[register][value high byte][value low byte]
```

Timeout 20 ms.

## 8. Đọc thanh ghi

`ina219_read_reg16()`:

1. Gửi địa chỉ thanh ghi.
2. Repeated-start.
3. Đọc hai byte.
4. Ghép thành `uint16_t`.

Hàm kiểm tra con trỏ output khác null.

## 9. Cấu hình INA219

Firmware ghi:

```cpp
INA219_CONFIG_CONTINUOUS_9BIT = 0x3807
INA219_CALIB_32V_2A = 4096
```

Mục tiêu dùng 9-bit là giảm conversion time so với 12-bit.

Calibration 4096 tương ứng cấu hình phổ biến:

- current LSB = 0,1 mA/bit;
- power LSB = 2 mW/bit.

Nếu điện trở shunt/module khác với giả định calibration, dòng và công suất có thể sai hệ số.

## 10. Chuyển raw sang đơn vị vật lý

### Bus voltage

Thanh ghi bus voltage có ba bit thấp không phải dữ liệu điện áp:

```cpp
bus_v = ((bus_raw >> 3) × 4 mV) / 1000
```

### Current

Current có dấu:

```cpp
current_ma = int16(current_raw) × 0,1
```

Cast sang `int16_t` quan trọng vì dòng có thể biểu diễn âm.

### Power

```cpp
power_mw = power_raw × 2
```

## 11. Vòng lặp DAQ

Mỗi vòng:

1. Lấy `timestamp_us`.
2. Đọc hai GPIO.
3. Đọc ba thanh ghi INA219.
4. In một dòng.
5. Delay 1 ms.

Thứ tự hiện tại là đọc GPIO trước khi đọc INA219. Timestamp cũng lấy trước toàn bộ ba lần đọc I2C. Vì thế:

- timestamp gần thời điểm bắt đầu vòng;
- power là giá trị register đọc sau đó;
- GPIO là snapshot trước quá trình đọc power.

Sai lệch vài trăm microsecond đến millisecond có thể tồn tại.

## 12. Schema log

```text
timestamp_us,
bus_v,
current_ma,
power_mw,
feature_pin_state,
infer_pin_state
```

Ví dụ:

```text
42373,5.0920,49.1000,250.0000,0,0
```

Nghĩa là:

- timestamp 42,373 ms từ khi boot;
- bus 5,092 V;
- dòng 49,1 mA;
- công suất register 250 mW;
- không ở feature;
- không ở inference.

## 13. Khi đọc lỗi

Firmware vẫn in timestamp và GPIO nhưng ba giá trị điện có dạng `nan`.

Parser micro dùng `pd.to_numeric(errors="coerce")` rồi `dropna()`, nên toàn bộ dòng lỗi bị loại.

Điều này tạo khoảng timestamp lớn hơn giữa hai mẫu còn lại. Do parser dùng timestamp thật để tính `sample_interval_us`, năng lượng vẫn được tích phân qua khoảng đó bằng giá trị công suất của mẫu trước. Đây là một giả định và có thể gây sai số nếu khoảng mất dữ liệu dài.

## 14. Vì sao median chu kỳ là khoảng 3,3 ms?

Code có delay 1 ms nhưng một vòng còn gồm:

- 3 giao dịch đọc thanh ghi;
- overhead ESP-IDF;
- format float;
- `printf` khoảng vài chục byte;
- truyền UART 115200.

Ví dụ 60 byte cần lý tưởng:

```text
60 × 10 / 115200 ≈ 5,2 ms
```

Dòng thực tế có thể ngắn hơn và buffering/driver ảnh hưởng, nhưng rõ ràng UART là giới hạn lớn.

Kết quả đo thực tế khoảng 3,3 ms quan trọng hơn suy luận lý thuyết từ `delay_us(1000)`.

## 15. Tại sao DAQ khó bắt `infer_sync`?

Invoke trung bình khoảng 374-380 µs, còn DAQ lấy mẫu khoảng 3298-3299 µs.

Nếu một xung 0,38 ms xuất hiện ngẫu nhiên trong khoảng lấy mẫu 3,3 ms, nhiều lần DAQ sẽ đọc GPIO trước hoặc sau xung và bỏ lỡ hoàn toàn.

Do đó:

- GPIO infer vẫn hữu ích để xác nhận một số burst;
- không thể dùng số row `infer=1` để tính chính xác độ rộng Invoke;
- phải dùng `invoke_time_us` từ target.

## 16. Đồng bộ clock

Target và DAQ có hai timer độc lập:

- target timestamp tính từ boot target;
- DAQ timestamp tính từ boot DAQ.

Không có clock synchronization tuyệt đối trong firmware. Phân tích micro hiện tại chủ yếu ghép burst theo thứ tự, không ghép bằng timestamp tuyệt đối giữa hai MCU.

Điều này hoạt động khi:

- số burst và số cửa sổ HIGH bằng nhau;
- không mất burst;
- thứ tự log đúng.

Nếu mất một burst ở giữa, ghép theo index có thể lệch toàn bộ phần sau.

## 17. Tích phân năng lượng từ log

Parser tạo:

```text
sample_interval_us[i] = timestamp[i+1] - timestamp[i]
```

Năng lượng excess:

```text
Σ max(power[i] - baseline, 0) × interval[i] / 1000
```

Đây gần với left Riemann sum: coi power tại mẫu `i` đại diện cho cả khoảng tới mẫu kế tiếp.

## 18. Giới hạn phép đo

1. INA219 không đủ nhanh để quan sát chính xác xung vài trăm µs.
2. UART làm giảm tốc độ lấy mẫu.
3. Timestamp không đúng chính xác thời điểm conversion INA219.
4. Thanh ghi power của INA219 có lượng tử hóa 2 mW/bit.
5. 9-bit nhanh nhưng nhiễu/độ phân giải kém hơn.
6. Hai MCU chưa đồng bộ clock.
7. Board regulator và USB cable ảnh hưởng điện áp/công suất.
8. Calibration phụ thuộc module/shunt thực tế.

## 19. Vì sao vẫn dùng được?

Hệ đo vẫn phù hợp để:

- so sánh công suất trung bình giữa mode;
- thấy HIGH có miền công suất khác NORMAL;
- phát hiện burst feature dài vài ms;
- ước lượng tổng năng lượng burst gồm tail.

Nó không phù hợp để khẳng định chính xác tuyệt đối năng lượng riêng của Invoke ở cấp vài chục µJ.

## 20. Cải tiến nếu làm tiếp

- Dùng power monitor nhanh hơn như Joulescope/Otii/PPK2 hoặc ADC/shunt tốc độ cao.
- Ghi binary vào RAM/SD thay vì format float UART mỗi mẫu.
- Dùng DMA UART tốc độ cao với giao thức framing và CRC.
- Timestamp GPIO bằng interrupt/input capture.
- Đồng bộ hai MCU bằng xung start.
- Gửi sequence number từ target sang DAQ.
- Đo nhiều lần, báo mean, std và confidence interval.
- Hiệu chuẩn INA219 bằng đồng hồ chuẩn và tải biết trước.

## 21. Cách trình bày DAQ trước hội đồng

Các ý chính:

- Tách DAQ để giảm ảnh hưởng phép đo lên target.
- INA219 đặt trên đường 5 V của toàn target.
- DAQ đọc power và hai GPIO sync.
- Chu kỳ thực tế khoảng 3,3 ms, chậm hơn Invoke.
- Vì vậy tổng burst đo bằng tích phân DAQ, còn AI energy chỉ là ước lượng từ thời gian firmware.
- Kết luận đáng tin hơn ở cấp “AI không chi phối tổng burst” so với giá trị µJ tuyệt đối của AI.
