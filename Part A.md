# PHẦN A: XÂY DỰNG VÀ KIỂM CHỨNG NGUYÊN MẪU PHẦN CỨNG

## 1. Giới thiệu

Sau giai đoạn tìm hiểu đề tài, nghiên cứu xác định rằng phần nguyên mẫu phần cứng không chỉ có nhiệm vụ “đọc được cảm biến”, mà phải tạo ra một nền thực nghiệm đủ tin cậy để đánh giá bài toán điều phối thích nghi theo năng lượng ở giai đoạn sau. Vì vậy, Phần A tập trung vào ba mục tiêu chính: xây dựng hệ phần cứng có thể thu tín hiệu PPG ổn định, tích hợp kênh đo công suất, và tổ chức logging đủ nhất quán để phục vụ phân tích offline.

Điểm cốt lõi của giai đoạn này là tạo ra một hệ thống có thể quan sát đồng thời hai đại lượng vốn thường bị tách rời trong các bài toán thử nghiệm nhỏ: chất lượng tín hiệu sinh lý và chi phí năng lượng. Điều đó giúp phần đánh giá ở Phần B không bị rơi vào tình trạng mô hình tốt nhưng không biết hệ thống thực sự tiêu thụ bao nhiêu điện, hoặc đo được công suất nhưng không gắn được với trạng thái thực của tín hiệu.

## 2. Phân tích vai trò của các thành phần trong đề tài

### 2.1. Thành phần Energy-Aware

Trong đề tài này, “energy-aware” không nên được hiểu đơn giản là giảm tần suất hoạt động càng nhiều càng tốt. Nghiên cứu xem đây là một bài toán đánh đổi giữa mức tiêu thụ năng lượng và khả năng duy trì giám sát sức khỏe ở mức chấp nhận được. Muốn đạt được điều đó, hệ thống phải đo được năng lượng của từng chế độ vận hành và phải phân biệt được khi nào nên dùng pipeline nhẹ, khi nào phải dùng pipeline mạnh.

Ngay từ Part A, điều này đã dẫn tới yêu cầu tích hợp một kênh đo công suất trực tiếp trên phần cứng, thay vì chỉ ước lượng chi phí từ thông số kỹ thuật của linh kiện.

### 2.2. Thành phần Wearable Health Monitoring

Thiết bị được định hướng cho ngữ cảnh wearable health monitoring, nên các ràng buộc không chỉ là đọc được tín hiệu mà còn bao gồm:

- nguồn năng lượng hạn chế;
- môi trường đo có nhiễu do chuyển động;
- tiếp xúc cảm biến không luôn ổn định;
- yêu cầu theo dõi kéo dài và gần liên tục.

Những ràng buộc này làm cho việc xây dựng nguyên mẫu phần cứng trở thành một bước có ý nghĩa học thuật rõ ràng. Nó buộc nghiên cứu phải chuyển từ cách tiếp cận “đo được trong điều kiện lý tưởng” sang “đo được trên một hệ có thể phát triển thành kiến trúc điều phối thích nghi”.

## 3. Các thành phần phần cứng

### 3.1. Cảm biến MAX30102

MAX30102 là cảm biến quang dùng để thu tín hiệu quang thể tích đồ (PPG). Cảm biến tích hợp LED đỏ, LED hồng ngoại, photodiode và khối xử lý quang học mức thấp, đồng thời hỗ trợ giao tiếp I2C với vi điều khiển. Tín hiệu đầu ra của MAX30102 không phải là nhịp tim trực tiếp, mà là chuỗi mẫu quang theo thời gian cần được xử lý tiếp để suy ra BPM hoặc các đặc trưng liên quan.

Điểm quan trọng của MAX30102 trong đề tài này là khả năng cấu hình được nhiều tham số vận hành như:

- tốc độ lấy mẫu;
- độ rộng xung;
- số lần lấy trung bình;
- dòng kích LED.

