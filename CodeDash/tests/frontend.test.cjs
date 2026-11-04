-"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { validateLogin, validateRegistration } = require("../assets/js/validation.js");
const { questions, filterQuestions } = require("../assets/js/mock-data.js");
const root = path.resolve(__dirname, "..");
test("all homepage navigation destinations exist", () => {
  const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
  for (const href of [...html.matchAll(/href="([^"]+\.html)"/g)].map((m) => m[1])) {
    assert.ok(fs.existsSync(path.join(root, href)), `${href} missing`);
  }
});
test("all expected pages exist", () => {
  for (const file of ["index.html", "about.html", "login.html", "register.html", "dashboard.html", "questions.html", "question.html", "account.html"]) {
    assert.ok(fs.existsSync(path.join(root, file)), `${file} missing`);
  }
});
test("invalid emails and empty passwords are rejected", () => {
  assert.match(validateLogin("not-an-email", "password"), /email/);
  assert.match(validateLogin("user@example.com", ""), /password/);
});
test("valid login form fields pass client validation", () => {
  assert.equal(validateLogin("user@example.com", "example-pass"), "");
});
test("registration rejects short username, short password, and mismatch", () => {
  assert.match(validateRegistration("ab", "user@example.com", "abcdefgh", "abcdefgh"), /Username/);
  assert.match(validateRegistration("alex", "user@example.com", "short", "short"), /8 characters/);
  assert.match(validateRegistration("alex", "user@example.com", "abcdefgh", "different"), /match/);
});
test("registration accepts valid input", () => {
  assert.equal(validateRegistration("alex_1", "user@example.com", "abcdefgh", "abcdefgh"), "");
});
test("filtering handles exact categories, difficulty and case-insensitive search", () => {
  assert.equal(filterQuestions(questions, "Network Layering & Addressing", "Easy", "IPV4").length, 1);
  assert.equal(filterQuestions(questions, "all", "Hard", "").length, 1);
});
test("filtering handles no matches and empty dataset", () => {
  assert.deepEqual(filterQuestions(questions, "all", "all", "not-present-anywhere"), []);
  assert.deepEqual(filterQuestions([], "all", "all", ""), []);
});
test("sample questions have unique IDs and required fields", () => {
  assert.equal(new Set(questions.map((q) => q.id)).size, questions.length);
  for (const q of questions) {
    for (const key of ["id", "title", "category", "difficulty", "description"]) assert.ok(q[key]);
  }
});
test("password length boundary: 7 vs 8", () => {
  const seven = validateRegistration(
    "alex", "alex@example.com", "1234567", "1234567"
  );
  const eight = validateRegistration(
    "alex", "alex@example.com", "12345678", "12345678"
  );
  assert.match(seven, /8 characters/);
  assert.equal(eight, "");
});
test("username length boundaries: 2, 3, 30, 31", () => {
  function check(username) {
    return validateRegistration(
      username, "alex@example.com", "12345678", "12345678"
    );
  }

  assert.match(check("ab"), /Username/);
  assert.equal(check("abc"), "");
  assert.equal(check("a".repeat(30)), "");
  assert.match(check("a".repeat(31)), /Username/);
});
test("registration rejects script-like usernames", () => {
  const result = validateRegistration(
    "<script>alert(1)</script>",
    "alex@example.com",
    "12345678",
    "12345678"
  );

  assert.match(result, /Username/);
});
