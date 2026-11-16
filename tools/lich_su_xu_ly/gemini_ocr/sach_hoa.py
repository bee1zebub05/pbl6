# -*- coding: utf-8 -*-
"""Lam sach + kiem dinh text OCR truoc khi ghi vao clean_data.

Dung chung boi bridge.py (lam sach ngay luc ghi) va don_dep_clean.py (don file da ghi).
De o mot cho de hai ben khong bao gio lech logic.

Gemini tra ve khong nhat quan - cung 1 prompt co the ra 3 kieu:
  1. van ban thuan                                  -> giu nguyen
  2. markdown: cau dan + ```text ... ```            -> boc rao
  3. code Python: text_content = \"\"\" ... \"\"\"  -> boc chuoi ba nhay
"""
import re

FENCE_DONG = re.compile(r"```[a-zA-Z]*[ \t]*\r?\n([\s\S]*?)```")
FENCE_MO = re.compile(r"```[a-zA-Z]*[ \t]*\r?\n")
BA_NHAY = re.compile(r'("""|\'\'\')([\s\S]*?)\1')
CAU_DAN = re.compile(r"^(chắc chắn|dưới đây|đây là|sure|here is|here'?s)[^\n]{0,200}\n+", re.I)
MA_NGUON = re.compile(
    r'^\s*(#\s|import\s|from\s+\w+\s+import|def\s|with\s+open|print\(|[a-z_]+\s*=\s*("""|\'\'\'|f?"))',
    re.M)
# Tieu de mo dau van ban hanh chinh VN - dau hieu day la NOI DUNG THAT
DAU_VAN_BAN = re.compile(
    r"^(BỘ |CHÍNH PHỦ|CỘNG H[OÒ]À|QUỐC HỘI|ỦY BAN|THỦ TƯỚNG|NGHỊ ĐỊNH|QUYẾT ĐỊNH|"
    r"THÔNG TƯ|LUẬT|ĐẠI HỌC|TRƯỜNG |BAN |HỘI ĐỒNG)")

MIN_KY_TU = 200


def lam_sach(t):
    """-> (text_sach, [viec_da_lam])"""
    viec = []
    if not t:
        return "", ["rỗng"]

    # 1) rao markdown
    khoi = [m.group(1) for m in FENCE_DONG.finditer(t)]
    if khoi:
        dai = max(khoi, key=len)
        if len(dai) > MIN_KY_TU:
            t, _ = dai.strip(), viec.append("bóc rào ```")
    elif "```" in t:
        m = FENCE_MO.search(t)
        if m:
            sau = re.sub(r"```[\s\S]*$", "", t[m.end():]).strip()
            if len(sau) > MIN_KY_TU:
                t, _ = sau, viec.append("bóc rào ``` (thiếu rào đóng)")

    # 2) vo boc Python
    if MA_NGUON.search(t[:400]):
        chuoi = [m.group(2) for m in BA_NHAY.finditer(t)]
        lay = max(chuoi, key=len) if chuoi else ""
        if len(lay) <= MIN_KY_TU:
            # khong co nhay dong (Gemini hien khoi code bi cat cut) -> lay het phan sau dau mo
            m = re.search(r'"""|\'\'\'', t)
            lay = t[m.end():] if m else ""
        if len(lay) <= MIN_KY_TU:
            # chuoi 1 dong dung nhay don/kep, xuong dong viet dang \n
            m = re.search(r'=\s*"((?:[^"\\]|\\.){%d,})"' % MIN_KY_TU, t)
            lay = m.group(1) if m else ""
        if len(lay) > MIN_KY_TU:
            t, _ = lay.strip(), viec.append("bóc chuỗi Python")

    # 3) xuong dong dang escape (\n) con sot lai sau khi boc chuoi
    if "\\n" in t and t.count("\n") < t.count("\\n"):
        t, _ = t.replace("\\n", "\n").replace('\\"', '"').replace("\\'", "'"), \
               viec.append("đổi \\n thành xuống dòng thật")

    # 4) cau dan con sot
    moi = CAU_DAN.sub("", t, count=1)
    if moi != t:
        t, _ = moi, viec.append("cắt câu dẫn")

    # 5) rac o CUOI: rao dong con lai, dong "print(...)", "Ket qua chay ma..."
    truoc = t
    t = re.sub(r"\n*```[a-zA-Z]*\s*$", "", t)
    t = re.sub(r"\n\s*(print\(|filename\s*=|with\s+open\()[^\n]*$", "", t)
    t = re.sub(r"\n\s*(Kết quả chạy mã|File saved successfully)[^\n]*$", "", t, flags=re.I)
    if t != truoc:
        viec.append("cắt rác ở cuối")

    return t.strip() + "\n", viec


def kiem_dinh(t, so_trang=None, min_ky_tu=None):
    """Text co dat de ghi vao clean_data khong? -> (dat, ly_do_khong_dat).

    min_ky_tu: nguong rieng. Khi cham TUNG KHUC PDF phai ha nguong xuong — trang cuoi
    van ban thuong chi co phan ky ten (~150 ky tu), lay nguong 200 cua ca file la loai
    oan mot trang hop le roi mat luon noi dung do (da gap khi doi chieu 0383).
    """
    s = (t or "").strip()
    nguong = min_ky_tu if min_ky_tu is not None else MIN_KY_TU
    if len(s) < nguong:
        return False, "quá ngắn (%d ký tự, ngưỡng %d)" % (len(s), nguong)
    if MA_NGUON.search(s[:400]) and not DAU_VAN_BAN.match(s):
        return False, "vẫn là mã nguồn, không phải nội dung văn bản"
    if "```" in s[:200]:
        return False, "còn dấu rào markdown ở đầu"
    # Tai lieu nhieu trang ma qua it chu -> gan nhu chac chan bi cat giua chung
    if so_trang and so_trang >= 5 and len(s) / so_trang < 400:
        return False, "quá ít chữ so với %d trang (%.0f chữ/trang)" % (so_trang, len(s) / so_trang)
    return True, ""
