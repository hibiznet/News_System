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

/* ===============================
   Floating Panel (draggable)
================================ */
(function floatingPanel() {
  const panel = document.getElementById("floating-menu");
  if (!panel) return;

  const handle = panel.querySelector(".floating-handle");
  const lockBtn = document.getElementById("floating-lock");
  const closeBtn = document.getElementById("floating-close");

  const KEY_POS = "overlay.floatingMenu.pos";
  const KEY_LOCK = "overlay.floatingMenu.lock";
  const KEY_HIDE = "overlay.floatingMenu.hide";

  // 숨김 상태 복원
  const hidden = localStorage.getItem(KEY_HIDE) === "1";
  if (hidden) panel.style.display = "none";

  // 위치 복원
  try {
    const saved = localStorage.getItem(KEY_POS);
    if (saved) {
      const { left, top } = JSON.parse(saved);
      if (typeof left === "number" && typeof top === "number") {
        panel.style.left = left + "px";
        panel.style.top = top + "px";
        panel.style.right = "auto";
        panel.style.bottom = "auto";
      }
    }
  } catch {}

  // 잠금 상태
  let locked = localStorage.getItem(KEY_LOCK) === "1";
  function renderLock() {
    if (lockBtn) lockBtn.textContent = locked ? "🔒" : "🔓";
    if (handle) handle.style.pointerEvents = locked ? "none" : "auto";
  }
  renderLock();

  if (lockBtn) {
    lockBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      locked = !locked;
      localStorage.setItem(KEY_LOCK, locked ? "1" : "0");
      renderLock();
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      panel.style.display = "none";
      localStorage.setItem(KEY_HIDE, "1");
    });
  }

  // 드래그
  if (!handle) return;

  let startX = 0, startY = 0, startLeft = 0, startTop = 0, dragging = false;

  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

  function onDown(e) {
    if (locked) return;
    dragging = true;

    const rect = panel.getBoundingClientRect();
    startX = e.clientX;
    startY = e.clientY;
    startLeft = rect.left;
    startTop = rect.top;

    panel.style.left = rect.left + "px";
    panel.style.top = rect.top + "px";
    panel.style.right = "auto";
    panel.style.bottom = "auto";

    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
    handle.setPointerCapture?.(e.pointerId);
  }

  function onMove(e) {
    if (!dragging) return;

    const dx = e.clientX - startX;
    const dy = e.clientY - startY;

    const w = panel.offsetWidth;
    const h = panel.offsetHeight;

    const maxLeft = window.innerWidth - w - 8;
    const maxTop = window.innerHeight - h - 8;

    const left = clamp(startLeft + dx, 8, maxLeft);
    const top = clamp(startTop + dy, 8, maxTop);

    panel.style.left = left + "px";
    panel.style.top = top + "px";
  }

  function onUp() {
    if (!dragging) return;
    dragging = false;

    const rect = panel.getBoundingClientRect();
    try {
      localStorage.setItem(KEY_POS, JSON.stringify({ left: rect.left, top: rect.top }));
    } catch {}

    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerup", onUp);
  }

  handle.addEventListener("pointerdown", onDown);
})();


/* ===============================
   신입 스트리머 TOP10
================================ */
function renderRookie(items) {
  const list = document.getElementById("rookie-list");
  if (!list) return;

  const html = items.slice(0, 10).map(it => {
    const move = (it.move || "same").toLowerCase();
    const delta = it.delta;

    const badge =
      move === "up" ? `▲${delta ?? ""}` :
      move === "down" ? `▼${delta ?? ""}` :
      move === "new" ? `NEW` : `-`;

    const cls =
      move === "up" ? "rookie-up" :
      move === "down" ? "rookie-down" :
      move === "new" ? "rookie-new" : "rookie-same";

    const live = it.is_live ? `<span class="rookie-live">LIVE</span>` : "";

    // 닉네임
    const name = String(it.name || "").replaceAll("<","&lt;").replaceAll(">","&gt;");

    return `
      <div class="rookie-item">
        <div class="rookie-left">${it.rank}. ${name} ${live}</div>
        <div class="rookie-right ${cls}">${badge}</div>
      </div>
    `;
  }).join("");

  list.innerHTML = html;
}


async function loadRookie() {
  const box = document.getElementById("rookie-box");
  if (!box) return;

  try {
    const res = await fetch("/overlay/rookie.json?t=" + Date.now(), { cache: "no-store" });
    const data = await res.json();

    if (!data.items || data.items.length === 0 || data.disabled) {
      box.style.display = "none";
      return;
    }

    box.style.display = "";
    renderRookie(data.items);
  } catch (e) {
    box.style.display = "none";
  }
}

