#!/usr/bin/env python3
"""
mini_weixin_bridge.py
=====================
最简版：微信 ClawBot 接入本地 Agent 的实现原理演示。

核心流程（三步走）：
  第一步：扫码登录，拿到 bot_token
  第二步：长轮询 getUpdates，等待用户发消息
  第三步：把消息交给 Agent 处理，把回复发回微信

用法：
  python mini_weixin_bridge.py           # 首次运行，会自动触发扫码登录
  python mini_weixin_bridge.py --login   # 强制重新扫码登录

依赖安装：
  pip install qrcode[pil]   # 在终端打印二维码
"""

import json
import os
import sys
import time
import base64
import struct
import secrets
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Any, Optional

# ── 导入本地 Agent ──
# agent.py 和本文件在同一目录，直接 import 即可
from agent import agent_loop, SYSTEM as AGENT_SYSTEM


# =============================================================================
# 一、配置（改这里就行）
# =============================================================================

# 微信后端网关地址（一般不需要改）
BASE_URL = "https://ilinkai.weixin.qq.com"

# token 和游标存储的本地文件路径
TOKEN_FILE  = Path(__file__).parent / ".weixin_token.json"   # 保存登录后的 token
BUF_FILE    = Path(__file__).parent / ".weixin_buf.txt"      # 保存消息游标（断点续传）


# =============================================================================
# 二、工具函数
# =============================================================================

def _url(path: str) -> str:
    """拼接完整 URL，确保 BASE_URL 末尾有斜杠。"""
    base = BASE_URL.rstrip("/") + "/"
    return base + path


def _headers(token: Optional[str] = None) -> dict:
    """
    构造每次请求都需要带的 HTTP 请求头。
    - AuthorizationType: 固定值，告诉服务端这是 bot token 认证
    - Authorization: 登录拿到的 token，未登录时不带
    - X-WECHAT-UIN: 随机数的 base64，模拟微信客户端标识
    """
    h = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        # 随机 uint32 → 十进制字符串 → base64，与原版协议一致
        "X-WECHAT-UIN": base64.b64encode(
            str(struct.unpack(">I", os.urandom(4))[0]).encode()
        ).decode(),
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _post(path: str, body: dict, token: Optional[str] = None, timeout: int = 15) -> dict:
    """
    发送 POST JSON 请求，返回解析后的响应字典。
    所有与微信后端的通信都走这个函数。
    """
    data = json.dumps(body).encode("utf-8")
    req  = urllib.request.Request(
        _url(path),
        data    = data,
        headers = {**_headers(token), "Content-Length": str(len(data))},
        method  = "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} /{path}: {e.read().decode(errors='replace')}") from e


