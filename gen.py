import random
import json
import time
import websockets
import asyncio
import os
import mimetypes
import requests
import base64
from google import genai
from google.genai import types
import uuid
import threading

########## CONSTANTS ##########
ID = "id"
NAME = "name"
USERNAME = "username"
PASSWORD = "password"
ROOM = "room"
TYPE = "type"
ROLE = "role"
HANDLER = "handler"
ALLOWED_CHARS = "0123456789abcdefghijklmnopqrstuvwxyz"

SOCKET_URL = "wss://chatp.net:5333/server"
URL = "url"
MSG_BODY = "body"
MSG_FROM = "from"
MSG_TO = "to"
MSG_TYPE_TXT = "text"
MSG_TYPE_IMG = "image"
MSG_TYPE_AUDIO = "audio"
MSG_URL = "url"
MSG_LENGTH = "length"
HANDLER_PROFILE_UPDATE = "profile_update"
HANDLER_LOGIN = "login"
HANDLER_LOGIN_EVENT = "login_event"
HANDLER_ROOM_JOIN = "room_join"
HANDLER_ROOM_LEAVE = "room_leave"
HANDLER_ROOM_EVENT = "room_event"
HANDLER_ROOM_MESSAGE = "room_message"
EVENT_TYPE_SUCCESS = "success"

BOT_ID = "bot"
BOT_PWD = "wldss123wldss1992"
GROUP_TO_INIT_JOIN = "ورق🤍🩷الورد"
GEMINI_API_KEY = "AIzaSyDskdaBm_GngJdJHLONHdhSDK7j2GvvPh4"
IMGBB_API_KEY = "1bc2faeed622d261210c9540beaa2d95"

DATA_DIR = "data"
USAGE_FILE = os.path.join(DATA_DIR, "usage.json")
BOTS_FILE = os.path.join(DATA_DIR, "child_bots.json")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
if not os.path.exists(USAGE_FILE):
    with open(USAGE_FILE, "w") as file:
        json.dump({}, file)
if not os.path.exists(BOTS_FILE):
    with open(BOTS_FILE, "w") as file:
        json.dump([], file)

# Store active child bots
CHILD_BOTS = {}
CHILD_BOT_SOCKETS = {}

########## HELPERS ##########
def gen_random_str(length):
    return ''.join(random.choice(ALLOWED_CHARS) for _ in range(length))

def load_json(path):
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)

def reset_usage():
    today = time.strftime("%Y-%m-%d")
    usage = load_json(USAGE_FILE)
    if usage.get("__date") != today:
        usage = {"__date": today}
        save_json(USAGE_FILE, usage)
    return usage

# =====================================
# CHILD BOT FUNCTIONS
# =====================================

async def create_child_bot(owner, room, username, password, main_ws):
    """Create a new child bot"""
    try:
        # Check if bot already exists in this room
        if room in CHILD_BOTS:
            await send_pm(main_ws, owner, f"""⚠️ *Bot already exists in this room!* ⚠️

📖 A bot is already active in `{room}`
🗑️ Please stop it first or use another room.

━━━━━━━━━━━━━━━━━━━━━
⚠️ *يوجد بوت نشط في هذه الغرفة!* ⚠️

📖 بوت يعمل بالفعل في `{room}`
🗑️ الرجاء إيقافه أولاً أو استخدام غرفة أخرى""")
            return False

        await send_pm(main_ws, owner, f"""🔨 *Creating bot... / جاري إنشاء البوت...* 🔨

📖 Please wait a moment...
📖 الرجاء الانتظار لحظة...

👤 Username: {username}
🏠 Room: {room}""")

        # Start child bot as a separate task
        task = asyncio.create_task(run_child_bot(room, username, password, owner, main_ws))
        
        CHILD_BOTS[room] = {
            "room": room,
            "username": username,
            "password": password,
            "owner": owner,
            "task": task,
            "created": time.time()
        }
        
        # Save to storage
        bots = load_json(BOTS_FILE, [])
        bots = [b for b in bots if b.get("room") != room]
        bots.append({
            "room": room,
            "username": username,
            "password": password,
            "owner": owner
        })
        save_json(BOTS_FILE, bots)
        
        print(f"[BOT CONNECTED] {username} -> {room}")
        
        await send_pm(main_ws, owner, f"""✅ *BOT CREATED SUCCESSFULLY!* ✅

━━━━━━━━━━━━━━━━━━━━━
📖 *English:* 🇬🇧
🏠 Room: `{room}`
👤 Bot: `{username}`
🔐 Status: Connected & Active ✨

━━━━━━━━━━━━━━━━━━━━━
📖 *العربية:* 🇸🇦
🏠 الغرفة: `{room}`
👤 البوت: `{username}`
🔐 الحالة: متصل ونشط ✨

━━━━━━━━━━━━━━━━━━━━━
💡 Send `help` or `مساعدة` for more commands""")
        
        return True
        
    except Exception as e:
        print(f"[CREATE BOT ERROR] {e}")
        await send_pm(main_ws, owner, f"""💥 *Bot crashed / تعطل البوت* 💥

📖 An error occurred while creating the bot.
🔄 Please try again later.

━━━━━━━━━━━━━━━━━━━━━
📖 حدث خطأ أثناء إنشاء البوت.
🔄 الرجاء المحاولة مرة أخرى لاحقًا.""")
        return False

