import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# ======================
# 環境変数
# ======================
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, OPENAI_API_KEY]):
    raise RuntimeError("環境変数が不足しています")

# ======================
# LINE設定
# ======================
app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ======================
# プラン設定
# ======================
PLAN_LIMITS = {
    "ライト": 1,
    "シルバー": 3,
    "ゴールド": 999
}

BASE_LINKS = {
    "ライト": "https://your-base-link/light",
    "シルバー": "https://your-base-link/silver",
    "ゴールド": "https://your-base-link/gold"
}

# ======================
# ユーザー状態（簡易）
# ======================
user_states = {}

def get_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = {
            "answers": {},
            "free_done": False,
            "plan": None,
            "used": 0
        }
    return user_states[user_id]

# ======================
# テキスト定義
# ======================
FREE_READING = """無料鑑定をお届けします🔮

あなたの今の流れを見ると、
「一度立ち止まり、方向を整える時期」に入っています。

やるべきことは見えているのに、
気持ちが追いつかず、
どこかモヤモヤした感覚を抱えやすいタイミング。

これは停滞ではなく、
次のステージへ進む前の調整期間です。

ここから先は、
もう少し深く読み解くことで
✔ なぜ今この状態なのか
✔ どんな選択が流れを変えるのか
がはっきりしてきます。
"""

PAID_READING = """本鑑定をお届けします🔮

あなたの流れを丁寧に読み解くと、
今は「人生の軸を切り替える直前」にいます。

これまでのあなたは、
周囲との期待や安定を優先し、
自分の本音を後回しにしてきました。

それは優しさでもあり、
同時に自分を抑える癖でもありました。

今このタイミングで
小さくでも「選び直す行動」を取ると、
人間関係・仕事・環境が
あなたに合う形へと静かに再編されていきます。

焦る必要はありません。
正解を探すより、
「違和感を無視しないこと」が
これからの運気を大きく動かします。

ここまでが今回の本鑑定です🔮
"""

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
# メッセージ処理
# ======================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    state = get_state(user_id)

    # リセット
    if text == "リセット":
        user_states[user_id] = {
            "answers": {},
            "free_done": False,
            "plan": None,
            "used": 0
        }
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="リセットしました。最初から始められます🔄")
        )
        return

    # 質問収集
    if not state["free_done"]:
        if "①" not in state["answers"]:
            state["answers"]["①"] = text
            reply = "ありがとうございます✨ 続けて教えてください。\n\n② いつ頃からモヤモヤしていますか？"
        elif "②" not in state["answers"]:
            state["answers"]["②"] = text
            reply = "ありがとうございます✨\n\n③ 最終的にどうなれたら理想ですか？"
        elif "③" not in state["answers"]:
            state["answers"]["③"] = text
            state["free_done"] = True
            reply = (
                FREE_READING +
                "\n\nここから先は【有料鑑定】になります。\n\n"
                "1️⃣ ライト\n2️⃣ シルバー\n3️⃣ ゴールド\n\n"
                "迷う場合は「おすすめ」と送ってください👇"
            )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # おすすめ
    if text == "おすすめ":
        reply = (
            "継続的に流れを見ていきたい方には\n"
            "【シルバープラン】がおすすめです🔮\n\n"
            f"{BASE_LINKS['シルバー']}\n\n"
            "購入後「購入しました」と送ってください。"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # プラン選択
    if text in PLAN_LIMITS:
        state["plan"] = text
        state["used"] = 0
        reply = (
            f"{text}プランを選択しました✨\n\n"
            "本鑑定をご希望の際は\n"
            "【鑑定して】と送ってください🔮"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # 購入完了
    if text == "購入しました":
        reply = (
            "ありがとうございます✨\n\n"
            "本鑑定をご希望のタイミングで\n"
            "【鑑定して】と送ってください🔮"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # 本鑑定
    if text == "鑑定して":
        if not state["plan"]:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="先にプランを選択してください。")
            )
            return

        if state["used"] >= PLAN_LIMITS[state["plan"]]:
            reply = (
                "このプランの鑑定回数は終了しました🔮\n\n"
                "🔁 継続・ランクアップはこちら👇\n"
                "1️⃣ ライト\n2️⃣ シルバー\n3️⃣ ゴールド\n\n"
                "迷う場合は「おすすめ」と送ってください。\n\n"
                f"{BASE_LINKS['ライト']}\n"
                f"{BASE_LINKS['シルバー']}\n"
                f"{BASE_LINKS['ゴールド']}"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        state["used"] += 1
        reply = PAID_READING + "\n\n🔔 鑑定はここで一区切りです。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # その他
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="内容を入力するか「鑑定して」と送ってください🔮")
    )

# ======================
# 起動
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