def _get(url: str, timeout: int = 35) -> dict:
    """发送 GET 请求，用于登录流程中拉取二维码和轮询扫码状态。"""
    req = urllib.request.Request(url, headers={"iLink-App-ClientVersion": "1"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} GET {url}: {e.read().decode(errors='replace')}") from e


# =============================================================================
# 三、第一步：扫码登录
# =============================================================================

def login() -> dict:
    """
    扫码登录，返回 {"token": "...", "account_id": "...", "base_url": "..."}

    登录流程：
      1. 调用 get_bot_qrcode  → 拿到二维码内容
      2. 在终端打印二维码，等用户用微信扫描
      3. 循环调用 get_qrcode_status → 等待状态变成 "confirmed"
      4. 从响应里取出 bot_token，登录完成
    """

    # ── 第 1 步：拉取二维码 ──
    base = BASE_URL.rstrip("/") + "/"
    url  = base + "ilink/bot/get_bot_qrcode?bot_type=3"
    print("[登录] 正在获取二维码...", flush=True)
    qr_resp     = _get(url)
    qrcode_raw  = qr_resp.get("qrcode", "")          # 服务端的二维码标识（用于轮询）
    qrcode_url  = qr_resp.get("qrcode_img_content", "")  # 可扫描的二维码链接

    if not qrcode_raw:
        raise RuntimeError(f"获取二维码失败: {qr_resp}")

    # ── 第 2 步：在终端打印二维码 ──
    print("\n请用微信扫描下方二维码：\n", flush=True)
    try:
        import qrcode                          # pip install qrcode[pil]
        qr = qrcode.QRCode(version=1, border=1)
        qr.add_data(qrcode_url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)            # 用 ASCII 字符在终端渲染，尺寸最小
    except ImportError:
        # 没有安装 qrcode 库时，直接打印链接，用浏览器打开也能扫
        print(f"  {qrcode_url}\n", flush=True)

    # ── 第 3 步：轮询等待扫码 ──
    print("等待扫码...", flush=True)
    poll_url = base + f"ilink/bot/get_qrcode_status?qrcode={urllib.parse.quote(qrcode_raw)}"
    deadline = time.time() + 480    # 最多等 8 分钟

    while time.time() < deadline:
        try:
            s = _get(poll_url)
        except Exception as e:
            print(f"  [轮询错误] {e}", flush=True)
            time.sleep(2)
            continue

        status = s.get("status", "wait")

        if status == "wait":
            # 还没扫，继续等，打一个点表示进度
            sys.stdout.write(".")
            sys.stdout.flush()

        elif status == "scaned":
            # 已经扫了，等用户在微信里点确认
            print("\n👀 已扫码，请在微信中点击确认...", flush=True)

        elif status == "confirmed":
            # ✅ 用户点了确认，登录成功！
            token      = s.get("bot_token", "")
            account_id = s.get("ilink_bot_id", "")
            # 账号 ID 规范化：把 @ 和 . 换成 -，例如 abc@im.wechat → abc-im-wechat
            account_id = account_id.replace("@", "-").replace(".", "-")
            real_base  = s.get("baseurl") or BASE_URL
            print(f"\n✅ 登录成功！account_id={account_id}", flush=True)
            return {"token": token, "account_id": account_id, "base_url": real_base}

        elif status == "expired":
            raise RuntimeError("二维码已过期，请重新运行程序。")

        time.sleep(1)

    raise RuntimeError("登录超时（8分钟），请重试。")


def load_token() -> Optional[dict]:
    """从本地文件读取上次保存的 token（如果有的话）。"""
    if TOKEN_FILE.exists():
        try:
            return json.loads(TOKEN_FILE.read_text("utf-8"))
        except Exception:
            pass
    return None


def save_token(data: dict) -> None:
    """把 token 信息保存到本地文件，下次启动不用重新扫码。"""
    TOKEN_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
    TOKEN_FILE.chmod(0o600)    # 仅当前用户可读，保护 token 安全


# =============================================================================
# 四、第二步：长轮询接收消息（getUpdates）
# =============================================================================

def getUpdates(token: str, buf: str = "", timeout: int = 35) -> dict:
    """
    长轮询接口：向服务端发请求，服务端"憋着"不回，直到有新消息或超时才返回。

    参数：
      buf     - 上次返回的游标，传给服务端表示"从这里继续"，首次传空字符串
      timeout - 等待秒数，服务端通常在 35 秒内有消息就返回，无消息就返回空

    返回值里的重要字段：
      msgs            - 新消息列表（可能为空）
      get_updates_buf - 新游标，下次请求要带上它
    """
    try:
        return _post(
            "ilink/bot/getupdates",
            body    = {"get_updates_buf": buf, "base_info": {"channel_version": "mini-bridge-1.0"}},
            token   = token,
            timeout = timeout + 5,    # 客户端超时比服务端多 5 秒，避免误判
        )
    except (TimeoutError, OSError) as e:
        if "timed out" in str(e).lower():
            # 超时是正常现象，不是错误，直接返回空结果，继续下一轮
            return {"ret": 0, "msgs": [], "get_updates_buf": buf}
        raise


# =============================================================================
# 五、第三步：发送回复（sendMessage）
# =============================================================================

def send_message(token: str, to_user_id: str, text: str, context_token: str) -> None:
    """
    向微信用户发送一条文本消息。

    重要：context_token 必须原样从收到的消息里取出并回传，
    服务端靠它把回复和对话关联起来。没有它，消息发不出去。
    """
    _post(
        "ilink/bot/sendmessage",
        token = token,
        body  = {
            "msg": {
                "from_user_id" : "",                            # bot 发送，留空
                "to_user_id"   : to_user_id,                   # 发给谁
                "client_id"    : f"mini-{secrets.token_hex(8)}",  # 本次消息的唯一ID，防重复
                "message_type" : 2,                            # 2 = BOT 消息
                "message_state": 2,                            # 2 = 消息已完成（非流式）
                "item_list"    : [{"type": 1, "text_item": {"text": text}}],  # type=1 是文本
                "context_token": context_token,                # ← 关键！必须带上
            },
            "base_info": {"channel_version": "mini-bridge-1.0"},
        },
    )


# =============================================================================
# 六、Agent 会话管理
# =============================================================================

# 每个微信用户维护一份独立的对话历史，key 是用户 ID
_sessions: dict[str, list] = {}


def askAgent(user_id: str, user_text: str) -> str:
    """
    把用户的消息交给 Agent 处理，返回 Agent 的回复文本。

    - 每个用户有自己独立的对话历史（_sessions），实现多用户隔离
    - agent_loop 会循环调用大模型直到得到最终回复
    """
    # 第一次对话时，初始化这个用户的历史，带上系统提示词
    if user_id not in _sessions:
        _sessions[user_id] = [{"role": "system", "content": AGENT_SYSTEM}]

    # 把用户这条消息追加到历史
    _sessions[user_id].append({"role": "user", "content": user_text})

    # 交给 Agent 处理，agent_loop 会直接修改传入的列表（追加 assistant 回复）
    try:
        reply = agent_loop(_sessions[user_id])
        return reply or "(无回复)"
    except Exception as e:
        return f"[Agent 出错] {e}"


# =============================================================================
# 七、长轮询监听循环
# =============================================================================

def run_monitor(token: str) -> None:
    """
    长轮询监听循环：持续等待微信消息，收到后交给 Agent 处理并回复。

    整个循环做三件事：
      1. 调 getUpdates() 等消息（服务端"憋着"，有消息才返回）
      2. 遍历返回的消息列表，提取文本，交给 ask_agent() 得到回复
      3. 调 sendMessage() 把回复发回给用户

    参数：
      token - 登录后拿到的 bot_token，每次请求都要带上
    """

    # ── 加载上次的消息游标（断点续传）──
    # 游标让服务端知道"从哪条消息开始"，程序重启后不会漏掉中途的消息
    buf = BUF_FILE.read_text("utf-8").strip() if BUF_FILE.exists() else ""
    if buf:
        print("[✓] 从上次游标恢复", flush=True)
    print("[监听中] 等待微信消息...\n", flush=True)

    fail_count = 0    # 连续失败计数，失败太多就暂停一会儿

    while True:

        # ── 第一件事：等消息 ──
        try:
            resp = getUpdates(token, buf=buf)
        except Exception as e:
            # 网络抖动或服务端异常，失败超过 3 次才真正暂停
            fail_count += 1
            print(f"[错误] getUpdates 失败 ({fail_count}/3): {e}", flush=True)
            if fail_count >= 3:
                print("[退避] 连续失败 3 次，等待 30 秒后重试...", flush=True)
                fail_count = 0
                time.sleep(30)
            else:
                time.sleep(2)
            continue

        fail_count = 0

        # 服务端返回了业务错误码，打印后稍等再重试
        if resp.get("ret", 0) != 0 or resp.get("errcode", 0) != 0:
            print(f"[服务端错误] {resp}", flush=True)
            time.sleep(2)
            continue

        # 更新并持久化游标（下次重启可以从这里接着取消息）
        new_buf = resp.get("get_updates_buf", "")
        if new_buf:
            buf = new_buf
            BUF_FILE.write_text(buf, "utf-8")

        # ── 第二件事 + 第三件事：处理每条消息，回复用户 ──
        for msg in resp.get("msgs") or []:

            # 只处理用户发来的消息（message_type=1），忽略 bot 自己发的（=2）
            if msg.get("message_type") != 1:
                continue

            from_user = msg.get("from_user_id", "")
            ctx_token = msg.get("context_token", "")  # ← 必须原样回传给 send_message

            # 从消息的 item_list 里找 type=1（文本）的那一项
            text = ""
            for item in msg.get("item_list") or []:
                if item.get("type") == 1:               # type=1 是文本消息
                    text = (item.get("text_item") or {}).get("text", "")
                    break

            if not text.strip():
                continue    # 非文本消息（图片、语音等）暂不处理

            print(f"[收到] {from_user}: {text[:60]}", flush=True)

            # 第二件事：把文本交给 Agent，得到回复
            reply = askAgent(from_user, text)
            print(f"[回复] {reply[:60]}", flush=True)

            # 第三件事：把 Agent 的回复发回微信
            try:
                send_message(token, from_user, reply, ctx_token)
                print("✅ 已发送", flush=True)
            except Exception as e:
                print(f"❌ 发送失败: {e}", flush=True)


# =============================================================================
# 八、主入口
# =============================================================================

def main():
    """
    程序入口，只做两件事：
      1. 登录（拿 token）
      2. 调 run_monitor() 开始监听
    """

    # 优先读取上次保存的 token，有就跳过扫码
    creds = load_token()

    if not creds:
        print("=== 微信扫码登录 ===", flush=True)
        creds = login()
        save_token(creds)
        print(f"[✓] token 已保存到 {TOKEN_FILE}", flush=True)

    token      = creds["token"]
    account_id = creds["account_id"]
    base_url   = creds.get("base_url", BASE_URL)
    print(f"\n[启动] account={account_id}  base={base_url}", flush=True)

    # 登录完成，进入消息监听循环
    run_monitor(token)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[退出] 再见！", flush=True)