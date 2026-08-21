# **XÂY DỰNG ĐỒ THỊ TRI THỨC HỖ TRỢ TRA CỨU VĂN BẢN PHÁP QUY TRONG QUẢN TRỊ ĐẠI HỌC** 

# **(pass neo4j: 12345678)** 

## **Tóm tắt (Abstract):** 

Quản trị đại học hiện đại đòi hỏi việc truy xuất nhanh chóng và chính xác các quy định, quy chế nội bộ. Tuy nhiên, sự gia tăng về số lượng và tính liên kết phức tạp giữa các văn bản pháp quy khiến phương pháp tìm kiếm dựa trên từ khóa truyền thống gặp nhiều hạn chế. Bài báo này đề xuất một phương pháp xây dựng đồ thị tri thức (Knowledge Graph) dựa trên nguồn dữ liệu văn bản pháp quy của Trường Đại học Bách khoa - ĐHĐN. Chúng tôi trích xuất các thực thể cốt lõi như **Văn bản** , **Đơn vị ban hành** , **Lĩnh vực chuyên môn** và **Căn cứ pháp lý** , đồng thời thiết lập các mối quan hệ đa tầng giữa chúng. Kết quả thực nghiệm cho thấy việc ứng dụng đồ thị tri thức giúp cải thiện đáng kể độ chính xác và khả năng kết nối thông tin so với các phương pháp tìm kiếm văn bản thông thường. 

## **1. Giới thiệu (Introduction)** 

**Bối cảnh:** Chuyển đổi số trong quản trị đại học (Digital Governance). 

**Vấn đề:** Văn bản pháp quy tại DUT rất đa dạng (từ quy chế học vụ đến quản lý tài sản công), thường xuyên được cập nhật và thay thế. Việc tìm kiếm hiện tại chỉ dừng lại ở mức độ so khớp từ khóa đơn giản, chưa thể hiện được mối liên hệ giữa văn bản trường và luật liên bang/bộ ngành. 

**Mục tiêu:** Xây dựng hệ thống đồ thị tri thức để "số hóa" mối quan hệ giữa các quy định, hỗ trợ cán bộ và sinh viên tra cứu hiệu quả. 

## **2. Phương pháp nghiên cứu (Methodology)** 

## **2.1. Thu thập dữ liệu (Data Collection)** 

- Nguồn dữ liệu: Toàn bộ văn bản công khai tại trang **dut.udn.vn/VanBanPhapQuy** . 

- Tiền xử lý: Sử dụng công cụ OCR (Tesseract hoặc Google Vision) <mark>/PyPDF2</mark> /… để chuyển đổi các file PDF scan sang định dạng văn bản (Plain Text). 

## **2.2. Định nghĩa lược đồ đồ thị (Graph Schema)** 

Hệ thống sử dụng Đồ thị tri thức bao gồm: 

## **2.2.1. Hệ thống thực thể (Nodes)** 

