async function loadStocks() {
  try {
    const res = await fetch("/overlay/stock.json?t=" + Date.now());
    const data = await res.json();

    // data.domestic.KOSPI = { price: 4909.93, change: 0.49 } 형태
    setStock("KOSPI",  data?.domestic?.KOSPI);
    setStock("KOSDAQ", data?.domestic?.KOSDAQ);
    setStock("DOW",    data?.global?.DOW);
    setStock("NASDAQ", data?.global?.NASDAQ);

  } catch (e) {
    console.error("stocks load fail", e);
    // 실패 시 표시
    ["KOSPI","KOSDAQ","DOW","NASDAQ"].forEach(id => setStock(id, null));
  }
}

function setStock(id, obj) {
  const el = document.getElementById(id);
  if (!el) return;

  // obj가 없거나, price가 None/null인 경우
  if (!obj || obj.price == null || obj.change == null) {
    el.textContent = "-";
    el.className = "";
    return;
  }

  const price = Number(obj.price);
  const change = Number(obj.change); // % 값 (예: 0.49)

  const arrow = change > 0 ? "▲" : change < 0 ? "▼" : "■";
  const sign  = change > 0 ? "+" : change < 0 ? "" : "";
  const changeText = `${arrow}${sign}${Math.abs(change).toFixed(2)}%`;

  // 표시는 "가격  ▲+0.49%" 형태로
  el.textContent = `${price.toFixed(2)}  ${changeText}`;

  // 색상 클래스
  el.className = change > 0 ? "up" : change < 0 ? "down" : "";
}

setInterval(loadStocks, 60000);
loadStocks();
