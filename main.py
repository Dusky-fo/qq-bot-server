# -*- coding: utf-8 -*-

import asyncio
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from fastapi import FastAPI, WebSocket, WebSocketDisconnect


# ============================================================
# Render 环境变量
# ============================================================

# NapCat -> Render WebSocket 鉴权 Token
ONEBOT_ACCESS_TOKEN = os.getenv("ONEBOT_ACCESS_TOKEN", "").strip()

# 文心云 软件 ID
CARD_APP_ID = os.getenv("CARD_APP_ID", "").strip()

# 文心云 管理密钥
CARD_USERNAME_KEY = os.getenv("CARD_USERNAME_KEY", "").strip()

# 管理员 QQ
# Render 中填写：
# ADMIN_QQ_IDS=602651116
#
# 多个管理员：
# ADMIN_QQ_IDS=123456789,987654321
ADMIN_QQ_IDS = {
    qq.strip()
    for qq in os.getenv("ADMIN_QQ_IDS", "").split(",")
    if qq.strip()
}


# ============================================================
# 文心云线路
# Render 是海外服务器，所以海外线路优先
# ============================================================

CARD_API_LINES = [
    "http://apiw1.1wxyun.com",  # 海外线路
    "http://api2.1wxyun.com",   # 国内备用
    "http://api.1wxyun.com",    # 国内主线路
]


# ============================================================
# 五个固定套餐
# ============================================================

PACKAGES = {
    "1": {
        "name": "1小时卡",
        "price": "0.10",
        "cardtype": 1,
        "kajifei": 1,
    },

    "2": {
        "name": "3小时卡",
        "price": "0.50",
        "cardtype": 1,
        "kajifei": 3,
    },

    "3": {
        "name": "天卡",
        "price": "2.00",
        "cardtype": 2,
        "kajifei": 1,
    },

    "4": {
        "name": "周卡",
        "price": "10.00",
        "cardtype": 3,
        "kajifei": 1,
    },

    "5": {
        "name": "月卡",
        "price": "20.00",
        "cardtype": 4,
        "kajifei": 1,
    },
}


# ============================================================
# 临时订单状态
#
# 目前只是测试版，保存在内存中。
# Render 重启以后这些选择会清空。
#
# 后面接支付系统时再换成数据库。
# ============================================================

pending_orders = {}


# ============================================================
# FastAPI
# ============================================================

app = FastAPI()


@app.get("/")
async def home():
    return {
        "status": "大冒险QQ发卡服务器运行正常",
        "mode": "NapCat + OneBot11",
        "websocket": "/onebot/v11/ws",
        "card_api": "ready",
    }


@app.get("/health")
async def health():
    return {
        "status": "ok"
    }


# ============================================================
# QQ 消息处理工具
# ============================================================

def get_message_text(event: dict) -> str:
    """
    从 OneBot 消息事件中提取纯文本。
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

            if segment.get("type") != "text":
                continue

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
    通过 NapCat 反向 WebSocket 调用 OneBot API。
    """

    packet = {
        "action": action,
        "params": params,
        "echo": f"render_{int(time.time() * 1000)}",
    }

    await websocket.send_text(
        json.dumps(
            packet,
            ensure_ascii=False
        )
    )


async def send_private_message(
    websocket: WebSocket,
    user_id,
    text: str
):
    """
    给 QQ 好友发送私聊消息。
    """

    await send_onebot_action(
        websocket,
        "send_private_msg",
        {
            "user_id": user_id,
            "message": text,
            "auto_escape": True,
        }
    )


def is_admin(user_id) -> bool:
    """
    判断 QQ 是否属于管理员。
    """

    return str(user_id) in ADMIN_QQ_IDS


# ============================================================
# 套餐菜单
# ============================================================

