# === Core Imports ===
import streamlit as st  # Streamlit UI
import tempfile  # For creating temporary file for PDF
import os
from summarizer_pipeline import (
    summarize_pdf_report,
    split_text_smart,
    extract_text_from_pdf,
    load_or_generate_ocr,
    deduplicate_ocr,
    read_prompt_template,
    summarize_chunk_with_id
)
import subprocess
import requests
import time
import platform
import ctypes
import atexit
from concurrent.futures import ThreadPoolExecutor, as_completed
import markdown
import fitz  # PyMuPDF – for counting PDF pages

# === Prevent Windows from Sleeping ===
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_AWAYMODE_REQUIRED = 0x00000040

def prevent_sleep():
    """Prevent Windows from going to sleep during long operations."""
    ctypes.windll.kernel32.SetThreadExecutionState(
        ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
    )

def restore_sleep():
    """Restore normal sleep behavior when script exits."""
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)

# Register cleanup at script exit
atexit.register(restore_sleep)

# === Ollama Management ===
def is_ollama_running():
    """Check if Ollama server is up and running locally."""
    try:
        response = requests.get("http://localhost:11434")
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        return False

def launch_ollama_if_needed(model="llama3:8b-instruct-q4_K_M"):
    """Auto-launch Ollama model subprocess if it's not already running."""
    if is_ollama_running():
        if not st.session_state.get("ollama_started_logged"):
            print(f"✅ Local Ollama3 AI Version - {model} is running.")
            st.session_state["ollama_started_logged"] = True
        return

    print("🚀 Starting Ollama with model:", model)
    if platform.system() == "Windows":
        subprocess.Popen(
            ['start', '/min', 'cmd', '/c', f'ollama run {model}'],
            shell=True
        )
    else:
        subprocess.Popen(
            f"ollama run {model} > /dev/null 2>&1 &",
            shell=True,
            executable="/bin/bash"
        )

    # Wait for startup
    for _ in range(10):
        if is_ollama_running():
            print("✅ Ollama is now running.")
            st.session_state["ollama_started_logged"] = True
            return
        time.sleep(1)

    print("❌ Failed to start Ollama. Is it installed and in PATH?")

# === Prompt Mappings ===
REPORT_TYPES = {
    "MPR": ("./prompts/mpr_prompt.txt", "./prompts/final_mpr_prompt.txt"),
    "Board Report": ("./prompts/board_prompt.txt", "./prompts/final_board_prompt.txt"),
    "Financial Reports": ("./prompts/finance_prompt.txt", "./prompts/final_finance_prompt.txt"),
    "Audit Reports": ("./prompts/audit_prompt.txt", "./prompts/final_audit_prompt.txt"),
    "Others": ("./prompts/other_prompt.txt", "./prompts/final_other_prompt.txt"),
}

def get_pdf_page_count(file_path):
    """Return number of pages in uploaded PDF using PyMuPDF."""
    doc = fitz.open(file_path)
    return len(doc)

