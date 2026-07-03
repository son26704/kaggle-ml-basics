# Script thuyết trình đồ án tốt nghiệp 20225225

Ghi chú sử dụng: bản này viết cho khoảng **11–12 phút trình bày**, để lại khoảng **3–4 phút phản biện** trong tổng thời lượng 15 phút. Slide 5 trong file PowerPoint đang bị ẩn nên được bỏ qua. Slide 14 và slide 15 đang gần như trùng nhau; trong script này, slide 14 dùng để trình bày kết quả, slide 15 dùng để nhấn mạnh hàm ý và chuẩn bị phản biện.

## Slide 1 — Mở đầu HUST

Kính thưa các thầy cô trong hội đồng, em xin phép bắt đầu phần trình bày đồ án tốt nghiệp của mình.

Đồ án của em nằm ở giao điểm giữa **AIoT**, **hệ nhúng** và **trí tuệ nhân tạo ứng dụng**. Trọng tâm của đồ án không chỉ là huấn luyện một mô hình AI, mà là đưa mô hình đó vào một hệ thống nhúng có cảm biến thật, có giới hạn năng lượng thật, và có cơ chế quyết định khi nào nên dùng xử lý nhẹ, khi nào nên kích hoạt xử lý mạnh hơn.

## Slide 2 — Tên đề tài

Đề tài của em là: **“Nghiên cứu và phát triển bộ điều phối TinyML thích nghi nhằm cân bằng khả năng theo dõi nhịp tim và năng lượng cho hệ thống giám sát sức khỏe đeo được.”**

Ý chính của tên đề tài có ba phần.

Thứ nhất là **theo dõi nhịp tim** từ tín hiệu PPG, tức tín hiệu quang học thường dùng trong vòng tay hoặc đồng hồ thông minh.

Thứ hai là **TinyML**, nghĩa là mô hình học máy được lượng tử hóa và chạy trực tiếp trên vi điều khiển, cụ thể trong đồ án là ESP32-S3.

Thứ ba, và cũng là phần quan trọng nhất của đồ án, là **bộ điều phối thích nghi**. Bộ điều phối này quyết định lúc nào hệ thống chỉ cần xử lý tín hiệu nhẹ để tiết kiệm năng lượng, và lúc nào tín hiệu khó hơn thì cần chuyển sang nhánh xử lý tăng cường có TinyML hỗ trợ.

## Slide 3 — Bài toán

Bài toán xuất phát từ một mâu thuẫn rất thực tế trong thiết bị đeo: thiết bị cần **theo dõi liên tục**, nhưng pin lại có giới hạn.

Với tín hiệu **PPG**, cảm biến không đo trực tiếp điện tim như ECG, mà đo biến thiên ánh sáng phản xạ hoặc truyền qua mô, liên quan đến thay đổi thể tích máu theo nhịp tim. Vì vậy tín hiệu PPG rất nhạy với **chuyển động**, **áp lực tiếp xúc**, **vị trí đặt cảm biến** và nhiễu môi trường.

Khi tín hiệu tốt, một pipeline xử lý tín hiệu số nhẹ, ví dụ lọc, tìm đỉnh và autocorrelation, có thể đủ để đưa ra nhịp tim. Nhưng khi tín hiệu xấu, các phương pháp đơn giản này dễ bị sai hoặc không đủ tin cậy. Khi đó, mô hình **TinyML** có thể hỗ trợ vì nó học quan hệ từ nhiều đặc trưng của cửa sổ tín hiệu.

Tuy nhiên, nếu luôn chạy TinyML và luôn chạy cấu hình cảm biến mạnh, hệ thống sẽ tốn năng lượng không cần thiết. Vì vậy câu hỏi nghiên cứu của em là: **khi nào nên dùng xử lý nhẹ, và khi nào nên kích hoạt TinyML?**

Thông điệp của slide này là đồ án không tối ưu một cực trị. Em không cố làm hệ thống tiết kiệm nhất bằng mọi giá, cũng không cố đạt coverage cao nhất bằng mọi giá. Mục tiêu là tạo một **điểm vận hành trung gian có kiểm soát** giữa năng lượng và khả năng duy trì đầu ra nhịp tim.

