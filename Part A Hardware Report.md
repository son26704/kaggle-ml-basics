# BÁO CÁO XÂY DỰNG HỆ THỐNG PROTOTYPE
ESP32-S3 + MAX30102 + INA219

## 1. Mục tiêu

Phần A có mục tiêu xây dựng và kiểm chứng một prototype phần cứng đủ tin cậy để làm nền cho giai đoạn tối ưu năng lượng và tích hợp TinyML ở Phần B. Trọng tâm của giai đoạn này không phải là tối ưu mô hình, mà là trả lời bốn câu hỏi cơ bản:

- ESP32-S3 có thể điều khiển ổn định bus I2C và đọc đồng thời hai ngoại vi hay không.
- MAX30102 có tạo ra được tín hiệu PPG đủ rõ để suy ra nhịp tim cơ bản trong điều kiện nghỉ hay không.
- INA219 có đo được telemetry năng lượng đủ ổn định để so sánh các cấu hình vận hành hay không.
- Toàn bộ pipeline phần cứng, firmware và logging có đủ trưởng thành để làm nền cho adaptive scheduling ở giai đoạn tiếp theo hay không.

Vì vậy, Part A đóng vai trò như một báo cáo xác nhận nền tảng: xác nhận phần cứng hoạt động, xác nhận dữ liệu đo được có ý nghĩa, và xác nhận cách ghép hệ thống cho phép quan sát đồng thời cả tín hiệu sinh lý lẫn năng lượng tiêu thụ.

---

## 2. Phần cứng sử dụng

### 2.1. ESP32-S3

Bộ xử lý trung tâm là ESP32-S3 N16R8, được lập trình bằng ESP-IDF. Trong prototype này, ESP32-S3 đảm nhiệm các vai trò sau:

- khởi tạo và làm `I2C master` cho toàn hệ thống;
- cấu hình, đọc dữ liệu và reset ngoại vi khi cần;
- xử lý tín hiệu mức cơ bản để quan sát dạng sóng và ước lượng BPM ban đầu;
- ghi log telemetry qua UART để phục vụ phân tích offline bằng Python/Jupyter;
- làm nền tảng phần cứng cho scheduler và TinyML ở Phần B.

Điểm quan trọng là ESP32-S3 không chỉ là vi điều khiển đọc cảm biến, mà còn là nơi hội tụ của cả ba lớp chức năng: điều khiển thiết bị, xử lý tín hiệu và về sau là suy luận học máy. Do đó, mọi đánh giá năng lượng nghiêm túc ở các giai đoạn sau đều phải tính chi phí của chính ESP32-S3, chứ không thể chỉ nhìn riêng cảm biến quang.

### 2.2. Cảm biến MAX30102

MAX30102 là cảm biến PPG tích hợp LED đỏ, LED hồng ngoại, photodiode và khối front-end quang học. Thiết bị giao tiếp qua I2C và cho phép cấu hình được:

- `sample rate`;
- `pulse width`;
- `sample averaging`;
- dòng LED cho từng kênh quang.

Dữ liệu đầu ra của MAX30102 là chuỗi mẫu số theo thời gian trên hai kênh `RED` và `IR`. Đây chưa phải nhịp tim hay SpO2, mà chỉ là tín hiệu quang phản xạ cần được xử lý tiếp. Chính điều này làm cho MAX30102 phù hợp với mục tiêu của đề tài: nó vừa cho phép kiểm chứng tín hiệu PPG thật, vừa buộc hệ thống phải tự giải quyết bài toán xử lý tín hiệu và điều phối tài nguyên.

### 2.3. Cảm biến INA219

INA219 là mạch đo điện áp, dòng điện và công suất qua I2C. Module sử dụng điện trở shunt trên board để đo sụt áp nhỏ và từ đó suy ra dòng tải. Trong prototype này, INA219 được dùng để ghi lại ba đại lượng:

