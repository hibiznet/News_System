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

/* ===============================
   SOOP 인기방송 TOP5
================================ */

function renderSoopTop(items) {
  const list = document.getElementById("soop-top-list");
  if (!list) return;

  list.innerHTML = "";
  items.slice(0, 5).forEach((it) => {
    const li = document.createElement("li");

    const title = (it.title || "").trim() || "(제목 없음)";
    const nick = (it.user_nick || "").trim();
    const view = typeof it.view_cnt === "number" ? it.view_cnt.toLocaleString() : "-";

    li.textContent = `${it.rank}. ${nick} - ${title}`;

    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = `(${view})`;
    li.appendChild(meta);

    list.appendChild(li);
  });
}

async function loadSoopTop() {
  const box = document.getElementById("soop-top-box");
  if (!box) return;

  try {
    const res = await fetch("/overlay/soop_top.json?t=" + Date.now(), { cache: "no-store" });
    const data = await res.json();

    // client_id 없거나 비활성/비어있으면 숨김
    if (!data.items || data.items.length === 0 || data.disabled) {
      box.style.display = "none";
      return;
    }

    box.style.display = "";
    renderSoopTop(data.items);

  } catch (e) {
    // 방송 안정: 실패 시 숨김
    box.style.display = "none";
  }
}

// 5초 주기 갱신
setInterval(loadSoopTop, 5000);
loadSoopTop();


loadBreaking();
loadNews();

setInterval(loadBreaking, 3000);
setInterval(loadNews, 60000);
