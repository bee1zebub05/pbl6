# -*- coding: utf-8 -*-
"""Cham diem: DO THI TRI THUC so voi BM25, tren bo cau hoi da duoc nguoi duyet.

CHI cham nhung cau da dien cot `dap_an_duyet` trong bo_cau_hoi.csv. Cau chua duyet bi
bo qua — vi `dap_an_de_xuat` sinh tu chinh do thi, dem cham cho do thi la vong tron,
ket qua se ra 100% mot cach vo nghia.

Hai he thong duoc so:
  BM25   — tim kiem tu khoa co dien, chay tren TOAN VAN 460 tai lieu. Day la muc chuan
           ma bai bao lay lam moc (baseline).
  DO THI — hieu cau hoi o muc thuoc tinh va quan he: nhan ra linh vuc / doi tuong /
           cap ban hanh de LOC, nhan ra "can cu vao X" / "thay the X" de DI THEO CANH.

    python danh_gia.py                      # cham va in bang
    python danh_gia.py --k 10               # lay top-k khac (mac dinh 20)
    python danh_gia.py --ra ket_qua.csv
"""
import argparse
import csv
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from do_thi_lib import CAP_TEN, GOC, HIEU_LUC, do_quan_trong, doc_van_ban, nap   # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SAU = 10          # do sau co dinh cho MRR va nDCG (Ontology §6.4)
BO = GOC / "data" / "danh_gia" / "bo_cau_hoi.csv"


