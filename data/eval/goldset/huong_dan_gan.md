# Hướng dẫn gán gold set

> Sinh tự động bởi `python run.py eval sample`. Sửa trực tiếp file này khi hai
> người gán thống nhất được một quy ước mới — §6.1 yêu cầu guideline phải được
> tài liệu hoá, và nó là thứ **sẽ thay đổi** sau vòng gán thử đầu tiên.

## Việc phải làm

Mỗi file trong `phieu_gan/` ứng với một văn bản. Mỗi dòng là một **số hiệu
được nhắc tới** trong văn bản đó. Với từng dòng, điền hai cột:

- **`NHAN`** — quan hệ giữa *văn bản nguồn* và *số hiệu được nhắc*.
- **`DICH_DUNG`** — chỉ điền khi cột `so_hieu_duoc_nhac` bị sai (máy nối nhầm
  văn bản). Ghi số hiệu đúng vào đây. Đúng rồi thì để trống.

Hai cột này tách bạch đúng hai tầng lỗi mà §6.2 yêu cầu đo riêng: *detection*
(có nhận ra quan hệ không) và *resolution* (nối đúng văn bản đích không).

## Giá trị hợp lệ của `NHAN`

| Nhãn | Khi nào | Dấu hiệu trong câu |
|---|---|---|
| `BASED_ON` | Văn bản nguồn lấy cái được nhắc làm **cơ sở pháp lý** | nằm trong khối "Căn cứ ..." đầu văn bản |
| `REFERENCES` | Chỉ **nhắc tới**, dẫn chiếu, không thay đổi hiệu lực | "theo quy định tại...", "hướng dẫn tại..." |
| `REPLACES` | Nguồn **thay thế** cái được nhắc → cái đó hết hiệu lực, nguồn thế chỗ | "thay thế ..." |
| `AMENDS` | Nguồn **sửa đổi / bổ sung** → cái đó **VẪN còn hiệu lực** | "sửa đổi, bổ sung một số điều của ..." |
| `REPEALS` | Nguồn **bãi bỏ** → cái đó hết hiệu lực, **không ai thế chỗ** | "bãi bỏ ...", "huỷ bỏ ..." |
| `KHONG` | Không phải quan hệ | số hiệu do OCR bịa, số trang, số công báo, hoặc chỉ là một phần trong tên của văn bản khác |

## Bốn quy ước dễ gây bất đồng

**1. Chủ ngữ là ai?** Chỉ gán quan hệ hiệu lực khi **chính văn bản nguồn** là
người thực hiện hành động. Câu:

> "...theo Nghị định số 09/2010/NĐ-CP ... sửa đổi, bổ sung Nghị định số
> 110/2004/NĐ-CP..."

Ở đây người sửa là 09/2010, **không phải** văn bản đang đọc. Cả hai dòng
`09/2010` và `110/2004` đều gán `REFERENCES`, không phải `AMENDS`.

**2. `REPLACES` khác `AMENDS`.** Đây là chỗ ontology nhấn mạnh nhất: `AMENDS`
**không** làm văn bản đích hết hiệu lực, hai cái kia thì có. Gán nhầm là sai
hẳn câu trả lời "văn bản nào đang còn hiệu lực".

**3. Cùng một số hiệu xuất hiện nhiều lần** → gán từng dòng độc lập theo đúng
ngữ cảnh của dòng đó. Một văn bản vừa `BASED_ON` vừa `REPLACES` một văn bản
khác là chuyện bình thường.

**4. Thiếu sót của máy.** Nếu đọc văn bản gốc mà thấy một quan hệ **không có
dòng nào** trong phiếu, thêm một dòng mới ở cuối: để trống `id`, điền
`so_hieu_duoc_nhac`, `NHAN`, và ghi `GHI_CHU = may-bo-sot`. Đây chính là dữ
liệu để đo **recall**, đừng bỏ qua.

Văn bản gốc nằm ở `data/clean/text_clean_gemma/<lĩnh vực>/`, tìm theo số hiệu.

## Quy trình

1. **Hai người gán độc lập.** Không xem bài của nhau, không xem nhãn máy.
2. Gán thử **20 văn bản đầu** → chạy `python run.py eval kappa` → ngồi lại xem
   chỗ bất đồng → **sửa file hướng dẫn này** → gán lại 20 văn bản đó.
3. Gán nốt phần còn lại.
4. `python run.py eval kappa` lần cuối để lấy con số κ đưa vào paper.
5. `python run.py eval extraction` để ra P/R/F1.

## Nộp bài

Người thứ nhất lưu phiếu đã điền vào `nguoi_gan_1/`, người thứ hai vào
`nguoi_gan_2/` — giữ nguyên tên file. Ví dụ:

```
data/eval/goldset/nguoi_gan_1/10_2016_TT-BGDDT.csv
data/eval/goldset/nguoi_gan_2/10_2016_TT-BGDDT.csv
```
