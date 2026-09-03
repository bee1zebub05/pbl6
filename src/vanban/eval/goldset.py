"""
§6.1 — chọn gold set và sinh phiếu gán.

## Vì sao phân tầng chứ không bốc ngẫu nhiên

Ontology nói "chọn 50–100 Document đa dạng". Đúng về bậc độ lớn, nhưng bốc ngẫu
nhiên thì hỏng ở chỗ khác: mật độ quan hệ trong kho lệch nhau hàng chục lần.

| Quan hệ      | Có mặt ở | Bốc ngẫu nhiên 75 VB bắt được |
| ------------ | -------- | ----------------------------- |
| `REFERENCES` | 356/448  | ~641 thể hiện                 |
| `BASED_ON`   | 354/448  | ~328                          |
| `REPLACES`   | 114/448  | ~22                           |
| `AMENDS`     |  42/448  | ~20                           |
| `REPEALS`    |  38/448  | **~9**                        |

Với n=328 thì khoảng tin cậy 95% của F1 rộng chừng ±3 điểm phần trăm. Với n=9
nó rộng ±20 điểm — mà §6.2 lại yêu cầu báo cáo P/R/F1 **cho từng loại quan hệ,
đừng gộp**. Vậy nên phải cố ý lấy thừa ở nhóm hiếm.

## Ba tầng

    A. Hệ thống có gán quan hệ hiệu lực   -> đo PRECISION của nhóm hiếm
    B. Có trích dẫn trong điều khoản thi
       hành nhưng hệ thống IM LẶNG        -> đo RECALL (nơi false negative ở)
    C. Ngẫu nhiên toàn kho                -> ước lượng KHÔNG THIÊN LỆCH

Tầng B là tầng dễ bị bỏ quên nhất và cũng là tầng quan trọng nhất. Nếu chỉ lấy
mẫu ở những chỗ hệ thống đã gán (tầng A), ta chỉ biết "cái nó nói có đúng
không", không bao giờ biết "nó bỏ sót bao nhiêu". Tầng B định nghĩa bằng **cấu
trúc** (Bước 1: có trích dẫn nằm trong điều khoản thi hành) chứ không bằng đầu
ra của Bước 3 — đó là điều kiện để nó không thiên lệch theo chính hệ thống đang
được chấm.

## Phiếu gán cố ý KHÔNG hiện nhãn của hệ thống

Người gán nhìn thấy nhãn máy thì gật theo, κ đo ra sẽ đẹp giả. Nhãn hệ thống
được cất riêng ở `he_thong.jsonl`, chỉ ghép lại lúc chấm điểm.
"""

from __future__ import annotations

import csv
import json
import random
import sqlite3
from pathlib import Path

from .. import config
from ..pipeline import say
from ..kg.session import KGSession

# Nhãn hợp lệ mà người gán được điền. `KHONG` = đây không phải một quan hệ
# (số hiệu bị OCR bịa ra, hoặc chỉ là tên văn bản nhắc thoáng qua).
NHAN_HOP_LE = (
    "BASED_ON",
    "REFERENCES",
    "REPLACES",
    "AMENDS",
    "REPEALS",
    "KHONG",
)

# Cỡ mặc định từng tầng. Tổng ~130 — nhỉnh hơn khoảng 50–100 của §6.1, nhưng
# đổi lại `AMENDS`/`REPEALS` được phủ gần như trọn vẹn thay vì 20 và 9 mẫu.
MAC_DINH = {"A": 71, "B": 30, "C": 30}

SEED = 20260827


