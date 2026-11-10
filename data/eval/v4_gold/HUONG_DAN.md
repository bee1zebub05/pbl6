# Hướng dẫn gán nhãn đối chứng cho bộ JSON v4

Mục đích: đo độ chính xác trích xuất của bộ `data/clean/json/v4/` (Ontology §6.1–6.2)
trên toàn bộ 103 văn bản (`danh_sach_103.json`). Đợt đầu gán 20 văn bản
(`danh_sach_20.json`, phân tầng theo 10 lĩnh vực); 83 văn bản còn lại chia thành
`lo_1.json` … `lo_4.json`, mỗi lô do hai agent gán độc lập vào `nhan_ai_1/` và `nhan_ai_2/`.

**Người gán hiện tại là AI (hai agent gán độc lập), không phải người.** Thư mục
`nhan_ai_1/` và `nhan_ai_2/` chứa nhãn của hai agent. Khi báo cáo phải ghi rõ
"nhãn do AI gán độc lập", không gọi là nhãn người. Nếu sau này có người gán,
đặt vào thư mục `nguoi_gan_<tên>/` theo đúng định dạng dưới đây.

## Quy tắc độc lập

- Chỉ đọc file `.txt` gốc trong `data/clean/sinh_vien_103/text/`.
- **Không** mở bất kỳ file nào trong `data/clean/json/`, `data/clean/sinh_vien_103/json_v2/`,
  `data/eval/v4_gold/` (trừ file hướng dẫn này, file danh sách được giao và thư mục ra của chính mình),
  và không truy vấn Neo4j. Đó là thứ đang được đo, xem vào là hỏng phép đo.

## Định dạng đầu ra

Mỗi văn bản một file JSON, tên file = tên file `.txt` đổi đuôi thành `.json`:

```json
{
  "sourceFile": "Công tác sinh viên/0070_1088_QĐ-ĐHBK_....txt",
  "documentNumber": "1088/QĐ-ĐHBK",
  "signers": ["Đoàn Quang Vinh"],
  "targetGroups": ["Người học"],
  "citations": [
    {"targetDocumentNumber": "32/CP", "relationType": "BASED_ON",
     "context": "Căn cứ Nghị định số 32/CP ngày 04/4/1994 của Chính phủ ..."}
  ],
  "note": null
}
```

- `documentNumber`: số hiệu của chính văn bản, như in ở đầu văn bản.
- `signers`: họ tên đầy đủ người ký (không kèm học hàm, chức vụ). Biểu mẫu để trống thì `[]`.
- `targetGroups`: chọn trong đúng 8 tên sau, chỉ khi văn bản nêu đối tượng áp dụng / phạm vi
  (Điều "Đối tượng áp dụng", "Phạm vi điều chỉnh", hoặc câu giao trách nhiệm thi hành):
  `Người học` · `Cán bộ, giảng viên, viên chức, người lao động` · `Đơn vị trực thuộc` ·
  `Cơ sở giáo dục / trường đại học thành viên` · `Cơ quan, tổ chức, cá nhân có liên quan` ·
  `Hội đồng và thành viên hội đồng` · `Doanh nghiệp, đối tác/tổ chức nước ngoài` · `Khác`.
  (Bản đầu của hướng dẫn này viết tắt hai tên trên; `tinh_diem.py` quy cả hai cách viết về tên chuẩn.)
- `citations`: mỗi cặp (văn bản đích, loại quan hệ) **một dòng**, dù câu đó lặp lại nhiều lần.
  `context` là một câu trích **nguyên văn** từ `.txt` làm bằng chứng.
- `note`: chỗ không chắc, ghi lý do.

## Gán `relationType`

| Nhãn | Khi nào | Dấu hiệu |
|---|---|---|
| `BASED_ON` | Văn bản đang đọc lấy văn bản đích làm cơ sở pháp lý | nằm trong khối "Căn cứ ..." đầu văn bản |
| `REFERENCES` | Chỉ nhắc tới, dẫn chiếu, không đổi hiệu lực | "theo quy định tại ...", "thực hiện theo ..." |
| `REPLACES` | Văn bản đang đọc **thay thế** văn bản đích | "... thay thế Quyết định số ..." |
| `AMENDS` | Văn bản đang đọc **sửa đổi / bổ sung** văn bản đích (đích vẫn còn hiệu lực) | "sửa đổi, bổ sung một số điều của ..." |
| `REPEALS` | Văn bản đang đọc **bãi bỏ** văn bản đích, không có văn bản thế chỗ | "bãi bỏ ...", "hết hiệu lực ..." do chính văn bản này tuyên bố |

Quy ước:

1. **Chủ ngữ phải là văn bản đang đọc.** "Nghị định 09/2010 sửa đổi Nghị định 110/2004"
   được nhắc trong văn bản đang đọc → cả hai là `REFERENCES`, không phải `AMENDS`.
2. Chỉ gán khi văn bản đích có **số hiệu** (phần số + ký hiệu, ví dụ `81/2021/NĐ-CP`,
   `2231/QĐ-ĐHBK`, `32/CP`). Nhắc tên không có số hiệu ("Luật Giáo dục đại học") thì bỏ qua.
3. Không gán văn bản tự trích chính nó, không gán số công báo, số trang, số tài khoản.
4. Số hiệu viết như trong văn bản; sửa lỗi OCR hiển nhiên (`O`→`0`, `l`→`1`) và ghi vào `note`.
5. Cùng một văn bản đích vừa là căn cứ vừa bị thay thế → hai dòng.
6. Phần "ban hành kèm theo" (Quy chế, Quy định đính kèm) thuộc cùng văn bản: trích dẫn trong
   đó vẫn tính cho văn bản này.

## Sau khi gán

`python data/eval/v4_gold/tinh_diem.py` tính Cohen's κ giữa hai bộ nhãn và P/R/F1 của v4
so với từng bộ và với phần hai bộ đồng ý.
