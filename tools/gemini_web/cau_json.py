# -*- coding: utf-8 -*-
"""Cau hang cho: dua tung file .txt da sach len Gemini web, nhan ve MOT file JSON
dung `legal_knowledge_graph/schema/document.schema.json`.

Dung chung toan bo may hang cho / checkpoint / extension Chrome voi cau_sua_txt.py.
Chi khac ba cho:

  1. Cau lenh (PROMPT)  -> bao Gemini tra ve JSON thay vi plaintext.
  2. Nguon viec         -> quet thang `data/clean/text_final`, khong doc CSV.
  3. Cong nhan ket qua  -> parse JSON roi cho qua `core/validate.py` cua
                           legal_knowledge_graph. Sai schema la KHONG nhan, tra
                           loi cu the ve extension de no thu lai.

    python tools/gemini_web/cau_json.py --chi 0322      # test mot file
    python tools/gemini_web/cau_json.py                 # chay het

Ra: data/kg_json/<linh vuc>/<ma>.json — ban nao qua duoc schema nhung con cho
dang ngo thi vao data/kg_json/_nghi_ngo/.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tempfile
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cau_sua_txt import Handler, Kho, chan_cau_trung, noi   # noqa: E402

GOC = Path(__file__).resolve().parents[2]
KHO_TXT = GOC / "data" / "clean" / "text_final"
RA_MAC_DINH = GOC / "data" / "kg_json"
TRANG_THAI = Path(__file__).resolve().parent / "trang_thai_json.json"

# ============================================================
# CAU LENH
# ============================================================
# Moi enum deu phai liet ke DU trong prompt. Thieu mot gia tri la Gemini tu bia
# ra nhan khac ("Cong van hanh chinh", "con_hieu_luc"...) va validate danh truot
# ca file. Cac danh sach duoi day chep tu chinh schema + reference seed.

_LOAI_VB = ("Luật | Pháp lệnh | Nghị định | Thông tư | Thông tư liên tịch | "
            "Quyết định | Nghị quyết | Chỉ thị | Hướng dẫn | Kế hoạch | "
            "Văn bản hợp nhất | Lệnh | Công văn | Hiến pháp")
_LINH_VUC = ("Công nghệ thông tin, CĐS | Công tác sinh viên | Cơ sở vật chất, xây dựng | "
             "Học liệu, truyền thông | Hợp tác quốc tế | Khoa học Công nghệ | Khảo thí | "
             "Khác | Pháp chế | Sở hữu trí tuệ | Thanh tra, kiểm tra | Thi đua, khen thưởng | "
             "Tuyển sinh | Tài chính, kế toán | Tổ chức, hành chính | Văn thư, lưu trữ | "
             "Đào tạo | Đảm bảo chất lượng, KĐCL")
_LOAI_ND = ("Quy định | Quy chế | Điều lệ | Quy trình | Nội quy | Đề án | Kế hoạch | "
            "Hướng dẫn | Chương trình")

PROMPT = (
    "Đây là toàn văn một văn bản pháp quy Việt Nam, đã OCR từ bản scan và đã được sửa "
    "lỗi chính tả. Hãy đọc và chuyển thành MỘT object JSON theo đúng cấu trúc dưới đây.\n\n"

    "TRẢ VỀ DUY NHẤT một khối mã ```json chứa object đó. Không viết lời dẫn, không giải "
    "thích, không thêm khối mã thứ hai.\n\n"

    "CẤU TRÚC (khoá nào không có trong danh sách này thì TUYỆT ĐỐI không được thêm):\n"
    "{\n"
    '  "schemaVersion": "1.0",\n'
    '  "sourceFile": null,\n'
    '  "mappedBy": "gemini-web",\n'
    '  "note": "ghi chỗ bạn không chắc, hoặc null",\n'
    '  "document": {\n'
    '    "documentNumber": "số hiệu chép nguyên văn, vd 2852/QĐ-ĐHĐN",\n'
    '    "title": "tiêu đề đầy đủ",\n'
    '    "documentType": "một trong: ' + _LOAI_VB + '",\n'
    '    "status": "CON_HIEU_LUC | HET_HIEU_LUC | CHUA_HIEU_LUC | null",\n'
    '    "issueDate": "dd/mm/yyyy hoặc null",\n'
    '    "effectiveDate": "dd/mm/yyyy hoặc null",\n'
    '    "expiryDate": "dd/mm/yyyy hoặc null",\n'
    '    "fileUrl": null,\n'
    '    "topics": ["chọn trong: ' + _LINH_VUC + '"],\n'
    '    "summary": "1-3 câu, tối đa 600 ký tự, chỉ tóm ý CÓ SẴN trong văn bản",\n'
    '    "idOverride": null\n'
    "  },\n"
    '  "organization": {\n'
    '    "name": "cơ quan BAN HÀNH, chép nguyên văn",\n'
    '    "orgType": "quoc_hoi | chinh_phu | thu_tuong | bo_nganh | dai_hoc_vung | '
    'truong_thanh_vien | don_vi_truc_thuoc | phong_ban | null",\n'
    '    "parentOrg": null,\n'
    '    "idOverride": null\n'
    "  },\n"
    '  "signers": [{"fullName": "họ tên", "academicTitle": "PGS.TS hoặc null", '
    '"position": ["Hiệu trưởng"], "idOverride": null}],\n'
    '  "citations": [{"targetDocumentNumber": "số hiệu văn bản được nhắc tới", '
    '"relationType": "BASED_ON | REFERENCES | REPLACES | AMENDS | REPEALS", '
    '"targetArticle": "Điều 5 hoặc null", "context": "câu chứa trích dẫn, tối đa 400 ký tự"}],\n'
    '  "mentions": ["tên tổ chức được NHẮC TỚI trong thân văn bản"],\n'
    '  "normativeContents": [{"title": "tên bản kèm theo", '
    '"contentType": "' + _LOAI_ND + '", "status": null, "idOverride": null, '
    '"articles": [ ...như articles bên dưới... ]}],\n'
    '  "articles": [{"number": "Điều 1", "heading": "tiêu đề Điều hoặc null", '
    '"text": "TOÀN VĂN của Điều, chép nguyên si", "isImplementationClause": false}]\n'
    "}\n\n"

    "QUY TẮC BẮT BUỘC:\n"
    "1. CHỈ chép những gì có trong văn bản. Không suy đoán, không bổ sung kiến thức "
    "ngoài. Không rõ thì để null hoặc mảng rỗng.\n"
    "2. `articles[].text` phải là TOÀN VĂN của Điều đó, chép nguyên si, giữ đủ các "
    "khoản, điểm. Không tóm tắt, không rút gọn.\n"
    "3. Điều nằm trong bản Quy định/Quy chế ban hành kèm theo thì đặt vào "
    "`normativeContents[].articles`, KHÔNG đặt ở `articles` gốc. `articles` gốc chỉ "
    "chứa các Điều của chính văn bản (thường là Điều 1, 2, 3 về ban hành và thi hành).\n"
    "4. `isImplementationClause` = true cho các Điều thi hành kiểu 'Quyết định này có "
    "hiệu lực...', 'Chánh Văn phòng... chịu trách nhiệm thi hành'.\n"
    "5. `number` phải đúng dạng `Điều <số>`, vd `Điều 1`, `Điều 12a`. Không thêm dấu chấm.\n"
    "6. Ngày dạng dd/mm/yyyy, có số 0 đứng đầu: `05/04/2023`, không phải `5/4/2023`.\n"
    "7. `citations`: quan hệ lấy theo động từ trong câu — 'Căn cứ' → BASED_ON, "
    "'thay thế' → REPLACES, 'sửa đổi, bổ sung' → AMENDS, 'bãi bỏ' → REPEALS, còn lại "
    "chỉ nhắc tên → REFERENCES. Không tự trích dẫn chính văn bản này.\n"
    "7a. `targetDocumentNumber` CHỈ được là SỐ HIỆU, dạng `<số>/<năm>/<mã>` hoặc "
    "`<số>/<mã>` — ví dụ `35/2021/TT-BGDĐT`, `32/CP`, `08/NQ-HĐĐH`. Văn bản được "
    "viện dẫn bằng TÊN mà không kèm số hiệu (ví dụ 'Luật Giáo dục đại học ngày "
    "18/6/2012') thì BỎ khỏi `citations`, đừng đặt cả câu vào ô số hiệu.\n"
    "7b. Mỗi số hiệu chỉ xuất hiện MỘT lần trong `citations`. Nếu một văn bản vừa "
    "nằm ở phần Căn cứ vừa được nhắc trong thân bài thì chỉ ghi một dòng, lấy quan "
    "hệ mạnh hơn theo thứ tự REPEALS > REPLACES > AMENDS > BASED_ON > REFERENCES.\n"
    "8. TUYỆT ĐỐI không thêm các khoá normalizedNumber, orgId, personId, topicId, "
    "articleId, authorityLevel, isStub — máy nạp tự sinh.\n"
    "9. Chuỗi JSON phải escape đúng: xuống dòng trong `text` viết là \\n, dấu nháy kép "
    "viết là \\\". JSON phải parse được.\n"
    "10. Văn bản in HOA TOÀN BỘ ở phần đầu (tên cơ quan, tiêu đề) thì viết lại theo "
    "chính tả thường: `ĐẠI HỌC ĐÀ NẴNG` → `Đại học Đà Nẵng`, `QUYẾT ĐỊNH Ban hành` → "
    "`Quyết định Ban hành`. Chỉ áp dụng cho `organization.name` và `document.title`; "
    "`articles[].text` vẫn chép nguyên si.\n"
    "11. Mốc trang `----- [Trang N] -----` là do máy OCR chèn, KHÔNG phải nội dung. "
    "Bỏ hẳn khỏi mọi trường; câu nào bị nó cắt làm đôi thì nối lại cho liền.\n"
)


class KhoJson(Kho):
    """Hang cho cho che do JSON: quet thang kho txt, nhan ket qua qua validate."""

    PROMPT = PROMPT
    CHE_DO = "xuất JSON → document.schema.json"
    RA_MO_TA = "data/kg_json/"

    # Loc theo co file, dat tu main(). JSON phai chua toan van tung Dieu nen file
    # cang to cang de bi Gemini cat giua chung — day la bien rui ro duy nhat chua
    # kiem soat duoc, nen chia dot chay theo no.
    TU_KB = 0.0
    TOI_KB = 1e9

    def _nap_csv(self, csv_path, chi, tu_loi_cao):
        """Bo qua CSV — nguon viec la toan bo `data/clean/text_final`."""
        bo_co = 0
        for p in sorted(KHO_TXT.rglob("*.txt")):
            ma = p.name[:4]
            if chi and ma not in chi:
                continue
            kb = p.stat().st_size / 1024
            if not (self.TU_KB <= kb <= self.TOI_KB):
                bo_co += 1
                continue
            self.viec[ma] = {
                "id": ma,
                # ten_file la ten file KET QUA (.json). Ten dung khi dinh kem
                # phai la ten .txt that — dat .json thi Gemini tuong dau vao la
                # JSON, hien icon <> va co the doc sai dinh dang.
                "ten_file": p.stem + ".json",
                "ten_dinh_kem": p.name,
                "linh_vuc": p.parent.name,
                "duong_dan": str(p),
                "so_dong": 0,
                "ty_le_loi": "",
            }
        noi("[cau] nap %d van ban tu %s" % (len(self.viec), KHO_TXT))
        if bo_co:
            noi("[cau] bo qua %d file ngoai khoang %.0f-%.0f KB"
                % (bo_co, self.TU_KB, self.TOI_KB))

    # ---------- nhan ket qua ----------
    def nop(self, ma, text, nguon=None):
        if ma not in self.viec:
            return False, "khong co viec nay"

        raw = _boc_json(text)
        if raw is None:
            return False, "khong tim thay object JSON trong cau tra loi"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            return False, "JSON hong: %s (dong %d cot %d)" % (e.msg, e.lineno, e.colno)
        if not isinstance(data, dict):
            return False, "tang ngoai cung khong phai object"

        v = self.viec[ma]
        # sourceFile do CAU dien, khong de model tu ghi — no khong biet duong dan that.
        goc = Path(v["duong_dan"])
        data["sourceFile"] = "%s/%s" % (goc.parent.name, goc.name)

        loi = _validate(data)
        if loi:
            return False, "sai schema: " + " | ".join(loi[:4])

        canh_bao, nghi_ngo = _soi_them(data, goc)

        thu_muc = (self.nghi_ngo_dir if nghi_ngo else self.ra_dir) / v["linh_vuc"]
        thu_muc.mkdir(parents=True, exist_ok=True)
        dich = thu_muc / v["ten_file"]
        io.open(dich, "w", encoding="utf-8", newline="\n").write(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n")

        n_dieu = len(data.get("articles") or []) + sum(
            len(n.get("articles") or []) for n in data.get("normativeContents") or [])
        with self.khoa:
            self.dang_lam.pop(ma, None)
            self.hong.pop(ma, None)
            self.xong[ma] = {"duong_dan": str(dich), "so_ky_tu": len(raw),
                             "goc": goc.stat().st_size, "nghi_ngo": nghi_ngo,
                             "nguon": nguon, "canh_bao": canh_bao,
                             "so_dieu": n_dieu, "luc": int(__import__("time").time())}
            self._ghi_trang_thai()
        return True, {"duong_dan": str(dich), "nghi_ngo": nghi_ngo,
                      "canh_bao": canh_bao, "so_dieu": n_dieu}


# ============================================================
# BOC + KIEM
# ============================================================

def _boc_json(text: str):
    """Lay object JSON ra khoi cau tra loi (co the con rao ``` hoac loi dan)."""
    t = text.strip()
    t = re.sub(r"^```[a-zA-Z]*[ \t]*\r?\n?", "", t)
    t = re.sub(r"\r?\n?```[ \t]*$", "", t).strip()
    if t.startswith("{"):
        return t
    i, j = t.find("{"), t.rfind("}")
    return t[i:j + 1] if 0 <= i < j else None


def _validate(data: dict) -> list[str]:
    """Cho qua chinh `core/validate.py` cua legal_knowledge_graph.

    Ghi ra file tam roi goi `load_and_validate` thay vi tu viet lai bo kiem: neu
    ductran sua schema hay sua luat kiem cheo, cau nay tu dong theo, khong lech.
    """
    from legal_knowledge_graph.core.validate import load_and_validate

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
        tam = Path(f.name)
    try:
        return list(load_and_validate(tam).errors)
    finally:
        tam.unlink(missing_ok=True)


# Tieu de Dieu THAT: "Điều 5." / "Điều 5 Pham vi..." — sau so la dau cham hoac
# mot tieu de mo dau bang CHU HOA.
#
# Phai loai VIEN DAN bi OCR ngat dong roi roi xuong dau dong:
#     "...quy dinh tai khoan 2\nĐiều 16 của Luật này, trừ..."
# Dem ca nhung cai do thi 0090 (Luat sua doi, chi co 3 Dieu that) bi bao la co
# 9 Dieu, roi canh bao "thieu Dieu" oan cho ban JSON dung.
_DIEU = re.compile(
    r"^[ \t]*Điều\s+(\d{1,3}[a-zA-Z]?)\s*(?:[.．:]|\s+(?=[A-ZĐÀ-Ỹ]))", re.M)
# Vien dan mo dau bang TEN LOAI van ban roi "này"/"số" — "Điều 7 Nghị định này;"
# — cung phai loc, khong thi dem Dieu bi thua va bao "thieu Dieu" oan.
_LOAI_VB_VD = (r"Nghị\s*định|Thông\s*tư|Quyết\s*định|Luật|Bộ\s*luật|Quy\s*chế|"
               r"Quy\s*định|Điều\s*lệ|Pháp\s*lệnh|Nghị\s*quyết|Chỉ\s*thị|Hiến\s*pháp")
_VIEN_DAN = re.compile(
    r"^\s*(?:của|tại|và|;|,)"
    r"|^\s*[Ll]uật này|^\s*này\b"
    r"|^\s*(?:%s)\s+(?:này|số|\d)" % _LOAI_VB_VD)


def _soi_them(data: dict, goc: Path) -> tuple[list[str], bool]:
    """Kiem cac thu schema khong bat duoc — deu la dau hieu model bo bot noi dung."""
    canh_bao: list[str] = []
    txt = io.open(goc, encoding="utf-8", errors="replace").read()

    # --- cac loi da gap that o lan chay thu, schema khong chan duoc ---
    ct = data.get("citations") or []
    # So hieu co the mang chu cai sau so: 30a/2008/NQ-CP, 16a/2019/TT-BGDDT.
    # Hai dang so hieu hop le:
    #   <so>/<ma>        35/2021/TT-BGDĐT, 32/CP, 30a/2008/NQ-CP
    #   <so>-<ma>/TW     29-NQ/TW, 91-KL/TW — van ban Dang dung GACH NGANG
    so_hieu = re.compile(r"^\d{1,5}[a-zA-Z]?\s*[/-]")
    xau = [c.get("targetDocumentNumber", "") for c in ct
           if not so_hieu.match(c.get("targetDocumentNumber", ""))]
    if xau:
        canh_bao.append("citations co %d muc khong phai so hieu: %s"
                        % (len(xau), "; ".join(x[:40] for x in xau[:2])))

    dem: dict[str, int] = {}
    for c in ct:
        k = (c.get("targetDocumentNumber") or "").strip()
        dem[k] = dem.get(k, 0) + 1
    trung = [k for k, v in dem.items() if v > 1]
    if trung:
        canh_bao.append("citations trung so hieu: %s" % ", ".join(trung[:3]))

    if "[Trang" in json.dumps(data, ensure_ascii=False):
        canh_bao.append("con sot moc [Trang N] trong JSON")

    for ten, gt in (("organization.name", data.get("organization", {}).get("name")),
                    ("document.title", data.get("document", {}).get("title"))):
        s = (gt or "").strip()
        chu = [c for c in s if c.isalpha()]
        if len(chu) > 8 and all(c.isupper() for c in chu[:20]):
            canh_bao.append("%s dang in HOA toan bo: %r" % (ten, s[:40]))

    so_goc = len({m.group(1) for m in _DIEU.finditer(txt)
                  if not _VIEN_DAN.match(txt[m.end():m.end() + 24])})
    so_json = len(data.get("articles") or []) + sum(
        len(n.get("articles") or []) for n in data.get("normativeContents") or [])
    if so_goc and so_json < so_goc * 0.8:
        canh_bao.append("thieu Dieu: txt co ~%d, JSON co %d" % (so_goc, so_json))

    # Dieu chep day du thi tong do dai phai xap xi than van ban. Ngan qua = bi tom tat.
    dai = sum(len(a.get("text") or "") for a in (data.get("articles") or []))
    dai += sum(len(a.get("text") or "")
               for n in (data.get("normativeContents") or [])
               for a in (n.get("articles") or []))
    # Doi them NGUONG TUYET DOI. Van ban nao cung co phan khong thuoc than Dieu
    # — tieu ngu, so hieu, can cu, noi nhan, khoi ky — va chung da nam o cac
    # truong khac. Van ban nho thi phan do chiem ti le lon: 0407 chi 2,8 KB, ba
    # Dieu dung 624 ky tu (29%) la DU, khong thieu gi ca.
    if so_json and dai < len(txt) * 0.3 and len(txt) - dai >= 3000:
        canh_bao.append("than Dieu ngan bat thuong (%d/%d ky tu = %.0f%%)"
                        % (dai, len(txt), 100.0 * dai / max(len(txt), 1)))

    if not (data.get("signers") or []):
        canh_bao.append("khong co nguoi ky")
    if not (data.get("citations") or []):
        canh_bao.append("khong co can cu/trich dan nao")

    return canh_bao, bool(canh_bao)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8779)
    ap.add_argument("--out", default=str(RA_MAC_DINH))
    ap.add_argument("--chi", default="", help="chi lam nhung ma nay, vd 0322,0425")
    ap.add_argument("--trang-thai", default=str(TRANG_THAI))
    ap.add_argument("--tu-kb", type=float, default=0.0,
                    help="chi lam file tu co nay tro len (KB)")
    ap.add_argument("--toi-kb", type=float, default=1e9,
                    help="chi lam file toi co nay (KB) — chia dot theo co file")
    a = ap.parse_args()

    import cau_sua_txt
    cau_sua_txt.TRANG_THAI = Path(a.trang_thai)

    chan_cau_trung(a.port)

    chi = set(x.strip() for x in a.chi.split(",") if x.strip()) or None
    KhoJson.TU_KB, KhoJson.TOI_KB = a.tu_kb, a.toi_kb
    Handler.kho = KhoJson(None, a.out, chi=chi)
    Path(a.out).mkdir(parents=True, exist_ok=True)

    noi("[cau] che do JSON · nghe tai http://127.0.0.1:%d\n[cau] ra: %s\n"
        "[cau] checkpoint: %s" % (a.port, a.out, a.trang_thai))
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
