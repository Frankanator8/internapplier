async function askQuestion(question) {
  const trimmed = (question || "").replace(/\s+/g, " ").trim();
  if (!trimmed) {
    resultEl.textContent = "No question text picked.";
    return;
  }
  const { card, body } = renderAnswerCard(trimmed);
  const appUuid = selectedApplicationUuid();
  try {
    const reply = await browser.runtime.sendMessage({
      type: "ANSWER_QUESTION",
      question: trimmed,
      application_uuid: appUuid,
    });
    if (reply && reply.ok && reply.answer) {
      finalizeAnswerCard(card, body, reply.answer);
      resultEl.textContent = "Answer ready — copied to clipboard.";
      try { await navigator.clipboard.writeText(reply.answer); } catch (_) {}
    } else {
      failAnswerCard(card, body, (reply && reply.error) || "no answer");
      resultEl.textContent = "AI answer failed.";
    }
  } catch (e) {
    failAnswerCard(card, body, e.message);
  }
}

askBtn.addEventListener("click", async () => {
  resultEl.textContent = "Click a question on the page (Esc to cancel)…";
  try {
    await browser.runtime.sendMessage({ type: "START_PICKER", field: "question" });
  } catch (e) {
    resultEl.textContent = `Error: ${e.message}`;
  }
});
