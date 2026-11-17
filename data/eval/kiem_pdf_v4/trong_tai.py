"""Áp các quyết định của trọng tài vào JSON v4, ghi note, validate, ghi nhật ký.

    python data/eval/kiem_pdf_v4/trong_tai.py <tệp quyết định .json>

Tệp quyết định là danh sách các mục:
    {"ma": "0472", "op": "set", "path": "signers.0.position", "moi": ["Phó Giám đốc"],
     "trang": "1", "phat_hien": "agent nhóm 1", "ket_luan": "DONG_Y", "ly_do": "..."}

op:
    set          gán giá trị `moi` vào `path` (khoá ngăn bằng dấu chấm, số là chỉ mục mảng)
    set_cite     sửa trích dẫn có targetDocumentNumber == `dich` (và relationType == `loai` nếu có):
                 `moi` là dict các trường mới (relationType, context, targetArticle)
    add_cite     thêm trích dẫn `moi` (dict đủ 4 trường); bỏ qua nếu đã có cùng đích + loại
    del_cite     bỏ trích dẫn có targetDocumentNumber == `dich` (`moi` để null)
    del_article  bỏ phần tử articles có number == `moi`

Mỗi mục: nối một câu vào note, validate cả tệp (hỏng thì hoàn tác tệp đó), ghi một dòng vào
nhat_ky_sua.csv. Tệp đã sửa xong được chép sang chuan/<mã>.json.
"""
from __future__ import annotations

import copy
import csv
import json
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent
REPO = GOC.parents[2]
sys.path.insert(0, str(REPO / "src"))
from legal_knowledge_graph.core.ingest.validate import load_and_validate  # noqa: E402

V4 = REPO / "data" / "clean" / "json" / "v4"
NHAT_KY = GOC / "nhat_ky_sua.csv"
COT = ["ma", "op", "truong", "cu", "moi", "trang_pdf", "phat_hien", "ket_luan", "ly_do"]


def tim(ma):
    ds = list(V4.rglob(f"{ma}_*.json"))
    assert len(ds) == 1, (ma, ds)
    return ds[0]


def lay(d, path):
    for k in path.split("."):
        d = d[int(k)] if k.isdigit() else d[k]
    return d


def gan(d, path, v):
    ks = path.split(".")
    for k in ks[:-1]:
        d = d[int(k)] if k.isdigit() else d[k]
    k = ks[-1]
    if k.isdigit():
        d[int(k)] = v
    else:
        d[k] = v


def ghi(p, d):
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def ap(d, m):
    op = m["op"]
    if op == "set":
        cu = lay(d, m["path"])
        gan(d, m["path"], m["moi"])
        return m["path"], cu
    if op == "set_cite":
        hit = [c for c in d["citations"] if c["targetDocumentNumber"] == m["dich"]
               and (not m.get("loai") or c["relationType"] == m["loai"])]
        assert len(hit) == 1, ("set_cite", m["ma"], m["dich"], len(hit))
        cu = {k: hit[0].get(k) for k in m["moi"]}
        hit[0].update(m["moi"])
        return f"citations[{m['dich']}]", cu
    if op == "add_cite":
        c = m["moi"]
        if any(x["targetDocumentNumber"] == c["targetDocumentNumber"] and x["relationType"] == c["relationType"]
               for x in d["citations"]):
            return None, None
        d["citations"].append(c)
        return f"citations[+{c['targetDocumentNumber']}]", None
    if op == "del_cite":
        khop = lambda c: c["targetDocumentNumber"] == m["dich"] and (not m.get("loai") or c["relationType"] == m["loai"])
        cu = [c for c in d["citations"] if khop(c)]
        assert len(cu) == 1, ("del_cite", m["ma"], m["dich"], len(cu))
        d["citations"] = [c for c in d["citations"] if not khop(c)]
        return f"citations[-{m['dich']}]", cu[0]
    if op == "del_article":
        cu = [a for a in d["articles"] if a["number"] == m["moi"]]
        assert len(cu) == 1, ("del_article", m["ma"], m["moi"])
        d["articles"] = [a for a in d["articles"] if a["number"] != m["moi"]]
        return f"articles[{m['moi']}]", cu[0]["text"][:80]
    raise ValueError(op)


def cau_note(truong, cu, moi, trang):
    rut = lambda v: json.dumps(v, ensure_ascii=False)[:120] if not isinstance(v, str) else v[:120]
    if cu is None:
        return f"Thêm {truong} theo PDF gốc trang {trang}."
    if moi is None:
        return f"Bỏ {truong} {rut(cu)}: {trang}."
    return f"{truong} sửa từ {rut(cu)} thành {rut(moi)} theo PDF gốc trang {trang}."


def main(tep):
    ds = json.load(open(tep, encoding="utf-8"))
    moi_file = not NHAT_KY.exists()
    f = open(NHAT_KY, "a", encoding="utf-8-sig" if moi_file else "utf-8", newline="")
    w = csv.DictWriter(f, fieldnames=COT)
    if moi_file:
        w.writeheader()
    theo_ma = {}
    for m in ds:
        theo_ma.setdefault(m["ma"], []).append(m)
    for ma, mucs in theo_ma.items():
        p = tim(ma)
        goc_txt = p.read_text(encoding="utf-8")
        d = json.loads(goc_txt)
        dong = []
        for m in mucs:
            truong, cu = ap(d, m)
            if truong is None:
                print(f"  = {ma} {m['op']} đã có, bỏ qua"); continue
            note = (d.get("note") or "").rstrip()
            cau = cau_note(truong, cu, m["moi"], m["trang"])
            d["note"] = f"{note}{'' if not note or note.endswith('.') else '.'} {cau}".strip()
            dong.append({"ma": ma, "op": m["op"], "truong": truong,
                         "cu": json.dumps(cu, ensure_ascii=False) if cu is not None else "",
                         "moi": json.dumps(m["moi"], ensure_ascii=False), "trang_pdf": m["trang"],
                         "phat_hien": m.get("phat_hien", ""), "ket_luan": m.get("ket_luan", ""), "ly_do": m.get("ly_do", "")})
        ghi(p, d)
        r = load_and_validate(p)
        if not r.ok:
            p.write_text(goc_txt, encoding="utf-8", newline="\n")
            print(f"  ✖ {ma} validate hỏng, đã hoàn tác: {r.errors}")
            continue
        for x in dong:
            w.writerow(x)
        (GOC / "chuan").mkdir(exist_ok=True)
        (GOC / "chuan" / f"{ma}.json").write_text(p.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        print(f"  ✔ {ma}: {len(dong)} chỗ sửa")
    f.close()


if __name__ == "__main__":
    main(sys.argv[1])
