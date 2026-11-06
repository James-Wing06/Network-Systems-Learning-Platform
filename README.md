# Network-Systems-Learning-Platform (NSLP)

## Project Overview

The Networking Systems Learning Platform is a web application designed to help users practice networking-related programming problems. Questions are organized by category and difficulty, and users submit code that is evaluated against predefined test cases.

The platform supports user registration, problem management, code submissions, automated grading, and performance tracking.

## Database Overview
The project uses **MySQL 8.4**, hosted on **Amazon Web Services (AWS RDS)**.

The database contains the following tables:
-**users** — Stores user accounts, authentication information, and administrator status.
-**categories** — Stores networking problem categories.
-**languages** — Stores supported programming languages.
-**questions** — Stores programming problems, descriptions, and difficulty levels.
-**question_languages** — Associates questions with their supported programming languages.
-**test_cases** — TODO FINISH README
