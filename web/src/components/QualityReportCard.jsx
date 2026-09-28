import { useMemo, useState } from 'react'
import { api } from '../api/client.js'

const fmtKey = (key) => {
  const [v, c] = String(key).split('_').map(Number)
  return `卷${v}第${c}章`
}

// ---- 句级高亮：与对方文本大二元组重叠率 ≥0.5 的句子标记为疑似照搬 ----
const bigrams = (s) => {
  const t = String(s ?? '').replace(/\s/g, '')
  const set = new Set()
  for (let i = 0; i < t.length - 1; i++) set.add(t.slice(i, i + 2))
  return set
}
const splitSentences = (text) => {
  const parts = []
  let buf = ''
  for (const ch of String(text ?? '')) {
    buf += ch
    if ('。！？…\n'.includes(ch)) {
      parts.push(buf)
      buf = ''
    }
  }
  if (buf.trim()) parts.push(buf)
  return parts.filter((p) => p.trim())
}
const markOverlaps = (text, otherText) => {
  const other = bigrams(otherText)
  return splitSentences(text).map((sent) => {
    const g = bigrams(sent)
    let hit = 0
    g.forEach((x) => other.has(x) && hit++)
    return { sent, hit: g.size > 0 && hit / g.size >= 0.5 }
  })
}

const MarkedText = ({ text, other }) => (
  <div className="text-xs leading-6 whitespace-pre-wrap max-h-64 overflow-auto">
    {markOverlaps(text, other).map((p, i) =>
      p.hit ? (
        <mark key={i} className="bg-red-200/70 dark:bg-red-500/30 rounded-sm">{p.sent}</mark>
      ) : (
        <span key={i}>{p.sent}</span>
      ),
    )}
  </div>
)

const Pane = ({ title, text, other }) => (
  <div className="rounded border border-border p-2 min-w-0">
    <p className="text-xs font-medium text-muted mb-1">{title}</p>
    <MarkedText text={text} other={other} />
  </div>
)

const dupSig = (d) => `${d.type}:${d.a.source}:${d.a.index}:${d.b.source}:${d.b.index}`

// 质检裁决卡：机器审核结果 + 重复片段并排对比 + 作者裁决（接受即定稿，不再生成）
export default function QualityReportCard({ projectId, vol, ch, report, pending, onChangePending, onEditScene }) {
  const [dismissed, setDismissed] = useState([])
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)

  const dups = useMemo(
    () => (report?.duplicates ?? []).filter((d) => !dismissed.includes(dupSig(d))),
    [report, dismissed],
  )
  const missing = report?.missing_beats ?? []
  if (!report || (dups.length === 0 && missing.length === 0)) {
    if (!report) return null
    return (
      <div className="card p-3 text-xs text-muted flex items-center gap-2">
        <span className="text-green-600 dark:text-green-400 font-medium">✅ 质检通过</span>
        <span>
          {report.words?.actual ?? 0} 字 · 单句段落占比 {(Math.round((report.style?.ratio ?? 0) * 100)) }%
        </span>
      </div>
    )
  }

  const removeScene = (idx) => {
    const scenes = (pending?.scenes ?? []).filter((_, i) => i !== idx)
    onChangePending({ ...pending, scenes }, undefined)
  }
  const aiRewrite = async (sceneId, suggested) => {
    const instruction = window.prompt('改写方向（留空 = 自由重写，保持情节、换掉重复表达）', suggested || '')
    if (instruction === null) return
    setBusy(sceneId)
    setError(null)
    try {
      const r = await api.pendingSceneRewrite(projectId, vol, ch, sceneId, instruction.trim())
      onChangePending(r.chapter, r.quality)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(null)
    }
  }
  const dismiss = (sig) => setDismissed([...dismissed, sig])

  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-amber-600 dark:text-amber-400">🛠 机器质检报告</span>
        <span className="text-xs text-muted">先机审、后人审：以下问题由你裁决，接受/编辑后的文本直接作为原文，不再自动生成</span>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}

      {dups.map((d) => {
        const sig = dupSig(d)
        const labelA = d.type === 'intra' ? `本章场景 ${d.a.index + 1} · ${d.a.heading || '（无标题）'}` : `${fmtKey(d.a.source)} · ${d.a.heading || '（无标题）'}（已写）`
        const labelB = `本章场景 ${d.b.index + 1} · ${d.b.heading || '（无标题）'}（新稿）`
        return (
          <div key={sig} className="rounded border border-amber-300 dark:border-amber-700 p-3 space-y-2">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <span className="text-xs font-medium text-amber-700 dark:text-amber-300">
                {d.type === 'intra' ? '本章两个场景互相重复' : '与最近章节的场景重复'} · 相似度 {d.ratio}
              </span>
              <button className="btn-ghost text-xs" onClick={() => dismiss(sig)}>忽略此项</button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <Pane title={labelA} text={d.a.text} other={d.b.text} />
              <Pane title={labelB} text={d.b.text} other={d.a.text} />
            </div>
            <div className="flex flex-wrap gap-2">
              {d.type === 'intra' ? (
                <>
                  <button className="btn-ghost text-xs" disabled={busy !== null}
                    onClick={() => { removeScene(d.b.index); dismiss(sig) }}>
                    保留场景 {d.a.index + 1}，删除场景 {d.b.index + 1}
                  </button>
                  <button className="btn-ghost text-xs" disabled={busy !== null}
                    onClick={() => { removeScene(d.a.index); dismiss(sig) }}>
                    保留场景 {d.b.index + 1}，删除场景 {d.a.index + 1}
                  </button>
                </>
              ) : (
                <button className="btn-ghost text-xs" disabled={busy !== null}
                  onClick={() => dismiss(sig)}>
                  保留新版（重复可接受）
                </button>
              )}
              <button className="btn-ghost text-xs" disabled={busy !== null}
                onClick={() => onEditScene?.(d.b.index)}>
                ✎ 手动编辑新稿
              </button>
              <button className="btn-ghost text-xs" disabled={busy !== null}
                onClick={() => aiRewrite((pending?.scenes ?? [])[d.b.index]?.id, '与已有情节重复，请换一个推进方式表达同一节拍，禁止复用相同对话与桥段')}>
                {busy === (pending?.scenes ?? [])[d.b.index]?.id ? '重写中…' : '✨ AI 重写此场景'}
              </button>
            </div>
          </div>
        )
      })}

      {missing.length > 0 && (
        <div className="rounded border border-border p-3 space-y-1">
          <p className="text-xs font-medium text-amber-700 dark:text-amber-300">规划了但未写的节拍（{missing.length}）</p>
          <ul className="text-xs text-muted space-y-0.5 list-disc pl-4">
            {missing.map((b, i) => <li key={i}>{b}</li>)}
          </ul>
          <p className="text-xs text-muted">可用上方「✎ 修改正文」补写，或放弃后带着该节拍重新生成。</p>
        </div>
      )}
    </div>
  )
}
