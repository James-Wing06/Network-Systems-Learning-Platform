"""Focused MySQL test suite for the NSLP database (nslpdatabase_secure_v3.sql).

Requires:  pip install mysql-connector-python

!!! Run ONLY against a disposable server/database. !!!
Your SQL script is hard-coded to the database `nslp`, and it creates accounts
that are granted on `nslp`. To test safely, make a copy of the script where
`nslp` -> `nslp_test` (and ideally the three account names get a `_test`
suffix), run it on a disposable RDS instance or local MySQL 8.4, then point
this suite at it.

Required environment variables
  DB_HOST, DB_USER, DB_PASSWORD   admin/owner account (can DDL + all DML)
  DB_NAME                         must end with _test
  ALLOW_TEST_DB=YES               explicit confirmation
  DB_SSL_CA                       path to the trusted RDS CA bundle

Optional (privilege tests for a role are SKIPPED if its password is missing)
  DB_PORT (3306)
  ACCOUNT_HOST ('%')              host part of the three least-privilege accounts
  APP_USER (nslp_app)             APP_PASSWORD
  GRADER_USER (nslp_grader)       GRADER_PASSWORD
  ADMINAPP_USER (nslp_admin_app)  ADMINAPP_PASSWORD

What is covered
  1. Schema introspection (columns, types, engine, collation, PK/UK/FK rules,
     CHECKs enforced, indexes on FK columns, view definition)
  2. Constraint behavior with SPECIFIC MySQL error numbers
  3. "Known gaps": documents behavior that is currently allowed (if you fix
     the schema, those tests fail on purpose -> update them)
  4. Injection / encoding payloads treated as inert data
  5. Account hygiene (SSL required, no GRANT OPTION, no wildcard grants)
  6. Per-account privilege tests (app / grader / admin_app)
  7. Session/server settings (strict mode, require_secure_transport, ...)
  8. Focused concurrency (unique keys and FK races)

NOT covered (needs API-level tests): SQL injection through Spring Boot,
"user A can't read user B's submissions", JPA/ORM compatibility with
column-level grants, password hashing, rate limiting.
"""

import os
import random
import re
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

import mysql.connector
from mysql.connector import Error

# ----------------------------------------------------------------------
# Safety guards + configuration
# ----------------------------------------------------------------------
DB = os.getenv("DB_NAME", "")
if not re.fullmatch(r"[A-Za-z0-9_]+_test", DB) or os.getenv("ALLOW_TEST_DB") != "YES":
    raise SystemExit(
        "Refusing to run: DB_NAME must end with _test and ALLOW_TEST_DB=YES."
    )
if not os.getenv("DB_SSL_CA"):
    raise SystemExit(
        "Set DB_SSL_CA to the trusted RDS CA certificate file; TLS verification is required."
    )

BASE = dict(
    host=os.environ["DB_HOST"],
    port=int(os.getenv("DB_PORT", "3306")),
    database=DB,
    connection_timeout=10,
)
SSL = dict(
    ssl_ca=os.environ["DB_SSL_CA"], ssl_verify_cert=True, ssl_verify_identity=True
)
ADMIN = (os.environ["DB_USER"], os.environ["DB_PASSWORD"])
ACCOUNT_HOST = os.getenv("ACCOUNT_HOST", "%")
ACCOUNTS = {
    "app": (os.getenv("APP_USER", "nslp_app"), os.getenv("APP_PASSWORD")),
    "grader": (os.getenv("GRADER_USER", "nslp_grader"), os.getenv("GRADER_PASSWORD")),
    "admin_app": (
        os.getenv("ADMINAPP_USER", "nslp_admin_app"),
        os.getenv("ADMINAPP_PASSWORD"),
    ),
}
P = "zt_"  # prefix for every row this suite creates (used by the cleanup sweep)

# This test suite mutates its selected database. Never run it on valuable data.
# The suffix guard alone does not establish that the RDS instance is isolated.

# MySQL error numbers
DUP, FK_PARENT, FK_CHILD = 1062, 1451, 1452
NULL_COL, TOO_LONG, OUT_OF_RANGE, CHECK_FAIL = 1048, 1406, 1264, 3819
# MySQL may enforce CHECK before reporting unsigned-column range errors.
INVALID_DIFFICULTY = {OUT_OF_RANGE, CHECK_FAIL}
ACCESS_DENIED_LOGIN, BAD_FIELD = 1045, 1054
DENIED = {1044, 1142, 1143, 1227}  # db / table / column / global-privilege denied

ALL_TABLES = [
    "users",
    "categories",
    "languages",
    "questions",
    "question_languages",
    "test_cases",
    "submissions",
]
USER_INS = "INSERT INTO users(username,email,password_hash) VALUES(%s,%s,%s)"


def s(v):
    """information_schema sometimes returns bytes; normalise to str."""
    return v.decode() if isinstance(v, (bytes, bytearray)) else v


def connect(user, password, ssl=True, autocommit=False):
    cfg = dict(BASE, user=user, password=password, autocommit=autocommit)
    if ssl:
        cfg.update(SSL)
    else:
        cfg["ssl_disabled"] = True
    return mysql.connector.connect(**cfg)


def admin_conn(autocommit=True):
    return connect(*ADMIN, autocommit=autocommit)


