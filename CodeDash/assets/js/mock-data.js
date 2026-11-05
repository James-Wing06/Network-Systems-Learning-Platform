"use strict";

// Demonstration content only; replace via backend GET /api/questions.
((root, factory) => {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else root.CodeDashMock = api;
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const questions = [
    {
      id: "ip-1",
      title: "Validate an IPv4 Address",
      category: "Network Layering & Addressing",
      difficulty: "Easy",
      description:
        "A support ticket reports an invalid IPv4 configuration. Write a function that returns true for a valid dotted-decimal IPv4 address and false otherwise.",
      input: "A string representing an IPv4 address.",
      output: "A boolean.",
      example: "192.168.1.10 → true; 256.1.2.3 → false",
    },
    {
      id: "net-2",
      title: "Classify a Port",
      category: "Troubleshooting & Diagnosis",
      difficulty: "Easy",
      description:
        "A technician needs to classify a TCP port number as well-known (0–1023), registered (1024–49151), or dynamic (49152–65535). Reject invalid port numbers.",
      input: "An integer port number.",
      output: "One classification or invalid.",
      example: "443 → well-known",
    },
    {
      id: "parse-3",
      title: "Parse a Log Entry",
      category: "Protocol Parsing & Data Processing",
      difficulty: "Medium",
      description:
        "Extract the timestamp and severity from a structured log line. Handle missing or malformed fields.",
      input: "A structured log line.",
      output: "Timestamp and severity, or an error.",
      example: "[ERROR] 2026-11-03 timeout → ERROR, 2026-11-03",
    },
    {
      id: "subnet-4",
      title: "Subnet Host Count",
      category: "Network Layering & Addressing",
      difficulty: "Medium",
      description:
        "Given an IPv4 CIDR prefix, calculate the total number of addresses in the block.",
      input: "A prefix length from 0 to 32.",
      output: "Total addresses.",
      example: "/24 → 256",
    },
    {
      id: "trace-5",
      title: "Diagnose a Route",
      category: "Troubleshooting & Diagnosis",
      difficulty: "Hard",
      description:
        "Analyze a list of hop statuses and identify the first failed hop, if any.",
      input: "A list of hop results.",
      output: "First failed hop index or none.",
      example: "ok, ok, timeout → 3",
    },
  ];
  function filterQuestions(items, category, difficulty, search) {
    const term = search.trim().toLowerCase();
    return items.filter(
      (q) =>
        (category === "all" || q.category === category) &&
        (difficulty === "all" || q.difficulty === difficulty) &&
        (!term || `${q.title} ${q.description}`.toLowerCase().includes(term)),
    );
  }
  return { questions, filterQuestions };
});
