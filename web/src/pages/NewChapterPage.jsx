import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import { runTaskWithProgress } from '../lib/taskStream.js'
import ChatPanel from '../components/ChatPanel.jsx'
import ConfirmView from '../components/ConfirmView.jsx'

// 新建章节独立页面：与 AI 讨论设计 → 按讨论生成（SSE 流式进度）→ 预览 → 接受/放弃
export default function NewChapterPage({ projectId, vol, onBack }) {
  const [volume, setVolume] = useState(null)
  const [chapterNo, setChapterNo] = useState(1)
  const [form, setForm] = useState({ title: '', goal: '', conflicts: '', hook: '', notes: '' })
  const [generating, setGenerating] = useState(false)
  const [progress, setProgress] = useState(null) // {message, pct}
  const [pending, setPending] = useState(null) // 预览章节
  const [packet, setPacket] = useState(null) // AI 的章节规划
  const [context, setContext] = useState('') // 写作用的完整提示上下文
  const [showPrompt, setShowPrompt] = useState(false)
  const [quickNote, setQuickNote] = useState('') // 主按钮旁的快速生成指令（可选）
  const [agentic, setAgentic] = useState(false) // 智能研究模式：写手自主查询状态/伏笔
  const [pipelinePending, setPipelinePending] = useState(null) // 流水线中本卷的章节级待确认项
  const [error, setError] = useState(null)
  const set = (k, v) => setForm({ ...form, [k]: v })

  const load = () => {
    api.listVolumes(projectId).then((d) => {
      const v = d.volumes.find((x) => x.volume === vol)
      setVolume(v ?? null)
    }).catch(() => {})
    api.products(projectId).then((d) => {
      const count = d.chapters ? Object.keys(d.chapters).filter((k) => k.startsWith(`${vol}_`)).length : 0
      setChapterNo(count + 1)
    }).catch(() => {})
    // 流水线若有本卷的章节级待确认项（4b 规划/5 正文预览/6 审查），在本页顶部承接处理
    api.projectState(projectId).then((d) => {
      if (!d.done && ['stage4r', 'stage4b', 'stage5', 'stage6'].includes(d.stage) && d.current_volume === vol) {
        setPipelinePending(d)
      } else {
        setPipelinePending(null)
      }
    }).catch(() => {})
  }

  useEffect(() => {
    load()
  }, [projectId, vol])

  const chatContext = `chapter_${vol}_${chapterNo}`

  const generate = async (useForm) => {
    setGenerating(true)
    setError(null)
    setProgress({ message: '提交生成任务…', pct: 2 })
    try {
      const { task_id } = await api.startChapterGenerateTask(projectId, vol, chapterNo, {
        title: useForm ? form.title : '',
        goal: useForm ? form.goal : '',
        conflicts: useForm ? form.conflicts.split(/[,，\n]/).map((s) => s.trim()).filter(Boolean) : [],
        hook: useForm ? form.hook : '',
        auto_plan: true,
        notes: (useForm ? form.notes : quickNote).trim(),
        chat_context: chatContext,
        agentic,
      })
      const result = await runTaskWithProgress(task_id, (p) => setProgress(p))
      setPending(result.pending)
      setPacket(result.packet)
      setContext(result.context ?? '')
      setShowPrompt(false)
    } catch (e) {
      setError(e.message)
    } finally {
      setGenerating(false)
      setProgress(null)
    }
  }

  const submit = () => generate(true)

  const accept = async () => {
    setGenerating(true)
    setError(null)
    try {
      await api.acceptChapter(projectId, vol, pending.chapter)
      onBack() // 接受后返回卷列表
    } catch (e) {
      setError(e.message)
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-8 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <button className="btn-ghost text-xs mb-2" onClick={onBack}>← 返回卷列表</button>
          <h2 className="text-xl font-semibold">新建章节 · 卷{vol} {volume?.title ?? ''}</h2>
          <p className="text-sm text-muted mt-1">第 {chapterNo} 章</p>
        </div>
        {!pending && (
          <div className="flex items-center gap-3 flex-wrap">
            <label
              className="flex items-center gap-1.5 text-xs text-muted cursor-pointer select-none whitespace-nowrap"
              title="写手写作前自主查询状态卡/伏笔账本/前文片段，成本略增"
            >
              <input type="checkbox" checked={agentic} onChange={(e) => setAgentic(e.target.checked)} />
              智能研究
            </label>
            <input
              className="input text-sm w-64"
              placeholder="补充一句生成指令（可选，如：节奏加快）"
              value={quickNote}
              onChange={(e) => setQuickNote(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !generating && generate(false)}
            />
            <button
              className="btn-primary whitespace-nowrap"
              disabled={generating}
              onClick={() => generate(false)}
              title="AI 会总结下方聊天中的讨论要点，结合卷设定与记忆交给写手生成本章"
            >
              {generating ? '生成中…' : '✍️ 按讨论生成本章'}
            </button>
          </div>
        )}
      </div>

      {error && <div className="mb-4 rounded border border-red-200 bg-red-50 dark:bg-red-900/20 dark:text-red-300 text-red-700 px-4 py-3 text-sm">{error}</div>}

      {/* 流水线待确认项：本卷有未处理完的规划/正文/审查确认时，优先在此继续 */}
      {pipelinePending && !pending && (
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 rounded px-2 py-0.5">
              流水线待确认
            </span>
            <span className="text-xs text-muted">上一批生成流程停在此处，确认后才会继续</span>
          </div>
          <ConfirmView
            view={pipelinePending}
            onSubmit={(body) =>
              api.confirm(projectId, body.action, body.data).then((v) => {
                if (v.done || !['stage4r', 'stage4b', 'stage5', 'stage6'].includes(v.stage) || v.current_volume !== vol) {
                  setPipelinePending(null)
                  load()
                } else {
                  setPipelinePending(v)
                }
                return v
              })
            }
            busy={generating}
          />
        </div>
      )}

      {/* 流式生成进度 */}
      {generating && progress && (
        <div className="card p-4 mb-4">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium">{progress.message}</span>
            <span className="text-xs text-muted">{progress.pct ?? ''}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-black/5 overflow-hidden dark:bg-white/10">
            <div className="h-full bg-primary rounded-full transition-all duration-500" style={{ width: `${progress.pct ?? 5}%` }} />
          </div>
          <p className="text-xs text-muted mt-2">任务在后台执行，本页面可以最小化，回来即可看到结果。</p>
        </div>
      )}

      {pending ? (
        // 生成预览：先看 AI 的规划与提示，再看正文
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-medium">生成预览 · 第{pending.chapter}章 {pending.title}</h3>
            <span className="text-xs text-muted">{pending.scenes?.length ?? 0} 个场景</span>
          </div>

          {/* AI 的章节规划（写作用提示） */}
          {packet && (
            <div className="card p-5">
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm font-semibold text-primary">📋 AI 的章节规划（它被要求怎么写这章）</p>
                <button className="btn-ghost text-xs" onClick={() => setShowPrompt(!showPrompt)}>
                  {showPrompt ? '收起完整提示' : '查看完整提示'}
                </button>
              </div>
              <div className="text-sm space-y-2">
                {packet.goal && <p><span className="text-muted">本章目标：</span>{packet.goal}</p>}
                {packet.conflicts?.length > 0 && <p><span className="text-muted">冲突：</span>{packet.conflicts.join(' / ')}</p>}
                {packet.hook && <p><span className="text-muted">章节钩子：</span>{packet.hook}</p>}
                {packet.characters?.length > 0 && <p><span className="text-muted">出场人物：</span>{packet.characters.join('、')}</p>}
                {packet.pov && <p><span className="text-muted">视角：</span>{packet.pov}</p>}
                {packet.beats?.length > 0 && (
                  <div>
                    <span className="text-muted">情绪节拍：</span>
                    <ol className="pl-5 mt-1 space-y-1">
                      {packet.beats.map((b, i) => (
                        <li key={i} className="list-decimal">{b.desc || b.type}</li>
                      ))}
                    </ol>
                  </div>
                )}
                {packet.foreshadow?.length > 0 && (
                  <p><span className="text-muted">伏笔：</span>{packet.foreshadow.map((f) => f.desc || f.kind || '').filter(Boolean).join('；')}</p>
                )}
              </div>
              {showPrompt && context && (
                <div className="mt-3 pt-3 border-t border-border">
                  <p className="text-xs font-medium text-muted mb-2">完整写作提示（注入的上下文：前文/记忆/人物状态/RAG）</p>
                  <pre className="text-xs leading-5 whitespace-pre-wrap text-muted max-h-64 overflow-auto">{context}</pre>
                </div>
              )}
            </div>
          )}

          {/* 生成正文 */}
          {(pending.scenes ?? []).map((s, i) => (
            <div key={s.id ?? i} className="card p-4">
              <p className="text-xs font-medium text-primary mb-2">{s.heading}</p>
              <p className="text-sm leading-7 whitespace-pre-wrap">{s.text}</p>
            </div>
          ))}
          <div className="flex justify-end gap-2">
            <button className="btn-ghost" disabled={generating} onClick={() => setPending(null)}>放弃</button>
            <button className="btn-primary" disabled={generating} onClick={accept}>
              {generating ? '保存中…' : '接受并保存'}
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* 与 AI 讨论本章设计：聊天即大纲 */}
          <ChatPanel
            projectId={projectId}
            context={chatContext}
            title={`章节助手 · 讨论第${chapterNo}章怎么写`}
            target="chapter"
            placeholder="自由聊这一章的想法/情节/对白/节奏……想好后点右上「按讨论生成本章」，AI 会自己提炼要点交给写手"
          />
          <p className="text-xs text-muted -mt-2">
            💡 想法聊清楚了就点右上「<span className="font-medium">按讨论生成本章</span>」——AI 会总结讨论要点，
            结合卷设定、前文记忆与人物状态交给写手，无需填任何表单。
          </p>

          {/* 高级选项（可选）：想手动指定时再展开 */}
          <details className="card p-5">
            <summary className="text-sm font-medium cursor-pointer select-none">
              高级选项（可选）：手动指定标题 / 目标 / 冲突 / 钩子 / 写作指令
            </summary>
            <div className="mt-4">
              <label className="block text-xs text-muted mb-1">章节标题（可选）</label>
              <input className="input mb-3" value={form.title} onChange={(e) => set('title', e.target.value)} placeholder={`如：第${chapterNo}章 破晓`} />
              <label className="block text-xs text-muted mb-1">本章目标 / 内容要点（可选，留空则以聊天讨论为准）</label>
              <textarea className="input mb-3" rows={3} value={form.goal} onChange={(e) => set('goal', e.target.value)} placeholder="如：主角与沈知微第一次正面交锋" />
              <label className="block text-xs text-muted mb-1">冲突（可选）</label>
              <textarea className="input mb-3" rows={2} value={form.conflicts} onChange={(e) => set('conflicts', e.target.value)} placeholder="如：身份误会，利益冲突" />
              <label className="block text-xs text-muted mb-1">章节钩子（可选）</label>
              <input className="input mb-2" value={form.hook} onChange={(e) => set('hook', e.target.value)} placeholder="如：门被敲响时，她看到了那张照片" />
              <label className="block text-xs text-muted mb-1">自定义写作指令（可选，灵活指导 AI 怎么写这章）</label>
              <textarea className="input mb-3" rows={2} value={form.notes} onChange={(e) => set('notes', e.target.value)} placeholder="如：多用环境渲染营造压抑感；对话要克制；结尾留白" />
              <div className="flex justify-end">
                <button className="btn-primary text-sm" disabled={generating} onClick={submit}>
                  {generating ? '生成中…' : '按以上信息生成'}
                </button>
              </div>
            </div>
          </details>
        </div>
      )}
    </div>
  )
}
