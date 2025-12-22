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

# ========= 初期化 =========
app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ========= プラン定義 =========
PLAN_INFO = {
    "light": {
        "name": "ライト",
        "limit": 1,
        "url": "https://fortune907.base.shop/items/128865860"
    },
    "silver": {
        "name": "シルバー",
        "limit": 3,
        "url": "https://fortune907.base.shop/items/128866117"
    },
    "gold": {
        "name": "ゴールド",
        "limit": None,
        "url": "https://fortune907.base.shop/items/128866188"
    }
}

# ========= ユーザー状態（簡易） =========
user_states = {}

def get_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = {
            "phase": "ask_questions",
            "answers": {},
            "plan": None,
            "used_count": 0,
            "waiting_purchase": False
        }
    return user_states[user_id]

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

# ========= メッセージ処理 =========
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    state = get_state(user_id)

    # ===== リセット =====
    if text.lower() in ["リセット", "reset"]:
        user_states.pop(user_id, None)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="状態をリセットしました。最初から始めます🔮")
        )
        return

    # ===== 質問フェーズ =====
    if state["phase"] == "ask_questions":
        if not state["answers"]:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=
                "状況を把握するために【3つだけ】教えてください。\n\n"
                "① 今いちばん気になっていること\n"
                "② いつ頃からモヤモヤしていますか？\n"
                "③ 最終的にどうなれたら理想ですか？\n\n"
                "まとめて送っても、1つずつでも大丈夫です✨"
                )
            )
            state["answers"]["raw"] = text
            return
        else:
            state["answers"]["raw"] += "\n" + text

            # 簡易的に3項目揃ったと判断
            if len(state["answers"]["raw"].split("\n")) < 3:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="ありがとうございます✨ 残りも教えてください。")
                )
                return

            # 無料鑑定
            free_text = (
                "無料鑑定をお届けします🔮\n\n"
                "あなたの流れを見ると、今は\n"
                "『一度立ち止まり、方向を整える時期』。\n\n"
                "気持ちの奥ではもう答えが見えているのに、\n"
                "現実とのズレに迷いが出やすいタイミングです。\n\n"
                "ただ、これは停滞ではありません。\n"
                "次に進むための“準備期間”であり、\n"
                "ここで選択を誤らなければ流れは大きく好転します。\n\n"
                "ここから先は、より深く読み解くことで\n"
                "具体的な行動指針や時期まで見えてきます。"
            )

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=free_text)
            )

            state["phase"] = "select_plan"
            return

    # ===== プラン選択 =====
    if state["phase"] == "select_plan":
        if "おすすめ" in text:
            reply = (
                "おすすめはこちらです👇\n\n"
                "・じっくり状況を深掘りしたい → シルバー\n"
                "・継続的に相談したい → ゴールド\n\n"
                "番号かプラン名で選んでください✨"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        if "ライト" in text or text == "1":
            plan = "light"
        elif "シルバー" in text or text == "2":
            plan = "silver"
        elif "ゴールド" in text or text == "3":
            plan = "gold"
        else:
            return

        state["plan"] = plan
        state["waiting_purchase"] = True
        info = PLAN_INFO[plan]

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=
            f"ここから先は【有料鑑定】になります。\n\n"
            f"【{info['name']}プラン】はこちらからご購入ください👇\n"
            f"{info['url']}\n\n"
            "購入後に【購入しました】と送ってください✨"
            )
        )
        return

    # ===== 購入確認 =====
    if state["waiting_purchase"]:
        if "購入しました" in text:
            state["waiting_purchase"] = False
            state["phase"] = "waiting_request"
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=
                "ありがとうございます✨\n\n"
                "鑑定したい内容があるときに\n"
                "【鑑定して】と送ってください🔮"
                )
            )
        return

    # ===== 鑑定待ち =====
    if state["phase"] == "waiting_request":
        if "鑑定して" not in text:
            return

        # 回数チェック
        limit = PLAN_INFO[state["plan"]]["limit"]
        if limit is not None and state["used_count"] >= limit:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=
                "今回のプランの鑑定回数は終了しました🔮\n\n"
                "継続・ランクアップをご希望の場合は\n"
                "もう一度プランを選んでください👇\n\n"
                "1️⃣ ライト\n2️⃣ シルバー\n3️⃣ ゴールド\n\n"
                "番号かプラン名で送ってください✨"
                )
            )
            state["phase"] = "select_plan"
            return

        # 本鑑定
        state["used_count"] += 1
        main_text = (
            "本鑑定をお届けします🔮\n\n"
            "あなたは今、人生の流れが\n"
            "『次の段階へ移る直前』にいます。\n\n"
            "これまで我慢してきたこと、\n"
            "飲み込んできた感情は、\n"
            "ここで無視すると後悔に変わりやすいですが、\n"
            "正しく向き合えば“選択する力”に変わります。\n\n"
            "大切なのは、周囲の期待より\n"
            "あなた自身の違和感を信じること。\n\n"
            "焦らず、一つずつ整えていけば\n"
            "運命の流れは確実に好転していきます。"
        )

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=main_text))
        return


# ========= 起動 =========
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
