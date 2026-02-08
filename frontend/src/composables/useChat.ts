import { ref, nextTick } from 'vue'
import type { Message } from '../types/chat'
import { ChatAPI } from '../api/chat'

export function useChat() {
  const messages = ref<Message[]>([])
  const isLoading = ref(false)
  const currentStreamingMessage = ref<Message | null>(null)
  
  // 用于取消当前的请求
  let cancelStream: (() => void) | null = null

  /**
   * 滚动到底部
   */
  const scrollToBottom = () => {
    nextTick(() => {
      const container = document.querySelector('.message-list')
      if (container) {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: 'smooth'
        })
      }
    })
  }

  /**
   * 发送消息
   */
  const sendMessage = async (content: string) => {
    if (!content.trim() || isLoading.value) return

    // 1. 添加用户消息
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: content.trim(),
      timestamp: Date.now()
    }
    messages.value.push(userMessage)
    
    // 准备发送给后端的历史记录（去掉刚加的这一条，因为后端只要之前的）
    // 或者你可以根据设计决定是否包含当前条，通常 API 设计是：新消息 + 历史
    // 我们的后端设计是：message + chat_history
    const historyPayload = messages.value.slice(0, -1).map(m => ({
      role: m.role,
      content: m.content
    }))

    // 2. 创建 AI 消息占位符
    const aiMessage: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      streaming: true
    }
    messages.value.push(aiMessage)
    currentStreamingMessage.value = aiMessage
    isLoading.value = true
    
    scrollToBottom()

    // 3. 调用流式 API
    cancelStream = ChatAPI.streamChat(
      {
        message: content.trim(),
        chat_history: historyPayload
      },
      // onToken
      (token) => {
        if (currentStreamingMessage.value) {
          currentStreamingMessage.value.content += token
          scrollToBottom()
        }
      },
      // onComplete
      (fullResponse) => {
        if (currentStreamingMessage.value) {
          // 确保内容完整
          if (currentStreamingMessage.value.content !== fullResponse && fullResponse) {
             currentStreamingMessage.value.content = fullResponse
          }
          currentStreamingMessage.value.streaming = false
        }
        currentStreamingMessage.value = null
        isLoading.value = false
        cancelStream = null
        scrollToBottom()
      },
      // onError
      (error) => {
        if (currentStreamingMessage.value) {
          currentStreamingMessage.value.content += `\n[错误: ${error}]`
          currentStreamingMessage.value.streaming = false
        }
        currentStreamingMessage.value = null
        isLoading.value = false
        cancelStream = null
        scrollToBottom()
      }
    )
  }

  /**
   * 清空历史
   */
  const clearHistory = () => {
    if (cancelStream) {
      cancelStream()
      cancelStream = null
    }
    messages.value = []
    isLoading.value = false
    currentStreamingMessage.value = null
  }

  return {
    messages,
    isLoading,
    sendMessage,
    clearHistory
  }
}