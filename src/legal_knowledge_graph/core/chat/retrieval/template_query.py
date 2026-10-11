"""
Chạy một template Cypher đã kiểm duyệt: resolve từng tham số thô thành khoá
thật (qua EntityResolver, không LLM) rồi thực thi. Resolve mơ hồ / không
thấy -> ResolutionFailed, KHÔNG chạy Cypher với tham số sai.

Dùng chung bởi node run_template, tool run_template của agent và CLI
`lkg ask --template`.
"""

from __future__ import annotations

from typing import Any

from ...graph_query import entity_resolver
from ...graph_query.templates import PARAM_TO_SLOT, TEMPLATES, ParamSpec, Template
from ..models import QueryResult, ResolutionFailed, TemplateParamError
from ..ports import EntityResolver, QueryExecutor


class TemplateQueryService:
    def __init__(self, executor: QueryExecutor, resolver: EntityResolver):
        self._executor = executor
        self._resolver = resolver

    @staticmethod
    def get_template(name: str) -> Template:
        if name not in TEMPLATES:
            raise TemplateParamError(f"Không có template '{name}'. Hợp lệ: {', '.join(TEMPLATES)}")
        return TEMPLATES[name]

    def run(self, template_name: str, raw_params: dict[str, Any]) -> QueryResult:
        tpl = self.get_template(template_name)
        params = self._fill(tpl, raw_params)
        result = self._executor.run(tpl.cypher, params, label=tpl.name)
        return QueryResult(template=tpl.name, cypher=tpl.cypher.strip(), params=params,
                           rows=result.rows, elapsed_ms=result.elapsed_ms)

    def _fill(self, tpl: Template, raw_params: dict[str, Any]) -> dict[str, Any]:
        known = {p.name for p in tpl.params}
        unknown = {k for k, v in raw_params.items() if v not in (None, "")} - known
        if unknown:
            raise TemplateParamError(
                f"Template '{tpl.name}' không nhận tham số {sorted(unknown)}; nhận: {sorted(known)}"
            )

        final: dict[str, Any] = {}
        for spec in tpl.params:
            raw = raw_params.get(spec.name)
            if raw not in (None, ""):
                final[spec.name] = self._resolve(spec, raw)
            elif spec.default is not None or not spec.required:
                final[spec.name] = spec.default
            else:
                raise TemplateParamError(f"Thiếu tham số bắt buộc '{spec.name}' cho template '{tpl.name}'")
        return final

    def _resolve(self, spec: ParamSpec, raw: Any) -> Any:
        result = self._resolver.resolve(spec.resolver, raw)
        slot = PARAM_TO_SLOT.get(spec.name)
        if isinstance(result, entity_resolver.Resolved):
            return result.value
        if isinstance(result, entity_resolver.Ambiguous):
            raise ResolutionFailed(spec.name, slot, f"'{raw}' mơ hồ", result.candidates)
        reason = f"không tìm thấy '{raw}'"
        if result.suggestion:
            reason += f" — {result.suggestion}"
        raise ResolutionFailed(spec.name, slot, reason)
