import os
import re
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from openai import OpenAI

# =========================
# 環境変数チェック
# =========================
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, OPENAI_API_KEY]):
    raise RuntimeError("環境変数が不足しています")

# =========================
# 初期化
# =========================
app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# 簡易セッション管理（ユーザーごと）
# =========================
user_states = {}

def get_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = {
            "phase": "start",
            "answers": [],
            "free_done": False
        }
    return user_states[user_id]

def reset_state(user_id):
    user_states[user_id] = {
        "phase": "start",
        "answers": [],
        "free_done": False
    }

# =========================
# Webhook
# =========================
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

# =========================
# メッセージ受信
# =========================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    state = get_state(user_id)

    # ---------- リセット ----------
    if text.lower() in ["reset", "リセット"]:
        reset_state(user_id)
        reply(event, "状態をリセットしました。\n最初から始めますね✨")
        send_menu(event)
        return

    # ---------- 開始 ----------
    if state["phase"] == "start":
        send_menu(event)
        state["phase"] = "menu"
        return

    # ---------- メニュー選択 ----------
    if state["phase"] == "menu":
        if re.search(r"恋愛|1", text):
            topic = "恋愛"
        elif re.search(r"相性|2", text):
            topic = "相性"
        elif re.search(r"仕事|生き方|3", text):
            topic = "仕事・生き方"
        elif re.search(r"性格|本質|4", text):
            topic = "性格・本質"
        elif re.search(r"手相|5", text):
            reply(event, "手相鑑定は画像を送ってください📷")
            return
        else:
            reply(event, "番号またはメニュー名で選んでくださいね✨")
            return

        state["topic"] = topic
        state["phase"] = "hearing"
        reply(
            event,
            f"{topic}について鑑定しますね。\n\n"
            "状況を把握するために【3つだけ】教えてください。\n\n"
            "① 今いちばん気になっていること\n"
            "② いつ頃からモヤモヤしていますか？\n"
            "③ 最終的にどうなれたら理想ですか？\n\n"
            "まとめて送っても、1つずつでも大丈夫です。"
        )
        return

    # ---------- ヒアリング ----------
    if state["phase"] == "hearing":
        state["answers"].append(text)

        if len(state["answers"]) < 3:
            reply(event, f"ありがとうございます✨\n（あと {3 - len(state['answers'])} つです）")
            return

        # 無料鑑定
        result = generate_fortune(state["topic"], state["answers"], deep=False)
        reply(event, result)

        state["free_done"] = True
        state["phase"] = "paid_guide"

        # 🔽 必ず有料案内を出す
        reply(
            event,
            "ここから先は【有料鑑定】になります。\n\n"
            "番号かプラン名で選んでください👇\n"
            "1️⃣ ライト\n"
            "2️⃣ シルバー\n"
            "3️⃣ ゴールド\n\n"
            "迷う場合は「おすすめ」と送ってください。"
        )
        return

    # ---------- 有料プラン案内 ----------
    if state["phase"] == "paid_guide":
        if re.search(r"1|ライト", text):
            send_light(event)
        elif re.search(r"2|シルバー", text):
            send_silver(event)
        elif re.search(r"3|ゴールド", text):
            send_gold(event)
        elif re.search(r"おすすめ", text):
            reply(
                event,
                "今の状況をしっかり整えたいなら【シルバー】がおすすめです✨\n"
                "継続的に流れを見られるので安心感があります。"
            )
            send_silver(event)
        else:
            reply(event, "番号・プラン名・おすすめ のいずれかで送ってください✨")
        return

# =========================
# メニュー表示
# =========================
def send_menu(event):
    reply(
        event,
        "🔮 運命ナビ占い・フォーチュンへようこそ ✨\n\n"
        "番号で選んでください👇\n"
        "1️⃣ 恋愛\n"
        "2️⃣ 相性\n"
        "3️⃣ 仕事・生き方\n"
        "4️⃣ 性格・本質\n"
        "5️⃣ 手相（画像送信）\n\n"
        "まずは【無料鑑定1回】受けられます🌙"
    )

# =========================
# プラン案内
# =========================
def send_light(event):
    reply(
        event,
        "✨ライトプラン（2,000円）\n"
        "・1テーマを丁寧に鑑定\n\n"
        "PayPay表示名が【paypay-◯◯】の形になるよう設定し、\n"
        "お支払い後に「支払いました」と送ってください✨"
    )

def send_silver(event):
    reply(
        event,
        "✨シルバープラン（5,000円）\n"
        "・2週間以内に【3回】鑑定\n\n"
        "PayPay表示名が【paypay-◯◯】の形になるよう設定し、\n"
        "お支払い後に「支払いました」と送ってください✨"
    )

def send_gold(event):
    reply(
        event,
        "✨ゴールドプラン（15,000円）\n"
        "・2週間 相談し放題\n\n"
        "PayPay表示名が【paypay-◯◯】の形になるよう設定し、\n"
        "お支払い後に「支払いました」と送ってください✨"
    )

# =========================
# 占い生成
# =========================
def generate_fortune(topic, answers, deep=False):
    prompt = f"""
あなたは落ち着いた視点で核心を突く占い師です。
スピリチュアルすぎず、現実的で前向きな鑑定を行ってください。

テーマ：{topic}
相談内容：
{answers}

{'有料鑑定なので深く具体的に鑑定してください。' if deep else '無料鑑定なので要点を簡潔に。'}
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return res.choices[0].message.content

# =========================
# 返信共通
# =========================
def reply(event, text):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=text)
    )

# =========================
# 起動
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

