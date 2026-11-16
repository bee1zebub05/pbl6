"""
Truy nguồn tới trang PDF gốc: manifest PDF có mã hash, và bảng Điều -> trang.

    python tools/kiem_tra/nguon_trang.py              # cả hai bước, mọi phiên bản JSON
    python tools/kiem_tra/nguon_trang.py --json v4    # chỉ một phiên bản

Ra data/clean/nguon_trang/:

- pdf_manifest.json  mỗi PDF gốc trong data/raw/pdf: đường dẫn, SHA-256, số
  trang, dung lượng, và chất lượng mốc trang của text_final tương ứng. PDF
  (2,3 GB) nằm ngoài git; manifest thì vào git, nên luôn kiểm được bản PDF
  đang có có đúng là bản đã OCR hay không.
- dieu_<phiên bản>.json  mỗi Điều (khoá articleId đúng như trên graph): PDF,
  trang đầu, trang cuối, độ tin cậy. `python run.py lkg` đọc file này khi đặt
  LKG_PAGE_PROVENANCE (xem src/legal_knowledge_graph/core/ingest/graph_model.py).

Độ tin cậy theo mốc `[Trang N]` của văn bản (kiểm trên bộ chuẩn 20 trang: chỉ
10/20 trang có mốc trỏ đúng nội dung, xem data/eval/ocr_gold/ket_qua.md):

    cao          mốc đủ 1..N, khớp số trang PDF
    trung_binh   mốc tăng dần nhưng thiếu trang: trang ghi được là đúng hoặc
                 sớm hơn trang thật (một mốc gom nhiều trang PDF)
    thap         mốc lộn xộn, lặp, hoặc theo khúc [Trang a-b]
    khong_ro     không tìm thấy Điều trong text_final

Chỉ "cao" nên hiện cho người dùng như số trang chắc chắn.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

GOC = Path(__file__).resolve().parents[2]
PDF = GOC / "data" / "raw" / "pdf"
KHO = GOC / "data" / "clean" / "text_final"
JSON = GOC / "data" / "clean" / "json"
RA = GOC / "data" / "clean" / "nguon_trang"

MOC = re.compile(r"^-+ \[Trang ([^\]]+)\] -+$", re.M)


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for khoi in iter(lambda: f.read(1 << 20), b""):
            h.update(khoi)
    return h.hexdigest()


def _rut(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip()


def chat_luong_moc(nhan: list[str], so_trang: int) -> str:
    if not nhan:
        return "thap"
    if any(not x.isdigit() for x in nhan):
        return "thap"
    so = [int(x) for x in nhan]
    if so == list(range(1, so_trang + 1)):
        return "cao"
    if so == sorted(set(so)) and so[-1] <= so_trang:
        return "trung_binh"
    return "thap"


class VanBan:
    """text_final đã bỏ mốc và gộp khoảng trắng, kèm bảng vị trí -> trang."""

    def __init__(self, txt: Path):
        raw = txt.read_text(encoding="utf-8")
        self.nhan = [m.group(1).strip() for m in MOC.finditer(raw)]
        doan = MOC.split(raw)  # [trước mốc đầu, nhãn1, đoạn1, nhãn2, đoạn2, ...]
        self.text, self.moc_vi_tri, self.moc_trang = "", [], []
        for i in range(1, len(doan), 2):
            nhan, noi_dung = doan[i].strip(), _rut(doan[i + 1])
            self.moc_vi_tri.append(len(self.text))
            self.moc_trang.append(int(nhan) if nhan.isdigit() else int(re.match(r"\d+", nhan).group())
                                  if re.match(r"\d+", nhan) else None)
            self.text += noi_dung + " "

    def trang_tai(self, vi_tri: int) -> int | None:
        i = bisect.bisect_right(self.moc_vi_tri, vi_tri) - 1
        return self.moc_trang[i] if i >= 0 else None

    def tim(self, doan_dieu: str) -> tuple[int, int] | None:
        """Vị trí đầu–cuối của Điều: tìm 80 ký tự đầu, rồi 80 ký tự cuối sau đó."""
        d = _rut(doan_dieu)
        if len(d) < 20:
            return None
        dau = self.text.find(d[:80])
        if dau < 0:
            return None
        cuoi = self.text.find(d[-80:], dau)
        return dau, (cuoi + 80 if cuoi >= 0 else dau + len(d))


def manifest() -> dict[str, dict]:
    ra: dict[str, dict] = {}
    import pymupdf

    txt_theo_ma = {t.name[:4]: t for t in KHO.rglob("*.txt")}
    for p in sorted(PDF.rglob("*.pdf")):
        ma = p.name[:4]
        so_trang = pymupdf.open(p).page_count
        txt = txt_theo_ma.get(ma)
        ra[ma] = {
            "pdf": str(p.relative_to(GOC)).replace("\\", "/"),
            "sha256": _sha256(p),
            "bytes": p.stat().st_size,
            "pages": so_trang,
            "textFinal": str(txt.relative_to(GOC)).replace("\\", "/") if txt else None,
            "pageMarkers": chat_luong_moc(VanBan(txt).nhan, so_trang) if txt else None,
        }
    return ra


def dieu(phien_ban: str, man: dict[str, dict]) -> tuple[dict[str, dict], dict[str, int]]:
    sys.path.insert(0, str(GOC / "src" / "legal_knowledge_graph"))
    from core.ingest.graph_model import GraphModel  # dùng đúng hàm sinh articleId của graph

    ra: dict[str, dict] = {}
    dem: dict[str, int] = {}
    cache: dict[str, VanBan] = {}
    for f in sorted((JSON / phien_ban).rglob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        ma = Path(data.get("sourceFile") or f.name).name[:4]
        thong_tin = man.get(ma)
        model = GraphModel()
        try:
            model.add_document_file(data)
        except (KeyError, TypeError, ValueError):
            continue
        for art in model.articles:
            muc = {"pdf": thong_tin["pdf"] if thong_tin else None,
                   "sha256": thong_tin["sha256"] if thong_tin else None,
                   "pageStart": None, "pageEnd": None, "confidence": "khong_ro"}
            if thong_tin and thong_tin["textFinal"]:
                vb = cache.setdefault(ma, VanBan(GOC / thong_tin["textFinal"]))
                vt = vb.tim(art["text"])
                if vt:
                    a, b = vb.trang_tai(vt[0]), vb.trang_tai(max(vt[1] - 1, vt[0]))
                    if a is not None:
                        muc.update(pageStart=a, pageEnd=max(a, b or a), confidence=thong_tin["pageMarkers"])
            ra[art["articleId"]] = muc
            dem[muc["confidence"]] = dem.get(muc["confidence"], 0) + 1
    return ra, dem


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", nargs="*", default=None, help="phiên bản JSON (mặc định: mọi thư mục trong data/clean/json)")
    a = ap.parse_args()
    RA.mkdir(parents=True, exist_ok=True)
    man = manifest()
    (RA / "pdf_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    moc: dict[str, int] = {}
    for v in man.values():
        moc[v["pageMarkers"]] = moc.get(v["pageMarkers"], 0) + 1
    print(f"pdf_manifest.json: {len(man)} PDF, chất lượng mốc trang {moc}")
    for pb in a.json or sorted(p.name for p in JSON.iterdir() if p.is_dir()):
        bang, dem = dieu(pb, man)
        (RA / f"dieu_{pb}.json").write_text(json.dumps(bang, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"dieu_{pb}.json: {len(bang)} Điều, độ tin cậy {dem}")


if __name__ == "__main__":
    main()
