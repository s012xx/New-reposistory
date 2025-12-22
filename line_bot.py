import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from openai import OpenAI

# ========= 環境変数 =========
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, OPENAI_API_KEY]):
    raise ValueError("環境変数が不足しています。")

# ========= 初期化 =========
app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
client = OpenAI(api_key=OPENAI_API_KEY)

# ========= 状態管理（簡易） =========
user_state = {}

# ========= 定数 =========
BASE_LINKS = {
    "ライト": "https://fortune907.base.shop/items/128865860",
    "シルバー": "https://fortune907.base.shop/items/128866117",
    "ゴールド": "https://fortune907.base.shop/items/128866188",
}

PLAN_LIMITS = {
    "ライト": 1,
    "シルバー": 3,
    "ゴールド": 999
}

# ========= 鑑定文 =========
FREE_READING_TEXT = """無料鑑定をお届けします🔮

あなたの流れを読み解くと、今は
「一度立ち止まり、方向を整えるタイミング」にいます。

ここ最近、
✔ 気持ちは前に進みたいのに、行動が追いつかない
✔ 決めたはずのことに、また迷いが出てくる
そんな感覚はありませんか？

これは停滞ではなく、
次の段階に進む前の“調整期間”です。

あなたの場合、
外から見た状況と、内側の本音に
少しズレが生まれているため、
無意識にブレーキをかけている状態が見えます。

ただ、流れそのものは悪くありません。
むしろ今は、
「本当に必要なものだけを残す」
という大切な整理が進んでいます。

ここから先は、
あなた個人の状況・選択肢・タイミングを
さらに具体的に読み解いていくことで、
迷いを減らし、行動に移しやすくなります。
"""

PAID_READING_TEXT = """本鑑定をお届けします🔮

あなたの流れを深く読み解くと、
今は「人生の流れが切り替わる直前」にいます。

これまでのあなたは、
自分よりも周囲を優先し、
状況に合わせて選択してきた場面が多かったはずです。

その積み重ねは決して無駄ではありませんが、
同時に
「本当は違う選び方もあったのでは」
という想いが心の奥に残っています。

今、運命の流れは
“これまでの延長”ではなく、
「自分で選び直す方向」へと動き始めています。

これからは、
自分の感覚を信じて選択することで、
流れは驚くほど軽くなっていきます。

ここまでが今回の本鑑定です。

また鑑定を希望するタイミングで、
「鑑定して」
と送ってください🔮
"""

# ========= Webhook =========
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

# ========= メイン処理 =========
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if user_id not in user_state:
        user_state[user_id] = {
            "answers": [],
            "plan": None,
            "used": 0
        }

    state = user_state[user_id]

    # ---- 初回ヒアリング ----
    if len(state["answers"]) < 3:
        state["answers"].append(text)

        if len(state["answers"]) < 3:
            reply = "ありがとうございます✨ 残りも教えてください。"
        else:
            reply = (
                FREE_READING_TEXT +
                "\n\nここから先は【有料鑑定】になります。\n\n"
                "番号かプラン名で選んでください👇\n"
                "1️⃣ ライト\n2️⃣ シルバー\n3️⃣ ゴールド\n\n"
                "迷う場合は「おすすめ」と送ってください。"
            )

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply)
        )
        return

    # ---- プラン選択 ----
    if state["plan"] is None:
        if text in ["1", "ライト"]:
            state["plan"] = "ライト"
        elif text in ["2", "シルバー"]:
            state["plan"] = "シルバー"
        elif text in ["3", "ゴールド"]:
            state["plan"] = "ゴールド"
        elif text == "おすすめ":
            reply = "じっくり相談したい方には【シルバー】がおすすめです。"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return
        else:
            return

        reply = (
            f"{state['plan']}プランをお選びいただきありがとうございます✨\n\n"
            f"こちらからご購入ください👇\n{BASE_LINKS[state['plan']]}\n\n"
            "購入後「購入しました」と送ってください。"
        )

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # ---- 購入確認 ----
    if text == "購入しました":
        reply = "ありがとうございます✨\n鑑定したいタイミングで「鑑定して」と送ってください。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # ---- 本鑑定 ----
    if text == "鑑定して":
        if state["used"] >= PLAN_LIMITS[state["plan"]]:
            reply = (
                "このプランの鑑定回数は終了しました。\n\n"
                "🔮 継続やランクアップも可能です。\n"
                "1️⃣ ライト\n2️⃣ シルバー\n3️⃣ ゴールド\n\n"
                "番号かプラン名で送ってください。"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        state["used"] += 1
        reply = PAID_READING_TEXT
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return
