# === Imports ===
import fitz  # PyMuPDF – for extracting text from PDF pages
from pdf2image import convert_from_path  # Convert PDF pages to images for OCR
import pytesseract  # Tesseract OCR engine
import hashlib  # For deduplication and caching
import os
import re
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed  # For parallel chunk summarization

# === Setup paths for Poppler and Tesseract ===
poppler_bin = r".\poppler-24.08.0\Library\bin"
os.environ["PATH"] += os.pathsep + poppler_bin

# Set path to Tesseract executable (change this to your actual installation path)
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\ejike.ozonkwo\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

# === Configuration ===
CACHE_DIR = "./cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# === Regex setup for cleaning text ===
non_ascii_re = re.compile(r"[^\x00-\x7F]+")     # Remove non-ASCII characters
multi_space_re = re.compile(r"\s+")             # Normalize multiple spaces

# === Utility Functions ===

# Clean and normalize extracted text
def clean_text(text):
    return multi_space_re.sub(" ", non_ascii_re.sub(" ", text)).strip()

# Generate hash for a single line of text (used for deduplication)
def hash_line(line):
    return hashlib.md5(line.lower().strip().encode()).hexdigest()

# Get hash of a file by reading it in chunks
def get_file_hash(path, block_size=65536):
    hasher = hashlib.md5()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(block_size), b''):
            hasher.update(block)
    return hasher.hexdigest()

# === PDF Text Extraction ===

# Extract text from PDF using PyMuPDF
def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    return "\n".join(f"[Page {i+1}]\n{page.get_text()}" for i, page in enumerate(doc))

# Convert PDF pages to images and apply OCR with Tesseract
def extract_text_from_images(pdf_path):
    images = convert_from_path(pdf_path, dpi=150)  # Convert each page to image (for scanned PDFs)

    def ocr_with_index(index_img):
        index, img = index_img
        text = pytesseract.image_to_string(img, lang='eng', config='--psm 3')
        return f"[Page {index + 1} - OCR]\n{text.strip()}"

    # Process pages in parallel (1 worker to avoid overuse)
    with ThreadPoolExecutor(max_workers=1) as executor:
        indexed = list(enumerate(images))
        return "\n".join(executor.map(ocr_with_index, indexed))

# Load OCR result from cache or generate and save if not present
def load_or_generate_ocr(pdf_path):
    filename = os.path.basename(pdf_path)
    ocr_cache = os.path.join(CACHE_DIR, filename + ".ocr.txt")
    hash_file = os.path.join(CACHE_DIR, filename + ".hash")
    current_hash = get_file_hash(pdf_path)

    # Load from cache if file hash matches
    if os.path.exists(ocr_cache) and os.path.exists(hash_file):
        with open(hash_file, 'r') as f:
            saved_hash = f.read().strip()
        with open(ocr_cache, 'r', encoding='utf-8') as f:
            cached_text = f.read()
        if saved_hash == current_hash and cached_text.strip():
            return cached_text

    # Otherwise, generate OCR and save to cache
    ocr_text = extract_text_from_images(pdf_path)
    with open(ocr_cache, 'w', encoding='utf-8') as f:
        f.write(ocr_text)
    with open(hash_file, 'w') as f:
        f.write(current_hash)
    return ocr_text

# Remove duplicate lines between PDF text and OCR (keeps only OCR text that isn't in original)
def deduplicate_ocr(text_pdf, text_ocr):
    pdf_hashes = set(hash_line(line) for line in text_pdf.splitlines() if line.strip())
    return "\n".join(
        line for line in text_ocr.splitlines() if hash_line(line) not in pdf_hashes
    )

# === Text Chunking ===

# Split text into manageable chunks for summarization
def split_text_smart(text, max_words=2000, min_words=200):
    words = text.split()
    chunks = []
    current_chunk = []

    for word in words:
        current_chunk.append(word)
        if len(current_chunk) >= max_words:
            chunks.append(' '.join(current_chunk))
            current_chunk = []

    if current_chunk:
        if len(current_chunk) < min_words and chunks:
            chunks[-1] += ' ' + ' '.join(current_chunk)
        else:
            chunks.append(' '.join(current_chunk))
    return chunks

# === Prompt Handling ===

# Load a prompt template from file
def read_prompt_template(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

# Query the local Ollama LLaMA3 model
def query_llama3(prompt, model="llama3:8b-instruct-q4_K_M"):
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False}
        )
        response.raise_for_status()
        return response.json()["response"]
    except Exception as e:
        print("LLaMA3 query error:", e)
        return "Model query failed."

# Format chunk using prompt and return summary with index
def summarize_chunk_with_id(index, chunk, prompt_template, model):
    prompt = prompt_template.replace("{text}", chunk)
    return (index, query_llama3(prompt, model))

# === Full Pipeline: Summary from PDF ===

def summarize_pdf_report(pdf_path, prompt_file_path, final_prompt_path, progress_callback=None):
    start_time = time.time()
    if progress_callback:
        progress_callback("🔍 Extracting PDF text...")

    # Step 1: Extract and clean all text (PDF + OCR)
    text_pdf = extract_text_from_pdf(pdf_path)
    text_ocr = load_or_generate_ocr(pdf_path)
    clean_ocr = deduplicate_ocr(text_pdf, text_ocr)
    combined = clean_text(text_pdf + "\n" + clean_ocr)

    if progress_callback:
        progress_callback("📚 Chunking text...")

    # Step 2: Load prompt templates
    prompt_template = read_prompt_template(prompt_file_path)
    final_prompt_template = read_prompt_template(final_prompt_path)

    # Step 3: Split into chunks
    chunks = split_text_smart(combined)

    if not chunks:
        return "No content extracted from PDF."

    if progress_callback:
        progress_callback(f"✂️ {len(chunks)} chunk(s) to summarize...")

    # Step 4: Summarize each chunk in parallel
    results = []
    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(summarize_chunk_with_id, i, chunk, prompt_template, "llama3:8b-instruct-q4_K_M"): i
            for i, chunk in enumerate(chunks, 1)
        }
        for i, future in enumerate(as_completed(futures), 1):
            try:
                result = future.result()
                results.append(result)
                if progress_callback:
                    progress_callback(f"✅ Summarized chunk {result[0]}/{len(chunks)}")
            except Exception as e:
                print(f"Error summarizing chunk {i}:", e)

    # Step 5: Combine all summaries
    results.sort()
    combined_summary = "\n\n".join(text for _, text in results)

    if progress_callback:
        progress_callback("🧠 Generating final summary...")

    # Step 6: Final summary using the combined summary
    final_prompt = final_prompt_template.replace("{text}", combined_summary)
    final_summary = query_llama3(final_prompt)

    if progress_callback:
        progress_callback(f"🎉 Done in {time.time() - start_time:.1f} seconds.")

    return final_summary
