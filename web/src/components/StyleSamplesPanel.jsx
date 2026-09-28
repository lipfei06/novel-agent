import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

const MAX_SAMPLES = 3
const MAX_CHARS = 800

// 作者风格样本：粘贴自己认可的文本片段，注入写手 prompt 作 few-shot 风格锚点
export default function StyleSamplesPanel({ projectId, samples, onChanged }) {
  const [draft, setDraft] = useState([])
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    setDraft((samples ?? []).map((s) => ({ ...s })))
    setSaved(false)
  }, [samples])

  const update = (i, k, v) => setDraft(draft.map((s, j) => (j === i ? { ...s, [k]: v } : s)))
  const add = () => setDraft([...draft, { id: `st${Date.now().toString(36)}`, name: '', text: '' }])
  const remove = (i) => setDraft(draft.filter((_, j) => j !== i))

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      await api.updateStyleSamples(projectId, draft)
      setSaved(true)
      onChanged?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted leading-5">
        粘贴 1-3 段你认可的文字（自己写的、或喜欢的作家段落，每段 ≤{MAX_CHARS} 字）。
        写手会模仿其叙事口吻、句式节奏与用词密度——情节仍由章节规划决定，样本只管"像谁写的"。
      </p>
      {draft.length === 0 && (
        <div className="rounded border border-dashed border-border p-6 text-center text-xs text-muted">
          还没有风格样本。点击下方按钮添加第一段。
        </div>
      )}
      {draft.map((s, i) => {
        const over = (s.text ?? '').length > MAX_CHARS
        return (
          <div key={s.id ?? i} className="rounded border border-border p-3 space-y-2">
            <div className="flex items-center gap-2">
              <input
                className="input text-sm flex-1"
                placeholder={`样本名称（如：我的文风 / 余华节奏）`}
                value={s.name ?? ''}
                onChange={(e) => update(i, 'name', e.target.value)}
              />
              <span className={`text-xs whitespace-nowrap ${over ? 'text-red-600' : 'text-muted'}`}>
                {(s.text ?? '').length}/{MAX_CHARS}
              </span>
              <button className="btn-ghost text-xs" onClick={() => remove(i)}>删除</button>
            </div>
            <textarea
              className="input text-sm leading-6"
              rows={5}
              placeholder="粘贴一段样例文本……"
              value={s.text ?? ''}
              onChange={(e) => update(i, 'text', e.target.value)}
            />
          </div>
        )
      })}
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex items-center justify-between">
        <button className="btn-ghost text-xs" disabled={draft.length >= MAX_SAMPLES} onClick={add}>
          + 添加样本（{draft.length}/{MAX_SAMPLES}）
        </button>
        <div className="flex items-center gap-2">
          {saved && <span className="text-xs text-green-600 dark:text-green-400">已保存 ✓</span>}
          <button className="btn-primary text-xs" disabled={saving} onClick={save}>
            {saving ? '保存中…' : '保存样本'}
          </button>
        </div>
      </div>
    </div>
  )
}