## Slide 4 — Mục tiêu và đóng góp

Ở slide này em tóm tắt mục tiêu và đóng góp chính của đồ án.

Về mục tiêu, em xây dựng một prototype gồm ESP32-S3 và cảm biến **MAX30102** để thu tín hiệu PPG. Trên ESP32-S3, em triển khai mô hình **MLP INT8** bằng **TensorFlow Lite Micro**. Hệ thống có hai trạng thái vận hành là **NORMAL** và **ENHANCED**. Bên cạnh đó, em xây dựng một node đo công suất riêng dùng ESP32 và cảm biến **INA219** để ghi lại công suất tiêu thụ.

Về đóng góp, điểm chính không phải chỉ là “đưa AI xuống MCU”, mà là **kiểm soát thời điểm dùng AI**. Cụ thể, đồ án có hai nhánh xử lý với chi phí khác nhau: nhánh nhẹ và nhánh tăng cường. Một **quality gate** đánh giá chất lượng từng cửa sổ PPG, sau đó scheduler quyết định giữ nguyên hoặc chuyển trạng thái.

Em đánh giá hệ thống ở hai mức. Mức **macro** là toàn phiên đo, so sánh công suất trung bình và HR coverage giữa Fixed Normal, Adaptive và Fixed Enhanced. Mức **micro** là từng burst xử lý tăng cường, để xem phần TinyML thực sự chiếm bao nhiêu năng lượng.

## Slide 6 — Kiến trúc phần cứng

Đây là kiến trúc phần cứng của hệ thống.

Hệ thống có hai node chính. Node thứ nhất là **target node**, gồm ESP32-S3 và cảm biến MAX30102. ESP32-S3 đọc MAX30102 qua bus **I2C**. Trong firmware hiện tại, đường I2C của target dùng **GPIO8 làm SDA** và **GPIO9 làm SCL**.

Node thứ hai là **DAQ node**, dùng một ESP32 khác để đo công suất. Node này đọc cảm biến **INA219** qua I2C, trong firmware là **GPIO21 SDA** và **GPIO22 SCL**. Nguồn 5V cấp cho target đi qua INA219 trước, nên INA219 đo được điện áp bus, dòng điện và công suất của target node.

Ngoài đường đo công suất, target còn xuất hai tín hiệu đồng bộ bằng GPIO. **GPIO10** được bật trong giai đoạn trích chọn đặc trưng, còn **GPIO11** được bật trong giai đoạn gọi TinyML Invoke. DAQ đọc hai tín hiệu này ở **GPIO4** và **GPIO5**. Nhờ vậy, khi phân tích log, em biết đoạn công suất nào tương ứng với feature extraction và đoạn nào tương ứng với inference.

Một điểm em muốn nhấn mạnh là DAQ chỉ **quan sát**. Nó không tham gia vào quyết định scheduler. Nếu để target node tự đo và in log, chính thao tác đó sẽ làm sai lệch công suất tiêu thụ thật. DAQ node ở đây chỉ thuần túy quan sát và hoàn toàn cách ly khỏi logic điều phối của hệ thống. Quyết định NORMAL hay ENHANCED hoàn toàn nằm trên target node.

Nếu hội đồng hỏi sơ đồ nối mạch, em sẽ trả lời rằng báo cáo có mô tả kết nối chính ở phần phần cứng và phụ lục; về nguyên lý, mạch gồm ba nhóm dây: **I2C target–MAX30102**, **I2C DAQ–INA219**, và **hai dây sync GPIO từ target sang DAQ**, cộng với mass chung và đường nguồn 5V đi qua INA219.

## Slide 7 — Luồng xử lý

Slide này mô tả luồng xử lý end-to-end của hệ thống.

Từ cảm biến MAX30102, target node lấy tín hiệu PPG, trong firmware chủ yếu dùng kênh **IR**. Tín hiệu được đưa vào ring buffer. Khi đủ một cửa sổ 8 giây và đi qua một stride 2 giây, task xử lý được đánh thức.

