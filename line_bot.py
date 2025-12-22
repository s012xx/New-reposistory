import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai

# ========= 環境変数 =========
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET, OPENAI_API_KEY]):
    raise Exception("環境変数が不足しています。")

openai.api_key = OPENAI_API_KEY

# ========= LINE設定 =========
app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ========= ユーザー状態管理（簡易） =========
user_states = {}

# ========= メッセージ生成 =========
def ai_reply(prompt):
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "あなたは占い分野のプロ鑑定士です。丁寧で核心を突く文章を作成してください。"},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

# ========= Webhook =========
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    handler.handle(body, signature)
    return "OK"

# ========= メイン処理 =========
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    state = user_states.get(user_id, {
        "phase": "start",
        "answers": [],
        "free_used": False,
        "plan": None,
        "silver_count": 0
    })

    # ---- リセット ----
    if text.lower() in ["リセット", "reset"]:
        user_states[user_id] = {
            "phase": "start",
            "answers": [],
            "free_used": False,
            "plan": None,
            "silver_count": 0
        }
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="状態をリセットしました。最初から進められます✨")
        )
        return

    # ---- 初回 ----
    if state["phase"] == "start":
        reply = (
            "はじめまして🔮\n"
            "運命ナビ占い・フォーチュンです。\n\n"
            "まずは無料鑑定をご案内します。\n"
            "状況を把握するために【3つだけ】教えてください。\n\n"
            "① 今いちばん気になっていること\n"
            "② いつ頃から続いていますか？\n"
            "③ 最終的にどうなれたら理想ですか？\n\n"
            "まとめて送っても、1つずつでも大丈夫です✨\n"
            "そろいましたら【鑑定して】と送ってください。"
        )
        state["phase"] = "collecting"
        user_states[user_id] = state
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # ---- 回答収集中 ----
    if state["phase"] == "collecting":
        if text in ["鑑定して", "鑑定お願いします"]:
            if len(state["answers"]) < 3:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="まだ情報がそろっていません。残りも教えてください✨")
                )
                return

            prompt = f"""
以下は相談者の情報です。
{state["answers"][0]}
{state["answers"][1]}
{state["answers"][2]}

無料鑑定として、今の流れと注意点をしっかり文章量多めで伝えてください。
"""
            result = ai_reply(prompt)

            reply = (
                "🔮 無料鑑定をお届けします\n\n"
                f"{result}\n\n"
                "ここから先は【有料鑑定】になります。\n\n"
                "番号かプラン名で選んでください👇\n"
                "1️⃣ ライト\n"
                "2️⃣ シルバー\n"
                "3️⃣ ゴールド\n\n"
                "迷う場合は「おすすめ」と送ってください。"
            )

            state["free_used"] = True
            state["phase"] = "select_plan"
            user_states[user_id] = state

            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return
        else:
            state["answers"].append(text)
            user_states[user_id] = state
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="ありがとうございます✨ 続けて教えてください。")
            )
            return

    # ---- プラン選択 ----
    if state["phase"] == "select_plan":
        if text in ["おすすめ", "オススメ"]:
            reply = (
                "迷っている方には【シルバープラン】がおすすめです✨\n"
                "状況が動いたときに、複数回鑑定できるのが強みです。\n\n"
                "よろしければ「シルバー」と送ってください。"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        if text in ["1", "ライト"]:
            state["plan"] = "light"
        elif text in ["2", "シルバー"]:
            state["plan"] = "silver"
        elif text in ["3", "ゴールド"]:
            state["plan"] = "gold"
        else:
            return

        reply = (
            "ありがとうございます✨\n"
            "ご購入が確認でき次第、鑑定に入ります。\n\n"
            "鑑定を始める準備ができたら\n"
            "【鑑定して】と送ってください🔮"
        )
        state["phase"] = "paid_wait"
        user_states[user_id] = state
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # ---- 有料鑑定 ----
    if state["phase"] == "paid_wait":
        if text not in ["鑑定して", "鑑定お願いします"]:
            return

        if state["plan"] == "silver":
            if state["silver_count"] >= 3:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="シルバープランの鑑定回数は終了しています✨")
                )
                return
            state["silver_count"] += 1

        prompt = f"""
これは有料の本鑑定です。
相談内容：
{state["answers"]}

深く、具体的で、読み応えのある鑑定文を作成してください。
"""

        result = ai_reply(prompt)

        reply = (
            "🔮 本鑑定をお届けします\n\n"
            f"{result}\n\n"
            "今回の鑑定はここまでになります✨\n"
            "また鑑定をご希望の際は【鑑定して】と送ってください。"
        )

        user_states[user_id] = state
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