# ----------------------------------------------------------------------
# Committed fixtures (needed so OTHER accounts can see rows) + cleanup
# ----------------------------------------------------------------------
def sweep():
    """Delete every row this suite ever created (prefix zt_)."""
    like = P.replace("_", "\\_") + "%"
    conn = admin_conn()
    cur = conn.cursor()
    for sql in [
        "DELETE FROM submissions WHERE user_id IN (SELECT user_id FROM users WHERE username LIKE %s)",
        "DELETE FROM submissions WHERE question_id IN (SELECT question_id FROM questions WHERE title LIKE %s)",
        "DELETE FROM test_cases WHERE question_id IN (SELECT question_id FROM questions WHERE title LIKE %s)",
        "DELETE FROM question_languages WHERE question_id IN (SELECT question_id FROM questions WHERE title LIKE %s)",
        "DELETE FROM questions WHERE title LIKE %s",
        "DELETE FROM categories WHERE cat_name LIKE %s",
        "DELETE FROM languages WHERE name LIKE %s",
        "DELETE FROM users WHERE username LIKE %s",
    ]:
        cur.execute(sql, (like,))
    cur.close()
    conn.close()


class Fixture:
    def create(self):
        tag = P + uuid.uuid4().hex[:12]
        self.username, self.email = tag, tag + "@example.test"
        self.code = "print('fixture')"
        conn = admin_conn()
        cur = conn.cursor()
        cur.execute(USER_INS, (self.username, self.email, "$2b$12$fixture_hash"))
        self.user_id = cur.lastrowid
        cur.execute("INSERT INTO categories(cat_name) VALUES(%s)", (tag + "c",))
        self.category_id = cur.lastrowid
        cur.execute("INSERT INTO languages(name) VALUES(%s)", (tag + "l",))
        self.language_id = cur.lastrowid
        cur.execute(
            "INSERT INTO questions(category_id,title,difficulty) VALUES(%s,%s,%s)",
            (self.category_id, tag + "q", 3),
        )
        self.question_id = cur.lastrowid
        cur.execute(
            "INSERT INTO question_languages(question_id,language_id) VALUES(%s,%s)",
            (self.question_id, self.language_id),
        )
        cur.execute(
            "INSERT INTO test_cases(question_id,input_data,expected_out,is_hidden) VALUES(%s,%s,%s,1)",
            (self.question_id, "in", "zt-secret"),
        )
        self.hidden_id = cur.lastrowid
        cur.execute(
            "INSERT INTO test_cases(question_id,input_data,expected_out,is_hidden) VALUES(%s,%s,%s,0)",
            (self.question_id, "in", "zt-public"),
        )
        self.public_id = cur.lastrowid
        cur.execute(
            "INSERT INTO submissions(question_id,user_id,language_id,code) VALUES(%s,%s,%s,%s)",
            (self.question_id, self.user_id, self.language_id, self.code),
        )
        self.submission_id = cur.lastrowid
        cur.close()
        conn.close()


FX = Fixture()


def setUpModule():
    sweep()
    FX.create()


def tearDownModule():
    sweep()


# ----------------------------------------------------------------------
# Base class (admin connection, every test rolled back)
# ----------------------------------------------------------------------
class DBCase(unittest.TestCase):
    creds = ADMIN

    def setUp(self):
        self.db = connect(*self.creds)
        self.cur = self.db.cursor(buffered=True)
        self.tag = uuid.uuid4().hex[:12]
        self.n = 0

    def tearDown(self):
        try:
            self.db.rollback()
        finally:
            self.cur.close()
            self.db.close()

    # -- helpers -------------------------------------------------------
    def sql(self, q, p=()):
        self.cur.execute(q, p)
        return self.cur.fetchall() if self.cur.with_rows else None

    def info(self, q, p=()):
        return [tuple(s(c) for c in r) for r in self.sql(q, p)]

    def scalar(self, q, p=()):
        return self.sql(q, p)[0][0]

    def expect_error(self, codes, q, p=()):
        """Statement must fail with one of the given MySQL error numbers."""
        codes = {codes} if isinstance(codes, int) else set(codes)
        self.sql("SAVEPOINT sp")
        with self.assertRaises(Error) as ctx:
            self.sql(q, p)
        self.assertIn(
            ctx.exception.errno,
            codes,
            f"wrong error {ctx.exception.errno} ({ctx.exception.msg}); wanted {sorted(codes)}",
        )
        try:
            self.sql("ROLLBACK TO SAVEPOINT sp")
        except Error:
            self.db.rollback()

    def denied(self, q, p=()):
        self.expect_error(DENIED, q, p)

    def name(self, kind=""):
        self.n += 1
        return f"{P}{self.tag}{kind}{self.n}"

    def user(self, username=None, email=None):
        username = username or self.name("u")
        self.sql(
            USER_INS,
            (username, email or username + "@example.test", "$2b$12$test_hash"),
        )
        return self.cur.lastrowid

    def category(self):
        self.sql("INSERT INTO categories(cat_name) VALUES(%s)", (self.name("c"),))
        return self.cur.lastrowid

    def language(self):
        self.sql("INSERT INTO languages(name) VALUES(%s)", (self.name("l"),))
        return self.cur.lastrowid

    def question(self, difficulty=3):
        self.sql(
            "INSERT INTO questions(category_id,title,difficulty) VALUES(%s,%s,%s)",
            (self.category(), self.name("q"), difficulty),
        )
        return self.cur.lastrowid

    def submission(self):
        uid, qid, lid = self.user(), self.question(), self.language()

        # Associate the programming language with the question
        self.sql(
            "INSERT INTO question_languages(question_id,language_id) VALUES(%s,%s)",
            (qid, lid),
        )

        # Create the submission
        self.sql(
            "INSERT INTO submissions(question_id,user_id,language_id,code) VALUES(%s,%s,%s,%s)",
            (qid, uid, lid, "print(1)"),
        )

        return self.cur.lastrowid


