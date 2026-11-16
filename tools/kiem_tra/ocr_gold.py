"""
Bộ chuẩn OCR theo trang: chọn trang, xuất ảnh, chấm `text_final` so với bản chuẩn.

    python tools/kiem_tra/ocr_gold.py chon  [--so-trang 20] [--seed 6]
    python tools/kiem_tra/ocr_gold.py cham

`chon` bốc trang ngẫu nhiên (cố định seed), xuất ảnh PNG từ PDF gốc ở
data/raw/pdf và ghi manifest. Bản chuẩn của mỗi trang là file .txt cùng tên,
gõ lại từ ảnh, đặt trong data/eval/ocr_gold/chuan/.

`cham` cắt đúng trang đó ra khỏi text_final (theo mốc `[Trang N]`), so với bản
chuẩn và ghi data/eval/ocr_gold/ket_qua.md + ket_qua.json:

- CER giữ dấu: mọi sai khác ký tự, sau chuẩn hoá NFC và gộp khoảng trắng.
- CER bỏ dấu: so sau khi bỏ dấu (và đ->d); hiệu hai CER là phần lỗi nằm ở dấu.
- Token chứa chữ số (số hiệu, ngày, trích dẫn, số Điều): bao nhiêu token của
  bản chuẩn có mặt đúng nguyên dạng trong text_final của trang.

CER đếm theo grapheme sau NFC, nên "ế" là một ký tự dù gõ dựng sẵn hay tổ hợp.

Cách chọn trang: một trang mỗi văn bản để kết quả không lệch về vài văn bản.
Khoảng 40% là trang 1 (đầu văn bản: số hiệu, ngày điền tay, con dấu), phần còn
lại là trang bất kỳ. Bỏ văn bản chỉ có mốc theo khúc `[Trang a-b]` vì không cắt
được đúng một trang.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

GOC = Path(__file__).resolve().parents[2]
KHO = GOC / "data" / "clean" / "text_final"
PDF = GOC / "data" / "raw" / "pdf"
RA = GOC / "data" / "eval" / "ocr_gold"

MOC = re.compile(r"^-+ \[Trang ([^\]]+)\] -+$", re.M)
SO = re.compile(r"\d")


def _tim(goc: Path, ma: str, duoi: str) -> Path | None:
    kq = sorted(goc.rglob(f"{ma}_*{duoi}"))
    return kq[0] if kq else None


def cat_trang(text: str) -> dict[int, str]:
    """{số trang: nội dung} theo mốc `[Trang N]`. Mốc không phải số đơn bị bỏ qua."""
    moc = list(MOC.finditer(text))
    ra: dict[int, str] = {}
    for i, m in enumerate(moc):
        nhan = m.group(1).strip()
        if not nhan.isdigit():
            continue
        cuoi = moc[i + 1].start() if i + 1 < len(moc) else len(text)
        ra[int(nhan)] = ra.get(int(nhan), "") + text[m.end():cuoi]
    return ra


def chon(so_trang: int, seed: int) -> None:
    import pymupdf

    rng = random.Random(seed)
    ung_vien = []
    for txt in sorted(KHO.rglob("*.txt")):
        ma = txt.name[:4]
        pdf = _tim(PDF, ma, ".pdf")
        if not pdf:
            continue
        noi_dung = txt.read_text(encoding="utf-8")
        if re.search(r"\[Trang \d+-\d+\]", noi_dung):
            continue
        trang = cat_trang(noi_dung)
        if trang:
            ung_vien.append((ma, txt, pdf, sorted(trang)))
    rng.shuffle(ung_vien)
    so_trang_1 = round(so_trang * 0.4)
    (RA / "anh").mkdir(parents=True, exist_ok=True)
    (RA / "chuan").mkdir(parents=True, exist_ok=True)
    ds = []
    for i, (ma, txt, pdf, trang) in enumerate(ung_vien[:so_trang]):
        doc = pymupdf.open(pdf)
        hop_le = [t for t in trang if t <= doc.page_count]
        if not hop_le:
            continue
        so = 1 if i < so_trang_1 and 1 in hop_le else rng.choice(hop_le)
        ten = f"{ma}_p{so:03d}"
        doc[so - 1].get_pixmap(dpi=150).save(RA / "anh" / f"{ten}.png")
        ds.append({"ten": ten, "ma": ma, "trang": so, "so_trang_pdf": doc.page_count,
                   "so_moc_text": len(trang),
                   "pdf": str(pdf.relative_to(GOC)).replace("\\", "/"),
                   "txt": str(txt.relative_to(GOC)).replace("\\", "/")})
    (RA / "manifest.json").write_text(json.dumps({"seed": seed, "trang": ds}, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    print(f"Đã chọn {len(ds)} trang -> {RA / 'anh'}")


KIEU_CHU = str.maketrans({"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "…": "..."})


def chuan_hoa(s: str) -> str:
    """NFC, gộp khoảng trắng, và quy dấu nháy cong / gạch dài / dấu ba chấm về
    một dạng: đó là khác biệt kiểu chữ, không phải lỗi nhận dạng."""
    s = unicodedata.normalize("NFC", s).translate(KIEU_CHU)
    return re.sub(r"\s+", " ", s).strip()


def bo_dau(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    s = "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", s)


def khoang_cach(a: str, b: str) -> int:
    """Levenshtein theo ký tự (sau NFC mỗi chữ tiếng Việt là một code point)."""
    if len(a) < len(b):
        a, b = b, a
    truoc = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        hien = [i]
        for j, cb in enumerate(b, 1):
            hien.append(min(truoc[j] + 1, hien[j - 1] + 1, truoc[j - 1] + (ca != cb)))
        truoc = hien
    return truoc[-1]


def khoang_cach_ban_toan_cuc(chuan: str, van_ban: str) -> tuple[int, int, int]:
    """Edit distance giữa `chuan` và đoạn con khớp nhất của `van_ban` (bỏ qua
    phần thừa ở hai đầu van_ban). -> (khoảng cách, vị trí đầu, vị trí cuối)."""
    m = len(van_ban)
    truoc = [0] * (m + 1)
    dau_truoc = list(range(m + 1))
    for i, ca in enumerate(chuan, 1):
        hien = [i] + [0] * m
        dau = [0] + [0] * m
        for j in range(1, m + 1):
            xoa, chen, thay = truoc[j] + 1, hien[j - 1] + 1, truoc[j - 1] + (ca != van_ban[j - 1])
            if thay <= xoa and thay <= chen:
                hien[j], dau[j] = thay, dau_truoc[j - 1]
            elif xoa <= chen:
                hien[j], dau[j] = xoa, dau_truoc[j]
            else:
                hien[j], dau[j] = chen, dau[j - 1]
        truoc, dau_truoc = hien, dau
    j = min(range(m + 1), key=lambda k: truoc[k])
    return truoc[j], dau_truoc[j], j


def cua_so(chuan: str, van_ban: str) -> str:
    """Khoanh vùng trong toàn văn bản: trượt một cửa sổ dài bằng bản chuẩn,
    chọn chỗ chứa nhiều cụm 4 từ của bản chuẩn nhất, rồi nới mỗi bên 25%.
    (Lấy trung vị vị trí khớp thì hỏng với văn bản luật, nơi cùng một cụm như
    "Luật Giáo dục đại học" lặp lại ở nhiều trang.)"""
    tu_c, tu_v = chuan.split(), van_ban.split()
    cum = {" ".join(tu_c[i:i + 4]) for i in range(max(len(tu_c) - 3, 1))}
    khop = [1 if " ".join(tu_v[i:i + 4]) in cum else 0 for i in range(len(tu_v))]
    L = len(tu_c)
    if not any(khop):
        return van_ban[: len(chuan) * 2]
    dem = sum(khop[:L])
    tot, dau = dem, 0
    for i in range(1, max(len(tu_v) - L + 1, 1)):
        dem += khop[i + L - 1] - khop[i - 1]
        if dem > tot:
            tot, dau = dem, i
    return " ".join(tu_v[max(dau - L // 4, 0): dau + L + L // 4])


def token_so(s: str) -> list[str]:
    return [t.strip(".,;:()\"'") for t in s.split() if SO.search(t)]


def cham() -> None:
    man = json.loads((RA / "manifest.json").read_text(encoding="utf-8"))
    dong = []
    tong = {"ky_tu": 0, "loi": 0, "loi_bo_dau": 0, "so": 0, "so_dung": 0}
    for t in man["trang"]:
        f = RA / "chuan" / f"{t['ten']}.txt"
        if not f.exists():
            continue
        chuan = chuan_hoa(f.read_text(encoding="utf-8"))
        toan_van = (GOC / t["txt"]).read_text(encoding="utf-8")
        theo_moc = chuan_hoa(cat_trang(toan_van).get(t["trang"], ""))
        # Không tin mốc trang: tìm đoạn khớp nhất trong toàn văn bản (đã bỏ mốc).
        vung = cua_so(chuan, chuan_hoa(MOC.sub(" ", toan_van)))
        d, a, b = khoang_cach_ban_toan_cuc(chuan, vung)
        ocr = vung[a:b]
        d0 = khoang_cach(bo_dau(chuan), bo_dau(ocr))
        # Mốc đúng khi đoạn khớp nằm gọn trong phần text dưới mốc [Trang N].
        moc_dung = bool(theo_moc) and len(theo_moc) <= 1.3 * len(chuan) and ocr[:200] in theo_moc
        so_chuan = token_so(chuan)
        so_ocr = set(token_so(ocr))
        dung = sum(1 for x in so_chuan if x in so_ocr)
        thieu = [x for x in so_chuan if x not in so_ocr]
        # Đếm từ không xét thứ tự: tách lỗi nhận dạng khỏi lệch thứ tự đọc
        # (vd header hai cột đọc xen dòng vẫn đủ chữ, nhưng CER ký tự tăng).
        tu_c, tu_o = Counter(chuan.split()), Counter(ocr.split())
        tu_thieu, tu_thua = sum((tu_c - tu_o).values()), sum((tu_o - tu_c).values())
        n = max(len(chuan), 1)
        dong.append({**t, "ky_tu": len(chuan), "cer": d / n, "cer_bo_dau": d0 / n, "moc_trang_dung": moc_dung,
                     "token_so": len(so_chuan), "token_so_dung": dung, "token_so_sai": thieu,
                     "tu_thieu": tu_thieu / max(sum(tu_c.values()), 1), "tu_thua": tu_thua / max(sum(tu_o.values()), 1)})
        tong["ky_tu"] += len(chuan)
        tong["loi"] += d
        tong["loi_bo_dau"] += d0
        tong["so"] += len(so_chuan)
        tong["so_dung"] += dung
        tong["tu_c"] = tong.get("tu_c", 0) + sum(tu_c.values())
        tong["tu_o"] = tong.get("tu_o", 0) + sum(tu_o.values())
        tong["thieu"] = tong.get("thieu", 0) + tu_thieu
        tong["thua"] = tong.get("thua", 0) + tu_thua
    if not dong:
        sys.exit("Chưa có bản chuẩn nào trong data/eval/ocr_gold/chuan/")
    tom = {
        "so_trang": len(dong),
        "cer_gop": tong["loi"] / tong["ky_tu"],
        "cer_bo_dau_gop": tong["loi_bo_dau"] / tong["ky_tu"],
        "cer_trung_vi": sorted(x["cer"] for x in dong)[len(dong) // 2],
        "tu_thieu_gop": tong["thieu"] / tong["tu_c"],
        "tu_thua_gop": tong["thua"] / tong["tu_o"],
        "token_so_dung": f"{tong['so_dung']}/{tong['so']}",
        "moc_trang_dung": f"{sum(x['moc_trang_dung'] for x in dong)}/{len(dong)}",
    }
    (RA / "ket_qua.json").write_text(json.dumps({"tom_tat": tom, "trang": dong}, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    md = ["# Chấm text_final theo bộ chuẩn OCR", "",
          f"- Số trang: {tom['so_trang']}",
          f"- CER gộp (giữ dấu): {tom['cer_gop']:.2%}",
          f"- CER gộp (bỏ dấu): {tom['cer_bo_dau_gop']:.2%}",
          f"- CER trung vị theo trang: {tom['cer_trung_vi']:.2%}",
          f"- Từ thiếu (có trong bản chuẩn, không có trong text_final, không xét thứ tự): {tom['tu_thieu_gop']:.2%}",
          f"- Từ thừa (có trong text_final, không có trong bản chuẩn): {tom['tu_thua_gop']:.2%}",
          f"- Token chứa chữ số khớp nguyên dạng: {tom['token_so_dung']}",
          f"- Trang mà mốc `[Trang N]` trỏ đúng nội dung: {tom['moc_trang_dung']}", "",
          "CER tính trên đoạn khớp nhất trong toàn văn bản, không dựa vào mốc trang.", "",
          "| Trang | Ký tự | CER | CER bỏ dấu | Từ thiếu | Từ thừa | Token số đúng | Token số lệch | Mốc trang |",
          "|---|---|---|---|---|---|---|---|---|"]
    for x in sorted(dong, key=lambda r: -r["cer"]):
        md.append(f"| {x['ten']} | {x['ky_tu']} | {x['cer']:.2%} | {x['cer_bo_dau']:.2%} | "
                  f"{x['tu_thieu']:.1%} | {x['tu_thua']:.1%} | "
                  f"{x['token_so_dung']}/{x['token_so']} | {', '.join(x['token_so_sai'][:6])} | "
                  f"{'đúng' if x['moc_trang_dung'] else 'lệch'} |")
    (RA / "ket_qua.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:8]))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="lenh", required=True)
    c = sub.add_parser("chon")
    c.add_argument("--so-trang", type=int, default=20)
    c.add_argument("--seed", type=int, default=6)
    sub.add_parser("cham")
    a = ap.parse_args()
    chon(a.so_trang, a.seed) if a.lenh == "chon" else cham()


if __name__ == "__main__":
    main()
