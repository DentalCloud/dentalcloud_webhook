
import os
import tempfile
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, ImageMessage, TextSendMessage

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

load_dotenv()
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
app = Flask(__name__)

def create_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        "drive_service.json",
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

drive_service = create_drive_service()

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    message_content = line_bot_api.get_message_content(event.message.id)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tf:
        for chunk in message_content.iter_content():
            tf.write(chunk)
        temp_file_path = tf.name

    file_metadata = {
        "name": os.path.basename(temp_file_path),
        "parents": [DRIVE_FOLDER_ID]
    }
    media = MediaFileUpload(temp_file_path, mimetype="image/jpeg")
    uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()

    drive_service.permissions().create(
        fileId=uploaded_file["id"],
        body={"type": "anyone", "role": "reader"},
    ).execute()
    file_link = f"https://drive.google.com/uc?id={uploaded_file['id']}"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"圖片已上傳成功：\n{file_link}")
    )

    os.remove(temp_file_path)
