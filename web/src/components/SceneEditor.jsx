import { useState } from 'react'
import { diffLines } from '../lib/diff.js'

// 场景块卡片 + 定点修改（只改选中场景，其余不动）
export default function SceneEditor({ chapter, onEdit }) {
  const [editing, setEditing] = useState(null) // scene id
  const [instruction, setInstruction] = useState('')
  const [busy, setBusy] = useState(false)
  const [diff, setDiff] = useState(null)

  const oldText = (id) => chapter.scenes.find((s) => s.id === id)?.text ?? ''

  const submit = async (scene) => {
    if (!instruction.trim()) return
    setBusy(true)
    const before = oldText(scene.id)
    try {
      const next = await onEdit({ scene_id: scene.id, instruction: instruction.trim() })
      const after = next.scenes.find((s) => s.id === scene.id)?.text ?? ''
      setDiff({ before, after, lines: diffLines(before, after) })
      setEditing(null)
      setInstruction('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted">
          第{chapter.volume}卷 第{chapter.chapter}章 · {chapter.title}
        </h3>
        <span className="text-xs text-muted">{chapter.scenes.length} 个场景</span>
      </div>

      {chapter.scenes.map((scene, idx) => (
        <div key={scene.id} className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-primary">{scene.heading}</span>
            <button className="btn-ghost text-xs" onClick={() => setEditing(editing === scene.id ? null : scene.id)}>
              {editing === scene.id ? '收起' : '定点修改'}
            </button>
          </div>
          <p className="text-sm leading-7 whitespace-pre-wrap">{scene.text}</p>

          {editing === scene.id && (
            <div className="mt-3 space-y-2">
              <input
                className="input"
                placeholder="修改指令，如：氛围改缓和些"
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
              />
              <div className="flex gap-2 justify-end">
                <button className="btn-primary text-xs" disabled={busy || !instruction.trim()} onClick={() => submit(scene)}>
                  {busy ? '修改中…' : '提交修改'}
                </button>
              </div>
            </div>
          )}
        </div>
      ))}

      {diff && (
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium">修改 diff</span>
            <button className="btn-ghost text-xs" onClick={() => setDiff(null)}>
              关闭
            </button>
          </div>
          <pre className="text-xs leading-6 overflow-x-auto">
            {diff.lines.map((l, i) => (
              <div
                key={i}
                className={
                  l.tag === 'add'
                    ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                    : l.tag === 'del'
                      ? 'bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-300'
                      : ''
                }
              >
                {l.tag === 'add' ? '+ ' : l.tag === 'del' ? '- ' : '  '}
                {l.text}
              </div>
            ))}
          </pre>
        </div>
      )}
    </div>
  )
}
