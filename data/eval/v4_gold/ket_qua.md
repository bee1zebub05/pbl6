# Kết quả đối chứng JSON v4 (103 văn bản)
Bộ nhãn A = `nhan_ai_1`, B = `nhan_ai_2`, danh sách `danh_sach_103.json`. Sinh bởi `python data/eval/v4_gold/tinh_diem.py`.
## Độ đồng thuận giữa A và B
| Chỉ số | Giá trị |
|---|---|
| Số cặp nguồn–đích (hợp hai bên) | 906 |
| Tỉ lệ đồng ý thô | 0.932 |
| Cohen's κ (quan hệ, kể cả KHONG) | 0.887 |
| Cohen's κ (loại quan hệ, trên 904 cặp cả hai cùng có) | 0.891 |
| F1 người ký giữa A và B | 1.0 |
| F1 nhóm đối tượng giữa A và B | 0.961 |

## Độ chính xác của JSON v4
| Hạng mục | P (A) | R (A) | F1 (A) | P (B) | R (B) | F1 (B) | F1 trung bình |
|---|---|---|---|---|---|---|---|
| Phát hiện cặp nguồn–đích | 0.996 | 0.931 | 0.963 | 0.996 | 0.931 | 0.963 | 0.963 |
| Quan hệ (cặp + loại) | 0.959 | 0.818 | 0.883 | 0.948 | 0.822 | 0.88 | 0.881 |
| Người ký | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| Nhóm đối tượng | 0.652 | 0.867 | 0.745 | 0.65 | 0.867 | 0.743 | 0.744 |

### Theo từng loại quan hệ
| Loại | Số nhãn A | Số nhãn B | Số trong v4 | F1 (A) | F1 (B) | F1 trung bình |
|---|---|---|---|---|---|---|
| BASED_ON | 577 | 589 | 598 | 0.97 | 0.962 | 0.966 |
| REFERENCES | 299 | 271 | 132 | 0.608 | 0.596 | 0.602 |
| REPLACES | 78 | 78 | 76 | 0.987 | 0.987 | 0.987 |
| AMENDS | 14 | 14 | 13 | 0.815 | 0.815 | 0.815 |
| REPEALS | 23 | 24 | 27 | 0.92 | 0.941 | 0.93 |

Tầng phân loại: trên các cặp v4 và A cùng phát hiện, v4 gán đúng loại 728/843; so với B: 733/843.

Văn bản thiếu nhãn: {'a': 0, 'b': 0, 'v4': 0}. Danh sách bất đồng giữa A và B: `ket_qua.json` → `dong_thuan.bat_dong`.
