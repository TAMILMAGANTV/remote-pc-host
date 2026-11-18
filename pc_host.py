import asyncio
import base64
import io
import json
import os
import random
import string
import threading
import tkinter as tk
from tkinter import messagebox
import mss
import pyautogui
import websockets
from PIL import Image

RELAY_URL = "wss://remote-relay-server-v5am.onrender.com"
CONFIG_FILE = "remote_config.json"

pyautogui.FAILSAFE = False

def load_or_create_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    config = {
        "id": "".join(random.choices(string.digits, k=9)),
        "password": "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)
    return config

def save_config(host_id, password):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"id": host_id, "password": password}, f)

config = load_or_create_config()
HOST_ID = config["id"]
HOST_PASSWORD = config["password"]
reconnect_flag = False

def capture_screen():
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        img.thumbnail((1280, 720))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=45)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

async def connect_to_relay():
    global reconnect_flag
    screen_w, screen_h = pyautogui.size()

    while True:
        reconnect_flag = False
        uri = f"{RELAY_URL}/ws/host/{HOST_ID}/{HOST_PASSWORD}"
        try:
            async with websockets.connect(uri) as ws:
                async def send_frames():
                    while not reconnect_flag:
                        img_data = capture_screen()
                        await ws.send(json.dumps({"type": "frame", "image": img_data}))
                        await asyncio.sleep(0.08)

                async def receive_commands():
                    async for message in ws:
                        if reconnect_flag:
                            break
                        cmd = json.loads(message)
                        action = cmd.get("type")
                        if action in ["click", "right_click", "double_click"]:
                            x = int(cmd["x"] * screen_w)
                            y = int(cmd["y"] * screen_h)
                            if action == "click":
                                pyautogui.click(x, y)
                            elif action == "right_click":
                                pyautogui.rightClick(x, y)
                            elif action == "double_click":
                                pyautogui.doubleClick(x, y)
                        elif action == "scroll":
                            pyautogui.scroll(cmd["amount"])
                        elif action == "type":
                            pyautogui.write(cmd["text"])
                        elif action == "key":
                            pyautogui.press(cmd["key"])

                await asyncio.gather(send_frames(), receive_commands())
        except Exception:
            await asyncio.sleep(2)

def start_async_loop():
    asyncio.run(connect_to_relay())

def start_gui():
    root = tk.Tk()
    root.title("My Remote PC Host")
    root.geometry("360x260")
    root.resizable(False, False)

    formatted_id = f"{HOST_ID[:3]} {HOST_ID[3:6]} {HOST_ID[6:]}"

    tk.Label(root, text="உங்கள் கணினி இணையத்துடன் இணைக்கப்பட்டுள்ளது", font=("Arial", 10, "bold"), fg="green").pack(pady=10)
    tk.Label(root, text="Your Permanent ID (நிரந்தர எண்):", font=("Arial", 10)).pack()
    tk.Label(root, text=formatted_id, font=("Arial", 18, "bold"), fg="#0052cc").pack(pady=2)

    tk.Label(root, text="Set Your Password (கடவுச்சொல் அமைக்கவும்):", font=("Arial", 10)).pack(pady=(10, 2))
    pass_entry = tk.Entry(root, font=("Arial", 12), justify="center", width=20)
    pass_entry.insert(0, HOST_PASSWORD)
    pass_entry.pack(pady=5)

    def update_password():
        global HOST_PASSWORD, reconnect_flag
        new_pass = pass_entry.get().strip()
        if len(new_pass) < 4:
            messagebox.showwarning("எச்சரிக்கை", "குறைந்தது 4 எழுத்துக்கள் கொண்ட பாஸ்வேர்டை உள்ளிடவும்!")
            return
        HOST_PASSWORD = new_pass
        save_config(HOST_ID, HOST_PASSWORD)
        reconnect_flag = True
        messagebox.showinfo("வெற்றி", "புதிய பாஸ்வேர்டு சேமிக்கப்பட்டது!")

    tk.Button(root, text="Save Password (சேமிக்கவும்)", command=update_password, bg="#0052cc", fg="white", font=("Arial", 10, "bold")).pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    threading.Thread(target=start_async_loop, daemon=True).start()
    start_gui()
    