Đối với DUT (http://dut.udn.vn/VanbanPhapquy), chúng ta có các node sau: 

- **Văn bản (Document Node):** Nút trung tâm, chứa thông tin về các quyết định, quy chế, quy định của DUT (tương đương với _Case node_ ). 

_Thuộc tính:_ Số hiệu, Trích yếu, Ngày ban hành, Người ký. 

- **Đơn vị ban hành (Issuer Node):** Đại diện cho các phòng ban, khoa hoặc Ban Giám hiệu (thay thế cho _Court node_ ). 

_Ví dụ:_ Phòng Đào tạo, Phòng Công tác Sinh viên, Ban Giám hiệu DUT. 

- **Lĩnh vực (Domain Node):** Phân loại văn bản theo mục đích (tương đương với _Domain node_ ). 

_Ví dụ:_ Quy chế học vụ, Quản lý tài chính, Nghiên cứu khoa học, Tuyển sinh. 

- **Căn cứ pháp lý (Legal Basis Node):** Các văn bản cấp cao hơn của Bộ GD&ĐT hoặc Chính phủ (tương đương với _Law node_ ). 

_Thuộc tính:_ Tên căn cứ, ngày căn cứ, cấp đưa ra 

_Ví dụ:_ (Thông tư 08/2021/TT-BGDĐT, 08/06/2021, Chính phủ) 

- **Đối tượng áp dụng (Target Node):** (Điểm mới so với bài báo) Xác định văn bản này dành cho ai. 

_Ví dụ:_ Sinh viên hệ chính quy, Giảng viên, Học viên cao học. 

## **2.2.2. Hệ thống quan hệ (Edges)** 

Các quan hệ này sẽ tạo nên các **Meta-path** để cho phép truy vấn ngữ nghĩa: 

- **BAN_HANH (ISSUED_BY):** Nối từ _Văn bản_ đến _Cơ quan ban hành_ . 

- **THUOC_LINH_VUC (BELONG_TO):** Nối từ _Văn bản_ đến _Lĩnh vực_ . 

- **THUOC_LOAI_VAN_BAN (TEXT_TYPE):** Nối từ _Văn bản_ đến _Loại văn bản_ 

- **CAN_CU (BASED_ON):** Nối từ _Văn bản_ đến các _Căn cứ pháp lý_ của Bộ/Nhà nước. 

- **THAY_THE (REPLACES):** Nối giữa hai nút _Văn bản_ nếu quy định mới thay thế quy định cũ. 

- **AP_DUNG_CHO (APPLIES_TO):** Nối từ _Văn bản_ đến _Đối tượng áp dụng_ . 

## **2.2.3.  Ví dụ cụ thể:** 

Giả sử cần trích xuất dữ liệu từ một văn bản thực tế trên trang http://dut.udn.vn/VanbanPhapquy: 

## **"Quyết định số 123/QĐ-ĐHBK về việc ban hành Quy định học vụ bậc Đại học"** 

## **Mô hình hóa trên Đồ thị:** 

1. **Nút Văn bản:** [Văn bản: 123/QĐ-ĐHBK] 

2. **Mối quan hệ:** 

- [Văn bản: 123/QĐ-ĐHBK] -- **BAN_HANH** --> [Đơn vị: Ban Giám hiệu] 

- [Văn bản: 123/QĐ-ĐHBK] -- **THUOC_LINH_VUC** --> [Lĩnh vực: Quy chế học vụ] 

- [Văn bản: 123/QĐ-ĐHBK] -- **CAN_CU** --> [Căn cứ: Thông tư 08/2021/TT-BGDĐT] 

- [Văn bản: 123/QĐ-ĐHBK] -- **AP_DUNG_CHO** --> [Đối tượng: Sinh viên đại học] 

- [Văn bản: 123/QĐ-ĐHBK] -- **THAY_THE** --> [Văn bản: 456/QĐ-ĐHBK (năm 2015)] 

## **2.3. Trích xuất tri thức:** 

- Sử dụng biểu thức chính quy (Regular Expressions) để bắt các trường dữ liệu có cấu trúc (Số hiệu, Ngày ban hành). 

- Sử dụng mô hình ngôn ngữ (như PhoBERT hoặc spaCy) để nhận diện thực thể tên riêng (NER) như tên các Phòng/Khoa và các loại đối tượng. 

## **3. Triển khai và Thử nghiệm** 

## **3.1. Lưu trữ trên Neo4j** 

- Sử dụng cơ sở dữ liệu đồ thị Neo4j để lưu trữ. 

- Thiết lập các truy vấn Cypher để thực hiện tìm kiếm đa lớp. 

## **3.2. Đánh giá hiệu quả** 

**Baseline:** So sánh với thuật toán BM25 (tìm kiếm từ khóa). 

**Chỉ số đánh giá:** Độ chính xác (Precision), Độ phủ (Recall), và Điểm F1. 

## **Kịch bản thử nghiệm:** 

Ví dụ: Tìm kiếm các văn bản liên quan đến "Học bổng" nhưng giới hạn bởi "Sinh viên năm nhất" và được ban hành bởi "Phòng Công tác sinh viên". 

## **4. Kết quả và Thảo luận** 

- Đồ thị tri thức giúp tìm ra các mối liên kết ngầm (ví dụ: các văn bản cùng dựa trên một Thông tư đã hết hiệu lực). 

- Khả năng lọc thông tin chính xác theo đối tượng áp dụng giúp giảm thời gian tra cứu cho sinh viên. 

## **5. Kết luận** 

Nghiên cứu khẳng định tiềm năng của đồ thị tri thức trong việc minh bạch hóa và tối ưu hóa hệ thống văn bản pháp quy đại học. 

**Hướng phát triển:** Kết hợp với mô hình ngôn ngữ lớn (LLM) để xây dựng hệ thống hỏi đáp tự động (RAG - Retrieval-Augmented Generation) dựa trên đồ thị đã xây dựng. 

