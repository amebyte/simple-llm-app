import os
from dotenv import load_dotenv
# 加载环境变量 (读取 .env 中的 DEEPSEEK_API_KEY)
load_dotenv()
# 加载 OpenAI 库，从这里也可以看到 Python 的库加载顺序跟 JavaScript ES6 import 是不一样，反而有点像 requrie
from openai import OpenAI

# 初始化客户端
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"), # 身份验证凭证，确保你有权访问 API
    base_url="https://api.deepseek.com" # 将请求重定向到 DeepSeek 的服务器（而非 OpenAI）
)
# 构建聊天请求
response = client.chat.completions.create(
  model="deepseek-chat", # 指定模型版本
  temperature=0.5,
  messages=[   # 对话消息数组
      {"role": "user", "content": "你是谁？"}
  ]
)
# 打印结果
# print(response.choices[0].message.content.strip())
# 使用 model_dump_json 并指定缩进
print(response.model_dump_json(indent=2))