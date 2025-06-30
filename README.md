# 🧠 PDF Report Summarizer
This is a **Streamlit-based application** that allows users to upload PDF reports and generate concise, structured summaries using the **LLaMA3** model through **Ollama**.
---

## 🔧 Features

- 📄 Upload and OCR-based text extraction from PDFs
- 🧩 Chunked summarization and final summary synthesis
- 🎯 Selectable report types: MPR, Board Report, Financial, etc.
- 📊 Page count estimation and time-to-completion display
- 🎛️ Custom or auto-limit on final summary page size
- 🟢 Progress bar with real-time chunk status
- ⛔ Stop processing at any point
- 🖨️ Copy/print support and styled HTML preview/download
- 🧠 Final summary always retained unless reset manually
- 🎛️ Final summaries are generated using user-selected prompt templates.
- 🧩 You can toggle chunk-level results and constrain length using a page selector.
- ⛔ Automatically prevents system sleep during long runs.
- 🎛️ Summary remains until a new file is uploaded or reset.
---

## 🧠 Model Used
- Model: llama3:8b-instruct-q4_K_M
- Manager: [Ollama](https://ollama.com/)
- ollama pull llama3:8b-instruct-q4_K_M
- Auto-launched via subprocess if not already running

## 📦 Requirements
- Python 3.8+
- [Tesseract-OCR](https://github.com/tesseract-ocr/tesseract) (Installed and added to PATH)
- [Poppler](https://github.com/oschwartz10612/poppler-windows/releases) for PDF-to-image conversion (on Windows)

> ⚠️ Make sure you manually configure:
> - `pytesseract.pytesseract.tesseract_cmd` in `summarizer_pipeline.py`
> - `poppler_bin` path in `summarizer_pipeline.py`

## ✅ Dependencies (requirements.txt)
> UI & Web App
- streamlit
- markdown
> PDF Processing
- PyMuPDF==1.23.21        # used as `fitz` to extract text from PDFs
- pdf2image==1.16.3        # converts PDF pages to images for OCR

> OCR
- pytesseract==0.3.10      # OCR engine (must install Tesseract binary separately)
> HTTP Requests
- requests

pip install -r requirements.txt

## 🔧 External Dependencies
These tools must be installed separately and added to your system PATH.

- 📌 **1. Tesseract OCR**
Used for extracting text from scanned PDF images.
- [Tesseract-OCR](https://github.com/tesseract-ocr/tesseract) (Installed and added to PATH) 

- 📌 **2. Poppler for Windows**
Used by pdf2image to convert PDF pages into images.
- [Poppler](https://github.com/oschwartz10612/poppler-windows/releases) for PDF-to-image conversion  

---
## 🏁 How to Run
1. **Clone the Repository**
   ```bash
   git clone https://github.com/your-user/pdf-summarizer.git
   cd pdf-summarizer

2. **Install Python Dependencies**
   ```bash
     pip install -r requirements.txt

3. **Launch Streamlit App**
   ``` bash
    streamlit run summarizers.py


## 📁 Project Structure
pdf-summarizer/
├── summarizers.py              # Main Streamlit frontend app
├── summarizer_pipeline.py     # Backend summarization pipeline
├── prompts/                   # Prompt templates
│   ├── mpr_prompt.txt
│   ├── final_mpr_prompt.txt
│   ├── board_prompt.txt
│   └── final_board_prompt.txt
├── cache/                     # OCR cache directory
├── img/
│   └── yourimg.png            # Optional logo for styled summary
├── requirements.txt
└── README.md


## 👨‍💻 Author - Ejike Ozonkwo
- [LinkedIn](https://www.linkedin.com/in/ozonkwoejike/)
- [Github](https://www.linkedin.com/in/ozonkwoejike/)

## 🤝 Contributing
Pull requests welcome. Open issues for enhancements or bugs.

## 🧾 License
MIT License