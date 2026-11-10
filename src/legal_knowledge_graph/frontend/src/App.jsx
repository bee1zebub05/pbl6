import { useEffect, useRef, useState } from 'react'
import { askChat } from './api'
import './App.css'

const STORAGE_KEY = 'lkg-chat'

const SUGGESTIONS = [
  'Điều kiện xét học bổng khuyến khích học tập là gì?',
  'Sinh viên bị buộc thôi học trong trường hợp nào?',
  'Quy định mới nhất về học phí là văn bản nào?',
  'Văn bản 4511/QĐ-ĐHBK quy định gì?',
]

const STATUS_LABEL = {
  CON_HIEU_LUC: 'còn hiệu lực',
  HET_HIEU_LUC: 'hết hiệu lực',
  CHUA_HIEU_LUC: 'chưa có hiệu lực',
}

// Tải lại trang vẫn giữ hội thoại trong tab. Không có sessionStorage (chế độ
// riêng tư, bị chặn...) thì coi như hội thoại mới, không làm hỏng trang.
function loadSaved() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY))
    return Array.isArray(saved?.messages) ? saved : null
  } catch {
    return null
  }
}

function save(threadId, messages) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ threadId, messages }))
  } catch {
    // Chỉ là tiện ích, lưu không được thì thôi.
  }
}

// `sources` có cả dòng theo văn bản lẫn theo Điều (core/chat/answering/evidence.py):
// gom về mỗi văn bản một mục. Dòng theo Điều mang tiêu đề của Điều nên không lấy làm tiêu đề văn bản.
function groupSources(sources = []) {
  const docs = new Map()
  for (const source of sources) {
    if (!source.documentNumber) continue
    const doc = docs.get(source.documentNumber) || {
      number: source.documentNumber,
      title: null,
      status: null,
      articles: [],
    }
    if (!source.articleId && source.title) doc.title = source.title
    doc.status = doc.status || source.status
    const article = source.articleId?.split('#').pop()
    if (article && !doc.articles.includes(article)) doc.articles.push(article)
    docs.set(source.documentNumber, doc)
  }
  return [...docs.values()]
}

function Sources({ sources }) {
  const docs = groupSources(sources)
  if (docs.length === 0) return null
  return (
    <details className="sources">
      <summary>Nguồn ({docs.length})</summary>
      <ul>
        {docs.map((doc) => (
          <li key={doc.number}>
            <strong>{doc.number}</strong>
            {doc.title && ` ${doc.title}`}
            {doc.articles.length > 0 && ` (${doc.articles.join(', ')})`}
            {STATUS_LABEL[doc.status] && <span className="muted"> · {STATUS_LABEL[doc.status]}</span>}
          </li>
        ))}
      </ul>
    </details>
  )
}

function BotMessage({ result, onPickCandidate, disabled }) {
  const candidates = result.clarification?.candidates || []
  const answered = result.kind === 'answer' || result.kind === 'agent_answer'
  return (
    <div className="msg msg-bot">
      <p className="answer">{result.answer}</p>
      {candidates.length > 0 && (
        <div className="chip-list">
          {candidates.map((c) => (
            <button key={c} type="button" className="chip" disabled={disabled} onClick={() => onPickCandidate(c)}>
              {c}
            </button>
          ))}
        </div>
      )}
      {answered && <Sources sources={result.sources} />}
    </div>
  )
}

export default function App() {
  const [saved] = useState(loadSaved)
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState(saved?.messages || [])
  const [loading, setLoading] = useState(false)
  // Mã hội thoại do backend cấp ở lượt đầu; null = lượt kế tiếp mở hội thoại mới.
  const [threadId, setThreadId] = useState(saved?.threadId || null)
  const inputRef = useRef(null)
  const bottomRef = useRef(null)

  useEffect(() => save(threadId, messages), [threadId, messages])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, loading])

  useEffect(() => {
    if (!loading) inputRef.current?.focus()
  }, [loading])

  // Ô nhập giãn theo nội dung; trần chiều cao nằm ở CSS.
  useEffect(() => {
    const input = inputRef.current
    if (!input) return
    input.style.height = 'auto'
    // scrollHeight không tính viền: thiếu phần này ô nhập luôn hiện thanh cuộn.
    input.style.height = `${input.scrollHeight + input.offsetHeight - input.clientHeight}px`
  }, [question])

  async function ask(q) {
    setLoading(true)
    try {
      const result = await askChat(q, threadId)
      setThreadId(result.thread_id)
      const { kind, answer, clarification, sources } = result
      setMessages((prev) => [...prev, { role: 'bot', result: { kind, answer, clarification, sources } }])
    } catch (err) {
      // Lỗi gọi API -> một message riêng có nút thử lại, vẫn giữ hội thoại.
      setMessages((prev) => [...prev, { role: 'error', text: err.message, retry: q }])
    } finally {
      setLoading(false)
    }
  }

  function send(text) {
    const q = text.trim()
    if (!q || loading) return
    setMessages((prev) => [...prev, { role: 'user', text: q }])
    setQuestion('')
    ask(q)
  }

  function retry(index, q) {
    if (loading) return
    setMessages((prev) => prev.filter((_, i) => i !== index))
    ask(q)
  }

  function newConversation() {
    setThreadId(null)
    setMessages([])
    setQuestion('')
    inputRef.current?.focus()
  }

  function onInputKeyDown(e) {
    // isComposing: Enter đang chốt chữ của bộ gõ, chưa phải lệnh gửi.
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send(question)
    }
  }

  return (
    <div className="chat-page">
      <header className="chat-header">
        <h1>Trợ lý văn bản ĐH Bách khoa</h1>
        <button type="button" className="new-chat" onClick={newConversation} disabled={loading}>
          Cuộc trò chuyện mới
        </button>
      </header>

      <div className="chat-log">
        {messages.length === 0 && (
          <div className="welcome">
            <p>Chào bạn! Bạn muốn hỏi gì về quy chế, quy định của Trường?</p>
            <div className="chip-list">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className="chip" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => {
          if (m.role === 'user') {
            return <div key={i} className="msg msg-user">{m.text}</div>
          }
          if (m.role === 'error') {
            return (
              <div key={i} className="msg msg-error">
                <p>{m.text}</p>
                <button type="button" className="chip" disabled={loading} onClick={() => retry(i, m.retry)}>
                  Thử lại
                </button>
              </div>
            )
          }
          return <BotMessage key={i} result={m.result} onPickCandidate={send} disabled={loading} />
        })}
        {loading && (
          <div className="msg msg-bot typing" role="status" aria-label="Đang trả lời">
            <span />
            <span />
            <span />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        className="chat-input"
        onSubmit={(e) => {
          e.preventDefault()
          send(question)
        }}
      >
        <textarea
          ref={inputRef}
          rows={1}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={onInputKeyDown}
          placeholder="Nhập câu hỏi..."
          aria-label="Câu hỏi"
          maxLength={1000}
        />
        <button type="submit" disabled={loading || !question.trim()}>
          Gửi
        </button>
      </form>
    </div>
  )
}
