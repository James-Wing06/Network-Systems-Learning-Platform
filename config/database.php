// Connect to the database 

<?php
    // Find server address
    $socket="change later"; // Also we can use host+port to enter
    // Which database 
    $databasename="change later";
    // Mysql username
    $username="change later";
    // Mysql password
    $password="change later";

try {
    $pdo = new PDO (
        // Data source name 
        "mysql:unix_socket=$socket;port=3306;dbname=$databasename;charset=utf8mb4",
        $username,
        $password,
        [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false
        ]
    );

    return $pdo;
} catch( PDOException $e) {
    die($e->getMessage());
    throw new RuntimeException("Database connection failed");
}
