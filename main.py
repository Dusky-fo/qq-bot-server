import os
import threading

import botpy
from botpy.message import GroupMessage, C2CMessage
from fastapi import FastAPI


# ==============================
# Render 环境变量
# ==============================

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")


# ==============================
# FastAPI
# 用来让 Render 保持 Web Service 在线
# ==============================

app = FastAPI()


@app.get("/")
async def home():
    return {
        "status": "大冒险QQ机器人服务器运行正常",
        "qq_bot": "starting"
    }


# ==============================
# QQ机器人
# ==============================

class MyClient(botpy.Client):

    async def on_ready(self):
        print("==============================")
        print("QQ机器人连接成功！")
        print(f"机器人名称：{self.robot.name}")
        print("==============================")


    # QQ群里 @机器人
    async def on_group_at_message_create(
        self,
        message: GroupMessage
    ):
        print("收到群消息：", message.content)

        await message.reply(
            content="你好，我是发卡机器人，已经成功上线。"
        )


    # QQ好友/C2C私聊
    async def on_c2c_message_create(
        self,
        message: C2CMessage
    ):
        print("收到私聊消息：", message.content)

        await message.reply(
            content="你好，我是发卡机器人，私聊功能正常。"
        )


# 群聊 + 私聊事件
intents = botpy.Intents(
    public_messages=True
)

client = MyClient(
    intents=intents
)


def run_qq_bot():
    print("==============================")
    print("正在连接 QQ 机器人平台...")
    print("APP_ID:", APP_ID)
    print("==============================")

    try:
        client.run(
            appid=APP_ID,
            secret=APP_SECRET
        )
    except Exception as e:
        print("QQ机器人启动失败：")
        print(repr(e))


# ==============================
# Render启动时，同时启动QQ机器人
# ==============================

@app.on_event("startup")
async def startup_event():

    bot_thread = threading.Thread(
        target=run_qq_bot,
        daemon=True
    )

    bot_thread.start()
