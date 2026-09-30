"""
Entry point của core/nlq/ — `python run.py ask "<câu hỏi>"`.

Trạng thái theo plan (abundant-sleeping-moth.md):
  - Phase 0/1 (xong): `--template NAME --param k=v` — chạy thủ công 1
    template, tham số thô đi qua `resolve.py` thật (không cần gõ sẵn
    orgId/normalizedNumber).
  - Phase 2 (xong): `ask(question)` — Stage A (match_template.py, Gemini
    chọn template + trích tham số thô) rồi resolve + execute y hệt
    đường thủ công ở trên.
  - Phase 3 (xong): Stage B (freeform.py, fallback khi Stage A miss) —
    Gemini tự viết Cypher, bắt buộc qua guard.py (blocklist + whitelist
    label/property + EXPLAIN dry-run + ép LIMIT) trước khi chạy thật.

`ask()` luôn trả về 1 trong 4 loại kết quả (xem plan, mục "Kết quả trả
về"): `template_result` / `freeform_result` (chưa có) / `resolution_failed`
/ `unsupported` — không bao giờ trộn lẫn "0 dòng hợp lệ" với "bị từ chối".
"""

from __future__ import annotations

import argparse
import dataclasses
from dataclasses import dataclass

from .. import config
from . import execute, freeform, gemini_client, guard, match_template, resolve, retrieval
from .templates import TEMPLATES, Template


class TemplateParamError(Exception):
    pass


class ResolutionFailed(Exception):
    """Tương ứng loại kết quả `resolution_failed` trong plan — 1 tham số
    không resolve được rõ ràng (mơ hồ hoặc không tồn tại). KHÔNG chạy
    Cypher nào khi lỗi này xảy ra.

    candidates: chỉ có giá trị khi lỗi gốc là resolve.Ambiguous — mang
    theo để NlqResult.candidates hiển thị gợi ý cho người dùng chọn, thay
    vì chỉ nhét vào chuỗi `reason` cho người đọc."""

    def __init__(self, param_name: str, reason: str, candidates: tuple[str, ...] | None = None):
        self.param_name = param_name
        self.reason = reason
        self.candidates = candidates
        super().__init__(f"'{param_name}': {reason}")


def _resolve_param(spec, raw: str, session_) -> resolve.Resolution:
    if spec.resolver == "org":
        return resolve.resolve_organization(raw, session_)
    if spec.resolver == "topic":
        return resolve.resolve_topic(raw)
    if spec.resolver == "target_group":
        return resolve.resolve_target_group(raw)
    if spec.resolver == "doc_number":
        return resolve.resolve_document_number(raw, session_)
    if spec.resolver == "status":
        return resolve.resolve_status(raw)
    if spec.resolver == "content_type":
        return resolve.resolve_content_type(raw)
    if spec.resolver == "fulltext_phrase":
        return resolve.Resolved(resolve.resolve_fulltext_phrase(raw))
    if spec.resolver == "int_limit":
        return resolve.Resolved(str(resolve.resolve_int_limit(raw, default=50, cap=config.NLQ_ROW_CAP)))
    raise ValueError(f"resolver không hợp lệ: {spec.resolver}")


def _coerce_default(spec):
    if spec.default_raw is None:
        return None
    if spec.resolver == "int_limit":
        return int(spec.default_raw)
    return spec.default_raw


