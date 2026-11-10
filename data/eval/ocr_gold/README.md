# Bộ chuẩn OCR theo trang (20 trang)

Đo `text_final` so với chữ thật trên ảnh trang PDF gốc. Trước bộ này, chất lượng
kho chỉ được đo bằng chỉ số đại diện (`vietnamese_score`, bộ kiểm âm tiết), không
so với bản gốc.

```bash
python tools/kiem_tra/ocr_gold.py chon --so-trang 20 --seed 6   # chọn trang, xuất ảnh vào anh/
python tools/kiem_tra/ocr_gold.py cham                          # chấm -> ket_qua.md, ket_qua.json
```

`anh/` không vào git (xuất lại được từ `data/raw/pdf` bằng lệnh `chon`).

## Bản chuẩn do ai gõ

**Claude (Opus 5.5) đọc ảnh trang và gõ lại, một người gán duy nhất, ngày 10/11/2026.**
Số hiệu và ngày điền tay được phóng to 400 DPI trước khi đọc. Đây chưa phải bộ
chuẩn độc lập do người gõ:

- Không có người gán thứ hai, nên chưa đo được sai số của chính bản chuẩn.
- Mô hình đọc ảnh có thể sai cùng kiểu với các mô hình OCR trong pipeline.

Trước khi dùng con số này trong báo cáo, một thành viên nhóm nên soát lại 20 file
`chuan/*.txt` với ảnh, ưu tiên các số viết tay.

## Quy ước gõ

- Chép mọi chữ in trên trang theo thứ tự đọc: hết cột trái rồi tới cột phải;
  phần đầu văn bản hai cột thì khối bên trái trước, khối bên phải sau.
- Giữ dòng đầu trang Công báo và số trang in trên giấy.
- Số hiệu và ngày điền tay chép đúng như viết.
- Bỏ: watermark của website (pipeline cố ý gỡ), dấu đỏ, chữ ký, dấu "ĐẾN" của
  văn thư, ghi chú viết tay thêm sau khi ban hành (vd "K/g: + Ban Giám hiệu").
- Lỗi của chính bản gốc giữ nguyên, vd "Trường Đại Bách khoa" thiếu chữ "học".
- Bảng: đọc theo hàng, mỗi ô một dòng.

Lúc chấm, cả hai phía đều được chuẩn hoá Unicode NFC, khoảng trắng được gộp, và
dấu nháy cong, gạch dài, dấu "…" được quy về một dạng. Đó là khác biệt kiểu chữ,
không phải lỗi nhận dạng.

## Cách chấm

Mốc `[Trang N]` trong `text_final` không đáng tin: chỉ 10/20 trang có mốc trỏ đúng
nội dung, nên CER được tính trên **đoạn khớp nhất trong toàn văn bản**, không cắt
theo mốc. Cùng lúc ghi lại mốc có đúng không, vì việc này ảnh hưởng tới truy
nguồn trang (`tools/kiem_tra/nguon_trang.py`).

| Chỉ số | Ý nghĩa |
|---|---|
| CER giữ dấu | Mọi sai khác ký tự, gồm cả lệch thứ tự đọc |
| CER bỏ dấu | Như trên, sau khi bỏ dấu; hiệu hai số là phần lỗi nằm ở dấu |
| Từ thiếu / thừa | Đếm từ không xét thứ tự: tách lỗi nhận dạng khỏi lệch thứ tự đọc |
| Token chứa chữ số | Số hiệu, ngày, trích dẫn của bản chuẩn có mặt nguyên dạng hay không |

## Kết quả lần đầu (10/11/2026)

Xem `ket_qua.md`. Tóm tắt: CER gộp 2,35% (trung vị 2,26%), hầu như không có lỗi
dấu (CER bỏ dấu 2,31%), từ thiếu 1,47%, 475/483 token chứa chữ số khớp.

Phần lớn CER đến từ khối đầu văn bản hai cột đọc xen dòng, khối ký bị thay bằng
"(Đã ký)" hoặc lẫn chữ trong con dấu, và dấu "-" đầu dòng Nơi nhận bị bỏ. Các lỗi
nội dung thật tìm được:

- `0415` trang 1: mất trọn câu "Căn cứ Nghị định số 32/CP ngày 04/4/1994…" và chữ
  "Về việc" ở trích yếu, đúng chỗ dấu "ĐẾN" của văn thư đè lên. Đồ thị thiếu cạnh căn cứ này.
- `0077` trang 1: số hiệu thành "2352/QĐ-ĐHBK.2 IQĐ-ĐHBK": bước tiêm số hiệu ghi
  đúng nhưng rác OCR cũ còn lại phía sau.
- `0077`, `0045` trang 1: chữ trong con dấu lẫn vào văn bản ("B8CHR Cekcuccac").
- `0013` trang 1: ghi chú viết tay chuyển văn bản bị đưa vào như nội dung.

20 trang đủ để thấy các kiểu lỗi trên, chưa đủ để ước lượng chắc CER toàn kho; cỡ
mẫu theo báo cáo `reports/Giải pháp OCR PDF tiếng Việt.md` là khoảng 40–120 trang.
