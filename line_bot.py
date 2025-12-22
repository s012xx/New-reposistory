from flask import Flask, request, abort
import os
from collections import defaultdict

app = Flask(__name__)

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN, OPENAI_API_KEY]):
    raise RuntimeError("環境変数が不足しています")

BASE_LINKS = {
    "ライト": "https://fortune907.base.shop/items/128865860",
    "シルバー": "https://fortune907.base.shop/items/128866117",
    "ゴールド": "https://fortune907.base.shop/items/128866188"
}

user_state = defaultdict(lambda: {
    "answers": [],
    "free_done": False,
    "plan": None,
    "count": 0
})

FREE_FORTUNE = """無料鑑定をお届けします🔮

あなたの流れを丁寧に読み解くと、今は
「一度立ち止まり、方向を整える大切な節目」。

これまで積み重ねてきた努力や我慢は、
決して間違っていません。
ただ、環境や人の期待に合わせる中で、
本来のあなたの感覚が少し後ろに下がっているようです。

最近、同じことで何度も迷ったり、
答えが分かっているのに決断できない感覚はありませんか？
それは運気が停滞しているのではなく、
「選び直す準備」が整ってきたサインです。

ここから先は、
・どこを手放すと楽になるのか
・今後どんな流れが強まるのか
・選択を誤らないためのポイント
を、より深く読み解く必要があります。

ここから先は【有料鑑定】になります。

番号かプラン名で選んでください👇
1️⃣ ライト
2️⃣ シルバー
3️⃣ ゴールド

迷う場合は「おすすめ」と送ってください。
"""

FULL_FORTUNE = """本鑑定をお届けします🔮

あなたの運命の流れを深く読み解くと、
今は「人生の軸を整え直す転換期」に入っています。

これまでのあなたは、
周囲とのバランスを大切にしながら、
自分の本音を後回しにしてきました。
その姿勢は間違いではありませんが、
今後も同じやり方を続けると、
心だけが先に疲れてしまいます。

今後数ヶ月で重要になるのは、
「全部を守ろうとしないこと」。
あなたが本当に守るべきものは、
人ではなく、あなた自身の感覚です。

現実面では、
・環境の変化
・人間関係の距離感
・役割の見直し
が同時に起こりやすい時期。

ここで無理に答えを急がず、
一つずつ整理することで、
運の流れは自然と好転していきます。

焦らなくて大丈夫。
あなたの選択は、ゆっくりでも確実に
未来を良い方向へ導いていきます。

必要なときに、また「鑑定して」と送ってください。
"""

@app.route("/callback", methods=["POST"])
def callback():
    data = request.json
    user_id = data["user"]
    text = data["message"].strip()

    state = user_state[user_id]

    if text == "リセット":
        user_state[user_id] = {
            "answers": [],
            "free_done": False,
            "plan": None,
            "count": 0
        }
        return "リセットしました"

    if not state["free_done"]:
        if len(state["answers"]) < 3:
            state["answers"].append(text)
            if len(state["answers"]) < 3:
                return "ありがとうございます✨ 残りも教えてください。"
            state["free_done"] = True
            return FREE_FORTUNE

    if text in ["ライト", "シルバー", "ゴールド"]:
        state["plan"] = text
        return f"""【{text}プラン】を選択されました。

こちらからご購入ください👇
{BASE_LINKS[text]}

購入後「購入しました」と送ってください。"""

    if text == "購入しました":
        return "ありがとうございます✨ 鑑定したいタイミングで「鑑定して」と送ってください。"

    if text == "鑑定して":
        if state["plan"] == "ライト" and state["count"] >= 1:
            return END_MESSAGE()
        if state["plan"] == "シルバー" and state["count"] >= 3:
            return END_MESSAGE()
        state["count"] += 1
        return FULL_FORTUNE

    if text == "おすすめ":
        return """今の流れを見る限り、
一度きりよりも、状況に合わせて見直せる
【シルバープラン】が合っています。

無理に決めなくて大丈夫です。
番号かプラン名で選んでください👇
1️⃣ ライト
2️⃣ シルバー
3️⃣ ゴールド"""

    return "必要な場合は「鑑定して」と送ってください。"

def END_MESSAGE():
    return """このプランの鑑定回数は終了しました。

🔮 継続やランクアップも可能です。
1️⃣ ライト
2️⃣ シルバー
3️⃣ ゴールド

おすすめを聞いてもOKです。"""

