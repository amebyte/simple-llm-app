import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate,HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

# 1. 加载环境变量 (读取 .env 中的 DEEPSEEK_API_KEY)
load_dotenv()

# 2. 创建组件
# 相对于上面的使用 OpenAI 的接口，现在经过 LangChain 封装后确实简洁了很多
llm = ChatOpenAI(
    model="deepseek-chat", 
    temperature=0.7,
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)

# 创建了一个人类角色的提示模板，`from_template` 方法允许我们通过一个字符串模板来定义提示，默认是人类角色。
# prompt = ChatPromptTemplate.from_template("{question}")
human = HumanMessagePromptTemplate.from_template("{question}")
prompt = ChatPromptTemplate.from_messages([human])

# 创建解析器
parser = StrOutputParser()
# 将AI响应转换为字符串，因为大模型返回的数据一般包含很多数据，我们只需要返回的字符串

# 3. 组合链 (LCEL 语法) Python LangChain 常见的链式调用
chain = prompt | llm | parser
# 等价于：输入 → 模板填充 → AI处理 → 结果解析

# 4. 执行
result = chain.invoke({"question": "你是谁？"})
# 内部执行：填充"你是谁？" → 调用API → 解析响应 → 返回字符串

# 5. 打印结果
print(result)