import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

const REASON_STYLE = {
  编辑覆盖: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  重写覆盖: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
  删除备份: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  恢复前备份: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
}

const fmtKey = (key) => {
  const [v, c] = String(key).split('_').map(Number)
  return `卷${v}第${c}章`
}

const fmtWords = (n) => (n >= 10000 ? `${(n / 10000).toFixed(1)} 万字` : `${n} 字`)

// 版本历史对话框：ch 为空时展示整卷备份组（含已删除章节），否则只看该章
export default function VersionHistoryDialog({ projectId, vol, ch = null, onClose, onRestored }) {
  const [groups, setGroups] = useState(null) // ch=null 时的卷级分组
  const [versions, setVersions] = useState(null) // 指定章的版本列表
  const [activeKey, setActiveKey] = useState(null) // 卷级模式下展开的章节键
  const [expanded, setExpanded] = useState(null) // 展开预览的版本 id
  const [preview, setPreview] = useState(null) // 展开版本的完整内容
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  // 章节模式固定 vol/ch；卷级模式按展开分组的键定位
  const vcOf = (key) => {
    const [v, c] = String(key ?? `${vol}_${ch}`).split('_').map(Number)
    return [v, c]
  }

  const loadVersions = (key) => {
    const [v, c] = vcOf(key)
    setVersions(null)
    api.chapterVersions(projectId, v, c).then((d) => setVersions(d.versions)).catch((e) => setError(e.message))
  }

  useEffect(() => {
    setError(null)
    if (ch) {
      loadVersions(`${vol}_${ch}`)
    } else {
      api.volumeVersions(projectId, vol).then((d) => setGroups(d.groups)).catch((e) => setError(e.message))
    }
  }, [projectId, vol, ch])

  const togglePreview = async (key, vid) => {
    if (expanded === vid) {
      setExpanded(null)
      setPreview(null)
      return
    }
    setExpanded(vid)
    setPreview(null)
    try {
      const [v, c] = vcOf(key)
      const d = await api.chapterVersion(projectId, v, c, vid)
      setPreview(d.version)
    } catch (e) {
      setError(e.message)
    }
  }

  const restore = async (key, vid) => {
    if (!confirm('恢复到这个版本？当前稿会自动留底，可再次恢复。')) return
    setBusy(true)
    setError(null)
    try {
      const [v, c] = vcOf(key)
      await api.restoreChapterVersion(projectId, v, c, vid)
      onRestored?.()
      onClose()
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  const rows = (key, list) =>
    list.map((v) => (
      <div key={v.id} className="rounded border border-border p-3">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2 min-w-0">
            <span className={`text-xs rounded px-1.5 py-0.5 whitespace-nowrap ${REASON_STYLE[v.reason] ?? 'bg-black/5 text-muted dark:bg-white/10'}`}>
              {v.reason ?? '备份'}
            </span>
            <span className="text-xs text-muted whitespace-nowrap">{v.saved_at}</span>
            <span className="text-sm truncate">{v.title}</span>
          </div>
          <div className="flex items-center gap-2 whitespace-nowrap">
            <span className="text-xs text-muted">{fmtWords(v.words ?? 0)}</span>
            <button className="btn-ghost text-xs" onClick={() => togglePreview(key, v.id)}>
              {expanded === v.id ? '收起' : '查看'}
            </button>
            <button className="btn-primary text-xs" disabled={busy} onClick={() => restore(key, v.id)}>
              {busy ? '恢复中…' : '恢复此版'}
            </button>
          </div>
        </div>
        {expanded === v.id && (
          <div className="mt-2 pt-2 border-t border-border max-h-64 overflow-auto">
            {preview === null ? (
              <p className="text-xs text-muted">加载中…</p>
            ) : (
              (preview.chapter?.scenes ?? []).map((s, i) => (
                <div key={i} className="mb-2">
                  <p className="text-xs font-medium text-primary">{s.heading}</p>
                  <p className="text-xs leading-5 whitespace-pre-wrap text-muted">{s.text}</p>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    ))

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="card w-[680px] max-h-[85vh] overflow-auto p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-base font-medium">
            🕘 {ch ? `第${ch}章历史版本` : `卷${vol}备份`}
          </h3>
          <button className="btn-ghost text-xs" onClick={onClose}>关闭</button>
        </div>
        <p className="text-xs text-muted mb-3">
          编辑、重写、删除都会自动留底（每章最多保留 20 份）。恢复后 AI 记忆会按恢复稿重放。
        </p>
        {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
        {ch ? (
          versions === null ? (
            <p className="text-sm text-muted">加载中…</p>
          ) : versions.length === 0 ? (
            <p className="text-sm text-muted">这一章还没有历史备份。修改或重写后会自动留底。</p>
          ) : (
            <div className="space-y-2">{rows(`${vol}_${ch}`, versions)}</div>
          )
        ) : groups === null ? (
          <p className="text-sm text-muted">加载中…</p>
        ) : groups.length === 0 ? (
          <p className="text-sm text-muted">本卷还没有备份。编辑、重写或删除章节后会自动留底。</p>
        ) : (
          <div className="space-y-2">
            {groups.map((g) => (
              <div key={g.key} className="rounded border border-border p-3">
                <button
                  className="w-full flex items-center justify-between text-left"
                  onClick={() => {
                    setActiveKey(activeKey === g.key ? null : g.key)
                    if (activeKey !== g.key) loadVersions(g.key)
                  }}
                >
                  <div className="min-w-0">
                    <span className="text-sm font-medium">
                      {fmtKey(g.key)} · {g.title || '（无标题）'}
                    </span>
                    {g.deleted && (
                      <span className="text-xs text-red-600 dark:text-red-400 ml-2 rounded px-1.5 py-0.5 bg-red-50 dark:bg-red-900/20">
                        已删除
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-muted whitespace-nowrap">
                    {g.count} 份 · 最近 {g.latest_saved_at}
                  </span>
                </button>
                {activeKey === g.key && (
                  <div className="mt-2 pt-2 border-t border-border space-y-2">
                    {versions === null ? <p className="text-xs text-muted">加载中…</p> : rows(g.key, versions)}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
