"""
Ráp node thành LangGraph:

    START → intent ─┬─ smalltalk / out_of_scope / unsafe → respond_direct → END
                    └─ domain_query → route ─┬─ khớp template  → run_template
                                             ├─ thiếu slot     → ask_clarify → END
                                             └─ thừa slot/other → agent → END
    run_template ─┬─ có kết quả        → retrieve → answer → END
                  ├─ thống kê / đếm    → answer → END (không GraphRAG, actions.py::RETRIEVAL_NONE)
                  ├─ resolve lỗi       → ask_clarify (còn lượt) / agent (hết lượt)
                  └─ lỗi tham số       → agent
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from ..models import ChatState
from .nodes import (AGENT, ANSWER, ASK_CLARIFY, INTENT, RESPOND_DIRECT, RETRIEVE, ROUTE, RUN_TEMPLATE,
                    ChatNodes)


class ChatGraphBuilder:
    def __init__(self, nodes: ChatNodes):
        self._nodes = nodes

    def build(self, checkpointer: BaseCheckpointSaver | None):
        n = self._nodes
        graph = StateGraph(ChatState)
        for name, fn in (
            (INTENT, n.intent), (RESPOND_DIRECT, n.respond_direct), (ROUTE, n.route),
            (RUN_TEMPLATE, n.run_template), (ASK_CLARIFY, n.ask_clarify), (RETRIEVE, n.retrieve),
            (ANSWER, n.answer), (AGENT, n.agent),
        ):
            graph.add_node(name, fn)

        graph.add_edge(START, INTENT)
        graph.add_conditional_edges(INTENT, n.after_intent, [ROUTE, RESPOND_DIRECT, END])
        graph.add_conditional_edges(ROUTE, n.after_route, [RUN_TEMPLATE, ASK_CLARIFY, AGENT, END])
        graph.add_conditional_edges(RUN_TEMPLATE, n.after_run_template, [RETRIEVE, ANSWER, ASK_CLARIFY, AGENT, END])
        graph.add_edge(RETRIEVE, ANSWER)
        for terminal in (RESPOND_DIRECT, ASK_CLARIFY, ANSWER, AGENT):
            graph.add_edge(terminal, END)
        return graph.compile(checkpointer=checkpointer, name="legal_chat")
