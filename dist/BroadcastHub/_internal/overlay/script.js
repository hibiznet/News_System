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
function floatingPanel() {
  const panel = document.getElementById("floating-menu");
  if (!panel) {
    console.warn("[floatingPanel] #floating-menu not found");
    return;
  }

  const handle = panel.querySelector(".floating-handle");
  const actions = panel.querySelector(".floating-actions");
  const lockBtn = document.getElementById("floating-lock");
  const closeBtn = document.getElementById("floating-close");

  const KEY_POS = "overlay.floatingMenu.pos";
  const KEY_LOCK = "overlay.floatingMenu.lock";
  const KEY_HIDE = "overlay.floatingMenu.hide";

  // ✅ 버튼 클릭이 절대 막히지 않게
  if (actions) actions.style.pointerEvents = "auto";
  if (lockBtn) lockBtn.style.pointerEvents = "auto";
  if (closeBtn) closeBtn.style.pointerEvents = "auto";

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
    panel.classList.toggle("is-locked", locked);
  }
  renderLock();

  // ✅ 드래그/클릭 충돌 방지: 버튼은 pointerdown에서 stop
  if (lockBtn) {
    lockBtn.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      e.stopPropagation();
    }, true);

    lockBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      locked = !locked;
      localStorage.setItem(KEY_LOCK, locked ? "1" : "0");
      renderLock();
      console.log("[floatingPanel] lock =", locked);
    });
  }

  if (closeBtn) {
    // ✅ click이 안 올라오는 케이스 대비: pointerdown에서 즉시 닫기
    closeBtn.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      e.stopPropagation();
      panel.style.display = "none";
      localStorage.setItem(KEY_HIDE, "1");
      console.log("[floatingPanel] close (pointerdown)");
    }, true);

    closeBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      panel.style.display = "none";
      localStorage.setItem(KEY_HIDE, "1");
      console.log("[floatingPanel] close (click)");
    });
  }

  // 드래그
  if (!handle) return;

  let startX = 0, startY = 0, startLeft = 0, startTop = 0, dragging = false;
  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

  function onDown(e) {
    // ✅ 버튼 영역은 드래그 시작 금지
    if (e.target.closest && e.target.closest(".floating-actions")) return;
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

  console.log("[floatingPanel] init OK");
}

// ✅ 무조건 실행(다른 코드 에러와 분리하고 싶으면 try/catch 권장)
try { floatingPanel(); } catch (e) { console.error("[floatingPanel] failed", e); }