# ======================================================================
# 1. Schema introspection
# ======================================================================
class TestSchemaIntrospection(DBCase):
    EXPECTED_COLUMNS = {
        "users": {
            "user_id": ("int unsigned", "NO"),
            "username": ("varchar(50)", "NO"),
            "email": ("varchar(255)", "NO"),
            "password_hash": ("varchar(255)", "NO"),
            "is_admin": ("tinyint(1)", "NO"),
            "created_at": ("datetime", "NO"),
        },
        "categories": {
            "category_id": ("int unsigned", "NO"),
            "cat_name": ("varchar(100)", "NO"),
            "description": ("varchar(500)", "YES"),
        },
        "languages": {
            "language_id": ("int unsigned", "NO"),
            "name": ("varchar(50)", "NO"),
        },
        "questions": {
            "question_id": ("int unsigned", "NO"),
            "category_id": ("int unsigned", "NO"),
            "title": ("varchar(200)", "NO"),
            "description": ("text", "YES"),
            "difficulty": ("tinyint unsigned", "NO"),
        },
        "question_languages": {
            "question_id": ("int unsigned", "NO"),
            "language_id": ("int unsigned", "NO"),
        },
        "test_cases": {
            "test_case_id": ("int unsigned", "NO"),
            "question_id": ("int unsigned", "NO"),
            "input_data": ("text", "YES"),
            "expected_out": ("text", "NO"),
            "is_hidden": ("tinyint(1)", "NO"),
        },
        "submissions": {
            "submission_id": ("int unsigned", "NO"),
            "question_id": ("int unsigned", "NO"),
            "user_id": ("int unsigned", "NO"),
            "language_id": ("int unsigned", "NO"),
            "code": ("mediumtext", "NO"),
            "status": ("varchar(30)", "NO"),
            "score": ("int", "YES"),
            "feedback": ("text", "YES"),
            "submitted_at": ("datetime", "NO"),
            "graded_at": ("datetime", "YES"),
        },
    }
    EXPECTED_PK = {
        "users": "user_id",
        "categories": "category_id",
        "languages": "language_id",
        "questions": "question_id",
        "question_languages": "question_id,language_id",
        "test_cases": "test_case_id",
        "submissions": "submission_id",
    }
    EXPECTED_UNIQUE = [
        ("users", "username"),
        ("users", "email"),
        ("categories", "cat_name"),
        ("languages", "name"),
    ]
    EXPECTED_FK_DELETE = {
        "fk_questions_category": "RESTRICT",
        "fk_ql_question": "CASCADE",
        "fk_ql_language": "CASCADE",
        "fk_test_cases_question": "CASCADE",
        "fk_submissions_question": "RESTRICT",
        "fk_submissions_user": "RESTRICT",
        "fk_submissions_language": "RESTRICT",
        "fk_submissions_supported_language": "RESTRICT",
    }
    EXPECTED_CHECKS = {
        "chk_users_username_len",
        "chk_users_email_format",
        "chk_questions_difficulty",
        "chk_submissions_status",
        "chk_submissions_score",
    }

    def index_defs(self, table):
        rows = self.info(
            "SELECT INDEX_NAME, NON_UNIQUE, GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) "
            "FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s "
            "GROUP BY INDEX_NAME, NON_UNIQUE",
            (DB, table),
        )
        return [(r[0], int(r[1]), r[2]) for r in rows]

    def test_columns_types_and_nullability(self):
        rows = self.info(
            "SELECT TABLE_NAME, COLUMN_NAME, LOWER(COLUMN_TYPE), IS_NULLABLE "
            "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s",
            (DB,),
        )
        actual = {}
        for t, c, ctype, nullable in rows:
            if t in self.EXPECTED_COLUMNS:
                actual.setdefault(t, {})[c] = (ctype, nullable)
        for table, expected in self.EXPECTED_COLUMNS.items():
            with self.subTest(table=table):
                self.assertEqual(actual.get(table), expected)

    def test_foreign_key_delete_rules(self):
        rows = self.info(
            "SELECT CONSTRAINT_NAME, DELETE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS "
            "WHERE CONSTRAINT_SCHEMA=%s",
            (DB,),
        )
        self.assertEqual(dict(rows), self.EXPECTED_FK_DELETE)

    def test_check_constraints_exist_and_are_enforced(self):
        rows = self.info(
            "SELECT cc.CONSTRAINT_NAME, tc.ENFORCED FROM information_schema.CHECK_CONSTRAINTS cc "
            "JOIN information_schema.TABLE_CONSTRAINTS tc ON tc.CONSTRAINT_SCHEMA=cc.CONSTRAINT_SCHEMA "
            "AND tc.CONSTRAINT_NAME=cc.CONSTRAINT_NAME WHERE cc.CONSTRAINT_SCHEMA=%s",
            (DB,),
        )
        self.assertEqual({r[0] for r in rows}, self.EXPECTED_CHECKS)
        self.assertTrue(all(r[1] == "YES" for r in rows))

    def test_public_view_definition(self):
        sec = self.info(
            "SELECT SECURITY_TYPE FROM information_schema.VIEWS "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
            (DB, "v_public_test_cases"),
        )
        self.assertEqual(sec, [("DEFINER",)])
        cols = self.info(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s "
            "AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION",
            (DB, "v_public_test_cases"),
        )
        self.assertEqual(
            [c[0] for c in cols],
            ["test_case_id", "question_id", "input_data", "expected_out"],
        )