def package_menu() -> str:
    return (
        "请选择套餐：\n\n"
        "1. 1小时卡  ¥0.10\n"
        "2. 3小时卡  ¥0.50\n"
        "3. 天卡     ¥2.00\n"
        "4. 周卡     ¥10.00\n"
        "5. 月卡     ¥20.00\n\n"
        "请回复 1-5 选择套餐。"
    )


# ============================================================
# 文心云 API
# ============================================================

def post_card_api(
    path: str,
    params: dict,
    timeout: int = 8
):
    """
    按顺序尝试三个文心云线路。

    海外 Render：
        apiw1
        ↓
        api2
        ↓
        api

    网络失败 / 超时 / HTTP错误时自动切换。
    """

    errors = []

    encoded_data = urllib.parse.urlencode(
        params
    ).encode("utf-8")

    headers = {
        "Content-Type":
            "application/x-www-form-urlencoded; charset=UTF-8",

        "User-Agent":
            "QQ-NapCat-CardServer/1.0",
    }

    for base_url in CARD_API_LINES:

        url = base_url + path

        try:

            request = urllib.request.Request(
                url=url,
                data=encoded_data,
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(
                request,
                timeout=timeout
            ) as response:

                status = response.getcode()

                body = response.read().decode(
                    "utf-8",
                    errors="replace"
                ).strip()

                if status == 200 and body:

                    print(
                        f"[文心云] 接口响应成功：{base_url}"
                    )

                    return body, base_url

                errors.append(
                    f"{base_url} -> "
                    f"HTTP {status} / 空响应"
                )

        except urllib.error.HTTPError as e:

            error_text = (
                f"{base_url} -> HTTP {e.code}"
            )

            print(
                "[文心云] 线路失败：",
                error_text
            )

            errors.append(error_text)

        except urllib.error.URLError as e:

            error_text = (
                f"{base_url} -> {e.reason}"
            )

            print(
                "[文心云] 线路失败：",
                error_text
            )

            errors.append(error_text)

        except Exception as e:

            error_text = (
                f"{base_url} -> {repr(e)}"
            )

            print(
                "[文心云] 线路失败：",
                error_text
            )

            errors.append(error_text)

    raise RuntimeError(
        "所有制卡线路均连接失败：\n"
        + "\n".join(errors)
    )


def make_card(
    package_id: str
):
    """
    调用文心云 type=101 管理制卡接口。

    当前测试：
    moshi = 1   单码
    duokai = 1
    number = 1
    """

    if not CARD_APP_ID:
        raise RuntimeError(
            "Render 未配置 CARD_APP_ID"
        )

    if not CARD_USERNAME_KEY:
        raise RuntimeError(
            "Render 未配置 CARD_USERNAME_KEY"
        )

    package = PACKAGES.get(package_id)

    if not package:
        raise RuntimeError(
            "套餐编号不存在"
        )

    params = {
        "usernamekey": CARD_USERNAME_KEY,

        "appid": CARD_APP_ID,

        # 1 = 单码
        "moshi": 1,

        "cardtype": package["cardtype"],

        "kajifei": package["kajifei"],

        # 单码多开数量
        "duokai": 1,

        # 卡密头暂时留空
        "kamitou": "",

        # 测试阶段每次只生成一张
        "number": 1,

        "beizhu":
            f"QQ机器人测试-{package['name']}",
    }

    return post_card_api(
        "/api.php?type=101",
        params
    )


# ============================================================
# 私聊业务逻辑
# ============================================================

async def handle_private_message(
    websocket: WebSocket,
    event: dict
):
    """
    所有购买 / 制卡业务只允许从这里进入。

    群聊绝不会调用这个函数。
    """

    user_id = event.get("user_id")

    text = get_message_text(event)

    if not user_id:
        return

    print(
        f"[私聊] QQ={user_id} 内容={text}"
    )

    # --------------------------------------------------------
    # 查看套餐
    # --------------------------------------------------------

    if text in {
        "购买",
        "买卡",
        "套餐",
        "/购买",
        "/价格",
        "价格",
    }:

        await send_private_message(
            websocket,
            user_id,
            package_menu()
        )

        return

    # --------------------------------------------------------
    # 选择套餐
    #
    # 这里只创建等待付款状态，
    # 不会直接调用制卡接口。
    # --------------------------------------------------------

    if text in PACKAGES:

        package = PACKAGES[text]

        pending_orders[str(user_id)] = {
            "package_id": text,
            "package_name": package["name"],
            "price": package["price"],
            "status": "WAITING_PAYMENT",
            "created_at": int(time.time()),
        }

        reply = (
            f"你选择的是：{package['name']}\n"
            f"价格：¥{package['price']}\n\n"
            "订单状态：等待付款\n\n"
            "当前为测试阶段，"
            "还没有接入微信/支付宝自动收款确认，"
            "所以不会直接生成卡密。"
        )

        await send_private_message(
            websocket,
            user_id,
            reply
        )

        return

    # --------------------------------------------------------
    # 查看自己的当前订单
    # --------------------------------------------------------

    if text in {
        "订单",
        "/订单",
    }:

        order = pending_orders.get(
            str(user_id)
        )

        if not order:

            await send_private_message(
                websocket,
                user_id,
                "你当前没有待处理订单。"
            )

            return

        await send_private_message(
            websocket,
            user_id,
            (
                f"套餐：{order['package_name']}\n"
                f"金额：¥{order['price']}\n"
                f"状态：{order['status']}"
            )
        )

        return

    # --------------------------------------------------------
    # 管理员测试制卡
    #
    # 示例：
    #
    # /测试制卡 1
    # /测试制卡 2
    # /测试制卡 3
    # /测试制卡 4
    # /测试制卡 5
    #
    # 普通 QQ 无权限执行。
    # --------------------------------------------------------

    if (
        text.startswith("/测试制卡")
        or text.startswith("测试制卡")
    ):

        if not is_admin(user_id):

            await send_private_message(
                websocket,
                user_id,
                "你没有制卡测试权限。"
            )

            print(
                f"[安全] 非管理员尝试制卡："
                f"{user_id}"
            )

            return

        parts = text.split()

        if len(parts) != 2:

            await send_private_message(
                websocket,
                user_id,
                (
                    "测试制卡格式：\n\n"
                    "/测试制卡 1\n\n"
                    "1 = 1小时卡\n"
                    "2 = 3小时卡\n"
                    "3 = 天卡\n"
                    "4 = 周卡\n"
                    "5 = 月卡"
                )
            )

            return

        package_id = parts[1]

        if package_id not in PACKAGES:

            await send_private_message(
                websocket,
                user_id,
                "套餐编号必须是 1-5。"
            )

            return

        package = PACKAGES[package_id]

        await send_private_message(
            websocket,
            user_id,
            (
                f"正在测试生成："
                f"{package['name']}\n"
                "请稍候..."
            )
        )

        try:

            # API 是同步 HTTP 请求，
            # 放在线程里执行，
            # 避免阻塞 FastAPI 主事件循环。
            result, used_line = (
                await asyncio.to_thread(
                    make_card,
                    package_id
                )
            )

            print(
                f"[制卡测试] 管理员={user_id} "
                f"套餐={package['name']} "
                f"线路={used_line}"
            )

            # 不擅自判断厂商返回字符串到底是
            # “成功卡密”还是“业务错误信息”，
            # 测试阶段原样返回，方便确认规则。
            reply = (
                f"文心云接口返回：\n\n"
                f"{result}"
            )

            await send_private_message(
                websocket,
                user_id,
                reply
            )

        except Exception as e:

            print(
                "[制卡测试失败]",
                repr(e)
            )

            await send_private_message(
                websocket,
                user_id,
                (
                    "制卡测试失败：\n"
                    f"{str(e)}"
                )
            )

        return

    # --------------------------------------------------------
    # 帮助
    # --------------------------------------------------------

    if text in {
        "帮助",
        "/帮助",
        "help",
        "/help",
    }:

        reply = (
            "发卡机器人使用方法：\n\n"
            "发送「购买」查看套餐\n"
            "发送 1-5 选择套餐\n"
            "发送「订单」查看当前订单"
        )

        if is_admin(user_id):

            reply += (
                "\n\n管理员测试：\n"
                "/测试制卡 1\n"
                "/测试制卡 2\n"
                "/测试制卡 3\n"
                "/测试制卡 4\n"
                "/测试制卡 5"
            )

        await send_private_message(
            websocket,
            user_id,
            reply
        )

        return

    # --------------------------------------------------------
    # 普通私聊
    # --------------------------------------------------------

    await send_private_message(
        websocket,
        user_id,
        (
            "你好，我是发卡机器人。\n\n"
            "发送「购买」查看套餐。"
        )
    )


# ============================================================
# NapCat OneBot 11 反向 WebSocket
# ============================================================

@app.websocket("/onebot/v11/ws")
async def onebot_websocket(
    websocket: WebSocket
):

    # --------------------------------------------------------
    # Token 鉴权
    # --------------------------------------------------------

    authorization = websocket.headers.get(
        "authorization",
        ""
    )

    query_token = websocket.query_params.get(
        "access_token",
        ""
    )

    if ONEBOT_ACCESS_TOKEN:

        expected = (
            f"Bearer {ONEBOT_ACCESS_TOKEN}"
        )

        if (
            authorization != expected
            and query_token != ONEBOT_ACCESS_TOKEN
        ):

            print(
                "NapCat WebSocket Token 验证失败"
            )

            await websocket.close(
                code=1008
            )

            return

    # --------------------------------------------------------
    # 接受 NapCat 连接
    # --------------------------------------------------------

    await websocket.accept()

    print("=" * 40)
    print(
        "NapCat OneBot WebSocket 已连接"
    )
    print("=" * 40)

    try:

        while True:

            raw_data = (
                await websocket.receive_text()
            )

            try:

                event = json.loads(
                    raw_data
                )

            except json.JSONDecodeError:

                print(
                    "收到无法解析的数据：",
                    raw_data
                )

                continue

            # API 返回包，不是 QQ 事件
            if "post_type" not in event:
                continue

            post_type = event.get(
                "post_type"
            )

            # 只处理消息事件
            if post_type != "message":
                continue

            message_type = event.get(
                "message_type"
            )

            # =================================================
            # 私聊
            #
            # 唯一允许进入购买 / 订单 / 制卡的入口
            # =================================================

            if message_type == "private":

                user_id = event.get(
                    "user_id"
                )

                self_id = event.get(
                    "self_id"
                )

                # 防止处理自己的消息
                if (
                    str(user_id)
                    == str(self_id)
                ):
                    continue

                await handle_private_message(
                    websocket,
                    event
                )

                continue

            # =================================================
            # 群聊
            #
            # 明确禁止进入交易机制。
            #
            # 无论群里：
            # @机器人 购买
            # @机器人 5
            # @机器人 测试制卡
            #
            # 全部不会调用文心云制卡接口。
            # =================================================

            if message_type == "group":

                group_id = event.get(
                    "group_id"
                )

                user_id = event.get(
                    "user_id"
                )

                text = get_message_text(
                    event
                )

                print(
                    f"[群聊忽略交易] "
                    f"群={group_id} "
                    f"QQ={user_id} "
                    f"内容={text}"
                )

                continue

    except WebSocketDisconnect:

        print("=" * 40)
        print(
            "NapCat WebSocket 已断开"
        )
        print(
            "等待 NapCat 自动重连..."
        )
        print("=" * 40)

    except Exception as e:

        print("=" * 40)
        print(
            "OneBot WebSocket 出现错误"
        )
        print(
            repr(e)
        )
        print("=" * 40)