Các tham số này tác động trực tiếp đến cả chất lượng tín hiệu lẫn mức tiêu thụ điện, do đó có vai trò rất quan trọng đối với tư tưởng điều phối thích nghi ở Phần B.

### 3.2. Cảm biến INA219

INA219 là mạch đo điện áp, dòng điện và công suất qua giao tiếp I2C. Vai trò của INA219 trong nghiên cứu không chỉ là một thiết bị phụ trợ, mà là thành phần cho phép định lượng bài toán tiết kiệm năng lượng một cách thực nghiệm. Nếu không có INA219, mọi kết luận về việc adaptive scheduling giúp tiết kiệm điện sẽ chỉ dừng ở mức giả định.

Một điểm đáng chú ý được rút ra ngay từ giai đoạn Part A là vị trí đặt INA219 trên đường nguồn quyết định trực tiếp ý nghĩa của kết quả đo. Đo trên nhánh cảm biến và đo trên toàn hệ thống là hai phép đo khác nhau về bản chất, phục vụ hai câu hỏi nghiên cứu khác nhau.

### 3.3. ESP32-S3

ESP32-S3 là phần tử xử lý trung tâm của hệ thống. Trong nguyên mẫu phần cứng, vi điều khiển này đảm nhiệm:

- khởi tạo và điều khiển bus I2C;
- cấu hình MAX30102 và đọc dữ liệu `RED/IR`;
- đọc telemetry năng lượng từ INA219;
- ghi log ra UART;
- làm nền tảng triển khai DSP, scheduler và TinyML ở các giai đoạn sau.

Việc lựa chọn ESP32-S3 có ý nghĩa quan trọng vì đây là môi trường triển khai thực của toàn bộ bài toán. Các quyết định về cảm biến, dữ liệu và mô hình đều phải phù hợp với giới hạn tài nguyên và hành vi thời gian thực của vi điều khiển này.

## 4. Kiến trúc hệ thống và hai cấu hình đo năng lượng

Về mặt khối chức năng, hệ thống gồm một nút xử lý trung tâm ESP32-S3, một cảm biến PPG MAX30102 và một mạch đo năng lượng INA219. ESP32-S3 đóng vai trò `I2C master`, còn MAX30102 và INA219 là các thiết bị `I2C slave`. Dữ liệu được thu nhận và ghi log đồng bộ để có thể phân tích ngoài tuyến.

[Ghi chú biên tập: Tái sử dụng sơ đồ khối tổng thể đã có trong PDF báo cáo tiến độ cũ cho Hình A.1. Nếu cần vẽ lại, xem hướng dẫn tại `report_diagram_guides.md`.]

### 4.1. Cấu hình đo nhánh cảm biến

Ở giai đoạn khảo sát đặc tính phần cứng, INA219 được đặt trên nhánh cấp nguồn của riêng MAX30102. Cách đo này hữu ích khi cần trả lời các câu hỏi dạng:

- tăng dòng LED làm riêng cảm biến tiêu thụ thêm bao nhiêu;
- thay đổi tốc độ lấy mẫu ảnh hưởng thế nào tới năng lượng của cảm biến;
- chế độ lấy trung bình làm thay đổi quan hệ giữa chất lượng tín hiệu và công suất ra sao.

Đây là phép đo phù hợp cho giai đoạn “hiểu cảm biến”.

### 4.2. Cấu hình đo công suất toàn hệ thống

Khi nghiên cứu chuyển sang mục tiêu đánh giá adaptive scheduling, phép đo trên nhánh cảm biến không còn đủ. Lý do là phần chênh lệch năng lượng quan trọng lúc này không chỉ đến từ MAX30102, mà còn đến từ:

- xử lý DSP trên ESP32-S3;
- trích chọn đặc trưng;
- suy luận TinyML;
- logging và điều phối trạng thái.

