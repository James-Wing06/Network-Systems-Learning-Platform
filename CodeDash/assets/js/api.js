"use strict";

// CodeDash API contract, not Judge0's native JSON format.
// The backend will handle communication with Judge0.

globalThis.CodeDash_API = {
  // Enable only after /api/submissions is implemented and tested.
  enabled: false,

  async submitSolution(questionId, language, code, mode = "submit") {
    const response = await fetch("/api/submissions", {
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