# ======================================================================
# 2. Constraint behavior (admin connection, specific error numbers)
# ======================================================================
class TestConstraints(DBCase):
    # ---- users ----

    def test_duplicate_username(self):
        u = self.name("u")
        self.user(u)
        self.expect_error(DUP, USER_INS, (u, "other_" + u + "@example.test", "h"))

    def test_duplicate_email(self):
        u = self.name("u")
        self.user(u)
        self.expect_error(DUP, USER_INS, ("other_" + u, u + "@example.test", "h"))

    def test_username_length_bounds(self):
        for value in ["", "a", "ab", "漢字", "💻🔒"]:  # <3 CHARACTERS (not bytes)
            with self.subTest(too_short=value):
                self.expect_error(
                    CHECK_FAIL,
                    USER_INS,
                    (value, uuid.uuid4().hex + "@example.test", "h"),
                )
        for value in ["abc", "漢字字", "x" * 50]:
            with self.subTest(valid=value):
                self.sql(
                    USER_INS,
                    (value + self.tag[:0], uuid.uuid4().hex + "@example.test", "h"),
                )
                self.db.rollback()
        self.expect_error(
            TOO_LONG, USER_INS, ("x" * 51, uuid.uuid4().hex + "@example.test", "h")
        )

    def test_invalid_email_shapes(self):
        for value in [
            "",
            "plainaddress",
            "missing-at.example",
            "a@b",
            "a@",
            "@example.com",
            "a@b.c",
            "a@b.",
        ]:
            with self.subTest(value=value):
                self.expect_error(CHECK_FAIL, USER_INS, (self.name("u"), value, "h"))

    # ---- categories / languages ----

    # ---- questions ----
    def test_question_difficulty_bounds(self):
        cid = self.category()
        ins = "INSERT INTO questions(category_id,title,difficulty) VALUES(%s,%s,%s)"
        for d in [0, 6, 100]:  # in TINYINT range, fail the CHECK
            with self.subTest(check=d):
                self.expect_error(CHECK_FAIL, ins, (cid, "bad", d))
        for d in [-1, 256]:  # outside TINYINT UNSIGNED range
            with self.subTest(range=d):
                self.expect_error(INVALID_DIFFICULTY, ins, (cid, "bad", d))
        self.expect_error(NULL_COL, ins, (cid, "bad", None))
        for d in [1, 2, 3, 4, 5]:
            with self.subTest(valid=d):
                self.sql(ins, (cid, "valid", d))

    # ---- question_languages ----
    def test_duplicate_question_language_pair(self):
        qid, lid = self.question(), self.language()
        self.sql(
            "INSERT INTO question_languages(question_id,language_id) VALUES(%s,%s)",
            (qid, lid),
        )
        self.expect_error(
            DUP,
            "INSERT INTO question_languages(question_id,language_id) VALUES(%s,%s)",
            (qid, lid),
        )

    # ---- test_cases ----

    def test_hidden_testcases_never_in_public_view(self):
        qid = self.question()
        self.sql(
            "INSERT INTO test_cases(question_id,expected_out,is_hidden) VALUES(%s,%s,1)",
            (qid, "secret"),
        )
        hidden = self.cur.lastrowid
        self.sql(
            "INSERT INTO test_cases(question_id,expected_out,is_hidden) VALUES(%s,%s,0)",
            (qid, "public"),
        )
        public = self.cur.lastrowid
        ids = {
            r[0]
            for r in self.sql(
                "SELECT test_case_id FROM v_public_test_cases WHERE question_id=%s",
                (qid,),
            )
        }
        self.assertEqual(ids, {public})
        # flipping the flag moves the row in/out of the view
        self.sql("UPDATE test_cases SET is_hidden=1 WHERE test_case_id=%s", (public,))
        self.assertEqual(
            self.sql(
                "SELECT COUNT(*) FROM v_public_test_cases WHERE question_id=%s", (qid,)
            )[0][0],
            0,
        )
        self.sql("UPDATE test_cases SET is_hidden=0 WHERE test_case_id=%s", (hidden,))
        self.assertEqual(
            self.sql(
                "SELECT COUNT(*) FROM v_public_test_cases WHERE question_id=%s", (qid,)
            )[0][0],
            1,
        )

    # ---- submissions ----

    def test_submission_missing_references(self):
        uid, qid, lid = self.user(), self.question(), self.language()
        for args in [
            (4294967295, uid, lid, "x"),
            (qid, 4294967295, lid, "x"),
            (qid, uid, 4294967295, "x"),
        ]:
            with self.subTest(args=args):
                self.expect_error(
                    FK_CHILD,
                    "INSERT INTO submissions(question_id,user_id,language_id,code) "
                    "VALUES(%s,%s,%s,%s)",
                    args,
                )

    def test_submission_score_bounds(self):
        sid = self.submission()
        for score in [-100, -1, 101, 100000]:
            with self.subTest(bad=score):
                self.expect_error(
                    CHECK_FAIL,
                    "UPDATE submissions SET score=%s WHERE submission_id=%s",
                    (score, sid),
                )
        for score in [None, 0, 1, 50, 99, 100]:
            with self.subTest(valid=score):
                self.sql(
                    "UPDATE submissions SET score=%s WHERE submission_id=%s",
                    (score, sid),
                )

    # ---- delete behavior ----

    def test_cascade_deletes(self):
        qid, lid = self.question(), self.language()
        self.sql(
            "INSERT INTO test_cases(question_id,expected_out) VALUES(%s,%s)", (qid, "x")
        )
        self.sql(
            "INSERT INTO question_languages(question_id,language_id) VALUES(%s,%s)",
            (qid, lid),
        )
        self.sql("DELETE FROM questions WHERE question_id=%s", (qid,))
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM test_cases WHERE question_id=%s", (qid,)),
            0,
        )
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM question_languages WHERE question_id=%s", (qid,)
            ),
            0,
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM languages WHERE language_id=%s", (lid,)),
            1,
        )  # parent kept


