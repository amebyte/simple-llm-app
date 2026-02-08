export interface Message {
    id: string
    role: 'user' | 'assistant'
    content: string
    timestamp: number
    streaming?: boolean  // 是否正在流式生成
  }
  
  export interface ChatRequest {
    message: string
    chat_history: Array<{
      role: string
      content: string
    }>
  }
  
  export interface SSEEvent {
    type: 'start' | 'token' | 'end' | 'error'
    content?: string
    full_response?: string
    message?: string
  }