def fill_template(tpl: Template, raw_params: dict[str, str], session_) -> dict:
    """Điền $param cho 1 template — mỗi giá trị thô đi qua đúng resolver
    khai báo trong ParamSpec (resolve.py, KHÔNG dùng LLM). Resolve thất
    bại (mơ hồ/không tồn tại) -> raise ResolutionFailed ngay, không âm
    thầm chạy Cypher với tham số sai. Thiếu tham số bắt buộc -> lỗi rõ."""

    final: dict = {}
    for spec in tpl.params:
        if spec.name in raw_params:
            result = _resolve_param(spec, raw_params[spec.name], session_)
            if isinstance(result, resolve.Resolved):
                # Resolution.value luôn là str (kiểu chung cho mọi resolver) —
                # int_limit phải ép lại về int trước khi vào $param, không thì
                # Neo4j báo CypherSyntaxError "expected Integer but was String".
                final[spec.name] = int(result.value) if spec.resolver == "int_limit" else result.value
            elif isinstance(result, resolve.Ambiguous):
                raise ResolutionFailed(
                    spec.name,
                    f"mơ hồ, có thể là: {' / '.join(result.candidates)}",
                    candidates=result.candidates,
                )
            else:  # NotFound
                msg = f"không tìm thấy giá trị khớp '{raw_params[spec.name]}'"
                if result.suggestion:
                    msg += f" — {result.suggestion}"
                raise ResolutionFailed(spec.name, msg)
        elif spec.default_raw is not None or not spec.required:
            final[spec.name] = _coerce_default(spec)
        else:
            raise TemplateParamError(
                f"Thiếu tham số bắt buộc '{spec.name}' cho template '{tpl.name}'"
            )
    return final


def run_template_manual(template_name: str, raw_params: dict[str, str]) -> dict:
    if template_name not in TEMPLATES:
        raise TemplateParamError(
            f"Không có template '{template_name}'. Danh sách hợp lệ: {', '.join(TEMPLATES)}"
        )
    tpl = TEMPLATES[template_name]
    with execute.session() as session_:
        params = fill_template(tpl, raw_params, session_)
        result = execute.run_in_session(
            session_, tpl.cypher, params, timeout_seconds=config.NLQ_QUERY_TIMEOUT_SECONDS
        )
    return {
        "template": tpl.name,
        "cypher": tpl.cypher.strip(),
        "params": params,
        "rows": result.rows,
        "elapsed_ms": result.elapsed_ms,
    }


@dataclass(frozen=True)
class NlqResult:
    kind: str  # "template_result" | "freeform_result" | "resolution_failed" | "unsupported"
    template: str | None = None
    cypher: str | None = None
    params: dict | None = None
    rows: list[dict] | None = None
    elapsed_ms: float | None = None
    reason: str | None = None
    confidence: float | None = None
    # Cơ chế hỏi lại (chỉ có ý nghĩa khi kind="resolution_failed" và
    # missing_param khác None — resolution_failed KHÔNG kèm missing_param
    # nghĩa là chấm dứt thật, không mời hỏi lại nữa, VD hết lượt):
    missing_param: str | None = None
    candidates: tuple[str, ...] | None = None
    raw_params: dict | None = None
    # Tier 2 — số lần Stage B đã tự sửa Cypher sau khi bị guard chặn.
    correction_attempts: int = 0
    # Retrieval ngữ nghĩa (core/nlq/retrieval.py) — chạy SONG SONG luồng
    # Cypher trên, độc lập với kind. retrieval=None + retrieval_reason có
    # giá trị nghĩa là retrieval thất bại (lỗi Gemini/Neo4j) — KHÔNG được
    # phép kéo theo hỏng luôn kết quả Cypher đã có.
    retrieval: list[dict] | None = None
    retrieval_reason: str | None = None


@dataclass(frozen=True)
class PendingClarification:
    """Ngữ cảnh đủ để tiếp tục 1 câu hỏi đang chờ trả lời 1 tham số còn
    thiếu — sống ở phía CLIENT (API/FE gửi lại nguyên trong request kế
    tiếp), backend KHÔNG lưu gì (xem plan, quyết định "stateless")."""

    template: str
    raw_params: dict[str, str]
    missing_param: str
    rounds: int = 0


# Câu hỏi gợi ý theo LOẠI resolver (không phải theo từng ParamSpec — đa số
# tham số cùng loại resolver dùng chung được 1 câu hỏi tự nhiên).
_CLARIFY_QUESTIONS: dict[str, str] = {
    "org": "Bạn muốn hỏi về đơn vị/tổ chức nào?",
    "topic": "Bạn muốn hỏi về lĩnh vực nào?",
    "target_group": "Bạn muốn hỏi về nhóm đối tượng nào?",
    "doc_number": "Số hiệu văn bản là gì?",
    "status": "Bạn muốn lọc theo tình trạng hiệu lực nào (còn hiệu lực / hết hiệu lực / chưa có hiệu lực)?",
    "content_type": "Bạn muốn hỏi về loại nội dung nào (Quy định/Quy chế/Nội quy...)?",
    "fulltext_phrase": "Bạn muốn tìm theo cụm từ nào?",
}


