function buildThemePayload() {
  return {
    "--app-bg": document.getElementById("appBg").value.trim(),

    "--panel-bg": document.getElementById("panelBg").value.trim(),
    "--panel-text": document.getElementById("panelText").value,

    "--weather-bg": document.getElementById("weatherBg").value.trim(),
    "--stock-bg": document.getElementById("stockBg").value.trim(),
    "--banner-bg": document.getElementById("bannerBg").value.trim(),

    "--lower-bg": document.getElementById("lowerBg").value,
    "--breaking-bg": document.getElementById("breakingBg").value,
    "--lower-text": document.getElementById("lowerText").value,

    "--up-color": document.getElementById("upColor").value,
    "--down-color": document.getElementById("downColor").value
  };
}

async function saveTheme() {
  const payload = buildThemePayload();

  await fetch("/api/theme", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  document.getElementById("status").innerText = "✅ 저장됨 (오버레이 자동 반영)";
}

async function resetTheme() {
  await fetch("/api/theme/clear", { method: "POST" });
  document.getElementById("status").innerText = "♻️ 초기화됨 (기본 테마로 복귀)";
}