# ======================================================================
# 3. Known gaps: documents what the schema CURRENTLY allows.
#    When you tighten the schema, these tests will fail -> flip them.
# ======================================================================
class TestKnownGaps(DBCase):
    # A forgotten flag publishes the test case. Consider DEFAULT TRUE.

    def test_gap_email_check_is_very_loose(self):
        for value in ["a@@b.cc", "a b@c.com", "a@b..co"]:
            with self.subTest(value=value):
                self.expect_error(CHECK_FAIL, USER_INS, (self.name("u"), value, "h"))

    def test_gap_whitespace_only_username_allowed(self):
        self.expect_error(
            CHECK_FAIL, USER_INS, ("   ", self.name("e") + "@example.test", "h")
        )

        # Stored as 'PASSED' -> app code comparing to 'passed' would miss it.

    def test_gap_submission_language_need_not_be_supported_by_question(self):
        uid, qid, lid = (
            self.user(),
            self.question(),
            self.language(),
        )  # no question_languages row
        self.expect_error(
            FK_CHILD,
            "INSERT INTO submissions(question_id,user_id,language_id,code) VALUES(%s,%s,%s,%s)",
            (qid, uid, lid, "x"),
        )


# ======================================================================
# 4. Injection / encoding payloads (tests parameter binding + storage only)
# ======================================================================
PAYLOADS = [
    "' OR '1'='1",
    "' OR 1=1 -- ",
    "admin'--",
    "' UNION SELECT NULL-- ",
    "'; DROP TABLE users; -- ",
    "' AND SLEEP(2)-- ",
    '" OR "x"="x',
    "\\' OR '1'='1",
    "') OR ('1'='1",
    "' /*comment*/ OR 1=1 -- ",
    "' OR 'a'='a' #",
    "'; SELECT @@version; -- ",
    "%",
    "_",
    "%%%",
    "\\",
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "../../etc/passwd",
    "..\\..\\windows\\win.ini",
    "${jndi:ldap://invalid.example/a}",
    "\x00",
    "\n\r\t",
    "💻🔒",
    "漢字éñ",
    "a" * 1000,
]


class TestInjectionAndEncoding(DBCase):
    def test_payloads_never_match_in_username_or_email_lookups(self):
        uid = self.user()
        for payload in PAYLOADS:
            with self.subTest(payload=repr(payload[:60])):
                self.assertEqual(
                    self.sql("SELECT user_id FROM users WHERE username=%s", (payload,)),
                    [],
                )
                self.assertEqual(
                    self.sql("SELECT user_id FROM users WHERE email=%s", (payload,)), []
                )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM users WHERE user_id=%s", (uid,)), 1
        )

    def test_payloads_as_submission_code_roundtrip(self):
        uid, qid, lid = self.user(), self.question(), self.language()

        # Register the language as supported by the question
        self.sql(
            "INSERT INTO question_languages(question_id,language_id) VALUES(%s,%s)",
            (qid, lid),
        )

        for payload in PAYLOADS:
            with self.subTest(payload=repr(payload[:60])):
                self.sql(
                    "INSERT INTO submissions(question_id,user_id,language_id,code) VALUES(%s,%s,%s,%s)",
                    (qid, uid, lid, payload),
                )
                self.assertEqual(
                    self.scalar(
                        "SELECT code FROM submissions WHERE submission_id=%s",
                        (self.cur.lastrowid,),
                    ),
                    payload,
                )

    def test_parameterized_stacked_statement_is_inert(self):
        payload = "1; DROP TABLE users; --"
        self.assertEqual(self.scalar("SELECT %s", (payload,)), payload)
        self.sql("SELECT 1 FROM users LIMIT 1")


# ======================================================================
# 5. Account hygiene (admin inspects the three accounts)
# ======================================================================
class TestAccountHygiene(DBCase):
    def test_accounts_exist_with_ssl_required_and_connection_cap(self):
        for role, (user, _) in ACCOUNTS.items():
            with self.subTest(role=role):
                ddl = self.sql("SHOW CREATE USER " + account_sql(user, ACCOUNT_HOST))[
                    0
                ][-1]
                ddl = s(ddl)
                self.assertIn("REQUIRE SSL", ddl)
                self.assertIn("MAX_USER_CONNECTIONS", ddl)
                # Auth plugin can vary across MySQL 8 configurations; TLS and caps are the policy.

    def test_no_global_privileges_or_grant_option(self):
        for role, (user, _) in ACCOUNTS.items():
            with self.subTest(role=role):
                grants = [
                    s(r[0])
                    for r in self.sql(
                        "SHOW GRANTS FOR " + account_sql(user, ACCOUNT_HOST)
                    )
                ]
                self.assertTrue(grants[0].startswith("GRANT USAGE ON *.*"), grants[0])
                for g in grants:
                    self.assertNotIn("ALL PRIVILEGES", g)
                    self.assertNotIn("WITH GRANT OPTION", g)
                    if not g.startswith("GRANT USAGE ON *.*"):
                        self.assertIn(
                            f"`{DB}`.",
                            g,
                            "grant outside the application database: " + g,
                        )
                        for dangerous in (
                            "DROP",
                            "ALTER",
                            "CREATE",
                            "TRUNCATE",
                            "REFERENCES",
                            "TRIGGER",
                            "EXECUTE",
                            "INDEX",
                        ):
                            self.assertNotRegex(g, rf"\b{dangerous}\b", g)

    def test_ssl_required_for_every_account(self):
        for role, (user, pw) in ACCOUNTS.items():
            if not pw:
                continue
            with self.subTest(role=role):
                with self.assertRaises(Error) as ctx:
                    connect(user, pw, ssl=False).close()
                self.assertIn(
                    ctx.exception.errno,
                    {1045, 3159},
                    "expected TLS/authentication rejection",
                )


