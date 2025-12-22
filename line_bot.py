import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# ========= 環境変数 =========
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, OPENAI_API_KEY]):
    raise ValueError("環境変数が不足しています。")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

app = Flask(__name__)

# ========= ユーザー状態管理（簡易） =========
user_states = {}

def reset_user(user_id):
    user_states[user_id] = {
        "phase": "free_intro",
        "answers": {},
        "paid": False,
        "plan": None
    }

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

# ========= メッセージ受信 =========
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if user_id not in user_states:
        reset_user(user_id)

    state = user_states[user_id]

    # -------- リセット --------
    if text.lower() in ["リセット", "reset"]:
        reset_user(user_id)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="リセットしました✨ 最初から始めましょう。")
        )
        return

    # -------- 無料鑑定前ヒアリング --------
    if state["phase"] == "free_intro":
        state["phase"] = "free_questions"
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
        return

    if state["phase"] == "free_questions":
        # 回答を蓄積（厳密な判定はしない）
        state["answers"][len(state["answers"]) + 1] = text

        if len(state["answers"]) < 3:
            return  # まだ待つ

        # 無料鑑定（簡易）
        state["phase"] = "free_done"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=(
                    "ありがとうございます✨\n\n"
                    "今の流れを見ると、あなたは「考えすぎて動けなくなる」時期を抜けつつあります。\n"
                    "本音では答えはもう見えているのに、周囲や不安がブレーキをかけている状態。\n\n"
                    "ここから先は、状況に合わせて\n"
                    "・選択肢の整理\n"
                    "・タイミング\n"
                    "・相手（または環境）の本心\n"
                    "を具体的に読み解いていく必要があります。"
                )
            )
        )
        return

    # -------- 有料案内（必ず出す） --------
    if state["phase"] == "free_done":
        state["phase"] = "select_plan"
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
        return

    # -------- プラン選択 --------
    if state["phase"] == "select_plan":
        if text in ["1", "ライト"]:
            state["plan"] = "ライト"
            url = "https://fortune907.base.shop/items/128865860"
        elif text in ["2", "シルバー"]:
            state["plan"] = "シルバー"
            url = "https://fortune907.base.shop/items/128866117"
        elif text in ["3", "ゴールド"]:
            state["plan"] = "ゴールド"
            url = "https://fortune907.base.shop/items/128866188"
        elif text == "おすすめ":
            state["plan"] = "シルバー"
            url = "https://fortune907.base.shop/items/128866117"
        else:
            return

        state["phase"] = "waiting_payment"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=(
                    f"{state['plan']}プランですね✨\n\n"
                    "以下のBASEショップからご購入ください👇\n"
                    f"{url}\n\n"
                    "ご購入後、\n"
                    "「購入しました」\n"
                    "と送ってください。"
                )
            )
        )
        return

    # -------- 購入確認 --------
    if state["phase"] == "waiting_payment":
        if text == "購入しました":
            state["paid"] = True
            state["phase"] = "paid"

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=(
                        "ご購入ありがとうございます✨\n\n"
                        "それでは本鑑定に入ります。\n"
                        "今いちばん深く知りたいテーマを、改めて教えてください。\n\n"
                        "（恋愛／相性／仕事／人生 など、自由でOKです）"
                    )
                )
            )
        return

    # -------- 本鑑定 --------
    if state["phase"] == "paid":
        # ここにOpenAI処理を追加して本鑑定を生成する想定
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=(
                    "本鑑定をお届けします🔮\n\n"
                    "あなたの流れを丁寧に読み解くと、\n"
                    "今は「切り替え直前のタイミング」。\n\n"
                    "これまで我慢してきたこと・後回しにしてきた想いが、\n"
                    "ここから少しずつ現実を動かしていきます。\n\n"
                    "（ここに本鑑定内容が続きます）"
                )
            )
        )
        return

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

