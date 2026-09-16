function ensureAnswersVisible() {
  answersSection.classList.toggle("hidden", !answersList.children.length);
}

function makeAnswerActions(entry, { retry, copy }) {
  const actions = document.createElement("div");
  actions.className = "answer-actions";
  if (copy) {
    const copyBtn = document.createElement("button");
    copyBtn.className = "secondary";
    copyBtn.type = "button";
    copyBtn.textContent = "Copy";
    copyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(entry.answer || "");
        copyBtn.textContent = "Copied!";
        setTimeout(() => { copyBtn.textContent = "Copy"; }, 1200);
      } catch (_) {
        copyBtn.textContent = "Copy failed";
        showToast("Could not copy to clipboard.", { kind: "error" });
        setTimeout(() => { copyBtn.textContent = "Copy"; }, 1200);
      }
    });
    actions.appendChild(copyBtn);
  }
  if (retry) {
    const retryBtnEl = document.createElement("button");
    retryBtnEl.className = "secondary";
    retryBtnEl.type = "button";
    retryBtnEl.textContent = "Retry";
    retryBtnEl.addEventListener("click", async () => {
      try {
        await browser.runtime.sendMessage({ type: "RETRY_ANSWER", id: entry.id });
      } catch (e) {
        showToast(`Error: ${e.message}`, { kind: "error" });
      }
    });
    actions.appendChild(retryBtnEl);
  }
  const dismissBtn = document.createElement("button");
  dismissBtn.className = "secondary";
  dismissBtn.type = "button";
  dismissBtn.textContent = "Dismiss";
  dismissBtn.setAttribute("aria-label", "Dismiss answer");
  dismissBtn.addEventListener("click", async () => {
    const card = document.getElementById(entry.id);
    if (card) card.remove();
    ensureAnswersVisible();
    try {
      await browser.runtime.sendMessage({ type: "DISMISS_ANSWER", id: entry.id });
    } catch (_) {}
  });
  actions.appendChild(dismissBtn);
  return actions;
}

function upsertAnswerCard(entry, { prepend = true } = {}) {
  if (!entry || !entry.id) return;
  answersSection.classList.remove("hidden");
  let card = document.getElementById(entry.id);
  if (card && card.dataset.status === "done" && entry.status === "pending") return;
  if (!card) {
    card = document.createElement("div");
    card.className = "answer-card";
    card.id = entry.id;
    if (prepend) answersList.insertBefore(card, answersList.firstChild);
    else answersList.appendChild(card);
  }
  card.dataset.status = entry.status || "";
  card.textContent = "";
  const q = document.createElement("div");
  q.className = "question";
  const question = entry.question || "";
  q.textContent = question.length > 200 ? question.slice(0, 197) + "…" : question;
  q.title = question;
  card.appendChild(q);

  if (entry.status === "pending") {
    const body = document.createElement("div");
    body.className = "spinner";
    body.textContent = "Thinking…";
    card.appendChild(body);
    return;
  }

  if (entry.status === "error") {
    const body = document.createElement("div");
    body.className = "answer-text error";
    body.textContent = `Failed: ${entry.error || "unknown error"}`;
    card.appendChild(body);
    card.appendChild(makeAnswerActions(entry, { retry: true, copy: false }));
    return;
  }

  const answer = entry.answer || "";
  const body = document.createElement("div");
  body.className = "answer-text";
  body.textContent = answer;
  body.setAttribute("draggable", "true");
  body.addEventListener("dragstart", (e) => {
    e.dataTransfer.setData("text/plain", answer);
    e.dataTransfer.effectAllowed = "copy";
  });
  card.appendChild(body);
  card.appendChild(makeAnswerActions(entry, { retry: false, copy: true }));
}

async function restoreAnswerCards() {
  const stored = await browser.storage.local.get(ANSWERS_KEY);
  const answers = stored[ANSWERS_KEY];
  answersList.innerHTML = "";
  if (!Array.isArray(answers) || !answers.length) {
    answersSection.classList.add("hidden");
    return;
  }
  answers.forEach((entry) => upsertAnswerCard(entry, { prepend: false }));
  ensureAnswersVisible();
}
