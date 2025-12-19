

import os
import base64
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent,
    TextMessage,
    ImageMessage,
    TextSendMessage,
)
from openai import OpenAI

# ==============================
# 環境変数（推奨）
# ==============================
LINE_CHANNEL_SECRET = "a57f15e4aea3dbb3051f89cbb4f9f2e4"
LINE_CHANNEL_ACCESS_TOKEN = "y10fR1TloXSab+7Q3Yn9UtcSpbDQa7N/jdqjW+JkRsT/bNrKtNj1WVbdd8dFQ7Yb/9D39BtiSKvdagiGlo+Oce/HDNTtwOzOAK0+MF6728Jv3zcy0hJ/fRiBPLhuN5Xc/m6SsoSUt0vbIBLzEkiSCQdB04t89/1O/w1cDnyilFU="
OPENAI_API_KEY = os.getenv("OPENAI=API=KEY","")

if not LINE_CHANNEL_SECRET or not LINE_CHANNEL_ACCESS_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError(
        "環境変数が不足しています。"
        " LINE_CHANNEL_SECRET / LINE_CHANNEL_ACCESS_TOKEN / OPENAI_API_KEY を設定してください。"
    )

# ==============================
# BASE 商品URL（あなたのURLを固定で入れてOK）
# ==============================
BASE_URL_LIGHT = "https://fortune907.base.shop/items/128865860"
BASE_URL_SILVER = "https://fortune907.base.shop/items/128866117"
BASE_URL_GOLD = "https://fortune907.base.shop/items/128866188"

# ==============================
# 状態管理（簡易：メモリ方式）
# ※PC再起動で消える。あとで必要なら永続化も可能。
# ==============================
user_state = {}       # "menu" / "hearing" / "free_done" / "paid"
user_free_used = {}   # 無料鑑定を使ったか
user_theme = {}       # "love" / "relation" / "job" / "personality"
user_answers = {}     # ヒアリング回答
user_plan = {}        # "light" / "silver" / "gold"

# OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# Flask & LINE
app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ==============================
# Botの最初の案内（メニュー）
# ==============================
MAIN_MENU = (
    "🌙 運命ナビ占いフォーチュンです。\n\n"
    "ここでは、恋愛・相性・仕事・人生のテーマを\n"
    "やさしく、必要なところははっきりとナビゲートします。\n\n"
    "まずは、気になるメニューの番号を送ってくださいね。\n\n"
    "1️⃣ 恋愛\n"
    "2️⃣ 相性\n"
    "3️⃣ 仕事・生き方\n"
    "4️⃣ 性格・本質\n"
    "5️⃣ 手相（画像送信OK）\n\n"
    "すべての方に【無料で1回、本鑑定】をご利用いただけます✨"
)

# ==============================
# ヒアリング質問
# ==============================
QUESTION_SETS = {
    "love": {
        "intro": "恋愛の鑑定に入る前に、まず3つだけ質問させてくださいね。",
        "questions": [
            "① 今、恋愛で一番気になっていることは何ですか？",
            "② 相手（または状況）との関係性を教えてください。",
            "③ あなたが望んでいる理想の未来はどんな形ですか？",
        ],
    },
    "relation": {
        "intro": "相性鑑定をより深くするため、2つ教えてください。",
        "questions": [
            "① お相手との現在の関係を教えてください。",
            "② その相手とどうなりたいと感じていますか？",
        ],
    },
    "job": {
        "intro": "仕事・生き方をみる前に、2つ質問させてください。",
        "questions": [
            "① 今、仕事で抱えている悩みや課題は何ですか？",
            "② あなたが本当はどう働きたいかを教えてください。",
        ],
    },
    "personality": {
        "intro": "性格・本質をみる前に、1つだけ教えてください。",
        "questions": [
            "① 今、自分自身について特に気になる部分はどこですか？",
        ],
    },
}

# ==============================
# 有料プラン案内（短 → 詳細は次メッセージ）
# ==============================
PAID_GUIDE_SHORT = (
    "🔮 無料鑑定はここまでとなります✨\n\n"
    "続けて詳しく知りたい場合は、有料プランをご利用ください。\n"
    "「1」「2」「3」または「ライト」「シルバー」「ゴールド」で選べます。\n\n"
    "1️⃣ ライト（2,000円）\n"
    "2️⃣ シルバー（5,000円 / 2週間・3回）\n"
    "3️⃣ ゴールド（15,000円 / 2週間相談し放題）\n\n"
    "迷う場合は「おすすめ教えて」と送ってください😊"
)

