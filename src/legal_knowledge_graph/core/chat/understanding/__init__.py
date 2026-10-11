"""
Bước 1 — hiểu câu hỏi (node intent, route):

    intent.py             phân loại intent, viết lại câu nối tiếp (1 lượt LLM)
    history.py            cắt và trình bày lịch sử hội thoại cho prompt
    router.py             trích action + slot (1 lượt LLM), bù số hiệu bằng regex
    template_selector.py  chọn template từ action + slot (thuần Python)
"""