function setupDraggablePanel(panelId){
  const panel = document.getElementById(panelId);
  if (!panel) return;

  const handle = panel.querySelector(".floating-handle");
  const lockBtn = panel.querySelector('[data-action="lock"]');
  const closeBtn = panel.querySelector('[data-action="close"]');

  const KEY_POS  = `overlay.panel.${panelId}.pos`;
  const KEY_LOCK = `overlay.panel.${panelId}.lock`;
  const KEY_HIDE = `overlay.panel.${panelId}.hide`;

  // 숨김 복원
  if (localStorage.getItem(KEY_HIDE) === "1") panel.style.display = "none";

  // 위치 복원
  try{
    const saved = localStorage.getItem(KEY_POS);
    if (saved){
      const {left, top} = JSON.parse(saved);
      if (typeof left === "number" && typeof top === "number"){
        panel.style.left = left + "px";
        panel.style.top  = top + "px";
        panel.style.right = "auto";
        panel.style.bottom = "auto";
      }
    }
  }catch{}

  let locked = localStorage.getItem(KEY_LOCK) === "1";
  const render = () => { if (lockBtn) lockBtn.textContent = locked ? "🔒" : "🔓"; };
  render();

  if (lockBtn){
    lockBtn.addEventListener("pointerdown", e=>{e.preventDefault(); e.stopPropagation();}, true);
    lockBtn.addEventListener("click", e=>{
      e.preventDefault(); e.stopPropagation();
      locked = !locked;
      localStorage.setItem(KEY_LOCK, locked ? "1":"0");
      render();
    });
  }

  if (closeBtn){
    closeBtn.addEventListener("pointerdown", e=>{
      e.preventDefault(); e.stopPropagation();
      panel.style.display = "none";
      localStorage.setItem(KEY_HIDE, "1");
      
      // panels.json도 업데이트
      const panelKey = panelId.replace("panel-", "");
      fetch("/api/panels", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          panels: {
            [panelKey]: {enabled: false}
          }
        })
      }).catch(err => console.log("[savePanel] error", err));
    }, true);
  }

  if (!handle) return;
  let startX=0,startY=0,startLeft=0,startTop=0,dragging=false;
  const clamp = (v,min,max)=>Math.max(min,Math.min(max,v));

  function onDown(e){
    if (e.target.closest && e.target.closest(".floating-actions")) return;
    if (locked) return;
    dragging = true;
    const rect = panel.getBoundingClientRect();
    startX = e.clientX; startY = e.clientY;
    startLeft = rect.left; startTop = rect.top;

    panel.style.left = rect.left + "px";
    panel.style.top  = rect.top + "px";
    panel.style.right = "auto";
    panel.style.bottom = "auto";

    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
    handle.setPointerCapture?.(e.pointerId);
  }

  function onMove(e){
    if (!dragging) return;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;

    const w = panel.offsetWidth;
    const h = panel.offsetHeight;

    const maxLeft = window.innerWidth - w - 8;
    const maxTop  = window.innerHeight - h - 8;

    panel.style.left = clamp(startLeft + dx, 8, maxLeft) + "px";
    panel.style.top  = clamp(startTop + dy, 8, maxTop) + "px";
  }

  function onUp(){
    if (!dragging) return;
    dragging = false;

    const rect = panel.getBoundingClientRect();
    try{ localStorage.setItem(KEY_POS, JSON.stringify({left: rect.left, top: rect.top})); }catch{}

    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerup", onUp);
  }

  handle.addEventListener("pointerdown", onDown);
}

// ✅ 등록만 하면 패널 수 늘려도 OK
document.addEventListener("DOMContentLoaded", () => {
  setupDraggablePanel("panel-jobsjp");
  setupDraggablePanel("panel-jpwx");
  setupDraggablePanel("panel-icn");
});


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
let jobsjpUi = { count: 6, roll: true, interval: 30 };
let jobsjpTimer = null;

function jpBadge(jpRequired){
  if (jpRequired === "required") return `<span class="badge no">일본어 필수</span>`;
  if (jpRequired === "preferred") return `<span class="badge warn">일본어 우대</span>`;
  if (jpRequired === "not_required") return `<span class="badge ok">일본어 불필요</span>`;
  return ``;
}

function renderJobsJP(data) {
  const box = document.getElementById("jobsjp-box");
  const list = document.getElementById("jobsjp-list");
  const meta = document.getElementById("jobsjp-meta");
  const sourceEl = document.getElementById("jobsjp-source");

  const items = data.items || [];
  if (!items.length) { box.style.display = "none"; return; }
  box.style.display = "";

  // ✅ 사이트명 크게
  sourceEl.textContent = data.sourceName || "JP 일본 취업 구인";
  meta.textContent = `업데이트 ${data.updated || ""}`;

  const pageItems = items.slice(0, (data.ui?.count || 6));

  list.innerHTML = pageItems.map(it => {
    const title = escapeHtml(it.title || "");
    const company = escapeHtml(it.company || "회사명 정보없음");
    const salary = escapeHtml(it.salary || "");
    const location = escapeHtml(it.location || "");
    const tags = Array.isArray(it.tags) ? it.tags.slice(0,6) : [];

    return `
      <div class="job-card">
        <div class="job-title">${title}</div>
        <div class="job-row">
          <span class="job-company">${company}</span>
          ${location ? `<span class="badge">${location}</span>` : ``}
          ${salary ? `<span class="badge">${salary}</span>` : ``}
          ${jpBadge(it.jpRequired)}
        </div>
        ${tags.length ? `<div class="tags">${tags.map(t=>`<span class="tag">${escapeHtml(t)}</span>`).join("")}</div>` : ``}
      </div>
    `;
  }).join("");
}

