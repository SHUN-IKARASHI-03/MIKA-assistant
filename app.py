import os
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

@app.route("/slack/events", methods=["POST"])
def slack_events():
    # リクエスト検証
    if not signature_verifier.is_valid_request(request.get_data(), request.headers):
        return "Invalid request", 403

    payload = request.json

    # Slack側のURL検証（初回用）
    if payload.get("type") == "url_verification":
        return jsonify({"challenge": payload["challenge"]})

    # イベント処理（@ミカさん）
    if "event" in payload:
        event = payload["event"]
        if event.get("type") == "app_mention":
            user = event["user"]
            text = event["text"]
            channel = event["channel"]

            # ChatGPTへ送信
            chat_completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
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