- `bus voltage`;
- `current`;
- `power`.

Sự hiện diện của INA219 là yếu tố biến prototype từ một mạch “đọc được PPG” thành một hệ có thể nghiên cứu bài toán năng lượng. Không có telemetry năng lượng, các phát biểu về tiết kiệm pin ở Phần B sẽ chỉ dừng ở mức giả định.

### 2.4. Kiến trúc hệ thống tổng thể

Sơ đồ khối của hệ thống cần được hiểu theo hai lớp song song: lớp truyền thông điều khiển và lớp đường cấp nguồn dùng để đo năng lượng.

Ở lớp điều khiển, `ESP32-S3` là nút trung tâm, đóng vai trò `I2C master` cho hai slave:

- `MAX30102` tại địa chỉ `0x57`;
- `INA219` tại địa chỉ `0x40`.

ESP32-S3 gửi lệnh cấu hình, đọc dữ liệu mẫu từ MAX30102, đọc các thanh ghi điện áp-dòng-công suất từ INA219, sau đó ghi toàn bộ telemetry ra UART để phân tích offline. Trong block diagram mới của hệ thống, phần chữ `Scheduler, TinyML` nằm ngay trong khối ESP32-S3 là hợp lý, vì về bản chất mọi quyết định thích nghi ở Phần B đều được thực thi trên vi điều khiển này chứ không nằm ở cảm biến.

Ở lớp cấp nguồn, prototype đã trải qua hai cấu hình đo khác nhau.

#### Bước 1: Đo nhánh cảm biến

Ở giai đoạn khảo sát phần cứng ban đầu, INA219 được đặt trên nhánh cấp nguồn của riêng MAX30102. Cấu hình này hữu ích khi cần trả lời các câu hỏi rất cụ thể về cảm biến, ví dụ:

- tăng `LED current` làm biên độ tín hiệu thay đổi thế nào;
- thay đổi `sample rate` làm riêng MAX30102 tiêu thụ thêm bao nhiêu;
- `averaging = 1` và `averaging = 4` khác nhau ra sao về chi phí năng lượng của chính cảm biến.

Đây là phép đo đúng cho mục tiêu “hiểu MAX30102”, nhưng chưa đủ để kết luận ở mức hệ thống.

#### Bước 2: Đo công suất toàn hệ thống

Khi bài toán chuyển sang adaptive scheduling, mục tiêu không còn là đo riêng cảm biến mà là đo chi phí thật của toàn node. Cấu hình cuối cùng vì vậy được chuyển sang:

`USB VBUS 5V từ PC -> INA219 VIN+ -> shunt nội bộ INA219 -> INA219 VIN- -> ESP32 VIN 5V`

Sau đó:

- rail `3V3` của ESP32 cấp lại cho `MAX30102`;
- rail `3V3` của ESP32 cấp cho logic của `INA219`;
- toàn bộ hệ thống dùng chung mass.

Kiến trúc này có ý nghĩa phương pháp luận rất lớn: mọi dòng tiêu thụ của node, bao gồm vi điều khiển, xử lý DSP, TinyML, UART logging và cảm biến, đều đi qua shunt của INA219. Vì vậy, các kết quả macro-level về power ở Phần B là `whole-system power`, không phải `sensor-only power`.

---

## 3. Môi trường firmware và các project thử nghiệm

### 3.1. Project đọc MAX30102

Bước đầu tiên của quá trình phát triển là xác nhận ESP32-S3 có thể giao tiếp ổn định với MAX30102, đọc được dữ liệu `RED/IR` liên tục và ghi log ra UART. Ở bước này, mục tiêu chưa phải là tối ưu năng lượng hay xây scheduler, mà là xác nhận tín hiệu thô tồn tại và có biến thiên phù hợp với nhịp mạch khi đặt ngón tay đúng cách.

### 3.2. Project đọc INA219

