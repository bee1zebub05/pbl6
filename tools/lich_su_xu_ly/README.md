# Lưu trữ mã xử lý dữ liệu (8–9/2026)

Mã nguồn của các đợt OCR, hiệu đính và dựng kho `text_final`, viết và chạy ngoài git trong
thư mục `F:\DUT4\PBL6\project\` ở máy của Kiên. Đưa vào repo ngày 16/11/2026 để mã của các
bước mà báo cáo mô tả (mục 3.4) không chỉ còn một bản trên một máy.

**Đây là bản lưu trữ, không chạy được tại chỗ.** Các script tự tìm thư mục gốc bằng
`Path(__file__).resolve().parents[2]`, tức giả định cấu trúc cũ:

```
<gốc>/
├── data/            raw/pdf, processed/..., clean/...
└── project/
    ├── gemini_ocr/  (thư mục gemini_ocr ở đây)
    ├── scripts/
    └── viz/
```

Muốn chạy lại thì chép thư mục con vào `<gốc>/project/` như trên. Kết quả cuối của các bước
này đã nằm trong `data/clean/text_final/`; luồng xử lý đang dùng xem `src/vanban/` và `tools/`.

| Thư mục | Nội dung |
|---|---|
| `gemini_ocr/` | OCR lượt hai bằng Gemma, cứu lỗi RECITATION (chia trang, cắt góc), vá khúc hỏng, dọn watermark, sửa lỗi ký tự, dựng bản sạch và bản cuối, kiểm chứng số hiệu và người ký; tiện ích Chrome `extension/` cùng `bridge.py` cho đợt rà soát qua giao diện web Gemini. Chi tiết: `gemini_ocr/README.md` |
| `scripts/` | Thử nghiệm ban đầu: trích lớp chữ PDF, OCR thử, so sánh các engine OCR |
| `viz/` | App Streamlit khám phá đồ thị của pipeline quy tắc cũ (`chay_viz.bat` ở thư mục gốc gọi app này) |

Không đưa vào: log và `.err` của các lượt chạy, tệp trạng thái (`state.json`,
`trang_thai*.json`), danh sách trung gian (`ds_*.json`, `ngo_so*.json`), báo cáo lỗi tự sinh,
bản sao lưu `.bak` và thư mục `_sao_luu_truoc_khi_va/`. Các tệp này vẫn nằm ở thư mục gốc cũ.
