# PHẦN B. TỐI ƯU HÓA NĂNG LƯỢNG VÀ TÍCH HỢP TINYML CHO BỘ ĐIỀU PHỐI THÍCH NGHI

## 1. Giới thiệu

Nếu Phần A tập trung vào việc xây dựng một prototype phần cứng có khả năng thu tín hiệu PPG ổn định và đo được công suất của toàn node, thì Phần B chuyển trọng tâm sang bài toán ở mức hệ thống: làm thế nào để node không phải luôn chạy ở cấu hình mạnh, nhưng vẫn duy trì được khả năng theo dõi nhịp tim trong những điều kiện tín hiệu khó.

Từ góc nhìn triển khai thực tế, khó khăn chính của đề tài không nằm ở việc chỉ chạy được một mô hình TinyML trên ESP32-S3, mà nằm ở việc thiết kế một cơ chế điều phối biết khi nào có thể dùng pipeline nhẹ để tiết kiệm điện, khi nào phải chuyển sang pipeline mạnh hơn để giữ độ tin cậy của đầu ra. Nói cách khác, Phần B không chỉ là phần “thêm AI vào hệ thống”, mà là phần tối ưu hóa quan hệ đánh đổi giữa chất lượng theo dõi và chi phí năng lượng trên phần cứng thật.

Kết quả của Phần A cho thấy một kết luận quan trọng: không tồn tại một cấu hình cảm biến tĩnh tối ưu cho mọi tình huống. Một cấu hình nhẹ có thể đủ tốt khi tay giữ ổn định, nhưng dễ suy giảm khi có thay đổi tiếp xúc hoặc motion artifact. Ngược lại, một cấu hình mạnh và pipeline xử lý nặng hơn có thể cải thiện chất lượng đầu ra, nhưng làm tăng công suất của toàn node cao hơn mức cần thiết nếu duy trì liên tục. Vì vậy, Phần B đặt mục tiêu xây dựng một kiến trúc điều phối thích nghi gồm hai trạng thái vận hành chính:

- **NORMAL**: ưu tiên tiết kiệm năng lượng, dùng profile cảm biến và pipeline xử lý nhẹ;
- **HIGH**: ưu tiên độ bền vững của đầu ra, dùng profile mạnh hơn và kích hoạt TinyML hỗ trợ.

Adaptive scheduler là cơ chế quyết định việc chuyển giữa hai trạng thái này.

[Ghi chú biên tập: Hình B.1 là lưu đồ điều phối hai trạng thái. Nên vẽ lại theo hướng dẫn trong `report_diagram_guides.md`.]

## 2. Đặt bài toán và định hướng phương pháp

Ở giai đoạn đầu của đề tài, bài toán được nhìn theo hướng tổng quát là một hệ thống **Energy-Aware Adaptive TinyML Scheduling for Wearable Health Monitoring**. Tuy nhiên, khi đi vào triển khai, mục tiêu cần được thu hẹp và diễn giải lại ở mức phù hợp với prototype đã xây dựng.

Trong phạm vi của Phần B, bài toán không được đặt theo hướng chẩn đoán y khoa hoàn chỉnh, mà theo hướng đánh giá và điều phối hoạt động của node đeo dựa trên chất lượng tín hiệu PPG và chi phí năng lượng của toàn hệ thống. Cụ thể, hệ thống cần trả lời ba câu hỏi:

1. Trong điều kiện tín hiệu tốt, có thể duy trì một pipeline nhẹ để tiết kiệm điện mà vẫn xuất được HR hợp lý hay không?
2. Khi tín hiệu trở nên khó hơn hoặc DSP đơn giản không còn đáng tin, có thể kích hoạt một pipeline mạnh hơn để duy trì khả năng xuất HR hay không?
3. Việc chuyển giữa hai mức xử lý này có tạo ra khác biệt thực sự về công suất tiêu thụ ở mức toàn node hay không?

Từ ba câu hỏi đó, nghiên cứu được triển khai theo hướng tối ưu đa mục tiêu, trong đó ba tiêu chí quan trọng nhất là:

- giảm công suất trung bình của toàn hệ thống;
- duy trì khả năng xuất HR trong điều kiện tín hiệu khó;
- ưu tiên độ tin cậy của đầu ra hơn là tăng coverage một cách hình thức.

Cách đặt bài toán như vậy giúp giữ được tinh thần của báo cáo tiến độ: đề tài vẫn thuộc hướng wearable health monitoring và TinyML trên edge device, nhưng trọng tâm học thuật được đặt đúng vào bài toán điều phối thích nghi theo năng lượng.

## 3. Dữ liệu và định hướng mô hình

### 3.1. Vai trò của dữ liệu công khai và dữ liệu phần cứng thật

Tương tự định hướng đã nêu trong báo cáo tiến độ ban đầu, Phần B không xem dữ liệu công khai và dữ liệu phần cứng thật là hai nguồn thay thế nhau, mà là hai nguồn phục vụ hai lớp mục tiêu khác nhau.

