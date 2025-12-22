import os
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
    raise Exception("環境変数が不足しています。")

app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# =====================
# 簡易ユーザー管理（メモリ）
# =====================
user_states = {}

def init_user(user_id):
    user_states[user_id] = {
        "answers": {},
        "phase": "question",
        "plan": None,
        "remaining": 0
    }

# =====================
# Webhook
# =====================
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# =====================
# メッセージ処理
# =====================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if user_id not in user_states or text == "リセット":
        init_user(user_id)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=
                "状況を把握するために【3つだけ】教えてください。\n\n"
                "① 今いちばん気になっていること\n"
                "② いつ頃からモヤモヤしていますか？\n"
                "③ 最終的にどうなれたら理想ですか？\n\n"
                "まとめて送っても、1つずつでも大丈夫です。"
            )
        )
        return

    state = user_states[user_id]

    # =====================
    # 質問フェーズ
    # =====================
    if state["phase"] == "question":
        answers = state["answers"]

        if "1" not in answers:
            answers["1"] = text
        elif "2" not in answers:
            answers["2"] = text
        elif "3" not in answers:
            answers["3"] = text

        if len(answers) < 3:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="ありがとうございます✨ 続けて教えてください。")
            )
            return

        # 無料鑑定
        state["phase"] = "free_done"
        free_text = (
            "無料鑑定をお届けします🔮\n\n"
            "あなたの流れを見ると、今は\n"
            "『一度立ち止まり、方向を整える時期』にいます。\n\n"
            "気持ちの奥ではすでに答えが見えている一方で、\n"
            "現実とのズレや周囲の影響により、\n"
            "決断を先延ばしにしやすい状態です。\n\n"
            "この時期は無理に動くより、\n"
            "自分の本音を整理することで\n"
            "次の選択が自然と見えてきます。\n\n"
            "ここから先は、より深く読み解くことで\n"
            "具体的な行動指針がはっきりしていきます。"
        )

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=free_text + "\n\n"
                "ここから先は【有料鑑定】になります。\n\n"
                "番号かプラン名で選んでください👇\n"
                "1️⃣ ライト\n"
                "2️⃣ シルバー\n"
                "3️⃣ ゴールド\n\n"
                "迷う場合は「おすすめ」と送ってください。"
            )
        )
        return

    # =====================
    # プラン選択
    # =====================
    if state["phase"] == "free_done":
        if text in ["1", "ライト"]:
            state["plan"] = "ライト"
            state["remaining"] = 1
        elif text in ["2", "シルバー"]:
            state["plan"] = "シルバー"
            state["remaining"] = 3
        elif text in ["3", "ゴールド"]:
            state["plan"] = "ゴールド"
            state["remaining"] = 999
        elif text == "おすすめ":
            state["plan"] = "シルバー"
            state["remaining"] = 3
        else:
            return

        state["phase"] = "payment"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=
                f"{state['plan']}プランを選択しました✨\n\n"
                "BASEショップでご購入後、\n"
                "「購入しました」と送ってください。"
            )
        )
        return

    # =====================
    # 購入確認
    # =====================
    if state["phase"] == "payment" and text == "購入しました":
        state["phase"] = "paid"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=
                "ありがとうございます✨\n\n"
                "本鑑定をご希望のタイミングで\n"
                "「鑑定して」と送ってください🔮"
            )
        )
        return

    # =====================
    # 本鑑定
    # =====================
    if state["phase"] == "paid" and text == "鑑定して":
        if state["remaining"] <= 0:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=
                    "このプランの鑑定回数は終了しました。\n\n"
                    "🔄 継続する\n⬆️ ランクアップする\n\n"
                    "場合は、プラン名を送ってください✨"
                )
            )
            return

        state["remaining"] -= 1

        result = (
            "本鑑定をお届けします🔮\n\n"
            "あなたは今、人生の流れが\n"
            "『次の段階へ移行する直前』にいます。\n\n"
            "これまで我慢してきたことや\n"
            "飲み込んできた感情は、\n"
            "決して無駄ではありません。\n\n"
            "ここからは\n"
            "「自分を優先する選択」を取ることで\n"
            "運命の歯車が静かに噛み合っていきます。\n\n"
            "焦らず、周囲と比べず、\n"
            "あなたのペースで進んで大丈夫です。\n\n"
            "今回の鑑定はここまでです✨"
        )

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=result)
        )
        return

# =====================
# 起動
# =====================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