function escapeHtml(s){
  return String(s ?? "")
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}

function restartJobsJPTimer() {
  if (jobsjpTimer) clearInterval(jobsjpTimer);
  if (!jobsjpUi.roll) return;
  const intervalMs = (jobsjpUi.interval || 30) * 1000;
  jobsjpTimer = setInterval(() => { jobsjpPage++; }, intervalMs);
}

async function loadJobsJP() {
  try {
    // panels.json에서 jobsjp의 enabled 확인
    const panelsRes = await fetch("/api/panels?t=" + Date.now(), {cache:"no-store"});
    const panelsData = panelsRes.ok ? await panelsRes.json() : {};
    const panelJobsJpEnabled = panelsData.data?.panels?.jobsjp?.enabled !== false;
    
    const box = document.getElementById("jobsjp-box");
    if (!panelJobsJpEnabled) {
      if (box) box.style.display = "none";
      return;
    }
    
    const res = await fetch("/overlay/jobs_jp.json?t=" + Date.now(), { cache:"no-store" });
    const data = await res.json();

    if (data.ui) {
      jobsjpUi = {
        count: Number(data.ui.count || 6),
        roll: !!data.ui.roll,
        interval: Number(data.ui.interval || 30)
      };
      jobsjpUi.count = Math.max(1, Math.min(10, jobsjpUi.count));
      jobsjpUi.interval = Math.max(5, Math.min(300, jobsjpUi.interval));
    }

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

async function loadJPWX() {
  try {
    // panels.json에서 jpwx의 enabled 확인
    const panelsRes = await fetch("/api/panels?t=" + Date.now(), {cache:"no-store"});
    const panelsData = panelsRes.ok ? await panelsRes.json() : {};
    const panelJpwxEnabled = panelsData.data?.panels?.jpwx?.enabled !== false;
    
    const box = document.getElementById("jpwx-box");
    if (!panelJpwxEnabled) {
      if (box) box.style.display = "none";
      return;
    }
    
    const res = await fetch("/overlay/jp_weather.json?t=" + Date.now(), {cache:"no-store"});
    const data = await res.json();

    const list = document.getElementById("jpwx-list");
    const meta = document.getElementById("jpwx-meta");
    const source = document.getElementById("jpwx-source");

    const items = data.items || [];
    if (!items.length) { box.style.display="none"; return; }
    box.style.display="";

    source.textContent = data.sourceName || "JP Weather";
    meta.textContent = `업데이트 ${data.updated || ""}`;

    list.innerHTML = items.map(it => {
      if (it.error) {
        return `<div class="job-card"><div class="job-title">${it.city} 날씨 오류</div><div class="job-row"><span class="badge warn">${it.error}</span></div></div>`;
      }
      const now = it.now || {};
      const t = it.today || {};
      const tm = it.tomorrow || {};
      return `
        <div class="job-card">
          <div class="job-title">${it.city}</div>
          <div class="job-row">
            <span class="badge">${now.icon || "🌡️"} 현재 ${now.temp ?? "--"}°</span>
            <span class="badge">${t.icon || "☀️"} 오늘 ${t.min ?? "--"}° / ${t.max ?? "--"}°</span>
            <span class="badge">${tm.icon || "🌤️"} 내일 ${tm.min ?? "--"}° / ${tm.max ?? "--"}°</span>
          </div>
        </div>
      `;
    }).join("");

  } catch(e) {
    const box = document.getElementById("jpwx-box");
    if (box) box.style.display="none";
  }
}
setInterval(loadJPWX, 30000);
loadJPWX();

async function loadICN() {
  try {
    // panels.json에서 icn의 enabled 확인
    const panelsRes = await fetch("/api/panels?t=" + Date.now(), {cache:"no-store"});
    const panelsData = panelsRes.ok ? await panelsRes.json() : {};
    const panelICNEnabled = panelsData.data?.panels?.icn?.enabled !== false;
    
    const box = document.getElementById("icn-box");
    if (!panelICNEnabled) {
      if (box) box.style.display = "none";
      return;
    }
    
    const res = await fetch("/overlay/icn_terminal_view.json?t=" + Date.now(), {cache:"no-store"});
    const data = await res.json();

    const list = document.getElementById("icn-list");
    const meta = document.getElementById("icn-meta");
    const source = document.getElementById("icn-source");

    const items = data.items || [];
    if (!items.length) { box.style.display="none"; return; }
    box.style.display="";

    source.textContent = data.sourceName || "ICN Terminal";
    meta.textContent = `업데이트 ${data.updated || ""} · 검색 "${data.ui?.query || ""}"`;

    list.innerHTML = items.map(it => {
      const term = (it.terminal || "").toUpperCase();
      const cls = term === "T2" ? "t2" : "t1";
      return `
        <div class="job-card">
          <div class="job-title">${it.airline} <span style="opacity:.7;font-weight:700">(${it.iata || ""}/${it.icao || ""})</span></div>
          <div class="job-row">
            <span class="badge ${cls}">${term || "T?"}</span>
            <span class="badge">탑승 터미널</span>
          </div>
        </div>
      `;
    }).join("");

  } catch(e) {
    const box = document.getElementById("icn-box");
    if (box) box.style.display="none";
  }
}
setInterval(loadICN, 5000);
loadICN();

// 파넬 설정 불러와서 적용 (관리자 페이지에서 저장하면 즉시 반영됨)
let lastResetToken = 0;

async function loadPanelSettings() {
  try {
    const res = await fetch("/overlay/panels.json?t=" + Date.now(), { cache: "no-store" });
    const cfg = await res.json();

    // ✅ resetToken 바뀌면 숨김 키 제거 후 다시 표시
    const token = Number(cfg.resetToken || 0);
    if (token && token !== lastResetToken) {
      lastResetToken = token;

    // 숨김 제거
    localStorage.removeItem("overlay.panel.panel-icn.hide");
    localStorage.removeItem("overlay.panel.panel-jpwx.hide");
    localStorage.removeItem("overlay.panel.panel-jobsjp.hide");

    // ✅ 위치 초기화(기본배치로 돌아가게)
    localStorage.removeItem("overlay.panel.panel-icn.pos");
    localStorage.removeItem("overlay.panel.panel-jpwx.pos");
    localStorage.removeItem("overlay.panel.panel-jobsjp.pos");

    // 표시
    ["panel-icn","panel-jpwx","panel-jobsjp"].forEach(id=>{
      const el = document.getElementById(id);
      if (el) el.style.display = "";
    });
    }

    applyPanel("panel-jobsjp", cfg.panels?.jobsjp);
    applyPanel("panel-jpwx",   cfg.panels?.jpwx);
    applyPanel("panel-icn",    cfg.panels?.icn);
  } catch (e) {}
}

function applyPanel(panelId, p) {
  const el = document.getElementById(panelId);
  if (!el || !p) return;

  // ON/OFF
  el.style.display = p.enabled ? "" : "none";

  // 스타일 적용
  if (p.width) el.style.width = p.width + "px";
  if (p.opacity != null) el.style.background = `rgba(0,0,0,${p.opacity})`;
  if (p.fontSize) el.style.fontSize = p.fontSize + "px";

  // 내부 글자도 같이(조금 더 확실)
  el.querySelectorAll(".job-title,.jobs-source,.jobs-sub,.badge,.tag,.floating-title")
    .forEach(n => { n.style.fontSize = ""; }); // 기본은 패널 font-size 상속
}

// 5초마다 설정 반영 (관리자에서 저장하면 즉시 반영됨)
setInterval(loadPanelSettings, 5000);
loadPanelSettings();


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

document.addEventListener("DOMContentLoaded", floatingPanel);