Dữ liệu công khai có giá trị chủ yếu ở các khía cạnh sau:

- hỗ trợ xây dựng và kiểm tra pipeline tiền xử lý;
- tạo điều kiện để thử nghiệm nhiều phương án mô hình khác nhau;
- cho phép đánh giá sai số trong điều kiện tham chiếu rõ ràng hơn so với tín hiệu phần cứng thô.

Trong khi đó, dữ liệu thu từ prototype phần cứng lại có vai trò khác:

- phản ánh ảnh hưởng của lực ép, vị trí tiếp xúc và chuyển động lên tín hiệu PPG;
- giúp nhận diện các cửa sổ tín hiệu mà DSP đơn giản trở nên kém tin cậy;
- làm cơ sở để xây dựng quality gate cho scheduler;
- kiểm tra xem cơ chế điều phối có hoạt động hợp lý trên node thực hay không.

Vì vậy, dữ liệu công khai chủ yếu hỗ trợ phần mô hình và quy trình huấn luyện, còn dữ liệu phần cứng thật quyết định tính thực dụng và tính hợp lệ của bộ điều phối trong bối cảnh hệ nhúng.

### 3.2. Hướng mô hình được cân nhắc và lựa chọn cuối cùng

Trong giai đoạn định hướng ban đầu, hai họ mô hình đã được cân nhắc:

- **MLP dựa trên vector đặc trưng**;
- **1D CNN dựa trên cửa sổ tín hiệu theo thời gian**.

Về mặt lý thuyết, 1D CNN có thể tận dụng trực tiếp hình dạng sóng PPG và tự học các mẫu hình theo thời gian. Tuy nhiên, khi đối chiếu với ràng buộc triển khai thật trên ESP32-S3, hướng này bộc lộ nhiều bất lợi hơn cho giai đoạn đồ án hiện tại: mô hình nặng hơn, khó đồng bộ hoàn toàn giữa pipeline Python và firmware, và khó kiểm soát chi phí bộ nhớ cũng như độ trễ hơn.

Sau quá trình thử nghiệm và tinh chỉnh, hệ thống cuối cùng ưu tiên hướng **feature-based MLP**. Quyết định này dựa trên bốn lý do chính:

- mô hình nhỏ hơn và phù hợp hơn với triển khai TinyML trên vi điều khiển;
- dễ chuẩn hóa đầu vào/đầu ra giữa môi trường huấn luyện và firmware nhúng;
- thuận lợi hơn cho lượng tử hóa INT8;
- dễ kiểm soát hơn về chi phí tính toán, bộ nhớ và độ trễ trong thời gian thực.

Lựa chọn này phản ánh đúng tinh thần của đề tài: mô hình không được chọn chỉ vì đạt điểm số offline tốt, mà phải phù hợp với hệ nhúng thật và phục vụ được bộ điều phối thích nghi ở cấp hệ thống.

## 4. Xây dựng nền tảng điều phối dựa trên luật

### 4.1. Lý do phải bắt đầu từ scheduler dựa trên luật

Trước khi tích hợp TinyML, hệ thống được xây dựng trước một scheduler dựa trên luật. Đây không phải là bước phụ, mà là nền tảng cần thiết để hiểu hành vi thực của tín hiệu và của chính prototype.

Nếu chưa hiểu cửa sổ tín hiệu nào là tốt, cửa sổ nào là xấu, và chưa biết những chỉ số nào có thể tính rẻ trên vi điều khiển để phản ánh chất lượng thực của PPG, thì việc đưa học máy vào quá sớm sẽ chỉ làm tăng độ phức tạp mà không giải quyết được vấn đề gốc.

Scheduler dựa trên luật ở giai đoạn này cho phép:

- ghi log hệ thống trong nhiều điều kiện đo khác nhau;
- xây dựng các chỉ số chất lượng rẻ về mặt tính toán;
- mô phỏng và tinh chỉnh logic chuyển trạng thái bằng dữ liệu thật;
- xác định rõ vùng nhiệm vụ mà TinyML thực sự cần hỗ trợ.

Nói cách khác, scheduler dựa trên luật đóng vai trò như một lớp nền để hệ thống hiểu tín hiệu, trước khi dùng TinyML để tăng độ bền vững cho các trường hợp khó.

### 4.2. Baseline wander và hiện tượng “inverted logic”

Một phát hiện quan trọng trong giai đoạn này là biên độ lớn ở tín hiệu thô không đồng nghĩa với chất lượng tốt. Trong thực nghiệm, nhiều cửa sổ bị ảnh hưởng bởi chuyển động hoặc lực ép mạnh lại có độ lệch chuẩn và biên độ đỉnh-đỉnh rất lớn, nhưng phần tăng đó chủ yếu đến từ thành phần nền thay đổi chậm chứ không phải từ thành phần nhịp tim hữu ích.

