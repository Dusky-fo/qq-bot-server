import botpy

class MyClient(botpy.Client):

    async def on_ready(self):
        print("QQ机器人上线")


    async def on_at_message_create(self, message):
        await message.reply(
            content="你好，我上线了"
        )


client = MyClient()

client.run(
    appid=APP_ID,
    secret=APP_SECRET
)
