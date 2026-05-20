const dot = document.getElementById("dot");
const statusText = document.getElementById("status-text");
const nameEl = document.getElementById("name");
const fillBtn = document.getElementById("fill-btn");
const resultEl = document.getElementById("result");

const API_BASE = "http://127.0.0.1:8765";

async function refreshStatus() {
  let ok = false;
  try {
    const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
    ok = res.ok;
  } catch (_) {
    ok = false;
  }
  dot.classList.remove("ok", "err");
  if (ok) {
    dot.classList.add("ok");
    statusText.textContent = "Connected to localhost:8765";
    fillBtn.disabled = false;
    try {
      const res = await fetch(`${API_BASE}/profile/general_info`);
      const info = await res.json();
      const name = [info.first_name, info.last_name].filter(Boolean).join(" ");
      nameEl.textContent = name ? `Profile: ${name}` : "Profile loaded (no name)";
    } catch (_) {
      nameEl.textContent = "";
    }
  } else {
    dot.classList.add("err");
    statusText.textContent = "Server unreachable";
    fillBtn.disabled = true;
    nameEl.textContent = "";
  }
}

fillBtn.addEventListener("click", async () => {
  resultEl.textContent = "Filling…";
  fillBtn.disabled = true;
  try {
    const reply = await browser.runtime.sendMessage({ type: "AUTOFILL_ACTIVE_TAB" });
    if (reply && reply.ok) {
      resultEl.textContent = "Done.";
    } else {
      resultEl.textContent = "Could not autofill.";
    }
  } catch (e) {
    resultEl.textContent = `Error: ${e.message}`;
  } finally {
    fillBtn.disabled = false;
  }
});

refreshStatus();
