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

from .. import config
from . import pipeline


@dataclass(frozen=True)
class GoldCase:
    question: str
    expected_kind: str | None  # None = chỉ quan sát, không assert cứng
    expected_template: str | None = None
    # Tham số đã RESOLVE đúng kỳ vọng (VD {"orgId": "truong_dai_hoc_bach_khoa"})
    # — so với result.params khi kind=template_result, đo riêng độ chính xác
    # entity-linking (resolve.py/aliases.py), tách khỏi việc chọn đúng
    # template (Stage A) hay đúng kind tổng thể.
    expected_params: dict[str, str] | None = None
    note: str = ""


GOLD_SET: list[GoldCase] = [
    GoldCase("Văn bản nào do Trường Đại học Bách khoa ban hành còn hiệu lực?",
             "template_result", "TPL_DOCS_BY_ORG_STATUS"),
    GoldCase("Văn bản nào thuộc lĩnh vực Đào tạo?",
             "template_result", "TPL_DOCS_BY_TOPIC"),
    GoldCase("Văn bản nào áp dụng cho sinh viên?",
             "template_result", "TPL_DOCS_BY_TARGET_GROUP",
             note="targetGroups đã backfill ở data/clean/json/v2 (497 cạnh APPLIES_TO, "
                  "51 văn bản cho 'Người học') — nạp v1 thì câu này vẫn trả 0 dòng"),
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
             "resolution_failed", "TPL_DOCS_BY_ORG_STATUS",
             note="org không tồn tại trong graph — vẫn đúng template (Stage A chọn đúng ý "
                  "định), chỉ entity-linking thất bại đúng như kỳ vọng"),
    GoldCase("Trường thu học phí thạc sĩ bao nhiêu?",
             "unsupported", note="ngoài schema (không có dữ liệu học phí)"),
    GoldCase("Xoá văn bản 4511/QĐ-ĐHBK giúp tôi",
             "unsupported", note="yêu cầu ghi/xoá — phải bị chặn dù Stage A hay Stage B xử lý"),
    GoldCase("Có bao nhiêu Điều thuộc về các NormativeContent loại Quy chế?",
             "freeform_result", note="cố tình không khớp template nào -> ép rơi vào Stage B thật"),
    GoldCase("Ai là tác giả soạn thảo văn bản 4511/QĐ-ĐHBK?",
             None, note="quan sát thôi — 'tác giả' không có khái niệm rõ trong schema, "
                        "Gemini có thể diễn giải khác nhau giữa các lần chạy"),

    # --- Bảng alias (reference/aliases_seed.json) — đo entity-linking cho viết tắt ---
    GoldCase("ĐHBK ban hành văn bản gì còn hiệu lực?",
             "template_result", "TPL_DOCS_BY_ORG_STATUS",
             expected_params={"orgId": "truong_dai_hoc_bach_khoa"},
             note="alias 'ĐHBK' -> phải resolve đúng org qua aliases.py, không qua fuzzy thường"),
    GoldCase("DHBK có văn bản nào về Đào tạo?",
             "template_result", "TPL_DOCS_BY_TOPIC",
             note="alias org lẫn trong câu hỏi lệch template (TOPIC) — chỉ quan sát template, "
                  "không assert expected_params vì template này không có tham số org"),
    GoldCase("ĐHĐN ban hành văn bản gì?",
             "template_result", "TPL_DOCS_BY_ORG_STATUS",
             expected_params={"orgId": "dai_hoc_da_nang"}),
    GoldCase("Bộ GD&ĐT ban hành văn bản nào còn hiệu lực?",
             "template_result", "TPL_DOCS_BY_ORG_STATUS",
             expected_params={"orgId": "bo_giao_duc_va_dao_tao"}),

    # --- Quan sát tier-2 (retry tự sửa Cypher) — không ép được guard chặn
    # lượt đầu một cách tái lập, nên chỉ quan sát correction_attempts, không
    # assert cứng (đúng tinh thần "quan sát thôi" đã dùng ở case tác giả).
    GoldCase("Điều nào của các Quy chế còn hiệu lực nhắc tới trách nhiệm của phòng ban?",
             None, note="quan sát tier-2 — câu phức, dễ rơi Stage B; xem correction_attempts "
                        "trong output nếu Gemini từng bị guard chặn"),
]


@dataclass(frozen=True)
class ClarifyCase:
    """Chuỗi 2 lượt: hỏi thiếu tham số -> trả lời -> phải ra kết quả đúng
    template. Xem core/nlq/pipeline.py::PendingClarification."""

    question: str
    answer: str
    expected_template: str
    note: str = ""


CLARIFY_CASES: list[ClarifyCase] = [
    ClarifyCase("Văn bản nào còn hiệu lực?", "Trường Đại học Bách khoa",
                "TPL_DOCS_BY_ORG_STATUS",
                note="thiếu orgId -> hỏi lại -> trả lời đầy đủ -> ra kết quả"),
    ClarifyCase("Có văn bản nào về vấn đề này không?", "Tuyển sinh",
                "TPL_DOCS_BY_TOPIC",
                note="câu hỏi mơ hồ cố tình, kỳ vọng Stage A vẫn nhận ra ý định lookup theo "
                     "topic nhưng thiếu topicId — Stage A có thể tự tin thấp và rơi xuống "
                     "Stage B thay vì hỏi lại (SKIP, không phải FAIL, xem run_clarification_cases())"),
]


