# BÁO CÁO XÂY DỰNG HỆ THỐNG PROTOTYPE  
ESP32-S3 + MAX30102 + INA219

## 1. Mục tiêu

Mục tiêu của giai đoạn này là xây dựng và kiểm chứng một hệ thống prototype phần cứng.  
Trọng tâm là:

- hiểu phần cứng ESP32-S3, MAX30102 và INA219;
- đọc được tín hiệu thật từ cảm biến MAX30102;
- hiểu dữ liệu cảm biến có dạng gì và phụ thuộc vào những cấu hình nào
- đo được điện áp, dòng điện và công suất của nhánh cấp nguồn bằng INA219
- ghép hai cảm biến vào cùng một hệ, kiểm tra sự tương tác giữa tín hiệu đo được và mức tiêu thụ năng lượng
- tạo ra cơ sở thực nghiệm để phục vụ bước tiếp theo là chọn dataset và thiết kế mô hình.

---

## 2. Phần cứng sử dụng

### 2.1. ESP32-S3

Bộ xử lý trung tâm là ESP32-S3 N16R8, được lập trình bằng ESP-IDF. ESP32-S3 có vai trò:

- khởi tạo và điều khiển bus I2C;
- cấu hình và đọc dữ liệu từ MAX30102;
- cấu hình và đọc dữ liệu từ INA219;
- ghi log dữ liệu dạng văn bản qua cổng nối tiếp;
- cung cấp nền tảng để sau này chạy TinyML.

Trong giai đoạn này, ESP32-S3 được cấp nguồn trực tiếp từ cổng USB nối với máy tính, chưa sử dụng pin hay adapter riêng.

---

### 2.2. Cảm biến MAX30102

MAX30102 là mô-đun cảm biến đo nhịp tim và đo quang thể tích, tích hợp:

- LED đỏ,
- LED hồng ngoại,
- photodiode,
- phần tử quang học,
- mạch điện tử nhiễu thấp,
- giao tiếp I2C.

Datasheet mô tả MAX30102 là cảm biến pulse oximetry và heart-rate monitor cho thiết bị đeo, có thể lập trình được tốc độ lấy mẫu và dòng LED để cân bằng giữa chất lượng tín hiệu và điện năng tiêu thụ.

MAX30102 cho ra dữ liệu quang dạng số trên hai kênh:

- RED: giá trị ADC tương ứng với ánh sáng đỏ phản xạ quay về;
- IR: giá trị ADC tương ứng với ánh sáng hồng ngoại phản xạ quay về.

Chúng là giá trị ADC theo thời gian, cần phải xử lý tiếp mới suy ra được BPM hoặc các thông tin khác (chưa phải nhịp tim hay nồng độ oxy máu).

---

### 2.3. Cảm biến INA219

INA219 là mạch đo điện áp, dòng điện và công suất, giao tiếp qua I2C. Theo datasheet, INA219 đo đồng thời:

- điện áp bus,
- điện áp rơi trên điện trở shunt,
- từ đó suy ra dòng điện,

Module INA219 có điện trở shunt in trên board là R100, tức khoảng 0.1 Ω.

---

### 2.4. Kiến trúc hệ thống tổng thể

Sơ đồ khối của prototype thể hiện ba khối phần cứng chính:

- **Microcontroller ESP32-S3**  
  là bộ điều khiển trung tâm, giữ vai trò I2C master, xử lý logic điều khiển, ghi log, và là nền tảng để sau này triển khai scheduler cùng TinyML.

- **PPG Sensor MAX30102**  
  là cảm biến quang đo RED/IR, hoạt động như một I2C slave tại địa chỉ `0x57`.

- **Power Monitor INA219**  
  là mạch giám sát năng lượng, hoạt động như một I2C slave tại địa chỉ `0x40`.

Điểm quan trọng của kiến trúc này là có **hai lớp kết nối khác nhau** cần được hiểu tách biệt.

Thứ nhất là **đường dữ liệu I2C**. ESP32-S3 điều khiển cả INA219 và MAX30102 qua cùng cặp tín hiệu `SDA/SCL`. Trên đường này:

- ESP32-S3 gửi lệnh cấu hình,
- MAX30102 trả về dữ liệu quang RED/IR,
- INA219 trả về điện áp, dòng điện và công suất.

