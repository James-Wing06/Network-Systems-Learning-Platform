// Express server entry pointes 

// Imports routers for different backend features.
"use strict";
// CodeDash/NSLP: same-origin Express server, session authentication, MySQL APIs.
const path = require("path");
require("dotenv").config({ path: path.join(__dirname, ".env") });
const express = require("express");
const session = require("express-session");
const { router: authRouter } = require("./auth");
const { router: questionsRouter } = require("./questions");
const { router: submissionsRouter } = require("./submissions");

if (!process.env.SESSION_SECRET || process.env.SESSION_SECRET.length < 32)
  throw new Error("Set a random SESSION_SECRET (32+ chars) in backend/.env");

// create express server
const app = express();
const port = Number(process.env.PORT || 3000);
// __DIR__ '/..' in PHP
const root = path.resolve(__dirname, "..");
if (process.env.NODE_ENV === "production") app.set("trust proxy", 1);

app.use(express.json({ limit: "128kb" }));
app.use(express.urlencoded({ extended: false, limit: "128kb" }));

app.use(session({
  name: "codedash.sid",
  secret: process.env.SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    maxAge: 24 * 60 * 60 * 1000
  }
}));

// Reject requests from a different origin when the browser supplies Origin.
// HTTPS reverse-proxy deployments should set APP_ORIGIN=https://your-domain.example.
app.use("/api", (req, res, next) => {
  if (["GET", "HEAD", "OPTIONS"].includes(req.method)) return next();
  const requestOrigin = req.get("origin");
  if (!requestOrigin) return next(); // CLI clients can omit Origin; sessions still required.
  const allowed = process.env.APP_ORIGIN || `${req.protocol}://${req.get("host")}`;
  if (requestOrigin !== allowed) return res.status(403).json({ error: "Origin not allowed." });
  next();
});

app.use("/api/auth", authRouter);
app.use("/api/questions", questionsRouter);
app.use("/api/submissions", submissionsRouter);


// return html static file
app.use("/assets", express.static(path.join(root, "assets")));
const pages = new Set([
  "index.html", "login.html", "register.html", "dashboard.html",
  "questions.html", "question.html", "account.html", "about.html"
]);
app.get("/", (_req, res) => res.sendFile(path.join(root, "index.html")));
app.get("/:page", (req, res) => {
  if (!pages.has(req.params.page)) return res.status(404).send("Not found");
  res.sendFile(path.join(root, req.params.page));
});
// api unknown just return 404
app.use("/api", (_req, res) => res.status(404).json({ error: "API route not found." }));


if (require.main === module) {
  app.listen(port, () => console.log(`CodeDash running at http://localhost:${port}`));
}
module.exports = app;
