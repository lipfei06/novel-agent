const NAV = [
  { id: 'projects', label: '我的小说', icon: '📚' },
  { id: 'library', label: '写作基础库', icon: '✍️' },
]

export default function Sidebar({ view, onNavigate }) {
  return (
    <aside className="w-52 shrink-0 border-r border-border bg-card flex flex-col">
      <div className="h-16 flex items-center px-5 border-b border-border">
        <span className="text-sm font-semibold tracking-wide">novel-agent</span>
      </div>
      <nav className="p-2 space-y-1">
        {NAV.map((item) => (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            className={`w-full flex items-center gap-3 rounded px-3 py-2 text-sm transition ${
              view === item.id
                ? 'bg-black/5 text-foreground font-medium dark:bg-white/10'
                : 'text-muted hover:bg-black/[0.03] hover:text-foreground dark:hover:bg-white/[0.06]'
            }`}
          >
            <span className="text-base leading-none">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>
      <div className="mt-auto p-4 border-t border-border">
        <p className="text-xs text-muted">多 Agent 小说写作系统</p>
      </div>
    </aside>
  )
}