/* ===============================
   Floating Menu show/hide from ui.json
================================ */
async function syncFloatingVisibility() {
  const panel = document.getElementById("floating-menu");
  if (!panel) return;

  try {
    const res = await fetch("/overlay/ui.json?t=" + Date.now(), { cache: "no-store" });
    const ui = await res.json();
    const hidden = !!ui?.floatingMenu?.hidden;

    panel.style.display = hidden ? "none" : "";
  } catch (e) {
    // 실패 시 현상 유지
  }
}
setInterval(syncFloatingVisibility, 2000);
syncFloatingVisibility();
/*
async function loadJobsJP(){
  const list = document.getElementById("jobsjp-list");
  const box = document.getElementById("jobsjp-box");
  if (!list || !box) return;

  try{
    const res = await fetch("/overlay/jobs_jp.json?t=" + Date.now(), {cache:"no-store"});
    const data = await res.json();
    const items = data.items || [];
    if (!items.length) { box.style.display="none"; return; }
    box.style.display="";

    list.innerHTML = items.slice(0,6).map(it => `
      <div class="floating-item">
        <div style="font-weight:900; font-size:13px">${it.title}</div>
        <div style="opacity:.75; font-size:11px">${it.pubDate || ""}</div>
      </div>
    `).join("");
  }catch(e){
    box.style.display="none";
  }
}
setInterval(loadJobsJP, 10000);
loadJobsJP();
*/
let jobsjpPage = 0;
let jobsjpLastPreset = "";
let jobsjpUi = { count: 6, roll: true, interval: 10 };
let jobsjpTimer = null;

function renderJobsJP(data) {
  const box = document.getElementById("jobsjp-box");
  const list = document.getElementById("jobsjp-list");
  const meta = document.getElementById("jobsjp-meta");
  if (!box || !list) return;

  const items = data.items || [];
  if (!items.length || data.disabled) { box.style.display = "none"; return; }
  box.style.display = "";

  if (meta) meta.textContent = `${data.presetName || ""} · 업데이트 ${data.updated || ""}`;

  const count = jobsjpUi.count || 6;
  const roll = !!jobsjpUi.roll;

  const pageSize = count;
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  if (!roll) jobsjpPage = 0;
  if (jobsjpPage >= totalPages) jobsjpPage = 0;

  const start = jobsjpPage * pageSize;
  const pageItems = items.slice(start, start + pageSize);

  list.innerHTML = pageItems.map(it => `
    <div class="floating-item" style="cursor:default;">
      <div style="font-weight:900; font-size:13px; line-height:1.25">${String(it.title || "")}</div>
      <div style="opacity:.75; font-size:11px; margin-top:4px">${String(it.pubDate || "")}</div>
    </div>
  `).join("");
}

function restartJobsJPTimer() {
  if (jobsjpTimer) clearInterval(jobsjpTimer);
  if (!jobsjpUi.roll) return;
  const intervalMs = (jobsjpUi.interval || 10) * 1000;
  jobsjpTimer = setInterval(() => {
    jobsjpPage++;
  }, intervalMs);
}

async function loadJobsJP() {
  try {
    const res = await fetch("/overlay/jobs_jp.json?t=" + Date.now(), { cache:"no-store" });
    const data = await res.json();

    // ui 옵션 반영
    if (data.ui) {
      jobsjpUi = {
        count: Number(data.ui.count || 6),
        roll: !!data.ui.roll,
        interval: Number(data.ui.interval || 10)
      };
      jobsjpUi.count = Math.max(1, Math.min(10, jobsjpUi.count));
      jobsjpUi.interval = Math.max(3, Math.min(60, jobsjpUi.interval));
    }

    // 프리셋 바뀌면 페이지 리셋
    if ((data.preset || "") !== jobsjpLastPreset) {
      jobsjpLastPreset = data.preset || "";
      jobsjpPage = 0;
      restartJobsJPTimer();
    }

    renderJobsJP(data);
  } catch (e) {
    const box = document.getElementById("jobsjp-box");
    if (box) box.style.display = "none";
  }
}

// 5초마다 JSON 갱신 확인
setInterval(loadJobsJP, 5000);
loadJobsJP();
restartJobsJPTimer();



setInterval(loadRookie, 5000);
loadRookie();

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
