import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError
from openai import OpenAI

# =====================
# 環境変数チェック
# =====================
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, OPENAI_API_KEY]):
    raise RuntimeError(
        "環境変数が不足しています。 "
        "LINE_CHANNEL_SECRET / LINE_CHANNEL_ACCESS_TOKEN / OPENAI_API_KEY を設定してください。"
    )

# =====================
# 初期化
# =====================
app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
client = OpenAI(api_key=OPENAI_API_KEY)

# =====================
# ユーザー状態管理
# =====================
user_states = {}

def get_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = {
            "step": "start",
            "answers": {},
            "selected_plan": None
        }
    return user_states[user_id]

def reset_state(user_id):
    user_states[user_id] = {
        "step": "start",
        "answers": {},
        "selected_plan": None
    }

# =====================
# メッセージ生成
# =====================
def start_message():
    return (
        "はじめまして🔮 運命ナビ占い・フォーチュンです。\n\n"
        "まずは【無料鑑定】から始めます。\n"
        "状況を把握するために、次の【3つ】を教えてください。\n\n"
        "① 今いちばん気になっていること\n"
        "② いつ頃からモヤモヤしていますか？\n"
        "③ 最終的にどうなれたら理想ですか？\n\n"
        "※まとめて送っても、1つずつでも大丈夫です。"
    )

def need_more_answers(state):
    missing = [q for q in ["1", "2", "3"] if q not in state["answers"]]
    return missing

def free_result_message():
    return (
        "🔮【無料鑑定結果】\n\n"
        "今のあなたは「気持ちと現実のズレ」に気づき始めている段階です。\n"
        "流れ自体は止まっていませんが、判断を先送りにしやすい時期。\n\n"
        "このまま曖昧にすると、同じ悩みを繰り返しやすい暗示があります。\n"
        "ただし、ポイントを整理すれば流れは十分に変えられます。\n\n"
        "ここまでが【無料鑑定】です✨"
    )

def plan_simple_message():
    return (
        "ここから先は【有料鑑定】になります。\n\n"
        "番号かプラン名で選んでください👇\n"
        "1️⃣ ライト\n"
        "2️⃣ シルバー\n"
        "3️⃣ ゴールド\n\n"
        "迷う場合は「おすすめ」と送ってください。"
    )

def plan_detail_message():
    return (
        "【プラン詳細】\n\n"
        "1️⃣ ライト（2,000円）\n"
        "・1テーマを丁寧に鑑定\n"
        "・現状整理と近い未来を明確にしたい方\n\n"
        "2️⃣ シルバー（4,000円 / 2週間・3回）\n"
        "・状況が動くたびに再鑑定OK\n"
        "・恋愛や人間関係の変化が気になる方\n\n"
        "3️⃣ ゴールド（6,000円 / 2週間）\n"
        "・相談し放題\n"
        "・人生全体を整えたい方"
    )

def payment_message(plan):
    links = {
        "light": "https://fortune907.base.shop/items/128865860",
        "silver": "https://fortune907.base.shop/items/128866117",
        "gold": "https://fortune907.base.shop/items/128866188"
    }

    names = {
        "light": "ライトプラン（2,000円）",
        "silver": "シルバープラン（4,000円）",
        "gold": "ゴールドプラン（6,000円）"
    }

    return (
        f"✨ {names[plan]} を選びました。\n\n"
        "以下のBASEショップからお支払いをお願いします👇\n"
        f"{links[plan]}\n\n"
        "お支払い完了後、\n"
        "【支払いました】と送ってください。\n"
        "確認後、本鑑定に入ります🔮"
    )

def paid_hearing_message():
    return (
        "ありがとうございます✨\n\n"
        "それでは【本鑑定】に入ります。\n"
        "鑑定したいテーマや、特に深く知りたい点があれば教えてください。\n\n"
        "（例：相手の気持ち／今後の展開／選択の判断など）"
    )

def generate_paid_reading(prompt):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "あなたは経験豊富な占い師です。核心を突きつつ、丁寧で現実的な鑑定を行ってください。"},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

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

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    state = get_state(user_id)

    # リセット
    if text.lower() in ["リセット", "reset"]:
        reset_state(user_id)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="リセットしました。最初から始めます🔁\n\n" + start_message())
        )
        return

    # スタート
    if state["step"] == "start":
        state["step"] = "free_hearing"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=start_message()))
        return

    # 無料ヒアリング（3項目揃うまで待つ）
    if state["step"] == "free_hearing":
        if "1" not in state["answers"]:
            state["answers"]["1"] = text
        elif "2" not in state["answers"]:
            state["answers"]["2"] = text
        elif "3" not in state["answers"]:
            state["answers"]["3"] = text

        missing = need_more_answers(state)
        if missing:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="ありがとうございます。続けて教えてください✨")
            )
            return
        else:
            state["step"] = "free_result"
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=free_result_message())
            )
            return

    # プラン案内
    if state["step"] == "free_result":
        state["step"] = "wait_plan"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=plan_simple_message())
        )
        return

    # プラン選択
    if state["step"] == "wait_plan":
        t = text.lower()
        if t in ["1", "ライト", "light"]:
            plan = "light"
        elif t in ["2", "シルバー", "silver"]:
            plan = "silver"
        elif t in ["3", "ゴールド", "gold"]:
            plan = "gold"
        elif "おすすめ" in t:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="迷ったら【シルバー】がおすすめです。\n\n" + plan_detail_message())
            )
            return
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="番号（1〜3）かプラン名で選んでください😊")
            )
            return

        state["selected_plan"] = plan
        state["step"] = "wait_payment"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=payment_message(plan))
        )
        return

    # 支払い待ち
    if state["step"] == "wait_payment":
        if "支払" in text:
            state["step"] = "paid_hearing"
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=paid_hearing_message())
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="お支払い後に【支払いました】と送ってください✨")
            )
        return

    # 本鑑定
    if state["step"] == "paid_hearing":
        reading = generate_paid_reading(text)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reading)
        )
        return


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

