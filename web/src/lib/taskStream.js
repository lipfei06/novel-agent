// 订阅后台生成任务的 SSE 进度流；任务完成后 resolve(result)，失败 reject(Error)
export function runTaskWithProgress(taskId, onProgress) {
  return new Promise((resolve, reject) => {
    const es = new EventSource(`/api/tasks/${taskId}/events`)
    const cleanup = () => es.close()
    es.addEventListener('progress', (e) => {
      try {
        onProgress?.(JSON.parse(e.data))
      } catch {
        /* 忽略坏帧 */
      }
    })
    es.addEventListener('done', (e) => {
      cleanup()
      try {
        resolve(JSON.parse(e.data).result)
      } catch {
        resolve(null)
      }
    })
    es.addEventListener('error', (e) => {
      cleanup()
      let msg = '生成任务中断'
      try {
        msg = JSON.parse(e.data).message || msg
      } catch {
        /* EventSource 原生网络错误无 data */
      }
      reject(new Error(msg))
    })
  })
}
