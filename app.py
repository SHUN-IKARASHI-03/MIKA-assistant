import os
import openai
from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
slack_token = os.getenv("SLACK_BOT_TOKEN")
openai.api_key = os.getenv("OPENAI_API_KEY")
slack_client = WebClient(token=slack_token)
signature_verifier = SignatureVerifier(signing_secret=os.getenv("SLACK_SIGNING_SECRET"))

@app.route("/slack/events", methods=["POST"])
def slack_events():
    if not signature_verifier.is_valid_request(request.get_data(), request.headers):
        return "Invalid request", 403

    payload = request.json

        # SlackのURL確認用 challenge 応答
    if "type" in payload and payload["type"] == "url_verification":
        return jsonify({"challenge": payload["challenge"]})
        
    if "event" in payload:
        event = payload["event"]
        if event.get("type") == "app_mention":
            user = event["user"]
            text = event["text"]
            channel = event["channel"]

            prompt = text.replace(f"<@{event['bot_id']}>", "").strip()

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "あなたは親切で賢い社内アシスタント『ミカさん』です。"},
                    {"role": "user", "content": prompt},
                ],
            )

            answer = response["choices"][0]["message"]["content"]
            slack_client.chat_postMessage(channel=channel, text=answer)

    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
