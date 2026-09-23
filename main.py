import os
import asyncio
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()


APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")


@app.get("/")
def home():
    return {
        "status": "QQ机器人运行中",
        "appid": APP_ID
    }


async def qq_bot_start():
    """
    QQ机器人连接入口
    后续这里接QQ官方WebSocket
    """

    print("QQ机器人启动")
    print("APP_ID:", APP_ID)

    while True:
        # 保持后台运行
        await asyncio.sleep(60)


@app.on_event("startup")
async def startup_event():

    asyncio.create_task(
        qq_bot_start()
    )