Ở trạng thái **NORMAL**, hệ thống đi theo **Fast Path**. Fast Path dùng các bước DSP nhẹ: detrend, lọc thông dải đơn giản, chuẩn hóa, tìm đỉnh và autocorrelation. Từ đó hệ thống lấy các chỉ số như biên độ, độ tuần hoàn và nhịp tim ước lượng.

Nếu tín hiệu đạt yêu cầu, hệ thống có thể xuất HR bằng DSP, không cần gọi TinyML. Nếu tín hiệu xấu liên tiếp, scheduler chuyển sang **ENHANCED**.

Ở trạng thái **ENHANCED**, hệ thống đi theo **Slow Path**. Lúc này cửa sổ PPG được đưa về biểu diễn cố định 512 mẫu, tương ứng 8 giây ở 64 Hz, sau đó trích **16 đặc trưng**, chuẩn hóa, lượng tử hóa và đưa vào mô hình MLP INT8.

Song song với đó, DAQ ghi công suất và hai chân sync. Vì vậy sau thí nghiệm, em có thể phân tích không chỉ hệ thống có hoạt động hay không, mà còn biết năng lượng đã tiêu ở phần nào.

## Slide 8 — Hai trạng thái vận hành

Hệ thống có hai trạng thái vận hành.

Trạng thái thứ nhất là **NORMAL**, hay Fast Path. Đây là trạng thái tiết kiệm hơn. Cảm biến chạy ở **50 Hz**, số mẫu trong cửa sổ 8 giây là 400 mẫu. Hệ thống chỉ dùng DSP nhẹ, tính quality metrics, tìm peak và autocorrelation. Điểm quan trọng là ở NORMAL, hệ thống **không gọi TinyML**.

Trạng thái thứ hai là **ENHANCED**, hay Slow Path. Ở trạng thái này, cảm biến tăng lên **100 Hz**, cửa sổ 8 giây có 800 mẫu. Sau đó firmware nội suy về 512 mẫu để tương thích với mô hình đã huấn luyện trên PPG-DaLiA 64 Hz. Hệ thống trích 16 đặc trưng, chuẩn hóa bằng scaler đã xuất từ notebook, lượng tử hóa input sang int8 và gọi mô hình MLP trên TensorFlow Lite Micro.

Việc chuyển trạng thái không xảy ra chỉ vì một cửa sổ đơn lẻ. Firmware dùng cơ chế kiểu **hysteresis**: cần đủ số cửa sổ xấu liên tiếp để đi lên ENHANCED, và đủ số cửa sổ tốt liên tiếp để quay về NORMAL. Cách này giúp tránh hệ thống bị nhảy trạng thái liên tục do nhiễu ngắn hạn.

## Slide 9 — Adaptive scheduler

Đây là phần lõi của đồ án: **adaptive scheduler**.

Quy tắc chính trên slide là: nếu có **4 cửa sổ xấu liên tiếp**, hệ thống chuyển lên ENHANCED. Nếu có **5 cửa sổ tốt liên tiếp**, hệ thống chuyển về NORMAL.

Quality gate không chỉ dựa vào một ngưỡng đơn giản. Nó kết hợp nhiều yếu tố. Thứ nhất là **biên độ**, thông qua các chỉ số như độ lệch chuẩn và peak-to-peak sau khi loại nền. Thứ hai là **tính chu kỳ**, thông qua autocorrelation. Thứ ba là **dải sinh lý**, tức HR ước lượng phải nằm trong khoảng hợp lý. Thứ tư là **sự đồng thuận** giữa peak-based HR và autocorrelation-based HR.

Nếu tín hiệu có biên độ bất thường, autocorrelation thấp hoặc hai phương pháp ước lượng nhịp tim lệch nhau quá nhiều, cửa sổ đó bị coi là khó hoặc xấu. Ngược lại, nếu tín hiệu có chu kỳ rõ và các estimator đồng thuận, hệ thống coi đó là cửa sổ tốt.

