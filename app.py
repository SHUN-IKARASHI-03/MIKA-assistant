import os
from flask import Flask, request
from datetime import datetime
from supabase import create_client, Client
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# 環境変数
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BOT_ID = os.getenv("BOT_ID")

# クライアント
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = OpenAI(api_key=OPENAI_API_KEY)

@app.route("/")
def index():
    return "OK", 200

@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.json

    # チャレンジ確認
    if "challenge" in data:
        return data["challenge"]

    if "event" not in data:
        return "No event found", 400

    event = data["event"]
    user_id = event.get("user")
    text = event.get("text", "")
    ts = event.get("ts")
    channel_id = event.get("channel")

    # Bot自身の発言はスキップ
    if user_id == BOT_ID:
        return "OK", 200

    # Slack表示名取得
    user_name = user_id

    # Slack APIで表示名取得（オプションで実装可）

    # Supabaseに記録（ISO形式で日時記録）
    try:
        supabase.table("messages_all").insert({
            "user_name": user_name,
            "text": text,
            "channel": channel_id,
            "timestamp": datetime.fromtimestamp(float(ts)).isoformat()
        }).execute()
        print(f"[LOGGED] {user_name}: {text}")
    except Exception as e:
        print(f"[ERROR] Failed to log to Supabase: {e}")

    return "OK", 200

# ポート指定（Render用）
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
