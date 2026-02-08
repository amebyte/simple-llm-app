import os
from typing import Generator
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 加载环境变量
load_dotenv()

class LLMApp:
    def __init__(self, model_name="deepseek-chat", temperature=0.7):
        """
        初始化 LLM 应用程序
        """
        # 检查 DeepSeek API 密钥
        if not os.getenv("DEEPSEEK_API_KEY"):
            raise ValueError("请在 .env 文件中设置 DEEPSEEK_API_KEY 环境变量")
        
        # 初始化配置
        self.model_name = model_name
        self.temperature = temperature
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = "https://api.deepseek.com/v1"
        
        # 初始化非流式 LLM (用于普通任务)
        self.llm = self._create_llm(streaming=False)
        
        # 初始化流式 LLM (用于流式对话)
        self.streaming_llm = self._create_llm(streaming=True)
        
        # 输出解析器
        self.output_parser = StrOutputParser()
        
        # 初始化对话链
        self._setup_chains()
    
    def _create_llm(self, streaming: bool = False):
        """创建 LLM 实例"""
        return ChatOpenAI(
            model_name=self.model_name,
            temperature=self.temperature,
            api_key=self.api_key,
            base_url=self.base_url,
            streaming=streaming
        )
    
    def _setup_chains(self):
        """设置处理链"""
        # 带上下文的对话 Prompt
        conversation_prompt = PromptTemplate(
            input_variables=["chat_history", "user_input"],
            template="""你是一个有用的 AI 助手。请根据对话历史回答用户的问题。
            
            对话历史：
            {chat_history}
            
            用户：{user_input}
            助手："""
        )
        # 注意：这里我们只定义 prompt，具体执行时再组合
        self.conversation_prompt = conversation_prompt

    def format_history(self, history_list) -> str:
        """格式化聊天历史"""
        if not history_list:
            return "无历史对话"
        
        formatted = []
        for msg in history_list:
            # 兼容 Pydantic model 或 dict
            if isinstance(msg, dict):
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
            else:
                role = getattr(msg, 'role', 'unknown')
                content = getattr(msg, 'content', '')
                
            formatted.append(f"{role}: {content}")
        
        return "\n".join(formatted[-10:])  # 只保留最近 10 条

    def stream_chat(self, user_input: str, chat_history: list) -> Generator[str, None, None]:
        """流式对话生成器"""
        try:
            history_text = self.format_history(chat_history)
            
            # 构建链：Prompt | StreamingLLM | OutputParser
            chain = self.conversation_prompt | self.streaming_llm | self.output_parser
            
            # 执行流式生成
            for chunk in chain.stream({
                "chat_history": history_text,
                "user_input": user_input
            }):
                yield chunk
                
        except Exception as e:
            yield f"Error: {str(e)}"