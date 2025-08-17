import socketio
from fastapi import FastAPI
from dotenv import load_dotenv
import os
import uvicorn
import asyncio # Needed for asyncio.to_thread

# Import database functions and schema description
from database import execute_sql_query, DB_SCHEMA_DESCRIPTION, engine #, get_db_schema_for_gemini

# Import Gemini service functions
from gemini_service import initialize_gemini_model, get_gemini_sql_response, get_gemini_chat_response # <--- NEW IMPORT

# Import Validators
from validators import ValidationRule, ForbiddenKeywordsRule, \
                       OnlySelectStatementsRule, WhitelistedTablesRule, \
                       RuleExecutor

# Load environment variables from .env file
load_dotenv()

# Configure Google Gemini API (moved to gemini_service, but get key here)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # Ensure this matches your .env key name
gemini_initialized_successfully = initialize_gemini_model(GEMINI_API_KEY) # Initialize Gemini model

# Initialize Socket.IO AsyncServer
# This will be the SOLE component handling CORS headers for Socket.IO traffic.
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*") # <--- ONLY CORS SETTING

app = FastAPI()

# Mount Socket.IO at /socket.io endpoint
app.mount("/socket.io", socketio.ASGIApp(sio))

# --- Socket.IO Event Handlers ---

@sio.on("connect")
async def connect(sid, environ, auth):
    print(f"Client connected: {sid}")
    # Initial status message
    status_content = "Connected to AI SQL Genie."
    if not gemini_initialized_successfully:
        status_content += " Warning: Gemini API Key not set or model failed to initialize. AI functions will not work."
    if not engine: # Assuming 'engine' is from database.py for DB connection status
        status_content += " Error: Database connection not established."
    else:
        status_content += " Type '/sql your question' for database queries."

    await sio.emit("status", {"content": status_content}, room=sid)

@sio.on("disconnect")
async def disconnect(sid):
    print(f"Client disconnected: {sid}")

@sio.on("client_message")
async def handle_client_message(sid, message):
    print(f"Received message from {sid}: {message}")
    user_message_lower = message.lower().strip() # Process message once

    # SQL command handling (Call Gemini for SQL generation and then execute)
    if user_message_lower.startswith("/sql"):
        user_question = message[4:].strip() # Get the natural language question after "/sql"
        print(f"User asking SQL question: '{user_question}'")

        if not engine:
            await sio.emit("error", {"content": "Database not connected. Cannot execute SQL."}, room=sid)
            return
        # Removed explicit model check here as get_gemini_sql_response handles it
        # and gemini_initialized_successfully covers initial state.

        try:
            # 1. Generate SQL query using Gemini based on schema
            generated_sql = await get_gemini_sql_response(user_question, DB_SCHEMA_DESCRIPTION)

            rules = [
              ForbiddenKeywordsRule(),
              OnlySelectStatementsRule(),
              WhitelistedTablesRule(allowed_tables=["client_academic_data", "client_info_view", "client_positions", "positions"]),
            ]
            validator = RuleExecutor(rules)
            is_valid, message = validator.execute_rules(generated_sql)

            if not is_valid:
                await sio.emit("error", {"content": "Dangerous SQL. Cannot execute SQL." + message}, room=sid)
                return

            # 2. Execute the generated SQL query against the database
            # execute_sql_query is synchronous, so run it in a thread pool to not block ASGI event loop
            db_results = await asyncio.to_thread(execute_sql_query, generated_sql)

            # 3. Format and send results back
            if "columns" in db_results and "rows" in db_results:
                response_content = f"SQL Query: `{generated_sql}`\n\nResults:\n"
                if db_results["rows"]:
                    headers = " | ".join(db_results["columns"])
                    # Ensure all values are strings for join
                    rows_str = "\n".join([" | ".join(map(str, row)) for row in db_results["rows"]])
                    response_content += f"```\n{headers}\n{'-' * len(headers)}\n{rows_str}\n```"
                else:
                    response_content += "No rows returned."
            else:
                # Handle case where execute_sql_query might return a message (e.g., for DDL/DML without results)
                response_content = f"SQL Query: `{generated_sql}`\n\nMessage: {db_results.get('message', 'Query executed, no specific result data.')}"

            await sio.emit("sql_result", {"content": response_content}, room=sid)

        except ValueError as ve: # Catch errors from Gemini generation or db.py
            print(f"Application error: {ve}")
            await sio.emit("error", {"content": f"Error: {ve}"}, room=sid)
        except Exception as e: # Catch any unexpected errors during SQL processing
            print(f"Unhandled error during SQL processing: {e}")
            await sio.emit("error", {"content": f"An unexpected error occurred during SQL processing: {e}"}, room=sid)

    # AI command handling (for general AI questions)
    elif user_message_lower.startswith("/ai"):
        ai_prompt = message[3:].strip() # Get the prompt after "/ai"
        print(f"Sending to Gemini for general AI: {ai_prompt}")
        gemini_response_text = await get_gemini_chat_response(ai_prompt)
        # get_gemini_chat_response now returns an error string if model is not available
        if "Sorry, Gemini model is not available" in gemini_response_text:
             await sio.emit("error", {"content": gemini_response_text}, room=sid)
        else:
            await sio.emit("chat", {"content": f"AI: {gemini_response_text}"}, room=sid)

    # Default chat handling (if no specific prefixes are used, send to Gemini for general chat)
    else:
        print(f"Sending general chat to Gemini: {message}")
        gemini_response_text = await get_gemini_chat_response(message)
        # get_gemini_chat_response now returns an error string if model is not available
        if "Sorry, Gemini model is not available" in gemini_response_text:
             await sio.emit("error", {"content": gemini_response_text}, room=sid)
        else:
            await sio.emit("chat", {"content": f"AI: {gemini_response_text}"}, room=sid)

# --- FastAPI Routes (for health checks or other REST API endpoints) ---
@app.get("/")
async def read_root():
    return {"message": "Welcome to the AI SQL Genie Backend! Socket.IO is available at /socket.io"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Backend is running!"}

# This block is for direct execution of main.py, typically not needed with uvicorn main:app
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)