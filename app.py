import os
import json
import traceback
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from datetime import datetime
from supabase import create_client, Client
from openai import OpenAI
from datetime import datetime

# 現在の日時（日本時間にしたいなら +9時間してもOK）
now = (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S JST")

# 環境変数の読み込み
load_dotenv()

# Flask アプリケーションの設定
app = Flask(__name__)

# 環境変数
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BOT_ID = os.getenv("BOT_ID")  # SlackのBot ID（Uで始まる）

# クライアント初期化
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Slack返信用関数
def send_slack_message(channel, message):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}"
    }
    data = {
        "channel": channel,
        "text": message
    }
    response = requests.post("https://slack.com/api/chat.postMessage", headers=headers, data=json.dumps(data))
    if not response.ok:
        print(f"[❌ ERROR] Failed to send message to Slack: {response.text}")

@app.route("/", methods=["GET"])
def home():
    return "ミカさん起動中（v1）", 200

@app.route("/slack/events", methods=["POST"])
def slack_events():
    try:
        payload = request.json

        # Slackの challenge（初回検証用）
        if "challenge" in payload:
            return jsonify({"challenge": payload["challenge"]})

        event = payload.get("event", {})
        if not event:
            return "No event in payload", 400

        if event.get("subtype") == "bot_message" or event.get("bot_id") or event.get("user") == BOT_ID:
            return "Ignored bot message", 200

        user_id = event.get("user")
        text = event.get("text", "")
        channel = event.get("channel")
        ts = event.get("ts")

        if not user_id or not text:
            return "No user_id or text", 400

        try:
            timestamp = datetime.fromtimestamp(float(ts)).isoformat()
        except:
            timestamp = datetime.utcnow().isoformat()

        # Supabase に記録
        data = {
            "user_id": user_id,
            "text": text.strip(),
            "channel": channel,
            "timestamp": timestamp
        }

        supabase.table("messages_all").insert(data).execute()
        print(f"[✅ LOGGED] {user_id} @ {channel} → '{text}'")

        # ChatGPT に問い合わせて返信生成
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": f"あなたは社内アシスタントの美香さんです。現在の日時は {now} です。"},
                {"role": "user", "content": text}
            ]
        )
        reply_text = response.choices[0].message.content.strip()

        # Slack に返信
        send_slack_message(channel, reply_text)
        print(f"[📣 REPLIED] → {reply_text}")

        return "OK", 200

    except Exception as e:
        print(f"[❌ ERROR] Exception in /slack/events: {e}")
        traceback.print_exc()
        return "Internal Server Error", 500

# Render用のポート起動
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
