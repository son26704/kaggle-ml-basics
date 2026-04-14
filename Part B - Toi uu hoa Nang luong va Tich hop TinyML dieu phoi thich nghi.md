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

Sau khi tách Fast Path và Slow Path, log công suất vẫn còn xuất hiện một số đỉnh tức thời. Phân tích tiếp cho thấy một phần của hiện tượng này đến từ chính cách lấy mẫu công suất: nếu phép đo bắt đúng thời điểm hệ thống vừa hoàn thành một burst tính toán nặng, giá trị sẽ phản ánh đỉnh tức thời hơn là mức công suất trung bình có ý nghĩa vận hành.

Vì vậy, phương pháp đo được hiệu chỉnh theo hướng:

- đọc telemetry công suất dày hơn theo chu kỳ ngắn;
- lấy trung bình theo cửa sổ ngắn;
- ưu tiên so sánh trên giá trị trung bình đại diện cho trạng thái vận hành, thay vì dựa trên từng điểm đỉnh đơn lẻ.

Điều chỉnh này là cần thiết về mặt phương pháp luận, vì mục tiêu của đề tài là đánh giá năng lượng vận hành của toàn node, chứ không chỉ mô tả các đỉnh tức thời trong quá trình thực thi.

## 8. Kiến trúc hoàn chỉnh và kết quả macro-level

Sau quá trình tinh chỉnh, hệ thống cuối cùng đạt được ba đặc tính mong muốn:

- phép đo năng lượng phản ánh công suất của toàn hệ thống;
- nhánh **NORMAL** thực sự là nhánh nhẹ;
- nhánh **HIGH** thực sự là nhánh mạnh có TinyML hỗ trợ.

![Hình B.2. Biểu đồ công suất theo thời gian của một phiên adaptive điển hình](artifacts/ppg_hr_macro_analysis_v6/adaptive_log_adaptive_4_timeseries_v6.png)

Hình B.2 minh họa một phiên adaptive điển hình sau khi kiến trúc đã được tối ưu. Đường công suất thay đổi theo trạng thái vận hành nhưng không còn duy trì các plateau bất thường kéo dài như ở giai đoạn nguyên mẫu ban đầu.

![Hình B.3. Biểu đồ so sánh công suất trung bình giữa ba chế độ vận hành](artifacts/report_assets/part_b_power_comparison_v6.png)

Hình B.3 cho thấy công suất trung bình của ba chế độ vận hành đã tách biệt rõ ràng ở phiên bản cuối. Đây là điều kiện cần để adaptive scheduling có ý nghĩa ở mức hệ thống.

![Hình B.4. Biểu đồ trade-off giữa công suất tiêu thụ và HR coverage](artifacts/report_assets/part_b_tradeoff_v6.png)

Hình B.4 biểu diễn trực quan quan hệ đánh đổi giữa công suất tiêu thụ và HR coverage. Adaptive scheduling nằm giữa hai baseline và phản ánh đúng vai trò của một cơ chế điều phối cân bằng giữa hiệu năng và năng lượng.

### 8.1. Kết quả chính thức của ba chế độ vận hành

| Chế độ vận hành | Công suất trung bình (mW) | HR coverage (%) |
|---|---:|---:|
| Fixed Normal | 261.78 | 46.23 |
| Adaptive | 273.21 | 65.81 |
| Fixed High | 286.94 | 89.31 |

Khi phân tích riêng bên trong adaptive scheduler, hệ thống ghi nhận:

- **Adaptive state 0**: `263.35 mW`
- **Adaptive state 1**: `283.11 mW`

Ý nghĩa của kết quả này là rất rõ về mặt kiến trúc. Trạng thái nhẹ của adaptive bám gần baseline **Fixed Normal**, còn trạng thái mạnh bám gần baseline **Fixed High**. Như vậy, bộ điều phối không chỉ thay đổi trạng thái trên logic điều khiển, mà thực sự đưa hệ thống sang hai miền tiêu thụ năng lượng khác nhau.

## 9. Chỉ số đánh giá và diễn giải kết quả

### 9.1. Các chỉ số đánh giá chính

Giống tinh thần của báo cáo tiến độ ban đầu, hệ thống không thể được đánh giá chỉ bằng một chỉ số duy nhất. Ở phiên bản hoàn thiện hơn của Phần B, các trục đánh giá quan trọng nhất là:

- công suất trung bình của từng chế độ vận hành;
- HR coverage, tức tỷ lệ thời gian hệ thống xuất được một giá trị HR hợp lệ;
- mức tách biệt giữa các baseline và các trạng thái của adaptive scheduler;
- độ ổn định vận hành trên phần cứng thật.

Bộ chỉ số này phù hợp với bản chất của đề tài hơn so với cách nhìn chỉ tập trung vào sai số mô hình, vì mục tiêu cuối cùng là tối ưu hóa vận hành của một node wearable chứ không phải chỉ tối ưu hóa một mô hình học máy độc lập.

