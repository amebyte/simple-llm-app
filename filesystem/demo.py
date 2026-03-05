"""
最小 MVP 示例 - LLM 文件系统操作能力演示
展示如何将文件系统工具集成到 LLM 应用中
"""

import os
import asyncio
from langchain_openai import ChatOpenAI
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent
from dotenv import load_dotenv

# 导入精简的文件系统工具
from filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool

# 加载环境变量
load_dotenv()


def convert_tools_to_langchain(tools):
    """将自定义工具转换为 LangChain 工具格式"""
    langchain_tools = []
    
    for tool in tools:
        # 创建同步包装器
        def create_sync_wrapper(async_tool):
            def sync_execute(**kwargs):
                return asyncio.run(async_tool.execute(**kwargs))
            return sync_execute
        
        # 转换为 LangChain StructuredTool
        lc_tool = StructuredTool(
            name=tool.name,
            description=tool.description,
            args_schema=tool.parameters,
            func=create_sync_wrapper(tool)
        )
        langchain_tools.append(lc_tool)
    
    return langchain_tools


async def main():
    """主函数 - 演示文件系统工具的使用"""
    
    print("🚀 初始化 LLM Agent (DeepSeek + 文件系统工具)")
    print("=" * 60)
    
    # 1. 创建 LLM 实例
    # 支持 DEEPSEEK_API_KEY 或 OPENAI_API_KEY
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ 错误: 未找到 API Key")
        print("   请在 .env 文件中设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY")
        return
    
    llm = ChatOpenAI(
        model="deepseek-chat",
        temperature=0,
        api_key=api_key,
        base_url="https://api.deepseek.com/v1"
    )
    
    # 2. 初始化文件系统工具
    tools = [
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        ListDirTool()
    ]
    
    # 3. 转换为 LangChain 工具
    langchain_tools = convert_tools_to_langchain(tools)
    
    # 4. 创建 System Prompt
    system_message = """你是一个具备文件系统操作能力的 AI 助手。
你可以使用以下工具：
- read_file: 读取文件内容
- write_file: 写入文件
- edit_file: 编辑文件(替换文本)
- list_dir: 列出目录内容

请用中文回答用户的问题，并在需要时使用工具完成任务。"""
    
    # 5. 创建 Agent
    # 注意：create_agent 使用 system_prompt 参数(字符串)，不是 prompt(ChatPromptTemplate)
    agent_executor = create_agent(llm, langchain_tools, system_prompt=system_message)
    
    # 6. 测试用例
    test_cases = [
        "列出当前目录的文件",
        "读取 filesystem.py 文件的前 5 行",
        "创建一个新文件 test_output.txt，内容是 '这是一个测试文件'",
    ]
    
    for i, question in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"📝 测试 {i}: {question}")
        print(f"{'='*60}\n")
        
        # 使用新的 invoke 方式
        result = await agent_executor.ainvoke({"messages": [HumanMessage(content=question)]})
        
        # 获取最后一条消息（Agent 的回答）
        final_message = result["messages"][-1]
        print(f"\n✅ 回答:\n{final_message.content}\n")
    
    print("\n" + "="*60)
    print("🎉 MVP 演示完成！")


if __name__ == "__main__":
    asyncio.run(main())