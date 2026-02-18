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

// ==========================================
// 배경이미지 관련 함수
// ==========================================

let currentBackground = null;

async function loadBackgroundList() {
  try {
    const response = await fetch("/api/backgrounds/list");
    const data = await response.json();
    const files = data.files || [];
    
    const listDiv = document.getElementById("backgroundList");
    listDiv.innerHTML = "";
    
    if (files.length === 0) {
      listDiv.innerHTML = '<p class="empty">📁 backgrounds 폴더에 이미지를 넣으세요</p>';
      return;
    }
    
    files.forEach(filename => {
      const item = document.createElement("div");
      item.className = "background-item";
      item.innerHTML = `
        <img src="/api/backgrounds/thumbnail/${encodeURIComponent(filename)}" alt="${filename}">
        <div class="background-item-name">${filename}</div>
      `;
      
      item.addEventListener("click", () => selectBackground(filename, item));
      listDiv.appendChild(item);
    });
  } catch (error) {
    console.error("배경이미지 로드 실패:", error);
    document.getElementById("backgroundList").innerHTML = '<p class="empty">⚠️ 배경이미지 로드 실패</p>';
  }
}

async function selectBackground(filename, element) {
  try {
    // 이전 선택 제거
    document.querySelectorAll(".background-item").forEach(el => {
      el.classList.remove("selected");
    });
    
    // 현재 선택 표시
    element.classList.add("selected");
    currentBackground = filename;
    
    // 서버에 저장
    const response = await fetch("/api/backgrounds/set", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: filename })
    });
    
    if (response.ok) {
      document.getElementById("status").innerText = `✅ 배경이미지 변경됨: ${filename}`;
    } else {
      document.getElementById("status").innerText = "❌ 배경이미지 저장 실패";
    }
  } catch (error) {
    console.error("배경이미지 선택 실패:", error);
    document.getElementById("status").innerText = "❌ 오류 발생";
  }
}

// 페이지 로드 시 배경이미지 리스트 표시
document.addEventListener("DOMContentLoaded", () => {
  loadBackgroundList();
});

