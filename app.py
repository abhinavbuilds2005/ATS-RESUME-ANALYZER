import os
import sys
import subprocess

print("=== DEBUGGING PORT & PROCESSES ===", flush=True)
print(f"PID: {os.getpid()}", flush=True)
print("ENV:", {k: v for k, v in os.environ.items() if "PORT" in k or "GRADIO" in k or "SPACE" in k or "ZERO" in k}, flush=True)
try:
    netstat = subprocess.check_output("ss -tulpn 2>&1 || netstat -tulpn 2>&1 || true", shell=True, text=True)
    print("OPEN PORTS:\n" + netstat, flush=True)
except Exception as e:
    print("Could not get open ports:", e, flush=True)
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
    port = int(os.getenv("PORT") or os.getenv("GRADIO_SERVER_PORT") or 7860)
    uvicorn.run(app, host="0.0.0.0", port=port)