Mục đích của scheduler là giảm chuyển trạng thái giả. Ví dụ chỉ một cửa sổ bị nhiễu không đủ để chuyển sang ENHANCED ngay. Ngược lại, khi đã lên ENHANCED thì cũng cần nhiều cửa sổ tốt mới quay lại NORMAL. Đây là cách đánh đổi giữa **độ ổn định** và **khả năng phản ứng**.

## Slide 10 — Mô hình TinyML

Mô hình TinyML trong đồ án là một **MLP hồi quy nhịp tim**. Đầu vào là **16 đặc trưng** trích từ cửa sổ PPG, không phải raw waveform trực tiếp.

Kiến trúc được chọn trong notebook là **16 → 192 → 128 → 64 → 1**. Ba lớp ẩn lần lượt có 192, 128 và 64 neuron, đều dùng **ReLU**. Lớp đầu ra có 1 neuron tuyến tính để dự đoán HR đã chuẩn hóa. Trong huấn luyện có dropout và L2 regularization, nhưng dropout chỉ dùng khi train; khi chạy trên ESP32 thì dropout không còn hoạt động.

Tổng số tham số Keras trước lượng tử là **36.289**. Con số này khớp với kiến trúc Dense: lớp 16–192, lớp 192–128, lớp 128–64 và lớp 64–1, bao gồm cả bias.

Dữ liệu huấn luyện offline là **PPG-DaLiA**. Em chia tín hiệu thành cửa sổ **8 giây**, stride **2 giây**, thu được **64.697 cửa sổ** từ **15 subject**. Việc chia train, validation và test được thực hiện theo **subject**, nghĩa là người trong tập test không xuất hiện trong train. Cách chia GroupShuffleSplit theo subject này giúp triệt tiêu hiện tượng **rò rỉ dữ liệu (Data leakage)**, ép mô hình không được 'học vẹt' nhịp tim của một cá nhân, từ đó phản ánh đúng năng lực tổng quát hóa (Generalization) khi thiết bị được đeo bởi một người dùng hoàn toàn mới.

Sau huấn luyện, mô hình được chuyển sang **TFLite INT8** để nhúng vào ESP32-S3 bằng TensorFlow Lite Micro. Trong firmware, input và output là int8; firmware tự chuẩn hóa feature, lượng tử hóa input, gọi Invoke, sau đó giải lượng tử và đưa HR về đơn vị BPM.

## Slide 11 — Thiết kế đánh giá thực nghiệm

Đánh giá thực nghiệm của em gồm ba phần.

Phần thứ nhất là **offline model evaluation**. Ở đây em so sánh mô hình Random Forest baseline và MLP INT8 trên tập test PPG-DaLiA bằng MAE và RMSE. Mục tiêu của phần này là kiểm tra mô hình TinyML có đủ hợp lý để đưa vào Slow Path hay không.

Phần thứ hai là **macro evaluation**. Ở mức này, em chạy ba chế độ: Fixed Normal, Adaptive và Fixed Enhanced. Fixed Normal luôn chạy nhánh tiết kiệm, Fixed Enhanced luôn chạy nhánh tăng cường, còn Adaptive tự chuyển trạng thái. Em đo công suất trung bình và HR coverage toàn phiên.

Phần thứ ba là **micro evaluation**. Ở đây em tách riêng các burst ENHANCED bằng tín hiệu GPIO sync, sau đó ước lượng năng lượng của toàn burst và phần TinyML trong burst.

Một điểm rất quan trọng là **HR coverage không phải sai số y sinh**. Coverage chỉ là tỷ lệ cửa sổ mà hệ thống có đầu ra HR hợp lệ. Nó cho biết khả năng duy trì đầu ra của hệ thống, chứ không chứng minh rằng HR trên prototype đã đạt chuẩn lâm sàng.

## Slide 12 — Kết quả offline model

Kết quả offline cho thấy mô hình **MLP INT8** đạt sai số thấp hơn baseline Random Forest trên cùng tập test.

Random Forest đạt **MAE 8.44 BPM** và **RMSE 12.89 BPM**. MLP INT8 đạt **MAE 8.11 BPM** và **RMSE 12.61 BPM**. Mức cải thiện tương ứng khoảng **3,9% về MAE** và **2,2% về RMSE**.

