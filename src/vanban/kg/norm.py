"""
Suy diễn thuộc tính node `Document` / `Organization` từ metadata.

Toàn bộ hàm ở đây chỉ cần **số hiệu + metadata crawler**, không đọc nội dung
văn bản. Đó là điều kiện bắt buộc: theo §1 Ontology, văn bản bị viện dẫn mà
chưa crawl vẫn phải dựng được thành node `Document` stub — lúc đó tất cả những
gì ta có chỉ là cái số hiệu moi ra từ thân văn bản khác. Cùng một bộ hàm chạy
được cho cả 460 văn bản thật lẫn ~1.600 stub ở Bước 2.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from ..normalize import deaccent


# ============================================================
# SỐ HIỆU
# ============================================================

# `Ð` (U+00D0, eth) không phải `Đ` (U+0110) nhưng nhìn y hệt — cả OCR lẫn
# người gõ metadata đều lẫn hai ký tự này (xem file 0158 `TT-BGDÐT`).
_DE_VARIANTS = {"Ð": "Đ", "ð": "đ"}

# Gạch ngang unicode: crawler và PDF trả về đủ loại, `QĐ–ĐHBK` với `QĐ-ĐHBK`
# là một.
_DASHES = {"–": "-", "—": "-", "−": "-", "‐": "-", "‑": "-"}

_SPACE = re.compile(r"\s+")


def so_hieu_norm(raw: str) -> str:
    """
    Dạng chuẩn để hiển thị và làm khoá: `Số: 09/2020/TT-BGDĐT` -> `9/2020/TT-BGDĐT`.

    Bỏ số 0 đứng đầu ở phần số thứ tự vì cùng một văn bản được viết cả hai
    kiểu (`08/2014/NĐ-CP` và `8/2014/NĐ-CP`) — không gộp thì Bước 2 sẽ nối
    trích dẫn vào hai node khác nhau. Hai phần sau (năm, mã loại) giữ nguyên.
    """

    if not raw:
        return ""

    text = unicodedata.normalize("NFC", str(raw)).strip()

    for src, dst in {**_DE_VARIANTS, **_DASHES}.items():
        text = text.replace(src, dst)

    text = re.sub(r"^\s*S[ốôo]\s*[:.]?\s*", "", text, flags=re.IGNORECASE)

    # Không phải văn bản nào cũng có số hiệu: Hiến pháp thì crawler ghi thẳng
    # "Hiến pháp 2013". Bỏ khoảng trắng và viết hoa cả cụm đó ra
    # "HIẾNPHÁP2013" — đọc không nổi. Chỉ chuẩn hoá khi thật sự là số hiệu.
    if "/" not in text:
        return text

    text = _SPACE.sub("", text).upper().strip("/-")

    parts = text.split("/")

    if parts and parts[0].isdigit() and int(parts[0]):
        parts[0] = str(int(parts[0]))

    return "/".join(parts)


def so_hieu_key(raw: str) -> str:
    """
    Khoá gộp trùng — bản bỏ dấu của `so_hieu_norm`.

    Metadata có cả `TT-BGDĐT` lẫn `TT-BGDDT` (doc 0307) cho cùng một loại văn
    bản. Trong kho hiện tại hai dạng đó chưa đụng nhau, nhưng trích dẫn moi từ
    text OCR ở Bước 2 thì mất dấu liên tục — dùng khoá bỏ dấu ngay từ bây giờ
    để không phải đổi khoá chính giữa chừng.
    """

    return _SPACE.sub("", deaccent(so_hieu_norm(raw)).replace(".", "")).upper()


# `2347/QĐ-ĐHBK`    -> ("2347", None,   "QĐ", "ĐHBK")
# `9/2020/TT-BGDĐT` -> ("9",    "2020", "TT", "BGDĐT")
# `3878/BGDĐT-PC`   -> ("3878", None,   None, "BGDĐT-PC")  (công văn, không mã loại)
_SO_HIEU_PARTS = re.compile(
    r"^(?P<num>\d+)"
    r"(?:/(?P<year>\d{4}))?"
    r"(?:/(?P<tail>.+))?$"
)

# Mã loại đứng trước dấu `-` trong đuôi số hiệu. `QH13`/`QH15` dính liền số
# khoá nên phải bắt riêng.
_TYPE_BY_CODE = {
    "QH": "Luật",
    "UBTVQH": "Pháp lệnh",
    "NĐ": "Nghị định",
    "TT": "Thông tư",
    "TTLT": "Thông tư liên tịch",
    "QĐ": "Quyết định",
    "NQ": "Nghị quyết",
    "CT": "Chỉ thị",
    "HD": "Hướng dẫn",
    "KH": "Kế hoạch",
    "VBHN": "Văn bản hợp nhất",
    "L": "Lệnh",
}


def split_so_hieu(norm: str) -> tuple[str, str | None, str | None, str | None]:
    """Tách số hiệu chuẩn thành (số, năm, mã loại, mã cơ quan)."""

    match = _SO_HIEU_PARTS.match(norm or "")

    if not match:
        return "", None, None, None

    num, year, tail = match.group("num"), match.group("year"), match.group("tail")

    if not tail:
        return num, year, None, None

    # `QH13`, `QH14`, `QH15` — Quốc hội khoá mấy, không có dấu `-`.
    if re.fullmatch(r"QH\d*", tail):
        return num, year, "QH", tail

    if "-" in tail:
        code, org = tail.split("-", 1)

        # Công văn không có mã loại: `3878/BGDĐT-PC` — `BGDĐT` là cơ quan chứ
        # không phải loại văn bản. Phân biệt bằng chính bảng mã loại.
        if code in _TYPE_BY_CODE:
            return num, year, code, org

        return num, year, None, tail

    if tail in _TYPE_BY_CODE:
        return num, year, tail, None

    return num, year, None, tail


def doc_type_from_so_hieu(norm: str) -> str | None:
    """Đoán loại văn bản từ số hiệu. Dùng khi metadata thiếu (stub, file lạc)."""

    _, _, code, org = split_so_hieu(norm)

    if code:
        return _TYPE_BY_CODE.get(code)

    # Không có mã loại mà vẫn có mã cơ quan -> công văn (`3878/BGDĐT-PC`).
    return "Công văn" if org else None


# ============================================================
# TỔ CHỨC (§2.2)
# ============================================================

# Mã cơ quan trong số hiệu -> (tên đầy đủ, orgType theo enum §2.2).
_ORG_BY_CODE: dict[str, tuple[str, str]] = {
    "QH": ("Quốc hội", "quoc_hoi"),
    "QH13": ("Quốc hội", "quoc_hoi"),
    "QH14": ("Quốc hội", "quoc_hoi"),
    "QH15": ("Quốc hội", "quoc_hoi"),
    "UBTVQH": ("Ủy ban Thường vụ Quốc hội", "quoc_hoi"),
    "CTN": ("Chủ tịch nước", "quoc_hoi"),
    "CP": ("Chính phủ", "chinh_phu"),
    "TTG": ("Thủ tướng Chính phủ", "thu_tuong"),
    "BGDĐT": ("Bộ Giáo dục và Đào tạo", "bo_nganh"),
    "BTC": ("Bộ Tài chính", "bo_nganh"),
    "BNV": ("Bộ Nội vụ", "bo_nganh"),
    "BTTTT": ("Bộ Thông tin và Truyền thông", "bo_nganh"),
    "BKHCN": ("Bộ Khoa học và Công nghệ", "bo_nganh"),
    "BLĐTBXH": ("Bộ Lao động - Thương binh và Xã hội", "bo_nganh"),
    "BTP": ("Bộ Tư pháp", "bo_nganh"),
    "BYT": ("Bộ Y tế", "bo_nganh"),
    "BQP": ("Bộ Quốc phòng", "bo_nganh"),
    "BCA": ("Bộ Công an", "bo_nganh"),
    "BXD": ("Bộ Xây dựng", "bo_nganh"),
    "BKHĐT": ("Bộ Kế hoạch và Đầu tư", "bo_nganh"),
    "TTCP": ("Thanh tra Chính phủ", "bo_nganh"),
    "ĐHĐN": ("Đại học Đà Nẵng", "dai_hoc_vung"),
    "ĐHBK": ("Trường Đại học Bách khoa", "truong_thanh_vien"),
    "HĐĐH": ("Hội đồng Đại học Đà Nẵng", "don_vi_truc_thuoc"),
    "HĐT": ("Hội đồng Trường Đại học Bách khoa", "don_vi_truc_thuoc"),
}

# Tên cơ quan trong metadata -> orgType. Metadata là nguồn chuẩn khi có, bảng
# mã trên chỉ dùng cho stub và file lạc.
_ORG_TYPE_BY_NAME: dict[str, str] = {
    "Quốc hội": "quoc_hoi",
    "Ủy ban Thường vụ Quốc hội": "quoc_hoi",
    "Chủ tịch nước": "quoc_hoi",
    "Chính phủ": "chinh_phu",
    "Thủ tướng Chính phủ": "thu_tuong",
    "Thanh tra chính phủ": "bo_nganh",
    "Thanh tra Chính phủ": "bo_nganh",
    "Đại học Đà Nẵng": "dai_hoc_vung",
    "Trường Đại học Bách khoa": "truong_thanh_vien",
    "Hội đồng Đại học Đà Nẵng": "don_vi_truc_thuoc",
    "Hội đồng Trường Đại học Bách khoa": "don_vi_truc_thuoc",
    "Thành phố Đà Nẵng": "bo_nganh",
}

# Cây PART_OF (§4). Chỉ khai cạnh trực tiếp, đường đi nhiều bậc để Cypher lo.
_PARENT: dict[str, str] = {
    "Trường Đại học Bách khoa": "Đại học Đà Nẵng",
    "Hội đồng Trường Đại học Bách khoa": "Trường Đại học Bách khoa",
    "Hội đồng Đại học Đà Nẵng": "Đại học Đà Nẵng",
    "Đại học Đà Nẵng": "Bộ Giáo dục và Đào tạo",
    "Thủ tướng Chính phủ": "Chính phủ",
}

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")

# Chính quyền địa phương: có trong kho (`104/KH-UBND` của Thành phố Đà Nẵng)
# nhưng bảng §3 không có bậc nào cho nó — §3 chỉ đi theo trục trung ương ->
# đại học vùng -> trường. Nhận diện riêng để đánh dấu "suy rộng".
_LOCAL_GOV_PREFIX = ("thanh pho", "uy ban nhan dan", "ubnd", "so ", "tinh ")


def org_id(name: str) -> str:
    """`Bộ Giáo dục và Đào tạo` -> `bo_giao_duc_va_dao_tao`."""

    return _SLUG_STRIP.sub("_", deaccent(name).lower()).strip("_")


def is_local_gov(name: str) -> bool:
    """Cơ quan chính quyền địa phương (UBND tỉnh/thành, sở)?"""

    return deaccent(name).lower().startswith(_LOCAL_GOV_PREFIX)


def org_type(name: str) -> str:
    """orgType theo enum §2.2. Bộ nào chưa khai tên thì vẫn ra `bo_nganh`."""

    if name in _ORG_TYPE_BY_NAME:
        return _ORG_TYPE_BY_NAME[name]

    flat = deaccent(name).lower()

    if flat.startswith("bo "):
        return "bo_nganh"

    if flat.startswith("truong "):
        return "truong_thanh_vien"

    if flat.startswith(("phong ", "ban ", "khoa ", "trung tam ", "vien ")):
        return "phong_ban"

    return "don_vi_truc_thuoc"


def org_parent(name: str) -> str | None:
    """Cơ quan cấp trên trực tiếp, hoặc None nếu là gốc."""

    if name in _PARENT:
        return _PARENT[name]

    # Mọi bộ ngành đều thuộc Chính phủ. Trừ Quốc hội / Chủ tịch nước — nhánh
    # quyền lực khác, không có cạnh PART_OF nào cả.
    return "Chính phủ" if org_type(name) == "bo_nganh" else None


def org_from_so_hieu(norm: str) -> tuple[str, str] | None:
    """(tên cơ quan, orgType) suy từ đuôi số hiệu. None nếu không nhận ra."""

    _, _, _, org_code = split_so_hieu(norm)

    if not org_code:
        return None

    if org_code in _ORG_BY_CODE:
        return _ORG_BY_CODE[org_code]

    # `BGDĐT-PC` = Bộ GD&ĐT, vụ Pháp chế. Cơ quan ban hành là cái đứng đầu.
    return _ORG_BY_CODE.get(org_code.split("-")[0])


# ============================================================
# AUTHORITY_LEVEL (§3)
# ============================================================

# Bảng §3 trộn hai tiêu chí: 4 bậc trên xét theo LOẠI văn bản, 2 bậc dưới xét
# theo CƠ QUAN. Với kho này phải lấy cơ quan làm chính — 252/501 văn bản mang
# loại "Quyết định, Quy định" nhưng do đủ mọi cấp ban hành, từ Thủ tướng xuống
# tới trường. Xét theo loại thì cả 252 cái rơi chung một bậc, vô nghĩa.
_LEVEL_BY_ORG_TYPE = {
    "quoc_hoi": 5,
    "chinh_phu": 4,
    "thu_tuong": 3,
    "bo_nganh": 3,
    "dai_hoc_vung": 2,
    "truong_thanh_vien": 1,
}

_LEVEL_BY_TYPE = {
    "Hiến pháp": 6,
    "Luật": 5,
    "Pháp lệnh": 5,
    "Nghị định": 4,
    "Thông tư": 3,
    "Thông tư liên tịch": 3,
}


def authority_level(
    doc_type: str | None,
    org_name: str | None,
) -> tuple[int | None, str]:
    """
    Bậc thẩm quyền theo §3. Trả về (bậc, ghi chú nguồn suy ra).

    Ghi chú được lưu cùng node: bảng §3 không phủ hết loại văn bản có thật
    trong kho (Công văn, Kế hoạch, Nghị quyết, văn bản UBND thành phố), nên
    phải phân biệt được bậc nào tra thẳng từ ontology, bậc nào là suy rộng.
    """

    if doc_type == "Hiến pháp":
        return 6, "onto"

    if org_name:
        kind = org_type(org_name)

        # Đơn vị trực thuộc (hội đồng trường, phòng ban) không có bậc riêng
        # trong §3 — cho bằng bậc của cơ quan mẹ.
        if kind in ("don_vi_truc_thuoc", "phong_ban"):
            parent = org_parent(org_name)
            level = _LEVEL_BY_ORG_TYPE.get(org_type(parent)) if parent else None

            if level:
                return level, "suy-rong: don-vi-truc-thuoc"

        level = _LEVEL_BY_ORG_TYPE.get(kind)

        if level:
            # UBND / sở địa phương bị xếp tạm vào `bo_nganh` cho có bậc, nhưng
            # chúng không nằm trong bảng §3 — phải nói rõ để còn kiểm lại.
            if is_local_gov(org_name):
                return level, "suy-rong: chinh-quyen-dia-phuong"

            return level, "onto"

    level = _LEVEL_BY_TYPE.get(doc_type or "")

    if level:
        return level, "onto: theo-loai"

    return None, "khong-suy-duoc"


# ============================================================
# NGÀY THÁNG + TÌNH TRẠNG HIỆU LỰC (§2.1)
# ============================================================

_DATE_VN = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")

STATUS_CON = "CON_HIEU_LUC"
STATUS_HET = "HET_HIEU_LUC"
STATUS_CHUA = "CHUA_HIEU_LUC"


def parse_date(raw: str | None) -> str | None:
    """`14/11/2018` -> `2018-11-14`. Không đọc được thì None."""

    if not raw:
        return None

    match = _DATE_VN.search(str(raw).strip())

    if not match:
        return None

    day, month, year = (int(match.group(i)) for i in (1, 2, 3))

    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_status(
    tinh_trang: str | None,
    effective_date: str | None = None,
    today: date | None = None,
) -> tuple[str | None, str | None, str]:
    """
    Đọc `tinh_trang` của crawler thành (status, expiryDate, ghi chú).

    Crawler nhét luôn ngày hết hiệu lực vào chuỗi: `"Hết hiệu lực 01/01/2024"`.
    §2.1 tách thành hai thuộc tính riêng nên phải bóc ra ở đây.

    `CHUA_HIEU_LUC` không có trong metadata — crawler chỉ biết còn/hết. Suy ra
    bằng cách so ngày hiệu lực với hôm nay: kho có văn bản đề năm 2026 nên
    trạng thái này là thật, không phải trường hợp lý thuyết.
    """

    text = (tinh_trang or "").strip()
    flat = deaccent(text).lower()
    today = today or date.today()

    if not text:
        return None, None, "thieu-tinh-trang"

    if flat.startswith("het hieu luc"):
        return STATUS_HET, parse_date(text), ""

    if flat.startswith("con hieu luc"):
        if effective_date and effective_date > today.isoformat():
            return STATUS_CHUA, None, "chua-den-ngay-hieu-luc"

        return STATUS_CON, None, ""

    return None, None, f"tinh-trang-la: {text[:40]}"


# ============================================================
# LOẠI VĂN BẢN + NORMATIVE CONTENT (§2.6)
# ============================================================

# Loại nội dung mà một Quyết định "ban hành kèm theo". Đây chính là node
# `NormativeContent` của §2.6 — 252/501 văn bản trong kho có dạng này.
NORMATIVE_TYPES = ("Quy định", "Quy chế", "Điều lệ", "Đề án", "Kế hoạch", "Hướng dẫn")

# Nhãn gộp nhóm của crawler, không phải loại văn bản thật. `"Luật, Pháp lệnh"`
# nghĩa là "Luật HOẶC Pháp lệnh" — 50 văn bản dùng chung nhãn này, phải nhìn số
# hiệu mới biết cái nào là cái nào (`100/2015/QH13` -> Luật).
GROUP_LABELS = frozenset({"Luật, Pháp lệnh"})


def split_loai(loai: str | None) -> tuple[str | None, str | None]:
    """
    `"Quyết định, Quy định"` -> ("Quyết định", "Quy định").

    Chỉ tách khi vế sau là một loại nội dung quy phạm. Nhãn `"Luật, Pháp lệnh"`
    trông y hệt về cú pháp nhưng là **tên nhóm** của crawler ("Luật hoặc Pháp
    lệnh") chứ không phải "Luật ban hành Pháp lệnh" — tách ra là sai.
    """

    if not loai:
        return None, None

    text = loai.strip()

    if "," not in text:
        return text, None

    head, tail = (part.strip() for part in text.split(",", 1))

    if tail in NORMATIVE_TYPES:
        return head, tail

    return text, None
