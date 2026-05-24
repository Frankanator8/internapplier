function normalize(s) {
  return (s || "").toString().toLowerCase().replace(/\s+/g, " ").trim();
}
