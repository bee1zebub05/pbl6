# -*- coding: utf-8 -*-
"""Sinh script Cypher dung do thi trong Neo4j — bam theo Ontology v0.3 (Muc 3).

    Node   Document, Organization, Person, Topic, TargetGroup, NormativeContent, Article
    Edge   ISSUED_BY, SIGNED_BY, HAS_TOPIC, APPLIES_TO, PART_OF,
           BASED_ON, REFERENCES, REPLACES/REPLACED_BY, AMENDS/AMENDED_BY,
           REPEALS/REPEALED_BY, PROMULGATES, HAS_ARTICLE

BAY DIEU DA DOI SO VOI BAN TRUOC, deu la de khop Ontology chu khong phai doi cho vui:

  1. THAY_THE tach thanh REPLACES / AMENDS / REPEALS + ba chieu nguoc (§4).
     Truoc day gop chung: mot van ban "sua doi, bo sung" bi doc thanh "thay the", suy ra
     van ban goc het hieu luc — nguoc han su that. Xem quan_he_hieu_luc.py.

  2. CanCuPhapLy khong con la mot LABEL RIENG. Ontology §1 noi ro: van ban bi vien dan
     ma chua crawl thi tao Document **stub**, CUNG CLASS, de sau lam giau len. Label
     rieng khien moi truy van phai viet hai nhanh MATCH, va mot ngay nao do crawl duoc
     van ban do thi phai doi label — hong het quan he cu.

  3. LoaiVanBan khong con la node. §9: "loai" la PROPERTY (`documentType`), khong phai
     thuc the. Node loai chi tao ra 16 sieu-nut noi vao tat ca moi thu, lam mo do thi.

  4. DonViBanHanh + DonViLienQuan gop thanh MOT `Organization` co `orgType` (§2.2).
     Hai label rieng cho cung mot thuc the la sai: "Phong Dao tao" vua ban hanh van ban
     vua duoc nhac den trong van ban khac -> truoc day thanh HAI nut khac nhau.

  5. Them PART_OF: Khoa/Phong -> Truong DHBK -> DHDN -> Bo GD&DT. Nho canh nay moi hoi
     duoc "tat ca van ban lien quan den bat ky don vi nao thuoc Truong".

  6. `authority_level` doi tu thang 1-5 (1 = cao nhat) sang thang 1-6 (6 = cao nhat) dung
     §3, va them bac Hien phap. Nho vay ORDER BY authority_level DESC ra dung van ban goc
     tham quyen cao nhat — truoc day phai nho la thang bi lat nguoc.

  7. Them NormativeContent + Article (§2.6, §2.7) -> retrieval cap dieu khoan.

Chay:
    F:\\DUT4\\PBL6\\project\\viz_env\\Scripts\\python.exe xuat_neo4j.py --ra do_thi_dut.cql
"""
import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from do_thi_lib import CAP_TEN, nap                      # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ontology §3: thang tham quyen 1-6, SO CANG LON CANG CAO. `cap` trong do_thi_lib chay
# nguoc (1 = Quoc hoi), nen doi bang 6 - cap. Hien phap duoc mot bac rieng tren cung.
def muc_tham_quyen(cap, loai, so_hieu):
    if re.search(r"hiến\s*pháp", "%s %s" % (loai or "", so_hieu or ""), re.I):
        return 6
    return 6 - cap if 1 <= cap <= 5 else 0


# Ontology §2.2 orgType. Suy tu tien to ten don vi + cap ban hanh.
def loai_don_vi(ten, cap=0):
    t = (ten or "").lower()
    if t.startswith(("phòng", "tổ ")):
        return "phong_ban"
    if t.startswith(("khoa", "trung tâm", "viện", "thư viện")):
        return "don_vi_truc_thuoc"
    if t.startswith("ban") or t.startswith(("đoàn", "công đoàn", "hội ", "đảng")):
        return "don_vi_truc_thuoc"
    if "quốc hội" in t:
        return "quoc_hoi"
    if "thủ tướng" in t:
        return "thu_tuong"
    if "chính phủ" in t:
        return "chinh_phu"
    if t.startswith("bộ") or "ngân hàng nhà nước" in t:
        return "bo_nganh"
    if "đại học đà nẵng" in t and "trường" not in t:
        return "dai_hoc_vung"
    if t.startswith("trường"):
        return "truong_thanh_vien"
    return {1: "quoc_hoi", 2: "chinh_phu", 3: "bo_nganh",
            4: "dai_hoc_vung", 5: "truong_thanh_vien"}.get(cap, "khac")


