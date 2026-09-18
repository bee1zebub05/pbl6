"""
Cứu những trang bị `RECITATION` chặn, bằng cách cắt trang thành 4 góc.

    python scripts/cuu_trang_recitation.py                    # xem trước
    python scripts/cuu_trang_recitation.py --apply
    python scripts/cuu_trang_recitation.py --nguon data/clean/text_gemma_moi --apply

Quét thư mục text tìm dấu `[[KHÔNG OCR ĐƯỢC TRANG a-b]]`, cắt đúng những trang đó
ra khỏi PDF gốc, chia mỗi trang thành 4 góc rồi OCR từng góc.

VÌ SAO PHẢI CẮT NHỎ TỚI MỨC NÀY — xem `docs/recitation.md` cho phần chẩn đoán.

Tóm tắt phần đo được trên 11 trang cuối cùng của kho, sau khi chúng đã trụ qua ba
lượt vá thông thường:

    4 model × cả file / từng trang, 3 lượt        -> trượt
    2 dạng gửi × 3 prompt × 4 model = 24 tổ hợp   -> trượt
    text layer sẵn có                             -> 0/11 dùng được, 7-8% dấu
    cắt 4 và 6 dải ngang                          -> phần lớn ClientError
    CẮT 2×2                                       -> 10/10 chỗ

Nguyên tắc vẫn là chia nhỏ — thứ đã cứu 68/78 chỗ khi hạ từ cả file xuống từng
trang — chỉ đẩy thêm một nấc xuống dưới mức trang. Một góc bảng không còn là "trang
tài liệu hoàn chỉnh" nên không còn khớp với cái model đã thuộc.

HAI ĐIỀU PHẢI BIẾT TRƯỚC KHI DÙNG

1. Cắt 2×2 xé đôi bảng theo chiều dọc, nên một hàng bảng bị tách làm hai mảnh. Đã
   thử giữ nguyên hàng bằng cách cắt dải ngang nhưng API từ chối ảnh quá dẹt. Vì
   vậy mỗi mảnh được DÁN NHÃN vị trí trong kết quả — người đọc sau không hiểu nhầm
   là văn bản liền mạch.

2. Prompt ở đây nói về ẢNH, không nói "đọc tài liệu này ra". Cụm sau chính là thứ
   bộ lọc recitation canh.
"""

from __future__ import annotations

import argparse
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vanban.core import config  # noqa: E402
from vanban.clean.key_pool import KeyPool, NoKeyAvailable  # noqa: E402

MOC = re.compile(r"\[\[KHÔNG OCR ĐƯỢC TRANG ([\d,\s-]+)\]\]")

PROMPT = ("Chuyển chữ trong ảnh này thành văn bản thuần, giữ nguyên dấu tiếng Việt. "
          "Chỉ xuất phần chữ đọc được.")

# Thứ tự Flash trước cho nhanh; RECITATION trả về rỗng NGAY nên đặt trước không tốn giờ.
MODELS = ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
          "gemma-4-31b-it", "gemma-4-26b-a4b-it")

VI_TRI = ("trên-trái", "trên-phải", "dưới-trái", "dưới-phải")
DPI = 200
TOI_THIEU = 40          # mảnh dưới ngưỡng này coi như không đọc được gì
LUOT_MOI_MODEL = 3      # ClientError hay xảy ra một cách ngẫu nhiên -> phải thử lại


def cac_trang(s: str) -> list[int]:
    ra: list[int] = []

    for phan in s.split(","):
        phan = phan.strip()

        if "-" in phan:
            a, b = phan.split("-", 1)

            if a.strip().isdigit() and b.strip().isdigit():
                ra += list(range(int(a), int(b) + 1))
        elif phan.isdigit():
            ra.append(int(phan))

    return ra


def chi_muc_pdf(raw: Path) -> dict[str, Path]:
    ix: dict[str, Path] = {}

    for f in sorted(raw.rglob("*.pdf")):
        k = f.name[:4]

        if k not in ix or f.relative_to(raw).as_posix().startswith("pdf/"):
            ix[k] = f

    return ix


def bon_goc(pdf: Path, trang: int) -> list[bytes]:
    """Trang -> 4 ảnh PNG: trên-trái, trên-phải, dưới-trái, dưới-phải."""

    import pymupdf

    with pymupdf.open(pdf) as d:
        pg = d[trang - 1]
        r = pg.rect
        ra = []

        for i in range(2):
            for j in range(2):
                o = pymupdf.Rect(
                    r.x0 + j * r.width / 2, r.y0 + i * r.height / 2,
                    r.x0 + (j + 1) * r.width / 2, r.y0 + (i + 1) * r.height / 2,
                )
                ra.append(pg.get_pixmap(dpi=DPI, clip=o).tobytes("png"))

    return ra


