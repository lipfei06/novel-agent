import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

const GENRES = [
  { id: 'webnovel', label: '网文长篇' },
  { id: 'literary', label: '传统长篇' },
  { id: 'short_story', label: '短篇/中篇' },
]

export default function ProjectsPage({ selectedId, onSelect }) {
  const [projects, setProjects] = useState([])
  const [showDialog, setShowDialog] = useState(false)
  const [error, setError] = useState(null)

  const load = () =>
    api.listProjects().then((d) => setProjects(d.projects)).catch((e) => setError(e.message))

  useEffect(() => {
    load()
  }, [])

  return (
    <div className="max-w-5xl mx-auto px-8 py-10">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-semibold">我的小说</h2>
          <p className="text-sm text-muted mt-1">多本作品并行创作，数据彼此隔离</p>
        </div>
        <button className="btn-primary" onClick={() => setShowDialog(true)}>
          新建项目
        </button>
      </div>

      {error && (
        <div className="mb-6 rounded border border-red-200 bg-red-50 text-red-700 px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {projects.length === 0 ? (
        <div className="card p-12 text-center text-muted">
          <p className="text-5xl mb-4">📖</p>
          <p className="text-sm">还没有项目，点击右上角「新建项目」开始创作</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((p) => (
            <div
              key={p.project_id}
              role="button"
              tabIndex={0}
              onClick={() => onSelect(p.project_id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') onSelect(p.project_id)
              }}
              className={`card p-5 text-left cursor-pointer transition hover:shadow-hover ${
                selectedId === p.project_id ? 'ring-2 ring-primary/30' : ''
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="min-w-0">
                  <h3 className="font-medium truncate">{p.title}</h3>
                  <p className="text-xs text-muted mt-1">
                    {GENRES.find((g) => g.id === p.genre)?.label ?? p.genre}
                  </p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    if (confirm(`删除项目 ${p.title}？数据将一并删除`)) {
                      api.deleteProject(p.project_id).then(load)
                    }
                  }}
                  className="text-muted hover:text-red-600 text-xs"
                >
                  删除
                </button>
              </div>
              <div className="mt-4">
                <div className="flex items-center justify-between text-xs text-muted">
                  <span>{p.stage ?? p.current_stage}</span>
                  <span>{p.chapters ?? 0} 章 · {p.volumes ?? 0} 卷</span>
                </div>
                <div className="mt-1 h-1.5 rounded-full bg-black/5 overflow-hidden dark:bg-white/10">
                  <div className="h-full bg-primary/50 rounded-full" style={{ width: '20%' }} />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showDialog && (
        <NewProjectDialog
          onClose={() => setShowDialog(false)}
          onCreated={() => {
            setShowDialog(false)
            load()
          }}
        />
      )}
    </div>
  )
}

function NewProjectDialog({ onClose, onCreated }) {
  const [title, setTitle] = useState('')
  const [genre, setGenre] = useState('webnovel')
  const [projectId, setProjectId] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async () => {
    if (!title.trim()) return
    setBusy(true)
    setErr(null)
    try {
      await api.createProject({
        title: title.trim(),
        genre,
        project_id: projectId.trim() || null,
      })
      onCreated()
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onClose}>
      <div className="card w-96 p-6" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-base font-semibold mb-4">新建项目</h3>
        <label className="block text-xs text-muted mb-1">书名</label>
        <input className="input mb-3" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="请输入书名" />
        <label className="block text-xs text-muted mb-1">题材</label>
        <select className="input mb-3" value={genre} onChange={(e) => setGenre(e.target.value)}>
          {GENRES.map((g) => (
            <option key={g.id} value={g.id}>
              {g.label}
            </option>
          ))}
        </select>
        <label className="block text-xs text-muted mb-1">项目 ID（可选）</label>
        <input
          className="input mb-4"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
          placeholder="留空自动生成"
        />
        {err && <p className="text-xs text-red-600 mb-3">{err}</p>}
        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose}>
            取消
          </button>
          <button className="btn-primary" disabled={busy || !title.trim()} onClick={submit}>
            {busy ? '创建中…' : '创建'}
          </button>
        </div>
      </div>
    </div>
  )
}