TRUONG = "Trường Đại học Bách khoa"
DHDN = "Đại học Đà Nẵng"
BO_GD = "Bộ Giáo dục và Đào tạo"

# Ban ... la don vi cap DHDN (Ban Dao tao, Ban To chuc Can bo...), con Phong ... la cap
# Truong. Day la su that ve to chuc cua DHDN, khong phai quy uoc tu dat.
def don_vi_cha(ten, kieu):
    t = (ten or "").lower()
    if kieu in ("phong_ban", "don_vi_truc_thuoc"):
        return DHDN if t.startswith("ban ") else TRUONG
    if kieu == "truong_thanh_vien":
        return DHDN
    if kieu == "dai_hoc_vung":
        return BO_GD
    return None


def q(s):
    """Boc chuoi cho Cypher. Tieu de van ban co ca dau nhay va dau gach cheo nguoc."""
    return "'" + str(s or "").replace("\\", "\\\\").replace("'", "\\'") + "'"


def qds(ds):
    return "[" + ", ".join(q(x) for x in ds) + "]"


def gom_trung(G):
    """Gom van ban theo SO HIEU. -> {so_hieu: {thuoc tinh da hop nhat}}

    Cung mot so hieu co the ung voi nhieu doc_id (ban scan lai, ban dat ten khac). Gop
    truoc khi sinh Cypher, khong de MERGE tuan tu ghi de len nhau.
    """
    nhom = defaultdict(list)
    for n, x in G.nodes(data=True):
        if x["ngoai_bo"]:
            continue
        nhom[x["so_hieu"] or n].append((n, x))

    ra = {}
    for so, ds in nhom.items():
        # lay ban DAY DU NHAT lam goc: nhieu trang nhat, roi den co ngay/nguoi ky
        ds.sort(key=lambda p: (p[1]["so_trang"], bool(p[1]["ngay"]),
                               bool(p[1]["nguoi_ky"])), reverse=True)
        _n0, g = ds[0]
        # Dieu/NormativeContent: lay tu ban NHIEU DIEU NHAT, vi ban OCR kem se thieu dieu
        tot = max(ds, key=lambda p: len(p[1].get("dieu") or []))[1]
        ra[so] = {
            "so_hieu": so,
            "doc_ids": sorted(n for n, _x in ds),
            "duong_dan": sorted(x["duong_dan"] for _n, x in ds if x["duong_dan"]),
            "tieu_de": g["tieu_de"],
            "loai": g["loai"],
            "co_quan": g["co_quan"],
            "linh_vuc": g["linh_vuc"],
            "ngay": next((x["ngay"] for _n, x in ds if x["ngay"]), ""),
            "nguoi_ky": next((x["nguoi_ky"] for _n, x in ds if x["nguoi_ky"]), ""),
            "hoc_ham": next((x.get("hoc_ham") for _n, x in ds if x.get("hoc_ham")), ""),
            "chuc_danh": next((x.get("chuc_danh") for _n, x in ds
                               if x.get("chuc_danh")), ""),
            "so_trang": g["so_trang"],
            "cap": g["cap"],
            "muc": muc_tham_quyen(g["cap"], g["loai"], so),
            "doi_tuong": sorted({d for _n, x in ds for d in (x["doi_tuong"] or [])}),
            "don_vi": sorted({d for _n, x in ds for d in (x.get("don_vi") or [])}),
            "dieu": tot.get("dieu") or [],
            "noi_dung": tot.get("noi_dung"),
            "so_ban": len(ds),
        }
    return ra