Song song với MAX30102, một firmware thử nghiệm riêng cho INA219 được dùng để kiểm chứng ba việc:

- giao tiếp I2C với địa chỉ cấu hình đúng;
- đọc được `bus voltage`, `shunt voltage`, `current`, `power`;
- hiểu được độ ổn định và độ nhạy của phép đo trong điều kiện cấp nguồn thực tế.

Điều này quan trọng vì sai số hay dao động trong phép đo điện năng có thể dẫn đến kết luận sai ở các giai đoạn tối ưu sau.

### 3.3. `ina219_max30102_test`

Project `ina219_max30102_test` là cột mốc kết nối Part A với Part B. Đây không chỉ là project ghép hai cảm biến vào cùng một firmware, mà còn là nền tảng cho toàn bộ workflow nghiên cứu về sau.

Vai trò của project này gồm:

- ghép MAX30102 và INA219 vào cùng một hệ thống trên ESP32-S3;
- thu đồng thời dữ liệu quang và telemetry năng lượng;
- chuẩn hóa định dạng log CSV để đưa vào notebook phân tích;
- tạo ra dữ liệu thực nghiệm cho việc xây quality gate và scheduler rule-based;
- về sau là cầu nối giữa thực nghiệm phần cứng và adaptive TinyML scheduling.

Điểm quan trọng là project này đã hỗ trợ cả hai kiểu đo năng lượng đã nêu ở phần kiến trúc: ban đầu đo nhánh cảm biến, sau đó chuyển sang đo công suất toàn hệ thống để phục vụ macro evaluation.

---

## 4. Khảo sát tín hiệu PPG từ MAX30102

### 4.1. Đọc dữ liệu `RED/IR`

Sau khi giao tiếp I2C ổn định, firmware ghi lại hai kênh `RED` và `IR` theo thời gian. Quan sát trực tiếp trên log cho thấy khi đặt ngón tay đúng cách, cả hai kênh đều có thành phần DC lớn và dao động AC nhỏ chồng lên trên. Thành phần AC này chính là phần chứa thông tin nhịp mạch.

Thực nghiệm cũng cho thấy tín hiệu phụ thuộc mạnh vào điều kiện tiếp xúc:

- đặt tay ổn định cho dạng sóng đều hơn;
- lực ép quá nhẹ làm biên độ nhỏ, dễ nhiễu;
- lực ép quá mạnh làm tín hiệu méo và dễ bão hòa cục bộ;
- rung tay hoặc gõ tay tạo nhiễu cơ học mạnh, xuất hiện baseline wander và đỉnh giả.

Những quan sát này là dữ kiện đầu tiên dẫn đến quyết định sau này phải có scheduler thích nghi thay vì dùng một pipeline cố định cho mọi tình huống.

### 4.2. Ảnh hưởng của cấu hình cảm biến

Part A tập trung khảo sát bốn nhóm tham số chính của MAX30102:

- `sample rate`;
- `pulse width`;
- `sample averaging`;
- `LED current`.

Mục tiêu không phải là tìm một bộ tham số “đẹp nhất” theo trực giác, mà là hiểu trade-off giữa chất lượng tín hiệu và chi phí năng lượng.

Kết quả thực nghiệm cho thấy:

- tăng `sample rate` giúp bám động học tốt hơn nhưng làm tăng dữ liệu phải xử lý và thường kéo theo tăng tiêu thụ;
- tăng `LED current` có thể cải thiện biên độ tín hiệu khi tiếp xúc yếu, nhưng nếu quá cao lại dễ đẩy hệ vào vùng bão hòa hoặc lãng phí năng lượng;
- `averaging` cao làm tín hiệu mượt hơn nhưng đồng thời làm thay đổi tốc độ hiệu dụng và đặc tính phản ứng của dữ liệu;
- `pulse width` tác động tới năng lượng mỗi xung và độ phân giải ADC, nên phải chọn cân bằng với mục tiêu đo.

