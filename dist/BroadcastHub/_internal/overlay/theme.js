(() => {
  const URL = "/overlay/banner.json";
  const POLL_MS = 2000;

  // DOM (있으면 쓰고, 없으면 조용히 무시)
  const rightBox = document.getElementById("banner-box");
  const rightText = document.getElementById("banner-text");

  const bottomBar = document.getElementById("banner-bar");
  const bottomText = document.getElementById("banner-bar-text");

  let lastSignature = "";
  let rotateTimer = null;
  let rotateIdx = 0;

  function safeShow(el, show) {
    if (!el) return;
    el.style.display = show ? "" : "none";
  }

  function pickPayloadText(payload) {
    const mode = payload?.mode || "single";

    if (mode === "rotate") {
      const arr = Array.isArray(payload.items) ? payload.items.filter(Boolean) : [];
      if (arr.length === 0) return "";
      const text = arr[rotateIdx % arr.length];
      rotateIdx = (rotateIdx + 1) % arr.length;
      return String(text || "").trim();
    }

    return String(payload?.text || "").trim();
  }

  function applyTargets(payload, text) {
    const enabled = payload?.enabled !== false;
    const targets = payload?.targets || { right: true, bottom: false };

    const showRight = enabled && targets.right === true && !!text;
    const showBottom = enabled && targets.bottom === true && !!text;

    if (rightText) rightText.textContent = text;
    if (bottomText) bottomText.textContent = text;

    safeShow(rightBox, showRight);
    safeShow(bottomBar, showBottom);
  }

  function clearRotateTimer() {
    if (rotateTimer) {
      clearInterval(rotateTimer);
      rotateTimer = null;
    }
  }

  function startRotateTimer(payload) {
    clearRotateTimer();

    const sec = Number(payload?.rotateSec || 8);
    const rotateMs = Math.max(2000, sec * 1000); // 최소 2초
    rotateTimer = setInterval(() => {
      const text = pickPayloadText(payload);
      applyTargets(payload, text);
    }, rotateMs);
  }

  async function loadOnce() {
    try {
      const res = await fetch(URL + "?t=" + Date.now(), { cache: "no-store" });
      if (!res.ok) return;

      const payload = await res.json();

      // 변경 감지(rotate가 아닌 경우에도 text 변경 즉시 반영)
      const signature = JSON.stringify({
        enabled: payload?.enabled,
        targets: payload?.targets,
        mode: payload?.mode,
        text: payload?.text,
        items: payload?.items,
        rotateSec: payload?.rotateSec
      });

      const isChanged = signature !== lastSignature;
      if (isChanged) {
        lastSignature = signature;
        rotateIdx = 0; // 새 배너 적용 시 순환 인덱스 리셋
      }

      const mode = payload?.mode || "single";

      if (mode === "rotate") {
        // rotate 모드: 즉시 1회 표시 후 타이머
        const text = pickPayloadText(payload);
        applyTargets(payload, text);
        if (isChanged) startRotateTimer(payload);
      } else {
        // single 모드: 타이머 불필요
        clearRotateTimer();
        const text = pickPayloadText(payload);
        applyTargets(payload, text);
      }
    } catch (e) {
      // 실패해도 방송 안정: 숨기거나 유지 중 선택 가능
      // 여기서는 "유지"를 위해 아무 것도 하지 않음
      // 필요하면 아래 2줄로 "숨김" 정책 가능:
      // safeShow(rightBox, false);
      // safeShow(bottomBar, false);
    }
  }

  // 시작
  loadOnce();
  setInterval(loadOnce, POLL_MS);
})();
