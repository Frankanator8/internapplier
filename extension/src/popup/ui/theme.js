const systemDarkMQ = window.matchMedia("(prefers-color-scheme: dark)");
let themePreference = "system";

function applyThemeFromPreference() {
  const effective =
    themePreference === "dark" ||
    (themePreference === "system" && systemDarkMQ.matches);
  document.body.classList.toggle("dark", effective);
}

function applyTheme(pref) {
  themePreference = pref === "light" || pref === "dark" ? pref : "system";
  applyThemeFromPreference();
}

systemDarkMQ.addEventListener("change", () => {
  if (themePreference === "system") applyThemeFromPreference();
});

async function loadTheme() {
  try {
    const res = await fetch(`${API_BASE}/theme`, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      applyTheme(data && data.preference);
      return;
    }
  } catch (_) {}
  applyTheme("system");
}

applyTheme("system");
