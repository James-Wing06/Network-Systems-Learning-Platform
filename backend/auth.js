
const express = require("express");
const bcrypt = require("bcryptjs");
const pool = require("./db");
const router = express.Router();

// Return an error response
function fail(res, status, message) {
  return res.status(status).json({ success: false, message });
}

// Check login status
function requireAuth(req, res, next) {
  if (!req.session || !req.session.userId) {
    return fail(res, 401, "Please log in first.");
  }
  next();
}

// Check email
function validEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && email.length <= 255;
}

// Register
router.post("/register", async (req, res) => {
  const { username, email, password, confirmPassword } = req.body || {};

  if (typeof username !== "string" || !/^[A-Za-z0-9_-]{3,30}$/.test(username))
    return fail(res, 400, "Invalid username.");

  if (typeof email !== "string" || !validEmail(email.trim()))
    return fail(res, 400, "Invalid email.");

  if (typeof password !== "string" || password.length < 8 ||
      Buffer.byteLength(password, "utf8") > 72)
    return fail(res, 400, "Invalid password length.");

  if (confirmPassword !== undefined && password !== confirmPassword)
    return fail(res, 400, "Passwords do not match.");

  try {
    const hash = await bcrypt.hash(password, 12);
    const cleanEmail = email.trim().toLowerCase();

    const [result] = await pool.execute(
      "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
      [username, cleanEmail, hash]
    );

    return res.status(201).json({
      success: true,
      message: "Account created. Please log in.",
      user: { user_id: result.insertId, username, email: cleanEmail }
    });
  } catch (err) {
    if (err.code === "ER_DUP_ENTRY")
      return fail(res, 409, "Username or email already exists.");

    console.error(err);
    return fail(res, 500, "Registration failed.");
  }
});

// Login
router.post("/login", async (req, res) => {
  const { email, password } = req.body || {};

  if (typeof email !== "string" || !validEmail(email.trim()) ||
      typeof password !== "string" || !password)
    return fail(res, 400, "Invalid email or password.");

  try {
    const [rows] = await pool.execute(
      "SELECT user_id, username, email, password_hash FROM users WHERE email = ? LIMIT 1",
      [email.trim().toLowerCase()]
    );

    const user = rows[0];

    if (!user || !(await bcrypt.compare(password, user.password_hash)))
      return fail(res, 401, "Invalid email or password.");

    req.session.regenerate((err) => {
      if (err) {
        console.error(err);
        return fail(res, 500, "Login failed.");
      }

      req.session.userId = user.user_id;

      req.session.save((saveErr) => {
        if (saveErr) {
          console.error(saveErr);
          return fail(res, 500, "Login failed.");
        }

        return res.json({
          success: true,
          message: "Login successful.",
          user: {
            user_id: user.user_id,
            username: user.username,
            email: user.email
          }
        });
      });
    });
  } catch (err) {
    console.error(err);
    return fail(res, 500, "Login failed.");
  }
});

// Get current user
router.get("/me", requireAuth, async (req, res) => {
  try {
    const [rows] = await pool.execute(
      "SELECT user_id, username, email FROM users WHERE user_id = ? LIMIT 1",
      [req.session.userId]
    );

    if (!rows.length) {
      return req.session.destroy(() =>
        fail(res, 401, "Account not found.")
      );
    }

    return res.json({ success: true, user: rows[0] });
  } catch (err) {
    console.error(err);
    return fail(res, 500, "Could not load account.");
  }
});

// Logout
router.post("/logout", (req, res) => {
  if (!req.session)
    return res.json({ success: true, message: "Logged out." });

  req.session.destroy((err) => {
    if (err) {
      console.error(err);
      return fail(res, 500, "Logout failed.");
    }

    res.clearCookie("codedash.sid", { path: "/" });
    return res.json({ success: true, message: "Logged out." });
  });
});

// Delete account
router.delete("/account", requireAuth, async (req, res) => {
  const { password } = req.body || {};

  if (typeof password !== "string" || !password)
    return fail(res, 400, "Password is required.");

  let conn;

  try {
    conn = await pool.getConnection();

    const [rows] = await conn.execute(
      "SELECT password_hash FROM users WHERE user_id = ? LIMIT 1",
      [req.session.userId]
    );

    if (!rows.length || !(await bcrypt.compare(password, rows[0].password_hash)))
      return fail(res, 401, "Incorrect password.");

    await conn.beginTransaction();

    await conn.execute(
      "DELETE FROM submissions WHERE user_id = ?",
      [req.session.userId]
    );
    await conn.execute(
      "DELETE FROM users WHERE user_id = ?",
      [req.session.userId]
    );

    await conn.commit();

    req.session.destroy((err) => {
      if (err) console.error(err);
      res.clearCookie("codedash.sid", { path: "/" });
      return res.json({ success: true, message: "Account deleted." });
    });
  } catch (err) {
    if (conn) await conn.rollback().catch(() => {});
    console.error(err);
    return fail(res, 500, "Could not delete account.");
  } finally {
    if (conn) conn.release();
  }
});

module.exports = { router, requireAuth };
