# -*- coding: utf-8 -*-
"""Chay khong nguoi truc: doi OCR xong -> va -> nhap -> dung lai do thi -> bao cao -> tat may.

Chay khi nguoi dung di ngu. Moi buoc deu ghi vao BAO CAO de sang hom sau doc lai duoc
toan bo dien bien, ke ca khi co buoc that bai.

NGUYEN TAC AN TOAN:
  - Moi buoc boc trong try/except. Mot buoc hong KHONG lam chet ca chuoi, va bao cao
    van duoc ghi ra.
  - Chi tat may khi da ghi xong bao cao.
  - Co --khong-tat de chay thu ma khong tat may.
  - Neu OCR chua xong sau HAN_CHO gio thi bo qua, lam tiep cac buoc con lai voi phan
    da co — thu duoc bao nhieu dung bay nhieu, hon la mat trang mot dem.

    python chay_dem.py                 # chay that, xong thi tat may
    python chay_dem.py --khong-tat     # lam het cac buoc nhung KHONG tat may
    python chay_dem.py --hoan 120      # doi bao nhieu giay truoc khi tat (mac dinh 120)
"""
import argparse
import io
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DAY = Path(__file__).resolve().parent
GOC = DAY.parents[1]
VIZ = GOC / "project" / "viz"
PY_VIZ = GOC / "project" / "viz_env" / "Scripts" / "python.exe"
MOI = GOC / "data" / "processed" / "text_gemma_moi"
LOG_OCR = DAY / "ocr_full.log"
BAO_CAO = GOC / "BAO_CAO_DEM.md"

# Han cho MAC DINH 8 tieng la qua ngan cho dot 219 file nang: do that mat hon 10
# tieng. Dat --han de chinh khi biet truoc khoi luong.
HAN_CHO_GIO = 8          # doi OCR toi da bao nhieu gio (doi duoc bang --han)


def ghi(dong, mo="a"):
    with io.open(BAO_CAO, mo, encoding="utf-8", newline="\n") as f:
        f.write(dong + "\n")
    print(dong, flush=True)


def chay(lenh, ten, python=None):
    """Chay mot lenh, tra ve (thanh cong, dau ra). Khong nem loi ra ngoai."""
    exe = str(python or sys.executable)
    try:
        r = subprocess.run([exe, "-B"] + lenh, cwd=str(DAY if python is None else VIZ),
                           capture_output=True, timeout=3 * 3600)
        out = r.stdout.decode("utf-8", errors="replace")
        err = r.stderr.decode("utf-8", errors="replace")
        ok = r.returncode == 0
        if not ok:
            out += "\n[stderr]\n" + err[-1500:]
        return ok, out
    except Exception as e:
        return False, "KHÔNG CHẠY ĐƯỢC: %s" % e


def ocr_con_chay():
    """Tien trinh OCR con song khong.

    PHAI boc trong @(...): Where-Object tra ve SCALAR khi chi khop 1 phan tu, luc do
    .Count khong co gia tri va ham nay bao nham la 'da chet' — da do that, suyt bo qua
    ca buoc doi trong khi OCR van dang chay.
    """
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "@(Get-WmiObject Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -like '*ocr_lai_file_nat*' }).Count"],
            capture_output=True, timeout=60)
        return int((r.stdout.decode(errors="replace").strip() or "0")) > 0
    except Exception:
        return True          # khong biet thi coi nhu CON chay, cho tiep cho an toan


