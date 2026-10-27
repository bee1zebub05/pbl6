# -*- coding: utf-8 -*-
"""Cau hang cho: dua tung file .txt da sach len Gemini web, nhan ve MOT file JSON
dung `legal_knowledge_graph/schema/document.schema.json`.

Dung chung toan bo may hang cho / checkpoint / extension Chrome voi cau_sua_txt.py.
Chi khac ba cho:

  1. Cau lenh (PROMPT)  -> bao Gemini tra ve JSON thay vi plaintext.
  2. Nguon viec         -> quet thang `data/clean/text_final`, khong doc CSV.
  3. Cong nhan ket qua  -> parse JSON roi cho qua `core/ingest/validate.py` cua
                           legal_knowledge_graph. Sai schema la KHONG nhan, tra
                           loi cu the ve extension de no thu lai.

    python tools/gemini_web/cau_json.py --chi 0322      # test mot file
    python tools/gemini_web/cau_json.py                 # chay het

Ra: data/clean/json/v1/<linh vuc>/<ma>.json — ban nao qua duoc schema nhung con cho
dang ngo thi vao data/clean/json/v1/_nghi_ngo/.
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
# Tu commit 88d6079 package `legal_knowledge_graph` nam duoi src/, khong con
# o goc repo -> _validate() import truot neu khong chen duong nay.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from cau_sua_txt import Handler, Kho, chan_cau_trung, noi   # noqa: E402
import va_dieu_thieu as VD                                  # noqa: E402

GOC = Path(__file__).resolve().parents[2]
KHO_TXT = GOC / "data" / "clean" / "text_final"
RA_MAC_DINH = GOC / "data" / "clean" / "json" / "v1"
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
            "Hướng dẫn | Chương trình | Phụ lục")
# reference/target_groups_seed.json — validate.py doi khop CHINH XAC mot trong tam muc.
_NHOM = ("Người học | Cán bộ, giảng viên, viên chức, người lao động | Đơn vị trực thuộc | "
         "Cơ sở giáo dục / trường đại học thành viên | Cơ quan, tổ chức, cá nhân có liên quan | "
         "Hội đồng và thành viên hội đồng | Doanh nghiệp, đối tác/tổ chức nước ngoài | Khác")
# reference/organizations_seed.json — ten CHUAN. Khong dung ten chuan thi loader sinh
# node rieng, mot co quan thanh nhieu node. Do that: ĐHBK tung bi tach lam 3 node.
# reference/organizations_seed.json — ten CHUAN. Khong dung ten chuan thi loader
# sinh node rieng, mot co quan thanh nhieu node. Do that: DHBK tung bi tach lam
# 3 node. Doc THANG tu seed, khong chep tay — chep tay thi them to chuc vao seed
# xong lai quen sua prompt.
def _doc_ten_co_quan():
    import json as _json
    _p = (GOC / "src" / "legal_knowledge_graph" / "reference"
          / "organizations_seed.json")
    try:
        _ds = _json.loads(_p.read_text(encoding="utf-8"))["organizations"]
    except Exception:
        return ""
    # Loc theo orgId, KHONG theo name: cap bien the (vd "Doan TNCS Ho Chi Minh"
    # va "Doan Thanh nien Cong san Ho Chi Minh") chung mot orgId, chi duoc dua
    # TEN HIEN THI vao prompt. Dua ca hai la bao model tu chon, data lai lech.
    _theo_id = {}
    for _o in _ds:
        _theo_id[_o["orgId"]] = _o["name"]   # dong sau ghi de = ten hien thi
    return " | ".join(dict.fromkeys(_theo_id.values()))


_CO_QUAN = _doc_ten_co_quan()

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
    '    "targetGroups": ["đối tượng áp dụng, chọn trong: ' + _NHOM + '"],\n'
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
    "khoản, điểm. Không tóm tắt, không rút gọn. `text` phải MỞ ĐẦU bằng "
    "đúng `number` rồi dấu chấm, y như văn bản in: `Điều 1. Miễn học phí...`, "
    "không được cắt bỏ phần `Điều 1.` ở đầu.\n"
    "3. Điều nằm trong bản Quy định/Quy chế ban hành kèm theo thì đặt vào "
    "`normativeContents[].articles`, KHÔNG đặt ở `articles` gốc. `articles` gốc chỉ "
    "chứa các Điều của chính văn bản (thường là Điều 1, 2, 3 về ban hành và thi hành).\n"
    "3a. Bản kèm theo KHÔNG đánh số bằng Điều mà đánh `1.`, `2.`, `2.1.` (hay gặp ở "
    "Quy trình, Kế hoạch, Chương trình, và cả Quy định dạng bảng) thì VẪN "
    "tạo `normativeContents`, cắt theo mục đánh số CẤP CAO NHẤT, mỗi mục một phần tử "
    "trong `articles`. Bảng biểu thì chép từng dòng thành văn xuôi trong `text` của mục "
    "chứa nó. TUYỆT ĐỐI không để `articles` rỗng — schema chặn, cả file bị loại.\n"
    "3b. `contentType` lấy theo CHỮ IN ở đầu bản kèm theo, không đoán. Tiêu đề "
    "ghi `PHỤ LỤC` thì `contentType` là `Phụ lục`, dù bên trong nó là bảng biểu hay "
    "danh mục. Đừng khai thành `Quy định` hay `Hướng dẫn`.\n"
    "3c. Một văn bản có thể kèm NHIỀU bản: ví dụ một Quy chế rồi một PHỤ LỤC. Mỗi "
    "bản là MỘT PHẦN TỬ RIÊNG trong `normativeContents`. Dòng `PHỤ LỤC` là TIÊU ĐỀ của bản "
    "mới, TUYỆT ĐỐI không biến nó thành một phần tử trong `articles` của bản trước, và "
    "không bao giờ được ghi `number` là `PHỤ LỤC` — `number` chỉ là số (xem luật 5).\n"
    "4. `isImplementationClause` = true cho các Điều thi hành kiểu 'Quyết định này có "
    "hiệu lực...', 'Chánh Văn phòng... chịu trách nhiệm thi hành'.\n"
    "5. `number` dạng `Điều <số>`, vd `Điều 1`, `Điều 12a`, không thêm dấu chấm. Riêng "
    "mục ở luật 3a thì ghi đúng con số văn bản in, bỏ dấu chấm cuối: `1`, `2`, `2.1` — "
    "hoặc số La Mã `I`, `II`, `IV` nếu văn bản đánh thế (rất hay gặp ở Đề án, Kế hoạch). "
    "Không tự đổi `1.` thành `Điều 1` — văn bản không viết thế.\n"
    "6. Ngày dạng dd/mm/yyyy, có số 0 đứng đầu: `05/04/2023`, không phải `5/4/2023`.\n"
    "6a. `status` chỉ phản ánh điều CHÍNH VĂN BẢN NÀY nói. Mặc định CON_HIEU_LUC; HET_HIEU_LUC khi "
    "chính nó nói vậy; CHUA_HIEU_LUC khi `effectiveDate` muộn hơn `issueDate`. ĐỪNG đoán xa hơn "
    "thế: bạn chỉ nhìn thấy MỘT văn bản, không thể biết vài năm sau có văn bản khác thay thế nó. "
    "Việc đó đã có tools/kiem_tra/suy_hieu_luc.py làm trên toàn kho.\n"
    "6b. `documentNumber` không được có khoảng trắng: `1088 /QĐ-ĐHBK` phải ghi "
    "`1088/QĐ-ĐHBK`. Văn bản in sẵn `Số: ...../QĐ-ĐHBK` rồi điền số viết tay vào chỗ trống nên "
    "hay thừa khoảng trắng — bỏ hết, chỉ giữ số và dấu `/`.\n"
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
        "7c. Một câu có NHIỀU số hiệu thì chỉ lấy số hiệu của văn bản ĐÍCH, bỏ chuỗi sửa "
    "đổi phía sau. Ví dụ 'bãi bỏ Điều 165 của Luật Xây dựng số 50/2014/QH13 đã được sửa "
    "đổi, bổ sung theo Luật số 03/2016/QH14, Luật số 45/2024/QH15' thì CHỈ ghi một dòng "
    "REPEALS tới 50/2014/QH13. Các số còn lại là lịch sử sửa đổi của chính nó, không phải "
    "văn bản bị bãi bỏ. Luật này CHỈ dành cho REPLACES/AMENDS/REPEALS. Khối `Căn cứ` "
    "thì NGƯỢC LẠI: mọi số hiệu trong đó đều là một dòng BASED_ON riêng, "
    "kể cả khi câu viết 'Căn cứ A ... được sửa đổi, bổ sung tại B' — A và B đều là "
    "căn cứ thật, giữ cả hai.\n"
    "7d. Số hiệu LUÔN có phần chữ (QH13, NĐ-CP, QĐ-ĐHBK, NQ/TW). Ngày tháng và năm KHÔNG "
    "phải số hiệu: '25/12/2001', '2015', '14/06/2019' đều SAI, bỏ hẳn trích dẫn đó.\n"
"8. TUYỆT ĐỐI không thêm các khoá normalizedNumber, orgId, personId, topicId, "
    "articleId, authorityLevel, isStub — máy nạp tự sinh.\n"
    "9. Chuỗi JSON phải escape đúng: xuống dòng trong `text` viết là \\n, dấu nháy kép "
    "viết là \\\". JSON phải parse được.\n"
    "10. Văn bản in HOA TOÀN BỘ ở phần đầu (tên cơ quan, tiêu đề) thì viết lại theo "
    "chính tả thường: `ĐẠI HỌC ĐÀ NẴNG` → `Đại học Đà Nẵng`, `QUYẾT ĐỊNH Ban hành` → "
    "`Quyết định Ban hành`. Chỉ áp dụng cho `organization.name` và `document.title`; "
    "`articles[].text` vẫn chép nguyên si.\n"
        "10a. `organization.name` phải dùng ĐÚNG tên chuẩn nếu cơ quan nằm trong danh sách: "
    + _CO_QUAN + ". Văn bản in 'Trường Đại học Bách khoa, Đại học Đà Nẵng' hay 'Trường "
    "Đại học Bách khoa - Đại học Đà Nẵng' thì vẫn ghi 'Trường Đại học Bách khoa'. Khác "
    "cách viết là máy nạp dựng thành node riêng, một trường thành ba node.\n"
    "10b. `mentions` chỉ ghi tổ chức CÓ DANH TÍNH RÕ, ưu tiên tên trong danh sách ở 10a. "
    "Bỏ các cụm chung chung không xác định được là đơn vị nào: 'Ban Giám hiệu', 'Phòng "
    "Đào tạo', 'Các Khoa, bộ môn trực thuộc', 'Các đơn vị'. Không chắc thì bỏ.\n"
    "10c. KHÔNG lấy `mentions` từ khối `Nơi nhận:` ở cuối văn bản. Đó là danh sách gửi "
    "công văn, không phải tổ chức được văn bản nhắc tới về nội dung. Chỉ lấy tổ chức "
    "xuất hiện trong thân các Điều hoặc phần Căn cứ.\n"
    "11. Mốc trang `----- [Trang N] -----` là do máy OCR chèn, KHÔNG phải nội dung. "
    "Bỏ hẳn khỏi mọi trường; câu nào bị nó cắt làm đôi thì nối lại cho liền.\n"
)


class KhoJson(Kho):
    """Hang cho cho che do JSON: quet thang kho txt, nhan ket qua qua validate."""

    PROMPT = PROMPT
    CHE_DO = "xuất JSON → document.schema.json"
    RA_MO_TA = "data/clean/json/v1/"

    # Loc theo co file, dat tu main(). JSON phai chua toan van tung Dieu nen file
    # cang to cang de bi Gemini cat giua chung — day la bien rui ro duy nhat chua
    # kiem soat duoc, nen chia dot chay theo no.
    TU_KB = 0.0
    TOI_KB = 1e9
    # Kho .txt nguon. Doi duoc qua --nguon de chay rieng mot tap con, vd
    # data/clean/sinh_vien_103/text (103 van ban lien quan nguoi hoc).
    NGUON = KHO_TXT

    def _nap_csv(self, csv_path, chi, tu_loi_cao):
        """Bo qua CSV — nguon viec la toan bo `data/clean/text_final`."""
        bo_co = 0
        for p in sorted(self.NGUON.rglob("*.txt")):
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
        noi("[cau] nap %d van ban tu %s" % (len(self.viec), self.NGUON))
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


def _cuu_json(raw: str, toi_da: int = 300):
    """Doc JSON co dau nhay thang khong escape ben trong chuoi.

    Model hay chuan hoa “Dat” thanh "Dat" roi quen escape, the la chuoi dut
    giua chung. Khong the quet mot luot roi doan dau la nhay that dau la nhay
    noi dung — "..." theo sau bang dau phay thi nhap nhang y het nhau.

    Nen de chinh json.loads chi cho: loi "Expecting ',' delimiter" tai vi tri p
    nghia la parser vua dong chuoi som ngay truoc p. Escape dung dau nhay do
    roi doc lai. Moi vong go duoc mot dau; van ban co bao nhieu dau nhay noi
    dung thi bay nhieu vong, va no hoi tu vi moi vong tien them.

    -> (data, so_dau_da_va) hoac (None, 0) neu khong cuu duoc.
    """
    import json as _json

    cuu = raw
    for lan in range(toi_da):
        try:
            return _json.loads(cuu), lan
        except _json.JSONDecodeError as e:
            # chi nhan loi do chuoi dong som; het JSON that thi chiu
            if "delimiter" not in e.msg and "Expecting" not in e.msg:
                return None, 0
            j = cuu.rfind('"', 0, e.pos)
            if j <= 0:
                return None, 0
            # dau nhay do da escape san thi khong phai thu pham
            n = 0
            k = j - 1
            while k >= 0 and cuu[k] == "\\":
                n += 1
                k -= 1
            if n % 2:
                return None, 0
            cuu = cuu[:j] + "\\" + cuu[j:]
    return None, 0


def _validate(data: dict) -> list[str]:
    """Cho qua chinh `core/ingest/validate.py` cua legal_knowledge_graph.

    Ghi ra file tam roi goi `load_and_validate` thay vi tu viet lai bo kiem: neu
    ductran sua schema hay sua luat kiem cheo, cau nay tu dong theo, khong lech.
    """
    from legal_knowledge_graph.core.ingest.validate import load_and_validate

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
    # So voi VUNG QUY PHAM (tu tieu de Dieu dau den tieu de Dieu cuoi) chu
    # KHONG so voi ca file. Phu luc — bieu mau, danh muc, de an — khong thuoc
    # Dieu nao ca; lay ca file lam mau so thi 0482 co ba Dieu dung 391 ky tu
    # tren file 200 KB se bi bao thieu, trong khi no da chep du ca ba.
    # Do DO PHU giua chinh cac Dieu DA CO trong JSON: dinh vi tung than Dieu
    # trong .txt, roi xem tu Dieu dau den Dieu cuoi con doan nao khong thuoc
    # Dieu nao khong. Do moi tra loi dung cau hoi 'co bi rot noi dung giua
    # chung khong'.
    #
    # Hai mau so truoc deu sai: lay ca file thi phu luc lam phong mau so; lay
    # tu tieu de Dieu dau den tieu de cuoi thi bieu mau phu luc (cung danh so
    # Dieu lai tu 1) cung lam phong. Ca hai deu bao nham hang chuc file.
    # So SAU KHI NEN khoang trang. Duong cu (va_dieu_thieu.py) CAT than Dieu
    # thang tu .txt nen giu nguyen cho ngat dong, find() khop tuyet doi chay
    # duoc. Duong moi model tu go lai, no noi dong khac di -> find() truot
    # gan het va bao oan: lo 103 van ban co 55 file dinh nhan nghi ngo, trong
    # do 0016 nguyen van 54/54 Dieu van bi gan, con 0013 lech that (3/29) lai
    # khong. Nen khoang trang xong thi hai duong do nhu nhau.
    # Don rac OCR roi nen khoang trang, ap dung cho CA HAI PHIA.
    #
    # Hai thu phai bo. Mot la moc '----- [Trang N] -----'. Hai la SO TRANG in
    # o dong rieng ngay sau moc — MOC_TRANG khong dong toi, ma no nam LOT GIUA
    # than Dieu nen find() truot: 0017 mat 38/57 Dieu chi vi the. Chi xoa dong
    # CHI CO CHU SO; '2. Chuan dau ra...' la khoan 2, xoa la sai.
    #
    # Phai don CA HAI PHIA vi hai duong sinh JSON khac nhau: va_dieu_thieu.py
    # CAT than Dieu thang tu .txt nen than Dieu CO so trang va giu nguyen cho
    # ngat dong; model tu go lai thi KHONG co so trang va noi dong khac di.
    # Don mot phia thi duong kia vo: chi don _sach, v4 tut tu 57 xuong 27 file
    # canh bao nhung v1 vot tu 2 len 175.
    def _don(_s):
        _s = VD.MOC_TRANG.sub("", _s or "")
        _s = re.sub(r"^[ \t]*\d{1,3}[ \t]*$", "", _s, flags=re.M)
        # Tieu de chay cua Cong bao, cung lot giua than Dieu nhu so trang.
        # Do that: 69/454 file co, tong 1.274 dong (0153 co 63, 0089 co 22).
        _s = re.sub(r"^[ \t]*CÔNG BÁO/.*$", "", _s, flags=re.M)
        return re.sub(r"\s+", " ", _s).strip()

    _sach = _don(txt)

    # Do RIENG tung khoi, khong gop ca van ban vao mot nhip. Dieu cua chinh
    # van ban va Dieu cua tung ban kem theo nam roi nhau trong .txt; do gop
    # thi nhip keo tu Dieu 1 den muc cuoi cua phu luc, om luon khoi ky ten
    # nam GIUA — 0156 nguyen van 6/6 Dieu van bi bao 45% chi vi the.
    _khoi = [("các Điều", data.get('articles') or [])]
    for _n in (data.get('normativeContents') or []):
        _khoi.append((_n.get('contentType') or 'bản kèm theo',
                      _n.get('articles') or []))

    for _ten, _ds in _khoi:
        _vt = []
        for _a in _ds:
            _t = _don(_a.get('text'))
            _i = _sach.find(_t) if _t else -1
            if _i >= 0:
                _vt.append((_i, _i + len(_t)))
        if len(_vt) < 2:
            continue
        _vt.sort()
        _gop = [list(_vt[0])]
        for _s, _e in _vt[1:]:
            if _s <= _gop[-1][1]:
                _gop[-1][1] = max(_gop[-1][1], _e)
            else:
                _gop.append([_s, _e])
        _phu = sum(e - s for s, e in _gop)
        _span = _gop[-1][1] - _gop[0][0]
        # Nguong 0,85 chon tu phan bo that tren 334 file: 304 file >= 95%,
        # dai 85-95% la tieu de Chuong/Muc da co y cat ra (chung nam GIUA cac
        # Dieu nen hien len thanh khoang ho), va chi 4 file rot xuong duoi 85%.
        if _span >= 3000 and _phu < _span * 0.85:
            canh_bao.append("ho noi dung giua %s (%d/%d ky tu = %.0f%%)"
                            % (_ten, _phu, _span, 100.0 * _phu / max(_span, 1)))

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
    ap.add_argument("--nguon", default=str(KHO_TXT),
                    help="thu muc .txt nguon (mac dinh data/clean/text_final)")
    a = ap.parse_args()

    KhoJson.NGUON = Path(a.nguon)
    # Nhan hien tren panel phai theo --out that, khong thi bao nham cho ghi.
    KhoJson.RA_MO_TA = a.out.replace(chr(92), "/").rstrip("/") + "/"
    if not KhoJson.NGUON.is_dir():
        raise SystemExit("khong thay thu muc nguon: %s" % KhoJson.NGUON)

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
