"use strict";
const express = require("express");
const pool = require("./db");

const router = express.Router();

function questionId(value) {
  const text = String(value);
  const n = Number(text);
  return /^\d+$/.test(text) && Number.isSafeInteger(n) && n > 0 ? n : null;
}

function difficultyLabel(level) {
  if (level <= 2) return "Easy";
  if (level === 3) return "Medium";
  return "Hard";
}

function mapQuestion(row) {
  return {
    id: String(row.question_id),
    title: row.title,
    category: row.cat_name,
    categoryId: row.category_id,
    difficulty: difficultyLabel(row.difficulty),
    difficultyLevel: row.difficulty,
    description: row.description || "No description available."
  };
}

//get questions from database
router.get("/", async (_req, res) => {
  try {
    const [rows] = await pool.execute(
      `SELECT q.question_id, q.title, q.description, q.difficulty,
              q.category_id, c.cat_name
         FROM questions q
         JOIN categories c ON c.category_id = q.category_id
        ORDER BY q.question_id`
    );
    return res.json({ success: true, questions: rows.map(mapQuestion) });
  } catch (err) {
    console.error("Questions list error:", err);
    return res.status(500).json({ success: false, error: "Could not load questions." });
  }
});

// ccording to ID return questions details 
router.get("/:id", async (req, res) => {
  const id = questionId(req.params.id);
  if (!id) return res.status(400).json({ success: false, error: "Invalid question ID." });
  try {
    const [[rows], [languages], [examples]] = await Promise.all([
      pool.execute(
        `SELECT q.question_id, q.title, q.description, q.difficulty,
                q.category_id, c.cat_name
           FROM questions q JOIN categories c ON c.category_id=q.category_id
          WHERE q.question_id=? LIMIT 1`, [id]),
      pool.execute(
        `SELECT l.language_id, l.name FROM question_languages ql
           JOIN languages l ON l.language_id=ql.language_id
          WHERE ql.question_id=? ORDER BY l.name`, [id]),
      // Never query the hidden test_cases table from the public API.
      pool.execute(
        `SELECT input_data, expected_out FROM v_public_test_cases
          WHERE question_id=? ORDER BY test_case_id LIMIT 5`, [id])
    ]);

    
    if (!rows.length) return res.status(404).json({ success: false, error: "Question not found." });
    const q = mapQuestion(rows[0]);
    q.languages = languages.map(l => ({ id: l.language_id, name: l.name }));
    q.examples = examples.map(e => ({ input: e.input_data || "", output: e.expected_out }));
    // Compatibility with the frontend's previous CodeDashMock ticket structure.
    q.input = q.examples[0]?.input ?? "No public example provided.";
    q.output = q.examples[0]?.output ?? "No public example provided.";
    q.example = q.examples.length ? "Use the public sample input above." : "No public example provided.";
    return res.json({ success: true, question: q });
  } catch (err) {
    console.error("Question detail error:", err);
    return res.status(500).json({ success: false, error: "Could not load question." });
  }
});

module.exports = { router, questionId, difficultyLabel };
