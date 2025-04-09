import os
import requests
from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier
from dotenv import load_dotenv
from openai import OpenAI

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
    SUPABASE_URL = "https://cqhhqogxlczlxrdpryas.supabase.co"  # ← あなたのURLに変更
    SUPABASE_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNxaGhxb2d4bGN6bHhyZHByeWFzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQxNjQxMDgsImV4cCI6MjA1OTc0MDEwOH0.Hbb0yPOMKY3sDgWLhoJOy2QR5zCnw1ozRQCXDSd3hmA"            # ← あなたのanonキーに変更
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

    print("📤 Sending to Supabase:", payload)  # ← ログ出力追加
    response = requests.post(f"{SUPABASE_URL}/rest/v1/{table_name}", headers=headers, json=[payload])
    print("📥 Supabase response:", response.status_code, response.text)  # ← レスポンス内容も出力
    return response.status_code

    response = requests.post(f"{SUPABASE_URL}/rest/v1/{table_name}", headers=headers, json=[payload])
    print("Supabase response:", response.status_code, response.text)
    return response.status_code

# Slackイベント受信エンドポイント
@app.route("/slack/events", methods=["POST"])
def slack_events():
    # リクエスト検証
    if not signature_verifier.is_valid_request(request.get_data(), request.headers):
        return "Invalid request", 403

    payload = request.json

    # SlackのURL検証（初回用）
    if payload.get("type") == "url_verification":
        return jsonify({"challenge": payload["challenge"]})

    # Slackイベント処理
    if "event" in payload:
        event = payload["event"]

        # 🔸 Supabaseに記録
        data_to_save = {
            "user_name": event.get("user", "unknown"),
            "text": event.get("text", ""),
            "channel_name": event.get("channel", "unknown"),
            "timestamp": event.get("ts", ""),
            "user_id": event.get("user", ""),
            "is_important": False,
            "context_id": event.get("thread_ts", None)
        }
        save_to_supabase(data_to_save)

        # 🔸 @ミカさん にメンションされた場合のみ応答
        if event.get("type") == "app_mention":
            user = event["user"]
            text = event["text"]
            channel = event["channel"]

            # ChatGPTに送信
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

# Renderで起動するためのポート指定
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
