import os
import sys
import socket

print("=== DEBUGGING PORT & SOCKETS ===", flush=True)
print(f"PID: {os.getpid()}", flush=True)

try:
    with open('/proc/net/tcp', 'r') as f:
        print("TCP sockets in /proc/net/tcp:\n" + "".join(f.readlines()[:10]), flush=True)
except Exception as e:
    print("Could not read /proc/net/tcp:", e, flush=True)

selected_port = None
for p in range(7860, 7875):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
        s.bind(('0.0.0.0', p))
        s.close()
        print(f"--> Port {p} is OPEN and CAN BIND!", flush=True)
        if selected_port is None:
            selected_port = p
    except Exception as e:
        print(f"--> Port {p} CANNOT bind: {e}", flush=True)

print(f"SELECTED PORT: {selected_port}", flush=True)
print("==================================", flush=True)

try:
    import spaces
except ImportError:
    pass

import gradio as gr
import uvicorn
from backend.main import app

# Mount a minimal Gradio block at /gradio
demo = gr.Blocks(title="ATS Resume Analyzer")
app = gr.mount_gradio_app(app, demo, path="/gradio")

if __name__ == "__main__":
    port = selected_port or int(os.getenv("PORT") or os.getenv("GRADIO_SERVER_PORT") or 7860)
    print(f"Starting server on 0.0.0.0:{port} ...", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port)