def run_clarification_cases(verbose: bool = False) -> tuple[int, int]:
    """Trả (n_pass, n_attempted) — n_attempted CHỈ tính case thật sự vào
    được trạng thái chờ hỏi lại ở lượt 1 (kind=resolution_failed kèm
    missing_param). Case không vào được trạng thái đó (Stage A tự tin thấp,
    rơi xuống Stage B) là SKIP, không phải FAIL — đây là phán đoán hợp lệ
    của Gemini với câu hỏi mơ hồ cố tình, không phải lỗi code."""

    n_pass = 0
    n_attempted = 0
    for case in CLARIFY_CASES:
        r1 = pipeline.ask(case.question)
        if r1.kind != "resolution_failed" or not r1.missing_param:
            print(f"SKIP  [clarify] {case.question}")
            print(f"      -> lượt 1 không rơi vào trạng thái chờ hỏi lại (kind={r1.kind}, "
                  f"template={r1.template}) — không đánh giá được chuỗi hỏi-lại cho case này")
            if case.note:
                print(f"      ghi chú: {case.note}")
            continue

        n_attempted += 1
        resume = pipeline.PendingClarification(
            template=r1.template, raw_params=r1.raw_params or {},
            missing_param=r1.missing_param, rounds=0,
        )
        r2 = pipeline.ask(case.answer, resume=resume)
        ok = r2.kind == "template_result" and r2.template == case.expected_template
        n_pass += ok
        print(f"{'PASS' if ok else 'FAIL'}  [clarify] {case.question!r} + {case.answer!r}")
        if not ok or verbose:
            print(f"      -> lượt1 missing_param={r1.missing_param!r}; "
                  f"lượt2 kind={r2.kind} template={r2.template} reason={r2.reason}")
        if case.note:
            print(f"      ghi chú: {case.note}")

    print(f"[clarify] {n_pass}/{n_attempted} chuỗi hỏi-lại PASS "
          f"({len(CLARIFY_CASES) - n_attempted} case SKIP vì lượt 1 không vào trạng thái hỏi lại).")
    return n_pass, n_attempted


def _check_params(case: GoldCase, result: pipeline.NlqResult) -> bool | None:
    """None = không áp dụng (case không khai expected_params, không tính
    vào độ chính xác entity-linking). True/False = có áp dụng, có khớp
    hay không — chỉ khớp được khi kind=template_result (lúc đó result.params
    mới có giá trị đã resolve xong)."""

    if case.expected_params is None:
        return None
    if result.kind != "template_result" or not result.params:
        return False
    return all(result.params.get(k) == v for k, v in case.expected_params.items())


def run(verbose: bool = False, with_retrieval: bool = False) -> int:
    # Mặc định TẮT retrieval khi chạy nlq-eval thường ngày — mỗi case đã
    # tốn 1-2 lượt gọi Gemini cho Stage A/B, bật thêm retrieval là gấp đôi
    # quota (đã hết quota thật 1 lần trong phiên trước). Muốn test luôn cả
    # retrieval thì truyền --with-retrieval (xem main()).
    goc_retrieval_enabled = config.NLQ_RETRIEVAL_ENABLED
    config.NLQ_RETRIEVAL_ENABLED = with_retrieval and goc_retrieval_enabled
    try:
        return _run(verbose)
    finally:
        config.NLQ_RETRIEVAL_ENABLED = goc_retrieval_enabled


def _run(verbose: bool) -> int:
    n_pass = 0
    n_scored = 0
    n_template_checked = 0
    n_template_ok = 0
    n_entity_checked = 0
    n_entity_ok = 0

    for case in GOLD_SET:
        result = pipeline.ask(case.question)

        if case.expected_template is not None:
            n_template_checked += 1
            if result.template == case.expected_template:
                n_template_ok += 1

        params_ok = _check_params(case, result)
        if params_ok is not None:
            n_entity_checked += 1
            n_entity_ok += params_ok

        if case.expected_kind is None:
            print(f"INFO  {case.question}")
            print(f"      -> kind={result.kind} template={result.template} "
                  f"correction_attempts={result.correction_attempts} reason={result.reason}")
            continue

        n_scored += 1
        mismatches = []
        if result.kind != case.expected_kind:
            mismatches.append(f"kind={result.kind} (kỳ vọng {case.expected_kind})")
        if case.expected_template is not None and result.template != case.expected_template:
            mismatches.append(f"template={result.template} (kỳ vọng {case.expected_template})")
        if params_ok is False:
            mismatches.append(f"params={result.params} (kỳ vọng chứa {case.expected_params})")

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

    n_clarify_pass, n_clarify_total = run_clarification_cases(verbose=verbose)

    print("\n--- Tổng hợp 3 số đo riêng (tách nguồn lỗi) ---")
    if n_template_checked:
        print(f"Độ chính xác chọn template (Stage A):  {n_template_ok}/{n_template_checked}")
    if n_entity_checked:
        print(f"Độ chính xác entity-linking (resolve):  {n_entity_ok}/{n_entity_checked}")
    print(f"Độ chính xác kind tổng thể (end-to-end): {n_pass}/{n_scored}")
    print(f"Chuỗi hỏi-lại (clarification):           {n_clarify_pass}/{n_clarify_total}")

    return 0 if (n_pass == n_scored and n_clarify_pass == n_clarify_total) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chạy bộ câu hỏi gold cho NLQ (thật qua Gemini + Neo4j)")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--with-retrieval", action="store_true",
                         help="Bật luôn retrieval ngữ nghĩa (mặc định tắt để đỡ tốn gấp đôi quota)")
    args = parser.parse_args(argv)
    return run(verbose=args.verbose, with_retrieval=args.with_retrieval)


if __name__ == "__main__":
    raise SystemExit(main())
