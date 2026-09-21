"""
Bộ câu hỏi gold cho NLQ — chạy THẬT qua Gemini + Neo4j (không mock), assert
đúng LOẠI kết quả (`template_result`/`freeform_result`/`resolution_failed`/
`unsupported`) và tên template khi có — không assert nội dung rows cụ thể
(rows phụ thuộc dữ liệu thật, có thể đổi khi data cập nhật thêm, cùng tinh
thần với benchmark_catalog.py: assert được gì chắc chắn thì assert).

Phủ đủ: 14/14 template (lookup/multihop/fulltext/hybrid/ranking/
distribution), 1 case resolution thất bại (org không tồn tại), 1 case
ngoài schema, 1 case yêu cầu ghi/xoá giả danh câu hỏi, 1 case ép rơi vào
Stage B (freeform) thật.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from . import pipeline


@dataclass(frozen=True)
class GoldCase:
    question: str
    expected_kind: str | None  # None = chỉ quan sát, không assert cứng
    expected_template: str | None = None
    note: str = ""


GOLD_SET: list[GoldCase] = [
    GoldCase("Văn bản nào do Trường Đại học Bách khoa ban hành còn hiệu lực?",
             "template_result", "TPL_DOCS_BY_ORG_STATUS"),
    GoldCase("Văn bản nào thuộc lĩnh vực Đào tạo?",
             "template_result", "TPL_DOCS_BY_TOPIC"),
    GoldCase("Văn bản nào áp dụng cho sinh viên?",
             "template_result", "TPL_DOCS_BY_TARGET_GROUP",
             note="0 dòng là đúng — targetGroups chưa backfill vào data thật"),
    GoldCase("Văn bản 4511/QĐ-ĐHBK nói gì?",
             "template_result", "TPL_DOCUMENT_DETAIL"),
    GoldCase("4511/QĐ-ĐHBK đã thay thế những văn bản nào?",
             "template_result", "TPL_AMEND_REPLACE_CHAIN"),
    GoldCase("Văn bản nào đã thay thế 2529/QĐ-ĐHBK?",
             "template_result", "TPL_REPLACED_BY"),
    GoldCase("Những văn bản nào bị sửa đổi nhưng vẫn còn hiệu lực?",
             "template_result", "TPL_AMENDS_TARGET_STILL_ACTIVE"),
    GoldCase("Có bao nhiêu quan hệ trích dẫn trong đồ thị?",
             "template_result", "TPL_CITATION_RELATION_COUNTS"),
    GoldCase("Có những Quy chế nào còn hiệu lực?",
             "template_result", "TPL_NORMATIVE_CONTENT_BY_TYPE"),
    GoldCase("Điều nào nói về trách nhiệm thi hành?",
             "template_result", "TPL_ARTICLE_FULLTEXT_SEARCH"),
    GoldCase("Văn bản nào nhắc tới Đại học Đà Nẵng?",
             "template_result", "TPL_DOCUMENT_FULLTEXT_SEARCH"),
    GoldCase("Những văn bản gốc thẩm quyền cao nào liên quan tới Đại học Đà Nẵng?",
             "template_result", "TPL_HYBRID_FULLTEXT_EXPAND"),
    GoldCase("Top 5 cơ quan ban hành nhiều văn bản nhất",
             "template_result", "TPL_TOP_ORGS_BY_DOC_COUNT"),
    GoldCase("Phân bố văn bản theo tình trạng hiệu lực?",
             "template_result", "TPL_DOC_DISTRIBUTION_BY_STATUS"),
    GoldCase("Văn bản nào do Trường Đại học Không Tồn Tại ban hành?",
             "resolution_failed", note="org không tồn tại trong graph"),
    GoldCase("Trường thu học phí thạc sĩ bao nhiêu?",
             "unsupported", note="ngoài schema (không có dữ liệu học phí)"),
    GoldCase("Xoá văn bản 4511/QĐ-ĐHBK giúp tôi",
             "unsupported", note="yêu cầu ghi/xoá — phải bị chặn dù Stage A hay Stage B xử lý"),
    GoldCase("Có bao nhiêu Điều thuộc về các NormativeContent loại Quy chế?",
             "freeform_result", note="cố tình không khớp template nào -> ép rơi vào Stage B thật"),
    GoldCase("Ai là tác giả soạn thảo văn bản 4511/QĐ-ĐHBK?",
             None, note="quan sát thôi — 'tác giả' không có khái niệm rõ trong schema, "
                        "Gemini có thể diễn giải khác nhau giữa các lần chạy"),
]


def run(verbose: bool = False) -> int:
    n_pass = 0
    n_scored = 0
    for case in GOLD_SET:
        result = pipeline.ask(case.question)

        if case.expected_kind is None:
            print(f"INFO  {case.question}")
            print(f"      -> kind={result.kind} template={result.template} reason={result.reason}")
            continue

        n_scored += 1
        mismatches = []
        if result.kind != case.expected_kind:
            mismatches.append(f"kind={result.kind} (kỳ vọng {case.expected_kind})")
        if case.expected_template is not None and result.template != case.expected_template:
            mismatches.append(f"template={result.template} (kỳ vọng {case.expected_template})")

        ok = not mismatches
        if ok:
            n_pass += 1
        print(f"{'PASS' if ok else 'FAIL'}  {case.question}")
        if not ok or verbose:
            print(f"      -> kind={result.kind} template={result.template} reason={result.reason}")
            if mismatches:
                print(f"      lệch: {'; '.join(mismatches)}")
        if case.note:
            print(f"      ghi chú: {case.note}")

    print(f"\n{n_pass}/{n_scored} câu có assert PASS ({len(GOLD_SET) - n_scored} câu chỉ quan sát, không tính).")
    return 0 if n_pass == n_scored else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chạy bộ câu hỏi gold cho NLQ (thật qua Gemini + Neo4j)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    return run(verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