Thứ hai là **đường cấp nguồn được đo công suất**. Theo sơ đồ khối, nguồn `3.3 V` từ ESP32-S3 không đi thẳng đến MAX30102 mà đi qua nhánh đo của INA219:

`ESP32-S3 3.3V -> INA219 VIN+ -> điện trở shunt nội bộ -> INA219 VIN- -> MAX30102 VIN`

Điều này có ý nghĩa thiết kế rất lớn. Nếu INA219 chỉ nằm trên cùng bus I2C nhưng không nằm trực tiếp trên đường nguồn của MAX30102, hệ thống vẫn có thể đọc được dữ liệu PPG nhưng sẽ **không đo đúng tiêu thụ của tải cảm biến**. Vì vậy, sơ đồ khối mới không chỉ minh họa bố trí phần cứng mà còn thể hiện rõ triết lý của prototype: đo đồng thời **tín hiệu sinh lý** và **chi phí năng lượng** của chính nhánh cảm biến đó.

Nói cách khác:

- các đường nét đứt trong sơ đồ biểu diễn **bus I2C dùng chung**,
- còn đường nguồn 3.3 V đi qua INA219 rồi mới sang MAX30102 biểu diễn **nhánh năng lượng được giám sát**.

Chính cách bố trí này là nền tảng cho toàn bộ các bước ở Phần B, nơi hệ thống không chỉ cần biết "tín hiệu có đẹp hay không" mà còn cần biết "để có tín hiệu đó, hệ thống đang tốn bao nhiêu năng lượng".

---

## 3. Project demo

### 3.1. max30102_test

Link: https://github.com/son26704/max30102_test/

Project dùng để:

- khởi tạo MAX30102;
- cấu hình mode đo;
- đọc FIFO;
- in log RED/IR;
- xuất log CSV theo thời gian;
- dùng Python để vẽ đồ thị và ước lượng BPM.

---

### 3.2. ina219_test

Link: https://github.com/son26704/ina219_test/

Project dùng để:

- khởi tạo INA219;
- đọc bus voltage;
- đọc shunt voltage;
- đọc current/power register;
- đồng thời tự tính dòng và công suất bằng công thức vật lý từ điện áp shunt và điện áp bus để kiểm chứng.

---

### 3.3. ina219_max30102_test

Link: https://github.com/son26704/ina219_max30102_test/

Project dùng để:

- ghép MAX30102 và INA219 vào cùng hệ thống;
- cấp nguồn cho MAX30102 qua nhánh đo của INA219;
- vừa đọc dữ liệu sinh lý RED/IR, vừa đo công suất trung bình của nhánh MAX30102;
- so sánh mức tiêu thụ năng lượng giữa các cấu hình khác nhau của MAX30102.

---

## 4. Thực nghiệm với MAX30102

### 4.1. Kết nối phần cứng

Module MAX30102 dùng trong thực nghiệm có các chân:

- VIN  
- GND  
- SDA  
- SCL  
- INT  

Trong giai đoạn test riêng, nối như sau:

- VIN → 3V3 của ESP32-S3  
- GND → GND  
- SDA → GPIO8  
- SCL → GPIO9  
- INT để hở, chưa dùng ngắt  

---

### 4.2. Các cấu hình quan trọng của MAX30102

#### 4.2.1. Chế độ hoạt động

MAX30102 hỗ trợ nhiều mode. Trong thực nghiệm sử dụng SpO2 mode, tức là đo đồng thời hai kênh đỏ và hồng ngoại. Datasheet cho biết mode control có các chế độ như heart-rate mode, SpO2 mode và multi-LED mode. SpO2 mode là lựa chọn phù hợp cho giai đoạn học cảm biến vì giữ đầy đủ thông tin ở cả RED và IR.

---

#### 4.2.2. Sample rate

Theo datasheet, sample rate của phần SpO2 có thể chọn từ:

- 50  
- 100  
- 200  
- 400  
- 800  
- 1000  
- 1600  
- 3200 mẫu mỗi giây  

Trong thực nghiệm, sample rate đang được đặt là 100 sps.

---

#### 4.2.3. Pulse width và độ phân giải ADC

