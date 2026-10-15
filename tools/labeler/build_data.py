"""Dựng thư mục data/ cho trang gán nhãn từ data/clean/sinh_vien_103/.

Chạy từ gốc repo:  python tools/labeler/build_data.py
Kết quả: tools/labeler/data/index.json và data/t/<id>.txt, <id>.draft.json (không commit, xem .gitignore).
Người phụ trách lấy từ cột `nguoi_gan` của danh_sach.csv.
"""
import csv
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "data", "clean", "sinh_vien_103")
TEXT_FINAL = os.path.join(ROOT, "data", "clean", "text_final")
REF = os.path.join(ROOT, "src", "legal_knowledge_graph", "reference")
OUT = os.path.join(os.path.dirname(__file__), "data")


def strip_articles(arts):
    return [{"number": a.get("number"), "heading": a.get("heading"), "text": a.get("text"),
             "isImplementationClause": a.get("isImplementationClause", False)} for a in arts or []]


def main():
    os.makedirs(os.path.join(OUT, "t"), exist_ok=True)
    rows = list(csv.DictReader(open(os.path.join(SRC, "danh_sach.csv"), encoding="utf-8-sig")))
    docs = []
    for r in rows:
        txt = os.path.join(ROOT, r["file_text"])
        did = os.path.basename(txt)[:4]
        text = open(txt, encoding="utf-8").read().replace("\r\n", "\n")
        with open(os.path.join(OUT, "t", did + ".txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        j = json.load(open(os.path.join(ROOT, r["file_json_v2"]), encoding="utf-8"))
        draft = {
            "document": j.get("document"), "organization": j.get("organization"),
            "signers": j.get("signers", []), "citations": j.get("citations", []), "mentions": j.get("mentions", []),
            "normativeContents": [{"title": n.get("title"), "contentType": n.get("contentType"),
                                   "articles": strip_articles(n.get("articles"))} for n in j.get("normativeContents", [])],
            "articles": strip_articles(j.get("articles")),
        }
        json.dump(draft, open(os.path.join(OUT, "t", did + ".draft.json"), "w", encoding="utf-8"), ensure_ascii=False)
        docs.append({
            "id": did, "soHieu": r["so_hieu"], "title": r["ten_van_ban"], "muc": r["muc"], "linhVuc": r["linh_vuc"],
            "loai": r["loai"], "ngay": r["ngay_ban_hanh"], "hieuLuc": r["hieu_luc"], "doiTuong": r["doi_tuong"],
            "dieuLienQuan": r["dieu_lien_quan"], "cauHoi": r["cau_hoi_vi_du"], "nghiNgo": bool(r["json_nghi_ngo"]),
            "sourceFile": os.path.relpath(txt, TEXT_FINAL).replace(os.sep, "/"), "chars": len(text),
            "phuTrach": r["nguoi_gan"],
        })
    seed = {
        "topics": [x["name"] for x in json.load(open(os.path.join(REF, "topics_seed.json"), encoding="utf-8"))["topics"]],
        "targetGroups": [x["name"] for x in json.load(open(os.path.join(REF, "target_groups_seed.json"), encoding="utf-8"))["target_groups"]],
        "organizations": [{"name": x["name"], "orgType": x["orgType"]} for x in
                          json.load(open(os.path.join(REF, "organizations_seed.json"), encoding="utf-8"))["organizations"]],
    }
    json.dump({"docs": docs, "seed": seed}, open(os.path.join(OUT, "index.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(docs)} văn bản -> {OUT}")


if __name__ == "__main__":
    main()
