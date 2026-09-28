import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import ChatPanel from './ChatPanel.jsx'
import VersionHistoryDialog from './VersionHistoryDialog.jsx'

// 卷/章管理：卷可新增/编辑；点「新建章节」跳转独立页面；点章节跳转查看/修改页
export default function VolumeManager({ projectId, products, onProductsChange, onOpenChapter, onNewChapter }) {
  const [volumes, setVolumes] = useState([])
  const [selected, setSelected] = useState(null) // 当前查看的卷号
  const [route, setRoute] = useState('list') // list | newVol | editVol
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [editingVol, setEditingVol] = useState(null)
  const [chatVol, setChatVol] = useState(null) // 正在对话的卷号
  const [backupVol, setBackupVol] = useState(null) // 展示备份对话框的卷号
  const [cost, setCost] = useState(null) // 按章成本流水（可选展示）

  const loadVolumes = () =>
    api.listVolumes(projectId).then((d) => setVolumes(d.volumes)).catch((e) => setError(e.message))

  useEffect(() => {
    loadVolumes()
    api.projectCost(projectId).then(setCost).catch(() => {})
  }, [projectId])

  const run = async (fn) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
      await loadVolumes()
      onProductsChange?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const chapterCount = (vol) =>
    products?.chapters ? Object.keys(products.chapters).filter((k) => k.startsWith(`${vol}_`)).length : 0

  // 章节详情/新建 → 独立页面（由上层路由）
  return (
    <div className="space-y-4">
      {error && <div className="rounded border border-red-200 bg-red-50 dark:bg-red-900/20 dark:text-red-300 text-red-700 px-4 py-3 text-sm">{error}</div>}

      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">分卷与章节</h3>
        <div className="flex gap-2">
          <button className="btn-ghost text-xs" onClick={() => setRoute('newVol')}>+ 手工新增卷</button>
          <button
            className="btn-ghost text-xs"
            disabled={busy}
            onClick={() =>
              run(async () => {
                const r = await api.createVolume(projectId, { generate: true })
                setVolumes(r.volumes)
              })
            }
          >
            {busy ? '生成中…' : '✨ AI 生成全部卷'}
          </button>
        </div>
      </div>

      {route === 'newVol' && (
        <NewVolumeForm
          projectId={projectId}
          currentVolumes={volumes}
          onCancel={() => setRoute('list')}
          onDone={() => {
            setRoute('list')
            onProductsChange?.()
          }}
          busy={busy}
          run={run}
          error={error}
        />
      )}

      {route === 'editVol' && (
        <VolumeEditForm
          projectId={projectId}
          volume={editingVol}
          onCancel={() => setRoute('list')}
          onDone={() => {
            setRoute('list')
            onProductsChange?.()
          }}
          busy={busy}
          run={run}
          error={error}
        />
      )}

      {volumes.length === 0 ? (
        <div className="card p-10 text-center text-muted text-sm">
          <p className="text-4xl mb-3">📖</p>
          还没有分卷。用「AI 生成全部卷」依据总纲自动规划，或「手工新增卷」。
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {volumes.map((v) => (
            <div key={v.volume} className="card p-5">
              <div className="flex items-start justify-between">
                <div>
                  <h4 className="font-medium">卷{v.volume} · {v.title}</h4>
                  <p className="text-xs text-muted mt-1">{(v.event_arc ?? []).join(' / ') || '—'}</p>
                </div>
                <span className="text-xs text-muted whitespace-nowrap">已写 {chapterCount(v.volume)} 章</span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  className="btn-primary text-xs"
                  onClick={() => onNewChapter?.({ projectId, vol: v.volume })}
                >
                  + 新建章节
                </button>
                <button
                  className="btn-ghost text-xs"
                  onClick={() => {
                    setSelected(v.volume)
                    setEditingVol(v)
                    setRoute('editVol')
                  }}
                >
                  编辑卷
                </button>
                <button className="btn-ghost text-xs" onClick={() => setChatVol(chatVol === v.volume ? null : v.volume)}>
                  {chatVol === v.volume ? '收起对话' : '💬 对话规划'}
                </button>
                <button
                  className="btn-ghost text-xs"
                  onClick={() => setBackupVol(backupVol === v.volume ? null : v.volume)}
                  title="编辑/重写/删除的自动留底，含已删除章节，可恢复"
                >
                  {backupVol === v.volume ? '收起备份' : '🕘 备份'}
                </button>
                <button
                  className="btn-ghost text-xs"
                  onClick={() => setSelected(selected === v.volume ? null : v.volume)}
                >
                  {selected === v.volume ? '收起章节' : '查看章节'}
                </button>
              </div>
              {backupVol === v.volume && (
                <VersionHistoryDialog
                  projectId={projectId}
                  vol={v.volume}
                  ch={null}
                  onClose={() => setBackupVol(null)}
                  onRestored={onProductsChange}
                />
              )}
              {chatVol === v.volume && (
                <div className="mt-3 pt-3 border-t border-border">
                  <ChatPanel
                    projectId={projectId}
                    context={`volume_${v.volume}`}
                    title={`卷${v.volume}助手 · 讨论本卷事件弧/伏笔/章数`}
                    target="volume_plan"
                    placeholder="给 AI 本卷的想法，一起讨论卷的规划…"
                    onApply={async (p) => {
                      let plan = Array.isArray(p.items) ? p.items.find((x) => x.volume === v.volume) : null
                      if (!plan && Array.isArray(p.items) && p.items.length === 1) plan = p.items[0]
                      if (plan && plan.title) {
                        await api.updateVolume(projectId, v.volume, {
                          title: plan.title,
                          event_arc: plan.event_arc ?? [],
                          chapter_count: plan.chapter_count ?? v.chapter_count,
                          ending_hook: plan.ending_hook ?? '',
                        })
                        await loadVolumes()
                        onProductsChange?.()
                      }
                    }}
                  />
                </div>
              )}
              {selected === v.volume && (
                <div className="mt-3 pt-3 border-t border-border">
                  <ChapterList vol={v.volume} chapters={products?.chapters ?? {}} cost={cost} onOpen={(ch) => onOpenChapter?.({ projectId, vol: v.volume, ch })} />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const chapterWords = (ch) =>
  (ch?.scenes ?? []).reduce((n, s) => n + (s.text ?? '').length, 0)

// 按章成本：后端流水只有 token 数，用全局 $/token 均价折算展示（≈ 估算）
function ChapterList({ vol, chapters, cost, onOpen }) {
  const chapterCost = cost && cost.total_tokens > 0 ? cost.est_cost_usd / cost.total_tokens : 0
  const items = Object.entries(chapters)
    .filter(([k]) => k.startsWith(`${vol}_`))
    .sort(([a], [b]) => {
      // 数值序：避免 "1_10" 排到 "1_2" 前面的字符串序问题
      const [av, ac] = a.split("_").map(Number)
      const [bv, bc] = b.split("_").map(Number)
      return av - bv || ac - bc
    })
  return (
    <div>
      <p className="text-xs font-medium text-muted mb-2">已写章节（点击查看/修改）</p>
      {items.length === 0 ? (
        <p className="text-sm text-muted">（尚无章节，点击「新建章节」开始）</p>
      ) : (
        <ul className="text-sm space-y-1">
          {items.map(([key, ch]) => {
            const cb = cost?.chapters?.[key]
            return (
              <li key={key}>
                <button
                  className="w-full flex items-center justify-between text-left text-muted hover:text-foreground rounded px-2 py-1 hover:bg-black/[0.03] dark:hover:bg-white/[0.06] transition"
                  onClick={() => onOpen?.(Number(key.split('_')[1]))}
                >
                  <span className="truncate">第{ch.chapter}章 · {ch.title}</span>
                  <span className="text-xs whitespace-nowrap">
                    {chapterWords(ch) >= 10000
                      ? `${(chapterWords(ch) / 10000).toFixed(1)} 万字`
                      : `${chapterWords(ch)} 字`}
                    <span className="text-primary ml-2">{ch.scenes?.length ?? 0} 场景</span>
                    {cb && chapterCost > 0 && (
                      <span className="ml-2">≈ ${(cb.total_tokens * chapterCost).toFixed(2)}</span>
                    )}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

// ---- 章节详情 + 修改 ----
// ---- 新增卷 ----
function NewVolumeForm({ projectId, currentVolumes, onCancel, onDone, busy, run, error }) {
  const next = Math.max(0, ...currentVolumes.map((v) => v.volume)) + 1
  const [form, setForm] = useState({ volume: next, title: '', event_arc: [], ending_hook: '' })
  const set = (k, v) => setForm({ ...form, [k]: v })
  return (
    <div className="card p-6">
      <h3 className="text-base font-medium mb-4">手工新增卷</h3>
      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      <label className="block text-xs text-muted mb-1">卷号</label>
      <input className="input mb-3" type="number" value={form.volume} onChange={(e) => set('volume', Number(e.target.value))} />
      <label className="block text-xs text-muted mb-1">卷名</label>
      <input className="input mb-3" value={form.title} onChange={(e) => set('title', e.target.value)} placeholder="如：风起青萍" />
      <label className="block text-xs text-muted mb-1">事件弧（每行一个，可选）</label>
      <textarea className="input mb-3" rows={3} value={form.event_arc.join('\n')} onChange={(e) => set('event_arc', e.target.value.split('\n').filter(Boolean))} />
      <label className="block text-xs text-muted mb-1">卷末悬念（可选）</label>
      <input className="input mb-4" value={form.ending_hook} onChange={(e) => set('ending_hook', e.target.value)} />
      <div className="flex justify-end gap-2">
        <button className="btn-ghost" onClick={onCancel}>返回</button>
        <button
          className="btn-primary"
          disabled={busy || !form.title.trim()}
          onClick={() => run(async () => { await api.createVolume(projectId, { generate: false, volume: form }); onDone() })}
        >
          {busy ? '保存中…' : '保存卷'}
        </button>
      </div>
    </div>
  )
}

// ---- 编辑卷 ----
function VolumeEditForm({ projectId, volume, onCancel, onDone, busy, run, error }) {
  const [form, setForm] = useState(() => ({
    title: volume?.title ?? '',
    event_arc: volume?.event_arc ?? [],
    ending_hook: volume?.ending_hook ?? '',
  }))
  const set = (k, v) => setForm({ ...form, [k]: v })
  return (
    <div className="card p-6">
      <h3 className="text-base font-medium mb-4">编辑卷{volume?.volume}</h3>
      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      <label className="block text-xs text-muted mb-1">卷名</label>
      <input className="input mb-3" value={form.title} onChange={(e) => set('title', e.target.value)} />
      <label className="block text-xs text-muted mb-1">事件弧（每行一个，可选）</label>
      <textarea className="input mb-3" rows={3} value={form.event_arc.join('\n')} onChange={(e) => set('event_arc', e.target.value.split('\n').filter(Boolean))} />
      <label className="block text-xs text-muted mb-1">卷末悬念（可选）</label>
      <input className="input mb-4" value={form.ending_hook} onChange={(e) => set('ending_hook', e.target.value)} />
      <div className="flex justify-end gap-2">
        <button className="btn-ghost" onClick={onCancel}>返回</button>
        <button
          className="btn-primary"
          disabled={busy}
          onClick={() => run(async () => { await api.updateVolume(projectId, volume.volume, form); onDone() })}
        >
          {busy ? '保存中…' : '保存'}
        </button>
      </div>
    </div>
  )
}

