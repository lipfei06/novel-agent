import { useMemo, useState } from 'react'
import { api } from '../api/client.js'

// 数值序排章节键，避免 "1_10" 排到 "1_2" 前
const sortKeys = (a, b) => {
  const [av, ac] = a.split('_').map(Number)
  const [bv, bc] = b.split('_').map(Number)
  return av - bv || ac - bc
}
const fmtKey = (key) => {
  const [v, c] = String(key).split('_').map(Number)
  return `卷${v}第${c}章`
}

// 常用虚词/高频搭配的二元组，不作为"重复桥段"信号
const STOPGRAMS = new Set([
  '的了', '一个', '自己', '他们', '没有', '什么', '这个', '那个', '已经', '就是',
  '不是', '一下', '起来', '过来', '时候', '知道', '看到', '出来', '开始', '这么',
  '那么', '一声', '他的', '她的', '是我', '是他', '是我', '但是', '可是', '因为',
  '所以', '如果', '现在', '可以', '不能', '不会', '所有', '这样', '那样', '怎么',
  '还是', '只是', '有些', '一点', '突然', '最后', '然后', '而且', '并且', '之后',
])

// 重复桥段警示：按事件句的中文二元组统计"出现在几个不同章"，跨章高频即疑似套路化
export function repetitionPatterns(ledger, minChapters = 3, topN = 12) {
  const byGram = new Map()
  for (const [key, events] of Object.entries(ledger ?? {})) {
    const grams = new Set()
    for (const ev of events ?? []) {
      const t = String(ev ?? '')
      for (let i = 0; i + 1 < t.length; i++) {
        const a = t[i]
        const b = t[i + 1]
        if (a >= '\u4e00' && a <= '\u9fff' && b >= '\u4e00' && b <= '\u9fff' && !STOPGRAMS.has(a + b)) {
          grams.add(a + b)
        }
      }
    }
    for (const g of grams) {
      if (!byGram.has(g)) byGram.set(g, new Set())
      byGram.get(g).add(key)
    }
  }
  return [...byGram.entries()]
    .filter(([, ks]) => ks.size >= minChapters)
    .sort((x, y) => y[1].size - x[1].size)
    .slice(0, topN)
    .map(([gram, ks]) => ({ gram, chapters: [...ks].sort(sortKeys) }))
}

// 解析立项目标字数：兼容 10000 / "10000字" / "10万" 三种写法
const parseTargetWords = (v) => {
  if (v === undefined || v === null) return 0
  const s = String(v)
  if (/万/.test(s)) {
    const n = parseFloat(s.replace(/[^\d.]/g, ''))
    return Number.isFinite(n) ? Math.round(n * 10000) : 0
  }
  const n = parseInt(s.replace(/[^\d]/g, ''), 10)
  return Number.isFinite(n) ? n : 0
}

