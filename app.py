import os
import requests
from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime

# 環境変数の読み込み
load_dotenv()

# Flaskアプリ初期化
app = Flask(__name__)

# APIキーやSlack認証情報の設定
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
slack_token = os.getenv("SLACK_BOT_TOKEN")
slack_client = WebClient(token=slack_token)
signature_verifier = SignatureVerifier(signing_secret=os.getenv("SLACK_SIGNING_SECRET"))

# Supabaseへの保存関数
def save_to_supabase(data):
    SUPABASE_URL = "https://cqhhqogxlczlxrdpryas.supabase.co"
    SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
    table_name = "messages"

    headers = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "user_name": data["user_name"],
        "text": data["text"],
        "channel_name": data["channel_name"],
        "timestamp": data["timestamp"],
        "user_id": data["user_id"],
        "is_important": data.get("is_important", False),
        "context_id": data.get("context_id", None)
    }

    print("📤 Sending to Supabase:", payload)
    response = requests.post(f"{SUPABASE_URL}/rest/v1/{table_name}", headers=headers, json=[payload])
    print("📥 Supabase response:", response.status_code, response.text)
    return response.status_code

# Slackイベント受信用エンドポイント
@app.route("/slack/events", methods=["POST"])
def slack_events():
    print("🎯 Slackイベント受信！")
    # リクエストの署名検証
    if not signature_verifier.is_valid_request(request.get_data(), request.headers):
        return "Invalid request", 403

    payload = request.json

    # URL検証（最初のみ必要）
    if payload.get("type") == "url_verification":
        return jsonify({"challenge": payload["challenge"]})

    # イベント処理
    if "event" in payload:
        event = payload["event"]
        print("✅ Slack event received:", event)

        # UNIX timestamp → ISO形式に変換
        try:
            ts_float = float(event.get("ts", ""))
            iso_timestamp = datetime.utcfromtimestamp(ts_float).isoformat()
        except:
            iso_timestamp = None

        data_to_save = {
            "user_name": event.get("user", "unknown"),
            "text": event.get("text", ""),
            "channel_name": event.get("channel", "unknown"),
            "timestamp": iso_timestamp,
            "user_id": event.get("user", ""),
            "is_important": False,
            "context_id": event.get("thread_ts", None)
        }

        print("📦 Saving to Supabase with data:", data_to_save)
        save_to_supabase(data_to_save)

        # @ミカさん と呼ばれたときだけ返事
        if event.get("type") == "app_mention":
            user = event["user"]
            text = event["text"]
            channel = event["channel"]

            chat_completion = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "あなたは優しくて賢い社内アシスタント『ミカさん』です。"},
                    {"role": "user", "content": text},
                ]
            )

            answer = chat_completion.choices[0].message.content
            slack_client.chat_postMessage(channel=channel, text=answer)

    return "OK", 200

# Flask起動
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