Điều này dẫn tới hiện tượng có thể gọi là **“inverted logic”**: cửa sổ xấu lại dễ vượt quality gate hơn cửa sổ tốt nhưng tiếp xúc nhẹ. Nếu không xử lý, scheduler sẽ dễ hiểu sai tín hiệu và kích hoạt pipeline mạnh vào những lúc không cần thiết.

Để khắc phục, pipeline được bổ sung bước loại bỏ nền chậm trước khi tính các chỉ số chất lượng. Một dạng cài đặt điển hình của tư tưởng này là bộ lọc high-pass dựa trên EMA:

```cpp
float alpha = dt / (tau_sec + dt);
lp += alpha * (x[i] - lp);
y[i] = x[i] - lp;
```

Sau bước này, các chỉ số amplitude và năng lượng phản ánh tốt hơn thành phần dao động hữu ích của PPG, thay vì bị chi phối bởi drift nền.

### 4.3. Quality gate theo “Goldilocks zone”

Phân tích tiếp theo cho thấy một cửa sổ tín hiệu tốt không phải là cửa sổ có biên độ càng lớn càng tốt, mà là cửa sổ có biên độ nằm trong một khoảng hợp lý, đồng thời vẫn giữ được tính chu kỳ. Từ đó, quality gate được chuyển từ cách nhìn “vượt ngưỡng là tốt” sang cách nhìn theo **Goldilocks zone**:

- biên độ không quá nhỏ để tránh trường hợp tín hiệu chìm trong nhiễu;
- biên độ không quá lớn để tránh trường hợp drift nền hoặc lực ép quá mạnh làm méo tín hiệu;
- tín hiệu phải có tính chu kỳ nhất định để DSP còn giữ được ý nghĩa.

Đây là bước chuyển quan trọng từ một scheduler ngưỡng đơn giản sang một bộ đánh giá chất lượng tín hiệu có ý nghĩa vật lý hơn, đồng thời làm nền cho logic kích hoạt TinyML về sau.

## 5. Thiết kế pipeline TinyML cho hệ nhúng

### 5.1. Feature engineering và lựa chọn đầu vào

Thay vì đưa trực tiếp tín hiệu thô vào một CNN lớn, hệ thống cuối cùng sử dụng một vector đặc trưng được trích từ cửa sổ PPG. Các nhóm đặc trưng chính gồm:

- đặc trưng biên độ và năng lượng;
- đặc trưng mô tả hình thái theo thời gian;
- các gợi ý HR lấy từ DSP;
- đặc trưng miền tần số.

Thiết kế này có hai lợi ích quan trọng. Thứ nhất, nó giữ được tính diễn giải kỹ thuật: khi mô hình hoạt động khác thường, có thể truy ngược về nhóm đặc trưng gây ảnh hưởng. Thứ hai, nó làm cho pipeline Python và pipeline firmware nhúng khớp nhau hơn, giảm rủi ro khi chuyển mô hình từ môi trường huấn luyện sang ESP32-S3.

### 5.2. Chuẩn hóa đầu ra mục tiêu và lượng tử hóa INT8

Một bước quan trọng trong phần TinyML là chuẩn hóa đầu ra mục tiêu bằng Z-score trước khi huấn luyện. Thay vì học trực tiếp HR theo đơn vị bpm, mô hình học trên phiên bản chuẩn hóa của đầu ra:

```cpp
y_norm = (y_bpm - hr_mean) / hr_std;
y_bpm  = y_norm * hr_std + hr_mean;
```

Cách làm này giúp quá trình huấn luyện ổn định hơn và làm cho phân bố đầu ra thuận lợi hơn khi chuyển sang lượng tử hóa INT8. Đây là điểm có ý nghĩa thực tế lớn vì đề tài không chỉ cần một mô hình chạy được, mà cần một mô hình đủ nhỏ cho vi điều khiển nhưng vẫn giữ sai số ở mức chấp nhận được.

### 5.3. Domain shift giữa dữ liệu huấn luyện và phần cứng thật

Một vấn đề cần được nhấn mạnh là dữ liệu huấn luyện và dữ liệu phần cứng thật không hoàn toàn đồng nhất. Dữ liệu công khai thường có điều kiện thu tốt hơn, mức nhiễu có cấu trúc hơn, trong khi tín hiệu từ prototype chịu ảnh hưởng mạnh của lực ép, thay đổi tiếp xúc và motion artifact.

Vì vậy, TinyML trong hệ thống cuối cùng không được dùng như một bộ thay thế tuyệt đối cho DSP. Thay vào đó, nó được đặt trong một khung điều phối có quality gate chặt chẽ, nghĩa là chỉ được huy động khi hệ thống đánh giá rằng pipeline nhẹ không còn đủ đáng tin hoặc cần hỗ trợ để duy trì đầu ra.

## 6. Kiến trúc thời gian thực trên ESP32-S3

### 6.1. Nút thắt cổ chai của nguyên mẫu ban đầu

