import asyncio
import base64
import io
import json
import socket
import threading
import tkinter as tk
import mss
import pyautogui
from PIL import Image
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

app = FastAPI()
pyautogui.FAILSAFE = False

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def capture_screen():
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        img.thumbnail((1280, 720))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=50)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    screen_w, screen_h = pyautogui.size()

    async def send_screen():
        try:
            while True:
                img_data = capture_screen()
                await websocket.send_text(json.dumps({"type": "frame", "image": img_data}))
                await asyncio.sleep(0.08)
        except Exception:
            pass

    send_task = asyncio.create_task(send_screen())

    try:
        while True:
            data = await websocket.receive_text()
            command = json.loads(data)
            if command["type"] == "click":
                x = int(command["x"] * screen_w)
                y = int(command["y"] * screen_h)
                pyautogui.click(x, y)
            elif command["type"] == "type":
                pyautogui.write(command["text"])
    except WebSocketDisconnect:
        send_task.cancel()

def run_server():
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="error")

# சிறிய UI விண்டோ (IP முகவரியைக் காட்ட)
def start_gui():
    root = tk.Tk()
    root.title("Remote PC Host")
    root.geometry("320x150")
    root.resizable(False, False)

    ip_address = get_local_ip()
    tk.Label(root, text="Remote Desktop இயங்குகிறது", font=("Arial", 12, "bold"), fg="green").pack(pady=15)
    tk.Label(root, text=f"உங்கள் IP முகவரி: {ip_address}:8000", font=("Arial", 11)).pack(pady=5)
    tk.Label(root, text="(இந்த விண்டோவை மூடினால் இணைப்பு துண்டிக்கப்படும்)", font=("Arial", 8), fg="gray").pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    start_gui()
  
