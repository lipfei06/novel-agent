import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

// 写作手法面板：从写作手法库挂载/卸载手法；机制型"暗线"附叙事蓝图管理
export default function TechniquePanel({ projectId, attached, blueprint, onChanged }) {
  const [lib, setLib] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [genBusy, setGenBusy] = useState(false)
  const attachedIds = new Set((attached ?? []).map((t) => t.id))
  const hasDarkLine = attachedIds.has('tech_dark_line')

  useEffect(() => {
    api.libraryList('technique').then((d) => setLib(d.entries)).catch((e) => setError(e.message))
  }, [])

  const setIds = async (ids) => {
    setBusy(true)
    setError(null)
    try {
      await api.setProjectTechniques(projectId, ids)
      onChanged?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }
  const attach = (id) => setIds([...attachedIds, id])
  const detach = (id) => setIds([...attachedIds].filter((x) => x !== id))

  const genBlueprint = async () => {
    setGenBusy(true)
    setError(null)
    try {
      await api.generateBlueprint(projectId)
      onChanged?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setGenBusy(false)
    }
  }
  const removeThread = async (tid) => {
    if (!confirm('删除这条暗线？蓝图中的真相与揭示计划将一并移除。')) return
    setBusy(true)
    setError(null)
    try {
      const bp = { ...(blueprint ?? {}), dark_threads: (blueprint?.dark_threads ?? []).filter((t) => t.id !== tid) }
      await api.productsUpdate(projectId, 'narrative_blueprint', bp)
      onChanged?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      {error && <div className="rounded border border-red-200 bg-red-50 dark:bg-red-900/20 dark:text-red-300 text-red-700 px-3 py-2 text-xs">{error}</div>}

      {/* 机制型"暗线"：叙事蓝图 */}
      {hasDarkLine && (
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-semibold text-primary">🌙 叙事蓝图（暗线 · 作者视角）</p>
            <button className="btn-ghost text-xs" disabled={genBusy || busy} onClick={genBlueprint}>
              {genBusy ? '生成中…' : blueprint ? '🔄 重新生成蓝图' : '✨ 生成叙事蓝图'}
            </button>
          </div>
          {blueprint ? (
            <div className="space-y-2 text-sm">
              {blueprint.theme && (
                <p>
                  <span className="text-muted text-xs">主题：</span>
                  {blueprint.theme}
                </p>
              )}
              {(blueprint.motifs ?? []).length > 0 && (
                <p>
                  <span className="text-muted text-xs">象征意象：</span>
                  {blueprint.motifs.join('、')}
                </p>
              )}
              {(blueprint.dark_threads ?? []).map((t) => (
                <div key={t.id} className="rounded border border-border p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium">《{t.name}》</span>
                    <button className="btn-ghost text-xs text-red-600 dark:text-red-400" disabled={busy} onClick={() => removeThread(t.id)}>
                      删除
                    </button>
                  </div>
                  <p className="text-xs leading-5">
                    <span className="text-muted">真相（仅作者知）：</span>
                    {t.truth}
                  </p>
                  <p className="text-xs leading-5">
                    <span className="text-muted">表象：</span>
                    {t.surface}
                  </p>
                  <p className="text-xs leading-5">
                    <span className="text-muted">揭示计划：</span>
                    {t.reveal_plan}
                  </p>
                  {(t.related ?? []).length > 0 && (
                    <p className="text-xs text-muted mt-1">关联人物：{t.related.join('、')}</p>
                  )}
                </div>
              ))}
              <p className="text-xs text-muted">生成的暗线会自动注入后续章节的规划与写作（暗示任务 + 揭示纪律），一致性检查会盯住"是否提前点破"。</p>
            </div>
          ) : (
            <p className="text-xs text-muted">点击"生成叙事蓝图"，AI 将基于立项书/总纲/已写章节设计主题、意象与 1-3 条暗线（真相 + 表象 + 揭示计划），生成后可逐条修改或删除。</p>
          )}
        </div>
      )}

      {/* 已挂载 */}
      <div>
        <p className="text-xs text-muted mb-2">已挂载手法（挂载后按阶段自动注入规划/写作/检查）</p>
        {(attached ?? []).length === 0 ? (
          <p className="text-sm text-muted">尚未挂载任何手法，从下方列表添加。</p>
        ) : (
          <div className="space-y-2">
            {attached.map((t) => (
              <div key={t.id} className="rounded border border-border p-3 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium">
                    {t.name}
                    <span className={`ml-2 text-[10px] rounded px-1.5 py-0.5 align-middle ${t.mode === 'mechanism' ? 'bg-primary/15 text-primary' : 'bg-black/5 text-muted dark:bg-white/10'}`}>
                      {t.mode === 'mechanism' ? '机制型' : '知识型'}
                    </span>
                  </p>
                  {t.guidance && <p className="text-xs text-muted mt-1 line-clamp-2">{t.guidance}</p>}
                </div>
                <button className="btn-ghost text-xs whitespace-nowrap" disabled={busy} onClick={() => detach(t.id)}>
                  卸载
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 手法库 */}
      <div>
        <p className="text-xs text-muted mb-2">写作手法库（跨项目共享，可自行扩充条目）</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {lib
            .filter((t) => !attachedIds.has(t.id))
            .map((t) => (
              <div key={t.id} className="rounded border border-border p-3 flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">
                    {t.name}
                    <span className={`ml-2 text-[10px] rounded px-1.5 py-0.5 align-middle ${t.mode === 'mechanism' ? 'bg-primary/15 text-primary' : 'bg-black/5 text-muted dark:bg-white/10'}`}>
                      {t.mode === 'mechanism' ? '机制型' : '知识型'}
                    </span>
                  </p>
                  <p className="text-xs text-muted mt-1 line-clamp-2">{t.description}</p>
                </div>
                <button className="btn-ghost text-xs whitespace-nowrap" disabled={busy} onClick={() => attach(t.id)}>
                  挂载
                </button>
              </div>
            ))}
          {lib.filter((t) => !attachedIds.has(t.id)).length === 0 && (
            <p className="text-xs text-muted">库中手法已全部挂载。</p>
          )}
        </div>
      </div>
    </div>
  )
}
