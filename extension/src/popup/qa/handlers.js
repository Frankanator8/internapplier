async function askQuestion(question) {
  const trimmed = (question || "").replace(/\s+/g, " ").trim();
  if (!trimmed) {
    showToast("No question text picked.", { kind: "warn" });
    return;
  }
  try {
    const reply = await browser.runtime.sendMessage({
      type: "ANSWER_QUESTION",
      question: trimmed,
      application_uuid: selectedApplicationUuid(),
    });
    if (reply && reply.entry) upsertAnswerCard(reply.entry);
    else if (reply && reply.id) {
      upsertAnswerCard({
        id: reply.id,
        question: trimmed,
        status: "pending",
        answer: "",
        error: "",
      });
    }
    showToast("Thinking…", { persist: true });
  } catch (e) {
    showToast(`Error: ${e.message}`, { kind: "error" });
  }
}

askBtn.addEventListener("click", async () => {
  await startPagePicker("question", "Click a question on the page (Esc to cancel)…");
});
