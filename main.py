import json
import os
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect


# ============================================================
# 基础配置
# ============================================================

# 以后我们会在 Render 环境变量里设置这个 Token
# NapCat 和 Render 两边必须完全一致
ONEBOT_ACCESS_TOKEN = os.getenv("ONEBOT_ACCESS_TOKEN", "")


# ============================================================
# FastAPI
# ============================================================

app = FastAPI()


@app.get("/")
async def home():
    return {
        "status": "大冒险QQ服务器运行正常",
        "mode": "NapCat + OneBot11",
        "websocket": "/onebot/v11/ws"
    }


@app.get("/health")
async def health():
    return {
        "status": "ok"
    }


# ============================================================
# OneBot 工具
# ============================================================

def get_message_text(event: dict) -> str:
    """
    从 OneBot 消息事件中提取文字。
    NapCat 可能同时提供 raw_message 和 message。
    """

    raw_message = event.get("raw_message")

    if isinstance(raw_message, str) and raw_message:
        return raw_message.strip()

    message = event.get("message", [])

    if isinstance(message, str):
        return message.strip()

    texts = []

    if isinstance(message, list):
        for segment in message:
            if not isinstance(segment, dict):
                continue

            if segment.get("type") == "text":
                data = segment.get("data", {})
                text = data.get("text", "")

                if text:
                    texts.append(text)

    return "".join(texts).strip()


async def send_onebot_action(
    websocket: WebSocket,
    action: str,
    params: dict
):
    """
    通过 NapCat 的反向 WebSocket 调用 OneBot API。
    """

    packet = {
        "action": action,
        "params": params,
        "echo": f"render_{int(time.time() * 1000)}"
    }

    await websocket.send_text(
        json.dumps(
            packet,
            ensure_ascii=False
        )
    )


# ============================================================
# NapCat OneBot 11 反向 WebSocket
# ============================================================

@app.websocket("/onebot/v11/ws")
async def onebot_websocket(websocket: WebSocket):

    # --------------------------------------------------------
    # Token 校验
    # --------------------------------------------------------

    authorization = websocket.headers.get("authorization", "")
    query_token = websocket.query_params.get("access_token", "")

    if ONEBOT_ACCESS_TOKEN:
        expected = f"Bearer {ONEBOT_ACCESS_TOKEN}"

        if authorization != expected and query_token != ONEBOT_ACCESS_TOKEN:
            print("NapCat WebSocket Token 验证失败")

            await websocket.close(code=1008)
            return

    # 接受连接
    await websocket.accept()

    print("==============================")
    print("NapCat OneBot WebSocket 已连接")
    print("==============================")

    try:

        while True:

            raw_data = await websocket.receive_text()

            try:
                event = json.loads(raw_data)
            except json.JSONDecodeError:
                print("收到无法解析的数据：", raw_data)
                continue

            # OneBot API 调用结果不是消息事件
            if "post_type" not in event:
                continue

            post_type = event.get("post_type")

            # 目前第一阶段只处理消息
            if post_type != "message":
                continue

            message_type = event.get("message_type")

            # =================================================
            # 私聊消息
            # =================================================

            if message_type == "private":

                user_id = event.get("user_id")
                self_id = event.get("self_id")

                # 防止机器人处理自己发出的消息
                if str(user_id) == str(self_id):
                    continue

                text = get_message_text(event)

                print("==============================")
                print("收到 QQ 私聊")
                print("QQ：", user_id)
                print("内容：", text)
                print("==============================")

                # -------------------------------------------------
                # 第一阶段先使用固定回复测试链路
                # 后面这里再替换成 AI 回复
                # -------------------------------------------------

                reply_text = (
                    "你好，我是发卡机器人，"
                    "NapCat 私聊自动回复已经正常运行。"
                )

                await send_onebot_action(
                    websocket,
                    "send_private_msg",
                    {
                        "user_id": user_id,
                        "message": reply_text,
                        "auto_escape": True
                    }
                )

                print("已回复 QQ：", user_id)

    except WebSocketDisconnect:

        print("==============================")
        print("NapCat WebSocket 已断开")
        print("等待 NapCat 自动重连...")
        print("==============================")

    except Exception as e:

        print("==============================")
        print("OneBot WebSocket 出现错误")
        print(repr(e))
        print("==============================")
