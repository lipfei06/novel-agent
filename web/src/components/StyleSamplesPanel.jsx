import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

const MAX_SELECTED = 3
const MAX_CHARS = 800

// 风格样本：从「仿写库」勾选条目（≤3）注入写手；也可粘贴新样本直接入库（AI 提取风格要点）
export default function StyleSamplesPanel({ projectId, samples, onChanged }) {
  const [library, setLibrary] = useState([]) // 仿写库条目
  const [selectedIds, setSelectedIds] = useState([]) // 当前选中（库条目 id）
  const [pasteOpen, setPasteOpen] = useState(false)
  const [pasteForm, setPasteForm] = useState({ name: '', text: '' })
  const [extracting, setExtracting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)

  const loadLibrary = () =>
    api.libraryList('style').then((d) => setLibrary(d.entries || [])).catch(() => {})

  useEffect(() => {
    loadLibrary()
    // 已选快照 → 按库条目 id 恢复勾选（私有旧样本无 source_id，显示为已选但不可回库）
    setSelectedIds((samples ?? []).map((s) => s.source_id).filter(Boolean))
  }, [samples])

  const toggle = (id) => {
    setSaved(false)
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id)
      if (prev.length >= MAX_SELECTED) {
        setError(`最多选 ${MAX_SELECTED} 段（控制写手 token 预算）`)
        return prev
      }
      setError(null)
      return [...prev, id]
    })
  }

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const picked = library.filter((e) => selectedIds.includes(e.id))
      await api.updateStyleSamples(
        projectId,
        picked.map((e) => ({
          id: e.id, source_id: e.id, name: e.name, text: e.text, digest: e.digest || '',
        })),
      )
      setSaved(true)
      onChanged?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const extract = async () => {
    if (!pasteForm.text.trim()) {
      setError('粘贴内容不能为空')
      return
    }
    setExtracting(true)
    setError(null)
    try {
      const r = await api.extractStyleSample(pasteForm.text.trim(), pasteForm.name.trim())
      setPasteForm({ name: '', text: '' })
      setPasteOpen(false)
      await loadLibrary()
      setSelectedIds((prev) => (prev.length >= MAX_SELECTED ? prev : [...prev, r.entry.id]))
    } catch (e) {
      setError(e.message)
    } finally {
      setExtracting(false)
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted leading-5">
        从仿写库勾选 1-3 段样本，写手会模仿其叙事口吻、句式节奏与用词密度（情节仍由章节规划决定）。
        保存后对本项目所有章节生成生效；样本管理（改名/删除）在「写作基础库 → 仿写库」。
      </p>

      {library.length === 0 ? (
        <div className="rounded border border-dashed border-border p-6 text-center text-xs text-muted">
          仿写库还是空的——粘贴一段你认可的文字开始（示例条目会在首次保存时自动入库）。
        </div>
      ) : (
        <div className="space-y-1.5">
          {library.map((e) => {
            const on = selectedIds.includes(e.id)
            return (
              <button
                key={e.id}
                type="button"
                onClick={() => toggle(e.id)}
                className={`w-full text-left rounded border p-3 transition ${
                  on ? 'border-primary bg-primary/5' : 'border-border hover:bg-black/[0.03] dark:hover:bg-white/[0.06]'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium">{on ? '☑' : '☐'} {e.name}</span>
                  <span className="text-xs text-muted whitespace-nowrap">{(e.text ?? '').length} 字</span>
                </div>
                {e.digest && <p className="text-xs text-muted mt-1 leading-5 line-clamp-2">要点：{e.digest}</p>}
              </button>
            )
          })}
        </div>
      )}

      {pasteOpen ? (
        <div className="rounded border border-border p-3 space-y-2">
          <input
            className="input text-sm"
            placeholder="样本名称（可留空自动命名）"
            value={pasteForm.name}
            onChange={(e) => setPasteForm({ ...pasteForm, name: e.target.value })}
          />
          <textarea
            className="input text-sm leading-6"
            rows={5}
            placeholder={`粘贴一段样例文本（≤${MAX_CHARS} 字），保存时 AI 会提取风格要点`}
            value={pasteForm.text}
            onChange={(e) => setPasteForm({ ...pasteForm, text: e.target.value })}
          />
          <div className="flex justify-end gap-2">
            <button className="btn-ghost text-xs" onClick={() => setPasteOpen(false)}>取消</button>
            <button className="btn-primary text-xs" disabled={extracting} onClick={extract}>
              {extracting ? '提取中…' : '✨ 提取要点并入库'}
            </button>
          </div>
        </div>
      ) : (
        <button className="btn-ghost text-xs" onClick={() => { setPasteOpen(true); setSaved(false) }}>
          ＋ 粘贴新样本入库
        </button>
      )}

      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex items-center justify-end gap-2">
        {saved && <span className="text-xs text-green-600 dark:text-green-400">已保存 ✓</span>}
        <button className="btn-primary text-xs" disabled={saving} onClick={save}>
          {saving ? '保存中…' : `保存选区（${selectedIds.length}/${MAX_SELECTED}）`}
        </button>
      </div>
    </div>
  )
}
