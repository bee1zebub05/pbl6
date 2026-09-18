"""
Điều phối khối đánh giá + gom mọi thứ thành một báo cáo duy nhất.

`bao_cao()` là thứ đáng quan tâm nhất khi chạy ở máy khác: nó viết
`data/eval/BAO_CAO.md` — một file tự chứa, mở lên là biết đang ở đâu, phần nào
đã có số, phần nào còn chờ người gán.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..core import config
from ..core.console import say
from ..kg.session import KGSession
from . import errors, extraction, goldset, retrieval


def _driver():
    """Kết nối Neo4j. Trả None kèm lý do nếu không nối được."""

    try:
        from neo4j import GraphDatabase
    except ImportError:
        return None, "chưa cài driver — `pip install neo4j`"

    try:
        d = GraphDatabase.driver(
            config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )
        d.verify_connectivity()

        return d, None
    except Exception as exc:
        return None, f"không nối được {config.NEO4J_URI}: {str(exc)[:120]}"


# ============================================================
# TỪNG BƯỚC
# ============================================================

def sample(session: KGSession, args) -> dict:
    """§6.1 — chọn gold set phân tầng, sinh phiếu gán."""

    co_mau = None

    if args.co_mau:
        phan = [int(x) for x in args.co_mau.split(",")]
        co_mau = dict(zip("ABC", phan))

    return goldset.chay(session, co_mau, args.seed, _out(args) / "goldset")


def queries(args) -> dict:
    """§6.3 — sinh bộ câu hỏi, tự điền đáp án cho nhóm suy được từ metadata."""

    out = _out(args)
    path = out / "queries.csv"

    driver, loi = _driver()

    if not driver:
        return {"loi": loi}

    try:
        if path.exists() and not args.lam_lai:
            cau_hoi = retrieval.doc_cau_hoi(path)
            say(f"  Đã có {len(cau_hoi)} câu ở {path} — giữ nguyên phần người đã điền.")
        else:
            cau_hoi = retrieval.sinh_cau_hoi(driver, args.so_cau)
            say(f"  Sinh {len(cau_hoi)} câu hỏi mới.")

        n = retrieval.dien_dap_an_metadata(driver, cau_hoi)
        retrieval.ghi_cau_hoi(path, cau_hoi)
    finally:
        driver.close()

    thieu = sum(1 for q in cau_hoi if not (q.get("DAP_AN") or "").strip())

    say(f"  Máy tự điền đáp án cho {n} câu (nhóm suy được từ metadata).")
    say(f"  Còn {thieu} câu cần NGƯỜI điền cột DAP_AN.")
    say(f"  -> {path}")

    return {"so_cau": len(cau_hoi), "tu_dien": n, "can_nguoi_dien": thieu}


def run_retrieval(args) -> dict:
    """§6.4–6.5 — chạy BM25 / KG / Hybrid và chấm điểm."""

    out = _out(args)
    path = out / "queries.csv"

    if not path.exists():
        return {"loi": f"Chưa có {path} — chạy `python run.py eval queries` trước."}

    driver, loi = _driver()

    if not driver:
        return {"loi": loi}

    try:
        cau_hoi = retrieval.doc_cau_hoi(path)
        ket_qua = retrieval.chay(driver, cau_hoi, out)
    finally:
        driver.close()

    (out / "retrieval_metrics.json").write_text(
        json.dumps(ket_qua, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    bao_cao_path = retrieval.xuat_bao_cao(ket_qua, out)

    say(f"  {ket_qua['co_dap_an']}/{ket_qua['so_cau_hoi']} câu có đáp án, đã chấm.")
    say(f"  {bao_cao_path}")
    say(f"  {out / 'retrieval_runs.jsonl'}   (kết quả thô từng câu, để soi lỗi)")

    return ket_qua


def _out(args) -> Path:
    out = Path(args.output) if getattr(args, "output", None) else config.EVAL_DIR
    out.mkdir(parents=True, exist_ok=True)

    return out


# ============================================================
# BÁO CÁO GỘP
# ============================================================

def bao_cao(session: KGSession, out_dir: Path | None = None) -> Path:
    """Gom mọi số đo đã có thành một file duy nhất."""

    out_dir = out_dir or config.EVAL_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    def doc_json(ten: str):
        path = out_dir / ten

        if not path.exists():
            return None

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    ag = doc_json("agreement.json")
    ex = doc_json("extraction_metrics.json")
    rt = doc_json("retrieval_metrics.json")
    ab = doc_json("ablation.json")

    lines = [
        "# Báo cáo đánh giá — KG Văn bản pháp quy DUT/ĐHĐN",
        "",
        f"> Sinh tự động lúc {datetime.now():%d/%m/%Y %H:%M} bởi "
        "`python run.py eval all`",
        "> Đặc tả: [rules/Ontology.md](../../rules/Ontology.md) §6",
        "",
        "## Tình trạng từng phần",
        "",
        "| Phần §6 | Trạng thái |",
        "|---|---|",
    ]

    def trang_thai(co: bool, dieu_kien: str) -> str:
        return "✅ có số" if co else f"⬜ chờ {dieu_kien}"

    kappa_xong = bool(ag and "kappa_tong" in ag)
    ex_xong = bool(ex and "detection" in ex)
    rt_xong = bool(rt and rt.get("co_dap_an"))

    # Multi-hop phải xét riêng: nhóm này không tự sinh được đáp án (suy đáp án
    # từ chính graph rồi chấm graph là lập luận vòng tròn), nên rất dễ rơi vào
    # cảnh cả ba hệ đều 0.000 chỉ vì chưa ai điền đáp án — trông y như "cả ba
    # cùng trượt", trong khi thật ra là chưa chấm câu nào.
    multi_xong = bool(
        rt and any(k.startswith("multi-hop|") for k in rt.get("theo_nhom", {}))
    )

    lines += [
        f"| 6.1 Gold set + κ | {trang_thai(kappa_xong, 'hai người gán xong')} |",
        f"| 6.2 P/R/F1 extraction | {trang_thai(ex_xong, 'gold set')} |",
        f"| 6.3–6.4 BM25/KG/Hybrid | {trang_thai(rt_xong, 'đáp án bộ câu hỏi')} |",
        f"| 6.5 Multi-hop tách riêng | "
        f"{trang_thai(multi_xong, 'đáp án nhóm multi-hop (người điền)')} |",
        f"| 6.6 Ablation | {trang_thai(bool(ab), 'không cần gì thêm')} |",
        f"| 6.7 Error analysis | {trang_thai(bool(ab), 'không cần gì thêm')} |",
        "",
    ]

    if kappa_xong:
        lines += [
            "## §6.1 — Đồng thuận",
            "",
            f"Cohen's κ = **{ag['kappa_tong']:.3f}** trên {ag['cung_gan']} ứng viên "
            f"cả hai cùng gán (đồng thuận thô {ag['dong_thuan_tho']:.1%}).",
            "",
        ]

    if ex_xong:
        micro = ex["detection"].get("_TONG_micro", {})
        lines += [
            "## §6.2 — Trích xuất",
            "",
            f"Micro-F1 tầng detection: **{micro.get('F1', 0):.3f}** "
            f"(P {micro.get('P', 0):.3f} / R {micro.get('R', 0):.3f})",
            f"Độ chính xác resolution: "
            f"**{ex['resolution']['do_chinh_xac']:.1%}**",
            "",
            "| Quan hệ | P | R | F1 |",
            "|---|---|---|---|",
        ]

        for rel, m in ex["detection"].items():
            if not rel.startswith("_"):
                lines.append(
                    f"| `{rel}` | {m['P']:.3f} | {m['R']:.3f} | {m['F1']:.3f} |"
                )

        lines.append("")

    if rt_xong:
        lines += [
            "## §6.4 — Ba hệ tìm kiếm",
            "",
            "| Hệ | P@5 | R@10 | MRR | nDCG@10 |",
            "|---|---|---|---|---|",
        ]

        for he in ("bm25", "kg", "hybrid"):
            m = rt["tong_the"].get(he, {})
            lines.append(
                f"| **{he.upper()}** | {m.get('P@5', 0):.3f} | "
                f"{m.get('R@10', 0):.3f} | {m.get('MRR', 0):.3f} | "
                f"{m.get('nDCG@10', 0):.3f} |"
            )

        lines += ["", "### §6.5 — Riêng nhóm multi-hop", ""]

        if multi_xong:
            lines += ["| Hệ | P@5 | R@10 | MRR |", "|---|---|---|---|"]

            for he in ("bm25", "kg", "hybrid"):
                m = rt["theo_nhom"].get(f"multi-hop|{he}", {})
                lines.append(
                    f"| **{he.upper()}** | {m.get('P@5', 0):.3f} | "
                    f"{m.get('R@10', 0):.3f} | {m.get('MRR', 0):.3f} |"
                )
        else:
            lines += [
                "> ⬜ **Chưa chấm được câu nào.** Nhóm multi-hop không tự sinh",
                "> đáp án được — lấy đáp án từ chính graph rồi đem chấm graph là",
                "> lập luận vòng tròn. Phải người đọc văn bản rồi điền cột",
                "> `DAP_AN` trong `queries.csv`.",
                ">",
                "> Đây là nhóm **quan trọng nhất** của cả §6: chỗ KG/Hybrid phải",
                "> thắng BM25 rõ rệt, nếu không thì phải giải thích tại sao.",
            ]

        lines.append("")

    if ab:
        d = ab["day_du"]
        lines += [
            "## §6.6 — Ablation",
            "",
            f"Graph đầy đủ {d['canh']:,} cạnh. Bỏ cắt vùng mất "
            f"**{ab['bo_cat_vung']['mat_phan_tram']}%**, bỏ stub mất "
            f"**{ab['bo_stub']['mat_phan_tram']}%**.",
            "",
        ]

    lines += [
        "## File chi tiết",
        "",
        "| File | Nội dung |",
        "|---|---|",
        "| `extraction.md` | §6.1–6.2 đầy đủ, kèm bảng bất đồng giữa hai người gán |",
        "| `retrieval.md` | §6.3–6.5 đầy đủ, tách theo nhóm câu hỏi |",
        "| `ablation_va_loi.md` | §6.6–6.7 |",
        "| `retrieval_runs.jsonl` | kết quả thô từng câu × từng hệ, để soi lỗi |",
        "| `goldset/` | phiếu gán, hướng dẫn, phân tầng |",
        "| `*.json` | cùng số liệu ở dạng máy đọc được |",
        "",
    ]

    path = out_dir / "BAO_CAO.md"
    path.write_text("\n".join(lines), encoding="utf-8")

    return path


def chay_tat_ca(session: KGSession, args) -> int:
    """Chạy mọi thứ chạy được, bỏ qua êm phần còn thiếu đầu vào."""

    out = _out(args)

    say(f"\n{'#' * 62}\n# §6.1  GOLD SET + PHIẾU GÁN\n{'#' * 62}")
    sample(session, args)

    say(f"\n{'#' * 62}\n# §6.1-6.2  ĐỒNG THUẬN + P/R/F1\n{'#' * 62}")
    kq = extraction.xuat(out, out / "goldset")

    if "loi" in kq["metrics"]:
        say(f"  (chưa chấm được: {kq['metrics']['loi']})")

    say(f"\n{'#' * 62}\n# §6.3  BỘ CÂU HỎI\n{'#' * 62}")
    kq_q = queries(args)

    if "loi" in kq_q:
        say(f"  Bỏ qua: {kq_q['loi']}")

    say(f"\n{'#' * 62}\n# §6.4-6.5  BM25 / KG / HYBRID\n{'#' * 62}")
    kq_r = run_retrieval(args)

    if "loi" in kq_r:
        say(f"  Bỏ qua: {kq_r['loi']}")

    say(f"\n{'#' * 62}\n# §6.6-6.7  ABLATION + PHÂN TÍCH LỖI\n{'#' * 62}")
    errors.xuat(session, out)

    path = bao_cao(session, out)

    say(f"\n{'=' * 62}")
    say(f"  BÁO CÁO GỘP -> {path}")
    say(f"  Toàn bộ kết quả nằm trong {out}  — copy nguyên thư mục này là đủ.")
    say(f"{'=' * 62}\n")

    return 0
