import type { ChatRequest, SSEEvent } from '../types/chat'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export class ChatAPI {
  /**
   * 流式对话接口
   */
  static streamChat(
    payload: ChatRequest,
    onToken: (token: string) => void,
    onComplete: (fullResponse: string) => void,
    onError: (error: string) => void
  ): () => void {
    // 使用 fetch API 配合 ReadableStream 来处理 POST 请求的流式响应
    // 因为标准的 EventSource 不支持 POST 请求
    const controller = new AbortController()
    
    const fetchStream = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
          signal: controller.signal,
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const reader = response.body?.getReader()
        const decoder = new TextDecoder()
        
        if (!reader) throw new Error('Response body is null')

        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          
          const chunk = decoder.decode(value, { stream: true })
          buffer += chunk
          
          // 处理 buffer 中的每一行
          const lines = buffer.split('\n\n')
          buffer = lines.pop() || '' // 保留最后一个可能不完整的块
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const jsonStr = line.slice(6)
              try {
                const data: SSEEvent = JSON.parse(jsonStr)
                
                switch (data.type) {
                  case 'start':
                    break
                  case 'token':
                    if (data.content) onToken(data.content)
                    break
                  case 'end':
                    if (data.full_response) onComplete(data.full_response)
                    return // 正常结束
                  case 'error':
                    onError(data.message || 'Unknown error')
                    return
                }
              } catch (e) {
                console.error('JSON parse error:', e)
              }
            }
          }
        }
      } catch (error: any) {
        if (error.name === 'AbortError') return
        onError(error.message)
      }
    }

    fetchStream()

    // 返回取消函数
    return () => controller.abort()
  }

  /**
   * 健康检查
   */
  static async healthCheck() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/health`)
      return await response.json()
    } catch (error) {
      console.error('Health check failed', error)
      return { status: 'error' }
    }
  }
}