const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Backend tự dừng mỗi lượt ở 60 giây (LKG_TURN_DEADLINE_SECONDS); chờ dư một chút.
const TIMEOUT_MS = 90_000

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
      signal: AbortSignal.timeout(TIMEOUT_MS),
    })
  } catch (err) {
    if (err.name === 'TimeoutError') {
      throw new Error('Mình chờ lâu quá mà chưa có phản hồi. Bạn thử lại nhé.')
    }
    throw new Error('Mình chưa kết nối được tới máy chủ. Bạn thử lại sau một lát nhé.')
  }

  let body = null
  try {
    body = await res.json()
  } catch {
    // body không phải JSON hợp lệ — vẫn xử lý tiếp bằng res.ok/res.status bên dưới
  }

  if (!res.ok) {
    // Chi tiết lỗi đã nằm ở log backend; người dùng chỉ cần một câu dễ hiểu.
    if (res.status >= 500) {
      throw new Error('Xin lỗi, mình đang gặp trục trặc nên chưa trả lời được. Bạn thử lại sau ít phút nhé.')
    }
    throw new Error(typeof body?.error === 'string' ? body.error : 'Mình chưa đọc được câu hỏi này, bạn thử viết lại nhé.')
  }

  return body
}