def _chon_tang(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Ba tầng, đã loại chồng lấn (một văn bản chỉ nằm ở đúng một tầng)."""

    def keys(sql: str) -> list[str]:
        return [row[0] for row in conn.execute(sql)]

    tang_a = keys(
        "SELECT DISTINCT doc_key FROM citations "
        "WHERE relation IN ('REPLACES', 'AMENDS', 'REPEALS') ORDER BY doc_key"
    )

    # Cấu trúc, không phải đầu ra phân loại: có trích dẫn nằm trong một Điều
    # được Bước 1 đánh dấu là điều khoản thi hành, mà Bước 3 không gán quan hệ
    # hiệu lực nào.
    tang_b = keys(
        "SELECT DISTINCT doc_key FROM citations "
        "WHERE in_thi_hanh = 1 AND part_kind != 'phu_luc' "
        "AND doc_key NOT IN (SELECT doc_key FROM citations "
        "                    WHERE relation IN ('REPLACES','AMENDS','REPEALS')) "
        "ORDER BY doc_key"
    )

    da_lay = set(tang_a) | set(tang_b)

    tang_c = [
        key
        for key in keys(
            "SELECT doc_key FROM docs WHERE cite_status = 'done' "
            "AND clean_path IS NOT NULL ORDER BY doc_key"
        )
        if key not in da_lay
    ]

    return {"A": tang_a, "B": tang_b, "C": tang_c}


def _lay_mau(pool: list[str], n: int, rng: random.Random) -> list[str]:
    return sorted(pool) if n >= len(pool) else sorted(rng.sample(sorted(pool), n))


def chon(
    session: KGSession,
    co_mau: dict[str, int] | None = None,
    seed: int = SEED,
) -> dict[str, list[str]]:
    """Chọn gold set. Cùng `seed` thì cùng kết quả, chạy ở máy nào cũng vậy."""

    co_mau = co_mau or MAC_DINH
    rng = random.Random(seed)

    with session._lock:  # noqa: SLF001
        pools = _chon_tang(session._conn)  # noqa: SLF001

    return {tang: _lay_mau(pools[tang], co_mau.get(tang, 0), rng) for tang in "ABC"}


# ============================================================
# PHIẾU GÁN
# ============================================================

_COT_PHIEU = [
    "id",
    "van_ban_nguon",
    "so_hieu_duoc_nhac",
    "nguyen_van",
    "vung",
    "dieu",
    "trong_dieu_khoan_thi_hanh",
    "ngu_canh",
    "NHAN",          # người gán điền
    "DICH_DUNG",     # người gán điền khi số hiệu đích bị nối sai
    "GHI_CHU",
]


def sinh_phieu(
    session: KGSession,
    mau: dict[str, list[str]],
    out_dir: Path | None = None,
) -> dict[str, Path]:
    """
    Sinh phiếu gán (CSV mở được bằng Excel) + bản nhãn hệ thống cất riêng.

    Mỗi dòng là một **ứng viên** — mọi số hiệu Bước 2 tìm thấy trong văn bản,
    kể cả cái Bước 3 cho là `REFERENCES` hay bỏ qua. Người gán chấm từng dòng.
    """

    out_dir = out_dir or config.EVAL_DIR / "goldset"
    phieu_dir = out_dir / "phieu_gan"
    phieu_dir.mkdir(parents=True, exist_ok=True)

    tang_cua = {key: tang for tang, keys in mau.items() for key in keys}
    tat_ca = sorted(tang_cua)

    with session._lock:  # noqa: SLF001
        rows = session._conn.execute(  # noqa: SLF001
            "SELECT id, doc_key, target_key, surface, zone, article_number, "
            "in_thi_hanh, context, relation, resolved FROM citations "
            f"WHERE doc_key IN ({','.join('?' * len(tat_ca))}) "
            "ORDER BY doc_key, offset",
            tat_ca,
        ).fetchall()

    theo_vb: dict[str, list] = {key: [] for key in tat_ca}

    for row in rows:
        theo_vb[row["doc_key"]].append(row)

    he_thong = out_dir / "he_thong.jsonl"
    danh_sach = out_dir / "danh_sach.csv"

    # --- nhãn của hệ thống: cất riêng, người gán KHÔNG được thấy ---
    with he_thong.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    {
                        "id": row["id"],
                        "doc_key": row["doc_key"],
                        "target_key": row["target_key"],
                        "relation": row["relation"],
                        "resolved": bool(row["resolved"]),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    # --- danh sách văn bản trong gold set ---
    with danh_sach.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["tang", "so_hieu", "so_ung_vien", "file_phieu"])

        for key in tat_ca:
            writer.writerow(
                [
                    tang_cua[key],
                    key,
                    len(theo_vb[key]),
                    f"phieu_gan/{_ten_file(key)}.csv",
                ]
            )

    # --- một phiếu cho mỗi văn bản ---
    for key in tat_ca:
        path = phieu_dir / f"{_ten_file(key)}.csv"

        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(_COT_PHIEU)

            for row in theo_vb[key]:
                writer.writerow(
                    [
                        row["id"],
                        row["doc_key"],
                        row["target_key"],
                        row["surface"],
                        row["zone"] or "",
                        row["article_number"] or "",
                        "x" if row["in_thi_hanh"] else "",
                        " ".join((row["context"] or "").split()),
                        "",
                        "",
                        "",
                    ]
                )

    say(f"  {len(tat_ca):>4} văn bản  |  {len(rows):,} ứng viên cần gán")
    say(f"  phiếu gán      -> {phieu_dir}")
    say(f"  danh sách      -> {danh_sach}")
    say(f"  nhãn hệ thống  -> {he_thong}  (KHÔNG đưa cho người gán)")

    return {"phieu": phieu_dir, "danh_sach": danh_sach, "he_thong": he_thong}


def _ten_file(doc_key: str) -> str:
    """`10/2016/TT-BGDDT` -> `10_2016_TT-BGDDT` (dấu `/` không đặt tên file được)."""

    return doc_key.replace("/", "_")


# ============================================================
# HƯỚNG DẪN GÁN
# ============================================================

HUONG_DAN = """\
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
"""


def sinh_huong_dan(out_dir: Path | None = None) -> Path:
    out_dir = out_dir or config.EVAL_DIR / "goldset"
    out_dir.mkdir(parents=True, exist_ok=True)

    path = out_dir / "huong_dan_gan.md"

    # Không ghi đè: sau vòng gán thử, đây là file NGƯỜI sửa, không phải máy.
    if path.exists():
        say(f"  hướng dẫn gán  -> {path}  (đã có, giữ nguyên)")
        return path

    path.write_text(HUONG_DAN, encoding="utf-8")
    say(f"  hướng dẫn gán  -> {path}")

    return path


def chay(
    session: KGSession,
    co_mau: dict[str, int] | None = None,
    seed: int = SEED,
    out_dir: Path | None = None,
) -> dict:
    out_dir = out_dir or config.EVAL_DIR / "goldset"
    mau = chon(session, co_mau, seed)

    say("\n  Phân tầng (§6.1):")

    with session._lock:  # noqa: SLF001
        pools = _chon_tang(session._conn)  # noqa: SLF001

    nhan = {
        "A": "hệ thống có gán quan hệ hiệu lực  -> đo precision",
        "B": "có trích dẫn ở điều khoản thi hành nhưng máy im lặng -> đo recall",
        "C": "ngẫu nhiên toàn kho               -> ước lượng không thiên lệch",
    }

    for tang in "ABC":
        say(f"    {tang}  {len(mau[tang]):>3}/{len(pools[tang]):<4} {nhan[tang]}")

    say(f"    tổng {sum(len(v) for v in mau.values())} văn bản\n")

    ket_qua = sinh_phieu(session, mau, out_dir)
    sinh_huong_dan(out_dir)

    (out_dir / "phan_tang.json").write_text(
        json.dumps({"seed": seed, "co_mau": co_mau or MAC_DINH, "mau": mau},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {"mau": mau, **ket_qua}