Khi chuyển từ phân tích offline sang firmware thời gian thực, hệ thống bộc lộ một nút thắt quan trọng: nếu khối đọc cảm biến và khối xử lý nặng nằm quá gần nhau trong cùng nhịp phục vụ, thời gian đáp ứng của đường thu mẫu bị ảnh hưởng. Khi đó, việc phục vụ cảm biến và việc suy luận/tính đặc trưng có thể tranh chấp tài nguyên, làm cho luồng dữ liệu cảm biến trở nên kém ổn định.

Phát hiện này cho thấy một nguyên tắc rất quan trọng của đề tài: một mô hình hoạt động tốt trong notebook chưa đủ để khẳng định hệ thống sẽ hoạt động tốt trên phần cứng thật. Ở mức node, tổ chức thực thi của firmware có ý nghĩa không kém bản thân mô hình.

### 6.2. Tách nhiệm vụ theo kiến trúc hai lõi

Để khắc phục, hệ thống được tổ chức lại theo hướng khai thác hai lõi của ESP32-S3:

- một lõi ưu tiên đọc cảm biến và duy trì luồng dữ liệu PPG ổn định;
- lõi còn lại đảm nhiệm các tác vụ nặng hơn như trích chọn đặc trưng và suy luận TinyML.

Song song với thay đổi này, firmware còn được bổ sung:

- cơ chế **decision freeze** sau lỗi hoặc sau khi vừa chuyển trạng thái;
- cơ chế phục hồi khi truy cập cảm biến gặp sự cố tức thời;
- làm mượt đầu ra HR để tăng tính ổn định ở lớp ứng dụng.

Những thay đổi này cho thấy phiên bản cuối không chỉ là một pipeline mô hình, mà là một hệ thời gian thực được tổ chức lại để vận hành ổn định trên phần cứng thật.

## 7. Tối ưu hóa năng lượng ở mức kiến trúc

### 7.1. Phát hiện bất thường trong tiêu thụ năng lượng

Trong giai đoạn đầu của Phần B, khi bắt đầu đánh giá năng lượng trên node thật, hệ thống xuất hiện một bất thường quan trọng: ở một số phiên, chế độ **NORMAL** tiêu thụ năng lượng gần với **HIGH**, mặc dù về nguyên tắc NORMAL phải là nhánh nhẹ hơn rõ rệt.

Nếu hiện tượng này không được giải quyết, adaptive scheduling gần như mất ý nghĩa, vì bộ điều phối chỉ thay đổi trạng thái về mặt logic chứ không tạo ra khác biệt thực sự về chi phí vận hành.

### 7.2. Phân tích nguyên nhân gốc

Phân tích sâu hơn cho thấy nguyên nhân chính không nằm ở logic quyết định trạng thái, mà ở kiến trúc thực thi của nhánh NORMAL trong nguyên mẫu ban đầu. Dù được gọi là “nhánh nhẹ”, NORMAL vẫn vô tình đi qua phần đáng kể của pipeline trích chọn đặc trưng vốn chỉ nên phục vụ cho nhánh HIGH.

Khối gây chi phí lớn nhất là phần tính đặc trưng miền tần số theo kiểu DFT trực tiếp. Điều này tạo ra một **compute overhead nền** ngay cả khi hệ thống đang ở trạng thái được kỳ vọng là tiết kiệm điện.

Nói cách khác, NORMAL khi đó đúng về tên gọi nhưng chưa đúng về bản chất kiến trúc.

### 7.3. Tách Fast Path và Slow Path

Để xử lý nguyên nhân gốc, hệ thống được tái cấu trúc thành hai đường xử lý rõ ràng:

- **Fast Path** cho trạng thái NORMAL, chỉ giữ lại các phép tính cần thiết để đánh giá chất lượng tín hiệu và ước lượng HR cơ bản;
- **Slow Path** cho trạng thái HIGH, kích hoạt đầy đủ trích chọn đặc trưng và mô hình TinyML.

Logic cốt lõi của thay đổi này có thể minh họa ngắn gọn như sau:

```cpp
const bool need_full_features = (state == SCHED_STATE_HIGH);
if (need_full_features) {
    extract_ppg_features(...);
    run_tinyml(...);
}
```

Đây là thay đổi kiến trúc quan trọng nhất của phần tối ưu năng lượng, vì từ thời điểm này hai trạng thái bắt đầu khác nhau thật sự ở lượng tính toán được thực thi, thay vì chỉ khác nhau ở tên gọi hoặc ở vài tham số hình thức.

### 7.4. Hiệu chỉnh phương pháp đo công suất

Sau khi tách Fast Path và Slow Path, việc chỉ nhìn vào log công suất averaged ở cùng một MCU không còn đủ để trả lời câu hỏi quan trọng nhất của đề tài: chi phí năng lượng thực sự nằm ở đâu trong một cửa sổ xử lý `HIGH`? Nếu chỉ đo công suất tổng quát theo thời gian, ta biết hệ thống đã tách được `NORMAL` và `HIGH`, nhưng vẫn chưa biết bao nhiêu năng lượng thuộc về **DSP/feature extraction**, bao nhiêu thuộc về **TinyML Invoke**, và phần “đuôi công suất” sau burst kéo dài đến đâu.