def _clarify_question(tpl: Template, param_name: str) -> str:
    spec = next((p for p in tpl.params if p.name == param_name), None)
    if spec is not None and spec.resolver in _CLARIFY_QUESTIONS:
        return _CLARIFY_QUESTIONS[spec.resolver]
    return f"Bạn có thể nêu rõ hơn giá trị cho '{param_name}' không?"


def _run_freeform(question: str, stage_a_confidence: float) -> NlqResult:
    """Stage A miss -> Stage B: Gemini tự viết Cypher, qua guard.py trước
    khi chạy thật. Bị guard chặn thì thử SỬA LẠI tối đa
    config.NLQ_FREEFORM_MAX_ATTEMPTS lần (gửi kèm lý do từ chối cụ thể của
    guard cho Gemini tự sửa), không chạy Cypher "một phần" ở bất kỳ lượt
    nào. Hết lượt vẫn không qua được guard -> unsupported hẳn.

    Mở 1 session DUY NHẤT cho toàn bộ vòng lặp — EXPLAIN (guard) và chạy
    Cypher thật (khi qua guard) dùng chung, tránh mở 2 kết nối Neo4j
    riêng cho mỗi lượt (trước đây guard tự mở session riêng cho EXPLAIN)."""

    cypher: str | None = None
    guard_reason: str | None = None
    attempt = 0

    with execute.session() as session_:
        while attempt < config.NLQ_FREEFORM_MAX_ATTEMPTS:
            attempt += 1
            try:
                if attempt == 1:
                    stage_b = freeform.generate_freeform(question)
                else:
                    stage_b = freeform.generate_freeform_correction(question, cypher, guard_reason)
            except gemini_client.GeminiCallError as exc:
                return NlqResult(
                    kind="unsupported",
                    reason=f"Lỗi gọi Gemini (Stage B, lượt {attempt}): {exc}",
                    confidence=stage_a_confidence,
                    correction_attempts=attempt - 1,
                )

            if stage_b.unsupported or not stage_b.cypher:
                return NlqResult(
                    kind="unsupported", reason=stage_b.reason, confidence=stage_a_confidence,
                    correction_attempts=attempt - 1,
                )

            cypher = stage_b.cypher
            try:
                capped_cypher = guard.guard_freeform_cypher(
                    cypher, {}, row_cap=config.NLQ_ROW_CAP, session_=session_
                )
            except guard.GuardRejected as exc:
                guard_reason = exc.reason
                continue  # còn lượt thì generate_freeform_correction() ở đầu vòng lặp kế tiếp

            result = execute.run_in_session(
                session_, capped_cypher, {}, timeout_seconds=config.NLQ_QUERY_TIMEOUT_SECONDS
            )
            correction_note = f" (đã tự sửa {attempt - 1} lần)" if attempt > 1 else ""
            return NlqResult(
                kind="freeform_result",
                cypher=capped_cypher,
                params={},
                rows=result.rows,
                elapsed_ms=result.elapsed_ms,
                confidence=stage_a_confidence,
                correction_attempts=attempt - 1,
                reason=f"Cypher do LLM tự sinh (freeform) — độ tin cậy thấp hơn kết quả template, "
                       f"nên soát lại Cypher{correction_note}.",
            )

    # Hết config.NLQ_FREEFORM_MAX_ATTEMPTS lượt mà lượt cuối vẫn bị guard chặn.
    return NlqResult(
        kind="unsupported",
        cypher=cypher,
        reason=f"Đã thử sửa Cypher {attempt - 1} lần nhưng vẫn bị chặn: {guard_reason}",
        confidence=stage_a_confidence,
        correction_attempts=attempt - 1,
    )


