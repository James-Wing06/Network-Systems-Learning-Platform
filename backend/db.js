"use strict";

const path = require("path");
const fs = require("fs");
require("dotenv").config({ path: path.join(__dirname, ".env") });
const mysql = require("mysql2/promise");

// MySQL connection settings
const settings = {
  host: process.env.DB_HOST,
  port: Number(process.env.DB_PORT || 3306),
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  waitForConnections: true,
  connectionLimit: 10,
  decimalNumbers: true
};

// SSL for AWS RDS
if (process.env.DB_SSL_CA) {
  settings.ssl = {
    ca: fs.readFileSync(process.env.DB_SSL_CA),
    rejectUnauthorized: true
  };
}

// Create and export connection pool
module.exports = mysql.createPool(settings);