Điểm em muốn nhấn mạnh không phải là MLP vượt trội rất lớn về độ chính xác. Chênh lệch là có, nhưng không quá lớn. Lý do MLP phù hợp hơn trong đồ án này là vì nó **dễ triển khai trên TensorFlow Lite Micro**, chỉ cần các toán tử Dense/FullyConnected, kích thước sau INT8 khoảng vài chục KB và phù hợp với tài nguyên MCU.

Vì vậy kết luận đúng ở slide này là: mô hình MLP INT8 **đủ phù hợp để đóng vai trò hỗ trợ trong Slow Path**, chứ không nên diễn giải rằng mô hình đã đạt độ chính xác y tế trên mọi điều kiện thực tế.

## Slide 13 — Kết quả macro

Đây là kết quả ở mức toàn phiên đo.

Ba điểm so sánh là Fixed Normal, Adaptive và Fixed Enhanced. Fixed Normal có công suất trung bình **261,78 mW** và HR coverage **46,23%**. Fixed Enhanced có công suất trung bình **286,94 mW** và coverage **89,31%**. Adaptive nằm giữa hai điểm này, với công suất **273,21 mW** và coverage **65,81%**.

So với Fixed Normal, Adaptive tăng công suất khoảng **11,43 mW**, tức khoảng **4,4%**, nhưng coverage tăng từ **46,23% lên 65,81%**, tức tăng **19,58 điểm phần trăm**.

So với Fixed Enhanced, Adaptive giảm công suất khoảng **4,79%**, nhưng coverage thấp hơn vì Adaptive không chạy nhánh mạnh liên tục.

Ý nghĩa của kết quả này là Adaptive đã tạo được một **điểm vận hành trung gian**. Nó không tốt hơn Fixed Normal về tiết kiệm năng lượng tuyệt đối, và cũng không tốt hơn Fixed Enhanced về coverage tuyệt đối. Nhưng nó đạt đúng mục tiêu của đồ án: **tăng khả năng duy trì đầu ra HR so với chế độ tiết kiệm, trong khi tránh chạy chế độ tăng cường liên tục**.

Nếu bị hỏi vì sao Adaptive chưa gần Fixed Enhanced hơn, em sẽ trả lời rằng scheduler hiện được thiết kế thận trọng, có hysteresis và chỉ chuyển khi đủ bằng chứng về chất lượng tín hiệu. Ngoài ra HR coverage ở đây phụ thuộc cả thuật toán DSP, điều kiện đo, tiếp xúc cảm biến và các ngưỡng quality gate.

## Slide 14 — Kết quả micro

Slide này đi sâu vào mức năng lượng từng burst xử lý tăng cường.

Kết quả cho thấy tổng năng lượng active của một burst ENHANCED nằm khoảng **1,39 đến 1,46 mJ**. Trong khi đó, phần TinyML ước lượng chỉ khoảng **33 đến 34 µJ**. Tỷ trọng TinyML chỉ khoảng **2,28% đến 2,45%** tổng năng lượng burst.

Điều này có nghĩa là phần gọi mô hình, tức `Invoke()`, **không phải thành phần chi phối năng lượng burst**. Phần chi phí lớn hơn nằm ở các bước xung quanh: chuẩn bị cửa sổ, DSP, trích chọn đặc trưng, chuyển dữ liệu, và đặc biệt là phần **power tail** sau burst – tức là khoảng thời gian nạp xả tụ điện và overhead của hệ điều hành trước khi chip thực sự trở về trạng thái ngủ sâu.

Về phương pháp đo, firmware target bật GPIO trong giai đoạn feature extraction và inference. DAQ đọc hai chân này cùng với công suất từ INA219. Vì vậy em có thể tách tương đối các đoạn xử lý. Tuy nhiên, năng lượng TinyML là **ước lượng gián tiếp**, không phải phép đo riêng biệt ở cấp transistor hay cấp peripheral bên trong chip.

Kết luận thực tế là nếu muốn tối ưu năng lượng tiếp theo, không nên chỉ tập trung ép mô hình nhỏ hơn nữa. Cần tối ưu toàn pipeline, đặc biệt là **DSP**, **feature extraction** và **power tail**.

