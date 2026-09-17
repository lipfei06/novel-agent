import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

// 关系图谱可视化：人物环形布局，边按关系类型着色，随章节推进显示关系演变
const KIND_COLOR = {
  敌人: '#dc2626',
  盟友: '#16a34a',
  师徒: '#2563eb',
  情侣: '#db2777',
  亲人: '#d97706',
  仇敌: '#7c3aed',
  互动: '#78716c',
}
const STATUS_LABEL = { active: '在世', dead: '已故', absent: '退场', transformed: '蜕变' }

export default function RelationGraph({ projectId }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.projectRelations(projectId).then(setData).catch((e) => setError(e.message))
  }, [projectId])

  if (error) return <p className="text-sm text-muted">关系图谱加载失败：{error}</p>
  if (!data) return <p className="text-sm text-muted">加载中…</p>

  const nodes = data.nodes ?? []
  const edges = data.edges ?? []
  if (nodes.length === 0) return <p className="text-sm text-muted">暂无人物关系数据。</p>

  // 环形布局：按章节+名字排序，围绕中心分布
  const ordered = [...nodes].sort((a, b) => (a.name ?? '').localeCompare(b.name ?? ''))
  const W = 520
  const H = 400
  const CX = W / 2
  const CY = H / 2
  const R = Math.min(CX, CY) - 46
  const pos = {}
  ordered.forEach((n, i) => {
    const angle = (i / ordered.length) * 2 * Math.PI - Math.PI / 2
    pos[n.id] = { x: CX + R * Math.cos(angle), y: CY + R * Math.sin(angle) }
  })

  const nameById = Object.fromEntries(ordered.map((n) => [n.id, n.name]))

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
        {edges.map((e, i) => {
          const a = pos[e.a]
          const b = pos[e.b]
          if (!a || !b) return null
          const color = KIND_COLOR[e.kind] ?? '#78716c'
          return (
            <g key={i}>
              <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={color} strokeWidth="1.2" opacity="0.7" />
              <text
                x={(a.x + b.x) / 2}
                y={(a.y + b.y) / 2 - 4}
                textAnchor="middle"
                fontSize="9"
                fill={color}
              >
                {e.kind}·第{e.chapter}章
              </text>
            </g>
          )
        })}
        {ordered.map((n) => (
          <g key={n.id}>
            <circle
              cx={pos[n.id].x}
              cy={pos[n.id].y}
              r={n.tier === 'main' ? 22 : n.tier === 'supporting' ? 16 : 10}
              fill={n.status === 'dead' ? '#f3f4f6' : n.tier === 'main' ? '#57534e' : '#d6d3d1'}
              stroke={n.status === 'dead' ? '#9ca3af' : '#78716c'}
              strokeWidth="1.5"
            />
            <text x={pos[n.id].x} y={pos[n.id].y + 4} textAnchor="middle" fontSize="11" fontWeight="600" fill="#18181b">
              {n.name}
            </text>
            <text x={pos[n.id].x} y={pos[n.id].y + 34} textAnchor="middle" fontSize="9" fill={n.status === 'dead' ? '#9ca3af' : '#78716c'}>
              {STATUS_LABEL[n.status] ?? n.status}
            </text>
          </g>
        ))}
      </svg>
      <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted">
        {Object.entries(KIND_COLOR).map(([k, c]) => (
          <span key={k} className="flex items-center gap-1">
            <span className="w-3 h-0.5 rounded" style={{ background: c }} />
            {k}
          </span>
        ))}
      </div>
    </div>
  )
}
