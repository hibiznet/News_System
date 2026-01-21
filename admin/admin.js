async function sendBreaking() {
  const text = document.getElementById("message").value.trim();
  const expire = Number(document.getElementById("expire").value);

  if (!text) return alert("문구를 입력하세요");

  await fetch("/api/breaking", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, expire })
  });

  document.getElementById("status").innerText = "🚨 송출 중";
}

async function clearBreaking() {
  await fetch("/api/clear", { method: "POST" });
  document.getElementById("status").innerText = "송출 해제됨";
}
