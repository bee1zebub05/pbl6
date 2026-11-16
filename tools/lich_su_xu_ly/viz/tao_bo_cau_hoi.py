# -*- coding: utf-8 -*-
"""Sinh BO CAU HOI DANH GIA cho thuc nghiem so sanh Do thi tri thuc voi BM25.

CANH BAO VE TINH VONG TRON — doc ky truoc khi dung:
    Script nay sinh DAP AN DE XUAT bang chinh do thi. Neu dem dap an do di cham diem
    cho do thi thi ket qua luon la 100% — vo nghia. Cot `dap_an_de_xuat` chi la BAN
    NHAP de nguoi doc do bot cong go tay; NGUOI LAM DE TAI PHAI DUYET va sua cot
    `dap_an_duyet` truoc khi chay danh_gia.py. Chi cot da duyet moi duoc tinh diem.

Ba muc do cau hoi, dung de cho thay do thi hon BM25 o dau:

    A. TU KHOA      — BM25 lam tot. Dung lam moc: neu do thi thua o day thi co van de.
    B. DA LOP       — loc dong thoi linh vuc + doi tuong + cap ban hanh. BM25 chi so
                      khop chu, khong hieu "danh cho sinh vien" la mot thuoc tinh.
    C. BAC CAU      — "van ban nao phai ra lai neu X het hieu luc". Phai DI THEO CANH
                      cua do thi, BM25 khong the tra loi. Day la luan diem cua bai bao.

    python tao_bo_cau_hoi.py              # xem truoc
    python tao_bo_cau_hoi.py --ra bo_cau_hoi.csv
"""
import argparse
import csv
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from do_thi_lib import CAP_TEN, HIEU_LUC, doc_van_ban, nap        # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOC = Path(__file__).resolve().parents[2]


