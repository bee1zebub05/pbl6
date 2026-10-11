"""Mô tả action cho prompt router.

Action chỉ có MỘT template thì mặc định lấy mô tả của template đó — chỉ cần
khai ở đây những action có NHIỀU template (chọn template theo slot) hoặc cần
mô tả bao quát hơn.
"""

from __future__ import annotations

AGENT_ACTION = "other"

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
