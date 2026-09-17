import { useEffect, useRef, useState } from 'react'

const MAX_LOGS = 200 // 日志上限，防止长会话内存/渲染膨胀
const RECONNECT_MAX = 6 // 异常断线重连上限；服务端正常 eof 关流不重连

// 用 fetch + ReadableStream 读 SSE（EventSource 不支持 POST/自定义头）
export function useSse(url, enabled = true, onEvent = () => {}) {
  const [logs, setLogs] = useState([])
  const [connected, setConnected] = useState(false)
  const controllerRef = useRef(null)

  useEffect(() => {
    if (!enabled || !url) return
    const controller = new AbortController()
    controllerRef.current = controller

    const connect = async () => {
      let retry = 0
      while (!controller.signal.aborted) {
        let sawEof = false
        try {
          const res = await fetch(url, { signal: controller.signal })
          if (!res.ok || !res.body) throw new Error(`SSE ${res.status}`)
          retry = 0
          setConnected(true)
          const reader = res.body.getReader()
          const decoder = new TextDecoder()
          let buffer = ''
          while (true) {
            const { done, value } = await reader.read()
            if (done) break
            buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
            const frames = buffer.split('\n\n')
            buffer = frames.pop() || ''
            for (const chunk of frames) {
              let event = 'message'
              for (const line of chunk.split('\n')) {
                if (line.startsWith('event: ')) {
                  event = line.slice(7).trim()
                } else if (line.startsWith('data: ')) {
                  let data
                  try {
                    data = JSON.parse(line.slice(6))
                  } catch {
                    continue // 跳过坏帧，不让整条流挂掉
                  }
                  if (event === 'log') {
                    setLogs((l) => [...l.slice(-(MAX_LOGS - 1)), data.message])
                  }
                  if (event === 'eof') sawEof = true
                  onEvent(event, data)
                }
              }
            }
          }
          // 服务端推完 eof 正常关流：不重连
          if (sawEof) {
            setConnected(false)
            return
          }
          throw new Error('SSE 连接中断（未收到 eof）')
        } catch (e) {
          if (e.name === 'AbortError') return
          setConnected(false)
          retry += 1
          if (retry > RECONNECT_MAX) return
          // 指数退避重连：1s, 2s, 4s...上限 15s
          const delay = Math.min(1000 * 2 ** (retry - 1), 15000)
          await new Promise((r) => setTimeout(r, delay))
        }
      }
    }

    connect()
    return () => controller.abort()
  }, [url, enabled, onEvent])

  return { logs, connected }
}
