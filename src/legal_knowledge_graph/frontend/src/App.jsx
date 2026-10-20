import { useState } from 'react'
import { askChat } from './api'
import './App.css'

// kind trả về từ /api/chat (core/chat/models/response.py::ChatResponse):
//   answer / agent_answer -> câu trả lời từ dữ liệu
//   no_data               -> không tìm thấy trong kho
//   clarification         -> bot hỏi lại (có thể kèm ứng viên)
//   direct                -> chào hỏi / ngoài phạm vi / yêu cầu bị từ chối
//   error                 -> sự cố hạ tầng, bot đã báo bằng câu thân thiện
const KIND_CLASS = {
  clarification: 'msg-clarify',
  direct: 'msg-direct',
  no_data: 'msg-cant-answer',
  error: 'msg-cant-answer',
}

// Giao diện chỉ hiện câu trả lời (và nút ứng viên khi bot hỏi lại). Chi tiết
// từng bước — Cypher, dòng kết quả, Điều GraphRAG, prompt LLM — nằm ở log phiên
// logs/sessions/ (core/chat/session_log.py), không đưa lên UI.
function BotMessage({ result, onPickCandidate, disabled }) {
  const candidates = result.clarification?.candidates || []
  return (
    <div className={`msg msg-bot ${KIND_CLASS[result.kind] || ''}`}>
      <p className="answer">{result.answer}</p>
      {candidates.length > 0 && (
        <div className="candidate-list">
          {candidates.map((c) => (
            <button key={c} type="button" className="candidate-btn" disabled={disabled} onClick={() => onPickCandidate(c)}>
              {c}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  // Mã hội thoại do backend cấp ở lượt đầu; null = lượt kế tiếp mở hội thoại mới.
  const [threadId, setThreadId] = useState(null)

  async function send(text) {
    const q = text.trim()
    if (!q || loading) return

    setMessages((prev) => [...prev, { role: 'user', text: q }])
    setQuestion('')
    setLoading(true)
    try {
      const result = await askChat(q, threadId)
      setThreadId(result.thread_id)
      setMessages((prev) => [...prev, { role: 'bot', result }])
    } catch (err) {
      // Lỗi gọi API -> một message riêng, UI không kẹt, vẫn giữ hội thoại để thử lại.
      setMessages((prev) => [...prev, { role: 'error', text: err.message }])
    } finally {
      setLoading(false)
    }
  }

  function newConversation() {
    setThreadId(null)
    setMessages([])
  }

  return (
    <div className="chat-page">
      <header className="chat-header">
        <div>
          <h1>Tra cứu văn bản pháp quy — ĐH Bách khoa</h1>
          <p className="muted">Hỏi bằng tiếng Việt; câu trả lời dựa trên đồ thị tri thức văn bản.</p>
        </div>
        <button type="button" className="new-chat" onClick={newConversation} disabled={loading}>
          Cuộc hội thoại mới
        </button>
      </header>

      <div className="chat-log">
        {messages.length === 0 && (
          <p className="muted placeholder">Ví dụ: "Văn bản 4511/QĐ-ĐHBK quy định gì?" rồi hỏi tiếp "Nó thay thế văn bản nào?"</p>
        )}
        {messages.map((m, i) => {
          if (m.role === 'user') {
            return <div key={i} className="msg msg-user">{m.text}</div>
          }
          if (m.role === 'error') {
            return <div key={i} className="msg msg-error">{m.text}</div>
          }
          return <BotMessage key={i} result={m.result} onPickCandidate={send} disabled={loading} />
        })}
        {loading && <div className="msg msg-bot msg-loading">Đang xử lý…</div>}
      </div>

      <form
        className="chat-input"
        onSubmit={(e) => {
          e.preventDefault()
          send(question)
        }}
      >
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Nhập câu hỏi..."
          maxLength={1000}
          disabled={loading}
        />
        <button type="submit" disabled={loading || !question.trim()}>
          Gửi
        </button>
      </form>
    </div>
  )
}