def ocr_goc(pool: KeyPool, png: bytes) -> tuple[str, str]:
    """Thử lần lượt các model cho MỘT góc. -> (text, model) hoặc ('', lý do)."""

    from google.genai import types

    ly = "chưa thử"

    for model in MODELS:
        for _ in range(LUOT_MOI_MODEL):
            try:
                state = pool.acquire(timeout=120)
            except NoKeyAvailable:
                return "", "hết key dùng được"

            try:
                r = pool.client_for(state).models.generate_content(
                    model=model,
                    contents=[
                        types.Part.from_bytes(data=png, mime_type="image/png"),
                        PROMPT,
                    ],
                    config=types.GenerateContentConfig(temperature=0.0),
                )
            except Exception as exc:
                pool.report_transient(state)
                ly = "%s: %s" % (model.split("-")[1], type(exc).__name__[:12])
                continue

            pool.report_ok(state)
            t = (r.text or "").strip()
            kt = (str(r.candidates[0].finish_reason) if r.candidates else "?")
            kt = kt.replace("FinishReason.", "")

            if len(t) >= TOI_THIEU:
                return t, model

            ly = "%s: %s(%d)" % (model.split("-")[1], kt[:4], len(t))

            # Thử lại y hệt khi bị chặn là vô ích — đổi model.
            if kt == "RECITATION":
                break

    return "", ly


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nguon", default="data/clean/text_gemma_moi")
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--song-song", type=int, default=6)
    args = ap.parse_args()

    try:
        import pymupdf  # noqa: F401
    except ImportError:
        print("Thiếu pymupdf.  pip install pymupdf")

        return 1

    nguon = Path(args.nguon)
    nguon = nguon if nguon.is_absolute() else ROOT / nguon
    raw = Path(args.raw)
    raw = raw if raw.is_absolute() else ROOT / raw

    viec = []

    for f in sorted(nguon.rglob("*.txt")):
        t = f.read_text(encoding="utf-8", errors="replace")

        for m in MOC.finditer(t):
            tr = cac_trang(m.group(1))

            if tr:
                viec.append({"file": f, "moc": m.group(0), "trang": tr,
                             "doc": f.name[:4]})

    print("=" * 80)
    print("CỨU TRANG BỊ RECITATION CHẶN — cắt 2×2")
    print("=" * 80)

    if not viec:
        print("  Không còn chỗ nào hỏng.")

        return 0

    print("  %d chỗ, %d trang, trên %d văn bản"
          % (len(viec), sum(len(v["trang"]) for v in viec),
             len({v["doc"] for v in viec})))
    print("-" * 80)

    if not args.apply:
        for v in viec:
            print("  %s  trang %s" % (v["doc"], ", ".join(map(str, v["trang"]))))

        print("-" * 80)
        print(">>> Mới là XEM TRƯỚC. Thêm --apply để OCR lại và vá vào.")

        return 0

    ix = chi_muc_pdf(raw)
    pool = KeyPool()
    khoa = threading.Lock()
    dem = {"cuu": 0}

    def lam(v):
        log = []
        pdf = ix.get(v["doc"])

        if not pdf:
            return v, ["      ✖ không thấy PDF gốc"], False

        phan = []

        for tr in v["trang"]:
            mieng = []

            for i, png in enumerate(bon_goc(pdf, tr)):
                s, ghi = ocr_goc(pool, png)

                if s:
                    mieng.append("[Trang %d — góc %s]\n%s" % (tr, VI_TRI[i], s))
                    log.append("      t%d %-10s %5d ký tự [%s]"
                               % (tr, VI_TRI[i], len(s), ghi))
                else:
                    log.append("      t%d %-10s ✖ %s" % (tr, VI_TRI[i], ghi))

            if mieng:
                phan.append("\n\n".join(mieng))

        if not phan:
            return v, log + ["      ✖ không cứu được"], False

        moi = "\n\n".join(phan)
        thieu = len(v["trang"]) - len(phan)

        if thieu:
            moi += "\n\n[[KHÔNG OCR ĐƯỢC %d TRANG]]" % thieu

        # Ghi file phải tuần tự: hai chỗ của CÙNG một văn bản ghi vào cùng một file,
        # không khoá thì bản ghi sau đọc phải nội dung cũ và xoá mất bản vá trước.
        with khoa:
            noi = v["file"].read_text(encoding="utf-8", errors="replace")

            if v["moc"] not in noi:
                return v, log + ["      ✖ không thấy dấu trong file"], False

            v["file"].write_text(noi.replace(v["moc"], moi, 1),
                                 encoding="utf-8", newline="\n")

        return v, log + ["      ✔ đã vá (%d ký tự)" % len(moi)], True

    with ThreadPoolExecutor(max_workers=args.song_song) as bom:
        for v, log, ok in bom.map(lam, viec):
            dem["cuu"] += ok
            print("  ▸ %s trang %s" % (v["doc"], ", ".join(map(str, v["trang"]))))

            for d in log:
                print(d)

            sys.stdout.flush()

    print("-" * 80)
    print("Vá được %d / %d chỗ" % (dem["cuu"], len(viec)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
