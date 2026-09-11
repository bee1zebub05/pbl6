"""
Trích người ký từ khối ký cuối văn bản -> node `Person` (Ontology §2.3).

Người ký là trường quan trọng của đề tài mà kho hiện chưa trích: chỉ có nó mới
trả lời được "văn bản nào do Hiệu trưởng X ký", "ai ký nhiều nhất ở lĩnh vực nào".

BỐN CÁI BẪY, đều đo được trên kho thật chứ không phải phòng xa:

1. Khối ký KHÔNG nằm ở cuối file.
   Phần lớn văn bản có phụ lục dài phía sau, nên chữ ký nằm giữa file. Đọc 40
   dòng cuối thì trượt 364/455 file. Phải quét toàn bộ rồi lấy lần khớp CUỐI
   CÙNG — đó là người ký bản chính, không phải người ký các văn bản được viện
   dẫn ở phần "Căn cứ".

2. Con dấu tròn đè lên chữ.
   OCR bẻ con dấu thành 5-8 mảnh vụn ('TRUÈAG', 'ĐẠI 18il HỌz') chen giữa chức
   danh và tên. Quét 6 dòng sau chức danh là hụt — 0082 có tên ở dòng thứ 8.
   Nên quét 14 dòng.

3. Chức danh bị sai dấu.
   Con dấu đè làm 'HIỆU TRƯỞNG' thành 'HIEU TRUơNG'. So khớp theo đúng dấu thì
   trượt gần hết, nên so khớp SAU KHI BỎ DẤU.

4. Chữ cái đầu của họ bị con dấu nuốt.
   'guyễn Kim Sơn' thay vì 'Nguyễn Kim Sơn'. Chữa được vì họ người Việt là tập
   ĐÓNG và nhỏ — dò ngược ra họ duy nhất khớp phần đuôi còn lại.

Chuẩn hoá tên xem `gop_ten_nguoi_ky` ở cuối file.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from collections import Counter, defaultdict

# --------------------------------------------------------------------------
# Bỏ dấu
# --------------------------------------------------------------------------


def bo_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")

    return s.replace("đ", "d").replace("Đ", "D").upper()


# --------------------------------------------------------------------------
# Nhận diện khối ký
# --------------------------------------------------------------------------

_CHUC_DANH = re.compile(
    r"HIEU\s*TRUONG|GIAM\s*DOC|CHU\s*TICH|BO\s*TRUONG|THU\s*TUONG|"
    r"TRUONG\s*BAN|CHANH\s*VAN\s*PHONG|CHU\s*NHIEM|THU\s*TRUONG|"
    r"TONG\s*THANH\s*TRA|VIEN\s*TRUONG|TM\.\s*HOI\s*DONG"
)

# Bản sao y ghi thẳng tên sau hai chấm, không qua khối ký.
_DA_KY = re.compile(r"[ĐD]ã\s*ký\s*:?\s*(.+)$", re.I)

# Học hàm đứng trước tên. OCR hay đọc 'PGS.TS.' thành 'PGS FS.' / 'PGS. IS.' vì
# con dấu đè lên chữ T. Cho phép biến thể đó, nhưng KHÔNG mở thành ký tự bất kỳ
# — mở rộng quá tay sẽ ăn mất từ đầu của tên thật.
_HOC_HAM = r"(?P<hh>(?:(?:PGS|GS|[TFI][S5]|ThS|Th\.S|CN)[\s.,]*){0,3})"

# Từ đầu được phép viết thường (con dấu nuốt mất chữ cái đầu), mọi từ sau BẮT
# BUỘC viết hoa đúng — nới chỗ này thì cụm 'Hỗ trợ sinh Vi' cũng lọt qua.
_TEN_NGUOI = re.compile(
    r"^"
    + _HOC_HAM
    + r"(?P<ten>[A-ZĐÀ-Ỹa-zà-ỹ][a-zà-ỹ]+(?:\s+[A-ZĐÀ-Ỹ][a-zà-ỹ]+){1,4})\s*$"
)

# Họ người Việt là tập ĐÓNG và nhỏ -> dùng làm bộ lọc chính xác cao. Không có nó
# thì mẫu tên bắt nhầm cả 'Hỗ trợ sinh Vi', 'Đại học Đà' — những cụm chữ hoa bình
# thường nằm ngay dưới khối ký.
HO_VIET = {
    "nguyen", "tran", "le", "pham", "hoang", "huynh", "phan", "vu", "vo", "dang",
    "bui", "do", "ho", "ngo", "duong", "ly", "doan", "dinh", "truong", "lam",
    "mai", "cao", "ta", "chu", "to", "thai", "kieu", "giang", "la", "quach",
    "tu", "ha", "luu", "vuong", "diep", "chuong", "trinh", "trieu", "khong",
    "nghiem", "luong", "thach", "bach", "au", "chau", "cu", "danh", "hua",
    "khuat", "lai", "lanh", "mac", "nong", "ong", "pho", "quang", "sy", "tang",
    "tong", "tinh", "ung", "van", "xa",
}

_CHUAN_CHUC_DANH = (
    ("HIEU TRUONG", "Hiệu trưởng"),
    ("GIAM DOC", "Giám đốc"),
    ("CHU TICH", "Chủ tịch"),
    ("BO TRUONG", "Bộ trưởng"),
    ("THU TUONG", "Thủ tướng"),
    ("TRUONG BAN", "Trưởng ban"),
    ("CHANH VAN PHONG", "Chánh Văn phòng"),
    ("CHU NHIEM", "Chủ nhiệm"),
    ("THU TRUONG", "Thứ trưởng"),
    ("TONG THANH TRA", "Tổng Thanh tra"),
    ("VIEN TRUONG", "Viện trưởng"),
    ("HOI DONG", "TM. Hội đồng"),
)


def _sua_ho(tu: str) -> str:
    """'guyễn' -> 'Nguyễn'. Trả '' nếu không phải họ người Việt."""

    k = bo_dau(tu).lower()

    if k in HO_VIET:
        return tu

    # Con dấu che mất 1-2 chữ cái đầu: tìm họ nào kết thúc bằng phần còn lại.
    # Chỉ nhận khi DUY NHẤT một họ khớp — nhiều họ khớp thì đoán là đoán mò.
    if len(k) >= 3:
        hop = [h for h in HO_VIET if h.endswith(k) and 0 < len(h) - len(k) <= 2]

        if len(hop) == 1:
            return hop[0].capitalize()

    return ""


def chuan_chuc_danh(dong: str) -> str:
    """Dòng chức danh -> tên chuẩn. '' nếu không nhận ra.

    'KT. HIỆU TRƯỞNG' và 'PHÓ HIỆU TRƯỞNG' đều về 'Phó hiệu trưởng': KT. nghĩa
    là ký thay, tức người ký không phải trưởng đơn vị. Bỏ qua chi tiết này là
    gán nhầm quyền hạn cho một phó hiệu trưởng.
    """

    kd = bo_dau(dong)

    for mau, ten in _CHUAN_CHUC_DANH:
        if re.search(mau.replace(" ", r"\s*"), kd):
            if re.search(r"\bKT\.|\bPHO\b|\bTL\.", kd):
                return "Phó " + ten[0].lower() + ten[1:]

            return ten

    return ""


def chuan_hoc_ham(s: str) -> str:
    """'PGS FS.' / 'PGS. IS.' -> 'PGS.TS'."""

    hh = re.sub(r"[\s.,]+", "", (s or "").upper())
    hh = re.sub(r"[TFI][S5]", "TS", hh)
    ra = [x for x in ("PGS", "GS", "TS", "THS", "CN") if x in hh]

    # 'PGS' chứa chuỗi con 'GS' — không phải hai học hàm.
    if "PGS" in ra and "GS" in ra:
        ra.remove("GS")

    return ".".join({"THS": "ThS"}.get(x, x) for x in ra)


def _tach_ten(s: str) -> tuple[str, str]:
    """Dòng -> (tên, học hàm). ('', '') nếu dòng không phải tên người."""

    m = _TEN_NGUOI.match((s or "").strip())

    if not m:
        return "", ""

    tu = m.group("ten").split()

    if not 2 <= len(tu) <= 5:
        return "", ""

    ho = _sua_ho(tu[0])

    if not ho:
        return "", ""

    tu[0] = ho if bo_dau(tu[0]).lower() in HO_VIET else ho.capitalize()

    return " ".join(tu), chuan_hoc_ham(m.group("hh"))


def tim_nguoi_ky(text: str) -> dict:
    """-> {'ho_ten', 'hoc_ham', 'chuc_danh'}; giá trị rỗng nếu không đọc được."""

    dong = [d.strip() for d in (text or "").splitlines() if d.strip()]
    ten = hoc_ham = chuc_danh = ""

    for i, d in enumerate(dong):
        m = _DA_KY.search(d)

        if m:
            a, b = _tach_ten(m.group(1))

            if a:
                ten, hoc_ham, chuc_danh = a, b, ""
                continue

        # Chức danh phải ĐỨNG MỘT MÌNH trên dòng thì mới là khối ký. Câu
        # '... của Bộ trưởng Bộ Giáo dục và Đào tạo)' giữa thân bài không phải
        # chữ ký — bắt cả những chỗ như vậy rồi lấy lần khớp cuối cùng thì kết
        # quả hay trỏ ra giữa tài liệu.
        if not _CHUC_DANH.search(bo_dau(d)) or len(d) > 34:
            continue

        if re.search(r"(của|theo|tại|do)\s*$", dong[i - 1] if i else "", re.I):
            continue

        if re.search(r"[)（].*$|^\(", d):
            continue

        for e in dong[i + 1: i + 15]:
            m2 = _DA_KY.search(e)
            a, b = _tach_ten(m2.group(1) if m2 else e)

            if a:
                ten, hoc_ham, chuc_danh = a, b, chuan_chuc_danh(d)
                break

    return {"ho_ten": ten, "hoc_ham": hoc_ham, "chuc_danh": chuc_danh}


# --------------------------------------------------------------------------
# Chuẩn hoá: gộp các cách viết sai của cùng một người
# --------------------------------------------------------------------------

# Cặp ký tự OCR hay đọc nhầm nhau trên chữ Việt có dấu và có con dấu đè lên.
# Mỗi cặp ở đây đều lấy từ lỗi THẬT đã gặp, không phải liệt kê cho đủ.
_NHAM = [
    set("vw"), set("ae"), set("ao"), set("eo"), set("il"), set("io"), set("ij"),
    set("un"), set("cg"), set("ce"), set("sf"), set("st"), set("rn"), set("hb"),
    set("gq"), set("pq"), set("uv"), set("mn"), set("dđ"),
]

_DAU = re.compile(r"[̀-ͯ]")

# Tiếng Việt: một ÂM TIẾT chỉ mang ĐÚNG MỘT dấu thanh. Năm dấu thanh là
# huyền/sắc/ngã/hỏi/nặng; còn mũ (U+0302), móc (U+031B), trăng (U+0306) KHÔNG
# phải dấu thanh.
#   'Nguyễn' = ê(mũ) + ngã        -> 1 dấu thanh, đúng chính tả
#   'Ngụyễn' = ụ(nặng) + ê + ngã  -> 2 dấu thanh, KHÔNG tồn tại trong tiếng Việt
# Đây là chỗ phân biệt bản OCR đúng với bản OCR sai khi cả hai bỏ dấu ra đều
# giống hệt nhau.
_THANH = set("̣̀́̃̉")


def _khoa(s: str) -> str:
    return bo_dau(s).lower()


def _dung_chinh_ta(s: str) -> bool:
    """Mỗi từ có quá một dấu thanh không?

    KHÔNG đếm tổng số dấu: bản OCR sai thường có NHIỀU dấu hơn bản đúng, vì nó
    rắc thêm dấu vào sai chỗ. Đếm tổng thì chọn nhầm đúng bản hỏng.
    """

    for tu in unicodedata.normalize("NFD", s or "").split():
        if sum(1 for c in tu if c in _THANH) > 1:
            return False

    return True


def _cung_nguoi(a: str, b: str) -> bool:
    """Hai cách viết (ĐÃ BỎ DẤU) này có phải cùng một người?"""

    if a == b:
        return True

    if abs(len(a) - len(b)) > 1:
        return False

    ops = [o for o in difflib.SequenceMatcher(None, a, b).get_opcodes()
           if o[0] != "equal"]

    if len(ops) != 1:
        return False

    kieu, i1, i2, j1, j2 = ops[0]

    if max(i2 - i1, j2 - j1) > 1:
        return False

    if kieu == "replace":
        # KHÔNG gộp bừa mọi cặp lệch một ký tự: 'Lê Văn Hải' và 'Lê Văn Mải'
        # cũng lệch một ký tự nhưng là hai người. Chỉ gộp khi ký tự lệch nằm
        # trong bảng nhầm của OCR.
        cap = {a[i1], b[j1]}

        return any(cap <= nham for nham in _NHAM)

    # Thêm/bớt một ký tự: chỉ nhận khi đó là KÝ TỰ BỊ LẶP ('Thườởng' <- 'Thưởng')
    dai, vt = (a, i1) if len(a) > len(b) else (b, j1)

    return dai[vt] == dai[vt - 1] if vt else (len(dai) > 1 and dai[vt] == dai[1])


def gop_ten_nguoi_ky(ten_dem: Counter | dict) -> dict[str, str]:
    """{tên: số lần} -> {tên gốc: tên chuẩn}.

    'Đoàn Quang Vinh' (21 văn bản) và 'Doan Quang Winh' (1 văn bản) là cùng một
    người; để nguyên thì thành hai node Person, mọi số đếm về người ký đều lệch
    và truy vấn 'văn bản nào do X ký' trả thiếu.

    Chọn tên chuẩn trong mỗi nhóm, theo thứ tự: đúng chính tả dấu thanh > họ là
    họ người Việt thật > xuất hiện nhiều lần hơn > còn nhiều dấu hơn.
    """

    ds = sorted(ten_dem)
    khoa = {t: _khoa(t) for t in ds}
    cha = {t: t for t in ds}

    def tim(x: str) -> str:
        while cha[x] != x:
            cha[x] = cha[cha[x]]
            x = cha[x]

        return x

    for i, a in enumerate(ds):
        for b in ds[i + 1:]:
            if _cung_nguoi(khoa[a], khoa[b]):
                ra, rb = tim(a), tim(b)

                if ra != rb:
                    cha[rb] = ra

    nhom: dict[str, list[str]] = defaultdict(list)

    for t in ds:
        nhom[tim(t)].append(t)

    ra: dict[str, str] = {}

    for thanh_vien in nhom.values():
        chuan = max(
            thanh_vien,
            key=lambda t: (
                _dung_chinh_ta(t),
                _khoa(t.split()[0]) in HO_VIET if t.split() else False,
                ten_dem[t],
                len(_DAU.findall(unicodedata.normalize("NFD", t))),
            ),
        )

        for t in thanh_vien:
            ra[t] = chuan

    return ra