Vì vậy, ở vòng đánh giá cuối, hệ thống được mở rộng thành một kiến trúc **dual-MCU DAQ**:

- **Target ESP32-S3** chạy scheduler và xuất hai tín hiệu đồng bộ phần cứng:
  - `PROFILING_FEATURE_GPIO`: lên mức cao trong lúc chạy `extract_ppg_features(...)`;
  - `PROFILING_INVOKE_GPIO`: lên mức cao trong lúc gọi `g_interpreter->Invoke()`.
- **DAQ ESP32 + INA219** đo `bus_v`, `current_ma`, `power_mw` đồng thời lấy mẫu hai chân sync và ghi ra `daq.csv`.
- `target.csv` giữ toàn bộ log UART nội bộ của ESP32-S3, bao gồm thời gian `TinyML Invoke time: ... us` cho từng lần suy luận.

Kiến trúc này tạo ra hai lớp dữ liệu đồng bộ theo sự kiện:

- `target.csv` cho biết **cửa sổ nào thực sự gọi TinyML** và `Invoke()` kéo dài bao nhiêu micro-giây;
- `daq.csv` cho biết **dạng công suất tức thời** của burst tính toán và cho phép tích phân năng lượng.

Một điểm quan trọng được rút ra từ dữ liệu thật là tốc độ lấy mẫu hữu hiệu của DAQ không đạt `500 us/sample` như cấu hình mục tiêu ban đầu. Khi đo trực tiếp từ chênh lệch `timestamp_us` trong log V7, chu kỳ lấy mẫu trung vị chỉ còn khoảng **`3298-3299 us/sample`**. Điều này không làm mất giá trị của hệ đo, nhưng nó thay đổi cách diễn giải:

- DAQ vẫn đủ tốt để bắt được **burst feature extraction** kéo dài nhiều mili-giây;
- DAQ **không đủ nhanh** để luôn bắt được xung `Invoke()` chỉ dài vài trăm micro-giây;
- vì vậy, `infer_pin_state` không thể là nguồn duy nhất để ước lượng năng lượng AI.

Để giải quyết, cặp `target.csv` và `daq.csv` được ghép theo **thứ tự burst** thay vì cố ép hai file về cùng mốc thời gian tuyệt đối. Trong log thực nghiệm, khi gộp các cụm hoạt động ở DAQ mà cách nhau không quá một mẫu trống, số burst thu được khớp hoàn toàn với số cửa sổ `HIGH` trong `target.csv`. Từ đó, mỗi cửa sổ `HIGH` được gắn với đúng một burst công suất.

Năng lượng của từng burst được tính theo dạng tích phân rời rạc có xét **power tail**:

```text
E_total = Σ max(P_i - P_baseline, 0) · Δt_i
```

trong đó:

- `P_baseline` là median công suất của một cửa sổ yên tĩnh ngay trước burst;
- `Δt_i` lấy trực tiếp từ `timestamp_us` của DAQ;
- miền tích phân không dừng ở lúc chân sync xuống thấp, mà kéo dài cho đến khi công suất trở lại vùng baseline.

Đối với TinyML, vì `Invoke()` quá ngắn so với nhịp lấy mẫu DAQ, năng lượng AI được ước lượng theo:

```text
E_AI ≈ P_peak_active · t_invoke
```

trong đó `P_peak_active` là đỉnh công suất dư `max(P - P_baseline)` của burst tương ứng, còn `t_invoke` lấy trực tiếp từ log `TinyML Invoke time` của ESP32-S3. Phần còn lại của burst được quy về DSP/feature extraction:

```text
E_DSP = E_total - E_AI
```

Phương pháp này cho phép trả lời đúng câu hỏi mà lớp macro-level chưa thể trả lời: **năng lượng thực sự được tiêu tốn chủ yếu ở đâu trong pipeline chậm**.

## 8. Đánh giá vi mô bằng kiến trúc dual-MCU hardware sync

Sau khi hoàn thiện refactor Fast Path/Slow Path và thay DFT ngây thơ bằng pipeline tối ưu hơn, hệ thống được đo lại bằng bộ log **V7**. Kết quả vi mô cho thấy ba điểm rất rõ:

- `NORMAL` không tạo burst `feature/infer` nữa, nghĩa là nhánh nhẹ đã thực sự tách khỏi Slow Path;
- thời gian `Invoke()` của MLP INT8 chỉ ở mức vài trăm micro-giây;
- chi phí năng lượng chủ đạo của cửa sổ `HIGH` vẫn nằm ở DSP và phần đuôi công suất sau burst.

![Hình B.2. Burst công suất điển hình với hai chân sync phần cứng](artifacts/ppg_hr_micro_analysis_v7/representative_burst_v7.png)

