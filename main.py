from fastapi import FastAPI, Request

app = FastAPI()


@app.get("/")
def home():
    return {
        "status": "大冒险QQ机器人服务器运行正常"
    }


@app.post("/qq/callback")
async def qq_callback(request: Request):
    data = await request.json()

    print("收到QQ消息:")
    print(data)

    return {
        "code": 0
    }
