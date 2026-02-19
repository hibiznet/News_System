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

// ==========================================
// 배경이미지 자동 회전 함수
// ==========================================

async function loadRotationConfig() {
  try {
    const response = await fetch("/api/backgrounds/rotation/config");
    const config = await response.json();
    
    document.getElementById("rotationEnabled").checked = config.enabled || false;
    document.getElementById("rotationInterval").value = config.interval_minutes || 15;
    
    // 활성화 상태에 따라 설정 표시/숨김
    const settings = document.getElementById("rotationSettings");
    settings.style.display = config.enabled ? "block" : "none";
  } catch (error) {
    console.error("회전 설정 로드 실패:", error);
  }
}

async function saveRotationConfig() {
  try {
    const enabled = document.getElementById("rotationEnabled").checked;
    const interval = parseInt(document.getElementById("rotationInterval").value);
    
    // 범위 검증
    if (interval < 1 || interval > 120) {
      document.getElementById("status").innerText = "❌ 회전 간격은 1~120분 사이여야 합니다.";
      return;
    }
    
    const response = await fetch("/api/backgrounds/rotation/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        enabled: enabled,
        interval_minutes: interval
      })
    });
    
    if (response.ok) {
      document.getElementById("status").innerText = enabled 
        ? `✅ 자동 회전 설정됨 (${interval}분 주기)` 
        : "✅ 자동 회전 해제됨";
    } else {
      document.getElementById("status").innerText = "❌ 설정 저장 실패";
    }
  } catch (error) {
    console.error("회전 설정 저장 실패:", error);
    document.getElementById("status").innerText = "❌ 오류 발생";
  }
}

async function rotateBackgroundNext() {
  try {
    const response = await fetch("/api/backgrounds/rotation/next", {
      method: "POST"
    });
    
    const data = await response.json();
    if (data.ok) {
      document.getElementById("status").innerText = `✅ 배경이미지 변경됨: ${data.current}`;
      loadBackgroundList();
    } else {
      document.getElementById("status").innerText = "❌ 배경 변경 실패";
    }
  } catch (error) {
    console.error("배경 전환 실패:", error);
    document.getElementById("status").innerText = "❌ 오류 발생";
  }
}

// 페이지 로드 시 배경이미지 리스트 표시
document.addEventListener("DOMContentLoaded", () => {
  loadBackgroundList();
  loadRotationConfig();
  
  // 회전 활성화 체크박스 이벤트
  const checkbox = document.getElementById("rotationEnabled");
  checkbox.addEventListener("change", () => {
    const settings = document.getElementById("rotationSettings");
    settings.style.display = checkbox.checked ? "block" : "none";
  });
});

