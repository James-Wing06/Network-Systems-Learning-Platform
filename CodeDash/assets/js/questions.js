"use strict";

const list = document.querySelector("#question-list");
const categoryFilter = document.querySelector("#category-filter");
const difficultyFilter = document.querySelector("#difficulty-filter");
const searchInput = document.querySelector("#search");
const count = document.querySelector("#result-count");
if (list && categoryFilter && difficultyFilter && searchInput && count) {
  [...new Set(CodeDashMock.questions.map((q) => q.category))].forEach(
    (category) => {
      const option = document.createElement("option");
      option.value = category;
      option.textContent = category;
      categoryFilter.append(option);
    },
  );
  function render() {
    const filtered = CodeDashMock.filterQuestions(
      CodeDashMock.questions,
      categoryFilter.value,
      difficultyFilter.value,
      searchInput.value,
    );
    list.replaceChildren();
    count.textContent = `${filtered.length} question(s) found`;
    filtered.forEach((q) => {
      const card = document.createElement("article");
      card.className = "card";
      const title = document.createElement("h3");
      title.textContent = q.title;
      const badge = document.createElement("span");
      badge.className = "pill";
      badge.textContent = q.difficulty;
      const category = document.createElement("p");
      category.textContent = q.category;
      const link = document.createElement("a");
      link.className = "btn primary";
      link.href = `question.html?id=${encodeURIComponent(q.id)}`;
      link.textContent = "Open ticket";
      card.append(title, badge, category, link);
      list.append(card);
    });
  }
  [categoryFilter, difficultyFilter, searchInput].forEach((el) =>
    el.addEventListener("input", render),
  );
  render();
}
