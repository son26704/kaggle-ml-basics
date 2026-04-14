# Hướng Dẫn Vẽ Sơ Đồ Cho Báo Cáo

File này dùng để hỗ trợ các hình không thể sinh trực tiếp từ log hoặc notebook. Bạn có thể vẽ lại trong Word, PowerPoint hoặc draw.io dựa trên ASCII và mô tả dưới đây.

## Hình A.1. Sơ đồ khối tổng thể của hệ thống prototype

ASCII gợi ý:

```text
                    +---------------------------+
                    |   ESP32-S3 MCU            |
                    | I2C Master / Scheduler /  |
                    | TinyML Runtime            |
                    +------------+--------------+
                                 | I2C
                 +---------------+---------------+
                 |                               |
                 v                               v
      +---------------------+         +----------------------+
      | INA219              |         | MAX30102             |
      | Power Monitor       |         | PPG Sensor           |
      | I2C Slave           |         | I2C Slave            |
      +----------+----------+         +----------------------+
                 |
                 | monitored power path
                 v
       USB 5V -> INA219 Shunt -> ESP32 VIN -> ESP32 3V3 -> Sensor rail
```

Cách vẽ:
- Đặt `ESP32-S3` ở trung tâm phía trên.
- Đặt `INA219` và `MAX30102` phía dưới, nối với ESP32-S3 bằng đường bus I2C.
- Thể hiện riêng một mũi tên nguồn đi qua `INA219` rồi vào `ESP32 VIN`.
- Chú thích `ESP32 3V3` cấp lại cho `INA219 logic` và `MAX30102`.

## Hình A.3. Hai cấu hình đo năng lượng được sử dụng trong quá trình nghiên cứu

ASCII gợi ý:

```text
Cấu hình 1: Đo nhánh cảm biến

ESP32 3V3 ---> INA219 ---> MAX30102
   |                           ^
   +--------- I2C -------------+


Cấu hình 2: Đo công suất toàn hệ thống

USB 5V ---> INA219 ---> ESP32 VIN ---> ESP32 3V3 ---> MAX30102
                    \-------------------------------> INA219 logic

ESP32 --- I2C --- INA219
ESP32 --- I2C --- MAX30102
```

Cách vẽ:
- Đặt hai sơ đồ cạnh nhau để nhấn mạnh sự khác nhau về điểm đo.
- Sơ đồ bên trái dùng để giải thích giai đoạn khảo sát cảm biến.
- Sơ đồ bên phải dùng để giải thích giai đoạn đánh giá `whole-system power`.

## Hình B.1. Lưu đồ điều phối hai trạng thái NORMAL và HIGH

ASCII gợi ý:

```text
        +-----------------------------+
        | Đọc cửa sổ tín hiệu PPG     |
        +-------------+---------------+
                      |
                      v
        +-----------------------------+
        | Đánh giá quality gate       |
        | amplitude / periodicity /   |
        | HR consistency              |
        +-------------+---------------+
                      |
          +-----------+-----------+
          |                       |
     tín hiệu tốt            tín hiệu xấu
          |                       |
          v                       v
 +------------------+   +-----------------------+
 | NORMAL           |   | HIGH                  |
 | DSP nhẹ          |   | DSP + Feature + AI    |
 | 50 Hz            |   | 100 Hz                |
 +--------+---------+   +-----------+-----------+
          |                         |
          +-----------+-------------+
                      |
                      v
        +-----------------------------+
        | Kiểm tra tín hiệu ổn định?  |
        +-------------+---------------+
                      |
                 quay về NORMAL
```

Cách vẽ:
- Dùng một hình thoi cho bước đánh giá chất lượng tín hiệu.
- Tô màu nhẹ `NORMAL` và `HIGH` khác nhau để nhấn mạnh hai profile.
- Có thể thêm chú thích `Fast Path` dưới nhánh `NORMAL` và `Slow Path` dưới nhánh `HIGH`.