# ======================================================================
# 6. Per-account privilege tests
# ======================================================================
class PrivBase(DBCase):
    role = None

    @classmethod
    def setUpClass(cls):
        if cls.role is None:
            raise unittest.SkipTest("abstract")
        user, pw = ACCOUNTS[cls.role]
        if not pw:
            raise unittest.SkipTest(f"no password configured for {cls.role}")
        cls.creds = (user, pw)

    def disabled_ddl_account_and_file_operations_denied(self):
        probe = "zt_probe_" + self.tag
        for stmt in [
            f"CREATE TABLE {probe} (id INT)",
            f"ALTER TABLE languages ADD COLUMN {probe} INT",
            f"DROP TABLE IF EXISTS {probe}",
            "TRUNCATE TABLE languages",
            f"CREATE VIEW {probe} AS SELECT 1",
            f"CREATE USER '{probe}'@'%' IDENTIFIED BY 'x'",
            f"GRANT SELECT ON {DB}.users TO '{probe}'@'%'",
            "CREATE INDEX zt_idx ON languages (name)",
            "SET GLOBAL sql_mode=''",
        ]:
            with self.subTest(stmt=stmt):
                self.denied_or_privileged_var(stmt)

    def denied_or_privileged_var(self, stmt):
        # SET GLOBAL needs SUPER-type privilege: error 1227 (in DENIED); DDL gives 1142/1044.
        self.expect_error(DENIED, stmt)

    def test_cannot_read_mysql_system_tables(self):
        for stmt in ["SELECT user, host FROM mysql.user", "SELECT * FROM mysql.db"]:
            with self.subTest(stmt=stmt):
                self.denied(stmt)

    def test_session_is_strict(self):
        mode = self.scalar("SELECT @@SESSION.sql_mode")
        self.assertTrue(
            "STRICT_ALL_TABLES" in mode or "STRICT_TRANS_TABLES" in mode, mode
        )


class TestAppAccountPrivileges(PrivBase):
    role = "app"

    # ---- users ----

    def test_can_read_submission_results(self):
        self.cur.execute(
            "SELECT submission_id, user_id, question_id, language_id, "
            "status, score, feedback, submitted_at "
            "FROM submissions WHERE submission_id=%s",
            (FX.submission_id,),
        )
        row = self.cur.fetchone()
        self.assertIsNotNone(row)

    def test_cannot_set_is_admin_on_insert(self):
        self.denied(
            "INSERT INTO users(username,email,password_hash,is_admin) VALUES(%s,%s,%s,1)",
            (self.name("u"), self.name("e") + "@example.test", "h"),
        )

    def test_cannot_update_is_admin_or_other_protected_columns(self):
        for col, val in [
            ("is_admin", 1),
            ("created_at", "2000-01-01 00:00:00"),
            ("user_id", 999999),
        ]:
            with self.subTest(col=col):
                self.denied(
                    f"UPDATE users SET {col}=%s WHERE user_id=%s", (val, FX.user_id)
                )

    # ---- reference data ----

    # ---- test cases / hidden data ----
    def test_cannot_touch_test_cases_table(self):
        self.denied("SELECT * FROM test_cases")
        self.denied("SELECT expected_out FROM test_cases")
        self.denied("SELECT COUNT(*) FROM test_cases")
        self.denied(
            "INSERT INTO test_cases(question_id,expected_out) VALUES(%s,%s)",
            (FX.question_id, "x"),
        )
        self.denied(
            "UPDATE test_cases SET is_hidden=0 WHERE test_case_id=%s", (FX.hidden_id,)
        )

    def test_public_view_shows_public_and_hides_hidden(self):
        ids = {
            r[0]
            for r in self.sql(
                "SELECT test_case_id FROM v_public_test_cases WHERE question_id=%s",
                (FX.question_id,),
            )
        }
        self.assertIn(FX.public_id, ids)
        self.assertNotIn(FX.hidden_id, ids)
        outs = {
            r[0]
            for r in self.sql(
                "SELECT expected_out FROM v_public_test_cases WHERE question_id=%s",
                (FX.question_id,),
            )
        }
        self.assertNotIn("zt-secret", outs)

    # ---- submissions ----

    def test_cannot_set_status_score_or_feedback_on_insert(self):
        for col in ["status", "score", "feedback"]:
            with self.subTest(col=col):
                val = {"status": "passed", "score": 100, "feedback": "great"}[col]
                self.denied(
                    f"INSERT INTO submissions(question_id,user_id,language_id,code,{col}) VALUES(%s,%s,%s,%s,%s)",
                    (FX.question_id, FX.user_id, FX.language_id, "x", val),
                )

    def test_cannot_read_submitted_code_back(self):
        self.denied(
            "SELECT code FROM submissions WHERE submission_id=%s", (FX.submission_id,)
        )
        self.denied(
            "SELECT * FROM submissions WHERE submission_id=%s", (FX.submission_id,)
        )  # JPA findById hazard


