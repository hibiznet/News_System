async function sendBanner() {
  const text = document.getElementById("bannerText").value.trim();
  const expire = Number(document.getElementById("expire").value);

  if (!text) {
    alert("배너 문구를 입력하세요");
    return;
  }

  await fetch("/api/banner", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, expire })
  });

  document.getElementById("status").innerText = "📢 배너 송출 중";
}

async function clearBanner() {
  await fetch("/api/banner/clear", { method: "POST" });
  document.getElementById("status").innerText = "❌ 배너 해제됨";
}