## Slide 15 — Nhấn mạnh hàm ý của kết quả micro

Slide này đang nhắc lại kết quả micro, nên em dùng nó để nhấn mạnh hàm ý kỹ thuật.

Một suy nghĩ dễ mắc phải là: “TinyML tốn năng lượng, vậy tối ưu AI là đủ.” Nhưng kết quả của em cho thấy với cấu hình hiện tại, TinyML chỉ chiếm vài phần trăm năng lượng của burst. Điều này làm thay đổi hướng tối ưu.

Nếu muốn giảm năng lượng hơn nữa, em sẽ ưu tiên ba hướng.

Thứ nhất là giảm chi phí **feature extraction**, ví dụ rút gọn số đặc trưng, dùng đặc trưng rẻ hơn, hoặc chỉ tính một số đặc trưng khi thật sự cần.

Thứ hai là tối ưu **DSP implementation**, vì các bước lọc, autocorrelation, PSD và tìm đỉnh có thể tốn đáng kể CPU.

Thứ ba là giảm **power tail**, tức thời gian và năng lượng sau khi xử lý xong nhưng hệ thống chưa quay về mức tiêu thụ thấp.

Nói ngắn gọn, kết quả micro giúp em nhìn hệ thống theo hướng **system-level optimization**, không chỉ model-level optimization.

## Slide 16 — Tổng kết

Em xin tổng kết lại đồ án bằng ba nhóm ý.

Thứ nhất, về phần thực hiện, em đã xây dựng được prototype gồm **ESP32-S3**, **MAX30102** và node đo công suất dùng **INA219**. Trên target node, em triển khai pipeline PPG, mô hình **MLP INT8** chạy bằng TensorFlow Lite Micro, và scheduler hai trạng thái **NORMAL / ENHANCED**.

Thứ hai, về kết quả, Adaptive đạt **273,21 mW** và **65,81% HR coverage**. So với Fixed Normal, Adaptive tăng coverage đáng kể. So với Fixed Enhanced, Adaptive giảm công suất vì không duy trì nhánh mạnh liên tục. Ở mức micro, TinyML chỉ chiếm khoảng **2,28–2,45%** năng lượng burst, cho thấy bottleneck năng lượng không nằm riêng ở Invoke.

Thứ ba, về giới hạn, em chưa khẳng định hệ thống đạt độ chính xác y sinh lâm sàng. HR coverage không thay thế cho MAE đo trực tiếp trên prototype. Năng lượng TinyML là ước lượng gián tiếp qua xung DAQ. Ngoài ra, còn tồn tại domain shift giữa dữ liệu PPG-DaLiA dùng để huấn luyện và tín hiệu MAX30102 thu trên prototype.

Hướng phát triển tiếp theo là kiểm chứng trên nhiều người dùng hơn, đồng bộ golden-vector giữa notebook và firmware, tối ưu feature/DSP, và đánh giá thêm các chiến lược scheduler mềm hơn thay vì chỉ hai trạng thái.

Thông điệp cuối cùng của đồ án là: **AI trên thiết bị đeo không chỉ cần chạy được trên MCU, mà cần được lập lịch theo chất lượng tín hiệu và chi phí năng lượng.**

## Slide 17 — Cảm ơn

Em xin kết thúc phần trình bày tại đây. Em xin cảm ơn các thầy cô đã lắng nghe, và em rất mong nhận được câu hỏi cũng như góp ý từ hội đồng.

# Câu trả lời nhanh cho phần phản biện

## 1. Nếu hỏi: “Đóng góp chính của đồ án là gì?”

Em nên trả lời: đóng góp chính là **scheduler thích nghi theo chất lượng PPG**, kết hợp prototype phần cứng, TinyML INT8 trên ESP32-S3 và đo năng lượng bằng DAQ riêng. Đồ án không chỉ huấn luyện mô hình HR, mà đánh giá trade-off giữa **năng lượng** và **HR coverage**.