Vì vậy, hệ thống được chuyển sang cấu hình đo công suất toàn hệ thống, trong đó đường nguồn của toàn node đi qua shunt của INA219 trước khi cấp vào vi điều khiển. Đây là cơ sở phương pháp luận để các kết quả macro-level ở Phần B phản ánh đúng chi phí vận hành của toàn bộ node, thay vì chỉ phản ánh một thành phần riêng lẻ.

[Ghi chú biên tập: Hình A.3 nên dùng sơ đồ hai cấu hình đo năng lượng đặt cạnh nhau. Có thể vẽ lại nhanh theo ASCII và hướng dẫn trong `report_diagram_guides.md`.]

## 5. Quy trình tích hợp và kiểm chứng các mô-đun

### 5.1. Kiểm chứng giao tiếp I2C

Bước đầu tiên của quá trình tích hợp là xác nhận từng ngoại vi hoạt động ổn định trên bus I2C. Nghiên cứu kiểm tra khả năng nhận diện thiết bị, ghi-đọc thanh ghi cấu hình và đọc dữ liệu lặp lại trong thời gian đủ dài. Việc kiểm chứng này có ý nghĩa nền tảng, vì nếu lớp giao tiếp phần cứng không ổn định thì các đánh giá tín hiệu và năng lượng đều không đáng tin cậy.

### 5.2. Thu nhận tín hiệu PPG

Sau khi giao tiếp ổn định, hệ thống được dùng để thu dữ liệu quang theo thời gian thực. Nghiên cứu quan sát đồng thời hai kênh `RED` và `IR`, từ đó nhận thấy thành phần nền lớn và thành phần dao động nhỏ mang thông tin nhịp tim. Trong điều kiện tiếp xúc tốt, tín hiệu tạo ra dạng sóng có chu kỳ hợp lý và đủ rõ để suy ra nhịp tim cơ bản.

![Hình A.2. Dạng sóng PPG điển hình trong điều kiện đặt tay ổn định](artifacts/report_assets/part_a_ppg_waveform_stable.png)

Hình A.2 được trích trực tiếp từ log ổn định của MAX30102, thể hiện rõ thành phần dao động tuần hoàn của kênh quang. Đây là bằng chứng thực nghiệm cho thấy nguyên mẫu phần cứng đã đủ tốt để xây dựng một baseline DSP ở điều kiện nghỉ.

### 5.3. Ghi telemetry năng lượng đồng bộ với tín hiệu

Một điểm mạnh của nguyên mẫu là dữ liệu tín hiệu và dữ liệu năng lượng không được thu tách rời, mà được ghi trên cùng một trục thời gian. Cách tổ chức này giúp phân tích offline có thể đối chiếu trực tiếp giữa chất lượng tín hiệu và mức tiêu thụ điện trong từng cấu hình vận hành. Đây chính là cầu nối giữa Part A và bài toán điều phối thích nghi ở Part B.

## 6. Khảo sát tín hiệu PPG và các tham số cấu hình cảm biến

### 6.1. Ảnh hưởng của sample rate, LED current, averaging và pulse width

Thực nghiệm cho thấy bốn nhóm tham số cấu hình chính của MAX30102 ảnh hưởng đồng thời tới cả tín hiệu PPG và chi phí năng lượng:

- `sample rate`;
- `LED current`;
- `sample averaging`;
- `pulse width`.

Nghiên cứu rút ra rằng các tham số này không nên được xem như những nút chỉnh độc lập chỉ để làm “đẹp” tín hiệu. Mỗi thay đổi đều kéo theo một đánh đổi giữa độ rõ của dạng sóng, độ nhạy với chuyển động, lượng dữ liệu phải xử lý và mức công suất tiêu thụ.

### 6.2. Ước lượng BPM cơ bản

Từ tín hiệu PPG thô, hệ thống xây dựng một pipeline DSP cơ bản để:

