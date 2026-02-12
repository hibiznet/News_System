const tabs = document.querySelectorAll(".tab");
const frame = document.getElementById("frame");

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach(t => t.classList.remove("active"));
    tab.classList.add("active");

    const src = tab.getAttribute("data-src");
    frame.src = src;
  });
});
