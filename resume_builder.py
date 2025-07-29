import os
from openai import OpenAI
import gradio as gr
import tempfile
from PyPDF2 import PdfReader

# === CONFIGURATION ===
OPENROUTER_API_KEY = "OPEN API KEY"  # <-- Replace this
SAVE_DIR = os.getcwd()  # Saves output to current working directory

client = OpenAI(
    api_key = OPENROUTER_API_KEY,
    base_url = "https://openrouter.ai/api/v1"
)
DEEPSEEK_MODEL = "tngtech/deepseek-r1t2-chimera:free"
FORMATTING_MODEL = "moonshotai/kimi-k2:free"

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "X-Title": "CV to Resume"
}


def read_pdf(file_path):
    reader = PdfReader(file_path)
    return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])


def call_openrouter_llm(prompt: str, model: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=16384,
    )
    return response.choices[0].message.content


def process_resume(file):
    try:
        raw_text = read_pdf(file.name)

        # Step 1: Clean resume using DeepSeek
        deepseek_prompt = (
            "You are a resume assistant. Clean and extract the key information from this raw CV text. "
            "Convert paragraphs to points with one point for each sub-heading under Projects and Experience, professional resume format:\n\n"
            f"{raw_text}"
        )
        cleaned_resume = call_openrouter_llm(deepseek_prompt, DEEPSEEK_MODEL)

        # Step 2: Format using Claude Haiku
        formatting_prompt = (
            "You are a professional resume formatter. Convert the following cleaned resume content "
            "into a well-structured HTML/CSS-styling and Bootstrap styling based resume with clear headings and professional layout. Keep it clean and modern.\n\n"
            f"{cleaned_resume}"
        )
        html_resume = call_openrouter_llm(formatting_prompt, FORMATTING_MODEL)

        # Step 3: Save HTML to disk
        html_path = os.path.join(tempfile.gettempdir(), "final_resume.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_resume)

        return html_resume, html_path

    except Exception as e:
        return f"[Error] Failed to generate resume: {str(e)}", None


# ========== GRADIO UI ==========

def gradio_interface(file):
    resume_html, download_path = process_resume(file)
    return resume_html, download_path


with gr.Blocks() as demo:
    gr.Markdown("# 📄 AI Resume Polisher & Formatter")
    gr.Markdown("Upload your CV (PDF) and receive a clean, professional resume in HTML format.")

    with gr.Row():
        file_input = gr.File(label="Upload your CV (PDF)", file_types=[".pdf"])

    with gr.Row():
        html_output = gr.HTML(label="Generated Resume Preview")

    with gr.Row():
        download_button = gr.File(label="Download HTML Resume")

    run_btn = gr.Button("Generate Resume")

    run_btn.click(fn=gradio_interface, inputs=[file_input], outputs=[html_output, download_button])

demo.launch()