def _run_template(tpl: Template, raw_params: dict[str, str], confidence: float | None, rounds: int) -> NlqResult:
    """Chạy 1 template đã CHỌN xong (Stage A hoặc resume của vòng hỏi lại).
    ResolutionFailed còn lượt hỏi lại (rounds < NLQ_MAX_CLARIFY_ROUNDS) ->
    resolution_failed KÈM missing_param (mời hỏi lại); hết lượt -> unsupported
    hẳn, không mời hỏi lại vô hạn."""

    try:
        with execute.session() as session_:
            params = fill_template(tpl, raw_params, session_)
            result = execute.run_in_session(
                session_, tpl.cypher, params, timeout_seconds=config.NLQ_QUERY_TIMEOUT_SECONDS
            )
    except ResolutionFailed as exc:
        if rounds < config.NLQ_MAX_CLARIFY_ROUNDS:
            return NlqResult(
                kind="resolution_failed",
                template=tpl.name,
                reason=_clarify_question(tpl, exc.param_name),
                confidence=confidence,
                missing_param=exc.param_name,
                candidates=exc.candidates,
                raw_params=raw_params,
            )
        return NlqResult(
            kind="unsupported",
            template=tpl.name,
            reason=f"Vẫn chưa xác định được '{exc.param_name}' sau nhiều lần hỏi lại "
                   f"({exc.reason}) — bạn thử đặt lại câu hỏi đầy đủ hơn nhé.",
            confidence=confidence,
        )
    except TemplateParamError as exc:
        return NlqResult(kind="unsupported", template=tpl.name, reason=str(exc), confidence=confidence)

    return NlqResult(
        kind="template_result",
        template=tpl.name,
        cypher=tpl.cypher.strip(),
        params=params,
        rows=result.rows,
        elapsed_ms=result.elapsed_ms,
        confidence=confidence,
    )


def _attach_retrieval(result: NlqResult, question: str) -> NlqResult:
    """Chạy retrieval ngữ nghĩa SAU KHI đã có kết quả Cypher (bất kể kind
    gì) — độc lập hoàn toàn, lỗi ở đây không được phép làm hỏng kết quả
    Cypher đã có (xem NlqResult.retrieval_reason). Bắt Exception rộng có
    chủ đích: lỗi có thể tới từ Gemini (GeminiCallError) HOẶC từ Neo4j
    (VD vector index chưa có embedding nào — trạng thái bình thường lúc
    mới build, chưa chạy `embed-articles`)."""

    if not config.NLQ_RETRIEVAL_ENABLED:
        return result
    try:
        with execute.session() as session_:
            hits = retrieval.retrieve(question, session_)
        return dataclasses.replace(result, retrieval=hits)
    except Exception as exc:
        return dataclasses.replace(result, retrieval_reason=f"Truy xuất ngữ nghĩa thất bại: {exc}")


def ask(question: str, resume: PendingClarification | None = None) -> NlqResult:
    """Điểm vào cho câu hỏi tự nhiên tự do — bọc _ask_core() bằng retrieval
    ngữ nghĩa, chạy cho MỌI kind kết quả (xem _attach_retrieval)."""

    return _attach_retrieval(_ask_core(question, resume), question)


