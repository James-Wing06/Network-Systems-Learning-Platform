/* global CodeDashMock */
// biome-ignore lint/suspicious/noRedundantUseStrict: Preserve strict mode for classic browser scripts.
"use strict";

// Dashboard reads demo questions only. Account progress and scores must come from the server.
(() => {
  const data =
    typeof CodeDashMock !== "undefined" ? CodeDashMock.questions : [];
  const total = document.getElementById("total-challenges");
  const categoriesCount = document.getElementById("total-categories");
  const categoryContainer = document.getElementById("dashboard-categories");
  const difficultyContainer = document.getElementById("difficulty-breakdown");
  const suggestions = document.getElementById("suggested-challenges");
  if (
    !total ||
    !categoriesCount ||
    !categoryContainer ||
    !difficultyContainer ||
    !suggestions
  ) {
    return;
  }

  const categories = [...new Set(data.map((q) => q.category))];
  total.textContent = String(data.length);
  categoriesCount.textContent = String(categories.length);
  const descriptions = {
    "Network Layering & Addressing":
      "IP addresses, subnets, and network fundamentals",
    "Troubleshooting & Diagnosis": "Find problems and reason through failures",
    "Protocol Parsing & Data Processing":
      "Interpret logs, protocols, and network data",
  };
  categories.forEach((name, index) => {
    const card = document.createElement("article");
    card.className = "dashboard-category";
    const indexText = document.createElement("span");
    indexText.className = "category-number";
    indexText.textContent = String(index + 1).padStart(2, "0");
    const heading = document.createElement("h3");
    heading.textContent = name;
    const description = document.createElement("p");
    description.textContent =
      descriptions[name] || "Practice networking challenges";
    const count = document.createElement("span");
    count.className = "dashboard-category-count";
    count.textContent = `${data.filter((q) => q.category === name).length} sample challenge(s)`;
    const link = document.createElement("a");
    link.className = "text-link";
    link.href = "questions.html";
    link.textContent = "Browse challenges";
    card.append(indexText, heading, description, count, link);
    categoryContainer.append(card);
  });

  for (const difficulty of ["Easy", "Medium", "Hard"]) {
    const amount = data.filter((q) => q.difficulty === difficulty).length;
    const row = document.createElement("div");
    row.className = "difficulty-row";
    const label = document.createElement("span");
    label.textContent = difficulty;
    const track = document.createElement("div");
    track.className = "difficulty-track";
    const bar = document.createElement("div");
    bar.className = "difficulty-bar";
    const percentage = data.length ? (amount / data.length) * 100 : 0;
    bar.style.width = `${percentage}%`;
    track.append(bar);
    const value = document.createElement("strong");
    value.textContent = String(amount);
    row.append(label, track, value);
    difficultyContainer.append(row);
  }

  data.slice(0, 3).forEach((q) => {
    const link = document.createElement("a");
    link.className = "dashboard-suggestion";
    link.href = `question.html?id=${encodeURIComponent(q.id)}`;
    const name = document.createElement("strong");
    name.textContent = q.title;
    const meta = document.createElement("span");
    meta.textContent = q.difficulty;
    link.append(name, meta);
    suggestions.append(link);
  });
  if (!data.length) {
    categoryContainer.textContent = "No sample categories available.";
    suggestions.textContent = "No sample challenges available.";
  }
})();
