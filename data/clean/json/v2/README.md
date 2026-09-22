# JSON v2 — v1 cộng đúng một trường: `document.targetGroups`

454 file, **sao chép nguyên vẹn từ `v1/`** rồi thêm duy nhất khoá
`document.targetGroups[]`. Đã đối chiếu từng file: bỏ khoá đó ra thì v2 giống
v1 **byte-for-byte về mặt nội dung** (454/454, 0 file lệch). Cấu trúc thư mục,
tên file, mã 4 chữ số đều giữ nguyên để đối chiếu hai chiều.

```
v2/
├── <lĩnh vực>/<mã>_….json     418 file
└── _nghi_ngo/<lĩnh vực>/…      36 file (giữ nguyên trạng thái nghi ngờ của v1)
```

## Vì sao có v2 thay vì sửa thẳng v1

`v1/` đã qua nhiều đợt sửa tay: commit `0befcd4` bù 95 trích dẫn model bỏ sót
vào 59 file, commit `7fd667c` đọc lại `0196` từ bản scan (53 → 105 Điều). Giữ
v1 nguyên vẹn làm mốc đối chiếu; v2 là bản đầy đủ nạp thẳng được:

```powershell
python run.py lkg all --dir data/clean/json/v2
python run.py lkg query --source benchmark
```

## Vì sao v1 thiếu trường này

Không phải "còn nợ gán tay" như `src/legal_knowledge_graph/README.md` §7 mục 1
ghi. `PROMPT` sinh JSON (`tools/gemini_web/cau_json.py`) **chưa bao giờ liệt kê**
`targetGroups` trong khối `CẤU TRÚC`, lại chốt *"khoá nào không có trong danh
sách này thì TUYỆT ĐỐI không được thêm"* — model bị **cấm** sinh trường đó. Nên
0/418 file v1 có nó.

## Sinh lại

```powershell
python tools/gemini_api/chay_json.py --bu-nhom               # v1 -> v2
python tools/gemini_api/chay_json.py --bu-nhom --chi 0082    # một mã
python tools/gemini_api/chay_json.py --bu-nhom --lam-lai     # gán lại cả file đã có
```

Chạy lại an toàn: file nào ở v2 đã có nhãn thì bỏ qua, nên đứt giữa chừng
(hết hạn mức) chỉ cần chạy lại là đi tiếp. Đợt đầu 39/266 file dính 429 và
được vá trong hai lượt chạy sau.

Mode này **không** sinh lại file. Nó cắt đoạn "Phạm vi điều chỉnh / đối tượng
áp dụng" từ `.txt` gốc (trần 2,6 KB thay vì cả văn bản ~29 KB), hỏi model đúng
một câu, rồi ghi đúng một khoá. Không đụng `citations`/`summary`/`signers`, nên
không thể làm mất phần đã sửa tay ở v1.

## Số liệu

| | |
|---|---:|
| Tổng file | 454 |
| Có nhãn | **268** |
| `targetGroups: []` | 186 |
| Tổng lượt gán nhãn | 554 |
| Trung bình (văn bản có nhãn) | 2,07 nhãn |

186 file rỗng là **kết luận, không phải thiếu sót**: cả văn bản không có mục nào
nói về đối tượng áp dụng, nên không tốn một lượt gọi API nào. Con số 268 khớp
với 268 đoạn "Đối tượng áp dụng" mà `target_groups_seed.json` ghi là căn cứ xây
vocabulary, và với 267/454 file `.txt` chứa cụm từ này.

| Nhãn | Số văn bản |
|---|---:|
| Cơ quan, tổ chức, cá nhân có liên quan | 174 |
| Cơ sở giáo dục / trường đại học thành viên | 104 |
| Đơn vị trực thuộc | 96 |
| Cán bộ, giảng viên, viên chức, người lao động | 93 |
| Người học | 55 |
| Khác | 16 |
| Doanh nghiệp, đối tác/tổ chức nước ngoài | 12 |
| Hội đồng và thành viên hội đồng | 4 |

## Chỗ cần rà lại

**16 văn bản mang nhãn `Khác`** (6% của 268). `target_groups_seed.json` ước
vocabulary phủ 263/268 (98%), tức kỳ vọng chỉ ~5 cái. Phần chênh là model chọn
`Khác` khi đoạn văn liệt kê đối tượng theo cách bắc cầu (vd "các đơn vị, cá nhân
được giao nhiệm vụ tại Điều 3") thay vì gọi tên nhóm. Nên mở từng file đọc lại,
đừng tin con số.

**Đã sửa một lỗi của chính bộ gán:** model hay chép cả phần giải thích sau dấu
gạch (`"Người học — Học sinh, sinh viên..."`) chứ không chỉ chép nhãn. Lượt chạy
đầu bộ so khớp không nhận ra dạng này và gán oan `Khác` cho 7 file
(`0389` `0483` `0362` `0346` `0173` `0242` `0416`). `_doc_mang_nhom()` giờ cắt ở
dấu gạch trước khi so khớp, và 7 file đó đã được gán lại đúng.

## Cách nhãn được ràng buộc

Nhãn model trả về đi qua `normalize.slug()` rồi phải khớp một mục trong
`src/legal_knowledge_graph/reference/target_groups_seed.json` — cùng đúng phép so
khớp mà `core/validate.py` dùng, nên không lệch được. Nhãn không khớp bị loại và
in ra màn hình. Mỗi file sau khi gán còn phải qua trọn bộ `load_and_validate()`;
trượt schema thì **không ghi sang v2**, giữ nguyên bản v1.

`python run.py lkg validate --dir data/clean/json/v2` → 418/418 hợp lệ.
