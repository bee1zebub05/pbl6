const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Ném Error với message rõ ràng cho MỌI trường hợp thất bại (network chết,
// backend trả lỗi có body JSON, backend trả lỗi không parse được JSON...)
// — App.jsx chỉ cần try/catch quanh 1 lời gọi này.
//
// threadId: mã hội thoại backend trả về ở lượt trước (null = hội thoại mới).
// Backend giữ lịch sử theo mã này (LangGraph checkpointer), FE không gửi lại lịch sử.
export async function askChat(question, threadId = null) {
  let res
  try {
    res = await fetch(`${BASE_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(threadId ? { question, thread_id: threadId } : { question }),
    })
  } catch {
    throw new Error('Không kết nối được tới backend — kiểm tra server có đang chạy không.')
  }

  let body = null
  try {
    body = await res.json()
  } catch {
    // body không phải JSON hợp lệ — vẫn xử lý tiếp bằng res.ok/res.status bên dưới
  }

  if (!res.ok) {
    const detail = body?.error || body?.detail || `HTTP ${res.status}`
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }

  return body
}