class TestGraderAccountPrivileges(PrivBase):
    role = "grader"

    def test_can_read_all_test_cases_including_hidden(self):
        outs = {
            r[0]
            for r in self.sql(
                "SELECT expected_out FROM test_cases WHERE question_id=%s",
                (FX.question_id,),
            )
        }
        self.assertEqual(outs, {"zt-secret", "zt-public"})

    def test_can_write_grading_results(self):
        self.sql(
            "UPDATE submissions SET status=%s, score=%s, feedback=%s WHERE submission_id=%s",
            ("passed", 100, "ok", FX.submission_id),
        )

    def test_cannot_modify_code_or_identity_columns(self):
        for col, val in [
            ("code", "cheat"),
            ("user_id", FX.user_id),
            ("question_id", FX.question_id),
            ("language_id", FX.language_id),
            ("submitted_at", "2000-01-01 00:00:00"),
        ]:
            with self.subTest(col=col):
                self.denied(
                    f"UPDATE submissions SET {col}=%s WHERE submission_id=%s",
                    (val, FX.submission_id),
                )

    def test_cannot_read_users_or_other_tables(self):
        for stmt in [
            "SELECT password_hash FROM users",
            "SELECT * FROM users",
            "SELECT * FROM categories",
            "SELECT * FROM languages",
            "SELECT * FROM question_languages",
            "SELECT * FROM v_public_test_cases",
        ]:
            with self.subTest(stmt=stmt):
                self.denied(stmt)


class TestAdminAppAccountPrivileges(PrivBase):
    role = "admin_app"

    def test_can_read_users_but_never_password_hash(self):
        self.sql(
            "SELECT user_id, username, email, is_admin, created_at FROM users WHERE user_id=%s",
            (FX.user_id,),
        )
        self.denied("SELECT password_hash FROM users WHERE user_id=%s", (FX.user_id,))
        self.denied("SELECT * FROM users WHERE user_id=%s", (FX.user_id,))

    def test_submissions_are_read_only_and_code_is_hidden(self):
        self.sql(
            "SELECT submission_id, question_id, user_id, language_id, status, score, feedback, submitted_at "
            "FROM submissions WHERE submission_id=%s",
            (FX.submission_id,),
        )
        self.denied(
            "SELECT code FROM submissions WHERE submission_id=%s", (FX.submission_id,)
        )
        self.denied("SELECT * FROM submissions")
        self.denied(
            "UPDATE submissions SET score=100 WHERE submission_id=%s",
            (FX.submission_id,),
        )
        self.denied(
            "DELETE FROM submissions WHERE submission_id=%s", (FX.submission_id,)
        )
        self.denied(
            "INSERT INTO submissions(question_id,user_id,language_id,code) VALUES(%s,%s,%s,%s)",
            (FX.question_id, FX.user_id, FX.language_id, "x"),
        )


# ======================================================================
# 7. Session / server settings
# ======================================================================
class TestServerSettings(DBCase):

    def test_global_sql_mode_is_strict(self):
        mode = self.scalar("SELECT @@GLOBAL.sql_mode")
        self.assertTrue(
            "STRICT_ALL_TABLES" in mode or "STRICT_TRANS_TABLES" in mode,
            f"global sql_mode not strict: {mode} (check RDS parameter group)",
        )

    def test_require_secure_transport(self):
        self.assertEqual(
            self.scalar("SELECT @@GLOBAL.require_secure_transport"),
            1,
            "set require_secure_transport=1 in the RDS parameter group",
        )


# ======================================================================
# 8. Concurrency (separate committed connections; cleaned up afterwards)
# ======================================================================
def race(n, work):
    """Small bounded concurrent race; every successful operation commits."""
    n = min(n, int(os.getenv("RACE_WORKERS", "4")))
    if n < 2 or n > 8:
        raise ValueError("RACE_WORKERS must be 2..8")
    barrier = threading.Barrier(n)

    def run(i):
        conn = admin_conn(autocommit=True)
        try:
            cur = conn.cursor()
            try:
                barrier.wait(timeout=20)
                work(cur, i)
                return "ok"
            except Error as e:
                return e.errno
            finally:
                cur.close()
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(run, range(n)))


def account_sql(user, host):
    """Safely quote account names for SHOW CREATE USER/SHOW GRANTS syntax."""

    def quote(x):
        return "'" + x.replace("\\", "\\\\").replace("'", "''") + "'"

    return quote(user) + "@" + quote(host)


class TestConcurrency(unittest.TestCase):
    # Concurrency fixtures are removed once in tearDownModule, not after each test.
    # Removing the shared fixture here would break later privilege tests.

    def test_simultaneous_duplicate_username_only_one_wins(self):
        name = P + uuid.uuid4().hex[:12]
        results = race(
            8,
            lambda cur, i: cur.execute(
                USER_INS, (name, f"{name}_{i}@example.test", "h")
            ),
        )
        self.assertEqual(results.count("ok"), 1, results)
        self.assertEqual(results.count(DUP), len(results) - 1, results)

    def test_delete_parent_vs_insert_child_never_leaves_orphans(self):
        tag = P + uuid.uuid4().hex[:12]
        conn = admin_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO categories(cat_name) VALUES(%s)", (tag,))
        cid = cur.lastrowid
        conn.close()

        def work(c, i):
            if i == 0:
                c.execute("DELETE FROM categories WHERE category_id=%s", (cid,))
            else:
                c.execute(
                    "INSERT INTO questions(category_id,title,difficulty) VALUES(%s,%s,1)",
                    (cid, f"{tag}_{i}"),
                )

        race(6, work)
        conn = admin_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM questions q LEFT JOIN categories c ON c.category_id=q.category_id "
            "WHERE c.category_id IS NULL"
        )
        self.assertEqual(cur.fetchone()[0], 0)
        conn.close()


