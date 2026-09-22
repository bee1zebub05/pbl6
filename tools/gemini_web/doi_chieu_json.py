# -*- coding: utf-8 -*-
"""Cham mot file JSON do Gemini sinh, theo ba tang.

    python tools/gemini_web/doi_chieu_json.py 0227

  Tang 1 HOP LE   — parse duoc khong, qua core/validate.py cua ductran khong.
  Tang 2 DAY DU   — bat duoc may Dieu tren tong so Dieu that trong .txt, than
                    Dieu co chep nguyen van hay bi tom tat, co tach dung phan
                    ban hanh kem theo vao normativeContents khong.
  Tang 3 DUNG     — so tung field voi ban ductran gan tay, neu ma do co mau.

Tang 3 chi chay duoc voi 17 ma da co mau trong legal_knowledge_graph/samples/.
"""
from __future__ import annotations

import io
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]
KHO_TXT = GOC / "data" / "clean" / "text_final"
RA = GOC / "data" / "clean" / "json" / "v1"
MAU = GOC / "src" / "legal_knowledge_graph" / "samples"

DIEU = re.compile(r"^[ \t]*Điều\s+(\d{1,3}[a-zA-Z]?)\s*[.．:]?", re.M)


def _tim(thu_muc: Path, ma: str, duoi: str):
    for p in sorted(thu_muc.rglob("*" + duoi)):
        if p.name.startswith(ma):
            return p
    return None


def _phang(s):
    """Bo dau + gom khoang trang, de so chuoi ma khong vuong dau cau."""
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _dieu_cua(d: dict) -> list[str]:
    ra = [a.get("number", "") for a in (d.get("articles") or [])]
    for n in d.get("normativeContents") or []:
        ra += [a.get("number", "") for a in (n.get("articles") or [])]
    return ra


def _than(d: dict) -> int:
    n = sum(len(a.get("text") or "") for a in (d.get("articles") or []))
    return n + sum(len(a.get("text") or "")
                   for c in (d.get("normativeContents") or [])
                   for a in (c.get("articles") or []))


def main() -> int:
    if len(sys.argv) < 2:
        print("dung: doi_chieu_json.py <ma>  (vd 0227)")
        return 2
    ma = sys.argv[1]

    js = _tim(RA, ma, ".json")
    if not js:
        print("Chua co ket qua cho %s trong %s" % (ma, RA))
        return 1
    txt = _tim(KHO_TXT, ma, ".txt")
    data = json.load(io.open(js, encoding="utf-8"))
    goc = io.open(txt, encoding="utf-8", errors="replace").read() if txt else ""

    print("=" * 74)
    print("%s   %s" % (ma, js.relative_to(GOC)))
    print("   nghi ngo: %s" % ("CO" if "_nghi_ngo" in str(js) else "khong"))
    print("=" * 74)

    # ---------- TANG 1 ----------
    from legal_knowledge_graph.core.validate import load_and_validate
    kq = load_and_validate(js)
    print("\nTANG 1 — HOP LE")
    print("   schema + kiem cheo: %s" % ("DAT" if kq.ok else "TRUOT"))
    for e in kq.errors[:8]:
        print("      - %s" % e[:110])

    # ---------- TANG 2 ----------
    so_goc = sorted(set(DIEU.findall(goc)), key=lambda x: (int(re.match(r"\d+", x).group()), x))
    co = _dieu_cua(data)
    so_json = [re.sub(r"^Điều\s+", "", x) for x in co]
    thieu = [x for x in so_goc if x not in so_json]
    thua = [x for x in so_json if x not in so_goc]
    than = _than(data)
    print("\nTANG 2 — DAY DU")
    print("   Dieu trong txt   : %d  %s" % (len(so_goc), ", ".join(so_goc)[:64]))
    print("   Dieu trong JSON  : %d  %s" % (len(co), ", ".join(co)[:64]))
    if thieu:
        print("   THIEU            : %s" % ", ".join(thieu))
    if thua:
        print("   THUA (khong co trong txt): %s" % ", ".join(thua))
    print("   than Dieu        : %d / %d ky tu cua txt = %.0f%%"
          % (than, len(goc), 100.0 * than / max(len(goc), 1)))
    print("   articles goc     : %d  |  normativeContents: %d"
          % (len(data.get("articles") or []),
             len(data.get("normativeContents") or [])))
    for n in data.get("normativeContents") or []:
        print("      + %r (%s) — %d Dieu"
              % ((n.get("title") or "")[:46], n.get("contentType"),
                 len(n.get("articles") or [])))

    # ---------- TANG 3 ----------
    mau = _tim(MAU, "", ".json")
    mau = None
    for p in sorted(MAU.glob("*.json")):
        j = json.load(io.open(p, encoding="utf-8"))
        if (j.get("sourceFile") or "").split("/")[-1].startswith(ma):
            mau = (p, j)
            break
    print("\nTANG 3 — DUNG (so voi ban ductran gan tay)")
    if not mau:
        print("   ma %s khong nam trong 17 mau, bo qua tang nay." % ma)
        print("=" * 74)
        return 0 if kq.ok else 1

    p, m = mau
    print("   doi chieu voi %s\n" % p.name)
    print("   %-16s %-34s %-34s" % ("field", "GEMINI", "DUCTRAN"))
    print("   " + "-" * 70)
    diem = [0, 0]

    def so(ten, a, b, phang=True):
        eq = (_phang(str(a)) == _phang(str(b))) if phang else (a == b)
        diem[1] += 1
        diem[0] += 1 if eq else 0
        print("   %-16s %-34s %-34s %s"
              % (ten, str(a)[:33], str(b)[:33], "" if eq else "  <<< LECH"))

    dg, dm = data.get("document", {}), m.get("document", {})
    for k in ("documentNumber", "documentType", "issueDate", "status"):
        so(k, dg.get(k), dm.get(k))
    so("organization", data.get("organization", {}).get("name"),
       m.get("organization", {}).get("name"))
    so("topics", sorted(dg.get("topics") or []), sorted(dm.get("topics") or []))

    def ky(d):
        return sorted((s.get("fullName"), s.get("academicTitle"),
                       tuple(s.get("position") or [])) for s in (d.get("signers") or []))
    so("signers", ky(data), ky(m))

    def ct(d):
        return sorted((c.get("targetDocumentNumber"), c.get("relationType"))
                      for c in (d.get("citations") or []))
    cg, cm = ct(data), ct(m)
    chung = set(cg) & set(cm)
    print("   %-16s %d cai%-28s %d cai%-28s  trung %d"
          % ("citations", len(cg), "", len(cm), "", len(chung)))
    for x in sorted(set(cm) - set(cg)):
        print("      ductran co, Gemini THIEU : %s (%s)" % x)
    for x in sorted(set(cg) - set(cm)):
        print("      Gemini co, ductran khong : %s (%s)" % x)

    print("\n   khop %d/%d field don tri" % (diem[0], diem[1]))
    print("=" * 74)
    return 0 if kq.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