- loại bỏ xu thế nền chậm;
- làm nổi phần dao động mang thông tin nhịp tim;
- dò đỉnh hoặc dùng tương quan để suy ra chu kỳ;
- đổi chu kỳ thành BPM.

Trong điều kiện nghỉ, pipeline này cho kết quả hợp lý. Điều đó xác nhận rằng nguyên mẫu phần cứng không chỉ tạo ra dữ liệu thô, mà đã đủ để xây dựng một baseline xử lý nhịp tim có giá trị thực nghiệm.

### 6.3. Giới hạn của BPM cơ bản

Tuy nhiên, nghiên cứu cũng ghi nhận rõ rằng BPM cơ bản suy giảm nhanh khi điều kiện đo trở nên khó hơn, chẳng hạn khi:

- thay đổi lực ép;
- tiếp xúc lỏng;
- rung tay;
- xuất hiện dao động cơ học tuần hoàn.

Điểm này có vai trò như một kết luận chuyển tiếp: nguyên mẫu phần cứng đã đủ để chứng minh khả năng đo, nhưng chưa đủ để giải quyết bài toán wearable trong điều kiện thực. Chính giới hạn này là động lực trực tiếp của adaptive scheduling và TinyML ở Phần B.

## 7. Kết quả chính của Phần A và bài học thiết kế

### 7.1. Kết quả đạt được

Đến cuối Part A, hệ nguyên mẫu đã đạt được các kết quả quan trọng sau:

- ESP32-S3 giao tiếp ổn định với MAX30102 và INA219;
- hệ thống thu được tín hiệu PPG có ý nghĩa;
- BPM cơ bản có thể được suy ra trong điều kiện tiếp xúc thuận lợi;
- telemetry năng lượng được ghi đồng bộ với tín hiệu;
- phương pháp đo năng lượng đã tiến hóa từ cảm biến riêng lẻ sang toàn node.

### 7.2. Bài học thiết kế

Từ các thực nghiệm phần cứng, nghiên cứu rút ra bốn bài học lớn.

Thứ nhất, tín hiệu PPG rất nhạy với điều kiện tiếp xúc, do đó mọi đánh giá trên thiết bị đeo đều phải tính đến yếu tố nhiễu cơ học. Thứ hai, các tham số cấu hình của cảm biến tạo ra đánh đổi trực tiếp giữa chất lượng tín hiệu và năng lượng, nên không tồn tại một cấu hình tĩnh tối ưu cho mọi điều kiện. Thứ ba, phương pháp đo năng lượng phải được thiết kế cùng với câu hỏi nghiên cứu; đo sai vị trí sẽ dẫn tới kết luận sai. Thứ tư, phần cứng nguyên mẫu chỉ là điều kiện cần; để giải quyết bài toán cuối cùng cần có thêm một cơ chế chọn chiến lược xử lý theo trạng thái thực của tín hiệu.

## 8. Hạn chế của Phần A và động cơ chuyển sang Phần B

Mặc dù Part A đã xác lập được nền phần cứng và hệ đo, giai đoạn này vẫn còn ba giới hạn lớn.

Trước hết, pipeline BPM cơ bản chưa đủ bền vững trước chuyển động và biến thiên tiếp xúc. Tiếp theo, cấu hình cảm biến tĩnh không thể đồng thời tối ưu cả chất lượng tín hiệu lẫn năng lượng cho mọi tình huống. Cuối cùng, việc đã đo được công suất toàn hệ thống mới chỉ tạo ra điều kiện đánh giá, chứ chưa tạo ra cơ chế thực sự để giảm công suất đó.

Do đó, Part B kế thừa trực tiếp nền tảng của Part A và giải quyết phần còn thiếu: xây dựng adaptive scheduler, tích hợp TinyML và đánh giá xem việc chuyển đổi giữa các profile vận hành có thực sự đem lại lợi ích năng lượng ở cấp hệ thống hay không.
