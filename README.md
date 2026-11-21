# AI Personal Assistant & Document Analyzer

**Live Demo:** [https://ai-chatbot-doc-analyzer.onrender.com/](https://ai-chatbot-doc-analyzer.onrender.com/)

A full-stack Flask web application powered by LLMs via the Groq API (`openai/gpt-oss-120b`), featuring a multi-turn conversational chatbot, a concise email summarizer, and a PDF/Excel/CSV financial and document extractor.

## Key Features
- **Multi-Turn AI Chatbot:** Maintains recent conversation context (`SYSTEM_PROMPT` + last 10 messages), supports clearing chat history (`/clear_chat`), and renders formatted responses (lists, tables, bold text) using Marked.js.
- **Email Summarizer:** Condenses pasted email threads into a crisp 2–3 sentence summary (`/summarize`).
- **PDF & Spreadsheet Extractor:** Extracts page text and structured tables from PDFs (`pdfplumber` with text-alignment table rules) as well as sheets/rows from `.xlsx`, `.xls`, and `.csv` files (`pandas` and `openpyxl`), then generates targeted financial insights or answers custom queries (`/extract`).

## Tech Stack
- **Backend:** Python, Flask, Gunicorn
- **LLM Integration:** Groq API (`https://api.groq.com/openai/v1`) with `openai/gpt-oss-120b`
- **Document & Tabular Parsing:** `pdfplumber`, `pandas`, `openpyxl`
- **Frontend:** HTML5, CSS3, JavaScript, Marked.js
- **Deployment:** Render

## Project Structure
```text
├── main.py              # Flask application, LLM endpoints, and PDF/Excel extractors
├── requirements.txt     # Python dependencies
├── .gitignore           # Excludes .env, __pycache__, and local IDE files
├── static/
│   └── style.css        # Application styles
└── templates/
    └── index.html       # Frontend UI and client-side request handling
