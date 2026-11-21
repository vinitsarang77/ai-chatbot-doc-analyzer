from flask import Flask, render_template, request, jsonify
import os
import io
import pdfplumber
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime
from zoneinfo import ZoneInfo

app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))

api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1"
)

SYSTEM_PROMPT = (
    "You are a helpful personal assistant. "
    "Answer ONLY the user's latest message directly and concisely. "
    "Use conversation history strictly for context when the user asks a follow-up or refers to earlier details. "
    "Never repeat previous answers or restate earlier personal details unless the user explicitly asks for them."
)

# ADD THIS RIGHT HERE:
chat_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

def get_system_prompt():
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    today_str = now.strftime("%A, %B %d, %Y")
    return (
        f"You are a helpful AI assistant. Today's date is {today_str}. "
        "Use this exact date for any calendar, day-of-week, or relative date questions."
    )

def extract_from_pdf(file_stream):
    extracted_parts = []
    table_settings = {
        "vertical_strategy": "text",
        "horizontal_strategy": "text",
        "snap_tolerance": 3,
    }

    with pdfplumber.open(file_stream) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            extracted_parts.append(f"--- Page {i} ---")
            text = page.extract_text()
            if text:
                extracted_parts.append(text)

            tables = page.extract_tables(table_settings=table_settings)
            for t_idx, table in enumerate(tables, start=1):
                # Keep only rows that have at least one non-empty cell
                valid_rows = [
                    [str(cell).strip() if cell else "" for cell in row]
                    for row in table
                    if any(cell and str(cell).strip() for cell in row)
                ]
                if valid_rows:
                    extracted_parts.append(f"\n[Table {t_idx} on Page {i}]")
                    for clean_row in valid_rows:
                        extracted_parts.append(" | ".join(clean_row))

    return "\n".join(extracted_parts)

def extract_from_excel(file_stream, filename):
    extracted_parts = []
    if filename.endswith(".csv"):
        df = pd.read_csv(file_stream)
        extracted_parts.append(df.to_string(index=False))
    else:
        excel_file = pd.ExcelFile(file_stream)
        for sheet_name in excel_file.sheet_names:
            df = excel_file.parse(sheet_name)
            extracted_parts.append(f"--- Sheet: {sheet_name} ---")
            extracted_parts.append(df.to_string(index=False))
    return "\n\n".join(extracted_parts)

@app.route("/")
def hello_world():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    try:
        if not api_key:
            return jsonify({"response": "Error: OPENAI_API_KEY is missing from your .env file!"}), 200

        question = request.form.get("question")
        chat_history.append({"role": "user", "content": question})

        # Keep system prompt + last 10 messages (without duplicating system prompt)
        recent_messages = [chat_history[0]] + chat_history[1:][-10:]
        
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=recent_messages,   # <-- Pass recent_messages here!
            temperature=0.7,
            max_tokens=512
        )
        answer = response.choices[0].message.content.strip()
        chat_history.append({"role": "assistant", "content": answer})
        return jsonify({"response": answer}), 200
    except Exception as e:
        return jsonify({"response": f"Backend Error: {str(e)}"}), 200

@app.route("/clear_chat", methods=["POST"])
def clear_chat():
    chat_history.clear()
    chat_history.append({"role": "system", "content": SYSTEM_PROMPT})
    return jsonify({"status": "cleared"}), 200

@app.route("/summarize", methods=["POST"])
def summarize():
    try:
        email_text = request.form.get("email")
        prompt = f"summarize the following email in 2-3 sentences: {email_text}"
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": "Act like an expert email assistant"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=512
        )
        summary = response.choices[0].message.content.strip()
        return jsonify({"response": summary}), 200
    except Exception as e:
        return jsonify({"response": f"Backend Error: {str(e)}"}), 200

@app.route("/extract", methods=["POST"])
def extract():
    try:
        if "file" not in request.files:
            return jsonify({"response": "Error: No file uploaded."}), 200

        file = request.files["file"]
        user_query = request.form.get("query", "").strip()
        filename = file.filename.lower()

        if filename == "":
            return jsonify({"response": "Error: No file selected."}), 200

        file_bytes = io.BytesIO(file.read())

        if filename.endswith(".pdf"):
            extracted_data = extract_from_pdf(file_bytes)
        elif filename.endswith((".xlsx", ".xls", ".csv")):
            extracted_data = extract_from_excel(file_bytes, filename)
        else:
            return jsonify({"response": "Unsupported file type. Upload a PDF, Excel (.xlsx/.xls), or CSV file."}), 200

        if not extracted_data.strip():
            return jsonify({"response": "No text or tables could be extracted from this file."}), 200

        # Limit text sent to LLM to avoid token limit errors on huge files
        truncated_data = extracted_data[:12000]
        instruction = user_query if user_query else "Summarize the key figures, tables, and financial insights from this document."

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": "You are an expert financial and document analyst. Extract and present key numbers and insights clearly."},
                {"role": "user", "content": f"{instruction}\n\nDocument Content:\n{truncated_data}"}
            ],
            temperature=0.2,
            max_tokens=1024
        )
        analysis = response.choices[0].message.content.strip()

        return jsonify({
            "analysis": analysis,
            "extracted_text": extracted_data
        }), 200

    except Exception as e:
        return jsonify({"response": f"Backend Error: {str(e)}"}), 200

if __name__ == "__main__":
    app.run(debug=True)

