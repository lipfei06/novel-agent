import { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../api/client.js'
import RelationGraph from './RelationGraph.jsx'
import ChatPanel from './ChatPanel.jsx'
import TechniquePanel from './TechniquePanel.jsx'
import CanonPanel from './CanonPanel.jsx'

// 作品设定区：全局规划 / 选题 / 世界观 / 人物 / 总纲 / 手法 / 伏笔与道具
const TABS = [
  ['chief', '全局规划'],
  ['concept', '选题立项'],
  ['world_bible', '世界观'],
  ['characters', '人物'],
  ['outline', '总纲'],
  ['techniques', '手法'],
  ['canon', '伏笔与道具'],
]

export default function ProductsPanel({ projectId, autoCollapse = false }) {
  const [data, setData] = useState(null)
  const [tab, setTab] = useState('chief')
  const [open, setOpen] = useState(!autoCollapse)

  // 流水线进入章节阶段时自动收起（作者仍可手动展开）
  useEffect(() => {
    if (autoCollapse) setOpen(false)
  }, [autoCollapse])

  const load = () => api.products(projectId).then(setData).catch(() => {})

  useEffect(() => {
    load()
  }, [projectId])

  const save = async (field, value) => {
    await api.productsUpdate(projectId, field, value)
    await load()
  }

  const hasSetup = data && (data.concept || data.outline)

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold">作品设定</h3>
        <button className="btn-ghost text-xs" onClick={() => setOpen(!open)}>
          {open ? '收起' : '展开'}
        </button>
      </div>

      {open && (
        <>
          {!hasSetup ? (
            <p className="text-sm text-muted">设定将在创作流程中生成（选题→世界观→人物→总纲），生成后可在此修改。</p>
          ) : (
            <>
              <div className="flex gap-1 mb-4 border-b border-border pb-3 overflow-x-auto">
                {TABS.map(([id, label]) => (
                  <button
                    key={id}
                    onClick={() => setTab(id)}
                    className={`rounded px-3 py-1.5 text-sm whitespace-nowrap transition ${
                      tab === id ? 'bg-primary text-white' : 'text-muted hover:bg-black/5 dark:hover:bg-white/10'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {tab === 'chief' && (
                <ChatPanel
                  projectId={projectId}
                  context="chief"
                  title="全局规划顾问 · 站在全书高度帮你把控方向"
                  hidePropose
                  placeholder="问方向、问节奏、问风险：如'目前伏笔回收得怎么样''接下来该写什么''哪里有问题'"
                />
              )}
              {tab === 'concept' && (
                <div className="space-y-4">
                  <ChatPanel
                    projectId={projectId}
                    context="concept"
                    title="选题助手"
                    target="concept"
                    onApply={async (p) => { await save('concept', p) }}
                    placeholder="聊聊你的小说立意…"
                  />
                  <ConceptSection value={data.concept} onSave={(v) => save('concept', v)} />
                </div>
              )}
              {tab === 'world_bible' && (
                <div className="space-y-4">
                  <ChatPanel
                    projectId={projectId}
                    context="world"
                    title="世界观助手"
                    target="world_bible"
                    onApply={async (p) => { await save('world_bible', p) }}
                    placeholder="聊聊世界观的设定…"
                  />
                  <WorldSection value={data.world_bible} onSave={(v) => save('world_bible', v)} />
                </div>
              )}
              {tab === 'characters' && (
                <div className="space-y-4">
                  <ChatPanel
                    projectId={projectId}
                    context="characters"
                    title="人物助手"
                    target="characters"
                    onApply={async (p) => { await save('characters', Array.isArray(p.items) ? p.items : p) }}
                    placeholder="聊聊人物设计…"
                  />
                  <CharactersSection value={data.characters} stateValue={data.character_state} onSave={(v) => save('characters', v)} projectId={projectId} />
                </div>
              )}
              {tab === 'outline' && (
                <div className="space-y-4">
                  <ChatPanel
                    projectId={projectId}
                    context="outline"
                    title="总纲助手"
                    target="outline"
                    onApply={async (p) => { await save('outline', p) }}
                    placeholder="聊聊全书结构/分卷…"
                  />
                  <OutlineSection value={data.outline} onSave={(v) => save('outline', v)} />
                </div>
              )}
              {tab === 'techniques' && (
                <TechniquePanel
                  projectId={projectId}
                  attached={data.techniques}
                  blueprint={data.narrative_blueprint}
                  onChanged={load}
                />
              )}
              {tab === 'canon' && <CanonPanel data={data} />}
            </>
          )}
        </>
      )}
    </div>
  )
}

// ---- 编辑上下文 ----
const Ctx = createContext(null)
function useEdit() {
  return useContext(Ctx)
}

function Editable({ value, onSave, children }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(null)
  const [saving, setSaving] = useState(false)

  const start = () => {
    setDraft(JSON.parse(JSON.stringify(value ?? {})))
    setEditing(true)
  }
  const submit = async () => {
    setSaving(true)
    try {
      await onSave(draft)
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }
  return (
    <Ctx.Provider value={{ editing, draft, setDraft }}>
      {children}
      <div className="mt-3">
        {!editing ? (
          <button className="btn-ghost text-xs" onClick={start}>编辑 ✎</button>
        ) : (
          <div className="flex gap-2 justify-end">
            <button className="btn-ghost text-xs" onClick={() => setEditing(false)}>取消</button>
            <button className="btn-primary text-xs" disabled={saving} onClick={submit}>
              {saving ? '保存中…' : '保存'}
            </button>
          </div>
        )}
      </div>
    </Ctx.Provider>
  )
}

// ---- 通用展示 ----
function Show({ rows }) {
  return (
    <div className="space-y-2">
      {rows.filter(([, v]) => v !== undefined && v !== null && v !== '').map(([label, v]) => (
        <div key={label}>
          <span className="text-xs text-muted">{label}：</span>
          <span className="text-sm">
            {Array.isArray(v) ? v.join(' / ') : String(v)}
          </span>
        </div>
      ))}
    </div>
  )
}

// ---- 选题 ----
function ConceptSection({ value, onSave }) {
  return (
    <Editable value={value} onSave={onSave}>
      <Show
        rows={[
          ['书名', value?.title_idea],
          ['一句话故事', value?.logline],
          ['核心卖点', value?.core_selling],
          ['目标读者', value?.target_reader],
          ['预计字数', value?.target_words],
          ['基调', value?.tone],
          ['敏感红线', value?.red_lines],
        ]}
      />
      <EditForm>
        <TextField k="title_idea" label="书名" />
        <TextField k="logline" label="一句话故事" textarea />
        <TextField k="core_selling" label="核心卖点" textarea />
        <TextField k="target_reader" label="目标读者" textarea />
        <TextField k="target_words" label="预计字数" />
        <TextField k="tone" label="基调" textarea />
        <ListField k="red_lines" label="敏感红线" />
      </EditForm>
    </Editable>
  )
}

// ---- 世界观 ----
const WORLD_CATS = [
  ['geography', '地理'], ['factions', '势力'], ['power_system', '力量体系'],
  ['history', '历史事件'], ['customs', '社会习俗'], ['glossary', '特有术语'],
]
function parseEntries(text) {
  return text.split('\n').map((l) => l.trim()).filter(Boolean).map((l) => {
    const [name, ...rest] = l.split(/[|：:]/)
    return { name: name?.trim() || '', desc: rest.join('：').trim() }
  })
}
function WorldSection({ value, onSave }) {
  return (
    <Editable value={value} onSave={onSave}>
      <div className="space-y-1 text-sm">
        {WORLD_CATS.map(([k, label]) => {
          const items = value?.[k] ?? []
          return (
            <div key={k}>
              <span className="text-xs text-muted">{label}：</span>
              {items.length ? items.map((i, idx) => <div key={idx}>{i.name} · {i.desc}</div>) : <span className="text-muted">—</span>}
            </div>
          )
        })}
      </div>
      <EditForm>
        {WORLD_CATS.map(([k, label]) => (
          <KeyedTextarea key={k} k={k} label={`${label}（每行：名称｜描述）`} toList={parseEntries} fromList={(items) => items.map((i) => `${i.name}｜${i.desc}`).join('\n')} />
        ))}
      </EditForm>
    </Editable>
  )
}

// ---- 人物 ----
const ROLES = { protagonist: '主角', ally: '伙伴', antagonist: '反派', supporting: '配角' }
const TIERS = { main: '主', supporting: '次', background: '路人' }
const STATUS_LABEL = { active: '在世', dead: '已故', absent: '退场', transformed: '蜕变' }
const ARC_LABEL = { start: '弧光·开端', mid: '弧光·成长', end: '弧光·蜕变' }

function CharactersSection({ value, stateValue, onSave, projectId }) {
  const chars = value ?? []
  const states = stateValue?.entries ?? []
  const [saved, setSaved] = useState({})
  const [showGraph, setShowGraph] = useState(false)

  const saveTemplate = async (cid) => {
    try {
      await api.saveCharacterTemplate(projectId, cid)
      setSaved({ ...saved, [cid]: true })
    } catch {
      setSaved({ ...saved, [cid]: false })
    }
  }

  return (
    <Editable value={value} onSave={onSave}>
      {/* 角色当前状态卡 */}
      {states.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-semibold text-primary mb-2">角色当前状态（随章节更新）</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {states.map((s, i) => (
              <div key={i} className="rounded border border-border p-3 text-sm">
                <span className="font-medium">{s.name}</span>
                <span className={`text-xs ml-2 px-1.5 py-0.5 rounded ${
                  s.status === 'dead' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                    : s.status === 'active' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                      : 'bg-black/5 text-muted dark:bg-white/10'
                }`}>
                  {STATUS_LABEL[s.status] ?? s.status}
                </span>
                {s.arc_stage && <span className="text-xs text-muted ml-1">{ARC_LABEL[s.arc_stage] ?? s.arc_stage}</span>}
                <div className="text-xs text-muted mt-1 leading-5">
                  位置：{s.location || '—'} · 情绪：{s.mood || '—'}
                  {s.health ? ` · 健康：${s.health}` : ''}
                </div>
                {s.goal_progress && <div className="text-xs text-muted">目标：{s.goal_progress}</div>}
                {s.knowledge && <div className="text-xs text-muted">知情：{s.knowledge}</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 关系图谱开关 */}
      <div className="mb-4 flex justify-end">
        <button className="btn-ghost text-xs" onClick={() => setShowGraph(!showGraph)}>
          {showGraph ? '收起关系图谱' : '展开关系图谱'}
        </button>
      </div>
      {showGraph && projectId && <div className="mb-4"><RelationGraph projectId={projectId} /></div>}

      <div className="space-y-2">
        {chars.length === 0 && <p className="text-sm text-muted">暂无人物</p>}
        {chars.map((c, i) => (
          <div key={c.id ?? i} className="rounded border border-border p-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="font-medium">
                {c.name}
                <span className="text-xs text-muted ml-2">{ROLES[c.role] ?? c.role}</span>
                <span className={`text-xs ml-1 px-1.5 py-0.5 rounded ${
                  c.tier === 'main' ? 'bg-primary/10 text-primary' : 'bg-black/5 text-muted dark:bg-white/10'
                }`}>
                  {TIERS[c.tier] ?? c.tier ?? '次'}
                </span>
              </span>
              {projectId && (
                <button
                  className="btn-ghost text-xs"
                  onClick={() => saveTemplate(c.id)}
                  disabled={saved[c.id] !== undefined}
                >
                  {saved[c.id] === true ? '已存模板 ✓' : '存为模板'}
                </button>
              )}
            </div>
            <div className="text-xs text-muted mt-1">动机：{c.motivation} · 缺陷：{c.flaw}</div>
            {c.appearance && <div className="text-xs text-muted mt-0.5">外貌：{c.appearance}</div>}
          </div>
        ))}
      </div>
      <CharactersEdit roles={ROLES} />
    </Editable>
  )
}
function CharactersEdit({ roles }) {
  const { editing, draft, setDraft } = useEdit()
  if (!editing) return null
  const chars = Array.isArray(draft) ? draft : []
  const setChar = (i, k, v) => setDraft(chars.map((c, idx) => (idx === i ? { ...c, [k]: v } : c)))
  const add = () => setDraft([...chars, { id: `c${Date.now().toString(36)}`, name: '', role: 'supporting', tier: 'supporting', motivation: '', flaw: '', appearance: '', voice: '', habits: '', background: '', signature_item: '' }])
  const remove = (i) => setDraft(chars.filter((_, idx) => idx !== i))
  return (
    <div className="mt-2 space-y-2">
      {chars.map((c, i) => (
        <div key={i} className="rounded border border-border p-3 space-y-2">
          <div className="flex gap-2">
            <input className="input text-sm" placeholder="姓名" value={c.name ?? ''} onChange={(e) => setChar(i, 'name', e.target.value)} />
            <select className="input text-sm w-24" value={c.role ?? 'supporting'} onChange={(e) => setChar(i, 'role', e.target.value)}>
              {Object.entries(roles).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <select className="input text-sm w-24" value={c.tier ?? 'supporting'} onChange={(e) => setChar(i, 'tier', e.target.value)}>
              {Object.entries(TIERS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <button className="btn-ghost text-xs" onClick={() => remove(i)}>删除</button>
          </div>
          <input className="input text-sm" placeholder="动机" value={c.motivation ?? ''} onChange={(e) => setChar(i, 'motivation', e.target.value)} />
          <input className="input text-sm" placeholder="缺陷" value={c.flaw ?? ''} onChange={(e) => setChar(i, 'flaw', e.target.value)} />
          <div className="grid grid-cols-2 gap-2">
            <input className="input text-sm" placeholder="外貌（身高体型/面容/标志特征）" value={c.appearance ?? ''} onChange={(e) => setChar(i, 'appearance', e.target.value)} />
            <input className="input text-sm" placeholder="声音/说话方式" value={c.voice ?? ''} onChange={(e) => setChar(i, 'voice', e.target.value)} />
            <input className="input text-sm" placeholder="小动作/习惯" value={c.habits ?? ''} onChange={(e) => setChar(i, 'habits', e.target.value)} />
            <input className="input text-sm" placeholder="出身/关键过往" value={c.background ?? ''} onChange={(e) => setChar(i, 'background', e.target.value)} />
            <input className="input text-sm" placeholder="标志性随身物品" value={c.signature_item ?? ''} onChange={(e) => setChar(i, 'signature_item', e.target.value)} />
          </div>
        </div>
      ))}
      <button className="btn-ghost text-xs" onClick={add}>+ 添加人物</button>
    </div>
  )
}

// ---- 总纲 ----
function OutlineSection({ value, onSave }) {
  return (
    <Editable value={value} onSave={onSave}>
      <Show
        rows={[
          ['故事立意', value?.premise],
          ['整体结构', value?.structure],
          ['核心转折', value?.core_events],
          ['结局', value?.ending],
          ['分卷', (value?.volumes ?? []).map((v) => `卷${v.volume} ${v.title}`)],
        ]}
      />
      <EditForm>
        <TextField k="premise" label="故事立意" textarea />
        <TextField k="structure" label="整体结构" />
        <ListField k="core_events" label="核心转折事件" />
        <TextField k="ending" label="结局" textarea />
      </EditForm>
    </Editable>
  )
}

// ---- 编辑表单辅助组件（仅在 editing 时渲染）----
function EditForm({ children }) {
  const { editing } = useEdit()
  if (!editing) return null
  return <div className="mt-3 pt-3 border-t border-border space-y-1">{children}</div>
}

function TextField({ k, label, textarea }) {
  const { draft, setDraft } = useEdit()
  const set = (v) => setDraft({ ...(draft ?? {}), [k]: v })
  const val = draft?.[k]
  return (
    <label className="block mb-3">
      <span className="text-xs text-muted">{label}</span>
      {textarea ? (
        <textarea className="input mt-1" rows={3} value={val ?? ''} onChange={(e) => set(e.target.value)} />
      ) : (
        <input className="input mt-1" value={val ?? ''} onChange={(e) => set(e.target.value)} />
      )}
    </label>
  )
}

function ListField({ k, label }) {
  const { draft, setDraft } = useEdit()
  const list = draft?.[k] ?? []
  const set = (v) => setDraft({ ...(draft ?? {}), [k]: v })
  return (
    <label className="block mb-3">
      <span className="text-xs text-muted">{label}</span>
      <textarea className="input mt-1 font-mono text-xs" rows={4} value={list.join('\n')} onChange={(e) => set(e.target.value.split('\n').map((s) => s.trim()).filter(Boolean))} placeholder="每行一项" />
    </label>
  )
}

function KeyedTextarea({ k, label, toList, fromList }) {
  const { draft, setDraft } = useEdit()
  const set = (v) => setDraft({ ...(draft ?? {}), [k]: toList(v) })
  return (
    <label className="block mb-3">
      <span className="text-xs text-muted">{label}</span>
      <textarea className="input mt-1 font-mono text-xs" rows={2} defaultValue={fromList(draft?.[k] ?? [])} onChange={(e) => set(e.target.value)} />
    </label>
  )
}
