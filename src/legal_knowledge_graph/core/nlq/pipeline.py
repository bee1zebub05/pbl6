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
from dataclasses import dataclass

from .. import config
from . import execute, freeform, gemini_client, guard, match_template, resolve
from .templates import TEMPLATES, Template


class TemplateParamError(Exception):
    pass


class ResolutionFailed(Exception):
    """Tương ứng loại kết quả `resolution_failed` trong plan — 1 tham số
    không resolve được rõ ràng (mơ hồ hoặc không tồn tại). KHÔNG chạy
    Cypher nào khi lỗi này xảy ra."""

    def __init__(self, param_name: str, reason: str):
        self.param_name = param_name
        self.reason = reason
        super().__init__(f"'{param_name}': {reason}")


_RESOLVERS_NEEDING_SESSION = {"org", "doc_number"}


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


def _run_freeform(question: str, stage_a_confidence: float) -> NlqResult:
    """Stage A miss -> Stage B: Gemini tự viết Cypher, qua guard.py trước
    khi chạy thật. Guard từ chối ở bất kỳ bước nào -> unsupported ngay,
    KHÔNG chạy Cypher "một phần"."""

    try:
        stage_b = freeform.generate_freeform(question)
    except gemini_client.GeminiCallError as exc:
        return NlqResult(kind="unsupported", reason=f"Lỗi gọi Gemini (Stage B): {exc}", confidence=stage_a_confidence)

    if stage_b.unsupported or not stage_b.cypher:
        return NlqResult(kind="unsupported", reason=stage_b.reason, confidence=stage_a_confidence)

    try:
        capped_cypher = guard.guard_freeform_cypher(stage_b.cypher, {}, row_cap=config.NLQ_ROW_CAP)
    except guard.GuardRejected as exc:
        return NlqResult(kind="unsupported", cypher=stage_b.cypher, reason=f"Bị chặn bởi guard: {exc.reason}", confidence=stage_a_confidence)

    result = execute.run_cypher(capped_cypher, {}, timeout_seconds=config.NLQ_QUERY_TIMEOUT_SECONDS)
    return NlqResult(
        kind="freeform_result",
        cypher=capped_cypher,
        params={},
        rows=result.rows,
        elapsed_ms=result.elapsed_ms,
        confidence=stage_a_confidence,
        reason="Cypher do LLM tự sinh (freeform) — độ tin cậy thấp hơn kết quả template, nên soát lại Cypher.",
    )


def ask(question: str) -> NlqResult:
    """Điểm vào cho câu hỏi tự nhiên tự do. Stage A chạy trước; miss ->
    Stage B (freeform, guard.py canh gác) — xem plan mục "Kết quả trả về:
    4 loại rõ ràng"."""

    try:
        stage_a = match_template.match_template(question)
    except gemini_client.GeminiCallError as exc:
        return NlqResult(kind="unsupported", reason=f"Lỗi gọi Gemini (Stage A): {exc}")

    if not stage_a.matched or not stage_a.template:
        return _run_freeform(question, stage_a.confidence)

    tpl = TEMPLATES[stage_a.template]
    try:
        with execute.session() as session_:
            params = fill_template(tpl, stage_a.params, session_)
            result = execute.run_in_session(
                session_, tpl.cypher, params, timeout_seconds=config.NLQ_QUERY_TIMEOUT_SECONDS
            )
    except ResolutionFailed as exc:
        return NlqResult(kind="resolution_failed", template=tpl.name, reason=str(exc), confidence=stage_a.confidence)
    except TemplateParamError as exc:
        return NlqResult(kind="unsupported", template=tpl.name, reason=str(exc), confidence=stage_a.confidence)

    return NlqResult(
        kind="template_result",
        template=tpl.name,
        cypher=tpl.cypher.strip(),
        params=params,
        rows=result.rows,
        elapsed_ms=result.elapsed_ms,
        confidence=stage_a.confidence,
    )


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
