import os
import openai
from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage
)

# ========= 環境変数 =========
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, OPENAI_API_KEY]):
    raise ValueError("環境変数が不足しています。")

openai.api_key = OPENAI_API_KEY

app = Flask(__name__)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ========= ユーザー状態管理（簡易） =========
user_states = {}

def reset_user(user_id):
    user_states[user_id] = {
        "step": "free_intro",
        "answers": {}
    }

# ========= Webhook =========
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
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

    # 初回 or 状態なし
    if user_id not in user_states:
        reset_user(user_id)

    state = user_states[user_id]

    # ===== リセット =====
    if text in ["リセット", "最初から", "やり直し", "もう一回"]:
        reset_user(user_id)
        reply(event, intro_message())
        return

    # ===== フロー分岐 =====
    if state["step"] == "free_intro":
        reply(event, hearing_message())
        state["step"] = "free_hearing"
        return

    if state["step"] == "free_hearing":
        collect_answers(state, text)
        if len(state["answers"]) < 3:
            reply(event, "ありがとうございます。続けて教えてください🌿")
            return
        else:
            reply(event, free_reading(state["answers"]))
            state["step"] = "plan_guide"
            return

    if state["step"] == "plan_guide":
        reply(event, plan_message())
        state["step"] = "wait_plan"
        return

    if state["step"] == "wait_plan":
        plan = normalize_plan(text)
        if not plan:
            reply(event, "「ライト」「シルバー」「ゴールド」または「おすすめ」と送ってください😊")
            return

        if plan == "recommend":
            reply(event, recommend_message())
            return

        state["selected_plan"] = plan
        reply(event, paid_hearing_message())
        state["step"] = "paid_hearing"
        return

    if state["step"] == "paid_hearing":
        state["paid_text"] = text
        reply(event, paid_reading(text))
        state["step"] = "done"
        return

    # ===== 想定外 =====
    reply(event, "少し分かりづらかったかもですね😊\n「リセット」と送ると最初からやり直せます。")

# ========= メッセージ群 =========

def reply(event, text):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=text)
    )

def intro_message():
    return (
        "はじめまして✨\n"
        "ここでは恋愛・相性・仕事・人生の流れを\n"
        "やさしく、必要な部分はしっかり鑑定します。\n\n"
        "まずは【無料鑑定】からどうぞ🌿"
    )

def hearing_message():
    return (
        "状況を正しく読み取るために、\n"
        "【3つだけ】教えてください🌿\n\n"
        "① 今いちばん気になっていること\n"
        "② いつ頃からモヤモヤしていますか？\n"
        "③ 最終的にどうなれたら理想ですか？\n\n"
        "まとめて送っても、1つずつでも大丈夫です。"
    )

def collect_answers(state, text):
    answers = state["answers"]
    if "1" not in answers:
        answers["1"] = text
    elif "2" not in answers:
        answers["2"] = text
    elif "3" not in answers:
        answers["3"] = text

def free_reading(answers):
    return (
        "教えてくれてありがとうございます。\n\n"
        "今の流れを占いの視点でみると、\n"
        "あなたは少し『考えすぎ』の状態に入っています。\n\n"
        "本来は直感が鋭いのに、\n"
        "今は不安が先に立ち、選択肢を狭めているようです。\n\n"
        "このまま進むと、\n"
        "✔ 無理に決める\n"
        "✔ 後から違和感が出る\n"
        "という流れになりやすいです。\n\n"
        "ここから先では、\n"
        "・どう整えるか\n"
        "・いつ動くとよいか\n"
        "・相性や未来の流れ\n"
        "まで詳しく読み解けます。"
    )

def plan_message():
    return (
        "より詳しく鑑定するために、\n"
        "3つのプランをご用意しています。\n\n"
        "1️⃣ ライト（2,000円）\n"
        "2️⃣ シルバー（4,000円）⭐おすすめ\n"
        "3️⃣ ゴールド（6,000円）\n\n"
        "「ライト」「シルバー」「ゴールド」\n"
        "または「おすすめ」と送ってください😊"
    )

def normalize_plan(text):
    t = text.lower()
    if "おすすめ" in t:
        return "recommend"
    if "ライト" in t or t == "1":
        return "light"
    if "シルバー" in t or t == "2":
        return "silver"
    if "ゴールド" in t or t == "3":
        return "gold"
    return None

def recommend_message():
    return (
        "今のお話を踏まえると、\n"
        "シルバープランがいちばん合っています🌿\n\n"
        "理由は、\n"
        "・テーマが1つに絞りきれていない\n"
        "・感情と状況にズレがある\n"
        "・タイミングを見極めたい\n\n"
        "この3点が強く出ているからです。\n\n"
        "ご希望があれば教えてください😊"
    )

def paid_hearing_message():
    return (
        "では本鑑定に入ります🔮\n\n"
        "次のことを教えてください。\n"
        "・特に知りたいテーマ\n"
        "・関係する相手がいればその関係性\n"
        "・いつ頃までに知りたいか\n\n"
        "思いつく範囲で大丈夫です。"
    )

def paid_reading(text):
    return (
        "お待たせしました。\n"
        "本鑑定の結果をお伝えします。\n\n"
        "あなたは今、人生の流れが切り替わる\n"
        "とても大切なタイミングにいます。\n\n"
        "（ここに占い結果を生成・追加）\n\n"
        "必要であれば、追加で読み解くこともできます🌙"
    )

# ========= 起動 =========
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