Datasheet cho biết LED pulse width có 4 mức:

- 69 µs → 15 bit  
- 118 µs → 16 bit  
- 215 µs → 17 bit  
- 411 µs → 18 bit  

Trong thực nghiệm chọn:

- pulse width = 411 µs  
- tương ứng ADC resolution = 18 bit  

---

#### 4.2.4. ADC range

Trong cấu hình SpO2 của MAX30102, ADC range có thể thay đổi để phù hợp với biên độ tín hiệu. Thực nghiệm chọn:

- ADC range = 4096 nA  

Đây là mức trung bình, đủ an toàn để bắt đầu, không quá nhạy gây bão hòa sớm, nhưng vẫn đủ để quan sát tín hiệu.

---

#### 4.2.5. Sample averaging qua FIFO

Datasheet cho biết FIFO của MAX30102 có thể lấy trung bình nội bộ theo số mẫu:

- 1 (không averaging)  
- 2  
- 4  
- 8  
- 16  
- 32  

Trong thực nghiệm đã so sánh:

- averaging = 4  
- averaging = 1  

---

#### 4.2.6. LED current

Dòng điều khiển LED đỏ và LED hồng ngoại quyết định độ sáng phát xạ, ảnh hưởng rất mạnh đến biên độ RED/IR và đồng thời ảnh hưởng tới điện năng tiêu thụ. Trong thực nghiệm đã thử:

- 0x10  
- 0x24  
- 0x40  

---

### 4.3. Ý nghĩa của RED và IR

RED là giá trị ADC của tín hiệu phản xạ từ LED đỏ. LED đỏ của MAX30102 có bước sóng đỉnh khoảng 660 nm.

IR là giá trị ADC của tín hiệu phản xạ từ LED hồng ngoại gần. LED IR của MAX30102 có bước sóng đỉnh khoảng 880 nm.

---

### 4.4. Quan sát thực nghiệm với vật thể và tay người

Khi đưa cảm biến gần các vật thể khác nhau:

- chiếu vào không khí hoặc vật ở xa → RED/IR rất thấp  
- chiếu vào bề mặt trắng → RED/IR tăng rất mạnh  
- chiếu vào bề mặt đen → RED/IR tăng ít hơn  
- đặt vào tay → RED/IR tăng rõ rệt lên hàng chục nghìn hoặc hơn trăm nghìn  

→ MAX30102 là cảm biến quang phản xạ:

- phản xạ càng mạnh thì ADC càng cao  
- khoảng cách, màu sắc bề mặt, vị trí tay và lực ép đều ảnh hưởng đến tín hiệu  

---

### 4.5. Ghi log và vẽ đồ thị bằng Python

Sau khi chỉnh log thành dạng CSV:

- time_ms, red, ir  

dữ liệu được nhập vào Python, dùng pandas và matplotlib để:

- đọc file  
- tạo trục thời gian theo giây  
- vẽ đồ thị RED  
- vẽ đồ thị IR  
- vẽ tín hiệu centered / bỏ nền tương đối  

Đồ thị cho thấy tín hiệu gồm hai thành phần:

- DC: nền lớn, thay đổi chậm theo lực ép, vị trí tiếp xúc, điều kiện quang học  
- AC: dao động nhỏ, nhanh, lặp lại theo nhịp tim  

→ nền tảng để tính BPM từ PPG.

---

### 4.6. Tính nhịp tim cơ bản (BPM)

Quy trình thực hiện trong Python như sau:

1. chọn kênh IR vì tín hiệu ổn định hơn;  
2. dùng rolling mean để ước lượng nền chậm;  
3. lấy signal_ac = signal - baseline để làm nổi bật thành phần dao động;  
4. làm mượt nhẹ  
5. dùng peak detection để tìm các đỉnh cục bộ  
6. tính khoảng thời gian giữa các peak  
7. suy ra BPM theo công thức:

\[
BPM = \frac{60}{\text{chu kỳ trung bình (giây)}}
\]

Kết quả thực nghiệm điển hình:

- tần số lấy mẫu hiệu dụng khoảng ~25 Hz khi averaging = 4  
- số peak phát hiện: 69  
- BPM ước lượng: khoảng 77.19 bpm  
- mean interval: khoảng 0.777 s  

