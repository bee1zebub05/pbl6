import { useState } from 'react'
import { askChat } from './api'
import './App.css'

// kind trả về từ /api/chat, xem core/nlq/pipeline.py::NlqResult:
//   template_result / freeform_result -> có rows thật, hiển thị như câu trả lời
//   resolution_failed / unsupported   -> không phải lỗi hệ thống, chỉ là bot
//                                        giải thích không trả lời được
const ANSWER_KINDS = new Set(['template_result', 'freeform_result'])

// Kết quả tìm kiếm ngữ nghĩa (embedding) — LUÔN chạy song song Cypher,
// độc lập với result.kind (kể cả khi Cypher unsupported/resolution_failed
// vẫn có thể có retrieval). Đây là khối hiển thị TẠM để tự mắt xem 2 loại
// kết quả — khi có bước LLM ghép rows+retrieval thành câu trả lời cuối,
// khối này sẽ đổi cách hiển thị (không cần xổ 2 khối rời như hiện tại).
function RetrievalSection({ result }) {
  if (!result.retrieval?.length && !result.retrieval_reason) return null

  return (
    <details className="retrieval-detail">
      <summary>
        Tìm kiếm ngữ nghĩa (retrieval)
        {result.retrieval?.length > 0 && (
          <span className="badge">{result.retrieval.length} đoạn liên quan</span>
        )}
        {result.retrieval_reason && <span className="badge badge-warn">lỗi retrieval</span>}
      </summary>
      {result.retrieval_reason ? (
        <p className="muted">{result.retrieval_reason}</p>
      ) : (
        <div className="retrieval-list">
          {result.retrieval.map((hit) => (
            <div key={hit.articleId} className="retrieval-hit">
              <div className="retrieval-hit-head">
                <span className="retrieval-heading">{hit.heading || hit.articleId}</span>
                <span className="badge">điểm {hit.score.toFixed(3)}</span>
                {hit.documentNumber && (
                  <span className="badge">
                    {hit.documentNumber}
                    {hit.status ? ` · ${hit.status}` : ''}
                  </span>
                )}
              </div>
              <p className="retrieval-text">{hit.text}</p>
            </div>
          ))}
        </div>
      )}
    </details>
  )
}

function BotMessage({ result, onPickCandidate }) {
  let content

  if (ANSWER_KINDS.has(result.kind)) {
    content = (
      <>
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
              <span className="badge badge-warn">
                tự sinh — soát lại
                {result.correction_attempts > 0 && ` · đã tự sửa ${result.correction_attempts} lần`}
              </span>
            )}
            {result.confidence != null && (
              <span className="badge">độ tin cậy {result.confidence.toFixed(2)}</span>
            )}
          </summary>
          <pre>{result.cypher}</pre>
        </details>
      </>
    )
  } else if (result.kind === 'resolution_failed' && result.missing_param) {
    // resolution_failed kèm missing_param -> bot đang hỏi lại, không phải lỗi/chấm dứt
    content = (
      <>
        <p>{result.reason || 'Bạn có thể nêu rõ hơn không?'}</p>
        {result.candidates?.length > 0 && (
          <div className="candidate-list">
            {result.candidates.map((c) => (
              <button key={c} type="button" className="candidate-btn" onClick={() => onPickCandidate(c)}>
                {c}
              </button>
            ))}
          </div>
        )}
      </>
    )
  } else {
    // resolution_failed chấm dứt hẳn / unsupported — bot giải thích, không phải lỗi
    content = <p>{result.reason || 'Không trả lời được câu hỏi này.'}</p>
  }

  const wrapperClass =
    result.kind === 'resolution_failed' && result.missing_param
      ? 'msg msg-bot msg-clarify'
      : !ANSWER_KINDS.has(result.kind)
        ? 'msg msg-bot msg-cant-answer'
        : 'msg msg-bot'

  return (
    <div className={wrapperClass}>
      {content}
      <RetrievalSection result={result} />
    </div>
  )
}

export default function App() {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  // Ngữ cảnh vòng hỏi-lại đang chờ trả lời — null nghĩa là câu hỏi tiếp theo
  // là 1 câu hỏi MỚI hoàn toàn. Backend không lưu gì (stateless), FE giữ
  // tạm object này và gửi lại nguyên trong request kế tiếp (xem api.js).
  const [pendingClarification, setPendingClarification] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    const q = question.trim()
    if (!q || loading) return

    const resumeSent = pendingClarification

    setMessages((prev) => [...prev, { role: 'user', text: q }])
    setQuestion('')
    setLoading(true)

    try {
      const result = await askChat(q, resumeSent)
      setMessages((prev) => [...prev, { role: 'bot', result }])
      if (result.kind === 'resolution_failed' && result.missing_param) {
        setPendingClarification({
          template: result.template,
          raw_params: result.raw_params || {},
          missing_param: result.missing_param,
          rounds: (resumeSent ? resumeSent.rounds : -1) + 1,
        })
      } else {
        setPendingClarification(null)
      }
    } catch (err) {
      // Lỗi gọi API (network chết, backend 500...) -> 1 message riêng, KHÔNG
      // throw tiếp -> người dùng gõ câu tiếp theo được ngay, UI không kẹt.
      // Không đụng pendingClarification — lỗi mạng, không phải câu trả lời
      // sai, nên vẫn giữ ngữ cảnh hỏi-lại để thử lại được.
      setMessages((prev) => [...prev, { role: 'error', text: err.message }])
    } finally {
      setLoading(false)
    }
  }

  function handlePickCandidate(text) {
    setQuestion(text)
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
          return <BotMessage key={i} result={m.result} onPickCandidate={handlePickCandidate} />
        })}
        {loading && <div className="msg msg-bot msg-loading">Đang xử lý…</div>}
      </div>

      {pendingClarification && (
        <div className="clarify-bar">
          <span className="muted">Bot đang chờ bạn bổ sung thông tin.</span>
          <button type="button" className="clarify-cancel" onClick={() => setPendingClarification(null)}>
            Hỏi câu khác
          </button>
        </div>
      )}

      <form className="chat-input" onSubmit={handleSubmit}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={pendingClarification ? 'Trả lời câu hỏi ở trên...' : 'Nhập câu hỏi...'}
          disabled={loading}
        />
        <button type="submit" disabled={loading || !question.trim()}>
          Gửi
        </button>
      </form>
    </div>
  )
}