def _ask_core(question: str, resume: PendingClarification | None = None) -> NlqResult:
    """Stage A chạy trước; miss -> Stage B (freeform, guard.py canh gác)
    — xem plan mục "Kết quả trả về: 4 loại rõ ràng".

    resume: câu trả lời cho 1 lượt hỏi-lại trước đó (xem PendingClarification
    — client/FE gửi lại nguyên, backend KHÔNG tự lưu gì). Có resume thì bỏ
    qua Stage A hoàn toàn, coi `question` là giá trị thô cho đúng tham số
    còn thiếu lần trước."""

    if resume is not None:
        tpl = TEMPLATES[resume.template]
        raw_params = {**resume.raw_params, resume.missing_param: question}
        return _run_template(tpl, raw_params, confidence=None, rounds=resume.rounds + 1)

    try:
        stage_a = match_template.match_template(question)
    except gemini_client.GeminiCallError as exc:
        return NlqResult(kind="unsupported", reason=f"Lỗi gọi Gemini (Stage A): {exc}")

    if not stage_a.matched or not stage_a.template:
        return _run_freeform(question, stage_a.confidence)

    tpl = TEMPLATES[stage_a.template]

    if stage_a.missing:
        # Stage A tự tin đúng template nhưng câu hỏi không nêu rõ 1+ tham số
        # bắt buộc -> hỏi lại NGAY tham số đầu tiên còn thiếu, không gọi
        # fill_template (nó sẽ ném TemplateParamError chung chung cho tham
        # số chưa từng có trong raw_params, không phải ResolutionFailed).
        # Mọi template hiện có tối đa 1 tham số bắt buộc nên chỉ hỏi 1 slot
        # là đủ trên thực tế; nếu sau này có template >=2 tham số bắt buộc,
        # cần mở rộng để hỏi tuần tự từng slot trong `missing`.
        missing_param = stage_a.missing[0]
        return NlqResult(
            kind="resolution_failed",
            template=tpl.name,
            reason=_clarify_question(tpl, missing_param),
            confidence=stage_a.confidence,
            missing_param=missing_param,
            raw_params=stage_a.params,
        )

    return _run_template(tpl, stage_a.params, stage_a.confidence, rounds=0)


def _parse_param_args(pairs: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in pairs:
        if "=" not in p:
            raise TemplateParamError(f"--param phải dạng key=value, nhận '{p}'")
        k, v = p.split("=", 1)
        out[k] = v
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hỏi bằng tiếng Việt tự nhiên -> Cypher -> kết quả thô (chưa tổng hợp câu trả lời tự nhiên)"
    )
    parser.add_argument("question", nargs="?", default=None,
                         help="Câu hỏi tự nhiên (CHƯA hỗ trợ ở giai đoạn này — dùng --template để test thủ công)")
    parser.add_argument("--template", help="Tên template chạy thủ công, xem core/nlq/templates.py")
    parser.add_argument("--param", action="append", default=[],
                         help="Tham số thô (tên tổ chức/lĩnh vực/số hiệu... viết tự nhiên, "
                              "resolve.py sẽ tự tra cứu), dạng key=value, có thể lặp lại")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if args.template:
        try:
            raw_params = _parse_param_args(args.param)
            result = run_template_manual(args.template, raw_params)
        except TemplateParamError as exc:
            print(f"LOI: {exc}")
            return 1
        except ResolutionFailed as exc:
            print(f"[resolution_failed] {exc}")
            return 1

        if args.verbose:
            print(f"[template] {result['template']}")
            print(f"[params]   {result['params']}")
            print(f"[cypher]   {result['cypher']}")
            print(f"[elapsed]  {result['elapsed_ms']:.2f} ms")
        print(f"{len(result['rows'])} dòng:")
        for row in result["rows"][:50]:
            print(f"  {row}")
        return 0

    if not args.question:
        print(
            "Cần 1 câu hỏi hoặc --template. Dùng: python run.py ask \"<câu hỏi>\" "
            "hoặc python run.py ask --template TPL_XXX --param key=value [--verbose]. "
            "Danh sách template: " + ", ".join(TEMPLATES)
        )
        return 1

    result = ask(args.question)

    if args.verbose or result.kind != "template_result":
        line = f"[{result.kind}]"
        if result.template:
            line += f" template={result.template}"
        if result.confidence is not None:
            line += f" confidence={result.confidence:.2f}"
        print(line)

    if result.kind == "resolution_failed":
        print(f"  {result.reason}")
        return 1
    if result.kind == "unsupported":
        print(f"  {result.reason}")
        return 1

    # template_result / freeform_result
    if args.verbose:
        print(f"[params]  {result.params}")
        print(f"[cypher]  {result.cypher}")
        print(f"[elapsed] {result.elapsed_ms:.2f} ms")
    print(f"{len(result.rows)} dòng:")
    for row in result.rows[:50]:
        print(f"  {row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
