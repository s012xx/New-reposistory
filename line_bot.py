import os
import sys
from flask import Flask, request, abort

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

from openai import OpenAI

# =========================
# 環境変数チェック（チェック2対応）
# =========================
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not LINE_CHANNEL_SECRET or not LINE_CHANNEL_ACCESS_TOKEN or not OPENAI_API_KEY:
    print("Error: 環境変数が不足しています。")
    sys.exit(1)

# =========================
# 初期化
# =========================
app = Flask(__name__)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# 状態管理（簡易）
# =========================
user_states = {}  # user_id: {"step": str}

# =========================
# Webhook
# =========================
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

# =========================
# メッセージ処理
# =========================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()

    state = user_states.get(user_id, {"step": "start"})

    # ===== 初回 or リセット =====
    if state["step"] == "start":
        reply = (
            "はじめまして🌙\n"
            "運命ナビ占い・フォーチュンへようこそ。\n\n"
            "ここでは、恋愛・人間関係・仕事・人生の流れについて、\n"
            "必要な部分はやさしく、核心はしっかりお伝えします。\n\n"
            "まずは【無料鑑定】として、\n"
            "以下から気になる番号を送ってください。\n\n"
            "1️⃣ 恋愛\n"
            "2️⃣ 相性・人間関係\n"
            "3️⃣ 仕事・生き方\n"
            "4️⃣ 性格・本質\n"
            "5️⃣ 手相（画像送信）"
        )
        user_states[user_id] = {"step": "free_menu"}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # ===== 無料鑑定：メニュー選択 =====
    if state["step"] == "free_menu":
        reply = (
            "ありがとうございます。\n\n"
            "では無料鑑定に入る前に、\n"
            "状況を把握するために【3つだけ】教えてください。\n\n"
            "① 今いちばん気になっていること\n"
            "② いつ頃からモヤモヤしていますか？\n"
            "③ 最終的にどうなれたら理想ですか？\n\n"
            "まとめて送っても、1つずつでも大丈夫です。"
        )
        user_states[user_id] = {"step": "free_hearing"}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # ===== 無料鑑定：軽めの鑑定 =====
    if state["step"] == "free_hearing":
        reply = (
            "教えてくれてありがとうございます。\n\n"
            "無料鑑定として、今の流れを簡単にお伝えしますね。\n\n"
            "今のあなたは、\n"
            "『本当は分かっているのに決めきれない』\n"
            "そんな状態に入りやすい時期です。\n\n"
            "流れ自体は悪くありませんが、\n"
            "このまま進むと同じテーマで迷いが繰り返されやすくなります。\n\n"
            "ここから先は、\n"
            "✔ なぜその迷いが起きているのか\n"
            "✔ 近い未来に何が動きやすいか\n"
            "✔ 今とるべき選択\n\n"
            "を【本鑑定】で詳しく読み解いていきます。\n\n"
            "続けて詳しく知りたい場合は、\n"
            "次のメッセージでご案内するプランをご確認ください✨"
        )
        user_states[user_id] = {"step": "paid_guide"}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # ===== 有料プラン案内 =====
    if state["step"] == "paid_guide":
        reply = (
            "🔮 有料鑑定プランのご案内です。\n\n"
            "1️⃣ ライト（2,000円）\n"
            "・1テーマを丁寧に鑑定\n"
            "・現状整理＋近い未来の流れ\n\n"
            "2️⃣ シルバー（5,000円 / 2週間・3回）\n"
            "・状況が動いたときに再鑑定OK\n\n"
            "3️⃣ ゴールド（15,000円 / 2週間相談し放題）\n"
            "・恋愛・仕事・人生すべて対応\n\n"
            "番号（1〜3）または\n"
            "「ライト」「シルバー」「ゴールド」と送ってください。\n\n"
            "迷う場合は「おすすめ教えて」でも大丈夫です。"
        )
        user_states[user_id] = {"step": "wait_plan"}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # ===== 本鑑定（文章量アップ版） =====
    if state["step"] == "paid":
        prompt = f"""
あなたは占い分野の指導者・鑑定者です。
以下の条件で本鑑定文を作成してください。

・無料鑑定より明確に深い内容
・占い要素はあるがスピリチュアル過多にしない
・相手の迷いの核心を言語化する
・文章量はしっかり多め
・断定しすぎず、導く語り口

相談内容：
「{user_text}」
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )

        ai_text = response.choices[0].message.content

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=ai_text)
        )
        return
        
