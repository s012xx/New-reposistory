import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# ======================
# 環境変数チェック
# ======================
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, OPENAI_API_KEY]):
    raise ValueError(
        "環境変数が不足しています。 "
        "LINE_CHANNEL_SECRET / LINE_CHANNEL_ACCESS_TOKEN / OPENAI_API_KEY を設定してください。"
    )

app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ======================
# ユーザー状態管理（簡易）
# ======================
user_states = {}

def reset_user(user_id):
    user_states[user_id] = {
        "step": "ask_questions",
        "answers": [],
        "paid": False
    }

# ======================
# Webhook
# ======================
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

# ======================
# メイン処理
# ======================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if user_id not in user_states:
        reset_user(user_id)

    state = user_states[user_id]

    # ---- reset ----
    if text.lower() in ["reset", "リセット"]:
        reset_user(user_id)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="リセットしました✨\n最初から進めますね。")
        )
        return

    # ======================
    # 質問フェーズ
    # ======================
    if state["step"] == "ask_questions":

        if len(state["answers"]) == 0:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=(
                        "状況を把握するために【3つだけ】教えてください。\n\n"
                        "① 今いちばん気になっていること\n"
                        "② いつ頃からモヤモヤしていますか？\n"
                        "③ 最終的にどうなれたら理想ですか？\n\n"
                        "まとめて送っても、1つずつでも大丈夫です。"
                    )
                )
            )
            state["answers"].append("__asked__")
            return

        # 回答としてカウント（内容ベース）
        state["answers"].append(text)

        if len(state["answers"]) < 4:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="ありがとうございます✨ 残りも教えてください。")
            )
            return

        # 3つ揃った
        state["step"] = "free_reading"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=(
                    "無料鑑定をお届けします🔮\n\n"
                    "あなたの流れを見ると、今は\n"
                    "『一度立ち止まり、方向を整える時期』。\n\n"
                    "気持ちの奥ではもう答えが見えているのに、\n"
                    "現実とのズレに迷いが出やすいタイミングです。\n\n"
                    "ここから先は、より深く読み解くことで\n"
                    "選択がはっきりしていきます。"
                )
            )
        )

        # 有料案内を必ず出す
        line_bot_api.push_message(
            user_id,
            TextSendMessage(
                text=(
                    "ここから先は【有料鑑定】になります。\n\n"
                    "番号かプラン名で選んでください👇\n"
                    "1️⃣ ライト\n"
                    "2️⃣ シルバー\n"
                    "3️⃣ ゴールド\n\n"
                    "迷う場合は「おすすめ」と送ってください。"
                )
            )
        )

        state["step"] = "select_plan"
        return

    # ======================
    # プラン選択
    # ======================
    if state["step"] == "select_plan":

        if text in ["1", "ライト"]:
            plan = "ライト"
        elif text in ["2", "シルバー"]:
            plan = "シルバー"
        elif text in ["3", "ゴールド"]:
            plan = "ゴールド"
        elif text == "おすすめ":
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=(
                        "迷ったら「シルバー」が一番バランスが良いですよ✨\n"
                        "内容を見てから決めたい場合は\n"
                        "1 / 2 / 3 の番号でも選べます。"
                    )
                )
            )
            return
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="番号かプラン名で選んでください✨")
            )
            return

        state["step"] = "waiting_payment"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=(
                    f"{plan}プランを選択しました✨\n\n"
                    "BASEにてご購入後、\n"
                    "「購入しました」と送ってください。"
                )
            )
        )
        return

    # ======================
    # 購入後
    # ======================
    if state["step"] == "waiting_payment":

        if "購入" in text:
            state["paid"] = True
            state["step"] = "paid_reading"

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=(
                        "本鑑定をお届けします🔮\n\n"
                        "あなたは今、人生の流れが\n"
                        "『次の段階へ移る直前』にいます。\n\n"
                        "これまで耐えてきたこと、\n"
                        "飲み込んできた感情は、\n"
                        "決して無駄ではありません。\n\n"
                        "ここからは\n"
                        "「選び直す勇気」が運命を動かします。\n\n"
                        "焦らなくて大丈夫。\n"
                        "あなたのペースで、確実に好転します。"
                    )
                )
            )
            return

        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="ご購入後に「購入しました」と送ってください✨")
            )
            return

# ======================
if __name__ == "__main__":
    app.run()

