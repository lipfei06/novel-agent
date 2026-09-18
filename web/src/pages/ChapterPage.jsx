import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import { runTaskWithProgress } from '../lib/taskStream.js'
import ChatPanel from '../components/ChatPanel.jsx'

// 右栏上部的品牌装饰：羽毛笔 + 摊开的书 + 墨线（纯 SVG，跟随明暗主题）
function AssistantBrand() {
  return (
    <div className="flex flex-col items-center justify-center py-8 select-none pointer-events-none text-primary">
      <svg width="150" height="120" viewBox="0 0 200 160" fill="none" className="opacity-70">
        {/* 羽毛笔：笔身 + 羽片 */}
        <path
          d="M152 22 C118 46 92 78 74 114 C71 108 70 101 72 94 C88 62 116 38 152 22 Z"
          fill="currentColor"
          opacity="0.45"
        />
        <path
          d="M152 22 C126 40 104 64 88 92 M132 34 C112 50 96 68 84 88"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          opacity="0.55"
        />
        {/* 笔杆与笔尖 */}
        <path
          d="M152 22 C120 48 94 80 76 114 L66 134 L74 112"
          stroke="currentColor"
          strokeWidth="2.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* 摊开的书 */}
        <path
          d="M28 108 C54 94 84 94 100 106 C116 94 146 94 172 108 L172 122 C146 108 116 108 100 120 C84 108 54 108 28 122 Z"
          fill="currentColor"
          opacity="0.28"
        />
        <path d="M100 106 L100 120" stroke="currentColor" strokeWidth="2" opacity="0.5" />
        {/* 墨迹线条 */}
        <path
          d="M42 142 C72 136 128 136 158 142"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          opacity="0.3"
        />
        <path
          d="M58 150 C82 146 118 146 142 150"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          opacity="0.18"
        />
      </svg>
      <p className="text-sm font-medium text-muted mt-3">novel-agent · 章节助手</p>
      <p className="text-xs text-muted opacity-70 mt-1">和 AI 聊聊这一章，把灵感聊成正文</p>
    </div>
  )
}

// 章节独立页面：左侧正文内容 + 右侧章节助手面板（并排布局）
export default function ChapterPage({ projectId, vol, ch, onBack }) {
  const [chapter, setChapter] = useState(null)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [regenerating, setRegenerating] = useState(false)
  const [regenProgress, setRegenProgress] = useState(null)
  const [preview, setPreview] = useState(null)

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
        await api.updateChapter(projectId, vol, ch, preview.data)
      } else {
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
    if (instruction === null) return
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
      onBack()
    } catch (e) {
      setError(e.message)
      setSaving(false)
    }
  }

  if (error && !chapter) return <div className="p-8 text-sm text-red-600">{error}</div>
  if (!chapter) return <div className="p-8 text-sm text-muted">章节不存在或尚未保存。</div>

  const scenes = editing && draft ? draft.scenes : chapter.scenes

  return (
    <div className="px-6 py-6">
      {/* 页头 */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <button className="btn-ghost text-xs mb-1" onClick={onBack}>← 返回卷列表</button>
          <h2 className="text-lg font-semibold">第{ch}章 · {chapter.title}</h2>
          <p className="text-xs text-muted mt-0.5">卷{vol} · {scenes?.length ?? 0} 个场景</p>
        </div>
        <div className="flex gap-2">
          <button
            className="btn-ghost text-red-600 dark:text-red-400 text-xs"
            disabled={saving || regenerating}
            onClick={deleteChapter}
            title="删除本章（仅允许删除最新一章）"
          >
            🗑 删除
          </button>
          <button
            className="btn-ghost text-xs"
            disabled={regenerating}
            onClick={regenerate}
            title="按右侧聊天框中的讨论重写本章；直接点也可，AI 会保持设定与情节骨架"
          >
            {regenerating ? `${regenProgress?.message ?? '重写中…'}` : '🔄 按讨论重写'}
          </button>
          {!editing ? (
            <button className="btn-primary text-sm" onClick={startEdit}>修改 ✎</button>
          ) : (
            <>
              <button className="btn-ghost text-sm" onClick={() => setEditing(false)}>取消</button>
              <button className="btn-primary text-sm" disabled={saving} onClick={save}>
                {saving ? '保存中…' : '保存修改'}
              </button>
            </>
          )}
        </div>
      </div>

      {error && <div className="mb-4 rounded border border-red-200 bg-red-50 dark:bg-red-900/20 dark:text-red-300 text-red-700 px-4 py-3 text-sm">{error}</div>}

      {/* 流式重写进度 */}
      {regenProgress && (
        <div className="card p-3 mb-4">
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-xs font-medium">{regenProgress.message}</span>
            <span className="text-xs text-muted">{regenProgress.pct ?? ''}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-black/5 overflow-hidden dark:bg-white/10">
            <div className="h-full bg-primary rounded-full transition-all duration-500" style={{ width: `${regenProgress.pct ?? 5}%` }} />
          </div>
        </div>
      )}

      {/* 主体：左右分栏（正文 | 章节助手） */}
      <div className="flex gap-5 items-stretch">
        {/* 左：正文内容 */}
        <div className="flex-1 min-w-0 space-y-4">
          {(scenes ?? []).map((s, i) =>
            editing ? (
              <div key={s.id ?? i} className="card p-4 space-y-2.5">
                <input className="input font-medium text-sm" value={s.heading ?? ''} placeholder="场景标题" onChange={(e) => setScene(i, 'heading', e.target.value)} />
                <textarea className="input leading-7 min-h-[140px] text-sm" value={s.text ?? ''} onChange={(e) => setScene(i, 'text', e.target.value)} />
              </div>
            ) : (
              <div key={s.id ?? i} className="card p-4">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-semibold text-primary">{s.heading}</p>
                  <button className="btn-ghost text-xs" disabled={saving} onClick={() => rewriteScene(s)}>
                    AI 改写
                  </button>
                </div>
                <p className="text-sm leading-7 whitespace-pre-wrap">{s.text}</p>
              </div>
            ),
          )}
        </div>

        {/* 右：品牌装饰在上，章节助手面板贴底对齐（整列粘性，滚动时始终可见） */}
        <div className="w-[45%] max-w-[620px] min-w-[380px] flex-shrink-0 sticky top-6 self-stretch max-h-[calc(100vh-8.5rem)] flex flex-col">
          <div className="flex-1 min-h-0 flex items-center justify-center">
            <AssistantBrand />
          </div>
          <ChatPanel
            projectId={projectId}
            context={`chapter_${vol}_${ch}`}
            title="章节助手"
            target="chapter"
            placeholder="和 AI 讨论本章情节、对白或改写思路…提出方案可直接预览覆盖，或点上方「重新生成」按讨论重写"
            onApply={async (p) => {
              if (p && p.scenes) {
                setPreview({ data: p, source: 'proposal' })
              }
            }}
          />
        </div>
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
