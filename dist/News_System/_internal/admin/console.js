const items = document.querySelectorAll(".nav-item");
const frame = document.getElementById("frame");
const title = document.getElementById("title");
const reloadBtn = document.getElementById("reloadBtn");

function setActive(btn) {
  items.forEach(i => i.classList.remove("active"));
  btn.classList.add("active");

  const src = btn.getAttribute("data-src");
  frame.src = src;

  // 제목은 버튼 텍스트 사용
  const label = btn.querySelector(".txt")?.innerText || "관리";
  title.innerText = label;
}

items.forEach(btn => {
  btn.addEventListener("click", () => setActive(btn));
});

reloadBtn.addEventListener("click", () => {
  try {
    frame.contentWindow.location.reload();
  } catch (e) {
    // cross-origin이 아니므로 보통 문제 없음
    frame.src = frame.src;
  }
});
