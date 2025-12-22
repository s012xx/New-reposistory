import os
import re
from flask import Flask, request, abort

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# =====================
# 環境変数チェック
# =====================
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, OPENAI_API_KEY]):
    raise ValueError("環境変数が不足しています。")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

app = Flask(__name__)

# =====================
# ユーザー状態管理（簡易）
# =====================
user_states = {}

def init_state(user_id):
    user_states[user_id] = {
        "step": "ask_questions",
        "answers": {},
        "free_done": False,
        "paid": False
    }

# =====================
# Webhook
# =====================
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

# =====================
# メッセージ受信
# =====================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if user_id not in user_states or text.lower() == "reset":
        init_state(user_id)
        reply_text = (
            "状況を把握するために【3つだけ】教えてください。\n\n"
            "① 今いちばん気になっていること\n"
            "② いつ頃からモヤモヤしていますか？\n"
            "③ 最終的にどうなれたら理想ですか？\n\n"
            "まとめて送っても、1つずつでも大丈夫です✨"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(reply_text))
        return

    state = user_states[user_id]

    # =====================
    # 有料購入後
    # =====================
    if state["paid"]:
        reply = generate_paid_fortune(text)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(reply))
        return

    # =====================
    # 無料鑑定前ヒアリング
    # =====================
    if state["step"] == "ask_questions":
        if "①" in text:
            state["answers"]["q1"] = text
        if "②" in text:
            state["answers"]["q2"] = text
        if "③" in text:
            state["answers"]["q3"] = text

        if len(state["answers"]) < 3:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage("ありがとうございます✨ 残りも教えてください。")
            )
            return

        # 無料鑑定へ
        free_result = generate_free_fortune(state["answers"])
        state["step"] = "free_done"
        state["free_done"] = True

        reply = (
            free_result
            + "\n\nここから先は【有料鑑定】になります。\n\n"
              "番号かプラン名で選んでください👇\n"
              "1️⃣ ライト\n"
              "2️⃣ シルバー\n"
              "3️⃣ ゴールド\n\n"
              "迷う場合は「おすすめ」と送ってください。"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(reply))
        return

    # =====================
    # プラン選択
    # =====================
    if state["free_done"]:
        if re.search(r"(1|ライト)", text):
            plan = "ライト"
        elif re.search(r"(2|シルバー)", text):
            plan = "シルバー"
        elif re.search(r"(3|ゴールド)", text):
            plan = "ゴールド"
        elif "おすすめ" in text:
            plan = "シルバー"
        else:
            return

        reply = (
            f"{plan}プランをお選びいただきありがとうございます✨\n\n"
            "以下のBASEショップよりご購入ください👇\n\n"
        )

        if plan == "ライト":
            reply += "https://fortune907.base.shop/items/128865860"
        elif plan == "シルバー":
            reply += "https://fortune907.base.shop/items/128866117"
        else:
            reply += "https://fortune907.base.shop/items/128866188"

        reply += (
            "\n\n購入後、このトークに\n"
            "「購入しました」と送ってください✨"
        )