def paid_guide_long() -> str:
    return (
        "【プラン詳細】\n"
        "1️⃣ ライト（2,000円）\n"
        "・1テーマの鑑定をしっかり丁寧に\n"
        "・現状整理＋近い未来の流れを知りたい人向け\n\n"
        "2️⃣ シルバー（5,000円 / 2週間・3回鑑定）\n"
        "・2週間のあいだに合計3回まで鑑定OK\n"
        "・日を空けてもOK、状況が動いたときに再鑑定可能\n"
        "・一度の鑑定では不安が消えない人に最適\n\n"
        "3️⃣ ゴールド（15,000円 / 2週間相談し放題）\n"
        "・2週間ずっと相談し放題\n"
        "・恋愛も仕事も人生もまとめてOK\n"
        "・しっかり整えたい、本気で変わりたい人向け\n\n"
        "選ぶときは「1」「2」「3」または「ライト」「シルバー」「ゴールド」でOKです🌙"
    )

# ==============================
# BASE購入案内（各プラン）
# ==============================
def base_checkout_text(plan: str) -> str:
    if plan == "light":
        return (
            "✨ライトプラン（2,000円）をお選びいただきありがとうございます。\n\n"
            "【お支払い方法】\n"
            "以下のBASE商品ページからご購入ください👇\n"
            f"{BASE_URL_LIGHT}\n\n"
            "ご購入が完了しましたら「購入しました」と送ってください✨"
        )
    if plan == "silver":
        return (
            "✨シルバープラン（5,000円 / 2週間・3回）をお選びいただきありがとうございます。\n\n"
            "【お支払い方法】\n"
            "以下のBASE商品ページからご購入ください👇\n"
            f"{BASE_URL_SILVER}\n\n"
            "ご購入が完了しましたら「購入しました」と送ってください✨"
        )
    if plan == "gold":
        return (
            "✨ゴールドプラン（15,000円 / 2週間相談し放題）をお選びいただきありがとうございます。\n\n"
            "【お支払い方法】\n"
            "以下のBASE商品ページからご購入ください👇\n"
            f"{BASE_URL_GOLD}\n\n"
            "ご購入が完了しましたら「購入しました」と送ってください✨"
        )
    return "プランが選択できませんでした。もう一度「1〜3」で選んでください🙏"

# ==============================
# 「購入しました」後の即スタート文
# ==============================
PURCHASED_START_TEXT = (
    "ご購入ありがとうございます✨\n"
    "確認できました。\n\n"
    "ここから本鑑定をスタートします🌙\n"
    "まず、今回いちばん見たいテーマを教えてください。\n\n"
    "・恋愛／相性／仕事・生き方／性格・本質／手相（画像OK）\n"
    "どれでも大丈夫です。\n\n"
    "状況を把握するために、以下の3つも一緒に送ってくださいね。\n"
    "① いまの状況（いつ頃から・何が起きているか）\n"
    "② 気になっている相手や関係性（いれば）\n"
    "③ どうなれたら安心できそうか（理想）"
)

# ==============================
# OpenAI テキスト鑑定
# ==============================
def ai_reply(prompt: str) -> str:
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return res.choices[0].message.content

# ==============================
# OpenAI 手相（画像）
# ==============================
def ai_palm_reading(image_bytes: bytes) -> str:
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    image_url = f"data:image/jpeg;base64,{encoded}"

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text":
                        "この手相の写真から、性格・過去・現在・未来の運勢を、"
                        "やさしく寄り添いながらも必要なところははっきり伝える形で説明してください。"
                        "恋愛運・仕事運・金運・総合運も入れてください。"
                    },
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
    )
    return res.choices[0].message.content

# ==============================
# Webhook
# ==============================
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

