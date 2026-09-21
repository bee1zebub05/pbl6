import { useState } from 'react'
import { askChat } from './api'
import './App.css'

// kind trả về từ /api/chat, xem core/nlq/pipeline.py::NlqResult:
//   template_result / freeform_result -> có rows thật, hiển thị như câu trả lời
//   resolution_failed / unsupported   -> không phải lỗi hệ thống, chỉ là bot
//                                        giải thích không trả lời được
const ANSWER_KINDS = new Set(['template_result', 'freeform_result'])

function BotMessage({ result }) {
  if (ANSWER_KINDS.has(result.kind)) {
    return (
      <div className="msg msg-bot">
        {result.rows?.length ? (
          <table className="rows-table">
            <thead>
              <tr>
                {Object.keys(result.rows[0]).map((col) => (
                  <th key={col}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows.map((row, i) => (
                <tr key={i}>
                  {Object.values(row).map((val, j) => (
                    <td key={j}>{String(val)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Không có dòng kết quả nào.</p>
        )}
        <details className="cypher-detail">
          <summary>
            Cypher đã chạy
            {result.kind === 'freeform_result' && (
              <span className="badge badge-warn">tự sinh — soát lại</span>
            )}
            {result.confidence != null && (
              <span className="badge">độ tin cậy {result.confidence.toFixed(2)}</span>
            )}
          </summary>
          <pre>{result.cypher}</pre>
        </details>
      </div>
    )
  }

  // resolution_failed / unsupported — bot giải thích, không phải lỗi
  return (
    <div className="msg msg-bot msg-cant-answer">
      <p>{result.reason || 'Không trả lời được câu hỏi này.'}</p>
    </div>
  )
}

export default function App() {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    const q = question.trim()
    if (!q || loading) return

    setMessages((prev) => [...prev, { role: 'user', text: q }])
    setQuestion('')
    setLoading(true)

    try {
      const result = await askChat(q)
      setMessages((prev) => [...prev, { role: 'bot', result }])
    } catch (err) {
      // Lỗi gọi API (network chết, backend 500...) -> 1 message riêng, KHÔNG
      // throw tiếp -> người dùng gõ câu tiếp theo được ngay, UI không kẹt.
      setMessages((prev) => [...prev, { role: 'error', text: err.message }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-page">
      <header className="chat-header">
        <h1>legal_knowledge_graph — chat</h1>
        <p className="muted">Hỏi bằng tiếng Việt tự nhiên, trả lời qua Cypher thật trên Neo4j.</p>
      </header>

      <div className="chat-log">
        {messages.length === 0 && (
          <p className="muted placeholder">
            Ví dụ: "Top 5 cơ quan ban hành nhiều văn bản nhất"
          </p>
        )}
        {messages.map((m, i) => {
          if (m.role === 'user') {
            return (
              <div key={i} className="msg msg-user">
                {m.text}
              </div>
            )
          }
          if (m.role === 'error') {
            return (
              <div key={i} className="msg msg-error">
                {m.text}
              </div>
            )
          }
          return <BotMessage key={i} result={m.result} />
        })}
        {loading && <div className="msg msg-bot msg-loading">Đang xử lý…</div>}
      </div>

      <form className="chat-input" onSubmit={handleSubmit}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Nhập câu hỏi..."
          disabled={loading}
        />
        <button type="submit" disabled={loading || !question.trim()}>
          Gửi
        </button>
      </form>
    </div>
  )
}
