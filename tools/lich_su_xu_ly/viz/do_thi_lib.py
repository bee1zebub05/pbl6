# -*- coding: utf-8 -*-
"""Nap do_thi.json va dung do thi networkx. Dung chung cho app Streamlit va script xuat.

Tach rieng khoi app.py de:
  - chay duoc doc lap (xuat Cypher, xuat GraphML) khong can Streamlit
  - Streamlit cache duoc ham nap thay vi doc lai file moi lan bam nut
"""
import json
import re
from collections import Counter
from pathlib import Path

import networkx as nx

GOC = Path(__file__).resolve().parents[2]
DO_THI_JSON = GOC / "data" / "do_thi" / "do_thi.json"
TEXT = GOC / "data" / "processed" / "text_final"

# Thang cap ban hanh: van ban cang o tren cang co hieu luc bao trum. Day la truc
# thong tin chinh cua ca do thi — mau sac va tang trong so do phan tang deu theo no.
CAP = [
    (1, "Quốc hội", "#1B2A4A"),
    (2, "Chính phủ / Thủ tướng", "#2F5D80"),
    (3, "Bộ, ngành", "#3E8B8A"),
    (4, "Đại học Đà Nẵng", "#7BA45F"),
    (5, "Trường ĐH Bách khoa", "#C1902F"),
    (0, "Chưa xếp được", "#9AA3AD"),
]
CAP_TEN = {c: t for c, t, _ in CAP}
CAP_MAU = {c: m for c, _t, m in CAP}
MAU_THAY_THE = "#B8332B"

# Ontology v0.3 §4 tach THAY_THE cu thanh ba quan he. Cac cho ve do thi / dem "chuoi
# hieu luc" phai xet CA BA, khong chi rieng REPLACES — neu khong thi mot van ban bi
# bai bo se hien nhu chua he bi dong cham.
HIEU_LUC = {"REPLACES", "AMENDS", "REPEALS",
            "REPLACED_BY", "AMENDED_BY", "REPEALED_BY"}
VIEN_DAN = {"BASED_ON", "REFERENCES"}

MA_CAP = [
    (1, ["QH13", "QH14", "QH15", "QH"]),
    (2, ["CP", "TTG", "NĐ-CP"]),
    (3, ["BGDĐT", "BGDDT", "BNV", "BTC", "BLĐTBXH", "TTCP", "BKHCN", "BTTTT",
         "BYT", "NHNN", "BKHĐT", "BNG", "BQP", "BCA", "BTNMT", "BXD", "TT"]),
    (4, ["ĐHĐN", "HĐĐH", "DHDN"]),
    (5, ["ĐHBK", "HĐT", "DHBK", "BCĐ"]),
]


def xep_cap(co_quan, so_hieu):
    """-> 1..5 theo cap ban hanh, 0 neu khong doan duoc."""
    cq = (co_quan or "").upper()
    for c, ds in MA_CAP:
        if cq in ds:
            return c
    duoi = (so_hieu or "").split("/")[-1].upper()
    for c, ds in MA_CAP:
        for m in ds:
            if duoi.endswith(m):
                return c
    return 0


