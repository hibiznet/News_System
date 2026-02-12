function payload() {
  return {
    mode: Number(document.getElementById("mode").value),
    items: [
      { src: document.getElementById("src1").value.trim() },
      { src: document.getElementById("src2").value.trim() },
      { src: document.getElementById("src3").value.trim() },
      { src: document.getElementById("src4").value.trim() }
    ]
  };
}

async function save() {
  await fetch("/api/layout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload())
  });
  document.getElementById("status").innerText = "✅ 저장됨";
}

async function clearAll() {
  await fetch("/api/layout/clear", { method: "POST" });
  document.getElementById("status").innerText = "♻️ 초기화됨";
}
