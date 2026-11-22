import os
import json
import time
from dotenv import load_dotenv
from openai import OpenAI
from rag import load_knowledge_base

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)
MODEL_NAME = "openai/gpt-oss-120b"

kb_rag = load_knowledge_base(os.path.join(basedir, "knowledge.txt"))

# 1. Golden Test Dataset (Questions + Ground Truth from knowledge.txt)
TEST_SET = [
    {
        "question": "Where did Vinit Sarang complete his M.Tech and what was his CGPA?",
        "ground_truth": "Vinit Sarang completed his M.Tech in Computer Science from SVNIT Surat (2024–2026) with an 8.26 CGPA."
    },
    {
        "question": "Where did Vinit intern and what platform did he work on?",
        "ground_truth": "Vinit interned as an Associate Software Intern at Casepoint Pvt. Ltd. in Surat from January 2024 to June 2024, working on the TestCraft online assessment platform."
    },
    {
        "question": "What accuracy did Vinit achieve in his Human Activity Recognition project?",
        "ground_truth": "Vinit achieved 78% classification accuracy in his Human Activity Recognition (HAR) project using TensorFlow (CNN) and Scikit-learn (Random Forest)."
    },
    {
        "question": "What tech stack powers SnapClass?",
        "ground_truth": "SnapClass is built using Python, Streamlit, Supabase, and computer vision facial recognition."
    },
    {
        "question": "What are the main features of Vinit's AI Personal Assistant and where is it deployed?",
        "ground_truth": "Vinit's AI Personal Assistant features a side-by-side Standard vs. RAG Chatbot, an Email Summarizer, and a PDF/Excel/CSV Document Analyzer, and it is deployed on Render with Gunicorn."
    }
]


def generate_rag_answer(question: str, chunks: list[str]) -> str:
    context = "\n---\n".join(chunks) if chunks else "No context retrieved."
    prompt = f"Relevant Knowledge Base Context:\n{context}\n\nUser Question: {question}"
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "Answer concisely using ONLY the provided context. If the answer is not in the context, say you don't know."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=300
    )
    return resp.choices[0].message.content.strip()


def evaluate_sample(question: str, ground_truth: str, chunks: list[str], answer: str) -> dict:
    context_text = "\n---\n".join(chunks) if chunks else "NONE"
    judge_prompt = f"""
You are a strict RAG evaluator. Score the following RAG pipeline output from 0.0 to 1.0 on 4 metrics.
Return ONLY valid JSON with keys: context_precision, context_recall, faithfulness, answer_relevance.

Question: {question}
Ground Truth: {ground_truth}
Retrieved Contexts:
{context_text}

Generated Answer: {answer}

Scoring Rules:
- context_precision: Fraction of retrieved chunks that are relevant to answering the question (0.0 to 1.0).
- context_recall: How well the retrieved contexts cover all facts in the Ground Truth (0.0 to 1.0).
- faithfulness: Whether all claims in the Generated Answer are strictly supported by the Retrieved Contexts without hallucination (0.0 to 1.0).
- answer_relevance: How directly and completely the Generated Answer addresses the Question (0.0 to 1.0).
"""
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You output only raw JSON with float scores between 0.0 and 1.0."},
            {"role": "user", "content": judge_prompt}
        ],
        temperature=0.0,
        response_format={"type": "json_object"}
    )
    return json.loads(resp.choices[0].message.content)


def run_evaluation():
    totals = {
        "context_precision": 0.0,
        "context_recall": 0.0,
        "faithfulness": 0.0,
        "answer_relevance": 0.0
    }
    total_ret_ms = 0.0
    total_gen_ms = 0.0

    print(f"\nRunning RAG Evaluation on {len(TEST_SET)} test cases...\n")

    for i, item in enumerate(TEST_SET, start=1):
        q = item["question"]
        gt = item["ground_truth"]

        t0 = time.perf_counter()
        chunks = kb_rag.retrieve(q, top_k=3)
        ret_ms = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        answer = generate_rag_answer(q, chunks)
        gen_ms = (time.perf_counter() - t1) * 1000

        scores = evaluate_sample(q, gt, chunks, answer)

        total_ret_ms += ret_ms
        total_gen_ms += gen_ms

        print(f"Q{i}: {q}")
        print(f"  Retrieved Chunks: {len(chunks)} | Retrieval: {ret_ms:.1f} ms | Generation: {gen_ms:.0f} ms")
        print(f"  Context Precision: {scores['context_precision']:.2f} | Context Recall: {scores['context_recall']:.2f}")
        print(f"  Faithfulness:      {scores['faithfulness']:.2f} | Answer Relevance: {scores['answer_relevance']:.2f}")

        if min(scores.values()) < 1.0:
            print(f"  [Debug] Answer: {answer}")
            for c_idx, c in enumerate(chunks, start=1):
                preview = c.replace("\n", " ")[:120]
                print(f"  [Debug] Chunk {c_idx}: {preview}...")
        print()

        for k in totals:
            totals[k] += float(scores[k])

    n = len(TEST_SET)
    print("=" * 55)
    print("AVERAGE RAG CHATBOT SCORES")
    print("=" * 55)
    for k, v in totals.items():
        print(f"{k.replace('_', ' ').title():<20}: {v / n:.2f}")
    print("-" * 55)
    print(f"{'Avg Retrieval Time':<20}: {total_ret_ms / n:.1f} ms")
    print(f"{'Avg Generation Time':<20}: {total_gen_ms / n:.0f} ms")


if __name__ == "__main__":
    run_evaluation()