
<?php

// Connect to the database

// Find server address
$socket = "change later";

// Database name
$databasename = "change later";

// MySQL username
$username = "change later";

// MySQL password
$password = "change later";

try {
    $pdo = new PDO(
        "mysql:unix_socket=$socket;dbname=$databasename;charset=utf8mb4",
        $username,
        $password,
        [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES => false
        ]
    );

    return $pdo;
} catch (PDOException $e) {
    error_log($e->getMessage());
    throw new RuntimeException("Database connection failed", 0, $e);
}
