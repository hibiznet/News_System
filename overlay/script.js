const BREAKING_URL = "breaking.json";
const NEWS_URL = "news.json";

let lastBreaking = "";

async function loadBreaking() {
  try {
    const res = await fetch(BREAKING_URL + "?t=" + Date.now());
    const data = await res.json();
    const text = data.text?.trim();

    if (text) {
      showBreaking(text);
    } else {
      hideBreaking();
    }
  } catch {
    hideBreaking();
  }
}

async function loadNews() {
  try {
    const res = await fetch(NEWS_URL + "?t=" + Date.now());
    const data = await res.json();
    document.getElementById("news-text").innerText =
      data.items.join("  ·  ");
  } catch {
    document.getElementById("news-text").innerText =
      "뉴스 정보를 불러올 수 없습니다.";
  }
}

function showBreaking(text) {
  document.getElementById("breaking-text").innerText = formatCBS(text);
  document.getElementById("breaking-box").style.display = "flex";
  document.getElementById("news-box").style.display = "none";

  if (text !== lastBreaking) {
    const sound = document.getElementById("alert-sound");
    sound.currentTime = 0;
    sound.play().catch(() => {});
  }

  lastBreaking = text;
}

function hideBreaking() {
  document.getElementById("breaking-box").style.display = "none";
  document.getElementById("news-box").style.display = "block";
  lastBreaking = "";
}

function formatCBS(text) {
  const now = new Date();
  const time =
    String(now.getHours()).padStart(2, "0") + ":" +
    String(now.getMinutes()).padStart(2, "0");
  return `[재난문자] ${time} ${text}`;
}

loadBreaking();
loadNews();

setInterval(loadBreaking, 3000);
setInterval(loadNews, 60000);
