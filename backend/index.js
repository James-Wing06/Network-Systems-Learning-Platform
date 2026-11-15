// Import the MySQL database driver module  
let mysql = require("mysql2");


// Creating a MySQL database connection object(Connection)
let connection = mysql.createConnection({
    host: "Unknown",
    port: 3306,
    user: "Unknown",
    password:"Unknown",
    database:"Unknown"
});

// Begin to connect to database 
// (err) => {} is a Callback Function
connection.connect((err) => {
    if(err) {
        console.error("Failed to connect: " + err.stack);
        return;
    }else{
        console.log("Connected Successfully");
    }
});

// After connection. We need to use query to allow SQL queries.
connection.query(
    "SELECT question_id, title, difficulty FROM questions",
    (err, result) => {
    if(err) {
        console.error("Query Error" + err.message);
        return;
    }
    console.log(result);
});


connection.end(); 