// 各环节确认点的人类友好展示（替代裸 JSON）
import { useState } from 'react'

// stage6 专用：审查报告 + 超限警示 + 每条矛盾的作者修复指令
function Stage6View({ r, onSubmit, busy }) {
  const [fixes, setFixes] = useState({})
  const issues = (r.issues ?? []).filter((i) => !i.resolved)
  const fixed = (r.issues ?? []).filter((i) => i.resolved)
  const exhausted = r.needs_human || (issues.length > 0 && (r.auto_fix_attempts ?? 0) >= 3)
  const KIND_LABELS = { setting: '设定冲突', character: '人物OOC', timeline: '时间线', style: '文风', logic: '逻辑' }
  const hasInput = Object.values(fixes).some((v) => v && v.trim())
  const submitFixes = () => {
    const list = Object.entries(fixes)
      .filter(([, v]) => v && v.trim())
      .map(([loc, instruction]) => ({ scene_id: loc, instruction: instruction.trim() }))
    if (list.length) onSubmit?.({ action: 'edit', data: { apply_edits: true, fixes: list } })
  }
  return (
    <div className="card p-5">
      {exhausted && issues.length > 0 && (
        <div className="rounded border border-amber-300 bg-amber-50 dark:bg-amber-900/20 text-amber-800 dark:text-amber-300 px-4 py-3 mb-3">
          <p className="text-sm font-medium">⚠️ 自动修复已超限（{r.auto_fix_attempts ?? 0} 次），以下矛盾无法自动解决</p>
          <p className="text-xs mt-1 opacity-80">
            请阅读每条矛盾的说明与位置，选择处理方式：填写修复指令让 AI 定点修改、点「重新生成」重新检查，或判断可容忍则直接「接受」。
          </p>
        </div>
      )}
      {issues.length === 0 ? (
        <>
          <p className="text-sm font-medium text-green-700 dark:text-green-400">✓ 本章一致性检查通过</p>
          {fixed.length > 0 && (
            <p className="text-xs text-muted mt-1">已自动修复 {fixed.length} 处（{r.auto_fix_attempts} 次修复）</p>
          )}
          <p className="text-xs text-muted mt-2">确认后进入下一环节。</p>
        </>
      ) : (
        <>
          <p className="text-sm text-muted mb-3">
            本章发现 {issues.length} 个待处理问题（已自动修复 {fixed.length} 处，{r.auto_fix_attempts ?? 0} 次修复）：
          </p>
          {issues.map((i, idx) => (
            <div key={idx} className="rounded border border-border bg-black/[0.02] dark:bg-white/[0.03] p-3 mb-2">
              <p className="text-sm">{i.description}</p>
              <p className="text-xs text-muted mt-1">
                {KIND_LABELS[i.kind] ?? i.kind}
                {' · '}位置：{i.location}
              </p>
              {i.fix_action && <p className="text-xs text-primary mt-1">AI 建议：{i.fix_action}</p>}
              {exhausted && (
                <div className="flex gap-2 mt-2 items-center flex-wrap">
                  <select
                    className="input text-xs w-auto"
                    defaultValue=""
                    onChange={(e) => setFixes((f) => ({ ...f, [idx]: { ...f[idx], scene_id: e.target.value } }))}
                  >
                    <option value="" disabled>选择要修改的场景…</option>
                    {(r.scenes ?? []).map((s) => (
                      <option key={s.id} value={s.id}>{s.heading || s.id}</option>
                    ))}
                  </select>
                  <input
                    className="input text-xs flex-1 min-w-[200px]"
                    placeholder="修复指令（如：把眼睛颜色改回灰色，与档案一致）"
                    onChange={(e) => setFixes((f) => ({ ...f, [idx]: { ...f[idx], instruction: e.target.value } }))}
                  />
                </div>
              )}
            </div>
          ))}
          {exhausted && (
            <div className="flex justify-end mt-2">
              <button className="btn-primary text-sm" disabled={busy || !hasInput} onClick={submitFixes}>
                {busy ? '修复中…' : '🔧 按指令修复并复查'}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function Field({ label, value }) {
  if (value === undefined || value === null || value === '') return null
  if (Array.isArray(value)) {
    if (value.length === 0) return null
    return (
      <div className="mb-3">
        <p className="text-xs font-medium text-muted mb-1">{label}</p>
        <ul className="text-sm space-y-0.5">
          {value.map((v, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-primary">·</span>
              <span>{typeof v === 'string' ? v : JSON.stringify(v)}</span>
            </li>
          ))}
        </ul>
      </div>
    )
  }
  return (
    <div className="mb-3">
      <p className="text-xs font-medium text-muted mb-1">{label}</p>
      <p className="text-sm leading-6 whitespace-pre-wrap">{String(value)}</p>
    </div>
  )
}

function EntryList({ title, entries, fields }) {
  if (!entries || entries.length === 0) return null
  return (
    <div className="mb-4">
      <p className="text-xs font-semibold text-primary mb-2">{title}</p>
      <div className="space-y-2">
        {entries.map((e, i) => (
          <div key={i} className="rounded border border-border bg-black/[0.02] dark:bg-white/[0.03] p-3">
            {fields.map(([key, label]) => {
              const v = e[key]
              if (v === undefined || v === null || v === '') return null
              return (
                <div key={key} className="mb-1.5 last:mb-0">
                  <span className="text-xs text-muted mr-2">{label}</span>
                  <span className="text-sm">
                    {Array.isArray(v) ? v.join(' / ') : typeof v === 'object' ? JSON.stringify(v) : v}
                  </span>
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}

// 各环节渲染器
export default function StageView({ stage, payload, onSubmit, busy }) {
  if (!payload) return null

  switch (stage) {
    case 'stage0': {
      const c = payload
      return (
        <div className="card p-5">
          <h3 className="text-base font-medium mb-4">{c.title_idea || '未命名'}</h3>
          <Field label="一句话故事" value={c.logline} />
          <Field label="核心卖点" value={c.core_selling} />
          <Field label="目标读者" value={c.target_reader} />
          <div className="grid grid-cols-2 gap-3">
            <Field label="预计字数" value={c.target_words ? `${c.target_words.toLocaleString()} 字` : null} />
            <Field label="卷数" value={c.volumes ? `${c.volumes} 卷` : null} />
          </div>
          <Field label="基调" value={c.tone} />
          <Field label="敏感红线" value={c.red_lines} />
        </div>
      )
    }

    case 'stage1': {
      const w = payload
      return (
        <div className="card p-5">
          <EntryList title="地理" entries={w.geography} fields={[['name', '名称'], ['desc', '描述']]} />
          <EntryList title="势力" entries={w.factions} fields={[['name', '名称'], ['desc', '描述']]} />
          <EntryList title="力量体系" entries={w.power_system} fields={[['name', '名称'], ['desc', '描述']]} />
          <EntryList title="历史事件" entries={w.history} fields={[['name', '事件'], ['desc', '说明']]} />
          <EntryList title="社会习俗" entries={w.customs} fields={[['name', '名称'], ['desc', '描述']]} />
          <EntryList title="特有术语" entries={w.glossary} fields={[['name', '术语'], ['desc', '解释']]} />
        </div>
      )
    }

    case 'stage2': {
      const chars = payload
      if (!Array.isArray(chars) || chars.length === 0) return null
      return (
        <div className="space-y-3">
          {chars.map((c, i) => (
            <div key={i} className="card p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium">{c.name}</span>
                <span className="text-xs text-muted">
                  {({ protagonist: '主角', ally: '伙伴', antagonist: '反派', supporting: '配角' })[c.role] ?? c.role}
                </span>
              </div>
              <Field label="动机" value={c.motivation} />
              <Field label="缺陷" value={c.flaw} />
              {c.arc?.length > 0 && <Field label="成长弧光" value={c.arc.map((a) => a.change).filter(Boolean)} />}
            </div>
          ))}
        </div>
      )
    }

    case 'stage3': {
      const o = payload
      return (
        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs text-muted">全书大纲</span>
            <span className="text-xs text-muted">v{o.version}</span>
          </div>
          <Field label="故事立意" value={o.premise} />
          <Field label="整体结构" value={o.structure} />
          <Field label="核心转折事件" value={o.core_events} />
          <Field label="结局" value={o.ending} />
          <p className="text-xs font-semibold text-primary mt-2 mb-1">分卷规划</p>
          {(o.volumes ?? []).map((v) => (
            <div key={v.volume} className="rounded border border-border bg-black/[0.02] dark:bg-white/[0.03] p-3 mb-2">
              <span className="text-sm font-medium">卷{v.volume} · {v.title}</span>
              <p className="text-sm text-muted mt-1">事件弧：{(v.event_arc ?? []).join(' / ') || '—'}</p>
              <p className="text-sm text-muted">章数：{v.chapter_count}</p>
              <p className="text-sm text-muted">结尾钩子：{v.ending_hook || '—'}</p>
            </div>
          ))}
        </div>
      )
    }

    case 'stage4a': {
      const plans = payload
      if (!Array.isArray(plans)) return null
      return (
        <div className="space-y-3">
          {plans.map((v) => (
            <div key={v.volume} className="card p-4">
              <span className="font-medium">卷{v.volume} · {v.title}</span>
              <Field label="事件弧" value={v.event_arc} />
              <Field label="埋下伏笔" value={v.foreshadow_seed} />
              <Field label="回收伏笔" value={v.foreshadow_payoff} />
              <Field label="章数安排" value={v.chapter_count ? `${v.chapter_count} 章` : null} />
              <Field label="卷末悬念" value={v.ending_hook} />
            </div>
          ))}
        </div>
      )
    }

    case 'stage4b': {
      const p = payload
      return (
        <div className="card p-5">
          <h3 className="text-base font-medium mb-3">{p.title || `第${p.chapter}章`}</h3>
          <Field label="本章目标" value={p.goal} />
          <Field label="冲突" value={p.conflicts} />
          <Field label="章节钩子" value={p.hook} />
          <Field label="出场人物" value={p.characters} />
          <Field label="叙事视角" value={p.pov} />
          <p className="text-xs font-semibold text-primary mt-2 mb-1">情绪节拍</p>
          {(p.beats ?? []).map((b, i) => (
            <div key={i} className="flex gap-2 text-sm mb-1">
              <span className="text-muted">{i + 1}.</span>
              <span>{b.desc || b.type}</span>
            </div>
          ))}
        </div>
      )
    }

    case 'stage6':
      return <Stage6View r={payload} onSubmit={onSubmit} busy={busy} />

    case 'stage8': {
      const r = payload
      return (
        <div className="card p-5">
          <p className="text-xs text-muted mb-2">审校范围：{r.scope === 'final' ? '全书终审' : r.scope}</p>
          <p className="text-sm leading-6 whitespace-pre-wrap">{r.comments}</p>
        </div>
      )
    }

    default:
      return (
        <div className="card p-5">
          <pre className="text-xs leading-6 whitespace-pre-wrap">{JSON.stringify(payload, null, 2)}</pre>
        </div>
      )
  }
}
