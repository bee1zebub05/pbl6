"""Mô tả action cho prompt router, và mức GraphRAG của từng action.

Action chỉ có MỘT template thì mặc định lấy mô tả của template đó — chỉ cần
khai ở đây những action có NHIỀU template (chọn template theo slot) hoặc cần
mô tả bao quát hơn.
"""

from __future__ import annotations

from typing import Literal

AGENT_ACTION = "other"

RetrievalMode = Literal["full", "scope", "none"]

# Mức GraphRAG (bước `retrieve`) sau khi template trả kết quả:
#   full   hỏi NỘI DUNG quy định — Điều gần nghĩa toàn kho + Điều trong văn bản kết quả
#   scope  hỏi về văn bản / quan hệ / danh sách — chỉ Điều trong các văn bản kết quả,
#          để vẫn hiệu chỉnh hiệu lực theo quan hệ thay thế / bãi bỏ
#   none   thống kê, đếm, xếp hạng, hồ sơ người / cơ quan — kết quả template đã đủ
# Action không khai ở hai tập dưới mặc định là scope.
RETRIEVAL_FULL: frozenset[str] = frozenset({
    "search_articles", "article_text", "document_articles", "document_contents", "search_contents",
    "list_contents", "legal_basis", "latest_document_about",
})
RETRIEVAL_NONE: frozenset[str] = frozenset({
    "status_distribution", "stats_by_authority_level", "stats_by_topic", "stats_by_type", "stats_by_year",
    "relation_counts", "most_cited", "longest_chains", "missing_documents", "amended_still_active",
    "org_citation_flow", "count_documents", "rank_orgs", "rank_signers", "org_structure", "org_topic_breakdown",
    "org_signers", "org_profile", "person_profile",
})


def retrieval_mode(action: str | None) -> RetrievalMode:
    if action in RETRIEVAL_FULL:
        return "full"
    if action in RETRIEVAL_NONE:
        return "none"
    return "scope"

ACTION_DESCRIPTIONS: dict[str, str] = {
    "list_documents": "Liệt kê văn bản theo điều kiện lọc: cơ quan ban hành (org), lĩnh vực (topic), nhóm đối tượng "
                      "(target_group), loại văn bản (doc_type), năm ban hành (year) hoặc từ năm (since_year), "
                      "kèm hiệu lực (status). Điền ĐỦ mọi điều kiện người dùng nêu.",
    "documents_signed_by": "Liệt kê văn bản do một người (person) hoặc người giữ một chức danh (position, ví dụ "
                           "Hiệu trưởng) ký.",
    "count_documents": "Đếm số văn bản thoả điều kiện (org, topic, target_group, doc_type, year, status).",
    "search_articles": "Hỏi về NỘI DUNG quy định (học phí, học bổng, kỷ luật, thôi học, tốt nghiệp...): tìm các Điều "
                       "chứa cụm từ (phrase), có thể giới hạn trong một văn bản (doc_number), văn bản còn hiệu lực "
                       "(status), của một cơ quan (org), cho một nhóm đối tượng (target_group) hoặc một lĩnh vực (topic).",
    AGENT_ACTION: "Câu hỏi trong phạm vi kho văn bản nhưng không khớp action nào ở trên (so sánh nhiều văn bản, "
                  "câu hỏi tổng hợp đặc biệt...).",
}
