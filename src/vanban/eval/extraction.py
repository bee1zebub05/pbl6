"""
§6.1–6.2 — độ đồng thuận giữa hai người gán, và P/R/F1 của bộ trích xuất.

Hai việc tách hẳn nhau:

* `kappa()` đọc hai thư mục phiếu đã điền, đo **Cohen's κ**. Chạy được ngay sau
  vòng gán thử 20 văn bản, không cần chờ gán hết — đó là mục đích của nó.
* `cham_diem()` gộp hai bản gán thành gold rồi so với nhãn máy.

## Hai tầng lỗi, đo riêng (§6.2)

    detection  — có nhận ra đây là một quan hệ, và đúng loại không?
    resolution — có nối đúng văn bản đích không?

Gộp hai tầng lại thì một cạnh `REPLACES` trỏ nhầm văn bản và một cạnh bỏ sót
hoàn toàn cùng bị tính là một lỗi, trong khi nguyên nhân và cách sửa khác hẳn:
cái đầu là lỗi chuẩn hoá số hiệu, cái sau là lỗi luật phân loại.

## Bỏ sót do máy không bắt được số hiệu

Dòng người gán tự thêm (`GHI_CHU = may-bo-sot`, không có `id`) là **false
negative của tầng phát hiện** — máy còn không sinh ra ứng viên để mà phân loại.
Bỏ qua nhóm này thì recall báo cáo ra sẽ cao giả.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from .. import config
from ..pipeline import say

QUAN_HE = ("BASED_ON", "REFERENCES", "REPLACES", "AMENDS", "REPEALS")
KHONG = "KHONG"


# ============================================================
# ĐỌC PHIẾU
# ============================================================

def doc_phieu(thu_muc: Path) -> dict[str, dict]:
    """
    Đọc một thư mục phiếu đã điền.

    Khoá: `id` của ứng viên. Dòng người gán tự thêm (không có `id`) được cấp
    khoá tổng hợp `<văn bản>|<số hiệu>|them` để vẫn đối chiếu được giữa hai
    người gán.
    """

    ket_qua: dict[str, dict] = {}

    if not thu_muc.exists():
        return ket_qua

    for path in sorted(thu_muc.glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                nhan = (row.get("NHAN") or "").strip().upper()

                if not nhan:
                    continue

                cid = (row.get("id") or "").strip()
                nguon = (row.get("van_ban_nguon") or "").strip()
                dich = (row.get("so_hieu_duoc_nhac") or "").strip()

                khoa = cid or f"{nguon}|{dich}|them"

                ket_qua[khoa] = {
                    "id": cid,
                    "nguon": nguon,
                    "dich": dich,
                    "nhan": nhan,
                    "dich_dung": (row.get("DICH_DUNG") or "").strip() or dich,
                    "ghi_chu": (row.get("GHI_CHU") or "").strip(),
                    "may_bo_sot": not cid,
                }

    return ket_qua


# ============================================================
# COHEN'S KAPPA (§6.1)
# ============================================================

def cohen_kappa(a: list[str], b: list[str]) -> float:
    """
    κ = (Po - Pe) / (1 - Pe).

    Po = tỷ lệ đồng thuận quan sát được; Pe = tỷ lệ đồng thuận **ngẫu nhiên**
    tính từ phân bố nhãn của từng người. Trừ đi Pe chính là điểm khác nhau giữa
    κ và "tỷ lệ giống nhau" — với dữ liệu lệch nặng như kho này (`REFERENCES`
    chiếm đa số), hai người gán bừa cùng một nhãn phổ biến đã đạt ~60% giống
    nhau mà không hề đồng thuận thật.
    """

    if not a:
        return float("nan")

    n = len(a)
    po = sum(1 for x, y in zip(a, b) if x == y) / n

    dem_a, dem_b = Counter(a), Counter(b)
    pe = sum(
        (dem_a[nhan] / n) * (dem_b[nhan] / n) for nhan in set(dem_a) | set(dem_b)
    )

    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def kappa(goldset_dir: Path | None = None) -> dict:
    """So hai thư mục `nguoi_gan_1/` và `nguoi_gan_2/`."""

    goldset_dir = goldset_dir or config.EVAL_DIR / "goldset"

    a = doc_phieu(goldset_dir / "nguoi_gan_1")
    b = doc_phieu(goldset_dir / "nguoi_gan_2")

    chung = sorted(set(a) & set(b))

    ket_qua: dict = {
        "nguoi_gan_1": len(a),
        "nguoi_gan_2": len(b),
        "cung_gan": len(chung),
        "chi_mot_nguoi_gan": len(set(a) ^ set(b)),
    }

    if not chung:
        ket_qua["loi"] = (
            "Chưa có ứng viên nào được cả hai người gán. Kiểm tra "
            f"{goldset_dir / 'nguoi_gan_1'} và {goldset_dir / 'nguoi_gan_2'}."
        )
        return ket_qua

    nhan_a = [a[k]["nhan"] for k in chung]
    nhan_b = [b[k]["nhan"] for k in chung]

    ket_qua["kappa_tong"] = round(cohen_kappa(nhan_a, nhan_b), 4)
    ket_qua["dong_thuan_tho"] = round(
        sum(1 for x, y in zip(nhan_a, nhan_b) if x == y) / len(chung), 4
    )

    # κ theo từng nhãn: gộp về nhị phân "là nhãn này / không phải". Nhãn hiếm
    # có thể κ thấp trong khi κ tổng vẫn đẹp — đó mới là chỗ cần sửa guideline.
    theo_nhan = {}

    for nhan in QUAN_HE + (KHONG,):
        x = [nhan if v == nhan else "~" for v in nhan_a]
        y = [nhan if v == nhan else "~" for v in nhan_b]

        if nhan in nhan_a or nhan in nhan_b:
            theo_nhan[nhan] = {
                "kappa": round(cohen_kappa(x, y), 4),
                "so_lan_nguoi_1": nhan_a.count(nhan),
                "so_lan_nguoi_2": nhan_b.count(nhan),
            }

    ket_qua["theo_nhan"] = theo_nhan

    # Ma trận bất đồng — bảng để mang vào buổi thống nhất guideline.
    bat_dong = Counter(
        (x, y) for x, y in zip(nhan_a, nhan_b) if x != y
    )
    ket_qua["bat_dong_nhieu_nhat"] = [
        {"nguoi_1": x, "nguoi_2": y, "so_lan": n}
        for (x, y), n in bat_dong.most_common(10)
    ]

    # Danh sách ứng viên bất đồng, để mở ra soi từng cái.
    ket_qua["vi_du_bat_dong"] = [
        {"id": k, "nguon": a[k]["nguon"], "dich": a[k]["dich"],
         "nguoi_1": a[k]["nhan"], "nguoi_2": b[k]["nhan"]}
        for k in chung
        if a[k]["nhan"] != b[k]["nhan"]
    ][:40]

    return ket_qua


# ============================================================
# GỘP THÀNH GOLD
# ============================================================

def gop_gold(goldset_dir: Path | None = None) -> tuple[dict[str, dict], dict]:
    """
    Gộp hai bản gán thành một gold set.

    Chỗ hai người khớp nhau -> lấy luôn. Chỗ bất đồng -> **loại khỏi gold**,
    không phải chọn bừa một bên. Chấm điểm trên những ca mà chính con người
    cũng không thống nhất được là đo nhiễu chứ không đo hệ thống; §6.7 thì vẫn
    liệt kê chúng ra như một loại lỗi riêng.

    Chỉ có một người gán (mới gán thử) -> dùng luôn bản đó, và ghi rõ trong
    báo cáo là chưa có κ.
    """

    goldset_dir = goldset_dir or config.EVAL_DIR / "goldset"

    a = doc_phieu(goldset_dir / "nguoi_gan_1")
    b = doc_phieu(goldset_dir / "nguoi_gan_2")

    if not b:
        return a, {"nguon": "chi-nguoi-gan-1", "bo_vi_bat_dong": 0}

    if not a:
        return b, {"nguon": "chi-nguoi-gan-2", "bo_vi_bat_dong": 0}

    gold: dict[str, dict] = {}
    bo = 0

    for khoa in set(a) | set(b):
        if khoa in a and khoa in b:
            if a[khoa]["nhan"] == b[khoa]["nhan"]:
                gold[khoa] = a[khoa]
            else:
                bo += 1
        else:
            # Chỉ một người thấy (thường là dòng "máy bỏ sót" người kia không
            # phát hiện) -> giữ, nhưng đánh dấu để §6.7 xem lại.
            gold[khoa] = (a.get(khoa) or b[khoa]) | {"chi_mot_nguoi": True}

    return gold, {"nguon": "hai-nguoi-gop", "bo_vi_bat_dong": bo}


# ============================================================
# CHẤM ĐIỂM (§6.2)
# ============================================================

def _prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0

    return {
        "P": round(p, 4),
        "R": round(r, 4),
        "F1": round(f, 4),
        "TP": tp,
        "FP": fp,
        "FN": fn,
    }


def cham_diem(goldset_dir: Path | None = None) -> dict:
    """P/R/F1 từng loại quan hệ, tách tầng detection và resolution."""

    goldset_dir = goldset_dir or config.EVAL_DIR / "goldset"
    gold, thong_tin = gop_gold(goldset_dir)

    if not gold:
        return {
            "loi": "Chưa có phiếu nào được điền. Xem "
                   f"{goldset_dir / 'huong_dan_gan.md'}"
        }

    he_thong_path = goldset_dir / "he_thong.jsonl"

    if not he_thong_path.exists():
        return {"loi": f"Thiếu {he_thong_path} — chạy `python run.py eval sample`."}

    may: dict[str, dict] = {}

    with he_thong_path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            may[str(row["id"])] = row

    # --- tầng DETECTION ---
    det: dict[str, Counter] = defaultdict(Counter)
    bo_sot_hoan_toan = Counter()

    for khoa, muc in gold.items():
        that = muc["nhan"]

        if muc["may_bo_sot"]:
            # Máy không sinh ra ứng viên -> false negative, trừ khi người gán
            # cũng bảo đây không phải quan hệ.
            if that != KHONG:
                det[that]["FN"] += 1
                bo_sot_hoan_toan[that] += 1
            continue

        doan = (may.get(muc["id"]) or {}).get("relation") or KHONG

        if doan == that:
            if that != KHONG:
                det[that]["TP"] += 1
        else:
            if that != KHONG:
                det[that]["FN"] += 1
            if doan != KHONG:
                det[doan]["FP"] += 1

    detection = {
        rel: _prf(det[rel]["TP"], det[rel]["FP"], det[rel]["FN"])
        for rel in QUAN_HE
        if sum(det[rel].values())
    }

    tong = Counter()

    for rel in QUAN_HE:
        tong.update(det[rel])

    detection["_TONG_micro"] = _prf(tong["TP"], tong["FP"], tong["FN"])

    # --- tầng RESOLUTION ---
    #
    # Chỉ xét những ứng viên mà cả người lẫn máy đều coi là quan hệ thật. Câu
    # hỏi ở đây khác hẳn: bỏ qua chuyện loại quan hệ, số hiệu đích có đúng
    # không? Đích sai nhưng loại đúng vẫn là một cạnh trỏ nhầm chỗ.
    res_dung = res_sai = res_khong_noi = 0

    for khoa, muc in gold.items():
        if muc["may_bo_sot"] or muc["nhan"] == KHONG:
            continue

        row = may.get(muc["id"])

        if not row:
            continue

        if not row["resolved"]:
            res_khong_noi += 1
        elif row["target_key"] == muc["dich_dung"]:
            res_dung += 1
        else:
            res_sai += 1

    tong_res = res_dung + res_sai + res_khong_noi

    resolution = {
        "dung": res_dung,
        "noi_sai_van_ban": res_sai,
        "khong_noi_duoc": res_khong_noi,
        "do_chinh_xac": round(res_dung / tong_res, 4) if tong_res else 0.0,
    }

    return {
        "gold": {
            "so_ung_vien": len(gold),
            "so_van_ban": len({m["nguon"] for m in gold.values()}),
            **thong_tin,
            "may_bo_sot_hoan_toan": dict(bo_sot_hoan_toan),
        },
        "detection": detection,
        "resolution": resolution,
    }


# ============================================================
# XUẤT
# ============================================================

def _bang_prf(ten: str, data: dict) -> list[str]:
    lines = [
        "",
        f"### {ten}",
        "",
        "| Quan hệ | P | R | F1 | TP | FP | FN |",
        "|---|---|---|---|---|---|---|",
    ]

    for rel, m in data.items():
        ten_hien = "**micro tổng**" if rel.startswith("_") else f"`{rel}`"
        lines.append(
            f"| {ten_hien} | {m['P']:.3f} | {m['R']:.3f} | {m['F1']:.3f} "
            f"| {m['TP']} | {m['FP']} | {m['FN']} |"
        )

    return lines


def xuat(out_dir: Path | None = None, goldset_dir: Path | None = None) -> dict:
    """Chạy cả κ lẫn chấm điểm, ghi JSON + Markdown."""

    out_dir = out_dir or config.EVAL_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    kq_kappa = kappa(goldset_dir)
    kq_diem = cham_diem(goldset_dir)

    (out_dir / "agreement.json").write_text(
        json.dumps(kq_kappa, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "extraction_metrics.json").write_text(
        json.dumps(kq_diem, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = ["# §6.1–6.2 — Đồng thuận và độ chính xác trích xuất", ""]

    if "loi" in kq_kappa:
        lines += [f"> ⚠️ {kq_kappa['loi']}", ""]
    else:
        lines += [
            "## Đồng thuận giữa hai người gán (§6.1)",
            "",
            f"- Cùng gán: **{kq_kappa['cung_gan']}** ứng viên",
            f"- Chỉ một người gán: {kq_kappa['chi_mot_nguoi_gan']}",
            f"- Đồng thuận thô: {kq_kappa['dong_thuan_tho']:.1%}",
            f"- **Cohen's κ = {kq_kappa['kappa_tong']:.3f}** "
            f"({_doc_kappa(kq_kappa['kappa_tong'])})",
            "",
            "| Nhãn | κ | người 1 | người 2 |",
            "|---|---|---|---|",
        ]

        for nhan, m in kq_kappa.get("theo_nhan", {}).items():
            lines.append(
                f"| `{nhan}` | {m['kappa']:.3f} | {m['so_lan_nguoi_1']} "
                f"| {m['so_lan_nguoi_2']} |"
            )

        if kq_kappa.get("bat_dong_nhieu_nhat"):
            lines += ["", "**Bất đồng hay gặp nhất** — mang vào buổi sửa guideline:", ""]

            for m in kq_kappa["bat_dong_nhieu_nhat"]:
                lines.append(
                    f"- `{m['nguoi_1']}` ↔ `{m['nguoi_2']}` — {m['so_lan']} lần"
                )

    lines += ["", "---", ""]

    if "loi" in kq_diem:
        lines += [f"> ⚠️ {kq_diem['loi']}", ""]
    else:
        g = kq_diem["gold"]
        lines += [
            "## Độ chính xác trích xuất (§6.2)",
            "",
            f"Gold set: **{g['so_ung_vien']} ứng viên / {g['so_van_ban']} văn bản** "
            f"(nguồn: {g['nguon']}, loại {g['bo_vi_bat_dong']} ca hai người bất đồng)",
        ]

        # Loại ca bất đồng là chuyện phải làm, nhưng KHÔNG trung tính: ca khó
        # với người thường cũng là ca khó với máy, nên bỏ chúng đi thì điểm báo
        # cáo cao hơn thực tế. Nói rõ mức độ để người đọc paper tự trừ hao.
        if g["bo_vi_bat_dong"]:
            ty_le = 100 * g["bo_vi_bat_dong"] / (
                g["so_ung_vien"] + g["bo_vi_bat_dong"]
            )
            lines += [
                "",
                f"> ⚠️ **{ty_le:.0f}% số ca bị loại vì hai người gán bất đồng.** "
                "Phép loại này không trung tính: ca mà người còn cãi nhau thường "
                "cũng là ca máy dễ sai, nên điểm dưới đây **lạc quan hơn thực "
                "tế**. Cách xử lý đúng là sửa guideline rồi gán lại cho tới khi "
                "tỷ lệ này đủ nhỏ, chứ không phải chấp nhận con số hiện tại.",
            ]

        if g["may_bo_sot_hoan_toan"]:
            lines += [
                "",
                "Máy **không sinh ra ứng viên** (lỗi tầng phát hiện, không phải "
                "tầng phân loại): "
                + ", ".join(f"`{k}` × {v}" for k, v in g["may_bo_sot_hoan_toan"].items()),
            ]

        lines += _bang_prf("Tầng detection — có nhận ra đúng loại quan hệ không", kq_diem["detection"])

        r = kq_diem["resolution"]
        lines += [
            "",
            "### Tầng resolution — có nối đúng văn bản đích không",
            "",
            f"- Nối đúng: **{r['dung']}**",
            f"- Nối nhầm văn bản khác: {r['noi_sai_van_ban']}",
            f"- Không nối được vào node nào: {r['khong_noi_duoc']}",
            f"- **Độ chính xác resolution = {r['do_chinh_xac']:.1%}**",
        ]

    lines.append("")

    path = out_dir / "extraction.md"
    path.write_text("\n".join(lines), encoding="utf-8")

    say(f"  {path}")
    say(f"  {out_dir / 'agreement.json'}")
    say(f"  {out_dir / 'extraction_metrics.json'}")

    return {"kappa": kq_kappa, "metrics": kq_diem}


def _doc_kappa(k: float) -> str:
    """Thang Landis & Koch — thang quy ước hay được trích trong paper."""

    for nguong, ten in (
        (0.81, "gần như hoàn hảo"),
        (0.61, "đáng kể"),
        (0.41, "vừa phải"),
        (0.21, "yếu"),
        (0.0, "rất yếu"),
    ):
        if k >= nguong:
            return ten

    return "tệ hơn ngẫu nhiên"
