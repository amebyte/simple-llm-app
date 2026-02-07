import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

# 1. 加载环境变量 (读取 .env 中的 DEEPSEEK_API_KEY)
load_dotenv()

# 2. 创建组件
# 适配 DeepSeek 的配置
llm = ChatOpenAI(
    model="deepseek-chat", 
    temperature=0.7,
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)

# 创建了一个聊天提示模板，`from_template` 方法允许我们通过一个字符串模板来定义提示。
prompt = ChatPromptTemplate.from_template("{question}")
# 模板等待一个名为 "question" 的变量

# 创建解析器：定义输出格式
parser = StrOutputParser()
# 将AI响应转换为字符串

# 3. 组合链 (LCEL 语法) Python LangChain 常见的链式调用
chain = prompt | llm | parser
# 等价于：输入 → 模板填充 → AI处理 → 结果解析

# 4. 执行
result = chain.invoke({"question": "你是谁？"})
# 内部执行：填充"你是谁？" → 调用API → 解析响应 → 返回字符串

# 5. 打印结果
print(result)