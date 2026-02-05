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

prompt = ChatPromptTemplate.from_template("{question}")
parser = StrOutputParser()

# 3. 组合链 (LCEL 语法)
# chain = prompt | llm | parser

# 第一步：prompt 处理
messages = prompt.invoke({"question": "你是谁？"})
# messages = [HumanMessage(content="你是谁？")]

# 第二步：llm 处理
response = llm.invoke(messages)
# response = AIMessage(content="我是DeepSeek...")

# 第三步：parser 处理
result = parser.invoke(response)

# 4. 执行
# result = chain.invoke({"question": "你是谁？"})
print(result)