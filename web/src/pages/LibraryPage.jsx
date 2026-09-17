import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

const FIELDS = {
  personality: ['name', 'category', 'tags', 'description', 'behavior_patterns', 'dialogue_style', 'strengths', 'weaknesses', 'growth_direction'],
  tool: ['name', 'category', 'description', 'usage_guidelines', 'examples', 'chapter_placement', 'common_mistakes'],
  character_template: ['name', 'role', 'description', 'motivation', 'flaw', 'behavior', 'dialogue_style', 'tags', 'applicable_genres'],
  technique: ['name', 'category', 'mode', 'apply_stage', 'description', 'guidance', 'checklist', 'tags'],
}

const TABS = [
  ['personality', '性格库'],
  ['tool', '小说工具库'],
  ['character_template', '人物模板库'],
  ['technique', '写作手法库'],
]

const LIST_FIELDS = new Set(['tags', 'behavior_patterns', 'strengths', 'weaknesses', 'examples', 'common_mistakes', 'applicable_genres', 'checklist'])

// 字段元数据：中文化标签 + 控件类型（text/textarea/list/select）
const FIELD_META = {
  name: { label: '名称' },
  category: { label: '分类' },
  description: { label: '说明', textarea: true },
  guidance: { label: '执行指导（告诉 AI 怎么运用）', textarea: true },
  checklist: { label: '检查要点（逗号分隔）', list: true },
  tags: { label: '标签（逗号分隔）', list: true },
  mode: { label: '类型', select: [['knowledge', '知识型'], ['mechanism', '机制型']] },
  apply_stage: { label: '生效阶段', select: [['all', '全部环节'], ['planning', '规划'], ['writing', '写作'], ['review', '检查']] },
  behavior_patterns: { label: '行为模式（逗号分隔）', list: true },
  dialogue_style: { label: '对话风格' },
  strengths: { label: '优点（逗号分隔）', list: true },
  weaknesses: { label: '缺点（逗号分隔）', list: true },
  growth_direction: { label: '成长方向' },
  usage_guidelines: { label: '使用指导', textarea: true },
  examples: { label: '示例（每行一条）', textarea: true },
  chapter_placement: { label: '适用位置' },
  common_mistakes: { label: '常见错误（逗号分隔）', list: true },
  role: { label: '定位' },
  motivation: { label: '动机', textarea: true },
  flaw: { label: '缺陷' },
  behavior: { label: '行为特征' },
  applicable_genres: { label: '适用题材（逗号分隔）', list: true },
}

export default function LibraryPage() {
  const [kind, setKind] = useState('personality')
  const [entries, setEntries] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [error, setError] = useState(null)

  const load = () =>
    api
      .libraryList(kind)
      .then((d) => {
        setError(null)
        setEntries(d.entries)
      })
      .catch((e) => setError(e.message))

  useEffect(() => {
    load()
  }, [kind])

  return (
    <div className="max-w-5xl mx-auto px-8 py-10">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h2 className="text-2xl font-semibold">写作基础库</h2>
          <p className="text-sm text-muted mt-1">性格参考与小说创作工具，跨项目共享</p>
        </div>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>
          新增条目
        </button>
      </div>

      <div className="flex gap-2 mt-4 mb-6">
        {TABS.map(([id, label]) => (
          <button
            key={id}
            onClick={() => setKind(id)}
            className={`rounded px-3 py-1.5 text-sm transition ${
              kind === id ? 'bg-primary text-white' : 'text-muted hover:bg-black/5'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <div className="mb-4 rounded border border-red-200 bg-red-50 text-red-700 px-4 py-3 text-sm">{error}</div>}

      {!error && entries.length === 0 ? (
        <div className="card p-12 text-center text-muted text-sm">
          暂无数据 —— 请先在后端执行 <code className="bg-black/5 rounded px-1">novel-agent lib seed</code>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {entries.map((e) => (
            <div key={e.id} className="card p-5">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">{e.name}</h3>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted">{e.category}</span>
                  <button
                    className="text-xs text-muted hover:text-red-600"
                    onClick={() => {
                      if (confirm(`删除「${e.name}」？`)) api.libraryDelete(kind, e.id).then(load)
                    }}
                  >
                    删除
                  </button>
                </div>
              </div>
              <p className="text-sm text-muted mt-2 line-clamp-2">{e.description}</p>
            </div>
          ))}
        </div>
      )}

      {showAdd && (
        <AddEntryDialog
          kind={kind}
          onClose={() => setShowAdd(false)}
          onAdded={() => {
            setShowAdd(false)
            load()
          }}
          onError={setError}
        />
      )}
    </div>
  )
}

function AddEntryDialog({ kind, onClose, onAdded, onError }) {
  const [form, setForm] = useState(() => {
    const base = Object.fromEntries(FIELDS[kind].map((f) => [f, '']))
    // 下拉字段给默认值（如 mode=knowledge），避免空字符串导致注入失效
    for (const f of FIELDS[kind]) {
      const meta = FIELD_META[f]
      if (meta?.select && !base[f]) base[f] = meta.select[0][0]
    }
    return base
  })
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setBusy(true)
    try {
      const entry = { id: `${kind}_${Date.now().toString(36)}` }
      for (const f of FIELDS[kind]) {
        const v = form[f] ?? ''
        entry[f] = FIELD_META[f]?.list
          ? v.split(/[,，\n]/).map((s) => s.trim()).filter(Boolean)
          : v
      }
      await api.libraryAdd(kind, entry)
      onAdded()
    } catch (e) {
      onError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onClose}>
      <div className="card w-[480px] p-6 max-h-[85vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-base font-semibold mb-4">
          新增 {{ personality: '性格', tool: '工具', character_template: '人物模板', technique: '写作手法' }[kind] ?? ''} 条目
        </h3>
        {FIELDS[kind].map((f) => {
          const meta = FIELD_META[f] ?? { label: f }
          const value = form[f] ?? ''
          return (
            <label key={f} className="block text-xs text-muted mb-1">
              {meta.label ?? f}
              {meta.select ? (
                <select
                  className="input mt-1 mb-3"
                  value={value || meta.select[0][0]}
                  onChange={(e) => setForm({ ...form, [f]: e.target.value })}
                >
                  {meta.select.map(([v, lbl]) => (
                    <option key={v} value={v}>{lbl}</option>
                  ))}
                </select>
              ) : meta.textarea ? (
                <textarea
                  className="input mt-1 mb-3"
                  rows={2}
                  value={value}
                  onChange={(e) => setForm({ ...form, [f]: e.target.value })}
                />
              ) : (
                <input className="input mt-1 mb-3" value={value} onChange={(e) => setForm({ ...form, [f]: e.target.value })} />
              )}
            </label>
          )
        })}
        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose}>取消</button>
          <button className="btn-primary" disabled={busy || !form.name?.trim()} onClick={submit}>
            {busy ? '提交中…' : '提交'}
          </button>
        </div>
      </div>
    </div>
  )
}