async def run_child_bot(room, username, password, owner, main_ws):
    """Run a child bot instance"""
    try:
        async with websockets.connect(SOCKET_URL, ssl=True) as ws:
            # Login
            login_payload = {
                HANDLER: HANDLER_LOGIN,
                ID: gen_random_str(20),
                USERNAME: username,
                PASSWORD: password
            }
            await ws.send(json.dumps(login_payload, ensure_ascii=False))
            
            # Wait for login success
            while True:
                try:
                    payload = await asyncio.wait_for(ws.recv(), timeout=10)
                    data = json.loads(payload)
                    if data.get(HANDLER) == HANDLER_LOGIN_EVENT:
                        if data.get(TYPE) == EVENT_TYPE_SUCCESS:
                            print(f"[CHILD BOT] {username} logged in successfully")
                            # Join the room
                            join_payload = {
                                HANDLER: HANDLER_ROOM_JOIN,
                                ID: gen_random_str(20),
                                NAME: room
                            }
                            await ws.send(json.dumps(join_payload, ensure_ascii=False))
                            await send_pm(main_ws, owner, f"✅ Bot `{username}` joined room `{room}` successfully! 🎉")
                            break
                        else:
                            print(f"[CHILD BOT] {username} login failed")
                            await send_pm(main_ws, owner, f"❌ Bot `{username}` failed to login. Check credentials! 🔐")
                            return
                except asyncio.TimeoutError:
                    print(f"[CHILD BOT] {username} login timeout")
                    await send_pm(main_ws, owner, f"⏰ Bot `{username}` login timeout! ⏰")
                    return
            
            CHILD_BOT_SOCKETS[room] = ws
            
            # Keep child bot alive and handle messages
            async for message in ws:
                try:
                    data = json.loads(message)
                    if data.get(HANDLER) == HANDLER_ROOM_EVENT:
                        await handle_child_bot_message(data, room, username, ws)
                except json.JSONDecodeError:
                    continue
                    
    except Exception as e:
        print(f"[CHILD BOT ERROR] {username}: {e}")
        await send_pm(main_ws, owner, f"🔴 Bot `{username}` disconnected! 🔴")

async def handle_child_bot_message(data, bot_room, bot_username, ws):
    """Handle incoming messages for child bot"""
    try:
        if MSG_BODY not in data:
            return
        
        msg = data[MSG_BODY]
        frm = data.get(MSG_FROM, "")
        room = data.get(ROOM, "")
        
        # Only respond to commands in its own room
        if room != bot_room:
            return
        
        # Handle AI image generation for child bot
        if msg.startswith("rsm "):
            usage = reset_usage()
            prompt = msg[4:].strip()
            if usage.get(frm, 0) < 100:
                await send_group_msg(ws, room, f"🎨 Generating image for: '{prompt}'... ⏳")
                file = await generate_image(prompt)
                if file:
                    url = upload_to_imgbb(file)
                    if url:
                        await send_group_msg_image(ws, room, url)
                        usage[frm] = usage.get(frm, 0) + 1
                        save_json(USAGE_FILE, usage)
                    else:
                        await send_group_msg(ws, room, "🔴 Failed to upload image. Please try again later.")
                else:
                    await send_group_msg(ws, room, "🔴 Failed to generate image. Please try a different prompt.")
            else:
                await send_group_msg(ws, room, "⛔ You've reached your daily limit! Please try again tomorrow! 🌙")
                
    except Exception as e:
        print(f"[CHILD BOT MESSAGE ERROR] {e}")

