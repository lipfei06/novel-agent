import { useMemo, useState } from 'react'

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

// 伏笔与道具：把正典事实层（事件账本/道具卡/已埋伏笔）变成可扫读的页面
export default function CanonPanel({ data }) {
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
