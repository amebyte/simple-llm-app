from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator, Field
from typing import Optional, List
import re

app = FastAPI()

# CORS 配置：允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中建议设置为具体的前端域名
    allow_credentials=True,
    allow_methods=["*"],  # 允许的方法
    allow_headers=["*"],  # 允许的头部
)

@app.get("/")
def read_root():
    return {"message": "我是 Cobyte，欢迎添加 v：icobyte，学习 AI 全栈。"}

@app.get("/items/{id}")
def read_item(
    id: int, 
    limit: int = 10,         # 默认值
    q: Optional[str] = None, # 可选参数
    short: bool = False,     # 默认值
    tags: List[str] = []     # 列表参数
):
    item = {"id": id, "limit": limit, "tags": tags}
    if q:
        item.update({"q": q})
    if not short:
        item.update({"desc": "长说明"})
    return item

# 请求体（Request Body）
class UserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str
    email: str
    @validator('username')
    def username_alphanumeric(cls, v):
        if not re.match('^[a-zA-Z0-9_]+$', v):
            raise ValueError('只能包含字母、数字和下划线')
        return v
    
    @validator('email')
    def email_valid(cls, v):
        if '@' not in v:
            raise ValueError('无效的邮箱地址')
        return v.lower()  # 转换为小写
    
    @validator('password')
    def password_strong(cls, v):
        if len(v) < 6:
            raise ValueError('密码至少6位')
        return v
# 响应模型（Response Model）
class UserResponse(BaseModel):
    username: str
    email: str

@app.post("/user/", response_model=UserResponse)
async def create_user(user: UserRequest):
    # 密码会被过滤，不会出现在响应中
    return user

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.1.1.1", port=9527)