Hình B.2 cho thấy một burst điển hình trong chế độ `fixed_high`. Dải công suất tăng mạnh khi `feature_pin_state` lên cao, sau đó còn duy trì một **power tail** rõ rệt ngay cả khi hai chân sync đã về mức thấp. Với burst đại diện này, tổng năng lượng tích phân đạt khoảng `1484.39 µJ`, trong khi phần TinyML chỉ được ước lượng khoảng `31.42 µJ`, tương đương xấp xỉ `2.12%`.

![Hình B.3. Giới hạn phân giải thời gian của DAQ so với Invoke thực tế](artifacts/ppg_hr_micro_analysis_v7/micro_timing_resolution_v7.png)

Hình B.3 giải thích vì sao `infer_pin_state` không thể được dùng đơn độc để đo AI. Trong log V7:

- chu kỳ lấy mẫu DAQ trung vị khoảng `3298-3299 µs`;
- thời gian `Invoke()` trung bình chỉ khoảng `373.94-380.46 µs`;
- tỷ lệ burst mà DAQ bắt được `infer_pin_state=1` chỉ đạt `45.71%` ở `fixed_high` và `73.68%` ở `adaptive`.

Nói cách khác, ngay cả khi xung `Invoke()` có được phát ra đúng, DAQ vẫn có thể bỏ lỡ nó đơn giản vì xung này ngắn hơn nhiều so với bước lấy mẫu. Việc kết hợp `invoke_time_us` từ `target.csv` với biên độ công suất dư của burst vì vậy là bắt buộc về mặt phương pháp.

![Hình B.4. So sánh baseline power, total burst energy và tách DSP/AI](artifacts/ppg_hr_micro_analysis_v7/micro_energy_dashboard_v7.png)

Hình B.4 tổng hợp kết quả vi mô của các burst `HIGH` trong V7. Bảng dưới đây trình bày các chỉ số quan trọng nhất:

| Chỉ số vi mô của Slow Path | Adaptive (`state=1`) | Fixed High |
|---|---:|---:|
| Baseline yên tĩnh (mW) | 253.00 | 254.00 |
| Chu kỳ lấy mẫu DAQ trung vị (µs) | 3299.00 | 3298.00 |
| Thời gian `Invoke()` trung bình (µs) | 380.46 | 373.94 |
| Độ rộng xung feature quan sát được (µs) | 7200.21 | 6961.80 |
| Thời gian tích phân toàn burst (µs) | 28994.95 | 25609.89 |
| Thời gian power tail trung bình (µs) | 18583.05 | 16574.89 |
| Total active energy mỗi burst (µJ) | 1460.10 | 1393.12 |
| DSP energy ước lượng mỗi burst (µJ) | 1426.75 | 1359.03 |
| TinyML energy ước lượng mỗi burst (µJ) | 33.35 | 34.08 |
| Tỷ trọng AI theo năng lượng tích lũy (%) | 2.28 | 2.45 |

Từ bảng này có thể rút ra ba kết luận định lượng rất mạnh.

Thứ nhất, **MLP INT8 thực sự rất nhẹ**. Ở cả `adaptive/state=1` lẫn `fixed_high`, mỗi lần `Invoke()` chỉ tiêu tốn khoảng `33-34 µJ`, tức nhỏ hơn rất nhiều so với năng lượng toàn burst khoảng `1.39-1.46 mJ`. Tỷ trọng AI tính theo năng lượng tích lũy chỉ khoảng **`2.28%` ở adaptive** và **`2.45%` ở fixed_high**.

Thứ hai, **bottleneck năng lượng thực sự nằm ở DSP/feature extraction**, không nằm ở mô hình. Chỉ riêng phần DSP đã tiêu tốn khoảng `1.36-1.43 mJ` cho mỗi burst, lớn hơn phần AI hơn một bậc độ lớn. Điều này xác nhận bằng dữ liệu thật rằng thiết kế TinyML của đề tài không hề là phần “nặng” của hệ thống; trái lại, mô hình đang ở mức rất hiệu quả về năng lượng.

Thứ ba, **power tail là thành phần không thể bỏ qua**. Nếu chỉ tích phân trong lúc chân sync ở mức cao, kết quả sẽ đánh giá thiếu đáng kể năng lượng của burst. Trong V7, thời gian tail trung bình còn dài hơn bản thân độ rộng xung feature quan sát được. Vì vậy, việc tích phân đến khi công suất thực sự trở về baseline là điều kiện bắt buộc để phép đo có ý nghĩa vật lý.

Một phát hiện bổ sung cũng rất quan trọng là refactor DSP đã thực sự loại bỏ nút thắt cũ. Ở giai đoạn trước tối ưu, feature extraction từng có lúc kéo dài hàng trăm mili-giây. Trong log V7 sau tối ưu, độ rộng xung feature quan sát được chỉ còn khoảng **`6.96-7.20 ms`**, còn toàn burst kể cả tail vào khoảng **`25.61-28.99 ms`**. Điều này cho thấy hướng tối ưu bằng Fast Path/Slow Path và FFT đã giải quyết đúng nguyên nhân gốc.