## 2. Nếu hỏi: “Coverage có phải độ chính xác không?”

Không. **HR coverage** là tỷ lệ cửa sổ có đầu ra HR hợp lệ. Nó đo khả năng duy trì đầu ra, không đo sai số BPM so với ground truth trên prototype. Sai số MAE/RMSE 8,11 BPM là đánh giá offline trên PPG-DaLiA.

## 3. Nếu hỏi: “Vì sao dùng MLP mà không dùng CNN?”

Vì input của hệ thống là **16 đặc trưng**, không phải waveform thô. Với feature vector nhỏ, MLP Dense là hợp lý, dễ nhúng bằng TFLM, ít operator và tài nguyên thấp. CNN phù hợp hơn nếu đưa raw signal vào mô hình.

## 4. Nếu hỏi: “Kiến trúc MLP chính xác là gì?”

Kiến trúc được chọn là **16 → 192 → 128 → 64 → 1**. Ba lớp ẩn đều dùng **ReLU**. Lớp output là tuyến tính. Khi train có dropout 0,20 và L2, nhưng khi inference trên ESP32 không có dropout.

## 5. Nếu hỏi: “Sơ đồ nối mạch như thế nào?”

Trả lời theo ba cụm:

- ESP32-S3 target đọc MAX30102 qua I2C: **SDA GPIO8**, **SCL GPIO9**.
- ESP32 DAQ đọc INA219 qua I2C: **SDA GPIO21**, **SCL GPIO22**.
- Nguồn 5V đi qua INA219 trước khi cấp cho target. Target xuất sync **GPIO10 feature** và **GPIO11 inference** sang DAQ ở **GPIO4/GPIO5**. Hai node cần **chung GND**.

## 6. Nếu hỏi: “Vì sao 4 cửa sổ xấu và 5 cửa sổ tốt?”

Đó là cơ chế **hysteresis**. Nếu chuyển ngay sau một cửa sổ thì scheduler dễ dao động do nhiễu ngắn hạn. Đi lên sau 4 cửa sổ xấu giúp phản ứng khi tín hiệu khó kéo dài. Đi xuống sau 5 cửa sổ tốt giúp chắc chắn tín hiệu đã ổn định trước khi quay về chế độ tiết kiệm.

## 7. Nếu hỏi: “TinyML chỉ 2–3% năng lượng thì dùng TinyML có đáng không?”

Có, vì mục tiêu của TinyML là tăng khả năng có đầu ra HR trong các cửa sổ khó. Kết quả 2–3% cho thấy bản thân Invoke không phải bottleneck chính; điều đó giúp định hướng tối ưu tiếp theo sang DSP, feature extraction và power tail.

## 8. Nếu hỏi: “Tại sao Adaptive không vừa tiết kiệm nhất vừa coverage cao nhất?”

Vì Fixed Normal và Fixed Enhanced là hai cực trị. Fixed Normal tiết kiệm nhất nhưng coverage thấp. Fixed Enhanced coverage cao nhưng tốn năng lượng hơn. Adaptive nằm giữa hai cực đó, đúng mục tiêu là tạo **điểm vận hành trung gian có kiểm soát**.

## 9. Nếu hỏi: “Kết quả offline có áp dụng trực tiếp cho prototype không?”

Không hoàn toàn. Offline dùng PPG-DaLiA, còn prototype dùng MAX30102 trong điều kiện đo khác. Có **domain shift** giữa dữ liệu huấn luyện và phần cứng thật. Vì vậy kết quả offline chứng minh mô hình đủ hợp lý để tích hợp, còn prototype cần thêm đánh giá có ground truth để kết luận độ chính xác y sinh.

## 10. Nếu hỏi: “Nếu phát triển tiếp, em sẽ làm gì đầu tiên?”

Ưu tiên đầu tiên là đánh giá prototype với ground truth đáng tin hơn, ví dụ thiết bị đo HR tham chiếu hoặc ECG. Sau đó là đồng bộ kiểm thử golden-vector giữa notebook và firmware, tối ưu feature/DSP, và thử scheduler nhiều mức hoặc ngưỡng thích nghi theo người dùng.
