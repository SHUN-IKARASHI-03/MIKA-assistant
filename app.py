import os
import json
from flask import Flask, request
from datetime import datetime
from supabase import create_client, Client
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier
import openai

# 環境変数（Renderの環境設定から取得）
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# 各種初期化
app = Flask(__name__)
slack_client = WebClient(token=SLACK_BOT_TOKEN)
signature_verifier = SignatureVerifier(SLACK_SIGNING_SECRET)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai.api_key = OPENAI_API_KEY

@app.route("/slack/events", methods=["POST"])
def slack_events():
    if not signature_verifier.is_valid_request(request.get_data(), request.headers):
        return "Invalid request signature", 400

    payload = request.json

    # Slackのチャレンジ検証（初回）
    if "challenge" in payload:
        return payload["challenge"]

    event = payload.get("event", {})

    # メッセージイベント処理（Bot自身の発言は除外）
    if event.get("type") == "message" and not event.get("subtype") and not event.get("bot_id"):
        user = event.get("user", "unknown")
        text = event.get("text", "")
        channel = event.get("channel", "")
        timestamp = datetime.fromtimestamp(float(event.get("ts", "0")))

        # Supabaseへ全投稿を記録
        supabase.table("messages_all").insert({
            "user_name": user,
            "text": text,
            "channel": channel,
            "timestamp": timestamp
        }).execute()

        print(f"[LOGGED] {user} @ {channel}: {text}")

        # クエスチョンメッセージに応答（記憶ベース）
        if text.strip().endswith("？") or text.strip().endswith("?"):
            # 過去の投稿から意味のありそうな情報を取得
            all_logs = supabase.table("messages_all").select("text").execute()
            past_texts = "\n".join([row["text"] for row in all_logs.data][-20:])  # 直近20件で制限

            prompt = f"""
            以下は社員たちの会話ログです：
            {past_texts}

            質問：「{text}」
            上記ログの情報を参考に、社員に親切に答えてください。
            情報がない場合は「すみません、まだ記憶にありません」と答えてください。
            """
            
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "あなたは社内AI秘書のミカさんです。Slackの過去会話を参考に社員の質問に答えます。"},
                        {"role": "user", "content": prompt}
                    ]
                )
                reply = response.choices[0].message.content
                slack_client.chat_postMessage(channel=channel, text=reply)

            except Exception as e:
                print(f"[ERROR] OpenAI応答エラー: {str(e)}")

    return "OK", 200

@app.route("/")
def index():
    return "ミカさんは元気に稼働中です！", 200
