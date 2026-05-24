function showForm() {
  mainView.classList.add("hidden");
  scanView.classList.add("hidden");
  formView.classList.remove("hidden");
}

function showMain() {
  formView.classList.add("hidden");
  scanView.classList.add("hidden");
  mainView.classList.remove("hidden");
}

function showScan() {
  formView.classList.add("hidden");
  mainView.classList.add("hidden");
  scanView.classList.remove("hidden");
}
