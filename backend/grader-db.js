"use strict";
// Separate grading privileges: only grader can read hidden test cases or save scores.
const path = require("path");
const fs = require("fs");
require("dotenv").config({ path: path.join(__dirname, ".env") });
const mysql = require("mysql2/promise");

let graderPool;
function getGraderPool() {
  if (graderPool) return graderPool;
  const user = process.env.GRADER_DB_USER || process.env.GRADER_USER;
  const password = process.env.GRADER_DB_PASSWORD || process.env.GRADER_PASSWORD;
  if (!user || !password) {
    const e = new Error("Set GRADER_DB_USER and GRADER_DB_PASSWORD in backend/.env");
    e.statusCode = 503;
    throw e;
  }
  const options = {
    user,
    password,
    database: process.env.DB_NAME || "csci387",
    waitForConnections: true,
    connectionLimit: 4
  };
  if (process.env.DB_SOCKET_PATH) {
    options.socketPath = process.env.DB_SOCKET_PATH;
  } else {
    options.host = process.env.DB_HOST || "127.0.0.1";
    options.port = Number(process.env.DB_PORT || 3306);
    if (process.env.DB_SSL_CA) options.ssl = {
      ca: fs.readFileSync(process.env.DB_SSL_CA), rejectUnauthorized: true
    };
  }
  graderPool = mysql.createPool(options);
  return graderPool;
}
module.exports = { getGraderPool };