def sinh_cypher(G):
    hop = gom_trung(G)
    ve = {}
    for so, v in hop.items():
        for d in v["doc_ids"]:
            ve[d] = so

    r = ["// Đồ thị tri thức văn bản pháp quy — Trường ĐH Bách khoa, ĐHĐN",
         "// Sinh tự động từ data/processed/text_clean_gemma — lược đồ Ontology v0.3",
         "//",
         "// %d văn bản gốc -> %d nút Document (đã gộp %d bản trùng số hiệu)"
         % (sum(v["so_ban"] for v in hop.values()), len(hop),
            sum(v["so_ban"] - 1 for v in hop.values())),
         "",
         "// ── Xoá đồ thị cũ (bỏ dòng này nếu muốn ghi thêm) ──",
         "MATCH (n) DETACH DELETE n;",
         "",
         "// ── Ràng buộc: mỗi khoá chỉ một nút ──",
         "// Document dùng chung cho cả văn bản đã crawl lẫn stub (Ontology §1), nên chỉ",
         "// một ràng buộc UNIQUE duy nhất trên so_hieu — không tách label riêng.",
         "CREATE CONSTRAINT doc_so IF NOT EXISTS "
         "FOR (v:Document) REQUIRE v.so_hieu IS UNIQUE;",
         "CREATE CONSTRAINT org_ten IF NOT EXISTS "
         "FOR (o:Organization) REQUIRE o.name IS UNIQUE;",
         "CREATE CONSTRAINT per_ten IF NOT EXISTS "
         "FOR (p:Person) REQUIRE p.fullName IS UNIQUE;",
         "CREATE CONSTRAINT top_ten IF NOT EXISTS "
         "FOR (t:Topic) REQUIRE t.name IS UNIQUE;",
         "CREATE CONSTRAINT tg_ten IF NOT EXISTS "
         "FOR (g:TargetGroup) REQUIRE g.name IS UNIQUE;",
         "CREATE CONSTRAINT nc_id IF NOT EXISTS "
         "FOR (c:NormativeContent) REQUIRE c.contentId IS UNIQUE;",
         "CREATE CONSTRAINT art_id IF NOT EXISTS "
         "FOR (a:Article) REQUIRE a.articleId IS UNIQUE;",
         "",
         "// ── Chỉ mục cho các trường hay dùng để LỌC ──",
         "// Ràng buộc UNIQUE đã tự sinh chỉ mục cho khoá; các trường dưới thì chưa có,",
         "// mà lọc theo khoảng thời gian / theo thẩm quyền là truy vấn rất hay dùng.",
         "CREATE INDEX doc_ngay IF NOT EXISTS FOR (v:Document) ON (v.issueDate);",
         "CREATE INDEX doc_muc IF NOT EXISTS "
         "FOR (v:Document) ON (v.authority_level);",
         "CREATE INDEX doc_loai IF NOT EXISTS FOR (v:Document) ON (v.documentType);",
         "CREATE INDEX doc_stub IF NOT EXISTS FOR (v:Document) ON (v.is_stub);",
         "CREATE INDEX art_so IF NOT EXISTS FOR (a:Article) ON (a.number);",
         ""]

    # ── Organization: gộp đơn vị ban hành và đơn vị được nhắc đến làm một ──
    org = {}
    for v in hop.values():
        if v["co_quan"]:
            org.setdefault(v["co_quan"], v["cap"])
        for u in v["don_vi"]:
            org.setdefault(u, 0)
    for x in (TRUONG, DHDN, BO_GD):
        org.setdefault(x, 0)

    tp, tg, ng = set(), set(), {}
    for v in hop.values():
        if v["linh_vuc"]:
            tp.add(v["linh_vuc"])
        for o in v["doi_tuong"]:
            tg.add(o)
        if v["nguoi_ky"]:
            # Ontology §2.3: mot nguoi giu nhieu chuc danh qua thoi gian (Pho hieu truong
            # roi Hieu truong). Gom moi chuc danh/hoc ham gap duoc thay vi ghi de.
            ng.setdefault(v["nguoi_ky"], (set(), set()))
            if v["chuc_danh"]:
                ng[v["nguoi_ky"]][0].add(v["chuc_danh"])
            if v["hoc_ham"]:
                ng[v["nguoi_ky"]][1].add(v["hoc_ham"])

    r.append("// ── Organization (§2.2) — gộp đơn vị ban hành + đơn vị liên quan ──")
    for ten in sorted(org):
        cap = org[ten]
        kieu = loai_don_vi(ten, cap)
        r.append("MERGE (o:Organization {name: %s}) SET o.orgType = %s, o.cap = %d, "
                 "o.ten_cap = %s;"
                 % (q(ten), q(kieu), cap, q(CAP_TEN.get(cap, ""))))
    r.append("")
    r.append("// ── PART_OF: cây tổ chức ──")
    for ten in sorted(org):
        cha = don_vi_cha(ten, loai_don_vi(ten, org[ten]))
        if cha and cha != ten and cha in org:
            r.append("MATCH (a:Organization {name: %s}), (b:Organization {name: %s}) "
                     "MERGE (a)-[:PART_OF]->(b);" % (q(ten), q(cha)))
    r.append("")

    r.append("// ── Topic / TargetGroup / Person ──")
    for x in sorted(tp):
        r.append("MERGE (:Topic {name: %s});" % q(x))
    for x in sorted(tg):
        r.append("MERGE (:TargetGroup {name: %s});" % q(x))
    for x in sorted(ng):
        cd, hh = ng[x]
        r.append("MERGE (p:Person {fullName: %s}) SET p.position = %s, "
                 "p.academicTitle = %s;"
                 % (q(x), qds(sorted(cd)), q(" ".join(sorted(hh)))))
    r.append("")

    r.append("// ── Document: văn bản trong bộ dữ liệu ──")
    for so in sorted(hop):
        v = hop[so]
        r.append(
            "MERGE (v:Document {so_hieu: %s}) SET v.is_stub = false, "
            "v.doc_id_chinh = %s, v.doc_ids = %s, v.title = %s, v.issueDate = %s, "
            "v.documentType = %s, v.authority_level = %d, v.cap = %d, "
            "v.so_trang = %d, v.so_ban_trung = %d, v.so_dieu = %d, v.fileUrl = %s;"
            % (q(so), q(v["doc_ids"][0]), qds(v["doc_ids"]), q(v["tieu_de"]),
               q(v["ngay"]), q(v["loai"]), v["muc"], v["cap"], v["so_trang"],
               v["so_ban"], len(v["dieu"]), qds(v["duong_dan"])))
    r.append("")

    r.append("// ── Document stub: bị viện dẫn nhưng chưa crawl (Ontology §1) ──")
    r.append("// Cùng label Document — hôm nào crawl được thì chỉ việc SET thêm thuộc")
    r.append("// tính và is_stub = false, mọi quan hệ đã nối vẫn còn nguyên.")
    for n, x in G.nodes(data=True):
        if not x["ngoai_bo"]:
            continue
        r.append("MERGE (c:Document {so_hieu: %s}) "
                 "SET c.is_stub = coalesce(c.is_stub, true), c.title = %s, "
                 "c.documentType = %s, c.authority_level = %d, c.cap = %d, "
                 "c.so_lan_vien_dan = %d;"
                 % (q(x["so_hieu"]), q(x["tieu_de"]), q(x.get("loai", "")),
                    muc_tham_quyen(x["cap"], x.get("loai", ""), x["so_hieu"]),
                    x["cap"], x.get("so_lan_vien_dan", 0)))
    r.append("")

    r.append("// ── ISSUED_BY / HAS_TOPIC / SIGNED_BY / APPLIES_TO ──")
    for so in sorted(hop):
        v = hop[so]
        s = q(so)
        if v["co_quan"]:
            r.append("MATCH (v:Document {so_hieu: %s}), (o:Organization {name: %s}) "
                     "MERGE (v)-[:ISSUED_BY]->(o);" % (s, q(v["co_quan"])))
        if v["linh_vuc"]:
            r.append("MATCH (v:Document {so_hieu: %s}), (t:Topic {name: %s}) "
                     "MERGE (v)-[:HAS_TOPIC]->(t);" % (s, q(v["linh_vuc"])))
        if v["nguoi_ky"]:
            r.append("MATCH (v:Document {so_hieu: %s}), (p:Person {fullName: %s}) "
                     "MERGE (v)-[:SIGNED_BY]->(p);" % (s, q(v["nguoi_ky"])))
        for o in v["doi_tuong"]:
            r.append("MATCH (v:Document {so_hieu: %s}), (g:TargetGroup {name: %s}) "
                     "MERGE (v)-[:APPLIES_TO]->(g);" % (s, q(o)))
        for u in v["don_vi"]:
            r.append("MATCH (v:Document {so_hieu: %s}), (o:Organization {name: %s}) "
                     "MERGE (v)-[:MENTIONS]->(o);" % (s, q(u)))
    r.append("")

    # ── NormativeContent + Article ──
    r.append("// ── NormativeContent (§2.6) + Article (§2.7) ──")
    r.append("// Khối Điều thứ hai trong một Quyết định chính là bản Quy định/Quy chế")
    r.append("// ban hành kèm theo — nó mới là thứ người ta muốn tra, không phải mấy")
    r.append("// Điều thi hành của cái quyết định bọc ngoài.")
    n_nc = n_art = 0
    for so in sorted(hop):
        v = hop[so]
        if not v["dieu"]:
            continue
        nd = v["noi_dung"]
        cid = "%s#ND" % so
        if nd:
            n_nc += 1
            r.append("MERGE (c:NormativeContent {contentId: %s}) SET c.contentType = %s, "
                     "c.title = %s, c.so_dieu = %d;"
                     % (q(cid), q(nd["loai"]), q(v["tieu_de"]), nd["so_dieu"]))
            r.append("MATCH (v:Document {so_hieu: %s}), "
                     "(c:NormativeContent {contentId: %s}) "
                     "MERGE (v)-[:PROMULGATES]->(c);" % (q(so), q(cid)))
        for i, d in enumerate(v["dieu"]):
            aid = "%s#%d" % (so, i + 1)
            n_art += 1
            r.append("MERGE (a:Article {articleId: %s}) SET a.number = %s, "
                     "a.heading = %s, a.so_khoan = %d, a.thu_tu = %d;"
                     % (q(aid), q(d["so"]), q(d["tieu_de"]), d["so_khoan"], i + 1))
            # Dieu thuoc khoi >=1 la cua ban Quy dinh kem theo, khong phai cua Quyet dinh
            if nd and d["khoi"] >= 1:
                r.append("MATCH (c:NormativeContent {contentId: %s}), "
                         "(a:Article {articleId: %s}) MERGE (c)-[:HAS_ARTICLE]->(a);"
                         % (q(cid), q(aid)))
            else:
                r.append("MATCH (v:Document {so_hieu: %s}), (a:Article {articleId: %s}) "
                         "MERGE (v)-[:HAS_ARTICLE]->(a);" % (q(so), q(aid)))
    r.append("")

    r.append("// ── Quan hệ giữa các văn bản (§4) ──")
    r.append("// BASED_ON = 'Căn cứ ...' đầu văn bản | REFERENCES = viện dẫn trong thân")
    r.append("// REPLACES / AMENDS / REPEALS + ba chiều ngược = quan hệ hiệu lực")
    da = set()
    for a, b, qh in G.edges(data="quan_he"):
        xa, xb = G.nodes[a], G.nodes[b]
        if xa["ngoai_bo"]:
            continue
        sa = ve.get(a, xa["so_hieu"] or a)
        sb = xb["so_hieu"] if xb["ngoai_bo"] else ve.get(b, xb["so_hieu"] or b)
        if sa == sb:                 # gop ban trung xong co the thanh tu tro chinh minh
            continue
        khoa = (sa, sb, qh)
        if khoa in da:
            continue
        da.add(khoa)
        r.append("MATCH (a:Document {so_hieu: %s}), (b:Document {so_hieu: %s}) "
                 "MERGE (a)-[:%s]->(b);" % (q(sa), q(sb), qh))
    r.append("")

    r.append("""// ── Vài truy vấn mẫu ──
// 1. Chuỗi thẩm quyền: văn bản gốc cao nhất mà một quyết định dựa vào (§3)
// MATCH (d:Document {so_hieu: '1425/QĐ-ĐHBK'})-[:BASED_ON*1..3]->(b:Document)
// RETURN b.so_hieu, b.title, b.authority_level
// ORDER BY b.authority_level DESC LIMIT 10;
//
// 2. Văn bản còn hiệu lực hay không — phân biệt sửa đổi với thay thế
// MATCH (d:Document {so_hieu: '6950/QĐ-ĐHBK'})
// OPTIONAL MATCH (d)<-[:REPLACES|REPEALS]-(x)   // hết hiệu lực
// OPTIONAL MATCH (d)<-[:AMENDS]-(y)             // vẫn hiệu lực, chỉ đổi vài điều
// RETURN d.so_hieu, collect(DISTINCT x.so_hieu) AS het,
//        collect(DISTINCT y.so_hieu) AS sua_doi;
//
// 3. Retrieval cấp điều khoản (§2.7)
// MATCH (v:Document)-[:PROMULGATES]->(c:NormativeContent)-[:HAS_ARTICLE]->(a:Article)
// WHERE toLower(a.heading) CONTAINS 'học bổng'
// RETURN v.so_hieu, c.contentType, a.number, a.heading LIMIT 25;
//
// 4. Mọi văn bản liên quan tới bất kỳ đơn vị nào thuộc Trường (nhờ PART_OF)
// MATCH (o:Organization)-[:PART_OF*0..2]->(:Organization {name: 'Trường Đại học Bách khoa'})
// MATCH (v:Document)-[:ISSUED_BY|MENTIONS]->(o)
// RETURN o.name, count(DISTINCT v) AS n ORDER BY n DESC;
//
// 5. Những văn bản cùng dựa trên một căn cứ — căn cứ đó sửa là cả chùm phải rà lại
// MATCH (v:Document)-[:BASED_ON]->(c:Document)
// WITH c, collect(v.so_hieu) AS ds, count(*) AS n
// WHERE n >= 5 RETURN c.so_hieu, c.is_stub, n, ds ORDER BY n DESC;
//
// 6. Stub nào bị viện dẫn nhiều nhất — thứ tự ưu tiên đi crawl bổ sung
// MATCH (c:Document {is_stub: true})<-[r]-()
// RETURN c.so_hieu, c.title, count(r) AS n ORDER BY n DESC LIMIT 20;
//
// 7. Ai ký nhiều văn bản nhất, và ở lĩnh vực nào
// MATCH (v:Document)-[:SIGNED_BY]->(p:Person)
// MATCH (v)-[:HAS_TOPIC]->(t:Topic)
// RETURN p.fullName, count(v) AS n, collect(DISTINCT t.name) AS linh_vuc
// ORDER BY n DESC LIMIT 15;
//
// 8. Kiểm tra sau khi nạp: số nút và cạnh từng loại
// MATCH (n) RETURN labels(n)[0] AS nhan, count(*) AS so ORDER BY so DESC;
// MATCH ()-[r]->() RETURN type(r) AS quan_he, count(*) AS so ORDER BY so DESC;""")
    return "\n".join(r) + "\n", n_nc, n_art


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ra", default="do_thi_dut.cql")
    ap.add_argument("--nguong-ngoai", type=int, default=3)
    a = ap.parse_args()
    G, _tk = nap(a.nguong_ngoai)
    s, n_nc, n_art = sinh_cypher(G)
    p = Path(a.ra)
    p.write_text(s, encoding="utf-8", newline="\n")
    hop = gom_trung(G)
    print("Đã ghi %s" % p)
    print("  %s dòng Cypher" % "{:,}".format(s.count("\n")))
    print("  %d nút Document thật (gộp từ %d bản) + %d Document stub"
          % (len(hop), sum(v["so_ban"] for v in hop.values()),
             sum(1 for _n, x in G.nodes(data=True) if x["ngoai_bo"])))
    print("  %d NormativeContent | %s Article | %d Person"
          % (n_nc, "{:,}".format(n_art),
             len({v["nguoi_ky"] for v in hop.values() if v["nguoi_ky"]})))
    print("Nạp vào Neo4j:")
    print('   cypher-shell -u neo4j -p 12345678 -f "%s"' % p.resolve())


if __name__ == "__main__":
    main()