async def send_group_msg(ws, room, msg):
    payload = {
        HANDLER: HANDLER_ROOM_MESSAGE,
        ID: gen_random_str(20),
        ROOM: room,
        TYPE: MSG_TYPE_TXT,
        URL: "",
        MSG_BODY: msg,
        MSG_LENGTH: ""
    }
    await ws.send(json.dumps(payload, ensure_ascii=False))

async def send_group_msg_image(ws, room, url):
    payload = {
        HANDLER: HANDLER_ROOM_MESSAGE,
        ID: gen_random_str(20),
        ROOM: room,
        TYPE: MSG_TYPE_IMG,
        MSG_URL: url,
        MSG_BODY: "",
        MSG_LENGTH: ""
    }
    await ws.send(json.dumps(payload, ensure_ascii=False))

async def generate_image(prompt):
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        model = "gemini-2.0-flash-preview-image-generation"
        contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
        config = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"])
        
        for chunk in client.models.generate_content_stream(model=model, contents=contents, config=config):
            part = chunk.candidates[0].content.parts[0]
            if part.inline_data:
                ext = mimetypes.guess_extension(part.inline_data.mime_type) or ".png"
                file_name = f"image_{int(time.time())}{ext}"
                with open(file_name, "wb") as f:
                    f.write(part.inline_data.data)
                return file_name
    except Exception as e:
        print("🔴 Error generating image:", e)
    return None

