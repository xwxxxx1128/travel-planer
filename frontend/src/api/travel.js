import api from './index'

export const travelApi = {
  createPlan: (data) => api.post('/travel/plan', data),
  demoPlan: () => api.get('/travel/plan/demo'),
  listPois: () => api.get('/knowledge/pois'),
  listHotels: () => api.get('/knowledge/hotels'),
  listRestaurants: () => api.get('/knowledge/restaurants'),
  listReviews: () => api.get('/knowledge/reviews'),
  crawlReviews: (data) => api.post('/crawl/reviews', data),
  graphStatus: () => api.get('/graph/status'),
  sendChat: (data) => api.post('/chat', data),
  // 节点级 SSE 流式对话：用原生 fetch 读取 text/event-stream，逐块回调
  sendChatStream: (data, onEvent) => {
    const token = localStorage.getItem('token')
    const body = JSON.stringify(data)
    const headers = { 'Content-Type': 'application/json' }
    if (token) headers.Authorization = `Bearer ${token}`
    return fetch('/api/chat/stream', {
      method: 'POST',
      headers,
      body,
    }).then(async (resp) => {
      if (!resp.ok || !resp.body) {
        let msg = `请求失败（${resp.status}）`
        try {
          const j = await resp.json()
          msg = j.detail || msg
        } catch (e) { /* ignore */ }
        throw new Error(msg)
      }
      const reader = resp.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''
      // 持续读取直到流结束；每块可能含多个 SSE 帧（以空行分隔）
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const frames = buffer.split('\n\n')
        buffer = frames.pop() || '' // 保留未完成的半帧
        for (const frame of frames) {
          const line = frame.trim()
          if (!line.startsWith('data:')) continue
          const payload = line.slice(5).trim()
          if (!payload) continue
          try {
            onEvent(JSON.parse(payload))
          } catch (e) {
            // 单帧解析失败不影响后续
          }
        }
      }
      // 处理流末尾残留的半帧（极少出现）
      const tail = buffer.trim()
      if (tail.startsWith('data:')) {
        const payload = tail.slice(5).trim()
        if (payload) {
          try { onEvent(JSON.parse(payload)) } catch (e) { /* ignore */ }
        }
      }
    })
  },
  flightAction: (data) => api.post('/chat/flight-action', data),
  // 中断点恢复：把用户对敏感操作的“批准/拒绝”回传给后端 Checkpointer
  resumeChat: (data) => api.post('/chat/resume', data),
  pendingChat: (session_id) => api.get('/chat/pending', { params: { session_id } }),
  getHistory: (session_id) => api.get('/chat/history/' + encodeURIComponent(session_id)),
}
