# -*- coding: utf-8 -*-
"""Cac cach nhin do thi MANH HON so voi mot buc tranh mang luoi duy nhat.

Do thi 500 nut ve het mot luc thi thanh 'bui long' — dep nhung khong doc duoc gi. Bon
cach nhin duoi day moi cach tra loi mot cau hoi khac han:

  1. VUNG LAN CAN (ego network)  — "van ban NAY lien quan toi nhung gi?"
     Chi ve 1 van ban va hang xom trong N buoc. Day la cach duy nhat doc duoc chi tiet.

  2. DONG CHAY (Sankey)          — "linh vuc nao chiu dieu chinh tu cap nao?"
     Linh vuc -> Cap ban hanh -> Loai van ban. Thay duoc cau truc quyen luc.

  3. DONG THOI GIAN              — "he thong van ban lon len the nao?"
     So van ban va so quan he moi theo nam.

  4. CHUM CUNG CAN CU            — "sua mot Thong tu thi keo theo bao nhieu van ban?"
     Day la cau hoi trung tam cua ca de tai.
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parent))
from do_thi_lib import CAP_MAU, CAP_TEN, MAU_THAY_THE, VIEN_DAN   # noqa: E402


def vung_lan_can(G, tam, buoc=1, toi_da=60):
    """-> do thi con gom `tam` va hang xom trong `buoc` buoc (di ca hai chieu).

    Di CA HAI CHIEU la co chu dich: mot van ban vua CAN CU vao cap tren, vua DUOC cac
    van ban khac can cu vao. Chi di mot chieu la mat nua buc tranh.
    """
    if tam not in G:
        return nx.DiGraph()
    giu = {tam}
    vien = {tam}
    for _ in range(buoc):
        moi = set()
        for n in vien:
            moi |= set(G.predecessors(n)) | set(G.successors(n))
        vien = moi - giu
        giu |= moi
        if len(giu) > toi_da:
            break
    return G.subgraph(giu).copy()


def _mo(hex_mau, alpha):
    """#1B2A4A + 0.4 -> 'rgba(27,42,74,0.4)'.

    Plotly KHONG nhan hex 8 ky tu (#RRGGBBAA) cho mau cua Sankey link — phai dung
    rgba(). Da do that: truyen '#1B2A4A66' vao thi no nem ValueError.
    """
    h = (hex_mau or "#888888").lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "rgba(%d,%d,%d,%.2f)" % (r, g, b, alpha)


def sankey_linh_vuc_cap(G, trong):
    """Sankey: Linh vuc -> Cap ban hanh -> Loai van ban."""
    lv_cap = Counter()
    cap_loai = Counter()
    for n in trong:
        x = G.nodes[n]
        lv = x["linh_vuc"] or "(không rõ)"
        cap = CAP_TEN.get(x["cap"], "Chưa xếp được")
        loai = x["loai"] or "(không rõ)"
        lv_cap[(lv, cap)] += 1
        cap_loai[(cap, loai)] += 1

    nhan = []
    ix = {}

    def them(t):
        if t not in ix:
            ix[t] = len(nhan)
            nhan.append(t)
        return ix[t]

    nguon, dich, gt, mau = [], [], [], []
    for (lv, cap), n in lv_cap.most_common():
        if n < 2:
            continue
        nguon.append(them(lv))
        dich.append(them(cap))
        gt.append(n)
        c = next((k for k, v in CAP_TEN.items() if v == cap), 0)
        mau.append(_mo(CAP_MAU.get(c, "#9AA3AD"), 0.40))
    for (cap, loai), n in cap_loai.most_common():
        if n < 3:
            continue
        nguon.append(them(cap))
        dich.append(them(loai))
        gt.append(n)
        c = next((k for k, v in CAP_TEN.items() if v == cap), 0)
        mau.append(_mo(CAP_MAU.get(c, "#9AA3AD"), 0.26))

    mau_nut = []
    for t in nhan:
        c = next((k for k, v in CAP_TEN.items() if v == t), None)
        mau_nut.append(CAP_MAU.get(c, "#5B6670") if c is not None else "#8894A0")

    f = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=nhan, pad=14, thickness=16, color=mau_nut,
                  line=dict(color="rgba(0,0,0,0)", width=0)),
        link=dict(source=nguon, target=dich, value=gt, color=mau)))
    f.update_layout(height=760, margin=dict(l=8, r=8, t=8, b=8), font_size=12)
    return f


def dong_thoi_gian(G, trong):
    """So van ban ban hanh va so quan he sinh ra theo tung nam."""
    nam_vb = Counter()
    nam_qh = Counter()
    for n in trong:
        y = G.nodes[n]["nam"]
        if not y.isdigit():
            continue
        nam_vb[int(y)] += 1
        nam_qh[int(y)] += G.out_degree(n)
    if not nam_vb:
        return None
    ys = sorted(nam_vb)
    f = go.Figure()
    f.add_bar(x=ys, y=[nam_vb[y] for y in ys], name="Văn bản ban hành",
              marker_color="#2F5D80")
    f.add_scatter(x=ys, y=[nam_qh[y] for y in ys], name="Quan hệ căn cứ sinh ra",
                  yaxis="y2", mode="lines+markers",
                  line=dict(color="#C1902F", width=2.5))
    f.update_layout(height=380, margin=dict(l=8, r=8, t=8, b=8),
                    yaxis=dict(title="Văn bản"),
                    yaxis2=dict(title="Quan hệ", overlaying="y", side="right"),
                    legend=dict(orientation="h", y=1.12),
                    plot_bgcolor="rgba(0,0,0,0)")
    return f


def chum_cung_can_cu(G, toi_thieu=5, toi_da=20):
    """-> [(nut can cu, [van ban cung dua vao no])] xep theo do lon chum."""
    ra = []
    for n, x in G.nodes(data=True):
        con = [a for a in G.predecessors(n)
               if G.edges[a, n].get("quan_he") in VIEN_DAN]
        if len(con) >= toi_thieu:
            ra.append((n, x, sorted(con)))
    ra.sort(key=lambda t: -len(t[2]))
    return ra[:toi_da]


def bieu_do_chum(chum):
    """Cot ngang: chum nao lon nhat."""
    ten = [x["so_hieu"] or n for n, x, _c in chum][::-1]
    gt = [len(c) for _n, _x, c in chum][::-1]
    mau = [CAP_MAU.get(x["cap"], "#9AA3AD") for _n, x, _c in chum][::-1]
    f = go.Figure(go.Bar(x=gt, y=ten, orientation="h", marker_color=mau,
                         text=gt, textposition="outside"))
    f.update_layout(height=max(320, 26 * len(ten)),
                    margin=dict(l=8, r=40, t=8, b=8),
                    xaxis_title="Số văn bản cùng căn cứ vào",
                    plot_bgcolor="rgba(0,0,0,0)")
    return f


def ma_tran_lien_ket(G, trong):
    """Nhiet: linh vuc A co bao nhieu quan he sang linh vuc B."""
    lv = sorted({G.nodes[n]["linh_vuc"] for n in trong if G.nodes[n]["linh_vuc"]})
    ix = {x: i for i, x in enumerate(lv)}
    m = [[0] * len(lv) for _ in lv]
    for a, b in G.edges():
        xa, xb = G.nodes[a], G.nodes[b]
        if xa["ngoai_bo"] or xb["ngoai_bo"]:
            continue
        if xa["linh_vuc"] in ix and xb["linh_vuc"] in ix:
            m[ix[xa["linh_vuc"]]][ix[xb["linh_vuc"]]] += 1
    f = go.Figure(go.Heatmap(
        z=m, x=lv, y=lv, colorscale=[[0, "#F6F7F9"], [1, "#1B2A4A"]],
        hovertemplate="%{y} → %{x}: %{z} quan hệ<extra></extra>"))
    f.update_layout(height=620, margin=dict(l=8, r=8, t=8, b=8),
                    xaxis_title="căn cứ vào lĩnh vực", yaxis_title="lĩnh vực của văn bản")
    return f
