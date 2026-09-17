import ThemeToggle from './ThemeToggle.jsx'

const TITLES = { projects: '我的小说', library: '写作基础库', workspace: '写作工作台', chapter: '章节', newChapter: '新建章节' }

export default function Topbar({ view, selectedId, onBack }) {
  return (
    <header className="h-16 shrink-0 border-b border-border bg-card/60 backdrop-blur flex items-center px-6 gap-3">
      {view === 'workspace' && (
        <button className="btn-ghost text-xs" onClick={onBack}>
          ← 返回
        </button>
      )}
      <h1 className="text-base font-medium">{TITLES[view] ?? view}</h1>
      {selectedId && <span className="text-sm text-muted">/ {selectedId}</span>}
      <div className="ml-auto flex items-center gap-2">
        <ThemeToggle />
      </div>
    </header>
  )
}
