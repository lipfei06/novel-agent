import { useCallback, useEffect, useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import Topbar from './components/Topbar.jsx'
import ProjectsPage from './pages/ProjectsPage.jsx'
import LibraryPage from './pages/LibraryPage.jsx'
import WorkspacePage from './pages/WorkspacePage.jsx'
import ChapterPage from './pages/ChapterPage.jsx'
import NewChapterPage from './pages/NewChapterPage.jsx'

// Hash 路由：URL 可深链、刷新不丢位置、浏览器后退可用（无需额外依赖）
// #/                        → 项目列表
// #/library                 → 写作基础库
// #/p/{id}                  → 工作台
// #/p/{id}/chapter/{v}/{c}  → 章节页
// #/p/{id}/new/{v}          → 新建章节页
function parseHash() {
  const parts = (window.location.hash.replace(/^#/, '') || '/').split('/').filter(Boolean)
  if (parts[0] === 'library') return { view: 'library' }
  if (parts[0] === 'p' && parts[1]) {
    const pid = parts[1]
    if (parts[2] === 'chapter' && parts[3] && parts[4]) {
      return { view: 'chapter', projectId: pid, vol: Number(parts[3]), ch: Number(parts[4]) }
    }
    if (parts[2] === 'new' && parts[3]) {
      return { view: 'newChapter', projectId: pid, vol: Number(parts[3]) }
    }
    return { view: 'workspace', projectId: pid }
  }
  return { view: 'projects' }
}

export default function App() {
  const [route, setRoute] = useState(parseHash)

  useEffect(() => {
    const onHash = () => setRoute(parseHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const go = useCallback((hash) => {
    if (window.location.hash === `#${hash}`) return
    window.location.hash = hash
  }, [])

  const navigate = useCallback(
    (target) => {
      if (target === 'library') go('/library')
      else go('/')
    },
    [go],
  )
  const openWorkspace = useCallback((id) => go(`/p/${id}`), [go])
  const openChapter = useCallback((t) => go(`/p/${t.projectId}/chapter/${t.vol}/${t.ch}`), [go])
  const openNewChapter = useCallback((t) => go(`/p/${t.projectId}/new/${t.vol}`), [go])
  const backToWorkspace = useCallback(() => go(`/p/${route.projectId}`), [go, route.projectId])

  if (route.view === 'chapter') {
    return (
      <div className="flex h-screen">
        <Sidebar view="workspace" onNavigate={navigate} />
        <div className="flex-1 flex flex-col min-w-0">
          <Topbar view="chapter" selectedId={route.projectId} onBack={backToWorkspace} />
          <main className="flex-1 overflow-auto">
            <ChapterPage
              projectId={route.projectId}
              vol={route.vol}
              ch={route.ch}
              onBack={backToWorkspace}
              onNavigate={(v, c) => go(`/p/${route.projectId}/chapter/${v}/${c}`)}
            />
          </main>
        </div>
      </div>
    )
  }

  if (route.view === 'newChapter') {
    return (
      <div className="flex h-screen">
        <Sidebar view="workspace" onNavigate={navigate} />
        <div className="flex-1 flex flex-col min-w-0">
          <Topbar view="newChapter" selectedId={route.projectId} onBack={backToWorkspace} />
          <main className="flex-1 overflow-auto">
            <NewChapterPage
              projectId={route.projectId}
              vol={route.vol}
              onBack={backToWorkspace}
            />
          </main>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen">
      <Sidebar view={route.view} onNavigate={navigate} />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar view={route.view} selectedId={route.projectId} onBack={() => go('/')} />
        <main className="flex-1 overflow-auto">
          {route.view === 'projects' && <ProjectsPage selectedId={route.projectId} onSelect={openWorkspace} />}
          {route.view === 'library' && <LibraryPage />}
          {route.view === 'workspace' && route.projectId && (
            <WorkspacePage
              key={route.projectId}
              projectId={route.projectId}
              onOpenChapter={openChapter}
              onNewChapter={openNewChapter}
            />
          )}
        </main>
      </div>
    </div>
  )
}
