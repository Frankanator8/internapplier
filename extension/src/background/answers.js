async function readAnswerEntries() {
  const stored = await browser.storage.local.get(ANSWERS_KEY);
  return Array.isArray(stored[ANSWERS_KEY]) ? stored[ANSWERS_KEY] : [];
}

async function writeAnswerEntries(answers) {
  await browser.storage.local.set({ [ANSWERS_KEY]: answers });
}

function notifyAnswerUpdated(entry) {
  browser.runtime.sendMessage({ type: "ANSWER_UPDATED", entry }).catch(() => {});
}

async function startAnswerJob(question, applicationUuid) {
  const id = `answer-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  const entry = {
    id,
    question: question || "",
    applicationUuid: applicationUuid || null,
    status: "pending",
    answer: "",
    error: "",
  };
  const answers = await readAnswerEntries();
  await writeAnswerEntries([entry, ...answers]);
  notifyAnswerUpdated(entry);
  runAnswerJob(id, entry.question, entry.applicationUuid);
  return { ok: true, id, pending: true, entry };
}

async function runAnswerJob(id, question, applicationUuid) {
  const reply = await answerQuestion(question, applicationUuid);
  const answers = await readAnswerEntries();
  let updated = null;
  const next = answers.map((a) => {
    if (a.id !== id) return a;
    updated = reply && reply.ok
      ? { ...a, status: "done", answer: reply.answer || "", error: "" }
      : { ...a, status: "error", error: (reply && reply.error) || "no answer", answer: "" };
    return updated;
  });
  await writeAnswerEntries(next);
  if (updated) notifyAnswerUpdated(updated);
}

async function retryAnswer(id) {
  const answers = await readAnswerEntries();
  const existing = answers.find((a) => a.id === id);
  if (!existing) return { ok: false, error: "not found" };
  const pending = { ...existing, status: "pending", error: "", answer: "" };
  await writeAnswerEntries(answers.map((a) => (a.id === id ? pending : a)));
  notifyAnswerUpdated(pending);
  runAnswerJob(id, existing.question, existing.applicationUuid || null);
  return { ok: true, id, pending: true, entry: pending };
}

async function dismissAnswer(id) {
  const answers = await readAnswerEntries();
  await writeAnswerEntries(answers.filter((a) => a.id !== id));
  browser.runtime.sendMessage({ type: "ANSWER_DISMISSED", id }).catch(() => {});
  return { ok: true };
}
