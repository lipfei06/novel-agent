// API 客户端：与后端 /api 联通（vite 代理到 8000）
const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = await res.text()
    try {
      const body = JSON.parse(detail)
      if (body.detail) detail = body.detail
    } catch {
      /* 非 JSON 响应 */
    }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  health: () => request('/health'),
  profiles: () => request('/profiles'),
  listProjects: () => request('/projects'),
  getProject: (id) => request(`/projects/${id}`),
  createProject: (body) =>
    request('/projects', { method: 'POST', body: JSON.stringify(body) }),
  deleteProject: (id) => request(`/projects/${id}`, { method: 'DELETE' }),
  startRun: (id, idea) =>
    request(`/projects/${id}/start`, { method: 'POST', body: JSON.stringify({ idea }) }),
  confirm: (id, action, data) =>
    request(`/projects/${id}/confirm`, {
      method: 'POST',
      body: JSON.stringify({ action, data }),
    }),
  projectState: (id) => request(`/projects/${id}/state`),
  products: (id) => request(`/projects/${id}/products`),
  projectRelations: (id) => request(`/projects/${id}/relations`),
  chatHistory: (id, context) => request(`/projects/${id}/chat?context=${encodeURIComponent(context)}`),
  chatSend: (id, context, message) =>
    request(`/projects/${id}/chat`, { method: 'POST', body: JSON.stringify({ context, message }) }),
  chatPropose: (id, context, target) =>
    request(`/projects/${id}/chat/propose`, { method: 'POST', body: JSON.stringify({ context, target }) }),
  chatReset: (id, context) =>
    request(`/projects/${id}/chat/reset?context=${encodeURIComponent(context)}`, { method: 'POST' }),
  productsUpdate: (id, field, value) =>
    request(`/projects/${id}/products`, {
      method: 'PUT',
      body: JSON.stringify({ field, value }),
    }),
  listVolumes: (id) => request(`/projects/${id}/volumes`),
  createVolume: (id, body) =>
    request(`/projects/${id}/volumes`, { method: 'POST', body: JSON.stringify(body) }),
  updateVolume: (id, vol, fields) =>
    request(`/projects/${id}/volumes/${vol}`, { method: 'PUT', body: JSON.stringify(fields) }),
  createChapter: (id, vol, form) =>
    request(`/projects/${id}/volumes/${vol}/chapters`, { method: 'POST', body: JSON.stringify(form) }),
  acceptChapter: (id, vol, ch, body) =>
    request(`/projects/${id}/chapters/${vol}/${ch}/accept`, {
      method: 'POST',
      ...(body ? { body: JSON.stringify({ chapter: body }) } : {}),
    }),
  discardChapter: (id, vol, ch) =>
    request(`/projects/${id}/chapters/${vol}/${ch}`, { method: 'DELETE' }),
  deleteSavedChapter: (id, vol, ch) =>
    request(`/projects/${id}/volumes/${vol}/chapters/${ch}`, { method: 'DELETE' }),
  updateChapter: (id, vol, ch, chapter) =>
    request(`/projects/${id}/chapters/${vol}/${ch}`, {
      method: 'PUT',
      body: JSON.stringify({ chapter }),
    }),
  projectCost: (id) => request(`/projects/${id}/cost`),
  chapterVersions: (id, vol, ch) =>
    request(`/projects/${id}/chapters/${vol}/${ch}/versions`),
  chapterVersion: (id, vol, ch, vid) =>
    request(`/projects/${id}/chapters/${vol}/${ch}/versions/${vid}`),
  restoreChapterVersion: (id, vol, ch, vid) =>
    request(`/projects/${id}/chapters/${vol}/${ch}/versions/${vid}/restore`, { method: 'POST' }),
  volumeVersions: (id, vol) => request(`/projects/${id}/volumes/${vol}/versions`),
  pendingSceneRewrite: (id, vol, ch, sceneId, instruction) =>
    request(`/projects/${id}/chapters/${vol}/${ch}/pending-scene-rewrite`, {
      method: 'POST',
      body: JSON.stringify({ scene_id: sceneId, instruction }),
    }),
  updateStyleSamples: (id, samples) =>
    request(`/projects/${id}/style-samples`, { method: 'PUT', body: JSON.stringify({ samples }) }),
  setProjectTechniques: (id, ids) =>
    request(`/projects/${id}/techniques`, { method: 'PUT', body: JSON.stringify({ ids }) }),
  generateBlueprint: (id) => request(`/projects/${id}/blueprint/generate`, { method: 'POST' }),
  startChapterGenerateTask: (id, vol, ch, body) =>
    request(`/projects/${id}/volumes/${vol}/chapters/${ch}/generate-task`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  startRegenerateTask: (id, vol, ch, instruction = '', chatContext = '') => {
    const params = new URLSearchParams()
    if (instruction) params.set('instruction', instruction)
    if (chatContext) params.set('chat_context', chatContext)
    const qs = params.toString()
    return request(`/projects/${id}/volumes/${vol}/chapters/${ch}/regenerate-task${qs ? `?${qs}` : ''}`, {
      method: 'POST',
    })
  },
  taskEventsUrl: (taskId) => `/api/tasks/${taskId}/events`,
  rewriteScene: (id, vol, ch, scene, instruction) =>
    request(`/projects/${id}/chapters/${vol}/${ch}/scenes/${scene}/rewrite`, {
      method: 'POST',
      body: JSON.stringify({ instruction }),
    }),
  saveCharacterTemplate: (id, cid) =>
    request(`/projects/${id}/characters/${cid}/template`, { method: 'POST' }),
  projectCost: (id) => request(`/projects/${id}/cost`),
  exportNow: (id) => request(`/projects/${id}/export`, { method: 'POST' }),
  finalFiles: (id) => request(`/projects/${id}/final`),
  libraryList: (kind) => request(`/library/${kind}`),
  libraryAdd: (kind, entry) =>
    request(`/library/${kind}`, { method: 'POST', body: JSON.stringify(entry) }),
  libraryUpdate: (kind, id, fields) =>
    request(`/library/${kind}/${id}`, { method: 'PUT', body: JSON.stringify(fields) }),
  libraryDelete: (kind, id) => request(`/library/${kind}/${id}`, { method: 'DELETE' }),
  populateMemes: (topic, count) =>
    request('/library/memes/populate', { method: 'POST', body: JSON.stringify({ topic, count }) }),
  extractMemes: (text) =>
    request('/library/memes/extract', { method: 'POST', body: JSON.stringify({ text }) }),
}
