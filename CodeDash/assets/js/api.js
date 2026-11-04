"use strict";

// CodeDash contract, NOT Judge0 native JSON. The PHP server talks to Judge0.
const CodeDash_API = {
  enabled: false, // Change to true ONLY when /api/submissions is implemented and tested.
  async submitSolution(questionId, language, code, mode = "submit") {
    const response = await fetch("/api/submissions", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ questionId, language, code, mode }),
    });
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error("The server returned an invalid response.");
    }
    if (!response.ok) {
      throw new Error(
        typeof data.error === "string"
          ? data.error
          : `Server error (${response.status}).`,
      );
    }
    return data;
  },
};