### 9.2. Diễn giải học thuật của trade-off

Coverage của **Adaptive** thấp hơn **Fixed High**, nhưng vẫn cao hơn rõ rệt so với **Fixed Normal**. Khoảng cách này không nên được hiểu là thất bại, mà là hệ quả trực tiếp của hai quyết định thiết kế có chủ đích.

Thứ nhất, hệ thống áp dụng quality gate khá chặt. Khi cửa sổ tín hiệu không đủ đáng tin, hệ thống ưu tiên **không xuất HR** thay vì phát ra một giá trị thiếu căn cứ. Thứ hai, adaptive scheduler phải gánh chi phí chuyển trạng thái và thời gian quá độ mà baseline luôn bật HIGH không có. Vì vậy, việc coverage của Adaptive thấp hơn nhánh mạnh cố định là hợp lý về mặt kiến trúc.

Nói cách khác, hệ thống chấp nhận hy sinh một phần coverage để đổi lấy công suất thấp hơn, miễn là các giá trị HR được giữ lại vẫn có độ tin cậy cao hơn về mặt thực nghiệm.

## 10. Phạm vi hiện tại, rủi ro còn lại và giới hạn của hệ thống

Mặc dù hệ thống đã đạt được kết quả rõ ràng hơn so với nguyên mẫu ban đầu, một số giới hạn và rủi ro của đề tài vẫn còn tồn tại.

Thứ nhất, sự khác biệt giữa dữ liệu huấn luyện và dữ liệu phần cứng thật vẫn là một nguồn sai số quan trọng. Tín hiệu PPG thực tế có thể thay đổi mạnh theo lực ép, vị trí tiếp xúc và chuyển động, nên một mô hình hoạt động tốt trong điều kiện dữ liệu chuẩn hóa chưa chắc sẽ giữ nguyên chất lượng khi đưa lên node thật.

Thứ hai, tín hiệu PPG ngoài đời thực vẫn chịu ảnh hưởng lớn của motion artifact. Điều này làm cho bài toán không chỉ là “ước lượng HR”, mà còn là “biết khi nào đầu ra HR không còn đáng tin”. Vì vậy, scheduler và quality gate vẫn đóng vai trò thiết yếu, chứ không thể bị thay thế hoàn toàn bởi TinyML.

Thứ ba, nếu scheduler tiếp tục được mở rộng theo hướng quá phức tạp, chi phí triển khai và độ khó bảo vệ thực nghiệm sẽ tăng lên đáng kể. Trong khuôn khổ đồ án tốt nghiệp, một kiến trúc hai trạng thái rõ ràng, có baseline so sánh và có đo năng lượng trên phần cứng thật là phù hợp hơn so với một cơ chế điều phối quá nhiều tầng nhưng khó kiểm chứng.

Thứ tư, mọi kết luận về năng lượng vẫn phụ thuộc mạnh vào cách bố trí điểm đo và phương pháp lấy mẫu công suất. Vì vậy, việc duy trì cấu hình đo toàn node và phương pháp lấy trung bình nhất quán là điều bắt buộc để bảo đảm tính so sánh giữa các thực nghiệm.

## 11. Kết luận

Phần B cho thấy đóng góp chính của đề tài không nằm ở việc chỉ chạy được một mô hình TinyML trên ESP32-S3, mà ở việc xây dựng được một kiến trúc điều phối thích nghi hoàn chỉnh trên phần cứng thật. Hệ thống cuối cùng kết hợp được bốn lớp thành phần:

- nền tín hiệu và quality gate từ scheduler dựa trên luật;
- mô hình TinyML phù hợp với ràng buộc edge deployment;
- kiến trúc thời gian thực đủ ổn định cho sensing và inference;
- phương pháp đo năng lượng đủ đúng để đánh giá lợi ích ở cấp hệ thống.

Từ góc nhìn wearable health monitoring, đây là kết quả quan trọng nhất của giai đoạn hiện tại: hệ thống không hoạt động nặng mọi lúc, không hoạt động nhẹ mọi lúc, mà biết khi nào cần trả thêm chi phí tính toán để duy trì độ tin cậy của đầu ra và khi nào nên quay về chế độ tiết kiệm năng lượng.

Xét trong ngữ cảnh báo cáo tiến độ đồ án tốt nghiệp, Phần B đồng thời đóng vai trò cầu nối từ phần prototype phần cứng ở Phần A sang phần đánh giá đóng góp của adaptive scheduling ở mức hệ thống. Nó chứng minh rằng bài toán của đề tài không chỉ dừng lại ở “đọc được cảm biến” hay “chạy được TinyML”, mà đã tiến tới mức thiết kế và kiểm chứng một cơ chế điều phối thích nghi có ý nghĩa thực nghiệm trên node thật.
