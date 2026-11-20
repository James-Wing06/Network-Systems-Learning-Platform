// biome-ignore lint/suspicious/noRedundantUseStrict: Preserve strict mode for classic browser scripts.
"use strict";

// CodeDash API contract, not Judge0's native JSON format.
// The backend handles fetching AWS test cases, communicating with Judge0, and saving results.

globalThis.CodeDash_API = {
  // Enabled to connect to the live /api/submissions grading backend.
  enabled: true,

  // Keep as "/api/submissions" if frontend and backend share a domain,
  // or replace with your full AWS API Gateway / backend URL (e.g., "https://amazonaws.com").
  endpoint: "/api/submissions",

  async submitSolution(questionId, language, code, mode = "submit") {
    if (!this.enabled) {
      throw new Error("Grading backend is currently disabled.");
    }

    if (!code || !code.trim()) {
      throw new Error("Please enter your Python solution before submitting.");
    }

    const response = await fetch(this.endpoint, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        questionId,
        language,
        code,
        mode,
      }),
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
