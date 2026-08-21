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

let currentDocId = null;
let modelReady = false;

// --- Model status polling ---------------------------------------------
const modelStatusEl = document.createElement("div");
modelStatusEl.id = "model-status";
modelStatusEl.className = "model-status";
document.querySelector(".ledger").prepend(modelStatusEl);

async function pollModelStatus() {
  try {
    const res = await fetch("/model-status");
    const data = await res.json();

    if (data.status === "ready") {
      modelReady = true;
      modelStatusEl.textContent = "● Model ready";
      modelStatusEl.className = "model-status ready";
      return; // stop polling
    }
    if (data.status === "error") {
      modelStatusEl.textContent = "● Model failed to load — check server terminal: " + (data.error || "");
      modelStatusEl.className = "model-status error";
      return; // stop polling, nothing more to wait for
    }
    if (data.status === "loading") {
      modelStatusEl.textContent = "● Connecting to Hugging Face Inference API…";
      modelStatusEl.className = "model-status loading";
    } else {
      modelStatusEl.textContent = "● Initializing model client…";
      modelStatusEl.className = "model-status loading";
    }
    setTimeout(pollModelStatus, 4000);
  } catch (err) {
    modelStatusEl.textContent = "● Could not reach server to check model status";
    modelStatusEl.className = "model-status error";
    setTimeout(pollModelStatus, 5000);
  }
}
pollModelStatus();

// --- Drag & drop niceties -------------------------------------------------
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
  title.textContent = fileInput.files.length ? fileInput.files[0].name : "Drop a document here";
}

// --- Upload ----------------------------------------------------------------
uploadForm.addEventListener("submit", async e => {
  e.preventDefault();
  if (!fileInput.files.length) {
    setStatus("Choose a file first.", "error");
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  uploadBtn.disabled = true;
  setStatus("Indexing document…", "");

  try {
    const res = await fetch("/upload", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) {
      setStatus(data.error || "Upload failed.", "error");
      return;
    }

    currentDocId = data.doc_id;
    docFilename.textContent = data.filename;
    docChunks.textContent = data.chunks_indexed;
    docRecord.classList.remove("hidden");

    setStatus("Document indexed. You can ask questions now.", "ok");
    questionInput.disabled = false;
    askBtn.disabled = false;
    chatLog.innerHTML = "";
  } catch (err) {
    setStatus("Network error while uploading.", "error");
  } finally {
    uploadBtn.disabled = false;
  }
});

function setStatus(message, kind) {
  uploadStatus.textContent = message;
  uploadStatus.className = "status" + (kind ? " " + kind : "");
}

// --- Ask ---------------------------------------------------------------
askForm.addEventListener("submit", async e => {
  e.preventDefault();
  const question = questionInput.value.trim();
  if (!question || !currentDocId) return;

  if (!modelReady) {
    addBubble("The model isn't ready yet — see the status line at the bottom of the page, or check the server terminal.", "answer error");
    return;
  }

  addBubble(question, "question");
  questionInput.value = "";
  askBtn.disabled = true;

  const pending = addBubble("Thinking…", "answer pending");

  try {
    const res = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: currentDocId, question }),
    });
    const data = await res.json();

    if (!res.ok) {
      pending.textContent = data.error || "Something went wrong.";
      pending.classList.add("error");
    } else {
      pending.textContent = data.answer;
      pending.classList.remove("pending");
    }
  } catch (err) {
    pending.textContent = "Network error while asking the model.";
  } finally {
    askBtn.disabled = false;
  }
});

function addBubble(text, cls) {
  const el = document.createElement("div");
  el.className = "bubble " + cls;
  el.textContent = text;
  chatLog.appendChild(el);
  chatLog.scrollTop = chatLog.scrollHeight;
  return el;
}