# ======================================================================
# 9. Additional integrity and security regression checks
# ======================================================================
class TestExtendedAdversarial(DBCase):

    def test_failed_constraint_does_not_mutate_existing_record(self):
        uid = self.user()
        before = self.sql(
            "SELECT username,email,is_admin FROM users WHERE user_id=%s", (uid,)
        )[0]
        self.expect_error(
            CHECK_FAIL,
            "UPDATE users SET username=%s,is_admin=1 WHERE user_id=%s",
            ("x", uid),
        )
        self.assertEqual(
            self.sql(
                "SELECT username,email,is_admin FROM users WHERE user_id=%s", (uid,)
            )[0],
            before,
        )

    def test_multirow_insert_rolls_back_atomically_on_duplicate(self):
        first = self.name("u")
        self.user(first)
        second = self.name("u")
        self.expect_error(
            DUP,
            "INSERT INTO users(username,email,password_hash) VALUES(%s,%s,%s),(%s,%s,%s)",
            (
                second,
                second + "@example.test",
                "h",
                first,
                "other_" + first + "@example.test",
                "h",
            ),
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM users WHERE username=%s", (second,)), 0
        )

    def test_binary_and_control_text_roundtrip(self):
        qid = self.question()
        for payload in [
            "\x00",
            "\x01\x02\x7f",
            "\r\n\t",
            "x\u202ey",
            "👩🏽‍💻",
            "a\u0301",
            "a\\b",
            "💻" * 1000,
        ]:
            with self.subTest(payload=repr(payload[:24])):
                self.sql(
                    "INSERT INTO test_cases(question_id,input_data,expected_out) VALUES(%s,%s,%s)",
                    (qid, payload, payload),
                )
                tid = self.cur.lastrowid
                self.assertEqual(
                    self.sql(
                        "SELECT input_data,expected_out FROM test_cases WHERE test_case_id=%s",
                        (tid,),
                    )[0],
                    (payload, payload),
                )

    def test_parameterized_payloads_cannot_change_admin_flag(self):
        uid = self.user()
        for payload in [
            "' OR 1=1 -- ",
            "1; UPDATE users SET is_admin=1",
            "' UNION SELECT password_hash FROM users -- ",
        ]:
            with self.subTest(payload=payload):
                self.assertEqual(
                    self.sql("SELECT user_id FROM users WHERE username=%s", (payload,)),
                    [],
                )
                self.assertEqual(
                    self.scalar("SELECT is_admin FROM users WHERE user_id=%s", (uid,)),
                    0,
                )


class TestUnicodeIdentity(DBCase):
    """Validate actual collation and consistent identity lookups, not guessed locale rules."""

    def test_unicode_equivalence_and_identity_lookup(self):
        pairs = [
            ("Istanbul", "İstanbul"),
            ("Istanbul", "ıstanbul"),
            ("strasse", "straße"),
            ("sigmaΣ", "sigmaς"),
            ("café", "cafe\u0301"),
            ("ADMIN", "ＡＤＭＩＮ"),
            ("admin", "ad\u200bmin"),
        ]
        for index, (a, b) in enumerate(pairs):
            with self.subTest(first=a, second=b):
                # Keep each pair isolated; usernames may collide across Unicode forms.
                self.sql("SAVEPOINT unicode_pair")
                try:
                    left, right = f"{P}{self.tag}{index}{a}", f"{P}{self.tag}{index}{b}"
                    self.sql(USER_INS, (left, self.name("e") + "@example.test", "h"))
                    uid = self.cur.lastrowid
                    equivalent = bool(self.scalar("SELECT %s = %s", (left, right)))
                    if equivalent:
                        self.expect_error(
                            DUP,
                            USER_INS,
                            (right, self.name("e") + "@example.test", "h"),
                        )
                        self.assertEqual(
                            self.scalar(
                                "SELECT user_id FROM users WHERE username=%s", (right,)
                            ),
                            uid,
                        )
                    else:
                        self.sql(
                            USER_INS, (right, self.name("e") + "@example.test", "h")
                        )
                        self.assertNotEqual(self.cur.lastrowid, uid)
                finally:
                    self.sql("ROLLBACK TO SAVEPOINT unicode_pair")

    def test_zero_width_and_control_character_roundtrip(self):
        qid = self.question()
        values = ["ad\u200bmin", "a\u00a0b", "abc\u202eXYZ", "x\x00y", "👨\u200d💻"]
        for value in values:
            with self.subTest(value=repr(value)):
                self.sql(
                    "INSERT INTO test_cases(question_id,input_data,expected_out) VALUES(%s,%s,%s)",
                    (qid, value, value),
                )
                self.assertEqual(
                    self.scalar(
                        "SELECT expected_out FROM test_cases WHERE test_case_id=%s",
                        (self.cur.lastrowid,),
                    ),
                    value,
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
