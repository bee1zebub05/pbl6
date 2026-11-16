"""Don rac con sot trong cac file .txt o clean_data.

Go 3 thu Gemini hay them vao ma ta khong muon co trong du lieu:
  1. Cau dan  "Duoi day la toan bo noi dung..."  o dau
  2. Rao markdown  ```text ... ```
  3. Vo boc Python  text_content = \"\"\" ... \"\"\"  (khi Gemini viet code ghi file)

Mac dinh CHI XEM TRUOC, khong ghi de. Them --apply moi that su sua file.

Chay:
    python don_dep_clean.py --only "pdf/Khac"          # xem truoc
    python don_dep_clean.py --only "pdf/Khac" --apply  # sua that
"""
import argparse
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FENCE_DONG = re.compile(r"```[a-zA-Z]*[ \t]*\r?\n([\s\S]*?)```")
FENCE_MO = re.compile(r"```[a-zA-Z]*[ \t]*\r?\n")
BA_NHAY = re.compile(r'("""|\'\'\')([\s\S]*?)\1')
CAU_DAN = re.compile(
    r"^(chắc chắn|dưới đây|đây là|sure|here is|here'?s)[^\n]{0,200}\n+", re.I)
MA_NGUON = re.compile(
    r'^\s*(#\s|import\s|from\s+\w+\s+import|def\s|with\s+open|print\(|[a-z_]+\s*=\s*("""|\'\'\'|f?"))',
    re.M)


def lam_sach(t):
    """Tra ve (text_da_sach, danh_sach_viec_da_lam)."""
    viec = []

    # 1) rao markdown dong day du -> lay khoi dai nhat
    khoi = [m.group(1) for m in FENCE_DONG.finditer(t)]
    if khoi:
        dai = max(khoi, key=len)
        if len(dai) > 200:
            t = dai.strip()
            viec.append("bóc rào ```")
    elif "```" in t:
        m = FENCE_MO.search(t)
        if m:
            sau = re.sub(r"```[\s\S]*$", "", t[m.end():]).strip()
            if len(sau) > 200:
                t = sau
                viec.append("bóc rào ``` (thiếu rào đóng)")

    # 2) vo boc Python
    if MA_NGUON.search(t[:400]):
        chuoi = [m.group(2) for m in BA_NHAY.finditer(t)]
        lay = max(chuoi, key=len) if chuoi else ""
        if len(lay) <= 200:
            m = re.search(r'"""|\'\'\'', t)
            lay = t[m.end():] if m else ""
        if len(lay) > 200:
            t = lay.strip()
            viec.append("bóc chuỗi Python")

    # 3) cau dan con sot
    moi = CAU_DAN.sub("", t, count=1)
    if moi != t:
        t = moi
        viec.append("cắt câu dẫn")

    t = t.strip() + "\n"
    return t, viec


def main():
    # __file__ = <goc>/project/gemini_ocr/don_dep_clean.py
    # parents[0]=gemini_ocr, parents[1]=project, parents[2]=<goc>  <- can cai nay
    root = Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(root / "data" / "clean_data"))
    ap.add_argument("--only", default="")
    ap.add_argument("--apply", action="store_true", help="ghi de that su (mac dinh chi xem truoc)")
    a = ap.parse_args()

    out = Path(a.out)
    only = a.only.replace("\\", "/").strip("/")
    n_doi = n_xem = 0

    for f in sorted(out.rglob("*.txt")):
        rel = f.relative_to(out).as_posix()
        if only and not rel.startswith(only):
            continue
        n_xem += 1
        goc = f.read_text(encoding="utf-8", errors="replace")
        moi, viec = lam_sach(goc)
        if not viec or moi == goc:
            print("  giữ nguyên  %s" % rel[-60:])
            continue
        n_doi += 1
        print("  SỬA        %s" % rel[-60:])
        print("             %s | %d -> %d ký tự" % (", ".join(viec), len(goc), len(moi)))
        print("             đầu: %s" % moi[:70].replace("\n", " ⏎ "))
        if a.apply:
            f.write_text(moi, encoding="utf-8", newline="\n")

    print("-" * 70)
    if a.apply:
        print("Đã sửa %d/%d file." % (n_doi, n_xem))
    else:
        print("Xem trước: %d/%d file sẽ đổi. Thêm --apply để ghi thật." % (n_doi, n_xem))


if __name__ == "__main__":
    main()