Nhận xét:

- BPM ra mức hợp lý về mặt sinh lý  
- kênh IR cho kết quả tốt hơn RED  
- phù hợp cho mức prototype  

---

### 4.7. Giới hạn của phương pháp BPM cơ bản

Kết quả ở mục 4.6 cho thấy pipeline xử lý cơ bản bằng Python đã đủ để xác nhận rằng tín hiệu PPG đo từ MAX30102 thực sự chứa thông tin nhịp tim. Tuy nhiên, cần nhấn mạnh rằng đây **chưa phải lời giải hoàn chỉnh cho bài toán wearable**.

Lý do là quy trình hiện tại vẫn dựa trên giả định rằng:

- ngón tay giữ khá ổn định trên cảm biến,  
- baseline thay đổi chậm và có thể bỏ nền bằng phép trừ đơn giản,  
- các peak quan sát được chủ yếu là peak tim thật.  

Trong thực tế, khi người dùng thay đổi lực ép, dịch chuyển tay, hoặc tạo rung cơ học, tín hiệu sẽ xuất hiện ba vấn đề:

- nền DC thay đổi mạnh theo thời gian,  
- biên độ dao động bị méo bởi điều kiện tiếp xúc,  
- peak detection có thể bắt nhầm đỉnh giả do motion artifact.  

Nói cách khác, phương pháp BPM cơ bản ở Phần A phù hợp để **kiểm chứng cảm biến và xác nhận tính khả dụng của tín hiệu**, nhưng chưa đủ robust để dùng làm thuật toán cuối cùng cho thiết bị đeo hoạt động ngoài đời thực. Đây chính là lý do mà ở Phần B, bài toán không còn là "đọc được BPM", mà chuyển thành "đánh giá chất lượng tín hiệu, phát hiện khi nào DSP không còn đáng tin, và chỉ kích hoạt pipeline xử lý mạnh hơn khi cần".

---

## 5. Thực nghiệm với INA219

### 5.1. Ý nghĩa của INA219

INA219 dùng để đo:

- điện áp bus  
- điện áp rơi trên shunt  
- dòng điện  
- công suất  

---

### 5.2. Kết nối phần cứng với INA219 riêng

INA219 được nối với ESP32 qua I2C:

- VCC → 3V3  
- GND → GND  
- SDA → GPIO8  
- SCL → GPIO9  

Để đo dòng của nhánh MAX30102:

- 3V3 của ESP32 → VIN+ của INA219  
- VIN- của INA219 → VIN của MAX30102  
- GND của MAX30102 → GND chung  

Như vậy, INA219 đo đúng nhánh:

- dòng cấp từ 3V3 sang module MAX30102  

→ dòng của nhánh tải MAX30102

---

### 5.3. Ý nghĩa các thông số

- BUS là điện áp bus tại VIN- so với GND  
- SHUNT là điện áp rơi trên điện trở shunt  
- CURRENT lấy từ Current Register  
- POWER lấy từ Power Register  

Ngoài ra có thể tự tính để kiểm chứng.

---

### 5.4. Kết quả test riêng INA219

Ban đầu:

- BUS ≈ 3.31 V  
- SHUNT ≈ 0.22–0.27 mV  
- dòng ≈ 2.2–2.7 mA  
- công suất ≈ 7–9 mW  

Sau khi tính thủ công:

- I_REG và I_MAN gần khớp nhau  
- P_REG và P_MAN gần nhau  

Nhận xét:

- INA219 hoạt động đúng  
- cách nối đúng  
- tính dòng từ SHUNT là tin cậy  

---

## 6. Ghép chung MAX30102 và INA219

### 6.1. Mục tiêu

- đo điện năng tiêu thụ của MAX30102  
- quan sát thay đổi tín hiệu quang  
- đánh giá trade-off tín hiệu và công suất  

---

### 6.2. Cách nối ghép chung

Trong cấu hình ghép chung, hệ thống được mắc đúng theo kiến trúc tổng thể đã mô tả ở mục 2.4.

**Đường cấp nguồn được đo công suất:**

`ESP32 3V3 -> INA219 VIN+ -> shunt -> INA219 VIN- -> MAX30102 VIN`

