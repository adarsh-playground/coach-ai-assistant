import os
from sqlalchemy import create_engine, inspect, text
from urllib.parse import quote_plus # Used for URL encoding password if needed

# --- Database Configuration for SQL Server (using pyodbc) ---
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "1433") # Default SQL Server port
DB_NAME = os.getenv("DB_NAME")

# List of specific table names to include in the schema for Gemini.
# These names MUST exactly match the table names in your SQL Server database (case-sensitive if your collation is).
# Adjust this list based on the tables you want Gemini to access.
TABLES_TO_INCLUDE = [
    "client",
    "person",
    "person_address",
    "address",
    "client_academic_data",
    "client_sport",
    "sport",
    "client_positions",
    "positions",
    "state"
    # Add all other table names that Gemini needs to know about for your queries
]
# If you leave this list empty, or comment it out, the system will try to load ALL tables it can find.

# --- ODBC Driver Configuration ---
# IMPORTANT: This must match the name of the ODBC driver installed on your system.
# On macOS after `brew install msodbcsql18`, it's typically 'ODBC Driver 18 for SQL Server'.
ODBC_DRIVER_NAME = "ODBC Driver 18 for SQL Server"

# Initialize engine to None; it will be set if connection is successful
engine = None

DB_SCHEMA_DESCRIPTION = """
Table: client_info_view (
    client_id INT,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    sport VARCHAR(255),
    gender VARCHAR(20),
    primary_phone VARCHAR(255)
    email_primary VARCHAR(255)
    birth_date DATE,
    graduation_year INT,
    city VARCHAR(100),
    state_code VARCHAR(20),
    zip VARCHAR(20),
    high_school_name VARCHAR(255)
    country VARCHAR(100)
)
Table: client_academic_data (client_id INT, overall_gpa float, act_score int, sat_score int, sat_reading int, sat_math int, sat_writing int)
Relationship: client_academic_data.client_id references client_info_view.client_id
Table: client_positions (client_position_id INT, client_id INT, position_id INT, description TEXT)
Relationship: client_positions.client_id references client_info_view.client_id
Table: positions (id INT, name VARCHAR(100))
Relationship: client_positions.position_id references positions.id
"""
# Table: client_sport (client_sport_id INT, client_id INT, sport_id INT)
# Relationship: client_sport.client_id references client_info_view.client_id

# Check if all critical DB environment variables are set
if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    print("CRITICAL ERROR: SQL Server database connection environment variables not fully set in backend/database.py.")
    print("Please set DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, and DB_NAME.")
    DB_SCHEMA_DESCRIPTION = "Database connection environment variables missing."
else:
    # Encode password to handle special characters if present in the password
    encoded_password = quote_plus(DB_PASSWORD)

    # SQLAlchemy URL for pyodbc: 'mssql+pyodbc:///?odbc_connect=...'
    # Incorporate TrustServerCertificate=yes to handle SSL certificate issues in dev/test
    DATABASE_URL = (
        f"mssql+pyodbc:///?odbc_connect="
        f"DRIVER={{{ODBC_DRIVER_NAME}}};" # Double braces to escape for f-string
        f"SERVER={DB_HOST},{DB_PORT};"
        f"DATABASE={DB_NAME};"
        f"UID={DB_USER};"
        f"PWD={encoded_password};"
        f"TrustServerCertificate=yes" # <--- This is the crucial line for SSL issues
    )

    print(f"Attempting to connect to SQL Server with pyodbc. Host: '{DB_HOST}', DB: '{DB_NAME}'")

    try:
        # Create the SQLAlchemy engine
        engine = create_engine(DATABASE_URL)

        # Test the connection immediately
        with engine.connect() as connection:
            # You can execute a simple query to further confirm connection if needed, e.g.,
            # connection.execute(text("SELECT 1"))
            print("Successfully connected to the SQL Server database for initial schema inspection.")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not connect to the database. Please check your DATABASE_URL, "
              f"pyodbc installation, ODBC driver, and SQL Server credentials/network access. Error: {e}")
        engine = None
        DB_SCHEMA_DESCRIPTION = f"Database connection failed: {e}"

# --- Helper function to execute SQL queries ---
def execute_sql_query(sql_query: str):
    if not engine:
        raise ValueError("Database connection not established. Cannot execute query.")

    with engine.connect() as connection:
        try:
            # Use text() to safely execute raw SQL
            result = connection.execute(text(sql_query))

            # Commit changes for non-SELECT queries
            if not sql_query.strip().lower().startswith("select"):
                connection.commit()
                return {"message": f"Query executed successfully. Rows affected: {result.rowcount}"}
            else:
                # Fetch results for SELECT queries
                columns = result.keys()
                rows = result.fetchall()
                formatted_rows = [list(row) for row in rows] # Convert Row objects to lists
                return {"columns": list(columns), "rows": formatted_rows}
        except Exception as e:
            # Rollback in case of an error for non-SELECT queries
            if not sql_query.strip().lower().startswith("select"):
                connection.rollback()
            raise ValueError(f"Database error executing query: {e}. Query was: '{sql_query}'")
