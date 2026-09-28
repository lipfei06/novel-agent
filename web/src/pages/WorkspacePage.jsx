import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client.js'
import { useSse } from '../hooks/useSse.js'
import ConfirmView from '../components/ConfirmView.jsx'
import ProductsPanel from '../components/ProductsPanel.jsx'
import VolumeManager from '../components/VolumeManager.jsx'
import ChatPanel from '../components/ChatPanel.jsx'

export default function WorkspacePage({ projectId, onOpenChapter, onNewChapter }) {
  const [meta, setMeta] = useState(null)
  const [idea, setIdea] = useState('')
  const [view, setView] = useState(null)
  const [started, setStarted] = useState(false)
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [products, setProducts] = useState(null)
  const [exporting, setExporting] = useState(false)
  const [files, setFiles] = useState([])
  const [cost, setCost] = useState(null)
  const [auto, setAuto] = useState(false)
  const inFlight = useRef(false)

  const setupDone = !!(products?.outline)
  // 章节级确认（4b/5/6）不在工作台展示：归属到「新建章节」页对应卷处理
  const isChapterStage = !!view && ['stage4r', 'stage4b', 'stage5', 'stage6'].includes(view.stage)
  // 自动继续：这些环节依次自动接受，进入章节环节（stage4b）或终审时暂停
  const AUTO_STAGES = ['stage0', 'stage1', 'stage2', 'stage3', 'stage4a']
  const sseUrl = `/api/projects/${projectId}/events`

  const reloadProducts = useCallback(() => {
    api.products(projectId).then(setProducts).catch(() => {})
    api.projectCost(projectId).then(setCost).catch(() => {})
  }, [projectId])

  const onSseEvent = useCallback(
    (event, data) => {
      if (!started) return
      if (event === 'confirmation') {
        setView(data)
        if (data.done) setDone(true)
      }
      if (event === 'eof' && data.done) setDone(true)
    },
    [started],
  )
  const { logs } = useSse(sseUrl, started, onSseEvent)

  useEffect(() => {
    api.getProject(projectId).then(setMeta).catch((e) => setError(e.message))
    api
      .projectState(projectId)
      .then((s) => {
        if (!s.started) return
        setStarted(true)
        if (s.done) setDone(true)
        else setView({ done: false, stage: s.stage, stage_label: s.stage_label, payload: s.payload })
      })
      .catch(() => {})
    reloadProducts()
    api.finalFiles(projectId).then((d) => setFiles(d.files)).catch(() => {})
  }, [projectId, reloadProducts])

  const start = async () => {
    setBusy(true)
    setError(null)
    try {
      const v = await api.startRun(projectId, idea)
      setStarted(true)
      setView(v)
      if (v.done) setDone(true)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const submit = async ({ action, data }) => {
    if (inFlight.current) return
    inFlight.current = true
    setBusy(true)
    setError(null)
    try {
      let v = await api.confirm(projectId, action, data)
      setView(v)
      reloadProducts()
      // 自动继续：设定环节依次自动接受，直到章节环节或结束
      while (auto && v && !v.done && AUTO_STAGES.includes(v.stage)) {
        v = await api.confirm(projectId, 'accept')
        setView(v)
        reloadProducts()
      }
      if (v.done) {
        setDone(true)
        api.finalFiles(projectId).then((d) => setFiles(d.files)).catch(() => {})
      }
    } catch (e) {
      setError(e.message)
    } finally {
      inFlight.current = false
      setBusy(false)
    }
  }

  const doExport = async () => {
    setExporting(true)
    setError(null)
    try {
      const r = await api.exportNow(projectId)
      setFiles(r.files.map((p) => ({ name: p.split(/[\\/]/).pop(), path: p })))
    } catch (e) {
      setError(e.message)
    } finally {
      setExporting(false)
    }
  }

  if (error && !meta && !products) return <div className="p-8 text-red-600 text-sm">{error}</div>

  return (
    <div className="max-w-7xl mx-auto px-8 py-8">
      {/* 标题区 */}
      <div className="flex items-end justify-between mb-6">
        <div>
          <h2 className="text-2xl font-semibold">{meta?.title ?? '…'}</h2>
          <p className="text-sm text-muted mt-1">
            {({ webnovel: '网文长篇', literary: '传统长篇', short_story: '短篇/中篇' })[meta?.genre] ?? meta?.genre}
          </p>
        </div>
        <div className="flex items-center gap-4">
          {cost && (
            <div className="text-right">
              <p className="text-sm font-medium">≈ ${cost.est_cost_usd}</p>
              <p className="text-xs text-muted">
                {cost.calls} 次调用 · {cost.total_tokens.toLocaleString()} tokens
              </p>
            </div>
          )}
          {done || (products?.chapters && Object.keys(products.chapters).length > 0) ? (
            <button className="btn-primary" disabled={exporting} onClick={doExport}>
              {exporting ? '导出中…' : '导出小说'}
            </button>
          ) : null}
        </div>
      </div>

      {error && <div className="mb-4 rounded border border-red-200 bg-red-50 dark:bg-red-900/20 dark:text-red-300 text-red-700 px-4 py-3 text-sm">{error}</div>}

      {/* 确认点：有 stage 才渲染确认卡（章节级确认归「新建章节」页）；空确认（断点待恢复/环节间瞬态）显示恢复条 */}
      {view && !view.done && view.stage && !isChapterStage && (
        <div className="mb-6">
          <ConfirmView view={view} onSubmit={submit} busy={busy} auto={auto} onAutoChange={setAuto} />
        </div>
      )}
      {view && !view.done && !view.stage && (
        <div className="mb-6 card p-4 flex items-center gap-3 flex-wrap">
          <span className="text-sm">创作流程停在半程（上次生成未走完确认）。</span>
          <button className="btn-primary text-xs" disabled={busy} onClick={() => submit({ action: 'accept' })}>
            {busy ? '恢复中…' : '▶ 恢复并继续'}
          </button>
          <span className="text-xs text-muted">点击后从断点继续执行生成流程</span>
        </div>
      )}

      {/* 创作区（宽屏双栏）：左=作品设定与全局顾问，右=分卷与章节管理 */}
      {setupDone ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          <div className="space-y-6 min-w-0">
            <ProductsPanel projectId={projectId} />
          </div>
          <div className="space-y-6 min-w-0">
            <VolumeManager
              projectId={projectId}
              products={products}
              onProductsChange={reloadProducts}
              onOpenChapter={onOpenChapter}
              onNewChapter={onNewChapter}
            />
          </div>
        </div>
      ) : (
        <SetupArea
          projectId={projectId}
          view={view}
          started={started}
          idea={idea}
          setIdea={setIdea}
          busy={busy}
          start={start}
          submit={submit}
          logs={logs}
        />
      )}
    </div>
  )
}

function SetupArea({ projectId, view, started, idea, setIdea, busy, start, submit, logs }) {
  return (
    <div className="space-y-4">
      {!view && (
        <ChatPanel
          projectId={projectId}
          context="concept"
          title="选题助手 · 先和 AI 聊出你满意的立意"
          target="concept"
          onApply={async (p) => {
            if (p && (p.logline || p.title_idea)) setIdea(p.logline || p.title_idea)
          }}
          placeholder="和 AI 聊你的小说构思…"
        />
      )}
      {!view && (
        <div className="card p-6">
          <p className="text-sm font-medium mb-1">第一步 · 建立作品设定</p>
          <p className="text-sm text-muted mb-3">从一句话立意开始，系统将依次生成 选题 → 世界观 → 人物 → 总纲（一次性创建，之后可随时修改）。</p>
          <textarea className="input h-24" value={idea} onChange={(e) => setIdea(e.target.value)} placeholder="例：真假千金身份错位后重新定义家人" />
          <button className="btn-primary mt-4" disabled={busy || !idea.trim()} onClick={start}>
            {busy ? '生成中…' : '开始生成设定'}
          </button>
        </div>
      )}
      <Logs logs={logs} />
    </div>
  )
}

function Logs({ logs }) {
  if (logs.length === 0) return null
  return (
    <div className="card p-3 max-h-40 overflow-auto">
      <p className="text-xs text-muted mb-2">运行日志</p>
      {logs.map((m, i) => (
        <p key={i} className="text-xs text-muted font-mono">{m}</p>
      ))}
    </div>
  )
}
