"""
Cài đặt cụ thể của các port trong ../ports.py (LLM, Neo4j). Chỉ nối và ghi log/trace;
ráp vào chatbot ở ../container.py (build_llm chọn LLM theo LKG_LLM_PROVIDER).

    langchain_llm.py          lớp nền chung cho LLM chạy qua LangChain
    gemini_llm.py             LLMProvider: Gemini Developer API + bể key
    openai_compatible_llm.py  LLMProvider: mọi server chuẩn OpenAI API (vLLM, Ollama, OpenRouter...)
    neo4j_adapters.py         QueryExecutor, EntityResolver
    graph_retriever.py  ContextRetriever (GraphRAG: embed + Cypher)
"""