def upload_to_imgbb(file_path):
    try:
        with open(file_path, "rb") as f:
            encoded = base64.b64encode(f.read())
        data = {
            "key": IMGBB_API_KEY,
            "image": encoded
        }
        response = requests.post("https://api.imgbb.com/1/upload", data=data)
        if response.status_code == 200:
            return response.json()["data"]["url"]
        else:
            print(f"🔴 ImgBB upload failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"🔴 Exception during ImgBB upload: {e}")
        return None

async def send_pm(ws, to, body):
    """Send private message to a user"""
    try:
        payload = {
            HANDLER: "chat_message",
            TYPE: MSG_TYPE_TXT,
            MSG_TO: to,
            MSG_BODY: body,
            ID: gen_random_str(20)
        }
        await ws.send(json.dumps(payload, ensure_ascii=False))
    except Exception as e:
        print(f"[SEND PM ERROR] {e}")

# =====================================
# MAIN BOT
# =====================================

async def on_room_message(ws, data, main_ws):
    try:
        if MSG_BODY not in data:
            return
        
        msg = data[MSG_BODY]
        frm = data.get(MSG_FROM, "")
        room = data.get(ROOM, "")
        
        # Handle creation command from PM (not from room messages)
        # This is handled in handle_pm function
        
    except Exception as e:
        print(f"🔴 Error processing message: {e}")

async def handle_pm(ws, data, main_ws):
    """Handle private messages for bot creation"""
    try:
        if MSG_BODY not in data:
            return
        
        msg = data[MSG_BODY].strip()
        frm = data.get(MSG_FROM, "")
        
        print(f"[PM] {frm}: {msg}")
        
        # ================= HELP COMMAND =================
        if msg.lower() in ["help", "مساعدة"]:
            help_msg = """🤖 *BOT SERVER / سيرفر البوت* 🤖

📖 *English Instructions:* 🇬🇧
━━━━━━━━━━━━━━━━━━━━━
To create a new bot, send:
`Dd room username password`

📝 *Example:* ✨
`Dd myroom mybot 123456`

🔍 *Parameters:* 📋
• `room`     → Chat room name 🏠
• `username` → Bot username 👤
• `password` → Bot password 🔐

━━━━━━━━━━━━━━━━━━━━━

📖 *التعليمات العربية:* 🇸🇦
━━━━━━━━━━━━━━━━━━━━━
لإنشاء بوت جديد، أرسل:
`Dd اسم_الغرفة اسم_المستخدم كلمة_السر`

📝 *مثال:* ✨
`Dd غرفتي بوتي 123456`

🔍 *المعاملات:* 📋
• `اسم_الغرفة` → اسم غرفة المحادثة 🏠
• `اسم_المستخدم` → اسم البوت 👤
• `كلمة_السر` → كلمة سر البوت 🔐

━━━━━━━━━━━━━━━━━━━━━
✅ *No symbols or hashtags needed!*
🚫 *لا تحتاج رموز أو علامات #`"""
            await send_pm(ws, frm, help_msg)
            return
        
        # ================= CREATE BOT COMMAND =================
        if msg.lower().startswith("dd "):
            parts = msg[3:].strip().split()
            
            if len(parts) < 3:
                await send_pm(ws, frm, """❌ *Invalid Command / أمر غير صحيح* ❌

📖 *English:* 🇬🇧
Please use:
`Dd room username password`

📝 *Example:* ✨
`Dd myroom bot1 123456`

━━━━━━━━━━━━━━━━━━━━━

📖 *العربية:* 🇸🇦
الرجاء استخدام:
`Dd اسم_الغرفة اسم_المستخدم كلمة_السر`

📝 *مثال:* ✨
`Dd غرفتي بوت1 123456`

💡 Tip: Send `help` or `مساعدة` for more info""")
                return
            
            room = parts[0]
            username = parts[1]
            password = parts[2]
            
            await create_child_bot(frm, room, username, password, ws)
            return
        
    except Exception as e:
        print(f"[HANDLE PM ERROR] {e}")

async def update_profile(ws):
    status_msg = f"""
┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🤖 ᴀɪ ʙᴏᴛ ᴄʀᴇᴀᴛᴏʀ.    ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━┫
┃  ✨ Dd [room] [user] [pw]┃
┃  🤖 Create your own bot ┃
┃  📖 Send 'help' for info┃
┃  🕒 {time.strftime("%H:%M %d/%m")}  
┗━━━━━━━━━━━━━━━━━━━━━━━━┛
"""
    await ws.send(json.dumps({
        "handler": HANDLER_PROFILE_UPDATE,
        "id": str(uuid.uuid4()),
        "type": "status",
        "value": f"<big><span style='color:#FF9900;font-family:monospace;'>{status_msg}</span>"
    }, ensure_ascii=False))

async def load_saved_bots(main_ws):
    """Load and reconnect saved bots"""
    bots = load_json(BOTS_FILE, [])
    print(f"[LOADING SAVED BOTS] {len(bots)}")
    
    for bot in bots:
        try:
            room = bot.get("room")
            username = bot.get("username")
            password = bot.get("password")
            owner = bot.get("owner")
            
            if room and username and password and room not in CHILD_BOTS:
                task = asyncio.create_task(run_child_bot(room, username, password, owner, main_ws))
                CHILD_BOTS[room] = {
                    "room": room,
                    "username": username,
                    "password": password,
                    "owner": owner,
                    "task": task,
                    "created": time.time()
                }
                print(f"[RECONNECTED] {username}")
        except Exception as e:
            print(f"[LOAD BOT ERROR] {e}")

async def login(ws):
    payload = {
        HANDLER: HANDLER_LOGIN,
        ID: gen_random_str(20),
        USERNAME: BOT_ID,
        PASSWORD: BOT_PWD
    }
    await ws.send(json.dumps(payload, ensure_ascii=False))

async def join_group(ws, group):
    payload = {
        HANDLER: HANDLER_ROOM_JOIN,
        ID: gen_random_str(20),
        NAME: group
    }
    await ws.send(json.dumps(payload, ensure_ascii=False))

async def start_bot(ws):
    """Main bot entry point"""
    await login(ws)
    await asyncio.sleep(3)
    await join_group(ws, GROUP_TO_INIT_JOIN)
    await update_profile(ws)
    await load_saved_bots(ws)
    
    while True:
        try:
            payload = await ws.recv()
            if payload:
                data = json.loads(payload)
                handler = data.get(HANDLER)
                
                if handler == HANDLER_ROOM_EVENT:
                    await on_room_message(ws, data, ws)
                
                # Handle private messages
                if handler == "chat_message":
                    await handle_pm(ws, data, ws)
                    
        except json.JSONDecodeError as e:
            print(f"🔴 JSON decode error: {e}")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"🔴 Connection closed: {e}, reconnecting...")
            await asyncio.sleep(5)
            return await main()
        except Exception as e:
            print(f"🔴 WebSocket error: {e}")
            await asyncio.sleep(5)

async def main():
    while True:
        try:
            async with websockets.connect(SOCKET_URL, ssl=True) as websocket:
                await start_bot(websocket)
        except Exception as e:
            print(f"🔴 Connection error: {e}, retrying in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == '__main__':
    print("🤖 AI Bot Creator Started! 🤖")
    print("📖 Type 'help' in PM to see commands")
    asyncio.run(main())
