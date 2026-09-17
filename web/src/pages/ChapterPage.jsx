import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import { runTaskWithProgress } from '../lib/taskStream.js'
import ChatPanel from '../components/ChatPanel.jsx'

// 章节独立页面：整页查看 + 修改 + 按讨论重新生成（SSE 流式进度）+ AI 改写场景
export default function ChapterPage({ projectId, vol, ch, onBack }) {
  const [chapter, setChapter] = useState(null)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [regenerating, setRegenerating] = useState(false)
  const [regenProgress, setRegenProgress] = useState(null)
  const [preview, setPreview] = useState(null) // 重新生成/方案应用 预览

  const load = () =>
    api
      .products(projectId)
      .then((d) => {
        const c = d.chapters?.[`${vol}_${ch}`]
        setChapter(c ?? null)
      })
      .catch((e) => setError(e.message))

  useEffect(() => {
    load()
  }, [projectId, vol, ch])

  const startEdit = () => {
    setDraft(JSON.parse(JSON.stringify(chapter ?? {})))
    setEditing(true)
  }
  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      await api.updateChapter(projectId, vol, ch, draft)
      await load()
      setEditing(false)
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }
  const setScene = (i, k, v) =>
    setDraft({ ...draft, scenes: draft.scenes.map((s, idx) => (idx === i ? { ...s, [k]: v } : s)) })

  const regenerate = async () => {
    // 直接按聊天讨论重写本章：聊天框里说怎么改 → 点重新生成即可（SSE 流式进度）
    setRegenerating(true)
    setError(null)
    setRegenProgress({ message: '提交生成任务…', pct: 2 })
    try {
      const { task_id } = await api.startRegenerateTask(projectId, vol, ch, '', `chapter_${vol}_${ch}`)
      const result = await runTaskWithProgress(task_id, (p) => setRegenProgress(p))
      setPreview({ data: result.pending, source: 'regenerate' })
    } catch (e) {
      setError(e.message)
    } finally {
      setRegenerating(false)
      setRegenProgress(null)
    }
  }
  const acceptPreview = async () => {
    setSaving(true)
    setError(null)
    try {
      if (preview.source === 'proposal') {
        // 聊天"提出方案"产出的完整章节：确认后覆盖当前章节
        await api.updateChapter(projectId, vol, ch, preview.data)
      } else {
        // "重新生成"产物：后端已存 pending，走接受端点
        await api.acceptChapter(projectId, vol, ch)
      }
      setPreview(null)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }
  const rewriteScene = async (scene) => {
    const instruction = window.prompt('改写这个场景：可输入简短提示（如"对话更多些/氛围更压抑"），留空直接确定则由 AI 自由重写', '')
    if (instruction === null) return // 点取消才中止，留空 = 自由重写
    setSaving(true)
    setError(null)
    try {
      await api.rewriteScene(projectId, vol, ch, scene.id, instruction.trim())
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }
  const deleteChapter = async () => {
    if (!confirm(`确定删除第${ch}章《${chapter.title}》？正文与章节摘要会一并移除，且无法恢复。`)) return
    setSaving(true)
    setError(null)
    try {
      await api.deleteSavedChapter(projectId, vol, ch)
      onBack() // 删除后返回卷列表
    } catch (e) {
      setError(e.message)
      setSaving(false)
    }
  }

  if (error && !chapter) return <div className="p-8 text-sm text-red-600">{error}</div>
  if (!chapter) return <div className="p-8 text-sm text-muted">章节不存在或尚未保存。</div>

  const scenes = editing && draft ? draft.scenes : chapter.scenes

  return (
    <div className="max-w-5xl mx-auto px-8 py-8">
      {/* 页头 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <button className="btn-ghost text-xs mb-2" onClick={onBack}>← 返回卷列表</button>
          <h2 className="text-xl font-semibold">第{ch}章 · {chapter.title}</h2>
          <p className="text-sm text-muted mt-1">卷{vol} · {scenes?.length ?? 0} 个场景</p>
        </div>
        <div className="flex gap-2">
          <button
            className="btn-ghost text-red-600 dark:text-red-400"
            disabled={saving || regenerating}
            onClick={deleteChapter}
            title="删除本章（仅允许删除最新一章）"
          >
            🗑 删除本章
          </button>
          <button
            className="btn-ghost"
            disabled={regenerating}
            onClick={regenerate}
            title="按下方聊天框中的讨论重写本章；直接点也可，AI 会保持设定与情节骨架"
          >
            {regenerating ? `${regenProgress?.message ?? '重新生成中…'}` : '🔄 按讨论重新生成'}
          </button>
          {!editing ? (
            <button className="btn-primary" onClick={startEdit}>修改 ✎</button>
          ) : (
            <>
              <button className="btn-ghost" onClick={() => setEditing(false)}>取消</button>
              <button className="btn-primary" disabled={saving} onClick={save}>
                {saving ? '保存中…' : '保存修改'}
              </button>
            </>
          )}
        </div>
      </div>

      {error && <div className="mb-4 rounded border border-red-200 bg-red-50 dark:bg-red-900/20 dark:text-red-300 text-red-700 px-4 py-3 text-sm">{error}</div>}

      {/* 流式重写进度 */}
      {regenProgress && (
        <div className="card p-4 mb-4">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium">{regenProgress.message}</span>
            <span className="text-xs text-muted">{regenProgress.pct ?? ''}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-black/5 overflow-hidden dark:bg-white/10">
            <div className="h-full bg-primary rounded-full transition-all duration-500" style={{ width: `${regenProgress.pct ?? 5}%` }} />
          </div>
        </div>
      )}

      {/* 场景列表 */}
      <div className="space-y-4">
        {(scenes ?? []).map((s, i) =>
          editing ? (
            <div key={s.id ?? i} className="card p-5 space-y-3">
              <input className="input font-medium" value={s.heading ?? ''} placeholder="场景标题" onChange={(e) => setScene(i, 'heading', e.target.value)} />
              <textarea className="input leading-7 min-h-[160px]" value={s.text ?? ''} onChange={(e) => setScene(i, 'text', e.target.value)} />
            </div>
          ) : (
            <div key={s.id ?? i} className="card p-5">
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm font-semibold text-primary">{s.heading}</p>
                <button
                  className="btn-ghost text-xs"
                  disabled={saving}
                  title="AI 重写这个场景：可输入少量提示，留空则自由重写（其余场景不动）"
                  onClick={() => rewriteScene(s)}
                >
                  AI 改写
                </button>
              </div>
              <p className="text-[15px] leading-8 whitespace-pre-wrap">{s.text}</p>
            </div>
          ),
        )}
      </div>

      {/* 章节对话助手 */}
      <div className="mt-8">
        <ChatPanel
          projectId={projectId}
          context={`chapter_${vol}_${ch}`}
          title="章节助手 · 讨论这章怎么写/怎么改"
          target="chapter"
          placeholder="和 AI 讨论本章情节、对白或改写思路…提出方案可直接预览覆盖，或点右上「重新生成」按讨论重写"
          onApply={async (p) => {
            if (p && p.scenes) {
              // 方案不直接覆盖已完成的章节：先进预览，确认后替换
              setPreview({ data: p, source: 'proposal' })
            }
          }}
        />
      </div>

      {/* 重新生成 / 方案应用 预览 */}
      {preview && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="card w-[640px] max-h-[85vh] overflow-auto p-6">
            <h3 className="text-base font-medium mb-1">
              {preview.source === 'proposal' ? 'AI 方案预览' : '重新生成预览'} · 第{ch}章 {preview.data.title}
            </h3>
            <p className="text-xs text-muted mb-4">接受后用此版本覆盖当前章节，放弃则保留原稿。</p>
            {(preview.data.scenes ?? []).map((s, i) => (
              <div key={s.id ?? i} className="rounded border border-border p-3 mb-2">
                <p className="text-xs font-medium text-primary mb-1">{s.heading}</p>
                <p className="text-sm leading-6 whitespace-pre-wrap">{s.text}</p>
              </div>
            ))}
            <div className="flex justify-end gap-2 mt-4">
              <button className="btn-ghost" onClick={() => setPreview(null)}>放弃</button>
              <button className="btn-primary" disabled={saving} onClick={acceptPreview}>
                {saving ? '保存中…' : '接受覆盖'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
