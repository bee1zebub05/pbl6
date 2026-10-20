"""
CLI của chatbot:

  lkg ask "<câu hỏi>" [--verbose]        một câu hỏi, một lượt
  lkg ask --template TPL_X --param k=v   chạy thủ công một template (không LLM)
  lkg chat [--verbose]                   hội thoại nhiều lượt trong terminal

Bộ nhớ hội thoại (MemorySaver) sống trong tiến trình, nên hội thoại nhiều
lượt chỉ có ở `chat` — mỗi lệnh `ask` là một tiến trình mới.
"""

from __future__ import annotations

import argparse
import json
import uuid

from ..observability import setup_logging
from . import session_log
from .container import build_chat_service, build_template_query_service
from .models import ChatResponse, ResolutionFailed, TemplateParamError


def _print_response(r: ChatResponse, verbose: bool) -> None:
    print(f"\n{r.answer}\n")
    if r.clarification and r.clarification.candidates:
        print("Lựa chọn: " + " | ".join(r.clarification.candidates))
    meta = f"[{r.kind}] intent={r.intent} action={r.action} template={r.template} " \
           f"llm_calls={r.llm_calls} {r.elapsed_ms:.0f}ms turn={r.turn_id}"
    if r.trace_id:
        meta += f" trace={r.trace_id}"
    print(meta)
    if verbose:
        if r.cypher:
            print(f"[cypher] {r.cypher}")
            print(f"[params] {r.params}")
        if r.rows is not None:
            print(f"[rows] {len(r.rows)} dòng")
            for row in r.rows[:10]:
                print(f"   {json.dumps(row, ensure_ascii=False, default=str)[:300]}")
        if r.sources:
            print(f"[sources] {json.dumps(r.sources, ensure_ascii=False)[:600]}")
        if r.retrieval_reason:
            print(f"[retrieval] {r.retrieval_reason}")


def _parse_params(pairs: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in pairs:
        if "=" not in p:
            raise TemplateParamError(f"--param phải dạng key=value, nhận '{p}'")
        k, v = p.split("=", 1)
        out[k] = v
    return out


def ask_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hỏi chatbot một câu (hoặc chạy thủ công một template)")
    parser.add_argument("question", nargs="?", default=None)
    parser.add_argument("--template", help="Chạy thủ công một template, bỏ qua LLM (xem core/graph_query/templates/)")
    parser.add_argument("--param", action="append", default=[], help="key=value (tên $param của template)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if args.template:
        setup_logging()
        try:
            result = build_template_query_service().run(args.template, _parse_params(args.param))
        except (TemplateParamError, ResolutionFailed) as exc:
            print(f"LỖI: {exc}")
            return 1
        if args.verbose:
            print(f"[cypher] {result.cypher}\n[params] {result.params}\n[elapsed] {result.elapsed_ms:.1f} ms")
        print(f"{len(result.rows)} dòng:")
        for row in result.rows[:50]:
            print(f"  {row}")
        return 0

    if not args.question:
        parser.error("cần một câu hỏi hoặc --template")
    response = build_chat_service().ask(args.question)
    _print_response(response, args.verbose)
    _print_session_log(response.thread_id)
    return 1 if response.kind == "error" else 0


def _print_session_log(thread_id: str) -> None:
    path = session_log.session_path(thread_id)
    if path is not None:
        print(f"(log phiên: {path})")


def chat_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hội thoại nhiều lượt với chatbot trong terminal")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    service = build_chat_service()
    thread_id = uuid.uuid4().hex
    print("Chatbot văn bản pháp quy — gõ /new để bắt đầu hội thoại mới, /exit để thoát.")
    while True:
        try:
            question = input("\nBạn: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            _print_session_log(thread_id)
            return 0
        if not question:
            continue
        if question in ("/exit", "/quit"):
            _print_session_log(thread_id)
            return 0
        if question == "/new":
            _print_session_log(thread_id)
            thread_id = uuid.uuid4().hex
            print("(đã bắt đầu hội thoại mới)")
            continue
        _print_response(service.ask(question, thread_id=thread_id), args.verbose)
