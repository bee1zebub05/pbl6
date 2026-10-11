"""
Agent ReAct cho câu hỏi không khớp template (nhiều điều kiện, hỏi Điều cụ
thể, so sánh...). Là một subgraph LangGraph riêng: `llm` ⇄ `tools`, tối đa
`max_steps` lượt gọi LLM; tin nhắn nháp của agent KHÔNG ghi vào lịch sử hội
thoại (compile với checkpointer=False).

Ba tool, mỗi tool trả (nội dung cho LLM, artifact có cấu trúc) — artifact
giữ Cypher/dòng/Điều thật để node chính trả ra API làm nguồn, không phải
đọc lại văn bản LLM viết.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool, tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from neo4j.exceptions import ClientError
from pydantic import BaseModel, Field, create_model

from .. import config
from ..graph_query.cypher_guard import GuardRejected
from ..graph_query.templates import INT_SLOTS, SLOT_TO_PARAM
from ..observability import log_event
from .models import AgentOutcome, DocumentContext, GraphContext, ResolutionFailed, TemplateParamError
from .ports import ContextRetriever, LLMProvider, QueryExecutor
from .prompts import AGENT_GAVE_UP_ANSWER, AGENT_SYSTEM
from .answering.evidence import context_to_text, rows_to_text
from .retrieval.template_query import TemplateQueryService

_LAST_STEP_NOTE = "Đã hết lượt tra cứu. KHÔNG gọi thêm công cụ — trả lời người dùng ngay bằng bằng chứng đã có."


class _AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def _run_template_args() -> type[BaseModel]:
    """Schema tham số của tool run_template, sinh từ SLOT_TO_PARAM — thêm slot
    mới vào kho template là tool tự nhận, không phải sửa danh sách ở đây."""

    fields: dict[str, Any] = {
        "template": (str, Field(description="Tên template trong danh mục, ví dụ TPL_DOCS_BY_ORG_STATUS")),
    }
    for slot, param in SLOT_TO_PARAM.items():
        kind = int if slot in INT_SLOTS else str
        fields[param] = (kind | None, Field(default=None, description=f"Giá trị thô cho {slot} (nếu template cần)"))
    return create_model("RunTemplateArgs", **fields)


RunTemplateArgs = _run_template_args()


class AgentService:
    def __init__(self, llm: LLMProvider, templates: TemplateQueryService, executor: QueryExecutor,
                 retriever: ContextRetriever, max_steps: int, max_rows: int):
        self._llm = llm
        self._templates = templates
        self._executor = executor
        self._retriever = retriever
        self._max_steps = max_steps
        self._max_rows = max_rows
        self._tools = self._build_tools()
        self._graph = self._build_graph()

    # ------------------------------------------------------------ tools

    def _build_tools(self) -> list[BaseTool]:
        max_rows = self._max_rows

        def run_template(template: str, **raw: Any) -> tuple[str, dict]:
            params = {k: v for k, v in raw.items() if v not in (None, "")}
            try:
                result = self._templates.run(template, params)
            except ResolutionFailed as exc:
                hint = f" Ứng viên: {', '.join(exc.candidates)}." if exc.candidates else ""
                return self._tool_result("run_template", f"KHÔNG RESOLVE ĐƯỢC '{exc.param_name}': {exc.reason}.{hint}")
            except TemplateParamError as exc:
                return self._tool_result("run_template", f"LỖI THAM SỐ: {exc}")
            query_limit = result.params.get("limit") if isinstance(result.params.get("limit"), int) else None
            return self._tool_result("run_template", rows_to_text(result.rows, max_rows, query_limit),
                                     cypher=result.cypher, rows=result.rows)

        run_template_tool = StructuredTool.from_function(
            func=run_template, name="run_template", args_schema=RunTemplateArgs,
            description="Chạy một truy vấn có sẵn (đã kiểm duyệt) theo tên template và tham số thô.",
            response_format="content_and_artifact",
        )

        @tool("run_cypher", response_format="content_and_artifact")
        def run_cypher(cypher: str) -> tuple[str, dict]:
            """Chạy Cypher CHỈ ĐỌC do bạn viết (MATCH/WHERE/RETURN...). Hệ thống tự kiểm duyệt và ép LIMIT."""

            try:
                capped, result = self._executor.run_guarded(cypher)
            except GuardRejected as exc:
                return self._tool_result("run_cypher", f"BỊ CHẶN: {exc.reason}. Hãy sửa Cypher theo đúng schema.")
            except ClientError as exc:
                return self._tool_result("run_cypher", f"LỖI KHI CHẠY CYPHER: {exc.message}")
            return self._tool_result("run_cypher", rows_to_text(result.rows, max_rows, config.CYPHER_ROW_CAP),
                                     cypher=capped, rows=result.rows)

        @tool("search_articles", response_format="content_and_artifact")
        def search_articles(query: str) -> tuple[str, dict]:
            """Tìm các Điều liên quan tới câu hỏi (ngữ nghĩa + từ khoá), kèm hiệu lực thực tế của văn bản
            chứa Điều, văn bản thay thế / sửa đổi và căn cứ."""

            context = self._retriever.retrieve(query)
            content = "Không có Điều nào phù hợp." if context.is_empty() else context_to_text(context)
            return self._tool_result("search_articles", content, context=context)

        return [run_template_tool, run_cypher, search_articles]

    @staticmethod
    def _tool_result(name: str, content: str, **artifact: Any) -> tuple[str, dict]:
        context = artifact.get("context")
        log_event("agent.tool", tool=name, rows=len(artifact.get("rows") or []),
                  articles=len(context.hits()) if context else 0, ok="rows" in artifact or "context" in artifact,
                  note=None if artifact else content[:200])
        return content, artifact

    # ------------------------------------------------------------ graph

    def _call_llm(self, state: _AgentState) -> dict:
        messages = state["messages"]
        steps_done = sum(1 for m in messages if isinstance(m, AIMessage))
        if steps_done >= self._max_steps - 1:
            messages = [*messages, HumanMessage(_LAST_STEP_NOTE)]
        response = self._llm.invoke_with_tools(messages, self._tools, node="agent")
        if steps_done >= self._max_steps - 1 and response.tool_calls:
            # Hết lượt mà model vẫn đòi gọi tool -> dừng, không vòng tiếp.
            response = AIMessage(content=AGENT_GAVE_UP_ANSWER)
        return {"messages": [response]}

    def _build_graph(self):
        graph = StateGraph(_AgentState)
        graph.add_node("llm", self._call_llm)
        graph.add_node("tools", ToolNode(self._tools))
        graph.add_edge(START, "llm")
        graph.add_conditional_edges("llm", tools_condition, {"tools": "tools", END: END})
        graph.add_edge("tools", "llm")
        return graph.compile(checkpointer=False, name="agent")

    # ------------------------------------------------------------ run

    def run(self, question: str) -> AgentOutcome:
        state = self._graph.invoke(
            {"messages": [SystemMessage(AGENT_SYSTEM), HumanMessage(question)]},
            config={"recursion_limit": 2 * self._max_steps + 2},
        )
        return self._outcome(state["messages"])

    @staticmethod
    def _outcome(messages: list[AnyMessage]) -> AgentOutcome:
        cypher: str | None = None
        rows: list[dict] = []
        documents: list[DocumentContext] = []
        tool_calls: list[dict] = []
        for m in messages:
            if isinstance(m, AIMessage):
                tool_calls += [{"tool": c["name"], "args": c["args"]} for c in m.tool_calls]
            elif isinstance(m, ToolMessage) and isinstance(m.artifact, dict):
                if m.artifact.get("rows") is not None:
                    cypher, rows = m.artifact.get("cypher"), m.artifact["rows"]
                if m.artifact.get("context") is not None:
                    documents += m.artifact["context"].documents

        final = messages[-1]
        answer = final.text.strip() if isinstance(final, AIMessage) and not final.tool_calls else ""
        log_event("agent", steps=sum(isinstance(m, AIMessage) for m in messages),
                  tools=[c["tool"] for c in tool_calls], answered=bool(answer))
        return AgentOutcome(answer=answer or AGENT_GAVE_UP_ANSWER, cypher=cypher, rows=rows,
                            context=GraphContext(documents=documents), tool_calls=tool_calls)