# === Main App Function ===
def main():
    st.set_page_config(page_title="🧠 PDF Report Summarizer", layout="centered")

    # Inject CSS and HTML for styling
    st.markdown("""<style> ... </style>""", unsafe_allow_html=True)

    st.title("📄 AI - Offline Report Summarizer")

    # Initialize session state variables
    if "stop_process" not in st.session_state:
        st.session_state.stop_process = False

    # If user clicked Stop, trigger stop flag
    if st.query_params.get("stop") or st.session_state.get("stop", False):
        st.session_state.stop_process = True
        st.warning("⚠️ Stopping process...")

    if "ollama_started_logged" not in st.session_state:
        launch_ollama_if_needed("llama3:8b-instruct-q4_K_M")

    # Preserve summary between interactions
    if "final_summary" not in st.session_state:
        st.session_state.final_summary = ""
        st.session_state.chunk_results = []

    # === Sidebar/Top Controls ===
    uploaded_file = st.file_uploader("Upload PDF report", type=["pdf"])
    report_type = st.selectbox("Report Type", list(REPORT_TYPES.keys()))

    page_mode = st.radio("Specify Page Length", ["Auto(AI decides)", "Custom (Page Limit)"])
    page_limit = 3
    if page_mode == "Custom (Page Limit)":
        page_limit = st.slider("Select Max number of pages for summary", min_value=1, max_value=5, value=3)

    show_chunks = st.checkbox("🔎 Display sub level summaries", value=False)

    # === Run Summarization ===
    if st.button("🔍 Summarize Report") and uploaded_file:
        # Clear previous summary results
        st.session_state.final_summary = ""
        st.session_state.chunk_results = []
        st.session_state.stop_process = False

        # Get prompt templates
        prompt_path, final_prompt_path = REPORT_TYPES[report_type]

        # Save uploaded PDF temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            temp_pdf.write(uploaded_file.read())
            temp_pdf_path = temp_pdf.name

        prevent_sleep()
        total_pages = get_pdf_page_count(temp_pdf_path)

        # UI Feedback Elements
        status = st.empty()
        progress_bar = st.progress(0)
        chunk_status = st.empty()
        timer_start = time.time()

        # === Text Extraction & Cleaning ===
        status.info("🔍 Extracting text & Images from PDF...")
        text_pdf = extract_text_from_pdf(temp_pdf_path)
        text_ocr = load_or_generate_ocr(temp_pdf_path)
        clean_ocr = deduplicate_ocr(text_pdf, text_ocr)
        combined_text = text_pdf + "\n" + clean_ocr

        # === Split Text into Chunks ===
        status.info("📚 Splitting text...")
        prompt_template = read_prompt_template(prompt_path)
        final_prompt_template = read_prompt_template(final_prompt_path)
        chunks = split_text_smart(combined_text)

        status.info(f"✂️ {len(chunks)} Section(s) to Summarize...")

        # === Summarize Each Chunk (Async) ===
        results = []
        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(summarize_chunk_with_id, i, chunk, prompt_template, "llama3:8b-instruct-q4_K_M"): i
                for i, chunk in enumerate(chunks, 1)
            }

            total = len(futures)
            for i, future in enumerate(as_completed(futures), 1):
                if st.session_state.stop_process:
                    status.warning("⛔ Process stopped by user.")
                    return
                try:
                    index, chunk_summary = future.result()
                    results.append((index, chunk_summary))
                    progress_bar.progress(i / total)
                    chunk_status.empty()
                    chunk_status.success(f"✅ Section {index}/{total} Completed ")
                except Exception as e:
                    results.append((i, f"❌ Error in chunk {i}: {str(e)}"))

        # Sort and assemble
        results.sort()
        combined_summary = "\n\n".join(text for _, text in results)
        st.session_state.chunk_results = results

        if st.session_state.stop_process:
            status.warning("⛔ Summary was stopped early. No final summary generated.")
            return

        # === Final Summary ===
        status.info("🧠 Generating the final summary...")
        final_prompt = final_prompt_template.replace("{text}", combined_summary)
        if page_mode == "Custom (Page Limit)":
            final_prompt += f"\n\nThe final summary should be concise and not exceed {page_limit} A4 pages."

        final_summary = summarize_chunk_with_id(0, combined_summary, final_prompt, "llama3:8b-instruct-q4_K_M")[1]
        st.success("✅ Summarization complete!")

        st.session_state.final_summary = final_summary
        elapsed_time = time.time() - timer_start

        # === Display Page Count and Duration ===
        st.info(f"📄 PDF Pages: {total_pages} | ⏱ Time Taken: {elapsed_time:.2f}s")

    # === Display Final Summary ===
    if st.session_state.final_summary:
        html_body = markdown.markdown(
            st.session_state.final_summary,
            extensions=['extra', 'admonition', 'tables']
        )

        st.markdown(f"""
            <div class="styled-summary-container">
                <div class="summary-header">
                    <img src="\\img\\logo.png" alt="Logo" width="120" style="margin-bottom:10px;" />
                    <h2> Summarized Report</h2>
                    <p style="color:#888; font-size:14px;"> Report is AI Generated</p>
                </div>
                <div id="summary-text">{html_body}</div>
                <hr style='margin-top:1em;'>
                <div style='text-align:right;'>
                    <button onclick="navigator.clipboard.writeText(document.getElementById('summary-text').innerText)" style='padding:6px 12px; background:#4CAF50; color:white; border:none; border-radius:5px; margin-right:10px;'>📋 Copy</button>
                    <button onclick="window.print()" style='padding:6px 12px; background:#2196F3; color:white; border:none; border-radius:5px;'>🖨️ Print</button>
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.download_button(
            label="📥 Download Summary",
            data=st.session_state.final_summary,
            file_name="summary.txt",
            mime="text/plain"
        )

        if st.button("🔄 Reset Selection"):
            st.session_state.final_summary = ""
            st.session_state.chunk_results = []

    # === Display Section-Level Summaries ===
    if show_chunks and st.session_state.chunk_results:
        with st.expander("🧩 View Section summaries"):
            for i, chunk in st.session_state.chunk_results:
                st.markdown(f"**Section {i}**\n\n{chunk}")

# === Entry Point ===
if __name__ == "__main__":
    main()
