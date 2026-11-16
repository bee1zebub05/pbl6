# -*- coding: utf-8 -*-
"""Ung dung truc quan hoa DO THI TRI THUC van ban phap quy DUT.

Chay:
    F:\\DUT4\\PBL6\\project\\viz_env\\Scripts\\streamlit.exe run F:\\DUT4\\PBL6\\project\\viz\\app.py
hoac dung file chay_viz.bat o thu muc goc project.

Bon phan:
  1. Do thi tri thuc  — pyvis (vis.js), hai kieu bo tri: luc day va phan tang theo cap
  2. Phan tich        — plotly: phan bo linh vuc, thang cap, dong thoi gian, do quan trong
  3. Tra cuu          — bang loc duoc + xem toan van + danh sach can cu / duoc vien dan
  4. Xuat Neo4j       — sinh script Cypher va file GraphML
"""
import sys
from pathlib import Path

import networkx as nx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pyvis.network import Network

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kham_pha as KP                                  # noqa: E402
from do_thi_lib import (CAP, CAP_MAU, CAP_TEN, HIEU_LUC, MAU_THAY_THE, doc_van_ban,  # noqa: E402
                        do_quan_trong, loc, nap)

st.set_page_config(page_title="Đồ thị tri thức văn bản pháp quy DUT",
                   page_icon="⚖", layout="wide")

MAU_NEN = "#F6F7F9"
MAU_MUC = "#111820"