![Hình B.5. Phân bố năng lượng burst giữa hai chế độ Slow Path](artifacts/ppg_hr_micro_analysis_v7/burst_energy_distribution_v7.png)

Hình B.5 cho thấy phân bố năng lượng burst của `adaptive/state=1` và `fixed_high` khá gần nhau. Điều này cũng phù hợp về mặt hệ thống: khi adaptive đã quyết định chuyển sang `HIGH`, nó thực thi gần như cùng một Slow Path với baseline `fixed_high`; khác biệt năng lượng còn lại chủ yếu đến từ độ khó của từng cửa sổ tín hiệu cụ thể chứ không đến từ bản thân MLP.

## 9. Kết quả macro-level và diễn giải trade-off ở cấp hệ thống

Kết quả vi mô ở trên trả lời câu hỏi “burst `HIGH` tốn năng lượng ở đâu”. Tuy nhiên, mục tiêu cuối cùng của đề tài vẫn là đánh giá **lợi ích hệ thống** của adaptive scheduling khi chạy liên tục trên node thật. Ở lớp này, chỉ số quan trọng vẫn là công suất trung bình, coverage và mức tách biệt giữa các trạng thái vận hành.

![Hình B.6. Biểu đồ công suất theo thời gian của một phiên adaptive điển hình](artifacts/ppg_hr_macro_analysis_v6/adaptive_log_adaptive_4_timeseries_v6.png)

Hình B.6 minh họa một phiên adaptive điển hình sau khi kiến trúc đã được tối ưu. Đường công suất thay đổi theo trạng thái vận hành nhưng không còn duy trì các plateau bất thường kéo dài như ở giai đoạn nguyên mẫu ban đầu.

![Hình B.7. Biểu đồ so sánh công suất trung bình giữa ba chế độ vận hành](artifacts/report_assets/part_b_power_comparison_v6.png)

Hình B.7 cho thấy công suất trung bình của ba chế độ vận hành đã tách biệt rõ ràng ở phiên bản cuối. Đây là điều kiện cần để adaptive scheduling có ý nghĩa ở mức hệ thống.

![Hình B.8. Biểu đồ trade-off giữa công suất tiêu thụ và HR coverage](artifacts/report_assets/part_b_tradeoff_v6.png)

Hình B.8 biểu diễn trực quan quan hệ đánh đổi giữa công suất tiêu thụ và HR coverage. Adaptive scheduling nằm giữa hai baseline và phản ánh đúng vai trò của một cơ chế điều phối cân bằng giữa hiệu năng và năng lượng.

### 9.1. Kết quả chính thức của ba chế độ vận hành

| Chế độ vận hành | Công suất trung bình (mW) | HR coverage (%) |
|---|---:|---:|
| Fixed Normal | 261.78 | 46.23 |
| Adaptive | 273.21 | 65.81 |
| Fixed High | 286.94 | 89.31 |

Khi phân tích riêng bên trong adaptive scheduler, hệ thống ghi nhận:

- **Adaptive state 0**: `263.35 mW`
- **Adaptive state 1**: `283.11 mW`

Ý nghĩa của kết quả này là rất rõ về mặt kiến trúc. Trạng thái nhẹ của adaptive bám gần baseline **Fixed Normal**, còn trạng thái mạnh bám gần baseline **Fixed High**. Như vậy, bộ điều phối không chỉ thay đổi trạng thái trên logic điều khiển, mà thực sự đưa hệ thống sang hai miền tiêu thụ năng lượng khác nhau.

### 9.2. Diễn giải học thuật của trade-off

Coverage của **Adaptive** thấp hơn **Fixed High**, nhưng vẫn cao hơn rõ rệt so với **Fixed Normal**. Khoảng cách này không nên được hiểu là thất bại, mà là hệ quả trực tiếp của hai quyết định thiết kế có chủ đích.

Thứ nhất, hệ thống áp dụng quality gate khá chặt. Khi cửa sổ tín hiệu không đủ đáng tin, hệ thống ưu tiên **không xuất HR** thay vì phát ra một giá trị thiếu căn cứ. Thứ hai, adaptive scheduler phải gánh chi phí chuyển trạng thái và thời gian quá độ mà baseline luôn bật HIGH không có. Vì vậy, việc coverage của Adaptive thấp hơn nhánh mạnh cố định là hợp lý về mặt kiến trúc.

Điểm mới quan trọng sau phân tích V7 là ta có thể diễn giải trade-off này sâu hơn: khi adaptive buộc phải vào `HIGH`, chi phí thêm mà hệ thống trả ra không đến từ bản thân MLP, mà chủ yếu đến từ khối DSP và phần tail của burst công suất. Như vậy, adaptive scheduling vẫn giữ đúng tinh thần “AI-aware nhưng energy-first”: TinyML được dùng như một lớp hỗ trợ cực nhẹ, còn phần chi phí thật sự cần quản trị nằm ở việc quyết định **khi nào Slow Path đáng để kích hoạt**.

## 10. Phạm vi hiện tại, rủi ro còn lại và giới hạn của hệ thống

