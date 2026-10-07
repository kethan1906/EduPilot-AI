// All data comes from the Flask REST API. Text is inserted with textContent
// (never innerHTML) so document/LLM text can't inject markup.

const $ = (id) => document.getElementById(id);

async function api(path, options) {
  const response = await fetch(path, options);
  let body = {};
  try { body = await response.json(); } catch (_) { /* non-JSON error page */ }
  if (!response.ok) {
    throw new Error(body.error || `Request failed (${response.status})`);
  }
  return body;
}

function setStatus(message, kind) {
  const el = $("uploadStatus");
  el.textContent = message;
  el.className = "status" + (kind ? " " + kind : "");
}

function emptyItem(text) {
  const li = document.createElement("li");
  li.className = "empty";
  li.textContent = text;
  return li;
}

async function loadDocuments() {
  const list = $("documentList");
  try {
    const { documents } = await api("/api/documents");
    list.replaceChildren();
    if (!documents.length) { list.appendChild(emptyItem("No documents yet.")); return; }
    for (const doc of documents) {
      const li = document.createElement("li");
      const name = document.createElement("div");
      name.textContent = doc.filename;
      const meta = document.createElement("div");
      meta.className = "meta";
      const badge = document.createElement("span");
      badge.className = "badge " + doc.status;
      badge.textContent = doc.status;
      meta.append(badge, ` ${doc.chunk_count} chunks`);
      li.append(name, meta);
      list.appendChild(li);
    }
  } catch (err) {
    list.replaceChildren(emptyItem("Could not load documents: " + err.message));
  }
}

async function loadHistory() {
  const list = $("historyList");
  try {
    const { queries } = await api("/api/queries");
    list.replaceChildren();
    if (!queries.length) { list.appendChild(emptyItem("No questions asked yet.")); return; }
    for (const item of queries) {
      const li = document.createElement("li");
      const q = document.createElement("div");
      q.className = "q";
      q.textContent = item.question;
      const a = document.createElement("div");
      a.className = "a";
      a.textContent = item.answer;
      li.append(q, a);
      list.appendChild(li);
    }
  } catch (err) {
    list.replaceChildren(emptyItem("Could not load history: " + err.message));
  }
}

$("fileInput").addEventListener("change", () => {
  const file = $("fileInput").files[0];
  $("fileLabel").textContent = file ? file.name : "Choose a PDF";
});

$("uploadForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = $("fileInput").files[0];
  if (!file) { setStatus("Choose a PDF first.", "err"); return; }

  const formData = new FormData();
  formData.append("file", file);
  $("uploadButton").disabled = true;
  setStatus("Extracting, chunking and embedding. This can take a while...");
  try {
    const result = await api("/api/documents", { method: "POST", body: formData });
    setStatus(`Indexed ${result.filename}: ${result.chunk_count} chunks.`, "ok");
    $("uploadForm").reset();
    $("fileLabel").textContent = "Choose a PDF";
  } catch (err) {
    setStatus(err.message, "err");
  } finally {
    $("uploadButton").disabled = false;
    loadDocuments();
  }
});

$("askForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = $("questionInput").value.trim();
  const errorEl = $("askError");
  errorEl.hidden = true;
  if (!question) {
    errorEl.textContent = "Please type a question.";
    errorEl.hidden = false;
    return;
  }

  $("askButton").disabled = true;
  $("askButton").textContent = "Thinking...";
  try {
    const data = await api("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    $("answer").textContent = data.answer;
    const sources = $("sources");
    sources.replaceChildren();
    if (!data.sources.length) sources.appendChild(emptyItem("No sources retrieved."));
    for (const s of data.sources) {
      const li = document.createElement("li");
      const where = document.createElement("span");
      where.className = "where";
      where.textContent = `${s.filename}, page ${s.page}`;
      const score = document.createElement("span");
      score.className = "score";
      score.textContent = "similarity " + Number(s.score).toFixed(3);
      li.append(where, score);
      sources.appendChild(li);
    }
    $("answerPanel").hidden = false;
    loadHistory();
  } catch (err) {
    $("answerPanel").hidden = true;
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  } finally {
    $("askButton").disabled = false;
    $("askButton").textContent = "Ask";
  }
});

loadDocuments();
loadHistory();
