import { useEffect, useRef, useState } from 'react'
import { askChat } from './api'
import './App.css'

const STORAGE_KEY = 'lkg-chat'
const BOT_NAME = 'Trợ lý ĐHBK'

const SUGGESTIONS = [
  'Điều kiện xét học bổng khuyến khích học tập là gì?',
  'Sinh viên bị buộc thôi học trong trường hợp nào?',
  'Quy định mới nhất về học phí là văn bản nào?',
  'Văn bản 4511/QĐ-ĐHBK quy định gì?',
  'Sinh viên bị kỷ luật thế nào?',
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

const Icon = {
  plus: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 5v14M5 12h14" />
    </svg>
  ),
  send: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M21 3 10 14M21 3l-7 18-4-7-7-4 18-7z" />
    </svg>
  ),
  chat: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" />
    </svg>
  ),
  copy: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="9" y="9" width="12" height="12" rx="2" />
      <path d="M5 15V5a2 2 0 0 1 2-2h10" />
    </svg>
  ),
  check: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m5 12 5 5L20 7" />
    </svg>
  ),
  user: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </svg>
  ),
  spark: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6" />
    </svg>
  ),
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

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // Trình duyệt chặn clipboard (trang không phải https...): bỏ qua.
    }
  }

  return (
    <button type="button" className="icon-btn" onClick={copy} title={copied ? 'Đã chép' : 'Chép câu trả lời'}>
      {copied ? Icon.check : Icon.copy}
    </button>
  )
}

function Question({ text }) {
  return (
    <div className="question">
      <span className="avatar">{Icon.user}</span>
      <p>{text}</p>
    </div>
  )
}

function BotLabel() {
  return (
    <div className="bot-label">
      {BOT_NAME} {Icon.spark}
    </div>
  )
}

function Answer({ result, onPickCandidate, disabled }) {
  const candidates = result.clarification?.candidates || []
  const answered = result.kind === 'answer' || result.kind === 'agent_answer'
  return (
    <div className="answer">
      <BotLabel />
      <p className="answer-text">{result.answer}</p>
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
      <div className="answer-actions">
        <CopyButton text={result.answer} />
      </div>
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
  const threadRef = useRef(null)

  useEffect(() => save(threadId, messages), [threadId, messages])

  // Cuộn tới tận đáy, gồm cả khoảng đệm dành cho ô nhập nổi; cuộn tới phần tử
  // cuối thì đoạn cuối câu trả lời bị ô nhập che mất.
  useEffect(() => {
    const thread = threadRef.current
    thread?.scrollTo({ top: thread.scrollHeight, behavior: 'smooth' })
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
    <div className="app">
      <div className="shell">
        <aside className="sidebar">
          <div className="brand">TRỢ LÝ ĐHBK</div>
          <button type="button" className="new-chat" onClick={newConversation} disabled={loading}>
            {Icon.plus}
            Cuộc trò chuyện mới
          </button>

          <div className="sidebar-section">Câu hỏi gợi ý</div>
          <ul className="suggestion-list">
            {SUGGESTIONS.map((s) => (
              <li key={s}>
                <button type="button" onClick={() => send(s)} disabled={loading} title={s}>
                  {Icon.chat}
                  <span>{s}</span>
                </button>
              </li>
            ))}
          </ul>

          <p className="sidebar-note">
            Tra cứu quy chế, quy định của Trường Đại học Bách khoa – Đại học Đà Nẵng.
          </p>
        </aside>

        <main className="main">
          <header className="mobile-header">
            <span className="brand">TRỢ LÝ ĐHBK</span>
            <button type="button" className="icon-btn" onClick={newConversation} disabled={loading}
              title="Cuộc trò chuyện mới">
              {Icon.plus}
            </button>
          </header>

          <div className="thread" ref={threadRef}>
            {messages.length === 0 && (
              <div className="welcome">
                <h1>Chào bạn!</h1>
                <p>Bạn muốn hỏi gì về quy chế, quy định của Trường?</p>
                <div className="chip-list">
                  {SUGGESTIONS.slice(0, 4).map((s) => (
                    <button key={s} type="button" className="chip" onClick={() => send(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => {
              if (m.role === 'user') return <Question key={i} text={m.text} />
              if (m.role === 'error') {
                return (
                  <div key={i} className="answer answer-error">
                    <BotLabel />
                    <p className="answer-text">{m.text}</p>
                    <button type="button" className="chip" disabled={loading} onClick={() => retry(i, m.retry)}>
                      Thử lại
                    </button>
                  </div>
                )
              }
              return <Answer key={i} result={m.result} onPickCandidate={send} disabled={loading} />
            })}
            {loading && (
              <div className="answer">
                <BotLabel />
                <div className="typing" role="status" aria-label="Đang trả lời">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}
          </div>

          <form
            className="composer"
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
              placeholder="Bạn muốn hỏi gì?"
              aria-label="Câu hỏi"
              maxLength={1000}
            />
            <button type="submit" className="send" disabled={loading || !question.trim()} title="Gửi">
              {Icon.send}
            </button>
          </form>
        </main>
      </div>
    </div>
  )
}
