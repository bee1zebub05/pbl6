"""
Vẽ knowledge graph mô tả trong `rules/Ontology.md` (v0.3 — Mức 3 / Paper).

Hai chế độ:

    python scripts/viz_ontology.py              # sơ đồ ONTOLOGY (schema)
    python scripts/viz_ontology.py --data       # đồ thị THỰC TẾ từ manifest.jsonl

Chế độ schema vẽ đúng 7 node type + 12 quan hệ trong §2 và §4, tô màu cạnh
theo cột "Độ khó" của bảng §4 — vì đó mới là thông tin dùng để lập kế hoạch:
nhìn một cái là thấy phần nào lấy được ngay từ metadata, phần nào phải chờ
OCR + NLP.

Chỉ dùng matplotlib + networkx + numpy, cả ba đã có sẵn (easyocr kéo theo),
không cần cài thêm.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "manifest.jsonl"
OUT_DIR = ROOT / "docs"


# ============================================================
# BẢNG MÀU
# ============================================================

# Màu node theo vai trò trong ontology.
COLOR = {
    "core": "#1d4ed8",      # Document — trung tâm
    "actor": "#7c3aed",     # Organization, Person
    "facet": "#0891b2",     # Topic, TargetGroup
    "content": "#c2410c",   # NormativeContent, Article (mới ở Mức 3)
}

# Màu cạnh theo cột "Độ khó" ở §4 — dùng để đọc lộ trình P1..P5 (§8).
DIFFICULTY = {
    "dễ": "#15803d",
    "TB": "#b45309",
    "khó": "#b91c1c",
}


def setup_font() -> None:
    """
    Chọn font có dấu tiếng Việt.

    DejaVu Sans (mặc định của matplotlib) phủ đủ Latin Extended Additional nên
    luôn dùng được; ưu tiên font hệ thống Windows cho đẹp hơn.
    """

    available = {f.name for f in matplotlib.font_manager.fontManager.ttflist}

    for name in ("Segoe UI", "Tahoma", "Arial", "DejaVu Sans"):
        if name in available:
            matplotlib.rcParams["font.family"] = name
            return


# ============================================================
# ONTOLOGY — chép từ rules/Ontology.md §2 và §4
# ============================================================

# Chiều cao hộp suy ra từ số property nên không bao giờ chồng chữ.
LINE_H = 0.27
HEAD_H = 0.74
PAD_H = 0.20

# name -> (x tâm, y tâm, rộng, nhóm màu, danh sách property)
NODES: dict[str, tuple] = {
    "Document": (
        0.0, 0.0, 3.7, "core",
        [
            "so_hieu_norm (PK)",
            "title, abstract",
            "documentType (enum)",
            "authority_level (1–6)",
            "status",
            "issueDate / effectiveDate",
            "expiryDate, fileUrl",
            "noi_dung_raw, is_stub",
        ],
    ),
    "Person": (
        0.0, 4.6, 2.9, "actor",
        ["personId", "fullName", "position", "academicTitle"],
    ),
    "Organization": (
        6.1, 2.5, 3.2, "actor",
        ["orgId", "name", "orgType", "parentOrg"],
    ),
    "Topic": (
        -6.1, 2.5, 3.2, "facet",
        ["topicId", "name", "description", "(18 lĩnh vực thật)"],
    ),
    "TargetGroup": (
        -6.1, -2.3, 3.2, "facet",
        ["targetGroupId", "name", "description", "level"],
    ),
    "NormativeContent": (
        6.1, -2.4, 3.4, "content",
        ["contentId", "contentType", "title", "status"],
    ),
    "Article": (
        6.1, -5.6, 2.9, "content",
        ["articleId", "number", "heading", "text"],
    ),
}

# (from, to, nhãn, cardinality, độ khó, độ cong, dịch nhãn (dx, dy))
EDGES: list[tuple] = [
    ("Document", "Person", "SIGNED_BY", "n→1", "TB", 0.0, (0.0, 0.0)),
    ("Document", "Organization", "ISSUED_BY", "n→1", "dễ", 0.0, (0.0, 0.0)),
    ("Document", "Topic", "HAS_TOPIC", "n→m", "dễ", 0.0, (0.0, 0.0)),
    ("Document", "TargetGroup", "APPLIES_TO", "n→m", "khó", 0.0, (0.0, 0.0)),
    ("Document", "NormativeContent", "PROMULGATES", "1→1", "dễ", 0.0, (0.0, 0.0)),
    ("NormativeContent", "Article", "HAS_ARTICLE", "1→n", "TB", 0.0, (0.0, 0.0)),
    # AMENDS trỏ được tới từng Điều, không chỉ tới cả văn bản (§4). Bẻ cong
    # mạnh xuống dưới để không cắt ngang qua NormativeContent; nhãn đẩy sang
    # trái để không dính vào viền hộp đó.
    ("Document", "Article", "AMENDS", "n→m", "khó", 0.55, (-1.35, -0.55)),
]

# Năm quan hệ Document -> Document. Vẽ rời từng self-loop thì rối, nên gom
# thành một cụm có chú thích riêng.
SELF_RELATIONS = [
    ("BASED_ON", "n→m", "TB", 'phần "Căn cứ" đầu VB'),
    ("REFERENCES", "n→m", "TB", "số hiệu trong thân VB"),
    ("REPLACES / REPLACED_BY", "n→m", "khó", "thay thế → B hết hiệu lực"),
    ("AMENDS / AMENDED_BY", "n→m", "khó", "sửa đổi → B VẪN hiệu lực"),
    ("REPEALS / REPEALED_BY", "n→m", "khó", "bãi bỏ → B hết, không VB thay"),
]

AUTHORITY = [
    ("Hiến pháp", 6),
    ("Luật, Pháp lệnh", 5),
    ("Nghị định", 4),
    ("Thông tư / QĐ-TTg", 3),
    ("VB Đại học Đà Nẵng", 2),
    ("VB Trường ĐHBK", 1),
]


# ============================================================
# VẼ SCHEMA
# ============================================================

def _dims(name: str) -> tuple[float, float, float, float]:
    """(x tâm, y tâm, rộng, cao) — cao tính từ số property."""

    x, y, w, _, props = NODES[name]

    return x, y, w, HEAD_H + len(props) * LINE_H + PAD_H


def _anchor(node: str, toward: tuple[float, float]) -> tuple[float, float]:
    """
    Điểm trên viền hộp `node` nằm trên đường nối tâm hộp tới `toward`.

    Cần thiết để mũi tên dừng ở mép hộp thay vì đâm vào giữa chữ.
    """

    x, y, w, h = _dims(node)
    dx, dy = toward[0] - x, toward[1] - y

    if dx == 0 and dy == 0:
        return x, y

    # Tỷ lệ để chạm cạnh đứng / cạnh ngang, lấy cái chạm trước.
    scale_x = (w / 2) / abs(dx) if dx else float("inf")
    scale_y = (h / 2) / abs(dy) if dy else float("inf")
    scale = min(scale_x, scale_y)

    return x + dx * scale, y + dy * scale


def _panel(ax, x0: float, y_top: float, width: float, height: float, title: str) -> None:
    """Khung chú thích nền xám kèm tiêu đề."""

    ax.add_patch(
        FancyBboxPatch(
            (x0, y_top - height),
            width,
            height,
            boxstyle="round,pad=0.1,rounding_size=0.14",
            linewidth=1.3,
            edgecolor="#94a3b8",
            facecolor="#f8fafc",
            zorder=3,
        )
    )

    ax.text(
        x0 + 0.28,
        y_top - 0.34,
        title,
        fontsize=9.2,
        fontweight="bold",
        color="#0f172a",
        va="center",
        zorder=4,
    )


def _draw_node(ax, name: str) -> None:
    x, y, w, h = _dims(name)
    group, props = NODES[name][3], NODES[name][4]
    color = COLOR[group]
    top = y + h / 2

    ax.add_patch(
        FancyBboxPatch(
            (x - w / 2, y - h / 2),
            w,
            h,
            boxstyle="round,pad=0.06,rounding_size=0.18",
            linewidth=1.8,
            edgecolor=color,
            facecolor=color + "14",  # cùng màu, alpha thấp (hex 8 chữ số)
            zorder=3,
        )
    )

    ax.text(
        x, top - 0.30, name,
        ha="center", va="center",
        fontsize=11.5, fontweight="bold", color=color, zorder=4,
    )

    ax.plot(
        [x - w / 2 + 0.20, x + w / 2 - 0.20],
        [top - 0.56, top - 0.56],
        color=color, linewidth=0.9, alpha=0.45, zorder=4,
    )

    for i, prop in enumerate(props):
        ax.text(
            x, top - HEAD_H - i * LINE_H - LINE_H / 2, prop,
            ha="center", va="center",
            fontsize=7.6, color="#334155", zorder=4,
        )


def _draw_edge(
    ax,
    src: str,
    dst: str,
    label: str,
    card: str,
    level: str,
    rad: float,
    shift: tuple[float, float] = (0.0, 0.0),
) -> None:
    color = DIFFICULTY[level]
    dx, dy, _, _ = _dims(dst)
    p_src = _anchor(src, (dx, dy))
    sx, sy, _, _ = _dims(src)
    p_dst = _anchor(dst, (sx, sy))

    ax.add_patch(
        FancyArrowPatch(
            p_src, p_dst,
            connectionstyle=f"arc3,rad={rad}",
            arrowstyle="-|>",
            mutation_scale=15,
            linewidth=1.7,
            color=color,
            zorder=2,
        )
    )

    # Nhãn đặt ở đỉnh cung (trung điểm đẩy lệch theo độ cong).
    mid_x = (p_src[0] + p_dst[0]) / 2
    mid_y = (p_src[1] + p_dst[1]) / 2
    vec_x, vec_y = p_dst[0] - p_src[0], p_dst[1] - p_src[1]
    mid_x += -vec_y * rad * 0.5 + shift[0]
    mid_y += vec_x * rad * 0.5 + shift[1]

    ax.text(
        mid_x, mid_y, f"{label}\n{card}",
        ha="center", va="center",
        fontsize=7.8, fontweight="bold", color=color, linespacing=1.35,
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="none", alpha=0.94),
        zorder=5,
    )


def _draw_self_loop(ax, node: str, label: str, level: str, side: str = "top") -> None:
    """
    Self-loop cho quan hệ nội bộ một node (`PART_OF`, cụm Document↔Document).

    Vẽ bằng đường tròn tham số chứ không dùng `arc3` — hai đầu cung trùng cạnh
    hộp khiến `arc3` bẻ ngược vào trong, đè lên chữ.
    """

    x, y, w, h = _dims(node)
    color = DIFFICULTY[level]
    sign = 1 if side == "top" else -1
    radius = 0.46
    cx, cy = x, y + sign * (h / 2 + radius * 0.72)

    # Chừa một khoảng hở ở chân vòng để đặt mũi tên.
    theta = np.linspace(np.pi * 0.62, np.pi * 2.34, 140)
    xs, ys = cx + radius * np.cos(theta), cy + radius * np.sin(theta)

    ax.plot(xs, ys, color=color, linewidth=1.7, zorder=2, solid_capstyle="round")
    ax.annotate(
        "",
        xy=(xs[-1], ys[-1]),
        xytext=(xs[-6], ys[-6]),
        arrowprops=dict(arrowstyle="-|>", color=color, linewidth=1.7, mutation_scale=14),
        zorder=2,
    )

    ax.text(
        cx, cy + sign * (radius + 0.34), label,
        ha="center", va="center",
        fontsize=7.8, fontweight="bold", color=color,
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.94),
        zorder=5,
    )


def _draw_self_relation_panel(ax) -> None:
    """Bảng 5 quan hệ Document -> Document, kèm dấu hiệu nhận biết."""

    x0, y_top, width = -10.4, -3.6, 7.4
    _panel(ax, x0, y_top, width, 2.65, "Document → Document  (self-loop)")

    for i, (name, card, level, hint) in enumerate(SELF_RELATIONS):
        row_y = y_top - 0.78 - i * 0.37

        ax.text(
            x0 + 0.38, row_y, f"{name}  {card}",
            fontsize=7.6, fontweight="bold", color=DIFFICULTY[level],
            va="center", zorder=4,
        )
        ax.text(
            x0 + 3.95, row_y, hint,
            fontsize=7.0, color="#475569", va="center", zorder=4,
        )


def _draw_authority_panel(ax) -> None:
    """Thang authority_level (§3) — property của Document, không phải node."""

    x0, y_top, width = -10.4, 7.4, 6.6
    _panel(ax, x0, y_top, width, 2.75, "Document.authority_level   (property, không phải node)")

    bar_x = x0 + 3.9
    unit = 0.34

    for i, (kind, level) in enumerate(AUTHORITY):
        row_y = y_top - 0.82 - i * 0.36

        ax.text(x0 + 0.38, row_y, kind, fontsize=7.4, color="#334155", va="center", zorder=4)
        ax.add_patch(
            FancyBboxPatch(
                (bar_x, row_y - 0.11),
                level * unit,
                0.22,
                boxstyle="square,pad=0",
                linewidth=0,
                facecolor=COLOR["core"],
                alpha=0.25 + 0.11 * level,
                zorder=4,
            )
        )
        ax.text(
            bar_x + level * unit + 0.14, row_y, str(level),
            fontsize=7.4, fontweight="bold", color="#334155", va="center", zorder=4,
        )


def draw_schema(out_path: Path) -> Path:
    """Vẽ sơ đồ ontology và ghi ra file ảnh."""

    fig, ax = plt.subplots(figsize=(18, 12))

    _draw_self_relation_panel(ax)
    _draw_authority_panel(ax)

    for src, dst, label, card, level, rad, shift in EDGES:
        _draw_edge(ax, src, dst, label, card, level, rad, shift)

    _draw_self_loop(ax, "Organization", "PART_OF  n→1", "dễ", side="top")
    _draw_self_loop(ax, "Document", "5 quan hệ — xem bảng dưới", "khó", side="bottom")

    for name in NODES:
        _draw_node(ax, name)

    ax.set_title(
        "Ontology v0.3 — Knowledge Graph văn bản pháp quy DUT/ĐHĐN\n"
        "7 node type · 12 quan hệ · màu cạnh = độ khó trích xuất (§4)",
        fontsize=15,
        fontweight="bold",
        color="#0f172a",
        pad=16,
    )

    handles = [
        plt.Line2D([], [], color=color, linewidth=2.8, label=f"Độ khó: {name}")
        for name, color in DIFFICULTY.items()
    ]
    handles += [
        plt.Line2D([], [], marker="s", linestyle="", markersize=9, color=color, label=label)
        for label, color in (
            ("Document (trung tâm)", COLOR["core"]),
            ("Chủ thể", COLOR["actor"]),
            ("Phân loại", COLOR["facet"]),
            ("Nội dung (mới ở Mức 3)", COLOR["content"]),
        )
    ]

    ax.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(0.63, 1.0),
        fontsize=8.6,
        framealpha=0.96,
        ncol=2,
        borderpad=0.7,
    )

    ax.set_xlim(-10.8, 10.4)
    ax.set_ylim(-7.6, 7.8)
    ax.set_aspect("equal")
    ax.axis("off")

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return out_path


# ============================================================
# VẼ ĐỒ THỊ THỰC TẾ TỪ MANIFEST
# ============================================================

COLUMN_X = 1.5
COLUMN_HALF_HEIGHT = 1.35


def _column_positions(graph) -> dict[str, np.ndarray]:
    """
    Ghim hub thành hai cột dọc: Organization bên trái, Topic bên phải.

    Vòng tròn nghe hợp lý hơn nhưng dùng thật thì hỏng: ở hai đầu cung khoảng
    cách theo trục dọc tiến về 0 nên nhãn chồng lên nhau, mà nhãn ở đây là tên
    cơ quan dài. Cột dọc cho khoảng cách đều tuyệt đối, và chừa hẳn lề trái /
    lề phải trống để nhãn trải ra ngoài.

    Hub lớn xếp vào giữa cột — đó là nơi Document tụ đông nhất.
    """

    positions: dict[str, np.ndarray] = {}

    for kind, x in (("Organization", -COLUMN_X), ("Topic", COLUMN_X)):
        hubs = [n for n, d in graph.nodes(data=True) if d["kind"] == kind]
        hubs.sort(key=lambda n: graph.in_degree(n), reverse=True)

        # Xếp từ giữa ra hai đầu: lớn nhất ở giữa, nhỏ dần về hai phía.
        upper, lower = hubs[0::2], hubs[1::2]
        ordered = upper[::-1] + lower

        count = max(len(ordered), 1)

        for i, node in enumerate(ordered):
            frac = 0.5 if count == 1 else i / (count - 1)
            y = COLUMN_HALF_HEIGHT * (1 - 2 * frac)
            positions[node] = np.array([x, y])

    return positions


def draw_instance(out_path: Path, limit: int) -> Path:
    """
    Vẽ đồ thị thật từ `data/manifest.jsonl`.

    Chỉ dựng được 2 quan hệ dễ nhất trong ontology — `ISSUED_BY` và
    `HAS_TOPIC` — vì đó là phần lấy thẳng từ metadata crawler (giai đoạn P1
    trong §8). Các quan hệ `BASED_ON` / `REFERENCES` / hiệu lực phải chờ P2–P3,
    khi đã trích được số hiệu từ thân văn bản.
    """

    import networkx as nx

    if not MANIFEST.exists():
        raise FileNotFoundError(f"Không tìm thấy {MANIFEST}")

    rows = [json.loads(line) for line in MANIFEST.open(encoding="utf-8")]
    rows = [r for r in rows if r.get("so_hieu")][:limit]

    graph = nx.DiGraph()

    for row in rows:
        doc = row["so_hieu"]
        graph.add_node(doc, kind="Document")

        org = (row.get("co_quan_ban_hanh") or "").strip()

        if org:
            graph.add_node(org, kind="Organization")
            graph.add_edge(doc, org, rel="ISSUED_BY")

        topic = (row.get("linh_vuc") or "").strip()

        if topic:
            graph.add_node(topic, kind="Topic")
            graph.add_edge(doc, topic, rel="HAS_TOPIC")

    kind_color = {
        "Document": COLOR["core"],
        "Organization": COLOR["actor"],
        "Topic": COLOR["facet"],
    }

    # Document nhiều và nằm ngoài rìa -> vẽ nhỏ; Organization/Topic là hub ->
    # vẽ to theo bậc để thấy ngay đơn vị nào ban hành nhiều nhất.
    sizes, colors = [], []

    for node, data in graph.nodes(data=True):
        kind = data["kind"]
        colors.append(kind_color[kind])

        # Căn bậc hai chứ không tuyến tính: Bộ GD&ĐT có ~136 văn bản, tỷ lệ
        # thẳng sẽ cho một hình tròn nuốt trọn nửa cột.
        sizes.append(
            55 if kind == "Document" else 120 + 90 * graph.in_degree(node) ** 0.5
        )

    fig, ax = plt.subplots(figsize=(17, 13))

    # Spring layout thuần dồn hub vào một góc, nhãn chồng nhau không đọc được.
    # Thay bằng: ghim hub thành hai cột rồi để spring xếp Document vào giữa.
    # Mỗi Document nối đúng một Organization và một Topic nên nó tự rơi vào
    # khoảng giữa — đọc được ngay "đơn vị nào ban hành về lĩnh vực nào".
    fixed = _column_positions(graph)
    pos = nx.spring_layout(
        graph,
        pos=fixed,
        fixed=list(fixed),
        k=0.30,
        iterations=200,
        seed=42,
    )

    nx.draw_networkx_edges(graph, pos, ax=ax, edge_color="#cbd5e1", width=0.5, arrows=False)
    nx.draw_networkx_nodes(graph, pos, ax=ax, node_color=colors, node_size=sizes, linewidths=0)

    # Chỉ ghi nhãn cho hub — 500 nhãn Document chồng lên nhau thì vô dụng.
    # Nhãn đẩy hẳn ra ngoài cột, quay lưng vào giữa, nên không đè lên cạnh.
    for kind, align, offset in (
        ("Organization", "right", -0.16),
        ("Topic", "left", 0.16),
    ):
        for node, data in graph.nodes(data=True):
            if data["kind"] != kind:
                continue

            x, y = pos[node]
            ax.text(
                x + offset, y, f"{node}  ({graph.in_degree(node)})",
                ha=align, va="center",
                fontsize=8.5, fontweight="bold", color="#0f172a",
                zorder=5,
            )

    counts = {k: 0 for k in kind_color}

    for _, data in graph.nodes(data=True):
        counts[data["kind"]] += 1

    ax.set_title(
        f"KG thực tế từ manifest.jsonl — {counts['Document']} Document · "
        f"{counts['Organization']} Organization · {counts['Topic']} Topic · "
        f"{graph.number_of_edges()} cạnh\n"
        "Mới dựng được ISSUED_BY + HAS_TOPIC (giai đoạn P1); "
        "quan hệ giữa các văn bản cần P2–P3",
        fontsize=13,
        fontweight="bold",
        color="#0f172a",
        pad=16,
    )

    ax.legend(
        handles=[
            plt.Line2D([], [], marker="o", linestyle="", markersize=9, color=color, label=kind)
            for kind, color in kind_color.items()
        ],
        loc="lower right",
        fontsize=9,
    )

    # Nhãn vẽ bằng ax.text nên không được tính vào autoscale — phải tự chừa lề
    # hai bên, nếu không tên cơ quan dài sẽ bị cắt cụt.
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]

    ax.set_xlim(min(xs) - 2.6, max(xs) + 2.6)
    ax.set_ylim(min(ys) - 0.35, max(ys) + 0.35)

    ax.axis("off")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return out_path


# ============================================================
# CLI
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vẽ knowledge graph mô tả trong rules/Ontology.md",
    )
    parser.add_argument(
        "--data",
        action="store_true",
        help="Vẽ đồ thị thật từ data/manifest.jsonl thay vì sơ đồ ontology",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Số văn bản tối đa khi dùng --data (mặc định 500)",
    )
    parser.add_argument("--out", type=Path, help="Đường dẫn file ảnh đầu ra")

    args = parser.parse_args()
    setup_font()

    if args.data:
        out = args.out or OUT_DIR / "kg_instance.png"
        path = draw_instance(out, args.limit)
    else:
        out = args.out or OUT_DIR / "kg_ontology.png"
        path = draw_schema(out)

    print(f"Đã ghi: {path.relative_to(ROOT).as_posix()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