def bo_dau(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D").lower()


def muc_A(G, trong, doc_text=None):
    """Cau hoi TU KHOA.

    UNG VIEN gom HAI nguon, KHONG chi tieu de:
        (1) cum tu xuat hien trong TIEU DE
        (2) cum tu xuat hien >= NGUONG_NHAC lan trong TOAN VAN

    Chi lay tieu de la thieu nghiem trong, va thieu theo huong LAM HAI BM25: cau
    "hoc bong" chi ra 3 van ban theo tieu de, trong khi Nghi dinh 84/2020 nhac 68 lan
    va Nghi dinh 86/2021 nhac 48 lan lai khong co trong dap an. BM25 tim tren toan van
    se tra ve dung hai van ban do roi bi cham la SAI — cham oan, va bai bao se bi
    phan bien ngay o cho nay.

    Gop ca hai nguon cho danh sach RONG hon can thiet: gach bot mot ung vien thua thi
    de, con nho ra mot van ban bi sot thi rat kho.
    """
    tu_khoa = [
        "quy chế đào tạo trình độ đại học", "quy chế tuyển sinh",
        "công tác sinh viên", "học bổng", "thi đua khen thưởng",
        "quản lý và sử dụng tài sản công", "văn bằng chứng chỉ",
        "liêm chính học thuật", "thanh tra", "kiểm định chất lượng",
        "chế độ làm việc của giảng viên", "nghỉ hưu", "học phí",
        "sở hữu trí tuệ", "an toàn thông tin",
    ]
    NGUONG_NHAC = 5
    ra = []
    for k in tu_khoa:
        kk = bo_dau(k)
        tu_tieu_de = {n for n in trong if kk in bo_dau(G.nodes[n]["tieu_de"])}
        tu_noi_dung = set()
        if doc_text:
            for n in trong:
                if n in tu_tieu_de:
                    continue
                if doc_text(n).count(kk) >= NGUONG_NHAC:
                    tu_noi_dung.add(n)
        hit = tu_tieu_de | tu_noi_dung
        if hit:
            ra.append({
                "muc": "A", "loai": "từ khoá",
                "cau_hoi": "Tìm các văn bản về %s" % k,
                "dap_an_de_xuat": " ".join(sorted(hit)),
                "so_dap_an": len(hit),
                "ghi_chu": "ứng viên: %d từ tiêu đề + %d từ nội dung (≥%d lần) — "
                           "DUYỆT rồi mới dùng"
                           % (len(tu_tieu_de), len(tu_noi_dung), NGUONG_NHAC),
            })
    return ra


def muc_B(G, trong):
    """Cau hoi DA LOP: giao cua linh vuc + doi tuong (+ cap)."""
    bo = [
        ("Công tác sinh viên", "Sinh viên", None),
        ("Đào tạo", "Học viên cao học", None),
        ("Đào tạo", "Nghiên cứu sinh", None),
        ("Tổ chức, hành chính", "Viên chức, người lao động", None),
        ("Khoa học Công nghệ", "Giảng viên", None),
        ("Tài chính, kế toán", "Viên chức, người lao động", None),
        ("Thi đua, khen thưởng", "Viên chức, người lao động", None),
        ("Tuyển sinh", "Sinh viên", None),
        ("Đảm bảo chất lượng, KĐCL", "Đơn vị thuộc trường", None),
        ("Thanh tra, kiểm tra", "Đơn vị thuộc trường", None),
        ("Đào tạo", "Sinh viên", 5),
        ("Công tác sinh viên", "Sinh viên", 4),
        ("Tổ chức, hành chính", "Viên chức, người lao động", 5),
        ("Pháp chế", "Đơn vị thuộc trường", None),
        ("Cơ sở vật chất, xây dựng", "Đơn vị thuộc trường", None),
    ]
    ra = []
    for lv, dt, cap in bo:
        hit = [n for n in trong
               if G.nodes[n]["linh_vuc"] == lv
               and dt in G.nodes[n]["doi_tuong"]
               and (cap is None or G.nodes[n]["cap"] == cap)]
        if not hit:
            continue
        q = "Văn bản thuộc lĩnh vực %s, áp dụng cho %s" % (lv, dt.lower())
        if cap:
            q += ", do %s ban hành" % CAP_TEN[cap]
        ra.append({
            "muc": "B", "loai": "đa lớp", "cau_hoi": q,
            "dap_an_de_xuat": " ".join(sorted(hit)), "so_dap_an": len(hit),
            "ghi_chu": "BM25 khó — phải hiểu lĩnh vực/đối tượng là thuộc tính",
        })
    return ra


def muc_C(G, trong, tk):
    """Cau hoi BAC CAU: phai di theo canh do thi moi tra loi duoc."""
    ra = []

    # C1 — chum van ban cung dua tren mot can cu cap tren
    for so, n in tk["vien_dan_ngoai"].most_common(6):
        nut = "NGOAI::" + so
        if nut not in G:
            continue
        hit = sorted(a for a in G.predecessors(nut))
        if len(hit) < 3:
            continue
        ra.append({
            "muc": "C", "loai": "bắc cầu — chùm cùng căn cứ",
            "cau_hoi": "Nếu %s hết hiệu lực thì những văn bản nào phải rà soát lại?" % so,
            "dap_an_de_xuat": " ".join(hit), "so_dap_an": len(hit),
            "ghi_chu": "BM25 KHÔNG trả lời được — phải đi theo cạnh CĂN_CỨ",
        })

    # C2 — van ban trong bo duoc vien dan nhieu nhat
    for n in sorted(trong, key=lambda x: -G.in_degree(x))[:4]:
        if G.in_degree(n) < 3:
            continue
        hit = sorted(a for a in G.predecessors(n))
        ra.append({
            "muc": "C", "loai": "bắc cầu — văn bản nền tảng",
            "cau_hoi": "Những văn bản nào của trường căn cứ vào %s?"
                       % G.nodes[n]["so_hieu"],
            "dap_an_de_xuat": " ".join(hit), "so_dap_an": len(hit),
            "ghi_chu": "BM25 KHÔNG trả lời được — phải đi theo cạnh CĂN_CỨ",
        })

    # C3 — chuoi hieu luc THAY_THE
    for a, b, q in G.edges(data="quan_he"):
        if q not in HIEU_LUC or G.nodes[b]["ngoai_bo"]:
            continue
        ra.append({
            "muc": "C", "loai": "bắc cầu — chuỗi hiệu lực",
            "cau_hoi": "Văn bản nào đã thay thế %s, và văn bản đó lại thay thế gì?"
                       % G.nodes[b]["so_hieu"],
            "dap_an_de_xuat": " ".join(sorted([a] + [c for c in G.successors(b)
                                                     if not G.nodes[c]["ngoai_bo"]])),
            "so_dap_an": 1 + sum(1 for c in G.successors(b) if not G.nodes[c]["ngoai_bo"]),
            "ghi_chu": "BM25 KHÔNG trả lời được — phải đi theo cạnh THAY_THẾ",
        })
        if sum(1 for x in ra if x["loai"].endswith("chuỗi hiệu lực")) >= 5:
            break
    return ra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ra", default=str(GOC / "data" / "danh_gia" / "bo_cau_hoi.csv"))
    a = ap.parse_args()

    G, tk = nap(3)
    trong = [n for n, x in G.nodes(data=True) if not x["ngoai_bo"]]

    import functools

    @functools.lru_cache(maxsize=None)
    def doc_text(n):
        return bo_dau(doc_van_ban(G.nodes[n]["duong_dan"]))

    print("Đang nạp toàn văn %d tài liệu để dò từ khoá trong nội dung…" % len(trong))
    hang = muc_A(G, trong, doc_text) + muc_B(G, trong) + muc_C(G, trong, tk)
    for i, h in enumerate(hang, 1):
        h["ma"] = "Q%03d" % i
        h["dap_an_duyet"] = ""          # NGUOI LAM DE TAI dien vao cot nay
        h["nhan_xet"] = ""

    cot = ["ma", "muc", "loai", "cau_hoi", "so_dap_an", "dap_an_de_xuat",
           "dap_an_duyet", "nhan_xet"]
    p = Path(a.ra)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cot, extrasaction="ignore")
        w.writeheader()
        w.writerows(hang)

    c = Counter(h["muc"] for h in hang)
    print("=" * 92)
    print("BỘ CÂU HỎI ĐÁNH GIÁ — %d câu" % len(hang))
    print("=" * 92)
    for m, ten in (("A", "từ khoá (BM25 làm được)"),
                   ("B", "đa lớp (BM25 khó)"),
                   ("C", "bắc cầu (BM25 không làm được)")):
        print("  Mức %s — %-34s %2d câu" % (m, ten, c[m]))
    print("-" * 92)
    for h in hang:
        print("  %s [%s] %-62s %2d đáp án"
              % (h["ma"], h["muc"], h["cau_hoi"][:62], h["so_dap_an"]))
    print("=" * 92)
    print("Đã ghi: %s" % p)
    print()
    print("  ⚠ CỘT `dap_an_de_xuat` SINH TỪ CHÍNH ĐỒ THỊ — chưa dùng chấm điểm được.")
    print("    Mở file bằng Excel, đọc từng câu, điền `dap_an_duyet` (mã doc cách nhau")
    print("    bằng dấu cách). Chỉ câu nào đã duyệt mới được tính điểm.")


if __name__ == "__main__":
    main()
