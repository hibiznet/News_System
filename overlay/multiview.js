(() => {
  const URL = "/overlay/layout.json";
  const POLL_MS = 2000;

  const container = document.getElementById("multiview");
  if (!container) return;

  let lastSig = "";

  function sanitizeUrl(url) {
    // 최소한의 안전장치: 빈값/공백 제거
    url = String(url || "").trim();
    if (!url) return "";
    return url;
  }

  function render(layout) {
    const mode = Number(layout?.mode || 1); // 1,2,4
    const items = Array.isArray(layout?.items) ? layout.items : [];

    const cls = mode === 2 ? "layout-2" : mode === 4 ? "layout-4" : "layout-1";
    container.className = cls;

    // 필요한 슬롯 수
    const count = mode === 2 ? 2 : mode === 4 ? 4 : 1;

    const html = [];
    for (let i = 0; i < count; i++) {
      const src = sanitizeUrl(items[i]?.src);
      if (!src) {
        // 빈 슬롯: 빈 박스로 둠 (원하면 display:none 처리 가능)
        html.push(`<div class="mv-slot"></div>`);
        continue;
      }

      html.push(`
        <div class="mv-slot">
          <iframe
            src="${src.replaceAll('"', "&quot;")}"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            referrerpolicy="strict-origin-when-cross-origin"
            allowfullscreen
          ></iframe>
        </div>
      `);
    }

    container.innerHTML = html.join("");
  }

  async function load() {
    try {
      const res = await fetch(URL + "?t=" + Date.now(), { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();

      const sig = JSON.stringify(data);
      if (sig === lastSig) return;
      lastSig = sig;

      render(data);
    } catch (e) {
      // 실패해도 조용히 (방송 안정)
    }
  }

  load();
  setInterval(load, POLL_MS);
})();