// 结构健康：已写字数/章节 vs 立项目标/卷计划，偏差 >30% 给漂移治理选项
function StructureHealth({ projectId, data, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState(null)
  const [error, setError] = useState(null)

  const chapters = data?.chapters ?? {}
  const totalWords = Object.values(chapters).reduce(
    (n, c) => n + (c?.scenes ?? []).reduce((m, s) => m + (s?.text ?? '').length, 0), 0,
  )
  const writtenChapters = Object.keys(chapters).length
  const targetWords = parseTargetWords(data?.concept?.target_words)
  const plannedChapters = (data?.volume_plans ?? []).reduce((n, v) => n + (v?.chapter_count || 0), 0)
  const budget = data?.word_budget?.per_chapter || 0
  if (!targetWords || writtenChapters === 0) return null
  const drift = (totalWords - targetWords) / targetWords

  const raiseTarget = async () => {
    const input = window.prompt('新的立项目标字数', String(targetWords))
    if (input === null) return
    const n = parseTargetWords(input)
    if (!n) { setError('未识别到有效数字'); return }
    setBusy(true)
    setError(null)
    try {
      await api.productsUpdate(projectId, 'concept', { ...(data.concept ?? {}), target_words: n })
      setNote(`立项目标已改为 ${n.toLocaleString()} 字`)
      onChanged?.()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  const compressChapters = async () => {
    const remaining = Math.max(1, (plannedChapters || writtenChapters + 1) - writtenChapters)
    const suggested = Math.max(500, Math.round((targetWords - totalWords) / remaining / 100) * 100)
    const input = window.prompt(
      `后续每章目标字数（剩余约 ${remaining} 章；当前${budget ? `自定义 ${budget}` : '按题材默认'}）`,
      String(budget || suggested),
    )
    if (input === null) return
    const n = parseInt(input.replace(/[^\d]/g, ''), 10) || 0
    setBusy(true)
    setError(null)
    try {
      const r = await api.updateWordBudget(projectId, n)
      setNote(n > 0 ? `后续章节目标已设为 ${n} 字/章` : '字数覆盖已清除，回退题材默认')
      onChanged?.()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <div>
      <p className="text-sm font-semibold text-primary mb-2">📐 结构健康</p>
      <div className="rounded border border-border p-3 text-xs space-y-1">
        <p>
          已写 <span className="font-medium text-foreground">{totalWords.toLocaleString()}</span> 字 ·
          {' '}{writtenChapters} 章
          {plannedChapters > 0 && <> / 计划 {plannedChapters} 章</>}
          {' '}· 立项目标 {targetWords.toLocaleString()} 字
          {budget > 0 && <span className="text-muted">（后续章节自定义 {budget} 字/章）</span>}
        </p>
        {Math.abs(drift) > 0.3 ? (
          <div className="rounded border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/10 p-2 space-y-1.5">
            <p className="text-amber-700 dark:text-amber-300 font-medium">
              {drift > 0 ? '超出' : '低于'}立项目标 {Math.round(Math.abs(drift) * 100)}%——建议二选一对齐，避免结构失控
            </p>
            <div className="flex flex-wrap gap-2">
              <button className="btn-ghost text-xs" disabled={busy} onClick={raiseTarget}>改立项目标</button>
              <button className="btn-ghost text-xs" disabled={busy} onClick={compressChapters}>设定后续章节字数</button>
            </div>
          </div>
        ) : (
          <p className="text-muted">字数与目标偏差 {Math.round(Math.abs(drift) * 100)}%，结构正常。</p>
        )}
        {note && <p className="text-green-600 dark:text-green-400">{note}</p>}
        {error && <p className="text-red-600">{error}</p>}
      </div>
    </div>
  )
}

// 伏笔与道具：把正典事实层（事件账本/道具卡/已埋伏笔）变成可扫读的页面
export default function CanonPanel({ data, onChanged }) {
  const [openCh, setOpenCh] = useState(null)
  const ledger = data?.event_ledger ?? {}
  const props = data?.prop_registry ?? {}
  const packets = data?.writer_packets ?? {}

  const chapterKeys = useMemo(
    () => Object.keys(ledger).sort(sortKeys),
    [ledger],
  )
  const patterns = useMemo(() => repetitionPatterns(ledger), [ledger])
  const foreshadow = useMemo(() => {
    const out = []
    for (const [key, pk] of Object.entries(packets)) {
      for (const f of pk?.foreshadow ?? []) {
        const desc = typeof f === 'string' ? f : f?.desc
        if (desc) out.push({ key, kind: typeof f === 'object' ? f.kind : '', desc })
      }
    }
    return out.sort((a, b) => sortKeys(a.key, b.key))
  }, [packets])

  const empty = chapterKeys.length === 0 && Object.keys(props).length === 0 && foreshadow.length === 0

  if (empty) {
    return (
      <div className="text-sm text-muted space-y-2">
        <p>还没有正典事实。章节生成并接受后，AI 会自动抽取：</p>
        <ul className="list-disc pl-5 space-y-1 text-xs">
          <li>道具卡——每件关键道具的既定事实与出现章节，正文不得与之矛盾</li>
          <li>事件账本——每章 3-6 条关键事件，写手会据此避免重复同类桥段</li>
          <li>已埋伏笔——章节规划里登记的伏笔，方便对照回收</li>
        </ul>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* 结构健康：字数/章数漂移治理 */}
      <StructureHealth projectId={projectId} data={data} onChanged={onChanged} />

      {/* 重复桥段警示 */}
      <div>
        <p className="text-sm font-semibold text-primary mb-2">⚠️ 重复桥段警示</p>
        {patterns.length === 0 ? (
          <p className="text-xs text-muted">暂未发现跨章重复的事件模式（出现于 3 章以上才会提示）。</p>
        ) : (
          <div className="space-y-1.5">
            {patterns.map((p) => (
              <div key={p.gram} className="rounded border border-amber-200 bg-amber-50 dark:border-amber-900/40 dark:bg-amber-900/10 px-3 py-2 text-xs">
                <span className="font-medium text-amber-700 dark:text-amber-300">「{p.gram}」相关事件</span>
                <span className="text-muted"> 出现在 {p.chapters.length} 章：{p.chapters.map(fmtKey).join('、')}</span>
              </div>
            ))}
            <p className="text-xs text-muted pt-1">同类桥段堆叠是网文最容易踩的坑；点右上「全局规划」问一句"哪里有重复"可以让 AI 给出具体改法。</p>
          </div>
        )}
      </div>

      {/* 道具登记卡 */}
      <div>
        <p className="text-sm font-semibold text-primary mb-2">🎒 道具登记卡（{Object.keys(props).length}）</p>
        {Object.keys(props).length === 0 ? (
          <p className="text-xs text-muted">暂无道具登记。</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {Object.entries(props).map(([name, p]) => (
              <div key={name} className="rounded border border-border p-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{name}</span>
                  <span className="text-xs text-muted whitespace-nowrap">
                    {fmtKey(p.first_ch)} → {fmtKey(p.last_ch)}
                  </span>
                </div>
                <ul className="text-xs text-muted mt-1 space-y-0.5 list-disc pl-4">
                  {(p.facts ?? []).map((f, i) => <li key={i}>{f}</li>)}
                </ul>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 事件账本 */}
      <div>
        <p className="text-sm font-semibold text-primary mb-2">📜 事件账本（{chapterKeys.length} 章）</p>
        {chapterKeys.length === 0 ? (
          <p className="text-xs text-muted">暂无事件记录。</p>
        ) : (
          <div className="space-y-1.5">
            {chapterKeys.map((key) => (
              <details key={key} open={openCh === key} onToggle={(e) => e.target.open && setOpenCh(key)}>
                <summary className="text-xs cursor-pointer select-none text-muted hover:text-foreground">
                  {fmtKey(key)} · {(ledger[key] ?? []).length} 条事件
                </summary>
                <ul className="text-sm mt-1 space-y-0.5 list-disc pl-5">
                  {(ledger[key] ?? []).map((ev, i) => <li key={i}>{ev}</li>)}
                </ul>
              </details>
            ))}
          </div>
        )}
      </div>

      {/* 已埋伏笔 */}
      <div>
        <p className="text-sm font-semibold text-primary mb-2">🧵 已埋伏笔（{foreshadow.length}）</p>
        {foreshadow.length === 0 ? (
          <p className="text-xs text-muted">章节规划中还没有登记伏笔。</p>
        ) : (
          <ul className="text-sm space-y-1">
            {foreshadow.map((f, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-xs text-muted whitespace-nowrap pt-0.5">{fmtKey(f.key)}{f.kind ? ` · ${f.kind}` : ''}</span>
                <span className="text-sm">{f.desc}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
