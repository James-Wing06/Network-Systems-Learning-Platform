"use strict";
const express = require("express");
const pool = require("./db");
const { requireAuth } = require("./auth");
const { getGraderPool } = require("./grader-db");
const { evaluate } = require("./judge0");
const { questionId } = require("./questions");

const router = express.Router();
router.use(requireAuth);

function normalizeLanguageName(name) {
  return String(name).trim().toLowerCase().replace(/[^a-z0-9]/g, "");
}
function error(res, code, message) {
  return res.status(code).json({ success: false, error: message });
}

async function findSupportedLanguage(qid, submitted) {
  const [languages] = await pool.execute(
    `SELECT l.language_id, l.name
       FROM languages l JOIN question_languages ql ON ql.language_id = l.language_id
      WHERE ql.question_id=? ORDER BY l.language_id`, [qid]
  );
  const candidate = String(submitted).trim();
  const key = normalizeLanguageName(candidate);
  return languages.find(l => String(l.language_id) === candidate ||
    normalizeLanguageName(l.name) === key ||
    (key === 'python' && normalizeLanguageName(l.name).startsWith('python')) ||
    (key === 'javascript' && normalizeLanguageName(l.name).startsWith('javascript')));
}

// POST /api/submissions -- front-end api.js contract: questionId, language, code, mode.
router.post("/", async (req, res) => {
  const body = req.body || {};
  const id = questionId(body.questionId);
  const language = body.language;
  const code = body.code;
  const mode = body.mode ?? "submit";

  if (!id) return error(res, 400, "Invalid question ID.");
  if (typeof language !== "string" && typeof language !== "number")
    return error(res, 400, "Select a programming language.");
  if (typeof code !== "string" || !code.trim())
    return error(res, 400, "Enter code before submitting.");
  if (code.length > 20000 || Buffer.byteLength(code, "utf8") > 80000)
    return error(res, 413, "Solution is too large.");
  if (!["run", "submit"].includes(mode))
    return error(res, 400, "Invalid submission mode.");

  let submissionId = null;
  try {
    const [questionRows] = await pool.execute(
      "SELECT question_id FROM questions WHERE question_id=?", [id]
    );
    if (!questionRows.length) return error(res, 404, "Question not found.");

    const supported = await findSupportedLanguage(id, language);
    if (!supported) return error(res, 400, "Language is not supported for this question.");

    // The grader account, not the public application account, reads hidden tests.
    const graderDb = getGraderPool();
    const [cases] = await graderDb.execute(
      `SELECT test_case_id, input_data, expected_out
         FROM test_cases WHERE question_id=? ORDER BY test_case_id`, [id]
    );
    if (!cases.length) return error(res, 422, "Question has no test cases yet.");

    // "run" is unsaved practice; "submit" persists an owned submission.
    if (mode === "submit") {
      const [inserted] = await pool.execute(
        `INSERT INTO submissions (question_id, user_id, language_id, code)
         VALUES (?, ?, ?, ?)`, [id, req.session.userId, supported.language_id, code]
      );
      submissionId = inserted.insertId;
    }

    let result;
    try {
      result = await evaluate({ source: code, language: supported, cases });
    } catch (judgeError) {
      console.error("Judge0 evaluation failed:", judgeError.message);
      if (submissionId !== null) {
        // Keep DB row pending (ungraded) rather than pretending code failed.
        // The database's chk_submissions_status enum is not assumed to include 'error'.
        await graderDb.execute(
          "UPDATE submissions SET feedback=? WHERE submission_id=?",
          ["Evaluation service unavailable. Submission has not been graded.", submissionId]
        );
      }
      return error(res, judgeError.statusCode || 503,
        "Evaluation service unavailable or not configured. No grade was recorded.");
    }

    if (submissionId !== null) {
      await graderDb.execute(
        `UPDATE submissions
            SET status=?, score=?, feedback=?
          WHERE submission_id=?`,
        [result.status === "Passed" ? "passed" : "failed", result.score, result.feedback, submissionId]
      );
    }
    return res.json({ success: true, mode, submissionId, ...result });
  } catch (err) {
    console.error("Submission API error:", err);
    return error(res, err.statusCode || 500,
      err.statusCode === 503 ? "Grading service is not configured." : "Could not process submission.");
  }
});

// GET /api/submissions/me : list only authenticated user's own results.
router.get("/me", async (req, res) => {
  try {
    const [rows] = await pool.execute(
      `SELECT s.submission_id, s.question_id, q.title AS question_title,
              s.language_id, s.status, s.score, s.feedback,
              s.submitted_at
         FROM submissions s JOIN questions q ON q.question_id=s.question_id
        WHERE s.user_id=?
        ORDER BY s.submitted_at DESC, s.submission_id DESC LIMIT 100`,
      [req.session.userId]
    );
    return res.json({ success: true, submissions: rows });
  } catch (err) {
    console.error("List results error:", err);
    return error(res, 500, "Could not load submissions.");
  }
});

// GET /api/submissions/:id : enforce ownership in SQL.
router.get("/:id", async (req, res) => {
  const sid = questionId(req.params.id);
  if (!sid) return error(res, 400, "Invalid submission ID.");
  try {
    const [rows] = await pool.execute(
      `SELECT submission_id, question_id, language_id, status, score,
              feedback, submitted_at
         FROM submissions WHERE submission_id=? AND user_id=? LIMIT 1`,
      [sid, req.session.userId]
    );
    if (!rows.length) return error(res, 404, "Submission not found.");
    return res.json({ success: true, submission: rows[0] });
  } catch (err) {
    console.error("Get result error:", err);
    return error(res, 500, "Could not load submission.");
  }
});

module.exports = { router };