**Đường giao tiếp I2C dùng chung:**

- ESP32-S3 là I2C master  
- INA219 là I2C slave tại địa chỉ `0x40`  
- MAX30102 là I2C slave tại địa chỉ `0x57`  
- hai cảm biến dùng chung `SDA`, `SCL` và mass chung  

Với cấu hình này, ESP32-S3 có thể thực hiện đồng thời hai nhiệm vụ:

- đọc dữ liệu quang RED/IR từ MAX30102,
- đọc điện áp, dòng điện và công suất của đúng nhánh cấp nguồn đi vào MAX30102 từ INA219.

Điểm cốt lõi là INA219 không chỉ là một cảm biến "đo kèm" trên bus, mà nằm trực tiếp trên nhánh nguồn của MAX30102. Vì vậy, giá trị power thu được phản ánh đúng chi phí năng lượng của cảm biến dưới từng cấu hình sample rate, averaging và LED current.

→ INA219 đo toàn bộ tiêu thụ của MAX30102 theo đúng sơ đồ khối của prototype

---

### 6.3. Đo giá trị tức thời và lấy trung bình

Dòng biến thiên mạnh do:

- LED bật/tắt theo xung  
- INA219 đo theo chu kỳ  

Giải pháp:

- đọc mỗi 10 ms  
- cộng dồn  
- lấy trung bình sau 50 mẫu  
- xuất I_MEAN, P_MEAN  

---

## 7. Kết quả so sánh cấu hình của MAX30102

### 7.1. Averaging

**Averaging = 4**

- dữ liệu mượt  
- ~25 Hz  
- công suất ~29.5–30.2 mW  

**Averaging = 1**

- dữ liệu thô  
- nhiều chi tiết  
- công suất ~31–32.4 mW  

→ Nhận xét:

- averaging = 4: mượt, tiết kiệm điện  
- averaging = 1: chi tiết hơn  

---

### 7.2. LED current

**0x10**

- RED/IR thấp  
- công suất ~21 mW  
- chưa bão hòa  

**0x24**

- RED ~110k–120k  
- IR ~130k–140k  
- công suất ~31–32 mW  
- tối ưu nhất  

**0x40**

- IR chạm trần ADC (262143)  
- bão hòa  

→ Nhận xét:

- tăng LED → tăng tín hiệu  
- nhưng quá cao → bão hòa  

---

### 7.3. Bài học thiết kế rút ra từ thực nghiệm tín hiệu và công suất

Phần so sánh cấu hình ở mục 7 không chỉ nhằm chọn một bộ thông số "đẹp" cho prototype, mà còn cho thấy một quy luật thiết kế quan trọng của hệ thống:

1. **Chất lượng tín hiệu và công suất luôn gắn chặt với nhau**  
   Khi thay đổi LED current hoặc sample averaging, ta không chỉ đổi biên độ tín hiệu mà còn đổi mức tiêu thụ năng lượng của node đo.

2. **Không tồn tại một cấu hình cố định tối ưu cho mọi tình huống**  
   Cấu hình cho tín hiệu đẹp khi tay giữ yên chưa chắc phù hợp khi có chuyển động; ngược lại, cấu hình có độ nhạy cao hơn có thể làm tăng công suất hoặc đẩy hệ thống vào vùng bão hòa.

3. **Cần một cơ chế điều phối thay vì chỉ chọn một bộ tham số tĩnh**  
   Kết quả thực nghiệm cho thấy cấu hình cảm biến không nên được xem như hằng số bất biến. Về sau, thay vì buộc toàn hệ thống luôn chạy ở một mức "an toàn", hướng hợp lý hơn là chỉ dùng cấu hình nặng khi điều kiện đo thực sự khó.

Đây là kết luận rất quan trọng để bước sang Phần B. Nó chuyển trọng tâm từ bài toán "tối ưu một cấu hình phần cứng" sang bài toán "điều phối thích nghi giữa nhiều cấu hình và nhiều tầng xử lý".

---

### Kết luận

- RED và IR thay đổi mạnh theo điều kiện đo  
- nhưng công suất gần như không đổi theo phản xạ  

→ nghĩa là:

- quang học phụ thuộc môi trường  
- điện năng phụ thuộc cấu hình  

