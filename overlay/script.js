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
   SOOP 인기방송 TOP5 (방송국 스타일)
================================ */
function escapeHtml(s) {
  return String(s || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderSoopTop(items) {
  const list = document.getElementById("soop-top-list");
  if (!list) return;

  const html = items.slice(0, 5).map((it) => {
    const rank = Number(it.rank || 0);
    const cls = rank === 1 ? "top1" : rank === 2 ? "top2" : rank === 3 ? "top3" : "";

    const title = escapeHtml((it.title || "").trim() || "(제목 없음)");
    const nick = escapeHtml((it.user_nick || "").trim() || "(닉네임)");
    const view = typeof it.view_cnt === "number" ? it.view_cnt : Number(it.view_cnt || 0);

    // 썸네일: API에서 thumb를 주면 사용, 없으면 플레이스홀더
    const thumb = (it.thumb || "").trim();
    const thumbTag = thumb
      ? `<img src="${escapeHtml(thumb)}" loading="lazy" />`
      : "";

    return `
      <div class="soop-item ${cls}">
        <div class="soop-thumb">
          ${thumbTag}
          <div class="soop-rank">${rank}</div>
        </div>
        <div class="soop-body">
          <div class="soop-title">${title}</div>
          <div class="soop-meta">
            <span class="soop-nick">${nick}</span>
            <span class="soop-view">👥 ${view.toLocaleString()}</span>
          </div>
        </div>
      </div>
    `;
  }).join("");

  list.innerHTML = html;
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
    box.style.display = "none";
  }
}


/* ===============================
   방송 상태 배지 (Live / Recorded)
================================ */
async function loadBroadcastStatus() {
  try {
    const res = await fetch("/overlay/live.json?t=" + Date.now(), { cache: "no-store" });
    const data = await res.json();

    const badge = document.getElementById("broadcast-badge");
    const textEl = document.getElementById("broadcast-text");

    if (!badge || !textEl) return;

    // enabled=false 또는 mode=off면 숨김
    const enabled = data?.enabled !== false;
    const mode = (data?.mode || "live").toLowerCase(); // live | recorded | off
    const text = (data?.text || "").trim();

    if (!enabled || mode === "off") {
      badge.style.display = "none";
      return;
    }

    badge.style.display = "";
    badge.classList.toggle("recorded", mode === "recorded");
    textEl.textContent = text || (mode === "recorded" ? "녹화방송중" : "생방송중 Live!");

  } catch (e) {
    // 실패하면 그냥 숨김(방송 안정)
    const badge = document.getElementById("broadcast-badge");
    if (badge) badge.style.display = "none";
  }
}

/* ===============================
   현재 날짜 / 시간 표시
================================ */
function updateDateTime() {
  const now = new Date();

  const days = ["일요일","월요일","화요일","수요일","목요일","금요일","토요일"];
  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  const date = now.getDate();
  const dayName = days[now.getDay()];

  let hours = now.getHours();
  const minutes = String(now.getMinutes()).padStart(2, "0");

  const ampm = hours >= 12 ? "오후" : "오전";
  hours = hours % 12;
  if (hours === 0) hours = 12;

  const dateEl = document.getElementById("current-date");
  const timeEl = document.getElementById("current-time");

  if (!dateEl || !timeEl) return;

  dateEl.textContent = `${year}년 ${month}월 ${date}일 ${dayName}`;
  timeEl.textContent = `${ampm} ${hours}:${minutes}`;
}

setInterval(updateDateTime, 1000);
updateDateTime();

setInterval(loadBroadcastStatus, 2000);
loadBroadcastStatus();

setInterval(loadSoopTop, 5000);
loadSoopTop();

loadBreaking();
loadNews();

setInterval(loadBreaking, 3000);
setInterval(loadNews, 60000);
