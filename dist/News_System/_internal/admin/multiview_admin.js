function normalizeYoutubeUrl(url) {
  url = (url || "").trim();
  if (!url) return "";

  // HTML에 &amp;로 들어온 경우도 대비
  url = url.replaceAll("&amp;", "&");

  // youtu.be/xxxx -> embed
  if (url.includes("youtu.be/")) {
    const id = url.split("youtu.be/")[1].split(/[?&]/)[0];
    url = `https://www.youtube.com/embed/${id}`;
  }

  // watch?v=xxxx -> embed
  if (url.includes("youtube.com/watch")) {
    const u = new URL(url);
    const id = u.searchParams.get("v");
    if (id) url = `https://www.youtube.com/embed/${id}`;
  }

  // 이미 embed면 video id 유지
  if (url.includes("youtube.com/embed/")) {
    // 기존 쿼리 유지 + autoplay/mute/playsinline 강제 부여
    const u = new URL(url);
    // 자동재생 정책 대응
    u.searchParams.set("autoplay", "1");
    u.searchParams.set("mute", "1");
    u.searchParams.set("playsinline", "1");

    // controls 파라미터가 이미 없으면 기본 0
    if (!u.searchParams.has("controls")) u.searchParams.set("controls", "0");

    return u.toString();
  }

  return url;
}

function normalizeUrl(url) {
  url = (url || "").trim();
  if (!url) return "";
  // 유튜브면 자동 옵션 붙이기
  if (url.includes("youtube.com") || url.includes("youtu.be")) {
    return normalizeYoutubeUrl(url);
  }
  // 그 외는 그대로
  return url.replaceAll("&amp;", "&");
}

function payload() {
  return {
    mode: Number(document.getElementById("mode").value),
    items: [
      { src: normalizeUrl(document.getElementById("src1").value) },
      { src: normalizeUrl(document.getElementById("src2").value) },
      { src: normalizeUrl(document.getElementById("src3").value) },
      { src: normalizeUrl(document.getElementById("src4").value) }
    ]
  };
}

async function save() {
  await fetch("/api/layout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload())
  });
  document.getElementById("status").innerText = "✅ 저장됨";
}

async function clearAll() {
  await fetch("/api/layout/clear", { method: "POST" });
  document.getElementById("status").innerText = "♻️ 초기화됨";
}


