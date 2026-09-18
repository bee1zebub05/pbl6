"""
§6.6–6.7 — ablation và phân tích lỗi.

Khác với §6.1–6.2, phần lớn nội dung ở đây **không cần người gán** — nó đo trên
chính trạng thái đã có trong `kg.db`, nên chạy được ngay và cho ra con số đưa
thẳng vào paper.

## Ablation (§6.6) làm bằng cách đếm lại, không phải chạy lại

§6.6 muốn biết "bỏ thành phần X đi thì tụt bao nhiêu". Với các thành phần ở đây
không cần chạy lại cả pipeline: mỗi trích dẫn đã lưu sẵn vùng chứa nó, cờ điều
khoản thi hành, và việc nó có nối được hay không — nên chỉ cần đếm lại tập con
tương ứng là ra ngay con số "còn lại bao nhiêu cạnh nếu thiếu X".

Bốn thành phần đo được theo cách này:

    -cắt vùng          bỏ Bước 1 -> không phân biệt Căn cứ / thi hành nữa
    -quan hệ hiệu lực  gộp REPLACES/AMENDS/REPEALS về REFERENCES
    -stub              chỉ giữ cạnh nối vào 450 văn bản đã crawl
    -authority_level   không xếp hạng được văn bản gốc

Riêng `-OCR` thì không đo kiểu này được: phải OCR lại toàn kho bằng lớp text
gốc của PDF, mà PDF đã bị xoá khỏi máy. Ghi rõ trong báo cáo là chưa đo được.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ..core import config
from ..core.console import say
from ..kg.session import KGSession


# ============================================================
# ABLATION (§6.6)
# ============================================================

def ablation(session: KGSession) -> dict:
    with session._lock:  # noqa: SLF001
        conn = session._conn  # noqa: SLF001

        def dem(sql: str, *args) -> int:
            return conn.execute(sql, args).fetchone()[0]

        day_du = dem(
            "SELECT COUNT(*) FROM (SELECT DISTINCT doc_key, target_key, relation "
            "FROM citations WHERE relation IS NOT NULL AND resolved = 1)"
        )
        canh_hieu_luc = dem(
            "SELECT COUNT(*) FROM (SELECT DISTINCT doc_key, target_key, relation "
            "FROM citations WHERE relation IN ('REPLACES','AMENDS','REPEALS') "
            "AND resolved = 1)"
        )
        canh_based_on = dem(
            "SELECT COUNT(*) FROM (SELECT DISTINCT doc_key, target_key "
            "FROM citations WHERE relation = 'BASED_ON' AND resolved = 1)"
        )
        khong_stub = dem(
            "SELECT COUNT(*) FROM (SELECT DISTINCT c.doc_key, c.target_key, c.relation "
            "FROM citations c JOIN docs d ON d.doc_key = c.target_key "
            "WHERE c.relation IS NOT NULL AND c.resolved = 1 AND d.is_stub = 0)"
        )
        co_bac = dem("SELECT COUNT(*) FROM docs WHERE authority_level IS NOT NULL")
        tong_doc = dem("SELECT COUNT(*) FROM docs")

    # Bỏ cắt vùng: không còn phân biệt được `BASED_ON` (vùng Căn cứ) với
    # `REFERENCES`, cũng không còn cờ điều khoản thi hành để lọc quan hệ hiệu
    # lực -> cả hai nhóm sụp về một loại `REFERENCES` duy nhất.
    khong_cat_vung = day_du - canh_based_on - canh_hieu_luc

    return {
        "day_du": {
            "canh": day_du,
            "trong_do_hieu_luc": canh_hieu_luc,
            "trong_do_based_on": canh_based_on,
        },
        "bo_cat_vung": {
            "canh_phan_loai_duoc": khong_cat_vung,
            "mat": day_du - khong_cat_vung,
            "mat_phan_tram": round(100 * (day_du - khong_cat_vung) / day_du, 1)
            if day_du else 0,
            "y_nghia": "Không có Bước 1 thì BASED_ON và ba quan hệ hiệu lực "
                       "đều không phân biệt được — sụp hết về REFERENCES.",
        },
        "bo_quan_he_hieu_luc": {
            "canh_mat": canh_hieu_luc,
            "y_nghia": "Mất khả năng trả lời 'văn bản nào đang còn hiệu lực' "
                       "và 'cái gì thay thế cái gì'.",
        },
        "bo_stub": {
            "canh_con_lai": khong_stub,
            "mat": day_du - khong_stub,
            "mat_phan_tram": round(100 * (day_du - khong_stub) / day_du, 1)
            if day_du else 0,
            "y_nghia": "Chuỗi BASED_ON đứt ở mọi văn bản chưa crawl — đúng chỗ "
                       "§3 cần để truy lên văn bản gốc thẩm quyền cao nhất.",
        },
        "bo_authority_level": {
            "node_mat_xep_hang": tong_doc - co_bac,
            "node_con_xep_hang": co_bac,
            "y_nghia": "Truy vấn §3 `ORDER BY authority_level DESC` không còn "
                       "sắp được thứ tự văn bản gốc.",
        },
        "khong_do_duoc": {
            "-OCR": "Cần OCR lại toàn kho bằng lớp text gốc của PDF, mà "
                    "data/raw/pdf/ đã bị xoá khỏi máy.",
            "-NormativeContent+Article": "Phải đo qua retrieval cấp điều khoản; "
                                         "xem retrieval.md khi có gold answer.",
        },
    }


# ============================================================
# PHÂN TÍCH LỖI (§6.7)
# ============================================================

def phan_tich_loi(session: KGSession) -> dict:
    """
    Phân loại lỗi điển hình bằng chính dữ liệu đã có.

    §6.7 liệt kê sẵn bốn nhóm cần soi: OCR nuốt số hiệu, nhầm
    REPLACES↔AMENDS, resolve sai văn bản trùng số khác năm, stub không bao giờ
    được nối. Ba trong bốn nhóm đó đếm được tự động.
    """

    with session._lock:  # noqa: SLF001
        conn = session._conn  # noqa: SLF001

        khong_noi = conn.execute(
            "SELECT COUNT(*) n FROM citations WHERE resolved = 0"
        ).fetchone()["n"]
        tong_cit = conn.execute("SELECT COUNT(*) n FROM citations").fetchone()["n"]

        # Số hiệu không nối được, chia theo HÌNH DẠNG.
        #
        # Không xếp theo số lần xuất hiện: ngưỡng tạo stub (>=2 lần HOẶC nằm
        # trong vùng Căn cứ) đã vét sạch mọi số hiệu lặp lại, nên phần còn sót
        # gần như chắc chắn đều đúng 1 lần. Bảng "hay gặp nhất" ở đây sẽ toàn
        # số 1 và chẳng nói lên điều gì.
        la = [
            row["target_key"]
            for row in conn.execute(
                "SELECT DISTINCT target_key FROM citations WHERE resolved = 0"
            )
        ]

        # Stub ĐÁNG CRAWL BỔ SUNG: được viện dẫn nhiều nhất. Đây mới là danh
        # sách hành động được — crawl thêm mấy văn bản này thì chuỗi BASED_ON
        # liền lại. ("stub là ngõ cụt" thì đúng với 100% stub theo định nghĩa,
        # vì stub không có text nên không bao giờ trích dẫn ai.)
        dang_crawl = conn.execute(
            "SELECT doc_key, so_hieu, doc_type, stub_hits FROM docs "
            "WHERE is_stub = 1 AND stub_hits IS NOT NULL "
            "ORDER BY stub_hits DESC LIMIT 15"
        ).fetchall()
        tong_stub = conn.execute(
            "SELECT COUNT(*) n FROM docs WHERE is_stub = 1"
        ).fetchone()["n"]

        # Chuỗi BASED_ON chết ở stub: văn bản thật -> stub, và stub đó không
        # đi tiếp được. Đây mới là thiệt hại thật của việc chưa crawl đủ.
        chuoi_chet = conn.execute(
            "SELECT COUNT(*) n FROM (SELECT DISTINCT c.doc_key FROM citations c "
            "JOIN docs d ON d.doc_key = c.target_key "
            "WHERE c.relation = 'BASED_ON' AND d.is_stub = 1)"
        ).fetchone()["n"]
        co_based_on = conn.execute(
            "SELECT COUNT(*) n FROM (SELECT DISTINCT doc_key FROM citations "
            "WHERE relation = 'BASED_ON')"
        ).fetchone()["n"]

        # Header lệch -> mọi cạnh xuất phát từ đây đều đáng ngờ từ gốc.
        header = {
            r["header_check"]: r["n"]
            for r in conn.execute(
                "SELECT header_check, COUNT(*) n FROM docs "
                "WHERE is_stub = 0 GROUP BY header_check"
            )
        }
        canh_tu_header_lech = conn.execute(
            "SELECT COUNT(*) n FROM citations c JOIN docs d ON d.doc_key = c.doc_key "
            "WHERE d.header_check = 'lech' AND c.relation IS NOT NULL"
        ).fetchone()["n"]

        moi_khoa = [row["doc_key"] for row in conn.execute("SELECT doc_key FROM docs")]

        # Văn bản không có Điều nào -> Bước 4 không sinh được Article.
        khong_dieu = conn.execute(
            "SELECT COUNT(*) n FROM docs WHERE clean_path IS NOT NULL "
            "AND COALESCE(n_articles, 0) = 0"
        ).fetchone()["n"]

    # Cụt đuôi: phần sau dấu `/` cuối cùng không có `-`, tức mất mã cơ quan
    # (`115/2020/ND` đáng lẽ là `115/2020/ND-CP`).
    cut_duoi = sum(1 for key in la if "-" not in key.rsplit("/", 1)[-1])

    # Trùng cả số lẫn đuôi, chỉ khác năm — `8/2014/TT-BGDĐT` vs
    # `8/2020/TT-BGDĐT`. Gom theo mỗi phần số thì `1/...` nào cũng trùng nhau,
    # con số ra vô nghĩa; phải giữ nguyên cả đuôi mới đúng ý §6.7.
    nhom: dict[tuple[str, str], set[str]] = {}

    for key in moi_khoa:
        phan = key.split("/")

        if len(phan) == 3:
            nhom.setdefault((phan[0], phan[2]), set()).add(key)

    trung_so = sum(1 for v in nhom.values() if len(v) > 1)

    return {
        "resolve": {
            "trich_dan_khong_noi_duoc": khong_noi,
            "ty_le": round(100 * khong_noi / tong_cit, 1) if tong_cit else 0,
            "so_hieu_la": len(la),
            "trong_do_cut_duoi": cut_duoi,
        },
        "stub": {
            "tong": tong_stub,
            "van_ban_co_chuoi_based_on_chet_o_stub": chuoi_chet,
            "van_ban_co_based_on": co_based_on,
            "ty_le_chuoi_chet": round(100 * chuoi_chet / co_based_on, 1)
            if co_based_on else 0,
            "nen_crawl_bo_sung": [
                {
                    "so_hieu": r["so_hieu"],
                    "loai": r["doc_type"],
                    "so_lan_bi_vien_dan": r["stub_hits"],
                }
                for r in dang_crawl
            ],
        },
        "header": {
            "phan_bo": header,
            "canh_sinh_tu_van_ban_header_lech": canh_tu_header_lech,
        },
        "cau_truc": {
            "so_hieu_trung_so_khac_nam": trung_so,
            "van_ban_khong_co_dieu_nao": khong_dieu,
        },
    }


# ============================================================
# XUẤT
# ============================================================

def xuat(session: KGSession, out_dir: Path | None = None) -> dict:
    out_dir = out_dir or config.EVAL_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    ab = ablation(session)
    loi = phan_tich_loi(session)

    (out_dir / "ablation.json").write_text(
        json.dumps(ab, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "error_analysis.json").write_text(
        json.dumps(loi, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    d = ab["day_du"]
    lines = [
        "# §6.6–6.7 — Ablation và phân tích lỗi",
        "",
        "## Ablation",
        "",
        f"Graph đầy đủ: **{d['canh']:,} cạnh** "
        f"({d['trong_do_based_on']:,} `BASED_ON`, "
        f"{d['trong_do_hieu_luc']:,} quan hệ hiệu lực).",
        "",
        "| Bỏ thành phần | Hậu quả | Mất |",
        "|---|---|---|",
        f"| Cắt vùng (Bước 1) | {ab['bo_cat_vung']['y_nghia']} "
        f"| **{ab['bo_cat_vung']['mat']:,} cạnh "
        f"({ab['bo_cat_vung']['mat_phan_tram']}%)** |",
        f"| Quan hệ hiệu lực | {ab['bo_quan_he_hieu_luc']['y_nghia']} "
        f"| {ab['bo_quan_he_hieu_luc']['canh_mat']:,} cạnh |",
        f"| Stub (§1) | {ab['bo_stub']['y_nghia']} "
        f"| {ab['bo_stub']['mat']:,} cạnh ({ab['bo_stub']['mat_phan_tram']}%) |",
        f"| `authority_level` (§3) | {ab['bo_authority_level']['y_nghia']} "
        f"| {ab['bo_authority_level']['node_mat_xep_hang']:,} node |",
        "",
        "**Chưa đo được:**",
        "",
    ]

    for ten, ly_do in ab["khong_do_duoc"].items():
        lines.append(f"- `{ten}` — {ly_do}")

    r, s, h, c = loi["resolve"], loi["stub"], loi["header"], loi["cau_truc"]

    lines += [
        "",
        "---",
        "",
        "## Phân tích lỗi",
        "",
        "### Resolve — trích dẫn không nối được vào node nào",
        "",
        f"**{r['trich_dan_khong_noi_duoc']:,}** lượt / {r['so_hieu_la']:,} số hiệu "
        f"phân biệt ({r['ty_le']}% tổng số trích dẫn), trong đó "
        f"**{r['trong_do_cut_duoi']:,}** là số hiệu **cụt đuôi** (mất phần "
        "`-CP`, `-BGDĐT`… do OCR hoặc xuống dòng).",
        "",
        "> Toàn bộ nhóm này gần như đều chỉ xuất hiện **đúng một lần** — đó là",
        "> hệ quả tất yếu của ngưỡng tạo stub (≥2 lần **hoặc** nằm trong vùng",
        "> Căn cứ): mọi số hiệu lặp lại đã được vét lên thành node rồi. Nên đây",
        "> là phần đuôi dài của nhiễu OCR, không phải chỗ sửa tay có lợi.",
        "",
        "### Chuỗi `BASED_ON` chết ở stub",
        "",
        f"**{s['van_ban_co_chuoi_based_on_chet_o_stub']:,}"
        f"/{s['van_ban_co_based_on']:,}** văn bản ({s['ty_le_chuoi_chet']}%) có ít "
        "nhất một nhánh căn cứ dừng lại ở một stub — tức truy ngược lên văn bản "
        "gốc thẩm quyền cao nhất (§3) bị đứt giữa chừng.",
        "",
        f"Crawl bổ sung {len(s['nen_crawl_bo_sung'])} văn bản dưới đây sẽ nối lại "
        "nhiều nhánh nhất:",
        "",
        "| Số hiệu | Loại | Số lần bị viện dẫn |",
        "|---|---|---|",
    ]

    for m in s["nen_crawl_bo_sung"]:
        lines.append(
            f"| `{m['so_hieu']}` | {m['loai'] or '?'} | {m['so_lan_bi_vien_dan']} |"
        )

    lines += [
        "",
        "### Header lệch kéo theo cạnh đáng ngờ",
        "",
        "| Kết luận đối chiếu header | Số văn bản |",
        "|---|---|",
    ]

    for ten, n in sorted(h["phan_bo"].items(), key=lambda x: -x[1]):
        lines.append(f"| `{ten}` | {n} |")

    lines += [
        "",
        f"**{h['canh_sinh_tu_van_ban_header_lech']:,} cạnh** xuất phát từ văn bản "
        "có header lệch metadata — mỗi cạnh đó mang sẵn cờ "
        "`source_header_check: \"lech\"` trong `relations.jsonl` để lọc ra.",
        "",
        "### Cấu trúc",
        "",
        f"- {c['so_hieu_trung_so_khac_nam']} nhóm văn bản **trùng cả số lẫn cơ "
        "quan, chỉ khác năm** (`8/2014/TT-BGDĐT` vs `8/2020/TT-BGDĐT`) — đúng "
        "nguồn resolve sai mà §6.7 nêu đích danh. Trích dẫn nào mất phần năm do "
        "OCR là có nguy cơ nối nhầm sang đây.",
        f"- {c['van_ban_khong_co_dieu_nao']} văn bản không đọc ra `Điều` nào "
        "→ Bước 4 không sinh được `Article`.",
        "",
    ]

    path = out_dir / "ablation_va_loi.md"
    path.write_text("\n".join(lines), encoding="utf-8")

    say(f"  {path}")
    say(f"  {out_dir / 'ablation.json'}")
    say(f"  {out_dir / 'error_analysis.json'}")

    return {"ablation": ab, "loi": loi}