# ==============================
# テキスト処理
# ==============================
@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # 初回
    if user_id not in user_state:
        user_state[user_id] = "menu"
        user_free_used[user_id] = False
        line_bot_api.reply_message(event.reply_token, TextSendMessage(MAIN_MENU))
        return

    # すでに有料（鑑定中）
    if user_state.get(user_id) == "paid":
        prompt = (
            "あなたは占い師です。やさしく寄り添いながらも、必要なところははっきり伝えてください。\n"
            f"ユーザーの相談: {text}"
        )
        reply_text = ai_reply(prompt)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(reply_text))
        return

    # 無料鑑定済み → 有料案内/購入フロー
    if user_free_used.get(user_id):
        # 購入した（即スタート）
        if "購入しました" in text:
            user_state[user_id] = "paid"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(PURCHASED_START_TEXT))
            return

        # おすすめ
        if "おすすめ" in text:
            msg = (
                "おすすめを整理しますね✨\n\n"
                "・まず1つのテーマをしっかり見たい → 1️⃣ライト\n"
                "・2週間で3回、状況の変化も見ながら整えたい → 2️⃣シルバー\n"
                "・恋愛も仕事も人生もまとめて深く相談したい → 3️⃣ゴールド\n\n"
                "番号（1〜3）かプラン名を送ってください🌙"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(msg))
            return

        # プラン選択
        if text in ["1", "ライト", "ライトプラン"]:
            user_plan[user_id] = "light"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(base_checkout_text("light")))
            return

        if text in ["2", "シルバー", "シルバープラン"]:
            user_plan[user_id] = "silver"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(base_checkout_text("silver")))
            return

        if text in ["3", "ゴールド", "ゴールドプラン"]:
            user_plan[user_id] = "gold"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(base_checkout_text("gold")))
            return

        # それ以外は案内を再提示（短→長の2通）
        line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(PAID_GUIDE_SHORT), TextSendMessage(paid_guide_long())],
        )
        return

    # メニュー選択（無料鑑定へ）
    if user_state.get(user_id) == "menu":
        if text == "5":
            msg = (
                "手相鑑定ですね✨\n\n"
                "手のひら全体が写るように、明るい場所で撮って送ってください。\n"
                "利き手・反対の手、どちらでもOKです。"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(msg))
            return

        theme_map = {"1": "love", "2": "relation", "3": "job", "4": "personality"}
        if text not in theme_map:
            line_bot_api.reply_message(event.reply_token, TextSendMessage("数字で選んでください✨\n\n" + MAIN_MENU))
            return

        theme = theme_map[text]
        user_theme[user_id] = theme
        user_state[user_id] = "hearing"
        user_answers[user_id] = []

        intro = QUESTION_SETS[theme]["intro"]
        q1 = QUESTION_SETS[theme]["questions"][0]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(f"{intro}\n\n{q1}"))
        return

    # ヒアリング中
    if user_state.get(user_id) == "hearing":
        theme = user_theme.get(user_id)
        questions = QUESTION_SETS[theme]["questions"]

        user_answers[user_id].append(text)

        # 次の質問
        if len(user_answers[user_id]) < len(questions):
            next_q = questions[len(user_answers[user_id])]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(next_q))
            return

        # 無料鑑定 実行
        prompt = (
            "あなたは占い師です。やさしく寄り添いながらも、必要なところははっきり伝えてください。\n"
            "以下の情報をもとに、現状→原因→近い未来の流れ→具体的なアドバイスの順で占ってください。\n\n"
            f"テーマ: {theme}\n"
            f"ユーザー回答: {user_answers[user_id]}\n"
        )
        result = ai_reply(prompt)

        user_free_used[user_id] = True
        user_state[user_id] = "free_done"

        line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(result), TextSendMessage(PAID_GUIDE_SHORT), TextSendMessage(paid_guide_long())],
        )
        return

    # 迷子救済
    line_bot_api.reply_message(event.reply_token, TextSendMessage(MAIN_MENU))

# ==============================
# 画像処理（手相）
# ==============================
@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id

    message_content = line_bot_api.get_message_content(event.message.id)
    image_bytes = message_content.content

    result = ai_palm_reading(image_bytes)

    # 無料扱い：一回見たら無料消費
    if user_id not in user_free_used:
        user_free_used[user_id] = False
    user_free_used[user_id] = True
    user_state[user_id] = "free_done"

    line_bot_api.reply_message(
        event.reply_token,
        [TextSendMessage(result), TextSendMessage(PAID_GUIDE_SHORT), TextSendMessage(paid_guide_long())],
    )

# ==============================
# 起動
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
    
