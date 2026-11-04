"use strict";

const ticket = document.querySelector("#ticket");
const submit = document.querySelector("#submit-code");
const runTests = document.querySelector("#run-tests");
const result = document.querySelector("#submission-message");
const code = document.querySelector("#code");
const difficulty = document.querySelector("#ticket-difficulty");
const statusLabel = document.querySelector("#workspace-status");
const id = new URLSearchParams(location.search).get("id");
const question = CodeDashMock.questions.find((item) => item.id === id);
function addTextElement(parent, tag, value, className = "") {
  const element = document.createElement(tag);
  element.textContent = String(value);
  if (className) element.className = className;
  parent.append(element);
  return element;
}

function feedback(message, isError = false) {
  result.replaceChildren();
  addTextElement(result, "p", message, `notice ${isError ? "error" : ""}`);
}

function renderServerResult(data) {
  result.replaceChildren();
  const status = typeof data.status === "string" ? data.status : "Unknown";
  addTextElement(result, "h3", `Execution status: ${status}`);
  if (Number.isInteger(data.passedTests) && Number.isInteger(data.totalTests))
    addTextElement(result, "p", `Tests passed: ${data.passedTests} / ${data.totalTests}`);
  if (typeof data.score === "number" && Number.isFinite(data.score))
    addTextElement(result, "p", `Score: ${data.score}`);
  if (typeof data.executionTime === "number" && Number.isFinite(data.executionTime))
    addTextElement(result, "p", `Execution time: ${data.executionTime} seconds`);
  if (typeof data.feedback === "string") {
    addTextElement(result, "p", data.feedback);
  }
  if (typeof data.stderr === "string" && data.stderr)
    addTextElement(result, "pre", data.stderr);
  if (statusLabel) statusLabel.textContent = status;
}

async function handleSubmission(mode) {
  const source = code.value;
  if (!source.trim()) {
    return feedback("Enter code before submitting.", true);
  }
  if (source.length > 20000) {
    return feedback("Solution exceeds the 20,000-character frontend limit.", true);
  }
  if (!CodeDash_API.enabled) {
    return feedback("Code validated locally. Judge0 execution is not connected yet. No code was executed, graded, or saved.");
  }
  submit.disabled = true;
  if (runTests) runTests.disabled = true;
  if (statusLabel) statusLabel.textContent = "Evaluating…";
  feedback("Sending code to the CodeDash backend for evaluation…");
  try {
    const selectedLanguage = document.querySelector("#language").value;
    const data = await CodeDash_API.submitSolution(
      question.id,
      selectedLanguage,
      source,
      mode
    );
    renderServerResult(data);
  } catch (error) {
    if (statusLabel) statusLabel.textContent = "Evaluation failed";
    feedback(error instanceof Error ? error.message : "Unexpected submission error.", true);
  } finally {
    submit.disabled = false;
    if (runTests) runTests.disabled = !CodeDash_API.enabled;
  }
}
if (ticket && submit && result && code) {
  if (!question) {
    addTextElement(ticket, "p", "Question not found. Return to the challenge list.", "notice error");
    if (difficulty) difficulty.textContent = "Unavailable";
    submit.disabled = true;
    code.disabled = true;
    feedback("Choose a valid challenge before writing a solution.", true);
  } else {
    if (difficulty) difficulty.textContent = question.difficulty;
    addTextElement(ticket, "h1", question.title);
    const meta = document.createElement("div");
    meta.className = "ticket-meta";
    addTextElement(meta, "span", question.category, "pill");
    addTextElement(meta, "span", question.difficulty, "pill");
    ticket.append(meta);
    addTextElement(ticket, "h3", "Problem Description");
    addTextElement(ticket, "p", question.description);
    const examples = [
      ["Input", question.input],
      ["Expected Output", question.output],
      ["Example", question.example]
    ];

    for (const [heading, value] of examples) {
      addTextElement(ticket, "h3", heading);
      addTextElement(ticket, "div", value, "ticket-example");
    }
    code.addEventListener("keydown", (event) => {
      if (event.key !== "Tab") return;
      event.preventDefault();
      code.setRangeText("    ", code.selectionStart, code.selectionEnd, "end");
    });
    if (runTests) {
      runTests.disabled = !CodeDash_API.enabled;
      runTests.addEventListener("click", () => handleSubmission("run"));
    }
    submit.addEventListener("click", () => handleSubmission("submit"));
  }
}
