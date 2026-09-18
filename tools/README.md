# `tools/` — công cụ chạy tay, không thuộc package

Khác `src/vanban/` ở chỗ: package là đường chạy chính (`python run.py …`), còn đây là
công cụ dùng theo đợt, chạy trực tiếp bằng `python <file>.py`. Không import chéo với
package, không nằm trong luồng `run.py`.

| Thư mục | Dùng để |
|---|---|
| [`gemini_web/`](gemini_web/) | Hiệu đính OCR hàng loạt bằng **giao diện web Gemini** (extension Chrome + máy chủ hàng chờ) |
| [`kiem_tra/`](kiem_tra/) | Đo chất lượng kho `data/clean/text_final` theo các trường mà knowledge graph cần |

Cả hai đều đọc `data/clean/text_final` và ghi kết quả vào `data/kiem_tra/`.

---

## Vì sao tách khỏi `src/vanban/`

`src/vanban/clean/` hiệu đính bằng **API chính thức** (`gemini_fix.py`, có `key_pool`,
có hạn mức, chạy trong pipeline có session). `tools/gemini_web/` thì lái **giao diện
web** bằng script — không phải API, không nằm trong pipeline, và có ràng buộc pháp lý
riêng (xem README của nó). Trộn hai thứ vào một chỗ là nhầm lẫn nguy hiểm.

`tools/kiem_tra/` đo trên kho đã chốt, độc lập với `src/vanban/kg/`. Hai bộ này có
phần chồng nhau (cùng trích số hiệu, người ký, quan hệ hiệu lực) — đây là **nợ kỹ
thuật đã biết**, ghi ra đây để không ai tưởng là cố ý thiết kế vậy. Bộ trong `kg/` là
bộ chính thức nạp vào Neo4j; bộ ở đây chỉ sinh báo cáo kiểm tra.
