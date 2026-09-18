import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { api } from '../api/client.js'

// 创作对话面板：多轮讨论 + 「提出方案」应用到表单
export default function ChatPanel({ projectId, context, title, target, onApply, placeholder }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [proposal, setProposal] = useState(null)
  const [applied, setApplied] = useState(false)
  const [error, setError] = useState(null)
  const boxRef = useRef(null)

  const load = () =>
    api
      .chatHistory(projectId, context)
      .then((d) => setMessages(d.messages))
      .catch(() => {}) // 首次加载失败保持空态即可（发送/提议的错误会显示）

  useEffect(() => {
    load()
  }, [projectId, context])

  useEffect(() => {
    boxRef.current?.scrollTo({ top: boxRef.current.scrollHeight })
  }, [messages])

  const send = async () => {
    if (!input.trim() || busy) return
    setBusy(true)
    setError(null)
    try {
      const r = await api.chatSend(projectId, context, input.trim())
      setMessages(r.messages)
      setInput('')
      setProposal(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const propose = async () => {
    setBusy(true)
    setError(null)
    try {
      const r = await api.chatPropose(projectId, context, target)
      const p = r.proposal
      setProposal(p)
      setApplied(false)
      if (p && onApply) {
        // 一步到位：方案生成后直接填入表单，免去二次点击；失败可手动重试
        try {
          await onApply(p)
          setApplied(true)
        } catch (e) {
          setError(`方案已生成，但填入表单失败：${e.message}。可点下方「应用到表单」重试。`)
        }
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const apply = async () => {
    if (!proposal) return
    setBusy(true)
    setError(null)
    try {
      await onApply(proposal)
      setApplied(true)
    } catch (e) {
      setError(`填入表单失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-semibold text-primary">💬 {title}</p>
        <button className="btn-ghost text-xs" onClick={() => { api.chatReset(projectId, context).then(load); setProposal(null) }}>
          清空对话
        </button>
      </div>

      <div ref={boxRef} className="min-h-96 max-h-[560px] overflow-auto space-y-2 mb-3 pr-1 pb-2">
        {messages.length === 0 && (
          <div className="h-80 flex items-center justify-center text-xs text-muted">
            和 AI 聊聊你的想法，满意后让它「提出方案」。
          </div>
        )}
        {messages.map((m, i) => (
          <div key={`${i}-${m.role}`} className={m.role === 'user' ? 'text-right' : 'text-left'}>
            <div
              className={`inline-block text-left rounded-lg px-3 py-2 max-w-[92%] ${
                m.role === 'user'
                  ? 'bg-primary text-white'
                  : 'bg-black/5 text-foreground dark:bg-white/10'
              }`}
            >
              {m.role === 'user' ? (
                <span className="text-sm whitespace-pre-wrap">{m.content}</span>
              ) : (
                <div className="chat-md text-sm leading-6">
                  <ReactMarkdown>{m.content}</ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {proposal && (
        <div className="rounded border border-border p-3 mb-3">
          <p className="text-xs font-medium text-primary mb-2">
            {applied ? '✓ AI 方案已填入表单（可微调后提交）' : 'AI 提出的方案'}
          </p>
          <ProposalPreview proposal={proposal} />
          <div className="flex flex-wrap gap-2 mt-2">
            <button className="btn-ghost text-xs" onClick={() => setProposal(null)}>收起</button>
            {onApply && !applied && (
              <button className="btn-primary text-xs" disabled={busy} onClick={apply}>
                {busy ? '处理中…' : '应用到表单'}
              </button>
            )}
          </div>
        </div>
      )}

      {error && (
        <div className="rounded border border-red-200 bg-red-50 dark:bg-red-900/20 dark:text-red-300 text-red-700 px-3 py-2 text-xs mb-3">
          {error}
        </div>
      )}

      <div className="flex gap-2">
        <input
          className="input text-sm py-2.5"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder={placeholder ?? '和 AI 讨论…'}
        />
        <button className="btn-ghost text-sm whitespace-nowrap px-4" disabled={busy} onClick={propose}>
          提出方案
        </button>
        <button className="btn-primary text-sm whitespace-nowrap px-5" disabled={busy || !input.trim()} onClick={send}>
          发送
        </button>
      </div>
    </div>
  )
}

function ProposalPreview({ proposal }) {
  if (!proposal) return null
  // 字符列表包装 → 取 items
  let p = proposal
  if (p.items && Array.isArray(p.items)) p = p.items
  return (
    <div className="text-xs text-muted space-y-1 max-h-64 overflow-auto">
      <KV rows={Object.entries(p)} />
    </div>
  )
}

function KV({ rows }) {
  const skipped = new Set(['version', 'id', 'items'])
  return (
    <>
      {rows.map(([k, v]) => {
        if (skipped.has(k)) return null
        if (v === null || v === undefined || v === '') return null
        if (Array.isArray(v)) {
          if (v.length === 0) return null
          const allObjects = v.every((x) => typeof x === 'object' && x !== null)
          if (allObjects) {
            return (
              <div key={k} className="pt-1">
                <span className="font-medium text-foreground">{k}：</span>
                <div className="space-y-1 pl-2">
                  {v.map((item, i) => (
                    <div key={i} className="rounded border border-border p-2">
                      <KV rows={Object.entries(item)} />
                    </div>
                  ))}
                </div>
              </div>
            )
          }
          return (
            <div key={k}><span className="font-medium text-foreground">{k}：</span>{v.join(' / ')}</div>
          )
        }
        if (typeof v === 'object') {
          return (
            <div key={k} className="pt-1">
              <span className="font-medium text-foreground">{k}：</span>
              <div className="pl-2"><KV rows={Object.entries(v)} /></div>
            </div>
          )
        }
        return <div key={k}><span className="font-medium text-foreground">{k}：</span>{String(v)}</div>
      })}
    </>
  )
}
