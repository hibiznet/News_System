const express = require("express");
const fs = require("fs");
const path = require("path");

const app = express();
app.use(express.json());
app.use(express.static(__dirname));

const BREAKING_PATH = path.join(__dirname, "overlay/breaking.json");

app.post("/api/breaking", (req, res) => {
  const { text, expire } = req.body;

  fs.writeFileSync(
    BREAKING_PATH,
    JSON.stringify({ text }, null, 2),
    "utf-8"
  );

  if (expire) {
    setTimeout(() => {
      fs.writeFileSync(
        BREAKING_PATH,
        JSON.stringify({ text: "" }, null, 2),
        "utf-8"
      );
    }, expire * 60 * 1000);
  }

  res.json({ ok: true });
});

app.post("/api/clear", (_, res) => {
  fs.writeFileSync(
    BREAKING_PATH,
    JSON.stringify({ text: "" }, null, 2),
    "utf-8"
  );
  res.json({ ok: true });
});

app.listen(8080, () => {
  console.log("서버 실행: http://localhost:8080");
});
