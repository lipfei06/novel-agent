import { useState } from 'react'
import SceneEditor from './SceneEditor.jsx'
import StageView from './StageView.jsx'

// 设定阶段（线性推进）；stage4b/5/6 为章节循环，stage8/9 为收尾
const SETUP_STAGES = ['stage0', 'stage1', 'stage2', 'stage3', 'stage4a']
const SETUP_LABELS = { stage0: '选题', stage1: '世界观', stage2: '人物', stage3: '总纲', stage4a: '卷纲' }
const CHAPTER_STAGES = ['stage4b', 'stage5', 'stage6']

// 确认点渲染：stage5 用场景编辑器；其余用人类友好的 StageView
// 保留「编辑 JSON」作为高级修改入口；支持「重新生成」与「自动继续」
export default function ConfirmView({ view, onSubmit, busy, auto, onAutoChange }) {
  const [jsonMode, setJsonMode] = useState(false)
  const [jsonText, setJsonText] = useState('')

  if (!view || view.done) return null

  const isChapter = view.stage === 'stage5'
  const pretty = JSON.stringify(view.payload, null, 2)

  const accept = () => onSubmit({ action: 'accept' })
  const regenerate = () => onSubmit({ action: 'regenerate' })
  const editJson = () => {
    try {
      onSubmit({ action: 'edit', data: JSON.parse(jsonText ?? pretty) })
    } catch {
      alert('JSON 格式错误')
    }
  }

  const setupIdx = SETUP_STAGES.indexOf(view.stage)
  const isChapterLoop = CHAPTER_STAGES.includes(view.stage)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="rounded bg-primary/10 text-primary px-2 py-0.5 text-xs font-medium">
            {view.stage_label || view.stage}
          </span>
          {/* 设定阶段：步骤条 */}
          {setupIdx >= 0 && (
            <span className="flex items-center gap-1.5 text-xs text-muted">
              {SETUP_STAGES.map((s, i) => (
                <span key={s} className="flex items-center gap-1.5">
                  {i > 0 && <span className="opacity-50">→</span>}
                  <span
                    className={
                      i < setupIdx
                        ? 'text-green-600 dark:text-green-400'
                        : i === setupIdx
                          ? 'font-semibold text-foreground'
                          : 'opacity-50'
                    }
                  >
                    {i < setupIdx ? '✓' : ''}
                    {SETUP_LABELS[s]}
                  </span>
                </span>
              ))}
              <span className="ml-1 opacity-70">（{setupIdx + 1}/5）</span>
            </span>
          )}
          {/* 章节循环：卷章进度 */}
          {isChapterLoop && view.current_volume != null && view.current_chapter != null && (
            <span className="text-xs text-muted">
              第 {view.current_volume} 卷 · 第 {view.current_chapter} 章（逐章确认）
            </span>
          )}
          {view.stage === 'stage8' && <span className="text-xs text-muted">全书成稿 · 最终审校</span>}
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-xs text-muted cursor-pointer select-none">
            <input
              type="checkbox"
              checked={!!auto}
              onChange={(e) => onAutoChange?.(e.target.checked)}
              className="accent-current"
            />
            设定环节自动继续
          </label>
          <button className="btn-ghost text-xs" onClick={() => setJsonMode(!jsonMode)}>
            {jsonMode ? '返回友好视图' : '编辑 JSON'}
          </button>
        </div>
      </div>

      {isChapter ? (
        <>
          {view.payload?.quality && (
            <div className="card p-3 mb-3 text-xs space-y-1">
              {view.payload.quality.duplicates?.length ? (
                <p className="text-amber-700 dark:text-amber-300">
                  ⚠️ 机器质检：{view.payload.quality.duplicates.length} 处疑似重复场景（相似度{' '}
                  {Math.max(...view.payload.quality.duplicates.map((d) => d.ratio))}），建议在下方编辑中处理
                </p>
              ) : (
                <p className="text-green-600 dark:text-green-400">✅ 机器质检通过（{view.payload.quality.words?.actual ?? 0} 字）</p>
              )}
              {view.payload.quality.missing_beats?.length > 0 && (
                <p className="text-amber-700 dark:text-amber-300">
                  ⚠️ 规划了但未写的节拍：{view.payload.quality.missing_beats.join('；')}
                </p>
              )}
            </div>
          )}
          <SceneEditor chapter={view.payload} onEdit={(data) => onSubmit({ action: 'edit', data })} />
        </>
      ) : jsonMode ? (
        <div className="card p-4">
          <textarea
            className="input font-mono text-xs h-64"
            defaultValue={pretty}
            onChange={(e) => setJsonText(e.target.value)}
          />
          <div className="flex justify-end mt-3">
            <button className="btn-ghost" disabled={busy} onClick={editJson}>
              提交编辑
            </button>
          </div>
        </div>
      ) : (
        <StageView stage={view.stage} payload={view.payload} onSubmit={onSubmit} busy={busy} />
      )}

      <div className="flex items-center gap-2">
        <button className="btn-primary" disabled={busy} onClick={accept}>
          {busy ? '处理中…' : '接受'}
        </button>
        <button className="btn-ghost" disabled={busy} onClick={regenerate} title="对当前产出不满意时，让 AI 重新生成一版">
          🔄 重新生成
        </button>
        {!isChapter && !auto && (
          <span className="text-xs text-muted">确认无误后点「接受」，进入下一环节</span>
        )}
        {auto && setupIdx >= 0 && (
          <span className="text-xs text-muted">已开启自动继续：设定环节将依次自动接受，进入章节写作时暂停</span>
        )}
      </div>
    </div>
  )
}
