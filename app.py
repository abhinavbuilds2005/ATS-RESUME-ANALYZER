import os
import gradio as gr
import uvicorn
from backend.main import app

# Mount a minimal Gradio block at /gradio to satisfy Hugging Face Gradio SDK
demo = gr.Blocks(title="ATS Resume Analyzer")
app = gr.mount_gradio_app(app, demo, path="/gradio")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