---

## 8. Cấu hình đề xuất tạm thời cho prototype

- Mode: SpO2 mode  
- Sample rate: 100 sps  
- Pulse width: 411 µs  
- ADC range: 4096 nA  
- LED current: 0x24  
- Sample averaging: 4  

Đây là cấu hình tạm thời phù hợp để tiếp tục phát triển prototype vì nó tạo được tín hiệu đủ rõ, chưa bão hòa ADC và cho phép quan sát tương đối ổn định trong điều kiện nghỉ. Tuy nhiên, cấu hình này **chưa được xem là cấu hình tối ưu cuối cùng cho wearable**, bởi nó mới phản ánh sự cân bằng trong một số điều kiện đo cơ bản, chưa giải quyết bài toán thích nghi theo trạng thái tín hiệu.

Trong thực tế, nếu cố định toàn bộ hệ thống ở một cấu hình duy nhất, ta sẽ gặp hai khả năng đều không lý tưởng:

- hoặc chọn cấu hình nhẹ để tiết kiệm điện nhưng dễ thất bại khi tín hiệu xấu,  
- hoặc chọn cấu hình mạnh để giữ chất lượng tín hiệu nhưng phải trả giá bằng công suất cao hơn mức cần thiết.  

Vì vậy, cấu hình đề xuất ở Phần A nên được hiểu là **baseline kỹ thuật để chuyển sang giai đoạn điều phối thích nghi ở Phần B**, chứ không phải lời giải cuối cùng của hệ thống.

---

## 9. Hạn chế của Part A và động cơ chuyển sang Part B

Từ toàn bộ thực nghiệm ở Phần A, có thể rút ra ba kết luận mang tính chuyển tiếp.

Thứ nhất, prototype đã chứng minh được tính khả thi của tầng phần cứng. ESP32-S3 có thể giao tiếp ổn định với cả MAX30102 và INA219 qua I2C, đọc được dữ liệu quang RED/IR, đồng thời đo được điện áp, dòng điện và công suất của nhánh tải cảm biến. Điều này tạo ra nền tảng đủ vững để bước sang tầng xử lý tín hiệu và tầng hệ thống.

Thứ hai, tín hiệu PPG thực tế không phải là một chuỗi lý tưởng chỉ chứa dao động nhịp tim. Nó chịu ảnh hưởng mạnh bởi lực ép, vị trí đặt tay, phản xạ quang học và các chuyển động cơ học. Do đó, peak detection cơ bản tuy hữu ích trong điều kiện nghỉ nhưng không đảm bảo còn đáng tin khi chuyển sang trạng thái có nhiễu.

Thứ ba, các thực nghiệm với INA219 cho thấy điện năng tiêu thụ phụ thuộc trực tiếp vào cấu hình cảm biến, trong khi các thực nghiệm với MAX30102 lại cho thấy chất lượng tín hiệu cũng phụ thuộc mạnh vào chính các cấu hình đó. Nói cách khác, hệ thống đã bộc lộ một trade-off cốt lõi:

- muốn tín hiệu mạnh hơn thì thường phải trả thêm công suất,  
- muốn tiết kiệm điện hơn thì có nguy cơ làm giảm độ ổn định của tín hiệu.  

Chính vì vậy, bài toán của giai đoạn tiếp theo không còn là "đọc được tín hiệu" hay "ước lượng được BPM cơ bản", mà là:

- đánh giá chất lượng cửa sổ tín hiệu theo thời gian thực,  
- nhận biết khi nào pipeline DSP nhẹ không còn đủ tin cậy,  
- và thiết kế một cơ chế điều phối thích nghi để chỉ kích hoạt các bước xử lý nặng hơn khi thật sự cần thiết.  

Đó là động cơ trực tiếp dẫn sang Phần B: **Tối ưu hóa năng lượng và tích hợp TinyML điều phối thích nghi**. Nếu Phần A trả lời câu hỏi "prototype phần cứng có hoạt động hay không", thì Phần B sẽ trả lời câu hỏi khó hơn: "làm thế nào để prototype này vừa tiết kiệm năng lượng, vừa duy trì được khả năng quan sát nhịp tim trong điều kiện nhiễu ngoài đời thực".
