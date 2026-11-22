from flask import Flask, render_template, request, jsonify
import os
import io
import re
import pdfplumber
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime
from zoneinfo import ZoneInfo

from rag import RAGPipeline, load_knowledge_base

app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))

api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1"
)

MODEL_NAME = "openai/gpt-oss-120b"

# Load FAISS Knowledge Base for the RAG Chatbot panel
kb_rag = load_knowledge_base(os.path.join(basedir, "knowledge.txt"))


def get_system_prompt(is_rag: bool = False) -> str:
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    today_str = now.strftime("%A, %B %d, %Y")
    base_prompt = (
        f"You are a helpful personal assistant. Today's date is {today_str}. "
        "Use this exact date for any calendar, day-of-week, or relative date questions. "
        "Answer ONLY the user's latest message directly and concisely. "
        "Use conversation history strictly for context when the user asks a follow-up or refers to earlier details. "
        "Never repeat previous answers or restate earlier personal details unless the user explicitly asks for them."
    )
    if is_rag:
        base_prompt += (
            " When Relevant Knowledge Base Context is provided, prioritize those retrieved facts accurately."
        )
    return base_prompt


# Separate chat histories for Left (Normal) and Right (RAG) panels
chat_history_normal = [{"role": "system", "content": get_system_prompt(is_rag=False)}]
chat_history_rag = [{"role": "system", "content": get_system_prompt(is_rag=True)}]


# --- PDF & Excel Extraction Helpers ---
def _clean_cell_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"\s*/\s*", "/", cleaned)
    cleaned = re.sub(r"\(\s+", "(", cleaned)
    cleaned = re.sub(r"\s+\)", ")", cleaned)
    return cleaned


def _should_merge_fragment(prev: str, curr: str) -> bool:
    if not prev or not curr:
        return False
    if prev.endswith((" ", ".", ",", ":", ";", "-", "/", ")")):
        return False
    return len(curr) <= 10 and " " not in curr and (curr.islower() or curr.isupper())


def format_pdf_tables(page) -> str:
    tables = page.extract_tables() or []
    formatted_rows = []
    for table in tables:
        for row in table:
            if not row:
                continue
            cells = [_clean_cell_text(str(c)) for c in row if c and _clean_cell_text(str(c))]
            if not cells:
                continue
            merged = []
            for cell in cells:
                if merged and _should_merge_fragment(merged[-1], cell):
                    merged[-1] += cell
                else:
                    merged.append(cell)
            deduped = []
            for item in merged:
                if not deduped or deduped[-1] != item:
                    deduped.append(item)
            if deduped:
                formatted_rows.append(deduped[0] if len(deduped) == 1 else " | ".join(deduped))
    return "\n".join(formatted_rows)


def extract_from_pdf(file_stream):
    extracted_parts = []
    with pdfplumber.open(file_stream) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            extracted_parts.append(f"--- Page {i} ---")
            text = page.extract_text()
            if text:
                extracted_parts.append(text)

            table_text = format_pdf_tables(page)
            if table_text:
                extracted_parts.append(f"\n[Extracted Tables on Page {i}]\n{table_text}")

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


# --- Routes ---
@app.route("/")
def hello_world():
    return render_template("index.html")


# LEFT PANEL: Standard Chatbot (Without RAG)
@app.route("/ask", methods=["POST"])
def ask():
    try:
        if not api_key:
            return jsonify({"response": "Error: OPENAI_API_KEY is missing from your .env file!"}), 200

        question = request.form.get("question", "").strip()
        if not question:
            return jsonify({"response": "Please enter a valid question."}), 200

        chat_history_normal[0]["content"] = get_system_prompt(is_rag=False)
        chat_history_normal.append({"role": "user", "content": question})

        recent_messages = [chat_history_normal[0]] + chat_history_normal[1:][-10:]

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=recent_messages,
            temperature=0.7,
            max_tokens=512
        )
        answer = response.choices[0].message.content.strip()
        chat_history_normal.append({"role": "assistant", "content": answer})
        return jsonify({"response": answer}), 200
    except Exception as e:
        return jsonify({"response": f"Backend Error: {str(e)}"}), 200


@app.route("/clear_chat", methods=["POST"])
def clear_chat():
    chat_history_normal.clear()
    chat_history_normal.append({"role": "system", "content": get_system_prompt(is_rag=False)})
    return jsonify({"status": "cleared"}), 200


# RIGHT PANEL: RAG Chatbot (With FAISS Knowledge Base)
@app.route("/ask_rag", methods=["POST"])
def ask_rag():
    try:
        if not api_key:
            return jsonify({"response": "Error: OPENAI_API_KEY is missing from your .env file!", "sources_count": 0}), 200

        question = request.form.get("question", "").strip()
        if not question:
            return jsonify({"response": "Please enter a valid question.", "sources_count": 0}), 200

        chat_history_rag[0]["content"] = get_system_prompt(is_rag=True)

        # Retrieve top relevant chunks from knowledge.txt using FAISS
        retrieved_chunks = kb_rag.retrieve(question, top_k=3)

        if retrieved_chunks:
            context_block = "\n---\n".join(retrieved_chunks)
            augmented_prompt = (
                f"Relevant Knowledge Base Context:\n{context_block}\n\n"
                f"User Question: {question}"
            )
        else:
            augmented_prompt = question

        chat_history_rag.append({"role": "user", "content": question})

        # Send recent history + augmented current question
        recent_messages = [chat_history_rag[0]] + chat_history_rag[1:-1][-9:] + [
            {"role": "user", "content": augmented_prompt}
        ]

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=recent_messages,
            temperature=0.5,
            max_tokens=512
        )
        answer = response.choices[0].message.content.strip()
        chat_history_rag.append({"role": "assistant", "content": answer})

        return jsonify({
            "response": answer,
            "sources_count": len(retrieved_chunks)
        }), 200
    except Exception as e:
        return jsonify({"response": f"Backend Error: {str(e)}", "sources_count": 0}), 200


@app.route("/clear_chat_rag", methods=["POST"])
def clear_chat_rag():
    chat_history_rag.clear()
    chat_history_rag.append({"role": "system", "content": get_system_prompt(is_rag=True)})
    return jsonify({"status": "cleared"}), 200


@app.route("/summarize", methods=["POST"])
def summarize():
    try:
        email_text = request.form.get("email", "").strip()
        prompt = f"Summarize the following email in 2-3 sentences: {email_text}"
        response = client.chat.completions.create(
            model=MODEL_NAME,
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

        # Use FAISS RAG for large documents when a specific question is asked
        doc_rag = RAGPipeline(chunk_size=800, overlap=120)
        num_chunks = doc_rag.build_index(extracted_data)

        if user_query and num_chunks > 3:
            top_chunks = doc_rag.retrieve(user_query, top_k=4, min_score=0.05)
            context_for_llm = "\n---\n".join(top_chunks) if top_chunks else extracted_data[:12000]
            prompt = (
                f"Answer the question using ONLY the retrieved document sections below:\n\n"
                f"{context_for_llm}\n\nQuestion: {user_query}"
            )
        else:
            instruction = user_query if user_query else "Summarize the key figures, tables, and financial insights from this document."
            prompt = f"{instruction}\n\nDocument Content:\n{extracted_data[:12000]}"

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are an expert financial and document analyst. Extract and present key numbers and insights clearly."},
                {"role": "user", "content": prompt}
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