Bài học rút ra là không tồn tại một cấu hình cố định duy nhất tối ưu cho mọi trạng thái tiếp xúc. Đây là nền tảng trực tiếp của ý tưởng `NORMAL profile` và `HIGH profile` ở Part B.

### 4.3. Ước lượng BPM cơ bản

Từ tín hiệu PPG thô, firmware và notebook thực hiện một pipeline đơn giản gồm:

- bỏ thành phần nền hoặc xu thế chậm;
- làm nổi thành phần dao động chứa nhịp tim;
- dò đỉnh hoặc dùng tương quan để suy ra chu kỳ tim;
- đổi chu kỳ thành BPM.

Trong điều kiện nghỉ và tiếp xúc ổn định, cách làm này cho ra BPM hợp lý. Ý nghĩa của kết quả này rất quan trọng: nó chứng minh rằng phần cứng và cảm biến đủ tốt để cung cấp một baseline DSP thực thụ, không phải chỉ cho ra “sóng đẹp” nhưng vô dụng.

### 4.4. Giới hạn của phương pháp BPM cơ bản

Tuy nhiên, Part A cũng cho thấy rõ giới hạn của pipeline này. Peak detection và autocorrelation hoạt động tốt khi điều kiện đo thuận lợi, nhưng suy giảm nhanh khi xuất hiện:

- chuyển động ngón tay;
- thay đổi lực ép;
- nhấc tay hoặc chạm không đủ chặt;
- dao động cơ học tuần hoàn gây đỉnh giả.

Điểm này cần được nhấn mạnh để nối sang Part B: BPM cơ bản của Part A là một baseline hữu ích, nhưng chưa phải lời giải đủ mạnh cho một wearable hoạt động trong điều kiện thật.

---

## 5. Đo năng lượng với INA219

### 5.1. Mục tiêu của phép đo năng lượng

Phép đo năng lượng trong Part A có hai vai trò khác nhau theo từng giai đoạn phát triển:

- ở giai đoạn đầu, nó giúp hiểu đặc tính tiêu thụ của riêng MAX30102 dưới các cấu hình khác nhau;
- ở giai đoạn sau, nó trở thành công cụ để đánh giá chi phí thật của toàn hệ thống khi có DSP, TinyML và adaptive scheduling.

Việc phân biệt hai mục tiêu này là cần thiết. Nếu chỉ đo nhánh cảm biến, có thể trả lời câu hỏi “MAX30102 tiêu thụ bao nhiêu”, nhưng không thể trả lời câu hỏi quan trọng hơn của đề tài là “toàn bộ node đeo tiêu thụ bao nhiêu khi đổi chiến lược xử lý”.

### 5.2. Telemetry và logging

Firmware tích hợp ghi lại đồng thời:

- timestamp;
- trạng thái hoặc profile vận hành;
- các tín hiệu `RED/IR`;
- `bus voltage`, `current`, `power` từ INA219.

Thiết kế log đồng bộ này là quyết định kỹ thuật quan trọng. Nhờ nó, notebook không chỉ nhìn thấy năng lượng hay tín hiệu một cách riêng rẽ, mà có thể so sánh trực tiếp: tại thời điểm tín hiệu xấu đi thì power thay đổi thế nào, khi đổi profile thì power có tăng tương ứng hay không, và liệu các lần chuyển trạng thái có gây chi phí phụ không.

### 5.3. Vì sao phải chuyển sang whole-system power

Kết quả debug qua các vòng log sau này xác nhận rằng chuyển từ đo nhánh cảm biến sang đo `whole-system power` là bắt buộc. Các chênh lệch giữa `DSP-only`, `AI-assisted`, và `adaptive` chủ yếu nằm ở phần chi phí của chính ESP32-S3, không chỉ ở LED hay ADC của MAX30102.