def chuan(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D").lower()


def tach_tu(s):
    return re.findall(r"[a-z0-9]+", chuan(s))


# ── BM25 ────────────────────────────────────────────────────────────────────
class BM25:
    """BM25 Okapi. Tu viet de khong phai them thu vien, cong thuc chuan k1=1.5 b=0.75."""

    def __init__(self, tai_lieu, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.ma = list(tai_lieu)                       # [(doc_id, [tu,...])]
        self.N = len(self.ma)
        self.dl = [len(t) for _d, t in self.ma]
        self.avg = sum(self.dl) / max(1, self.N)
        self.tf = [Counter(t) for _d, t in self.ma]
        df = Counter()
        for t in self.tf:
            df.update(t.keys())
        self.idf = {w: math.log(1 + (self.N - n + 0.5) / (n + 0.5))
                    for w, n in df.items()}

    def tim(self, cau, k=20):
        q = tach_tu(cau)
        diem = []
        for i, (doc, _t) in enumerate(self.ma):
            s = 0.0
            for w in q:
                f = self.tf[i].get(w, 0)
                if not f:
                    continue
                s += (self.idf.get(w, 0) * f * (self.k1 + 1) /
                      (f + self.k1 * (1 - self.b + self.b * self.dl[i] / self.avg)))
            if s > 0:
                diem.append((s, doc))
        diem.sort(reverse=True)
        return [d for _s, d in diem[:k]]


# ── Tim kiem dua tren DO THI ────────────────────────────────────────────────
class TimDoThi:
    """Hieu cau hoi o muc THUOC TINH va QUAN HE, khong chi so khop chu.

    Day khong phai 'gian lan': mot he thong tra cuu dua tren do thi that su lam dung
    viec nay — nhan dien thuc the trong cau hoi roi truy van theo canh. Cai duoc so
    sanh la KHA NANG cua hai cach bieu dien du lieu, khong phai chat luong cai dat.
    """

    def __init__(self, G):
        self.G = G
        self.trong = [n for n, x in G.nodes(data=True) if not x["ngoai_bo"]]
        # MRR/nDCG do THU HANG, nen ket qua do thi phai duoc XEP HANG chu khong the tra
        # ve theo thu tu abc — sap abc thi hai chi so nay do dung mot thu vo nghia
        # (van ban co ma 0001 luon dung dau). Xep theo PageRank: van ban duoc nhieu van
        # ban khac can cu vao thi dat len truoc.
        self.pr = do_quan_trong(G)
        self.lv = sorted({G.nodes[n]["linh_vuc"] for n in self.trong if G.nodes[n]["linh_vuc"]})
        self.dt = sorted({d for n in self.trong for d in G.nodes[n]["doi_tuong"]})
        self.so = {}
        for n, x in G.nodes(data=True):
            if x["so_hieu"]:
                self.so.setdefault(chuan(x["so_hieu"]), n)

    def _xep(self, ds):
        """Xep hang theo PageRank giam dan; hoa thi theo ma cho on dinh."""
        return [n for n in sorted(ds, key=lambda n: (-self.pr.get(n, 0.0), n))]

    def _nut_theo_so(self, cau):
        """Tim nut ma so hieu / ten cua no duoc nhac den trong cau hoi."""
        c = chuan(cau)
        hop = [(len(k), n) for k, n in self.so.items() if len(k) >= 4 and k in c]
        return max(hop)[1] if hop else None

    def tim(self, cau, k=20):
        c = chuan(cau)

        # --- quan he: "can cu vao X" / "X het hieu luc" / "thay the X" ---
        nut = self._nut_theo_so(cau)
        if nut and re.search(r"can cu vao|het hieu luc|ra soat", c):
            return self._xep(self.G.predecessors(nut))[:k]
        if nut and "thay the" in c:
            ra = [a for a in self.G.predecessors(nut)
                  if self.G.edges[a, nut].get("quan_he") in HIEU_LUC]
            ra += [b for b in self.G.successors(nut) if not self.G.nodes[b]["ngoai_bo"]]
            return self._xep(set(ra))[:k]

        # --- thuoc tinh: linh vuc + doi tuong + cap ---
        lv = [x for x in self.lv if chuan(x) in c]
        dt = [x for x in self.dt if chuan(x) in c]
        cap = [n for n, t in CAP_TEN.items() if n and chuan(t) in c]
        if lv or dt or cap:
            ra = [n for n in self.trong
                  if (not lv or self.G.nodes[n]["linh_vuc"] in lv)
                  and (not dt or any(d in self.G.nodes[n]["doi_tuong"] for d in dt))
                  and (not cap or self.G.nodes[n]["cap"] in cap)]
            return self._xep(ra)[:k]

        # --- con lai: so khop tren TIEU DE (metadata sach hon toan van) ---
        q = set(tach_tu(cau)) - {"tim", "cac", "van", "ban", "ve", "nhung", "nao"}
        diem = []
        for n in self.trong:
            t = set(tach_tu(self.G.nodes[n]["tieu_de"]))
            chung = len(q & t)
            if chung:
                diem.append((chung / max(1, len(q)), n))
        diem.sort(reverse=True)
        return [n for _s, n in diem[:k]]


# ── Hybrid: BM25 loc ung vien + do thi mo rong/re-rank (Ontology §6.4) ──────
class Hybrid:
    """BM25 lay ung vien, do thi cho diem lai theo LIEN KET giua cac ung vien.

    Y tuong: neu BM25 tra ve mot chum van ban ma chung LIEN KET voi nhau (cung can cu,
    can cu lan nhau), thi chum do dung chu de hon mot ket qua le loi trung tu khoa. Do
    thi khong tim thay them van ban moi ngoai danh sach ung vien — no chi SAP LAI, nen
    khong the "an gian" bang cach doan bua.
    """

    def __init__(self, bm, dt, G, rong=4, K=60, gan_ket=0.5):
        self.bm, self.dt, self.G = bm, dt, G
        self.rong, self.K, self.gan_ket = rong, K, gan_ket

    def tim(self, cau, k=20):
        n_uv = max(k, SAU) * self.rong
        uv = self.bm.tim(cau, n_uv)
        do = self.dt.tim(cau, n_uv)
        if not uv:
            return do[:k]

        # Reciprocal Rank Fusion: diem = sum 1/(K + hang). Dung RRF chu khong dung diem
        # tho vi BM25 va do thi cho ra hai thang diem khong so sanh duoc voi nhau. Cach
        # cong tho (1/hang cho BM25, cong bu cho do thi) thi ket qua hang 1 cua BM25 an
        # 1.0, lon hon moi khoan bu — do thi khong bao gio keo noi mot ket qua rac
        # xuong. RRF thi khong he thong nao ap dao duoc he thong kia.
        d = {}
        for ds in (uv, do):
            for i, n in enumerate(ds):
                d[n] = d.get(n, 0.0) + 1.0 / (self.K + i + 1)

        # Thuong GAN KET: ung vien nao noi voi cac ung vien khac thi dung chu de hon mot
        # ket qua le loi chi trung tu khoa. Chia cho hang xom nhieu nhat de khoan thuong
        # nay khong bao gio vuot qua mot bac RRF.
        tap = set(d)
        lk = {n: sum(1 for m in list(self.G.predecessors(n)) + list(self.G.successors(n))
                     if m in tap) for n in tap}
        cao = max(lk.values()) or 1
        for n in tap:
            d[n] += self.gan_ket * (lk[n] / cao) / self.K
        return sorted(d, key=lambda n: (-d[n], n))[:k]


# ── cham diem ───────────────────────────────────────────────────────────────
def diem(du_doan, dung, sau=10):
    """-> (P, R, F1, MRR, nDCG@sau).

    P/R/F1 tinh tren dung k phan tu duoc truyen vao (R-precision). MRR va nDCG thi
    tinh tren `sau` ket qua dau — hai chi so nay do CHAT LUONG XEP HANG nen phai co
    do sau co dinh, neu khong thi cau it dap an se duoc do o k=2 con cau nhieu dap an
    do o k=20, so khong so sanh duoc voi nhau.
    """
    t = set(dung)
    if not t:
        return None
    d = set(du_doan)
    tp = len(d & t)
    p = tp / len(d) if d else 0.0
    r = tp / len(t)
    f = 2 * p * r / (p + r) if (p + r) else 0.0

    dd = list(du_doan)[:sau]
    mrr = next((1.0 / (i + 1) for i, n in enumerate(dd) if n in t), 0.0)
    dcg = sum(1.0 / math.log2(i + 2) for i, n in enumerate(dd) if n in t)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(t), sau)))
    return p, r, f, mrr, (dcg / idcg if idcg else 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=0,
                    help="top-k cố định; để 0 (mặc định) dùng R-precision: "
                         "k = số đáp án đúng của từng câu")
    ap.add_argument("--bo", default=str(BO))
    ap.add_argument("--ra", default=str(GOC / "data" / "danh_gia" / "ket_qua.csv"))
    ap.add_argument("--dung-de-xuat", action="store_true",
                    help="CHẤM THỬ bằng đáp án đề xuất — KHÔNG dùng cho bài báo")
    a = ap.parse_args()

    G, tk = nap(3)
    trong = [n for n, x in G.nodes(data=True) if not x["ngoai_bo"]]

    print("Đang nạp toàn văn %d tài liệu cho BM25…" % len(trong))
    tl = [(n, tach_tu(doc_van_ban(G.nodes[n]["duong_dan"]))) for n in trong]
    bm = BM25(tl)
    dt = TimDoThi(G)
    hy = Hybrid(bm, dt, G)

    hang = list(csv.DictReader(open(a.bo, encoding="utf-8-sig")))
    cot_dap_an = "dap_an_de_xuat" if a.dung_de_xuat else "dap_an_duyet"
    lam = [h for h in hang if (h.get(cot_dap_an) or "").strip()]

    print("=" * 96)
    print("CHẤM ĐIỂM — %s | đáp án lấy từ cột `%s`"
          % ("R-precision (k = số đáp án đúng)" if a.k <= 0 else "top-%d" % a.k,
             cot_dap_an))
    print("=" * 96)
    if a.dung_de_xuat:
        print("  ⚠ ĐANG CHẤM THỬ bằng đáp án do chính đồ thị sinh ra.")
        print("    Con số ở đây CHỈ để kiểm tra chương trình chạy đúng, KHÔNG được")
        print("    đưa vào bài báo: đồ thị tự chấm cho mình thì luôn thắng.")
        print("-" * 96)
    if not lam:
        print("  Chưa câu nào được duyệt đáp án.")
        print("  Mở %s, điền cột `dap_an_duyet` rồi chạy lại." % a.bo)
        print("  Muốn chạy thử chương trình: thêm --dung-de-xuat")
        return

    kq = []
    gom = defaultdict(lambda: defaultdict(list))
    for h in lam:
        dung = (h[cot_dap_an] or "").split()
        # R-PRECISION: lay top-k DUNG BANG so dap an dung cua tung cau.
        # Lay k co dinh (vi du 20) se phat oan he thong nao cung phai tra du 20 ket qua
        # trong khi cau chi co 3 dap an — precision bi chan tran o 3/20 = 0,15 du he
        # thong tra dung ca 3. Day la cach cham chuan cho bai toan tim kiem.
        k = len(dung) if a.k <= 0 else a.k
        # Lay sau hon k de con do duoc MRR/nDCG@SAU, roi cat ve k cho P/R/F1
        s = {}
        for ten, he in (("BM25", bm), ("Đồ thị", dt), ("Hybrid", hy)):
            ds = he.tim(h["cau_hoi"], max(k, SAU))
            prf = diem(ds[:k], dung, SAU)      # P/R/F1 o do sau R-precision
            xh = diem(ds, dung, SAU)           # MRR/nDCG o do sau co dinh
            s[ten] = None if prf is None else prf[:3] + xh[3:]
        if any(v is None for v in s.values()):
            continue
        d = {"ma": h["ma"], "muc": h["muc"], "cau_hoi": h["cau_hoi"]}
        for ten, v in s.items():
            kh = {"BM25": "bm25", "Đồ thị": "dothi", "Hybrid": "hybrid"}[ten]
            for i, m in enumerate(("P", "R", "F1", "MRR", "nDCG")):
                d["%s_%s" % (kh, m)] = round(v[i], 4)
            gom[h["muc"]][ten].append(v)
            gom["TỔNG"][ten].append(v)
        kq.append(d)

    print("%-6s %-3s %-34s %17s %17s %17s"
          % ("mã", "mức", "câu hỏi", "BM25 P/R/F1", "ĐỒ THỊ P/R/F1", "HYBRID P/R/F1"))
    print("-" * 96)
    for r in kq:
        print("%-6s %-3s %-34s  %.2f %.2f %.2f  %.2f %.2f %.2f  %.2f %.2f %.2f"
              % (r["ma"], r["muc"], r["cau_hoi"][:34],
                 r["bm25_P"], r["bm25_R"], r["bm25_F1"],
                 r["dothi_P"], r["dothi_R"], r["dothi_F1"],
                 r["hybrid_P"], r["hybrid_R"], r["hybrid_F1"]))

    print("=" * 96)
    print("%-6s %-8s %8s %8s %8s %8s %9s   %s"
          % ("mức", "hệ", "P", "R", "F1", "MRR", "nDCG@%d" % SAU, "số câu"))
    print("-" * 96)
    for m in ("A", "B", "C", "TỔNG"):
        if m not in gom:
            continue
        for ten in ("BM25", "Đồ thị", "Hybrid"):
            v = gom[m][ten]
            if not v:
                continue
            tb = [sum(x[i] for x in v) / len(v) for i in range(5)]
            print("%-6s %-8s %8.3f %8.3f %8.3f %8.3f %9.3f   %d"
                  % (m, ten, tb[0], tb[1], tb[2], tb[3], tb[4], len(v)))
        print("-" * 96)
    print("  Mức A = single-hop | B = thuộc tính/lọc | C = multi-hop & hiệu lực (§6.5)")
    print("  Multi-hop là chỗ đồ thị/Hybrid phải thắng BM25 rõ rệt — nếu không thì")
    print("  phải giải thích tại sao, đừng chỉ báo con số tổng.")

    if kq:
        p = Path(a.ra)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(kq[0].keys()))
            w.writeheader()
            w.writerows(kq)
        print("Bảng chi tiết: %s" % p)


if __name__ == "__main__":
    main()
