import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

const FIELDS = {
  personality: ['name', 'category', 'tags', 'description', 'behavior_patterns', 'dialogue_style', 'strengths', 'weaknesses', 'growth_direction'],
  tool: ['name', 'category', 'description', 'usage_guidelines', 'examples', 'chapter_placement', 'common_mistakes'],
  character_template: ['name', 'role', 'description', 'motivation', 'flaw', 'behavior', 'dialogue_style', 'tags', 'applicable_genres'],
  technique: ['name', 'category', 'mode', 'apply_stage', 'description', 'guidance', 'checklist', 'tags'],
  meme: ['name', 'category', 'kind', 'description', 'content', 'usage', 'emotion', 'risk', 'as_of', 'tags'],
  style: ['name', 'digest', 'text', 'tags', 'as_of'],
}

const TABS = [
  ['personality', '性格库'],
  ['tool', '小说工具库'],
  ['character_template', '人物模板库'],
  ['technique', '写作手法库'],
  ['meme', '梗库'],
  ['style', '仿写库'],
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
  kind: { label: '梗类型', select: [['句式梗', '句式梗'], ['名场面梗', '名场面梗'], ['谐音梗', '谐音梗'], ['情绪梗', '情绪梗'], ['行话梗', '行话梗']] },
  content: { label: '梗本体（示例句）', textarea: true },
  usage: { label: '用法（什么剧情/情绪下用）', textarea: true },
  emotion: { label: '情绪色彩（喜/丧/讽/燃…）' },
  risk: { label: '风险等级', select: [['safe', 'safe（化用安全）'], ['caution', 'caution（明梗注意限流）'], ['avoid', 'avoid（直接引用，勿用）']] },
  as_of: { label: '入库时间（YYYY-MM）' },
  digest: { label: '风格要点（声线采样：人称/节奏/用词/对话占比；可留空由 AI 提取）', textarea: true },
  text: { label: '样本原文（≤800 字，写手将模仿其口吻与节奏）', textarea: true },
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
  const [showPopulate, setShowPopulate] = useState(false)
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
        <div className="flex gap-2">
          {kind === 'meme' && (
            <button className="btn-ghost" onClick={() => setShowPopulate(true)}>
              ✨ AI 填充
            </button>
          )}
          <button className="btn-primary" onClick={() => setShowAdd(true)}>
            新增条目
          </button>
        </div>
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
              <p className="text-sm text-muted mt-2 line-clamp-2">{e.description || e.content}</p>
              {kind === 'meme' && (
                <p className="text-xs text-muted mt-1.5 flex flex-wrap gap-2">
                  <span>{e.kind}</span>
                  <span>·</span>
                  <span>{e.emotion}</span>
                  <span>·</span>
                  <span className={e.risk === 'caution' ? 'text-amber-600' : e.risk === 'avoid' ? 'text-red-600' : ''}>{e.risk}</span>
                  {e.as_of && <><span>·</span><span>{e.as_of}</span></>}
                </p>
              )}
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

      {showPopulate && (
        <PopulateDialog
          onClose={() => setShowPopulate(false)}
          onDone={(msg) => {
            setShowPopulate(false)
            setError(msg || null)
            load()
          }}
        />
      )}
    </div>
  )
}

function PopulateDialog({ onClose, onDone }) {
  const [mode, setMode] = useState('generate') // generate=AI 生成 | extract=粘贴提取
  const [topic, setTopic] = useState('职场')
  const [count, setCount] = useState(10)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async () => {
    setBusy(true)
    setErr(null)
    try {
      if (mode === 'generate') {
        const r = await api.populateMemes(topic, count)
        onDone(`✨ AI 填充完成：新增 ${r.added} 条「${topic}」梗（重复的已自动跳过）`)
      } else {
        const r = await api.extractMemes(text)
        onDone(`✨ 提取完成：新增 ${r.added} 条梗（重名/无效的已自动跳过）`)
      }
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  const valid = mode === 'generate' ? topic.trim() : text.trim()

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onClose}>
      <div className="card w-[480px] p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex gap-2 mb-3">
          {[
            ['generate', '✨ AI 生成'],
            ['extract', '📋 粘贴提取'],
          ].map(([m, label]) => (
            <button
              key={m}
              className={`rounded px-3 py-1 text-sm transition ${mode === m ? 'bg-primary text-white' : 'text-muted hover:bg-black/5'}`}
              onClick={() => { setMode(m); setErr(null) }}
            >
              {label}
            </button>
          ))}
        </div>
        {mode === 'generate' ? (
          <>
            <p className="text-xs text-muted mb-4">
              AI 按题材方向批量整理网络热梗/流行句式入库（自动跳过与库内重名的条目）。热梗有时效性，
              条目带入库时间（as_of），是否仍流行由你判断，可随时删除。
            </p>
            <label className="block text-xs text-muted mb-1">
              题材方向
              <input className="input mt-1 mb-3" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="如：职场 / 情感 / 校园 / 玄幻" />
            </label>
            <label className="block text-xs text-muted mb-1">
              数量（1-30）
              <input className="input mt-1 mb-3" type="number" min="1" max="30" value={count} onChange={(e) => setCount(e.target.value)} />
            </label>
          </>
        ) : (
          <>
            <p className="text-xs text-muted mb-4">
              把你在网上刷到的梗随手复制过来（网页摘录/段子罗列/聊天记录都行），AI 从中提取结构化梗条目入库。
              新鲜度由你把关，零外部依赖。
            </p>
            <label className="block text-xs text-muted mb-1">
              粘贴素材
              <textarea
                className="input mt-1 mb-3"
                rows={6}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="粘贴你在网上看到的梗/流行句…"
              />
            </label>
          </>
        )}
        {err && <div className="rounded border border-red-200 bg-red-50 text-red-700 px-3 py-2 text-xs mb-3">{err}</div>}
        <div className="flex justify-end gap-2">
          <button className="btn-ghost text-sm" onClick={onClose}>取消</button>
          <button className="btn-primary text-sm" disabled={busy || !valid} onClick={submit}>
            {busy ? '处理中…' : mode === 'generate' ? '开始填充' : '提取入库'}
          </button>
        </div>
      </div>
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
          新增 {{ personality: '性格', tool: '工具', character_template: '人物模板', technique: '写作手法', meme: '梗' }[kind] ?? ''} 条目
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
