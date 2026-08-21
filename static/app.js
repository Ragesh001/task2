const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const uploadForm = document.getElementById("upload-form");
const uploadStatus = document.getElementById("upload-status");
const uploadBtn = document.getElementById("upload-btn");

const docRecord = document.getElementById("doc-record");
const docFilename = document.getElementById("doc-filename");
const docChunks = document.getElementById("doc-chunks");

const askForm = document.getElementById("ask-form");
const questionInput = document.getElementById("question-input");
const askBtn = document.getElementById("ask-btn");
const chatLog = document.getElementById("chat-log");
const modelStatusEl = document.getElementById("model-status");
const modelStatusText = modelStatusEl ? modelStatusEl.querySelector(".status-text") : null;

let currentDocId = null;
let modelReady = false;

// --- Model Status Polling ---------------------------------------------
async function pollModelStatus() {
  try {
    const res = await fetch("/model-status");
    const data = await res.json();

    if (data.status === "ready") {
      modelReady = true;
      if (modelStatusEl) {
        modelStatusEl.className = "status-pill ready";
        if (modelStatusText) modelStatusText.textContent = "AI Ready";
      }
      return;
    }

    if (data.status === "error") {
      if (modelStatusEl) {
        modelStatusEl.className = "status-pill error";
        if (modelStatusText) modelStatusText.textContent = "API Error";
      }
      return;
    }

    if (modelStatusEl) {
      modelStatusEl.className = "status-pill loading";
      if (modelStatusText) modelStatusText.textContent = "Connecting...";
    }
    setTimeout(pollModelStatus, 3000);
  } catch (err) {
    if (modelStatusEl) {
      modelStatusEl.className = "status-pill error";
      if (modelStatusText) modelStatusText.textContent = "Offline";
    }
    setTimeout(pollModelStatus, 5000);
  }
}

pollModelStatus();

// --- Drag & Drop ------------------------------------------------------
["dragenter", "dragover"].forEach(evt =>
  dropzone.addEventListener(evt, e => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  })
);

["dragleave", "drop"].forEach(evt =>
  dropzone.addEventListener(evt, e => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  })
);

dropzone.addEventListener("drop", e => {
  if (e.dataTransfer.files.length) {
    fileInput.files = e.dataTransfer.files;
    updateDropzoneLabel();
  }
});

fileInput.addEventListener("change", updateDropzoneLabel);

function updateDropzoneLabel() {
  const title = dropzone.querySelector(".dropzone-title");
  if (fileInput.files.length) {
    title.textContent = fileInput.files[0].name;
  } else {
    title.textContent = "Choose a file or drag here";
  }
}

// --- Upload Document --------------------------------------------------
uploadForm.addEventListener("submit", async e => {
  e.preventDefault();
  if (!fileInput.files.length) {
    setStatus("Please select a document first.", "error");
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  // Reset state before upload so stale doc_id is never used
  currentDocId = null;
  askBtn.disabled = true;
  questionInput.disabled = true;
  uploadBtn.disabled = true;
  setStatus("Extracting text and indexing chunks...", "");

  try {
    const res = await fetch("/upload", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) {
      setStatus(data.error || "Upload failed.", "error");
      return;
    }

    currentDocId = data.doc_id;          // Set AFTER successful response
    docFilename.textContent = data.filename;
    docChunks.textContent = data.chunks_indexed;
    docRecord.classList.remove("hidden");

    setStatus("Document indexed! You can ask questions below.", "ok");
    questionInput.disabled = false;
    askBtn.disabled = false;
    questionInput.value = "";
    questionInput.focus();

    // Clear chat log for fresh session
    chatLog.innerHTML = "";
  } catch (err) {
    setStatus("Network error while uploading.", "error");
  } finally {
    uploadBtn.disabled = false;
  }
});

function setStatus(message, kind) {
  if (!message) {
    uploadStatus.textContent = "";
    uploadStatus.className = "status-banner";
    return;
  }
  uploadStatus.textContent = message;
  uploadStatus.className = "status-banner visible " + (kind || "");
}

// --- Ask Question -----------------------------------------------------
// Allow pressing Enter to submit (Shift+Enter for newline)
questionInput.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!askBtn.disabled) {
      askForm.requestSubmit();
    }
  }
});

askForm.addEventListener("submit", async e => {
  e.preventDefault();
  const question = questionInput.value.trim();
  if (!question || !currentDocId) return;

  if (!modelReady) {
    addBubble("The AI model is still initializing. Please wait a moment.", "answer error");
    return;
  }

  addBubble(question, "question");
  questionInput.value = "";
  askBtn.disabled = true;

  const pending = addBubble("Thinking...", "answer pending");

  try {
    const res = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: currentDocId, question }),
    });
    const data = await res.json();

    if (!res.ok) {
      pending.textContent = data.error || "Failed to generate answer.";
      pending.classList.remove("pending");
      pending.classList.add("error");
    } else {
      pending.innerHTML = renderMarkdown(data.answer);
      pending.classList.remove("pending");
    }
  } catch (err) {
    pending.textContent = "Network connection issue while communicating with server.";
    pending.classList.remove("pending");
    pending.classList.add("error");
  } finally {
    askBtn.disabled = false;
    questionInput.focus();
  }
});

// ── Lightweight Markdown → HTML renderer ───────────────────────────────────
function renderMarkdown(text) {
  // Escape HTML first to prevent XSS
  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Fenced code blocks  ```...```
  html = html.replace(/```([\s\S]*?)```/g, (_, code) =>
    `<pre><code>${code.trim()}</code></pre>`);

  // Headings  ### ## #
  html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");

  // Horizontal rule
  html = html.replace(/^---+$/gm, "<hr>");

  // Blockquote
  html = html.replace(/^&gt; (.+)$/gm, "<blockquote>$1</blockquote>");

  // Bold **text** or __text__
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/__(.+?)__/g, "<strong>$1</strong>");

  // Italic *text* or _text_
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  html = html.replace(/_(.+?)_/g, "<em>$1</em>");

  // Inline code `code`
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Numbered list  1. item
  html = html.replace(/^(\d+\. .+(?:\n(?!\d+\. |[-*] |#|```|---)[^\n]*)*)/gm, (block) => {
    const items = block.split(/\n(?=\d+\. )/);
    const lis = items.map(item => `<li>${item.replace(/^\d+\. /, "")}</li>`).join("");
    return `<ol>${lis}</ol>`;
  });

  // Unordered list  - item  or  * item
  html = html.replace(/^([-*] .+(?:\n(?!\d+\. |[-*] |#|```|---)[^\n]*)*)/gm, (block) => {
    const items = block.split(/\n(?=[-*] )/);
    const lis = items.map(item => `<li>${item.replace(/^[-*] /, "")}</li>`).join("");
    return `<ul>${lis}</ul>`;
  });

  // Paragraphs — wrap lines not already in block tags
  html = html
    .split(/\n{2,}/)
    .map(para => {
      para = para.trim();
      if (!para) return "";
      if (/^<(h[1-3]|ul|ol|pre|hr|blockquote)/.test(para)) return para;
      return `<p>${para.replace(/\n/g, "<br>")}</p>`;
    })
    .join("\n");

  return html;
}

function addBubble(text, cls) {
  const el = document.createElement("div");
  el.className = "bubble " + cls;

  if (cls.includes("answer") && !cls.includes("pending") && !cls.includes("error")) {
    el.innerHTML = renderMarkdown(text);
  } else {
    el.textContent = text;
  }

  chatLog.appendChild(el);
  chatLog.scrollTop = chatLog.scrollHeight;
  return el;
}
