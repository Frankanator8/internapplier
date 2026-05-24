let _answerCounter = 0;

function renderAnswerCard(question) {
  answersSection.classList.remove("hidden");
  const id = `answer-${++_answerCounter}`;
  const card = document.createElement("div");
  card.className = "answer-card";
  card.id = id;
  const q = document.createElement("div");
  q.className = "question";
  q.textContent = question.length > 200 ? question.slice(0, 197) + "…" : question;
  q.title = question;
  card.appendChild(q);
  const body = document.createElement("div");
  body.className = "spinner";
  body.textContent = "Thinking…";
  card.appendChild(body);
  answersList.insertBefore(card, answersList.firstChild);
  return { card, body };
}

function finalizeAnswerCard(card, body, answer) {
  body.className = "answer-text";
  body.textContent = answer;
  body.setAttribute("draggable", "true");
  body.addEventListener("dragstart", (e) => {
    e.dataTransfer.setData("text/plain", answer);
    e.dataTransfer.effectAllowed = "copy";
  });
  const actions = document.createElement("div");
  actions.className = "answer-actions";
  const copyBtn = document.createElement("button");
  copyBtn.className = "secondary";
  copyBtn.textContent = "Copy";
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(answer);
      copyBtn.textContent = "Copied!";
      setTimeout(() => { copyBtn.textContent = "Copy"; }, 1200);
    } catch (_) {}
  });
  const dismissBtn = document.createElement("button");
  dismissBtn.className = "secondary";
  dismissBtn.textContent = "×";
  dismissBtn.title = "Dismiss";
  dismissBtn.style.flex = "0";
  dismissBtn.addEventListener("click", () => {
    card.remove();
    if (!answersList.children.length) answersSection.classList.add("hidden");
  });
  actions.appendChild(copyBtn);
  actions.appendChild(dismissBtn);
  card.appendChild(actions);
}

function failAnswerCard(card, body, error) {
  body.className = "answer-text";
  body.style.color = "#b91c1c";
  body.textContent = `Failed: ${error || "unknown error"}`;
}
