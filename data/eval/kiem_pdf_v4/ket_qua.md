# Độ sai lệch JSON model so với bản đối chiếu PDF gốc

Số văn bản chấm: 131.

| Trường | Đúng | Tỷ lệ đúng |
|---|---|---|
| so_hieu | 127/131 | 97.0% |
| loai_van_ban | 131/131 | 100.0% |
| ngay_ban_hanh | 124/131 | 94.7% |
| ngay_hieu_luc | 118/131 | 90.1% |
| trang_thai | 128/131 | 97.7% |
| co_quan | 131/131 | 100.0% |
| so_dieu | 130/131 | 99.2% |

| Trường tập hợp | P | R | F1 |
|---|---|---|---|
| nguoi_ky | 0.92 | 0.91 | 0.91 |
| trich_dan | 0.90 | 0.78 | 0.84 |
| nhom_doi_tuong | 1.00 | 1.00 | 1.00 |
| linh_vuc | 1.00 | 1.00 | 1.00 |

| Loại quan hệ | Số trong bản chuẩn | Số model trả về | P | R | F1 |
|---|---|---|---|---|---|
| BASED_ON | 590 | 573 | 0.88 | 0.86 | 0.87 |
| REFERENCES | 65 | 50 | 1.00 | 0.77 | 0.87 |
| REPLACES | 21 | 21 | 1.00 | 1.00 | 1.00 |
| AMENDS | 22 | 18 | 0.94 | 0.77 | 0.85 |
| REPEALS | 99 | 28 | 1.00 | 0.28 | 0.44 |

Văn bản sai theo trường: so_hieu: 0025, 0081, 0219, 0340; ngay_ban_hanh: 0060, 0214, 0229, 0239, 0273, 0422, 0451; ngay_hieu_luc: 0060, 0214, 0219, 0273, 0332, 0333, 0334, 0335, 0336, 0340, 0341, 0422, 0431; trang_thai: 0390, 0433, 0453; so_dieu: 0229
