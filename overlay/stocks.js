async function loadStocks() {
  const res = await fetch("/data/stocks.json");
  const data = await res.json();

  setStock("kospi", data.kospi);
  setStock("kosdaq", data.kosdaq);
  setStock("dow", data.dow);
  setStock("nasdaq", data.nasdaq);
}

function setStock(id, value) {
  const el = document.getElementById(id);
  el.textContent = value;
  el.className = value.startsWith("-") ? "down" : "up";
}

setInterval(loadStocks, 60000);
loadStocks();