Nói cách khác, nếu vẫn giữ cách đo cũ thì kết luận năng lượng sẽ bị thiên lệch. Part A vì vậy không chỉ xây phần cứng, mà còn xây đúng cách đo cho câu hỏi nghiên cứu của Part B.

---

## 6. Tích hợp toàn hệ thống

### 6.1. Ghép bus I2C dùng chung

ESP32-S3 giao tiếp với cả MAX30102 và INA219 trên cùng một bus I2C. Điều này giúp kiến trúc gọn, đúng với bối cảnh embedded thực tế, nhưng đồng thời buộc firmware phải quản lý truy cập thiết bị cẩn thận. Khi hệ thống còn đơn giản ở Part A, việc này chủ yếu là kiểm tra đúng địa chỉ và thứ tự cấu hình. Sang Part B, đây chính là nền để tách sensor task và AI task mà không làm hỏng truy cập ngoại vi.

### 6.2. Hai cấu hình nối ghép đã sử dụng

Trong suốt quá trình làm đề tài, hai cấu hình wiring sau đều có giá trị, nhưng phục vụ hai mục tiêu khác nhau.

#### Cách 1: Đo nhánh cảm biến MAX30102

INA219 được đặt trên đường cấp nguồn của MAX30102. Cách làm này phù hợp cho việc khảo sát cảm biến ở mức vi mô, ví dụ khi thay đổi `LED current` hoặc `sample rate` và muốn biết riêng cảm biến tăng thêm bao nhiêu điện.

#### Cách 2: Đo công suất toàn hệ thống

Sau khi chuyển sang đánh giá adaptive scheduling, wiring được đổi sang cấu hình cuối cùng:

`PC USB 5V -> INA219 -> ESP32 VIN 5V`

với:

- `ESP32 3V3 -> MAX30102`;
- `ESP32 3V3 -> INA219 logic`;
- toàn hệ thống dùng chung `GND`.

Đây là cấu hình đúng với câu hỏi nghiên cứu cuối cùng và là cấu hình được dùng cho các log macro-level đã chốt ở V6. Cách nối này cũng khớp với block diagram mới: INA219 vừa là một `I2C slave`, vừa là phần tử nằm trên đường năng lượng đang được giám sát.

### 6.3. Ý nghĩa phương pháp luận

Việc thay đổi cách nối ghép không phải là một chi tiết phụ của phần cứng, mà là một bước hiệu chỉnh phương pháp. Nó cho thấy cùng một bộ phần cứng có thể cho ra kết luận rất khác nếu đo sai đại lượng cần đo. Part A vì vậy đóng góp không chỉ ở mức “lắp mạch chạy được”, mà còn ở mức xây đúng nền đo lường cho giai đoạn đánh giá thuật toán sau này.

---

## 7. Kết quả đạt được và bài học thiết kế

### 7.1. Kết quả đạt được

Đến cuối Part A, prototype đã đạt được các kết quả cốt lõi sau:

- ESP32-S3 giao tiếp ổn định với MAX30102 và INA219 qua I2C;
- log được đồng thời tín hiệu quang và telemetry năng lượng;
- quan sát được tín hiệu PPG thật và suy ra BPM cơ bản trong điều kiện nghỉ;
- xác nhận được rằng cấu hình cảm biến ảnh hưởng đồng thời tới chất lượng tín hiệu và chi phí năng lượng;
- xây được một firmware tích hợp đủ tốt để làm nền cho notebook phân tích và các bước tối ưu tiếp theo.

### 7.2. Bài học thiết kế rút ra từ thực nghiệm tín hiệu và công suất

Từ toàn bộ thí nghiệm Part A, có bốn bài học quan trọng.

Thứ nhất, MAX30102 rất nhạy với điều kiện tiếp xúc. Tín hiệu thay đổi mạnh theo lực ép, vị trí đặt tay và chuyển động cơ học, nên mọi kết luận dựa trên một điều kiện đặt tay đơn lẻ đều dễ bị thiên lệch.