st.markdown("""
<style>
  .block-container { padding-top: 2.2rem; max-width: 1500px; }
  [data-testid="stMetricValue"] { font-size: 1.7rem; font-variant-numeric: tabular-nums; }
  [data-testid="stMetricLabel"] { font-size: .78rem; letter-spacing: .04em;
                                  text-transform: uppercase; opacity: .75; }
  .chu-thich { display:flex; flex-wrap:wrap; gap:.45rem 1.1rem; margin:.35rem 0 .9rem; }
  .chu-thich span { display:inline-flex; align-items:center; gap:.4rem; font-size:.82rem; }
  .cham { width:.7rem; height:.7rem; border-radius:50%; display:inline-block; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner="Đang nạp đồ thị…")
def _nap(nguong):
    G, tk = nap(nguong)
    return G, tk, do_quan_trong(G)


def dong_cung(html):
    """Chen lenh TAT LUC DAY ngay khi do thi xep xong.

    vis.js chay mo phong luc day lien tuc, nen sau khi xep xong cac nut van tu troi
    nhe — nhin nhu do thi 'quay quay', rat kho ro chuot dung vao mot nut hay doc nhan.
    Bat su kien 'stabilizationIterationsDone' (vis.js phat ra khi xep xong) roi tat
    physics: do thi dung yen han, van keo tay va phong to duoc binh thuong.

    Dat truoc 'return network' de chay sau khi bien network da ton tai.
    """
    neo = "network = new vis.Network(container, data, options);"
    them = neo + """
                  network.once("stabilizationIterationsDone", function () {
                      network.setOptions({physics: {enabled: false}});
                  });
                  // mang nho van co the xep xong truoc khi kip gan su kien tren
                  setTimeout(function () {
                      network.setOptions({physics: {enabled: false}});
                  }, 8000);"""
    return html.replace(neo, them, 1) if neo in html else html


def khung_pyvis(H, pr, phan_tang, cao=720, tam=None, tu_dung=True):
    """Dung HTML pyvis. phan_tang=True -> xep theo cấp ban hành thành từng tầng."""
    net = Network(height="%dpx" % cao, width="100%", directed=True,
                  bgcolor="#FFFFFF", font_color=MAU_MUC, notebook=False, cdn_resources="in_line")
    bac_max = max([d for _n, d in H.degree()] + [1])

    for n, x in H.nodes(data=True):
        bac = H.degree(n)
        kich = 9 + 26 * (bac / bac_max) ** 0.6
        mau = CAP_MAU.get(x["cap"], CAP_MAU[0])
        vien = MAU_MUC if n == tam else ("#FFFFFF" if not x["ngoai_bo"] else mau)
        nhan = x["so_hieu"] or n
        mo_ta = ["<b>%s</b>" % (x["so_hieu"] or n), x["tieu_de"][:180]]
        if x["ngoai_bo"]:
            mo_ta.append("<i>Ngoài bộ dữ liệu — được viện dẫn %d lần</i>"
                         % x.get("so_lan_vien_dan", 0))
        else:
            mo_ta += ["Lĩnh vực: %s" % x["linh_vuc"],
                      "Cấp: %s" % CAP_TEN.get(x["cap"], "?"),
                      "Ngày ban hành: %s" % (x["ngay"] or "không đọc được"),
                      "Người ký: %s" % (x["nguoi_ky"] or "không đọc được"),
                      "Số trang: %d" % x["so_trang"],
                      "Độ quan trọng (PageRank): %.4f" % pr.get(n, 0)]
        net.add_node(n, label=nhan, title="<br>".join(mo_ta), size=kich, color={
            "background": mau, "border": vien,
            "highlight": {"background": mau, "border": MAU_MUC}},
            borderWidth=3 if n == tam else 1,
            shape="square" if x["ngoai_bo"] else "dot",
            level=x["cap"] if x["cap"] else 6,
            font={"size": 13, "face": "Segoe UI", "color": MAU_MUC})

    for a, b, q in H.edges(data="quan_he"):
        thay = q in HIEU_LUC
        net.add_edge(a, b, color=MAU_THAY_THE if thay else "#C3CBD4",
                     width=2.2 if thay else 1,
                     title="THAY THẾ" if thay else "CĂN CỨ",
                     dashes=thay, arrowStrikethrough=False)

    if phan_tang:
        net.set_options("""{
          "layout": {"hierarchical": {"enabled": true, "direction": "UD",
            "sortMethod": "directed", "levelSeparation": 190, "nodeSpacing": 62,
            "treeSpacing": 130, "blockShifting": true, "edgeMinimization": true}},
          "physics": {"enabled": false},
          "edges": {"smooth": {"type": "cubicBezier", "forceDirection": "vertical",
                    "roundness": 0.45}, "arrows": {"to": {"scaleFactor": 0.5}}},
          "interaction": {"hover": true, "tooltipDelay": 120, "navigationButtons": true}
        }""")
    else:
        net.set_options("""{
          "physics": {"solver": "forceAtlas2Based", "forceAtlas2Based":
            {"gravitationalConstant": -62, "centralGravity": 0.008,
             "springLength": 120, "springConstant": 0.06, "damping": 0.5},
            "stabilization": {"iterations": 320}},
          "edges": {"smooth": {"type": "continuous", "roundness": 0.2},
                    "arrows": {"to": {"scaleFactor": 0.5}}},
          "interaction": {"hover": true, "tooltipDelay": 120, "navigationButtons": true}
        }""")
    html = net.generate_html(notebook=False)
    # bo tri phan tang von da tat physics san, chi kieu luc day moi can dong cung
    return dong_cung(html) if (tu_dung and not phan_tang) else html


def chu_thich_cap():
    o = ['<div class="chu-thich">']
    for c, ten, mau in CAP:
        o.append('<span><i class="cham" style="background:%s"></i>%s</span>' % (mau, ten))
    o.append('<span><i class="cham" style="background:%s;border-radius:2px"></i>'
             'Nét đứt đỏ = THAY THẾ</span></div>' % MAU_THAY_THE)
    st.markdown("".join(o), unsafe_allow_html=True)


# ── nạp dữ liệu ──────────────────────────────────────────────────────────────
st.sidebar.title("Bộ lọc")
nguong = st.sidebar.slider("Văn bản ngoài bộ: hiện khi được viện dẫn từ", 1, 20, 3,
                           help="Thông tư/Nghị định không nằm trong 455 file, nhưng được "
                                "nhiều văn bản trong bộ cùng căn cứ vào.")
G, tk, pr = _nap(nguong)

ds_lv = sorted({x["linh_vuc"] for _n, x in G.nodes(data=True) if x["linh_vuc"]})
ds_loai = sorted({x["loai"] for _n, x in G.nodes(data=True) if x["loai"]})
ds_nam = sorted({int(x["nam"]) for _n, x in G.nodes(data=True) if x["nam"].isdigit()})

f_lv = st.sidebar.multiselect("Lĩnh vực", ds_lv)
f_cap = st.sidebar.multiselect("Cấp ban hành", [c for c, _t, _m in CAP],
                               format_func=lambda c: CAP_TEN[c])
f_loai = st.sidebar.multiselect("Loại văn bản", ds_loai)
f_nam = st.sidebar.slider("Năm ban hành", min(ds_nam), max(ds_nam),
                          (min(ds_nam), max(ds_nam))) if ds_nam else (None, None)
f_tim = st.sidebar.text_input("Tìm trong số hiệu / tiêu đề")
chi_lien_ket = st.sidebar.checkbox("Chỉ hiện văn bản có liên kết", value=True,
                                   help="Ẩn các văn bản đứng một mình, không căn cứ vào "
                                        "và cũng không được văn bản nào căn cứ tới.")
giu_ngoai = st.sidebar.checkbox("Hiện văn bản ngoài bộ", value=True)

H = loc(G, f_lv, f_cap, f_loai, f_nam, f_tim, chi_lien_ket, giu_ngoai)

# danh sach van ban trong bo, KHONG loc — tab Kham pha nhin toan canh
trong_all2 = [n for n, x in G.nodes(data=True) if not x["ngoai_bo"]]

st.title("Đồ thị tri thức văn bản pháp quy")
st.caption("Trường Đại học Bách khoa – Đại học Đà Nẵng · %d văn bản đã OCR và làm sạch"
           % tk["so_van_ban"])

vb_hien = [n for n, x in H.nodes(data=True) if not x["ngoai_bo"]]
an = tk["so_van_ban"] - len(vb_hien)

c = st.columns(5)
c[0].metric("Văn bản", "%d" % tk["so_van_ban"])
c[1].metric("Quan hệ căn cứ", "%d" % tk["so_canh"])
c[2].metric("Quan hệ thay thế", "%d" % tk["so_thay_the"])
c[3].metric("Lĩnh vực", "%d" % len(ds_lv))
c[4].metric("Đang hiện", "%d nút · %d cạnh" % (H.number_of_nodes(), H.number_of_edges()),
            delta="ẩn %d văn bản" % an if an else None, delta_color="off")

# So nut luon nho hon 455 va rat de bi hieu nham la mat du lieu. Noi thang dang an bao
# nhieu, vi ly do gi, va an theo cai nut nao — de nguoi dung tu bat lai duoc.
if an:
    ly_do = []
    if chi_lien_ket:
        n_codoc = sum(1 for n, x in G.nodes(data=True)
                      if not x["ngoai_bo"] and G.degree(n) == 0)
        if n_codoc:
            ly_do.append("**%d** văn bản chưa trích được quan hệ nào — ẩn bởi ô "
                         "*Chỉ hiện văn bản có liên kết*" % n_codoc)
    if not giu_ngoai:
        n_chi_ngoai = sum(1 for n, x in G.nodes(data=True)
                          if not x["ngoai_bo"] and G.degree(n) > 0
                          and all(G.nodes[b]["ngoai_bo"] for b in G.successors(n))
                          and not any(True for _ in G.predecessors(n)))
        if n_chi_ngoai:
            ly_do.append("**%d** văn bản chỉ căn cứ vào văn bản ngoài bộ — mất chỗ bám "
                         "khi tắt ô *Hiện văn bản ngoài bộ*" % n_chi_ngoai)
    if f_lv or f_cap or f_loai or f_tim or (ds_nam and f_nam != (min(ds_nam), max(ds_nam))):
        ly_do.append("phần còn lại do bộ lọc lĩnh vực / cấp / loại / năm / từ khoá")
    if ly_do:
        st.info("Đang ẩn %d / %d văn bản: %s."
                % (an, tk["so_van_ban"], "; ".join(ly_do)))

t1, t5, t2, t3, t4 = st.tabs(["Đồ thị tri thức", "Khám phá quan hệ", "Phân tích",
                              "Tra cứu văn bản", "Xuất sang Neo4j"])

# ── 1. Đồ thị ────────────────────────────────────────────────────────────────
with t1:
    a, b = st.columns([3, 1])
    with b:
        kieu = st.radio("Cách bố trí", ["Lực đẩy (cụm chủ đề)", "Phân tầng theo cấp"],
                        help="Phân tầng xếp văn bản thành 5 tầng theo cấp ban hành — "
                             "thấy rõ quy định của trường dựa lên luật và thông tư cấp trên.")
        cao = st.slider("Chiều cao khung", 480, 1100, 760, 20)
        tu_dung = st.checkbox("Dừng chuyển động khi xếp xong", value=True,
                              help="Tắt mô phỏng lực đẩy sau khi đồ thị ổn định, để các "
                                   "nút đứng yên. Vẫn kéo và phóng to được bình thường.")
    with a:
        chu_thich_cap()
    if H.number_of_nodes() == 0:
        st.warning("Bộ lọc hiện tại không còn văn bản nào. Nới bớt điều kiện ở thanh bên.")
    elif H.number_of_nodes() > 900:
        st.warning("Đang có %d nút — vẽ sẽ rất chậm. Lọc bớt ở thanh bên."
                   % H.number_of_nodes())
    else:
        st.iframe(
            khung_pyvis(H, pr, kieu.startswith("Phân tầng"), cao, tu_dung=tu_dung),
            height=cao + 24)
        st.caption("Rê chuột lên một nút để xem đầy đủ thông tin. Kéo để sắp lại. "
                   "Mũi tên chạy theo chiều **A căn cứ vào B**.")

# ── 2. Phân tích ─────────────────────────────────────────────────────────────
with t2:
    # Mac dinh cham TOAN BO 455 van ban chu khong theo bo loc: cac bieu do nay la buc
    # tranh chung cua kho van ban. Nhung phai noi ro dang tinh tren tap nao, neu khong
    # so o day (455) va so "Dang hien" o tren se da nhau ma khong biet vi sao.
    theo_loc = st.toggle("Chỉ tính các văn bản đang hiện (%d)" % len(vb_hien),
                         value=False,
                         help="Tắt: thống kê trên toàn bộ %d văn bản. "
                              "Bật: chỉ tính phần đang qua bộ lọc." % tk["so_van_ban"])
    nguon_nut = H if theo_loc else G
    trong = [(n, x) for n, x in nguon_nut.nodes(data=True) if not x["ngoai_bo"]]
    st.caption("Đang thống kê trên **%d văn bản** (%s)."
               % (len(trong), "theo bộ lọc" if theo_loc else "toàn bộ kho, không lọc"))
    df = pd.DataFrame([{
        "doc": n, "so_hieu": x["so_hieu"], "tieu_de": x["tieu_de"], "loai": x["loai"],
        "linh_vuc": x["linh_vuc"], "cap": CAP_TEN.get(x["cap"], "?"), "cap_so": x["cap"],
        "nam": x["nam"], "so_trang": x["so_trang"], "nguoi_ky": x["nguoi_ky"],
        "duoc_vien_dan": G.in_degree(n), "vien_dan_toi": G.out_degree(n),
        "quan_trong": pr.get(n, 0),
    } for n, x in trong])

    r1 = st.columns(2)
    with r1[0]:
        st.subheader("Văn bản theo lĩnh vực")
        d = df["linh_vuc"].value_counts().reset_index()
        d.columns = ["Lĩnh vực", "Số văn bản"]
        f = px.bar(d, x="Số văn bản", y="Lĩnh vực", orientation="h",
                   color_discrete_sequence=["#2F5D80"], text="Số văn bản")
        f.update_layout(height=520, yaxis={"categoryorder": "total ascending"},
                        margin=dict(l=0, r=10, t=10, b=0), plot_bgcolor="rgba(0,0,0,0)")
        f.update_traces(textposition="outside", cliponaxis=False)
        st.plotly_chart(f, width="stretch")
    with r1[1]:
        st.subheader("Thang cấp ban hành")
        d = df["cap"].value_counts().reset_index()
        d.columns = ["Cấp", "Số văn bản"]
        mau_theo_ten = {t: m for _c, t, m in CAP}
        f = px.bar(d, x="Số văn bản", y="Cấp", orientation="h", text="Số văn bản",
                   color="Cấp", color_discrete_map=mau_theo_ten)
        f.update_traces(textposition="outside", cliponaxis=False)
        f.update_layout(height=240, showlegend=False, yaxis={"categoryorder": "total ascending"},
                        margin=dict(l=0, r=10, t=10, b=0), plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(f, width="stretch")

        st.subheader("Văn bản ban hành theo năm")
        d = df[df["nam"] != ""].groupby("nam").size().reset_index(name="Số văn bản")
        f = px.bar(d, x="nam", y="Số văn bản", color_discrete_sequence=["#3E8B8A"])
        f.update_layout(height=250, xaxis_title="", margin=dict(l=0, r=10, t=10, b=0),
                        plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(f, width="stretch")

    st.divider()
    r2 = st.columns(2)
    with r2[0]:
        st.subheader("Văn bản nền tảng — được nhiều văn bản khác căn cứ vào")
        st.caption("Xếp theo PageRank trên đồ thị đảo chiều: không phải văn bản trích dẫn "
                   "nhiều nhất, mà văn bản được cả hệ thống dựa lên nhiều nhất.")
        d = df.nlargest(15, "quan_trong")[["so_hieu", "tieu_de", "linh_vuc",
                                           "duoc_vien_dan", "quan_trong"]]
        d.columns = ["Số hiệu", "Tiêu đề", "Lĩnh vực", "Được viện dẫn", "PageRank"]
        st.dataframe(d, width="stretch", hide_index=True,
                     column_config={"PageRank": st.column_config.NumberColumn(format="%.4f"),
                                    "Tiêu đề": st.column_config.TextColumn(width="large")})
    with r2[1]:
        st.subheader("Căn cứ ngoài bộ được viện dẫn nhiều nhất")
        st.caption("Thông tư / Nghị định cấp trên mà nhiều văn bản của trường cùng dựa vào. "
                   "Một văn bản ở đây hết hiệu lực là kéo theo cả chùm phải rà lại.")
        d = pd.DataFrame([{"Số hiệu": s, "Số lần được viện dẫn": n}
                          for s, n in tk["vien_dan_ngoai"].most_common(15)])
        st.dataframe(d, width="stretch", hide_index=True)

    st.divider()
    st.subheader("Lĩnh vực nào dựa vào cấp nào")
    st.caption("Mỗi ô là số văn bản. Hàng nào dồn về cột bên trái là lĩnh vực chịu điều "
               "chỉnh chủ yếu từ luật và nghị định cấp trên.")
    bang = pd.crosstab(df["linh_vuc"], df["cap"])
    thu_tu = [CAP_TEN[c] for c, _t, _m in CAP if CAP_TEN[c] in bang.columns]
    bang = bang[thu_tu]
    f = go.Figure(go.Heatmap(z=bang.values, x=bang.columns, y=bang.index,
                             colorscale=[[0, "#F6F7F9"], [1, "#1B2A4A"]],
                             text=bang.values, texttemplate="%{text}",
                             hovertemplate="%{y}<br>%{x}: %{z} văn bản<extra></extra>"))
    f.update_layout(height=560, margin=dict(l=0, r=10, t=10, b=0))
    st.plotly_chart(f, width="stretch")

# ── 3. Tra cứu ───────────────────────────────────────────────────────────────
with t3:
    trong_h = [n for n, x in H.nodes(data=True) if not x["ngoai_bo"]]
    if not trong_h:
        st.info("Bộ lọc hiện tại không còn văn bản nào.")
    else:
        dsach = sorted(trong_h, key=lambda n: -pr.get(n, 0))
        chon = st.selectbox("Chọn văn bản (%d văn bản khớp bộ lọc)" % len(dsach), dsach,
                            format_func=lambda n: "%s — %s" % (G.nodes[n]["so_hieu"],
                                                               G.nodes[n]["tieu_de"][:90]))
        x = G.nodes[chon]
        k = st.columns(4)
        k[0].metric("Số hiệu", x["so_hieu"] or "—")
        k[1].metric("Ngày ban hành", x["ngay"] or "—")
        k[2].metric("Được viện dẫn", "%d" % G.in_degree(chon))
        k[3].metric("Số trang", "%d" % x["so_trang"])
        st.markdown("**%s**" % x["tieu_de"])
        st.caption("%s · %s · %s%s"
                   % (x["loai"], CAP_TEN.get(x["cap"], "?"), x["linh_vuc"],
                      " · Người ký: " + x["nguoi_ky"] if x["nguoi_ky"] else ""))
        if x["doi_tuong"]:
            st.caption("Đối tượng áp dụng: " + ", ".join(x["doi_tuong"]))

        q = st.columns(2)
        with q[0]:
            st.markdown("##### Văn bản này căn cứ vào")
            ra = [{"Số hiệu": G.nodes[b]["so_hieu"],
                   "Tiêu đề": G.nodes[b]["tieu_de"][:70],
                   "Quan hệ": G.edges[chon, b]["quan_he"],
                   "Trong bộ": "không" if G.nodes[b]["ngoai_bo"] else "có"}
                  for b in G.successors(chon)]
            if ra:
                st.dataframe(pd.DataFrame(ra), width="stretch", hide_index=True)
            else:
                st.caption("Không trích được căn cứ nào.")
        with q[1]:
            st.markdown("##### Văn bản khác căn cứ vào văn bản này")
            ra = [{"Số hiệu": G.nodes[b]["so_hieu"],
                   "Tiêu đề": G.nodes[b]["tieu_de"][:70],
                   "Quan hệ": G.edges[b, chon]["quan_he"]}
                  for b in G.predecessors(chon)]
            if ra:
                st.dataframe(pd.DataFrame(ra), width="stretch", hide_index=True)
            else:
                st.caption("Chưa có văn bản nào trong bộ căn cứ vào đây.")

        with st.expander("Xem toàn văn bản OCR đã làm sạch"):
            t = doc_van_ban(x["duong_dan"])
            st.caption("Nguồn: %s · %s ký tự" % (x["duong_dan"], "{:,}".format(len(t))))
            st.text_area("Toàn văn", t, height=460, label_visibility="collapsed")

# ── 4. Xuất Neo4j ────────────────────────────────────────────────────────────
with t4:
    st.subheader("Xuất đồ thị sang Neo4j")
    st.write("Sinh script Cypher dựng đủ 6 loại nút và 6 loại quan hệ theo đúng lược đồ "
             "trong `Xay-dung-graph-db.docx`. Dán vào Neo4j Browser hoặc chạy bằng "
             "`cypher-shell` là có ngay đồ thị để truy vấn.")
    if st.button("Sinh script Cypher", type="primary"):
        from xuat_neo4j import sinh_cypher
        s = sinh_cypher(G)
        st.success("Đã sinh %s dòng." % "{:,}".format(s.count("\n")))
        st.download_button("Tải cypher.cql", s, "do_thi_dut.cql", "text/plain")
        st.code(s[:2500] + "\n…", language="cypher")

    st.divider()
    st.subheader("Xuất GraphML")
    st.write("Dùng cho Gephi, Cytoscape hoặc `networkx.read_graphml`.")
    if st.button("Sinh GraphML"):
        import io
        Gx = G.copy()
        for _n, at in Gx.nodes(data=True):
            at["doi_tuong"] = ", ".join(at.get("doi_tuong") or [])
        buf = io.BytesIO()
        nx.write_graphml(Gx, buf, encoding="utf-8")
        st.download_button("Tải do_thi_dut.graphml", buf.getvalue(),
                           "do_thi_dut.graphml", "application/xml")
        st.success("Xong — %d nút, %d cạnh." % (Gx.number_of_nodes(), Gx.number_of_edges()))


# ── 5. Khám phá quan hệ ──────────────────────────────────────────────────────
with t5:
    st.caption("Bốn cách nhìn, mỗi cách trả lời một câu hỏi khác nhau. "
               "Vẽ cả 500 nút một lúc thì đẹp nhưng không đọc được gì — "
               "những biểu đồ dưới đây mới cho thấy cấu trúc.")
    k1, k2, k3, k4 = st.tabs(["Vùng lân cận", "Dòng chảy", "Chùm cùng căn cứ",
                              "Ma trận lĩnh vực"])

    # --- 5.1 vùng lân cận: chỉ vẽ 1 văn bản và hàng xóm ---
    with k1:
        st.markdown("##### Một văn bản liên quan tới những gì")
        trong_all = [n for n, x in G.nodes(data=True) if not x["ngoai_bo"]]
        a, b = st.columns([3, 1])
        with a:
            tam = st.selectbox(
                "Chọn văn bản làm tâm", sorted(trong_all, key=lambda n: -G.degree(n)),
                format_func=lambda n: "%s — %s  (%d liên kết)"
                % (G.nodes[n]["so_hieu"], G.nodes[n]["tieu_de"][:64], G.degree(n)))
        with b:
            buoc = st.slider("Số bước lan toả", 1, 3, 1,
                             help="1 bước = hàng xóm trực tiếp. 2 bước = hàng xóm "
                                  "của hàng xóm — đồ thị to lên rất nhanh.")
        E = KP.vung_lan_can(G, tam, buoc)
        st.caption("Vùng lân cận %d bước của %s: **%d nút · %d quan hệ**"
                   % (buoc, G.nodes[tam]["so_hieu"], E.number_of_nodes(),
                      E.number_of_edges()))
        chu_thich_cap()
        if E.number_of_nodes() > 1:
            st.iframe(khung_pyvis(E, pr, False, 620, tam=tam), height=644)
            st.caption("Nút viền đậm là văn bản đang chọn.")
        else:
            st.info("Văn bản này chưa có liên kết nào.")

    # --- 5.2 dòng chảy lĩnh vực → cấp → loại ---
    with k2:
        st.markdown("##### Lĩnh vực nào chịu điều chỉnh từ cấp nào")
        st.caption("Độ dày mỗi dải là số văn bản. Đọc từ trái sang: "
                   "lĩnh vực → cấp ban hành → loại văn bản.")
        st.plotly_chart(KP.sankey_linh_vuc_cap(G, trong_all2), width="stretch")
        st.divider()
        st.markdown("##### Hệ thống văn bản lớn lên theo thời gian")
        f = KP.dong_thoi_gian(G, trong_all2)
        if f:
            st.plotly_chart(f, width="stretch")

    # --- 5.3 chùm cùng căn cứ — câu hỏi trung tâm của đề tài ---
    with k3:
        st.markdown("##### Sửa một văn bản thì kéo theo bao nhiêu văn bản khác")
        toi_thieu = st.slider("Chỉ hiện chùm từ bao nhiêu văn bản trở lên", 3, 30, 5)
        chum = KP.chum_cung_can_cu(G, toi_thieu)
        if not chum:
            st.info("Không có chùm nào đạt ngưỡng này.")
        else:
            st.caption("**%d chùm**. Đây là câu hỏi trung tâm của đề tài: một căn cứ "
                       "hết hiệu lực thì cả chùm phải rà soát lại." % len(chum))
            st.plotly_chart(KP.bieu_do_chum(chum), width="stretch")
            cỡ = {n: len(c) for n, _x, c in chum}
            chon = st.selectbox(
                "Xem chi tiết một chùm", list(cỡ),
                format_func=lambda n: "%s — %d văn bản cùng căn cứ"
                % (G.nodes[n]["so_hieu"], cỡ[n]))
            ds = next(c for n, _x, c in chum if n == chon)
            st.dataframe(pd.DataFrame([
                {"Số hiệu": G.nodes[d]["so_hieu"], "Lĩnh vực": G.nodes[d]["linh_vuc"],
                 "Ngày": G.nodes[d]["ngay"], "Tiêu đề": G.nodes[d]["tieu_de"][:80]}
                for d in ds]), width="stretch", hide_index=True)

    # --- 5.4 ma trận liên kết giữa các lĩnh vực ---
    with k4:
        st.markdown("##### Lĩnh vực nào căn cứ vào lĩnh vực nào")
        st.caption("Ô đậm = nhiều quan hệ. Đường chéo là quan hệ trong cùng lĩnh vực; "
                   "ô ngoài đường chéo cho thấy các lĩnh vực phụ thuộc lẫn nhau.")
        st.plotly_chart(KP.ma_tran_lien_ket(G, trong_all2), width="stretch")
