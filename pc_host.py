import asyncio
import base64
import io
import json
import os
import random
import string
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox
import mss
import pyautogui
import pyperclip
import websockets
from PIL import Image, ImageDraw

RELAY_URL = "wss://remote-relay-server-v5am.onrender.com"
CONFIG_FILE = "remote_config.json"

# மவுஸ் நகர்வில் எந்தத் தாமதமும் இல்லாமல் அதிவேகமாக இயங்க
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

SCREEN_QUALITY = 50
SCREEN_WIDTH = 1280

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

def enable_autostart():
    try:
        startup_folder = os.path.join(
            os.getenv("APPDATA"),
            r"Microsoft\Windows\Start Menu\Programs\Startup"
        )
        exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
        bat_path = os.path.join(startup_folder, "MyAnyDesk_AutoStart.bat")
        with open(bat_path, "w") as f:
            f.write(f'@echo off\ncd /d "{os.path.dirname(exe_path)}"\nstart "" "{exe_path}"\n')
        return True
    except Exception:
        return False

def capture_screen():
    global SCREEN_QUALITY, SCREEN_WIDTH
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

        # தெளிவான AnyDesk ஸ்டைல் மவுஸ் கர்சர்
        try:
            mx, my = pyautogui.position()
            rel_x = mx - monitor["left"]
            rel_y = my - monitor["top"]
            draw = ImageDraw.Draw(img)
            pointer = [
                (rel_x, rel_y),
                (rel_x, rel_y + 22),
                (rel_x + 5, rel_y + 17),
                (rel_x + 10, rel_y + 26),
                (rel_x + 13, rel_y + 24),
                (rel_x + 8, rel_y + 15),
                (rel_x + 15, rel_y + 15),
            ]
            draw.polygon(pointer, fill="white", outline="black")
        except Exception:
            pass

        ratio = SCREEN_WIDTH / float(img.size[0])
        new_height = int(float(img.size[1]) * ratio)
        img = img.resize((SCREEN_WIDTH, new_height), Image.Resampling.BILINEAR)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=SCREEN_QUALITY)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

async def connect_to_relay():
    global reconnect_flag, SCREEN_QUALITY, SCREEN_WIDTH
    screen_w, screen_h = pyautogui.size()

    while True:
        reconnect_flag = False
        uri = f"{RELAY_URL}/ws/host/{HOST_ID}/{HOST_PASSWORD}"
        try:
            async with websockets.connect(uri, max_size=20 * 1024 * 1024) as ws:
                async def send_frames():
                    while not reconnect_flag:
                        img_data = capture_screen()
                        await ws.send(json.dumps({"type": "frame", "image": img_data}))
                        await asyncio.sleep(0.035)  # ~28 FPS அதிவேக ஸ்ட்ரீமிங்

                async def receive_commands():
                    global SCREEN_QUALITY, SCREEN_WIDTH
                    async for message in ws:
                        if reconnect_flag:
                            break
                        cmd = json.loads(message)
                        action = cmd.get("type")

                        # AnyDesk போல விரல் நகரும் அளவிற்கு ஏற்ப ஸ்மூத்தாக நகரும் முறை
                        if action == "move_rel":
                            dx = int(cmd["dx"])
                            dy = int(cmd["dy"])
                            pyautogui.moveRel(dx, dy, _pause=False)

                        elif action == "move":
                            x = int(cmd["x"] * screen_w)
                            y = int(cmd["y"] * screen_h)
                            pyautogui.moveTo(x, y, _pause=False)

                        elif action in ["click", "right_click", "double_click"]:
                            if action == "click":
                                pyautogui.click(_pause=False)
                            elif action == "right_click":
                                pyautogui.rightClick(_pause=False)
                            elif action == "double_click":
                                pyautogui.doubleClick(_pause=False)

                        elif action == "mouse_down":
                            pyautogui.mouseDown(_pause=False)
                        elif action == "mouse_up":
                            pyautogui.mouseUp(_pause=False)

                        elif action == "scroll":
                            pyautogui.scroll(cmd["amount"], _pause=False)

                        elif action == "type":
                            pyautogui.write(cmd["text"])

                        elif action == "paste_text":
                            pyperclip.copy(cmd["text"])
                            pyautogui.hotkey("ctrl", "v")

                        elif action == "key":
                            pyautogui.press(cmd["key"])

                        elif action == "hotkey":
                            pyautogui.hotkey(*cmd["keys"])

                        elif action == "quality":
                            level = cmd["level"]
                            if level == "low":
                                SCREEN_WIDTH, SCREEN_QUALITY = 854, 30
                            elif level == "medium":
                                SCREEN_WIDTH, SCREEN_QUALITY = 1280, 50
                            elif level == "hd":
                                SCREEN_WIDTH, SCREEN_QUALITY = 1600, 75

                        elif action == "power":
                            mode = cmd["mode"]
                            if mode == "restart":
                                subprocess.Popen("shutdown /r /t 5", shell=True)
                            elif mode == "shutdown":
                                subprocess.Popen("shutdown /s /t 5", shell=True)

                await asyncio.gather(send_frames(), receive_commands())
        except Exception:
            await asyncio.sleep(2)

def start_async_loop():
    asyncio.run(connect_to_relay())

def start_gui():
    root = tk.Tk()
    root.title("My AnyDesk Pro - PC Host")
    root.geometry("380x310")
    root.resizable(False, False)

    formatted_id = f"{HOST_ID[:3]} {HOST_ID[3:6]} {HOST_ID[6:]}"

    tk.Label(root, text="● இணையத்துடன் இணைக்கப்பட்டுள்ளது (Online)", font=("Arial", 10, "bold"), fg="green").pack(pady=10)
    tk.Label(root, text="Your Permanent ID (நிரந்தர எண்):", font=("Arial", 10)).pack()
    tk.Label(root, text=formatted_id, font=("Arial", 20, "bold"), fg="#0052cc").pack(pady=2)

    tk.Label(root, text="Set Permanent Password (கடவுச்சொல்):", font=("Arial", 10)).pack(pady=(8, 2))
    pass_entry = tk.Entry(root, font=("Arial", 12), justify="center", width=22)
    pass_entry.insert(0, HOST_PASSWORD)
    pass_entry.pack(pady=4)

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

    def setup_boot():
        if enable_autostart():
            messagebox.showinfo("வெற்றி", "இனி கம்ப்யூட்டர் ஆன் ஆனவுடன் இந்த செயலி தானாகவே இயங்கும்!")
        else:
            messagebox.showerror("பிழை", "Auto-Start அமைக்க முடியவில்லை.")

    tk.Button(root, text="Save Password (சேமிக்கவும்)", command=update_password, bg="#0052cc", fg="white", font=("Arial", 10, "bold"), width=24).pack(pady=6)
    tk.Button(root, text="Enable Auto-Start on Boot", command=setup_boot, bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), width=24).pack(pady=4)

    root.mainloop()

if __name__ == "__main__":
    threading.Thread(target=start_async_loop, daemon=True).start()
    start_gui()
    
