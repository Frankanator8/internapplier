const FIELD_TO_INPUT = {
  company: fCompany,
  role: fRole,
  date: fDate,
  link: fLink,
  notes: fNotes,
  description: fDescription,
};

let defaultStatus = "Added";

function todayISO() {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

function readForm() {
  return {
    company: fCompany.value.trim(),
    role: fRole.value.trim(),
    date: fDate.value.trim(),
    link: fLink.value.trim(),
    status: fStatus.value,
    notes: fNotes.value.trim(),
    description: fDescription.value.trim(),
  };
}

function writeForm(data) {
  fCompany.value = data.company || "";
  fRole.value = data.role || "";
  fDate.value = data.date || todayISO();
  fLink.value = data.link || "";
  if (data.status) fStatus.value = data.status;
  else fStatus.value = defaultStatus;
  fNotes.value = data.notes || "";
  fDescription.value = data.description || "";
}
