"""
app.py
------
Task2 - Document Q&A system.

Flow:
  1. User uploads a document (PDF / DOCX / TXT) via the web UI.
  2. The server extracts the text and splits it into chunks, storing
     them in memory against a document id (returned to the browser).
  3. User asks a question about that document.
  4. The server retrieves the most relevant chunks (TF-IDF) and sends
     them + the question to the Hugging Face model (openai/gpt-oss-20b)
     which generates an answer grounded in the document content.

Run with:  python app.py
"""

import os
import uuid

from dotenv import load_dotenv
load_dotenv()  # loads HF_TOKEN (and any other vars) from .env

from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename

from document_reader import is_supported, extract_text, chunk_text
from retriever import get_relevant_chunks
from ai_engine import AIEngine

import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Use system temp directory for uploads so it works across local and read-only serverless filesystems (e.g. Vercel)
UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), "task2_uploads")
MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB per upload

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# In-memory store: { doc_id: {"filename": str, "chunks": list[str]} }
# For a production system, replace this with a real database.
DOCUMENT_STORE = {}


# Eagerly initialize the Inference client (lightweight, no thread needed)
AIEngine.start_loading()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_document():
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not is_supported(file.filename):
        return jsonify({"error": "Unsupported file type. Use PDF, DOCX, or TXT."}), 400

    filename = secure_filename(file.filename)
    doc_id = str(uuid.uuid4())
    saved_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{doc_id}_{filename}")
    file.save(saved_path)

    try:
        text = extract_text(saved_path)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Failed to read document: {exc}"}), 500

    if not text.strip():
        return jsonify({"error": "No extractable text found in the document."}), 400

    chunks = chunk_text(text)
    DOCUMENT_STORE[doc_id] = {"filename": filename, "chunks": chunks}

    return jsonify({
        "doc_id": doc_id,
        "filename": filename,
        "chunks_indexed": len(chunks),
        "message": "Document uploaded and indexed successfully.",
    })


@app.route("/model-status", methods=["GET"])
def model_status():
    if AIEngine.status == "not_started":
        AIEngine.start_loading()
    return jsonify({
        "status": AIEngine.status,
        "error": AIEngine.error_message,
    })


@app.route("/ask", methods=["POST"])
def ask_question():
    data = request.get_json(silent=True) or {}
    doc_id = data.get("doc_id")
    question = (data.get("question") or "").strip()

    if not doc_id or doc_id not in DOCUMENT_STORE:
        return jsonify({"error": "Unknown or missing doc_id. Upload a document first."}), 400

    if not question:
        return jsonify({"error": "Question cannot be empty."}), 400

    # Fail fast with a clear message instead of hanging if the client
    # isn't ready yet (missing HF_TOKEN, or failed to initialize).
    if AIEngine.status == "not_started":
        AIEngine.start_loading()  # safety net, shouldn't normally happen
        return jsonify({
            "error": "Inference client just started initializing. "
                     "Check /model-status and try again in a moment."
        }), 503
    if AIEngine.status == "error":
        return jsonify({
            "error": f"Model client failed to initialize: {AIEngine.error_message}"
        }), 500

    chunks = DOCUMENT_STORE[doc_id]["chunks"]
    print(f"[app] /ask doc_id={doc_id!r} chunks={len(chunks)} question={question!r}", flush=True)

    if not chunks:
        return jsonify({"error": "Document has no indexed chunks. Please re-upload the file."}), 400

    relevant_chunks = get_relevant_chunks(chunks, question, top_k=3)

    # Fall back to the first 3 chunks if TF-IDF returns nothing
    if not relevant_chunks:
        relevant_chunks = chunks[:3]

    context = "\n\n---\n\n".join(relevant_chunks)

    if not context.strip():
        return jsonify({"error": "Could not extract relevant content from the document."}), 400

    try:
        answer = AIEngine.answer_question(context, question)
    except Exception as exc:  # noqa: BLE001
        print(f"[app] /ask inference error: {exc}")
        return jsonify({"error": f"Model inference failed: {exc}"}), 500

    return jsonify({
        "answer": answer,
        "used_chunks": len(relevant_chunks),
    })


@app.route("/documents", methods=["GET"])
def list_documents():
    return jsonify([
        {"doc_id": doc_id, "filename": meta["filename"], "chunks": len(meta["chunks"])}
        for doc_id, meta in DOCUMENT_STORE.items()
    ])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