Thứ hai, các tham số như `sample rate`, `averaging`, `pulse width` và `LED current` ảnh hưởng đồng thời tới cả chất lượng tín hiệu lẫn năng lượng. Không có một cấu hình cố định vừa tối ưu cho mọi điều kiện đo vừa tối ưu cho pin.

Thứ ba, cách đo năng lượng phải tiến hóa cùng câu hỏi nghiên cứu. Đo nhánh cảm biến là đúng cho giai đoạn hiểu MAX30102, nhưng không đủ cho giai đoạn đánh giá scheduler và TinyML. Việc chuyển sang đo `whole-system power` là bắt buộc nếu muốn kết luận đúng ở mức hệ thống.

Thứ tư, Part A đã xác nhận phần cứng sẵn sàng, nhưng cũng cho thấy rõ những gì phần cứng thuần chưa giải quyết được: motion artifact, chất lượng tín hiệu thay đổi mạnh theo bối cảnh, và chi phí năng lượng không thể tối ưu bằng một cấu hình tĩnh.

---

## 8. Vai trò của Part A đối với phần đánh giá năng lượng sau này

Các kết quả macro-level cuối cùng ở notebook `ppg_hr_macro_analysis.ipynb` và các artifact `V6` không xuất hiện từ đầu. Chúng dựa trực tiếp trên ba nền tảng được xây ở Part A:

- nền tảng phần cứng đủ ổn định để chạy lâu và ghi log nhiều phiên;
- nền tảng telemetry đủ đồng bộ để đối chiếu tín hiệu với năng lượng;
- nền tảng wiring đủ đúng để đo chi phí thật của toàn bộ node.

Nói cách khác, Part B chỉ có thể bảo vệ được các con số năng lượng cuối cùng vì Part A đã làm xong phần việc khó hơn tưởng tượng: chuẩn hóa hệ đo và chuẩn hóa cách quan sát hệ thống.

---

## 9. Hạn chế của Part A và động cơ chuyển sang Part B

Mặc dù prototype ở Part A đã chứng minh được khả năng đọc tín hiệu PPG, ước lượng BPM cơ bản và ghi lại telemetry năng lượng, vẫn còn ba hạn chế lớn cần giải quyết ở giai đoạn tiếp theo.

### 9.1. Hạn chế về độ bền vững của thuật toán

Pipeline BPM hiện tại chủ yếu dựa trên peak detection và xử lý tín hiệu đơn giản. Cách làm này phù hợp để kiểm chứng cảm biến, nhưng chưa đủ mạnh khi người dùng thay đổi lực ép, rung tay hoặc tạo motion artifact tuần hoàn.

### 9.2. Hạn chế của cấu hình tĩnh

Kết quả Part A cho thấy không có một cấu hình MAX30102 cố định nào vừa tiết kiệm năng lượng vừa luôn cho tín hiệu tốt trong mọi điều kiện. Điều này dẫn trực tiếp tới ý tưởng phải có nhiều profile vận hành và một bộ điều phối quyết định khi nào dùng profile nào.

### 9.3. Động cơ trực tiếp sang Part B

Từ các kết quả ở Part A, bài toán ở giai đoạn tiếp theo không còn là “đọc được tín hiệu”, mà là:

- khi nào tín hiệu đủ tốt để chỉ dùng DSP nhẹ;
- khi nào cần nâng profile cảm biến và dùng pipeline mạnh hơn;
- làm sao để việc chuyển đổi đó thực sự tạo ra lợi ích năng lượng ở mức toàn hệ thống.

Đó chính là lý do Part B tập trung vào adaptive scheduling, TinyML và đánh giá `whole-system power` bằng các bộ log V2-V6. Nếu diễn đạt ngắn gọn, Part A tạo ra nền phần cứng và nền đo lường; Part B khai thác hai nền đó để tối ưu hệ thống ở mức vận hành thật.