def nap(nguong_ngoai=3):
    """-> (DiGraph, dict thong ke).

    Nut = van ban trong bo + van ban NGOAI bo duoc vien dan >= nguong_ngoai lan.
    Giu van ban ngoai lai la co chu dich: cho nao nhieu van ban cung tro ve mot Thong tu
    thi day chinh la 'moi lien ket ngam' — bo di thi mat luon phat hien do.
    """
    d = json.loads(DO_THI_JSON.read_text(encoding="utf-8"))
    vb, canh = d["van_ban"], d["canh"]

    G = nx.DiGraph()
    for k, v in vb.items():
        G.add_node(k, **{
            "so_hieu": v["so_hieu"], "tieu_de": v["tieu_de"], "loai": v["ten_loai"],
            "co_quan": v["ten_co_quan"], "linh_vuc": v["linh_vuc"], "ngay": v["ngay"],
            "nam": v["ngay"][:4] if v["ngay"] else "", "nguoi_ky": v["nguoi_ky"], "hoc_ham": v.get("hoc_ham", ""),
            "chuc_danh": v.get("chuc_danh", ""),
            "so_trang": v["so_trang"], "doi_tuong": v["doi_tuong"],
            "don_vi": v.get("don_vi") or [],
            "dieu": v.get("dieu") or [], "noi_dung": v.get("noi_dung"),
            "duong_dan": v["duong_dan"], "ngoai_bo": False,
            "cap": xep_cap(v["co_quan"], v["so_hieu"]),
        })

    dem_ngoai = Counter()
    loai_ngoai = {}
    for c in canh:
        if not c.get("trong_bo"):
            dem_ngoai[c["den"]] += 1
            loai_ngoai.setdefault(c["den"], c.get("loai", ""))

    for so, n in dem_ngoai.items():
        if n < nguong_ngoai:
            continue
        k = "NGOAI::" + so
        loai = (loai_ngoai.get(so) or "văn bản").strip().capitalize()
        G.add_node(k, **{
            "so_hieu": so, "tieu_de": "%s %s" % (loai, so), "loai": loai,
            "co_quan": "Ngoài bộ dữ liệu", "linh_vuc": "", "ngay": "", "nam": "",
            "nguoi_ky": "", "so_trang": 0, "doi_tuong": [], "don_vi": [],
            "duong_dan": "",
            "ngoai_bo": True, "so_lan_vien_dan": n,
            "cap": xep_cap(so.split("/")[-1], so),
        })

    for c in canh:
        a = c["tu"]
        b = c["den"] if c.get("trong_bo") else "NGOAI::" + c["den"]
        if a in G and b in G and a != b:
            G.add_edge(a, b, quan_he=c["quan_he"])

    tk = {
        "so_van_ban": len(vb),
        "so_nut_ngoai": sum(1 for _, x in G.nodes(data=True) if x["ngoai_bo"]),
        "so_canh": G.number_of_edges(),
        "so_thay_the": sum(1 for *_e, q in G.edges(data="quan_he") if q in HIEU_LUC),
        "vien_dan_ngoai": dem_ngoai,
    }
    return G, tk


def do_quan_trong(G):
    """PageRank: van ban nao la NEN TANG cua ca he thong.

    Canh da chay theo huong 'A can cu vao B', nen van ban nen tang la van ban co NHIEU
    MUI TEN TRO VAO — dung chieu ma PageRank von do. Khong dao chieu do thi: dao lai
    thanh do 'van ban nao trich dan nhieu nhat', mot chi so hoan toan khac.

    Hon han viec chi dem bac vao: mot quy dinh duoc 3 van ban NEN TANG dua vao thi quan
    trong hon quy dinh duoc 5 van ban le te dua vao.
    """
    try:
        return nx.pagerank(G, alpha=0.85)
    except Exception as e:      # thieu scipy -> van chay duoc, chi mat cot xep hang
        print("Không tính được PageRank (%s) — tạm xếp theo số lần được viện dẫn." % e)
        n = max(1, G.number_of_edges())
        return {x: G.in_degree(x) / n for x in G}


def loc(G, linh_vuc=None, cap=None, loai=None, nam=(None, None), tim="",
        chi_co_lien_ket=False, giu_ngoai=True):
    """-> do thi con theo bo loc. Nut ngoai bo khong bi loc theo linh vuc/nam vi
    chung khong co nhung thuoc tinh do — loc se xoa sach chung mot cach vo ly."""
    giu = []
    tim = (tim or "").strip().lower()
    for n, x in G.nodes(data=True):
        if x["ngoai_bo"]:
            if giu_ngoai:
                giu.append(n)
            continue
        if linh_vuc and x["linh_vuc"] not in linh_vuc:
            continue
        if cap and x["cap"] not in cap:
            continue
        if loai and x["loai"] not in loai:
            continue
        if nam[0] and x["nam"] and not (nam[0] <= int(x["nam"]) <= nam[1]):
            continue
        if tim and tim not in (x["tieu_de"] + " " + x["so_hieu"]).lower():
            continue
        giu.append(n)
    H = G.subgraph(giu).copy()
    if giu_ngoai:      # bo nut ngoai bo tro thanh co doc sau khi loc
        H.remove_nodes_from([n for n, x in H.nodes(data=True)
                             if x["ngoai_bo"] and H.degree(n) == 0])
    if chi_co_lien_ket:
        H.remove_nodes_from([n for n in list(H) if H.degree(n) == 0])
    return H


def doc_van_ban(duong_dan, so_trang_dau=None):
    p = GOC / duong_dan
    if not p.exists():
        return ""
    t = p.read_text(encoding="utf-8", errors="replace")
    if so_trang_dau:
        phan = re.split(r"-{3,}\s*\[Trang\s+\d+\]\s*-{3,}", t)
        t = "\n".join(phan[:so_trang_dau + 1])
    return t
