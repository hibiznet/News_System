async function loadBanner() {
  const res = await fetch("banner.json");
  const data = await res.json();
  document.getElementById("banner-text").innerText = data.text;
}

setInterval(loadBanner, 10000);
loadBanner();
