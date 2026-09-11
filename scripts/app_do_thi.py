"""
App trực quan hoá knowledge graph — đọc thẳng từ Neo4j.

    pip install streamlit pyvis networkx
    streamlit run scripts/app_do_thi.py

Khác `scripts/viz_ontology.py`: cái đó vẽ SƠ ĐỒ LƯỢC ĐỒ (7 node type, 12 quan
hệ) — dùng để trình bày thiết kế. Cái này duyệt DỮ LIỆU THẬT đã nạp vào graph,
lọc và đi theo cạnh được, dùng để tra cứu và để soi lỗi trích xuất.

MỘT CHI TIẾT KHÔNG HIỂN NHIÊN: vis.js mặc định chạy physics mãi không dừng, đồ
thị vài trăm nút cứ rung liên tục, không đọc nổi và ăn hết CPU. Phải chèn tay
đoạn tắt physics sau khi ổn định — xem `dong_bang_physics`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vanban import config  # noqa: E402

st.set_page_config(page_title="KG văn bản pháp quy DUT", layout="wide")

# Thang thẩm quyền của Ontology §3 — số càng lớn càng cao.
MUC_TEN = {
    6: "Hiến pháp",
    5: "Luật, Pháp lệnh",
    4: "Nghị định",
    3: "Thông tư / QĐ-TTg",
    2: "VB Đại học Đà Nẵng",
    1: "VB Trường ĐHBK",
    0: "Chưa xếp được",
}
MUC_MAU = {
    6: "#1B2A4A", 5: "#2F5D80", 4: "#3E8B8A",
    3: "#7BA45F", 2: "#C1902F", 1: "#B8663A", 0: "#9AA3AD",
}
MAU_HIEU_LUC = "#B8332B"


@st.cache_resource
def mo_driver():
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
    )
    driver.verify_connectivity()

    return driver


def hoi(cypher: str, **tham_so) -> list[dict]:
    with mo_driver().session(database=config.NEO4J_DATABASE) as s:
        return [dict(r) for r in s.run(cypher, **tham_so)]


@st.cache_data(ttl=300)
def nap_van_ban() -> list[dict]:
    return hoi(
        """
        MATCH (d:Document)
        OPTIONAL MATCH (d)-[:HAS_TOPIC]->(t:Topic)
        OPTIONAL MATCH (d)-[:ISSUED_BY]->(o:Organization)
        RETURN d.so_hieu            AS so_hieu,
               coalesce(d.title, d.trich_yeu, '') AS tieu_de,
               coalesce(d.authority_level, 0)     AS muc,
               coalesce(d.is_stub, false)         AS la_stub,
               substring(coalesce(d.issueDate, ''), 0, 4) AS nam,
               collect(DISTINCT t.name)[0]        AS linh_vuc,
               collect(DISTINCT o.name)[0]        AS co_quan
        """
    )


@st.cache_data(ttl=300)
def nap_canh() -> list[dict]:
    return hoi(
        """
        MATCH (a:Document)-[r]->(b:Document)
        RETURN a.so_hieu AS tu, b.so_hieu AS den, type(r) AS quan_he
        """
    )


def dong_bang_physics(html: str) -> str:
    """Tắt physics sau khi đồ thị ổn định.

    Không làm thì vis.js rung mãi: vài trăm nút là không đọc nổi chữ và CPU
    chạy hết công suất cho tới khi đóng tab. `stabilizationIterationsDone`
    không phải lúc nào cũng bắn (đồ thị nhỏ ổn định trước khi listener gắn
    xong), nên đặt thêm một mốc thời gian làm chốt chặn.
    """

    neo = "network = new vis.Network(container, data, options);"

    if neo not in html:
        return html

    return html.replace(
        neo,
        neo
        + """
        network.once("stabilizationIterationsDone", function () {
            network.setOptions({physics: {enabled: false}});
        });
        setTimeout(function () {
            network.setOptions({physics: {enabled: false}});
        }, 8000);""",
        1,
    )


def ve(nut: list[dict], canh: list[dict], cao: int = 620) -> None:
    from pyvis.network import Network

    net = Network(height=f"{cao}px", width="100%", directed=True,
                  bgcolor="#FFFFFF", font_color="#222222")
    net.barnes_hut(gravity=-9000, spring_length=150)

    co = {n["so_hieu"] for n in nut}

    for n in nut:
        muc = int(n["muc"] or 0)
        nhan = n["so_hieu"] or "?"
        title = f"{nhan}\n{(n.get('tieu_de') or '')[:120]}\n{MUC_TEN.get(muc, '')}"
        net.add_node(
            nhan,
            label=nhan,
            title=title,
            color=MUC_MAU.get(muc, "#9AA3AD"),
            shape="dot" if not n.get("la_stub") else "diamond",
            size=12 if not n.get("la_stub") else 8,
        )

    for c in canh:
        if c["tu"] not in co or c["den"] not in co:
            continue

        la_hieu_luc = c["quan_he"] in ("REPLACES", "AMENDS", "REPEALS")
        net.add_edge(
            c["tu"], c["den"],
            title=c["quan_he"],
            color=MAU_HIEU_LUC if la_hieu_luc else "#C3CBD4",
            dashes=la_hieu_luc,
            width=2 if la_hieu_luc else 1,
        )

    st.components.v1.html(dong_bang_physics(net.generate_html()), height=cao + 20)


# --------------------------------------------------------------------------

st.title("Đồ thị tri thức văn bản pháp quy — Trường ĐH Bách khoa, ĐHĐN")

try:
    van_ban = nap_van_ban()
    canh = nap_canh()
except Exception as exc:
    st.error(
        f"Không kết nối được Neo4j tại `{config.NEO4J_URI}`.\n\n"
        f"`{type(exc).__name__}: {exc}`\n\n"
        "Khởi động graph rồi nạp dữ liệu:\n\n"
        "```\n"
        "docker run -d -p 7474:7474 -p 7687:7687 "
        "-e NEO4J_AUTH=neo4j/12345678 neo4j:5\n"
        "python run.py kg load\n"
        "```"
    )
    st.stop()

if not van_ban:
    st.warning("Graph rỗng. Chạy `python run.py kg load` trước.")
    st.stop()

that = [v for v in van_ban if not v["la_stub"]]
linh_vuc = sorted({v["linh_vuc"] for v in that if v["linh_vuc"]})
nam_co = sorted({v["nam"] for v in that if v["nam"]})

with st.sidebar:
    st.header("Bộ lọc")
    chon_lv = st.multiselect("Lĩnh vực", linh_vuc)
    chon_muc = st.multiselect(
        "Cấp thẩm quyền",
        sorted(MUC_TEN, reverse=True),
        format_func=lambda m: f"{m} — {MUC_TEN[m]}",
    )
    tim = st.text_input("Tìm trong số hiệu / trích yếu")
    hien_stub = st.checkbox("Hiện văn bản stub (bị viện dẫn, chưa crawl)", value=True)
    toi_da = st.slider("Số nút tối đa vẽ", 50, 600, 250, step=50)

lo = van_ban if hien_stub else that

if chon_lv:
    lo = [v for v in lo if v["la_stub"] or v["linh_vuc"] in chon_lv]

if chon_muc:
    lo = [v for v in lo if int(v["muc"] or 0) in chon_muc]

if tim:
    k = tim.lower()
    lo = [v for v in lo
          if k in (v["so_hieu"] or "").lower() or k in (v["tieu_de"] or "").lower()]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Văn bản", f"{len(that):,}")
c2.metric("Stub", f"{len(van_ban) - len(that):,}")
c3.metric("Quan hệ", f"{len(canh):,}")
c4.metric("Đang lọc", f"{len(lo):,}")

tab1, tab2, tab3 = st.tabs(["Đồ thị", "Vùng lân cận", "Chuỗi hiệu lực"])

with tab1:
    if len(lo) > toi_da:
        # Giữ lại nút NHIỀU LIÊN KẾT NHẤT, không cắt bừa theo thứ tự: cắt bừa
        # thì phần còn lại rời rạc, nhìn như graph không có cạnh nào.
        bac: dict[str, int] = {}

        for c in canh:
            bac[c["tu"]] = bac.get(c["tu"], 0) + 1
            bac[c["den"]] = bac.get(c["den"], 0) + 1

        lo_ve = sorted(lo, key=lambda v: -bac.get(v["so_hieu"], 0))[:toi_da]
        st.caption(
            f"Đang vẽ {toi_da} nút nhiều liên kết nhất trong {len(lo):,} nút khớp lọc."
        )
    else:
        lo_ve = lo

    ve(lo_ve, canh)
    st.caption("Nét đứt đỏ = quan hệ hiệu lực (REPLACES / AMENDS / REPEALS). "
               "Hình thoi = văn bản stub. Màu theo cấp thẩm quyền.")

with tab2:
    ds = sorted(v["so_hieu"] for v in that if v["so_hieu"])
    chon = st.selectbox("Chọn một văn bản", ds)

    if chon:
        quanh = {chon}

        for c in canh:
            if c["tu"] == chon:
                quanh.add(c["den"])
            elif c["den"] == chon:
                quanh.add(c["tu"])

        ve([v for v in van_ban if v["so_hieu"] in quanh], canh, cao=520)

        vao = [c for c in canh if c["den"] == chon]
        ra_ = [c for c in canh if c["tu"] == chon]
        a, b = st.columns(2)
        a.write(f"**{len(vao)} văn bản trỏ tới đây**")
        a.dataframe([{"Từ": c["tu"], "Quan hệ": c["quan_he"]} for c in vao],
                    use_container_width=True)
        b.write(f"**Đây trỏ tới {len(ra_)} văn bản**")
        b.dataframe([{"Tới": c["den"], "Quan hệ": c["quan_he"]} for c in ra_],
                    use_container_width=True)

with tab3:
    hl = [c for c in canh if c["quan_he"] in ("REPLACES", "AMENDS", "REPEALS")]
    st.write(f"**{len(hl)} quan hệ hiệu lực**")

    if hl:
        st.dataframe(
            [{"Văn bản": c["tu"], "Quan hệ": c["quan_he"], "Tác động lên": c["den"]}
             for c in hl],
            use_container_width=True, height=420,
        )
        st.caption(
            "REPLACES = B hết hiệu lực, A thế chỗ · "
            "AMENDS = B VẪN hiệu lực, chỉ đổi vài điều · "
            "REPEALS = B hết hiệu lực, không ai thế chỗ"
        )
    else:
        st.info("Chưa có quan hệ hiệu lực nào trong graph.")