Mặc dù hệ thống đã đạt được kết quả rõ ràng hơn so với nguyên mẫu ban đầu, một số giới hạn và rủi ro của đề tài vẫn còn tồn tại.

Thứ nhất, sự khác biệt giữa dữ liệu huấn luyện và dữ liệu phần cứng thật vẫn là một nguồn sai số quan trọng. Tín hiệu PPG thực tế có thể thay đổi mạnh theo lực ép, vị trí tiếp xúc và chuyển động, nên một mô hình hoạt động tốt trong điều kiện dữ liệu chuẩn hóa chưa chắc sẽ giữ nguyên chất lượng khi đưa lên node thật.

Thứ hai, tín hiệu PPG ngoài đời thực vẫn chịu ảnh hưởng lớn của motion artifact. Điều này làm cho bài toán không chỉ là “ước lượng HR”, mà còn là “biết khi nào đầu ra HR không còn đáng tin”. Vì vậy, scheduler và quality gate vẫn đóng vai trò thiết yếu, chứ không thể bị thay thế hoàn toàn bởi TinyML.

Thứ ba, nếu scheduler tiếp tục được mở rộng theo hướng quá phức tạp, chi phí triển khai và độ khó bảo vệ thực nghiệm sẽ tăng lên đáng kể. Trong khuôn khổ đồ án tốt nghiệp, một kiến trúc hai trạng thái rõ ràng, có baseline so sánh và có đo năng lượng trên phần cứng thật là phù hợp hơn so với một cơ chế điều phối quá nhiều tầng nhưng khó kiểm chứng.

Thứ tư, dù kiến trúc dual-MCU DAQ đã cải thiện mạnh khả năng micro-profiling, hệ đo hiện tại vẫn còn giới hạn phân giải thời gian. Dữ liệu V7 cho thấy DAQ chỉ đạt khoảng `3.3 ms/sample`, trong khi `Invoke()` chỉ kéo dài khoảng `0.37-0.38 ms`. Vì vậy, năng lượng AI trong báo cáo này vẫn là **ước lượng có kiểm soát** dựa trên `invoke_time_us` của target kết hợp với đỉnh công suất dư của burst, chứ chưa phải phép đo trực tiếp ở mức vi mô hoàn toàn tách biệt. Tuy nhiên, ngay cả với cách ước lượng bảo thủ này, phần AI vẫn chỉ chiếm khoảng `2.3-2.4%`, nên kết luận về tính nhẹ của TinyML vẫn rất vững.

## 11. Kết luận

Phần B cho thấy đóng góp chính của đề tài không nằm ở việc chỉ chạy được một mô hình TinyML trên ESP32-S3, mà ở việc xây dựng được một kiến trúc điều phối thích nghi hoàn chỉnh trên phần cứng thật. Hệ thống cuối cùng kết hợp được bốn lớp thành phần:

- nền tín hiệu và quality gate từ scheduler dựa trên luật;
- mô hình TinyML phù hợp với ràng buộc edge deployment;
- kiến trúc thời gian thực đủ ổn định cho sensing và inference;
- phương pháp đo năng lượng hai tầng, gồm macro-level cho công suất hệ thống và micro-level dual-MCU để bóc tách burst xử lý.

Điểm kết luận mạnh nhất của vòng thực nghiệm cuối là: **MLP INT8 không phải bottleneck năng lượng của hệ thống**. Với dữ liệu V7, mỗi lần `Invoke()` chỉ tiêu tốn khoảng `33-34 µJ`, tương đương khoảng `2.3-2.4%` năng lượng của một burst `HIGH`, trong khi phần còn lại chủ yếu thuộc về DSP/feature extraction và power tail. Điều này chứng minh hướng TinyML của đề tài là rất hiệu quả: mô hình đủ nhỏ để đưa AI vào node mà gần như không phá vỡ ngân sách năng lượng.

Từ góc nhìn wearable health monitoring, đây là kết quả quan trọng nhất của giai đoạn hiện tại: hệ thống không hoạt động nặng mọi lúc, không hoạt động nhẹ mọi lúc, mà biết khi nào cần trả thêm chi phí tính toán để duy trì độ tin cậy của đầu ra và khi nào nên quay về chế độ tiết kiệm năng lượng. Khi đã cần vào `HIGH`, chi phí tăng thêm chủ yếu đến từ phần xử lý tín hiệu chứ không đến từ mô hình học máy.

Xét trong ngữ cảnh báo cáo tiến độ đồ án tốt nghiệp, Phần B đồng thời đóng vai trò cầu nối từ phần prototype phần cứng ở Phần A sang phần đánh giá đóng góp của adaptive scheduling ở mức hệ thống. Nó chứng minh rằng bài toán của đề tài không chỉ dừng lại ở “đọc được cảm biến” hay “chạy được TinyML”, mà đã tiến tới mức thiết kế và kiểm chứng một cơ chế điều phối thích nghi có ý nghĩa thực nghiệm trên node thật.
