-- Database: nslp
--
-- Accounts:
-- nslp_app       - Registration, login, and submissions
-- nslp_admin_app - Administrative operations
-- nslp_grader    - Code grading
--
-- Permissions follow the principle of least privilege.
-- Account passwords and credentials are intentionally excluded.
--
-- Exact GRANT statements will be added after verification.

-- ==================================================
-- APPLICATION ACCOUNT: nslp_app
-- ==================================================
-- These grants require the account to exist already.
-- Run only during database setup, not during testing.
-- No passwords are stored in this file.

GRANT SELECT ON `nslp`.`categories` TO `nslp_app`@`%`;

GRANT SELECT ON `nslp`.`languages` TO `nslp_app`@`%`;

GRANT SELECT ON `nslp`.`question_languages` TO `nslp_app`@`%`;

GRANT SELECT ON `nslp`.`questions` TO `nslp_app`@`%`;

GRANT SELECT (
    `feedback`, `language_id`, `question_id`,
    `score`, `status`, `submission_id`,
    `submitted_at`, `user_id`
),
INSERT (
    `code`, `language_id`, `question_id`, `user_id`
)
ON `nslp`.`submissions` TO `nslp_app`@`%`;

GRANT SELECT (
    `created_at`, `email`, `is_admin`,
    `password_hash`, `user_id`, `username`
),
INSERT (
    `email`, `password_hash`, `username`
),
UPDATE (
    `email`, `password_hash`, `username`
)
ON `nslp`.`users` TO `nslp_app`@`%`;

GRANT SELECT ON `nslp`.`v_public_test_cases` TO `nslp_app`@`%`;

-- ==================================================
-- ADMIN APPLICATION ACCOUNT: nslp_admin_app
-- ==================================================
-- Manages questions, categories, languages, and test cases.
-- Can read user information except password hashes.
-- Can read submission results but not submitted code.
-- Account must exist before executing these grants.

GRANT SELECT, INSERT, UPDATE, DELETE
ON `nslp`.`categories`
TO `nslp_admin_app`@`%`;

GRANT SELECT, INSERT, UPDATE, DELETE
ON `nslp`.`languages`
TO `nslp_admin_app`@`%`;

GRANT SELECT, INSERT, UPDATE, DELETE
ON `nslp`.`question_languages`
TO `nslp_admin_app`@`%`;

GRANT SELECT, INSERT, UPDATE, DELETE
ON `nslp`.`questions`
TO `nslp_admin_app`@`%`;

GRANT SELECT (
    `feedback`, `graded_at`, `language_id`,
    `question_id`, `score`, `status`,
    `submission_id`, `submitted_at`, `user_id`
)
ON `nslp`.`submissions`
TO `nslp_admin_app`@`%`;

GRANT SELECT, INSERT, UPDATE, DELETE
ON `nslp`.`test_cases`
TO `nslp_admin_app`@`%`;

GRANT SELECT (
    `created_at`, `email`, `is_admin`,
    `user_id`, `username`
)
ON `nslp`.`users`
TO `nslp_admin_app`@`%`;

-- ==================================================
-- GRADER ACCOUNT: nslp_grader
-- ==================================================
-- Reads questions, test cases, and submitted code.
-- Updates grading status, score, feedback, and timestamp.
-- Cannot modify submitted code or submission ownership.
-- Account must already exist before executing these grants.

GRANT SELECT
ON `nslp`.`questions`
TO `nslp_grader`@`%`;

GRANT SELECT (
    `code`,
    `language_id`,
    `question_id`,
    `status`,
    `submission_id`,
    `user_id`
),
UPDATE (
    `feedback`,
    `graded_at`,
    `score`,
    `status`
)
ON `nslp`.`submissions`
TO `nslp_grader`@`%`;

GRANT SELECT
ON `nslp`.`test_cases`
TO `nslp_grader`@`%`;