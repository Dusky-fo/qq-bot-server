import os
import asyncio
import botpy

from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")


app = FastAPI()


@app.get("/")
def home():
    return {
        "status": "QQ机器人运行中"
    }


class MyClient(botpy.Client):

    async def on_ready(self):
        print("QQ机器人上线成功")


    async def on_at_message_create(self, message):

        print("收到消息:", message.content)

        await message.reply(
            content="你好，我是发卡机器人"
        )


client = MyClient()


@app.on_event("startup")
async def start_bot():

    asyncio.create_task(
        client.start(
            appid=APP_ID,
            secret=APP_SECRET
        )
    )