def so_file():
    try:
        return len(list(MOI.rglob("*.txt")))
    except Exception:
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--khong-tat", action="store_true")
    ap.add_argument("--hoan", type=int, default=120)
    ap.add_argument("--han", type=float, default=HAN_CHO_GIO,
                    help="đợi OCR tối đa bao nhiêu giờ")
    a = ap.parse_args()

    t0 = time.time()
    ghi("# Báo cáo chạy đêm", "w")
    ghi("")
    ghi("Bắt đầu: **%s**" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    ghi("")

    # ── 1. đợi OCR xong ──
    ghi("## 1. Đợi OCR chạy xong")
    ghi("")
    n0 = so_file()
    ghi("- Lúc bắt đầu đợi: **%d file** đã OCR" % n0)
    han = time.time() + a.han * 3600
    lan_cuoi = n0
    dung_yen = 0
    while time.time() < han:
        if not ocr_con_chay():
            ghi("- Tiến trình OCR đã kết thúc lúc %s"
                % datetime.now().strftime("%H:%M:%S"))
            break
        n = so_file()
        if n == lan_cuoi:
            dung_yen += 1
            # 40 lan x 90s = 1 gio khong nhich -> coi nhu treo, di tiep
            if dung_yen >= 40:
                ghi("- ⚠ Đứng yên ở %d file suốt 1 tiếng — coi như treo, đi tiếp." % n)
                break
        else:
            dung_yen = 0
            lan_cuoi = n
        time.sleep(90)
    else:
        ghi("- ⚠ Quá %.1f tiếng vẫn chưa xong — đi tiếp với phần đã có." % a.han)

    n1 = so_file()
    ghi("- Kết thúc bước này: **%d file** (thêm %d file trong đêm)" % (n1, n1 - n0))
    ghi("")

    # ── 2. vá khúc hỏng ──
    ghi("## 2. Vá những khúc bị hỏng")
    ghi("")
    ok, out = chay(["va_khuc_hong.py", "--thu-muc",
                    "data/processed/text_gemma_moi", "--apply"], "vá khúc")
    ghi("```")
    ghi("\n".join(x for x in out.splitlines()
                  if x.strip() and not x.startswith("Direct use"))[-2200:])
    ghi("```")
    ghi("")

    # ── 3. nhập vào bản sạch qua cổng kiểm định ──
    ghi("## 3. Nhập vào text_clean_gemma (qua cổng kiểm định)")
    ghi("")
    ok, out = chay(["nhap_ban_moi.py", "--apply"], "nhập")
    ghi("```")
    ghi("\n".join(x for x in out.splitlines() if x.strip())[-2800:])
    ghi("```")
    ghi("")

    # ── 4. dựng lại đồ thị + Cypher ──
    ghi("## 4. Dựng lại đồ thị tri thức")
    ghi("")
    ok, out = chay(["trich_do_thi.py"], "đồ thị")
    ghi("```")
    ghi("\n".join(x for x in out.splitlines() if x.strip())[-1800:])
    ghi("```")
    ok2, out2 = chay(["xuat_neo4j.py", "--ra",
                      str(GOC / "data" / "do_thi" / "do_thi_dut.cql")],
                     "cypher", python=PY_VIZ)
    ghi("```")
    ghi("\n".join(x for x in out2.splitlines() if x.strip())[-900:])
    ghi("```")
    ghi("")

    # ── 5. kiểm chứng chất lượng ──
    ghi("## 5. Kiểm chứng chất lượng bản cuối")
    ghi("")
    ok, out = chay(["kiem_chung_ban_sach.py"], "kiểm chứng")
    ghi("```")
    ghi("\n".join(x for x in out.splitlines() if x.strip())[-3000:])
    ghi("```")
    ghi("")

    # ── 6. thống kê các trường thông tin ──
    ghi("## 6. Độ phủ từng trường thông tin")
    ghi("")
    ma = (
        "import json,sys,io\n"
        "sys.stdout.reconfigure(encoding='utf-8',errors='replace')\n"
        "d=json.load(io.open(r'%s',encoding='utf-8'))['van_ban']\n"
        "n=len(d)\n"
        "for ten,k in (('Số hiệu','so_hieu'),('Trích yếu','tieu_de'),"
        "('Loại văn bản','ten_loai'),('Đơn vị ban hành','ten_co_quan'),"
        "('Lĩnh vực','linh_vuc'),('Ngày ban hành','ngay'),('Người ký','nguoi_ky'),"
        "('Căn cứ pháp lý','can_cu'),('Đối tượng áp dụng','doi_tuong'),"
        "('Đơn vị liên quan','don_vi')):\n"
        "    c=sum(1 for v in d.values() if v.get(k))\n"
        "    print('| %%s | %%d / %%d | %%.0f%%%% |'%%(ten,c,n,100.0*c/n))\n"
        % (GOC / "data" / "do_thi" / "do_thi.json")
    )
    ok, out = chay(["-c", ma], "trường")
    ghi("| trường | có | phủ |")
    ghi("|---|---|---|")
    ghi("\n".join(x for x in out.splitlines() if x.startswith("|")))
    ghi("")

    # ── 7. node cô đơn ──
    ghi("## 7. Node cô đơn trong đồ thị")
    ghi("")
    ma2 = (
        "import sys;sys.path.insert(0,'.');sys.stdout.reconfigure("
        "encoding='utf-8',errors='replace')\n"
        "from do_thi_lib import nap\n"
        "G,t=nap(3)\n"
        "tr=[n for n,x in G.nodes(data=True) if not x['ngoai_bo']]\n"
        "cd=[n for n in tr if G.degree(n)==0]\n"
        "print('- Văn bản: **%d**'%len(tr))\n"
        "print('- Quan hệ CĂN_CỨ/THAY_THẾ: **%d**'%t['so_canh'])\n"
        "print('- Node cô đơn: **%d** (%.0f%%)'%(len(cd),100.0*len(cd)/len(tr)))\n"
    )
    ok, out = chay(["-c", ma2], "cô đơn", python=PY_VIZ)
    ghi("\n".join(x for x in out.splitlines() if x.strip()))
    ghi("")

    phut = (time.time() - t0) / 60
    ghi("---")
    ghi("")
    ghi("Kết thúc: **%s** — chạy %d phút %d giây"
        % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), phut, (phut % 1) * 60))
    ghi("")
    ghi("Bản dữ liệu cuối: `data/processed/text_clean_gemma`")
    ghi("Cypher cho Neo4j: `data/do_thi/do_thi_dut.cql`")
    ghi("Xem đồ thị: nháy đúp `chay_viz.bat`")

    if a.khong_tat:
        ghi("")
        ghi("*(chạy với --khong-tat nên KHÔNG tắt máy)*")
        return

    ghi("")
    ghi("Máy sẽ tắt sau %d giây. Huỷ bằng: `shutdown /a`" % a.hoan)
    try:
        subprocess.run(["shutdown", "/s", "/t", str(a.hoan),
                        "/c", "Xong OCR - xem BAO_CAO_DEM.md"], timeout=60)
    except Exception as e:
        ghi("Không hẹn tắt máy được: %s" % e)


if __name__ == "__main__":
    main()
