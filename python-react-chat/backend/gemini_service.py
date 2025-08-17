# backend/gemini_service.py
import os
import google.generativeai as genai
import asyncio

# Global variable to hold the initialized Gemini model instance
_gemini_model = None
# Global chat sessions for different interaction types
_gemini_chat_sql_session = None
_gemini_chat_general_session = None

def initialize_gemini_model(api_key: str):
    """
    Initializes the Google Gemini model and creates chat sessions.
    This function should be called only once at application startup.
    """
    global _gemini_model, _gemini_chat_sql_session, _gemini_chat_general_session

    if _gemini_model is not None:
        print("Gemini model already initialized. Skipping re-initialization.")
        return True # Already initialized

    if not api_key:
        print("CRITICAL ERROR: GOOGLE_API_KEY not provided. Gemini functions will not work.")
        _gemini_model = None
        return False # Indicate failure

    try:
        genai.configure(api_key=api_key)
        _gemini_model = genai.GenerativeModel('models/gemini-1.5-flash')
        print("Gemini model initialized successfully using models/gemini-1.5-flash.")

        # Initialize chat sessions
        # SQL Session: Start with specific instructions
        _gemini_chat_sql_session = _gemini_model.start_chat(history=[
            {"role": "user", "parts": "You are a SQL expert for a MS SQL Server database. Convert natural language to SQL queries. Only use tables and columns explicitly mentioned in the provided schema. Do not make up names. Ensure correct SQL Server syntax. When given a schema, acknowledge it. When asked a question, provide *only* the SQL query."},
            {"role": "model", "parts": "Acknowledged. I will provide SQL queries as requested. Please provide the database schema when ready."}
        ])
        print("Gemini SQL chat session initialized.")

        # General Chat Session: You can add an initial system persona here if desired
        _gemini_chat_general_session = _gemini_model.start_chat(history=[
            {"role": "user", "parts": "You are a helpful AI assistant. Answer general questions concisely and clearly."},
            {"role": "model", "parts": "I understand. How can I help you today?"}
        ])
        print("Gemini general chat session initialized.")

        return True
    except Exception as e:
        print(f"Error initializing Gemini model or chat sessions: {e}")
        _gemini_model = None
        _gemini_chat_sql_session = None
        _gemini_chat_general_session = None
        return False # Indicate failure

async def get_gemini_sql_response(user_question: str, db_schema: str):
    """
    Uses Gemini to generate a SQL query based on user's natural language question and DB schema.
    This uses the SQL chat session to maintain context for SQL-specific questions.
    """
    if _gemini_chat_sql_session is None:
        raise ValueError("Gemini SQL chat session not available. Ensure model was initialized.")

    # The SQL prompt needs to include the schema with each question,
    # as the schema itself is external context, not part of the 'chat' history for the AI.
    # The session history will handle remembering previous SQL questions/responses.
    prompt_for_sql_generation = f"""
    Database schema:
    {db_schema}

    User's question: {user_question}

    SQL Query:
    """
    try:
        # Send the schema and current question to the SQL session
        response = await _gemini_chat_sql_session.send_message_async(prompt_for_sql_generation)
        sql_query = response.text.strip()
        # Clean up markdown
        if sql_query.lower().startswith("```sql") and sql_query.lower().endswith("```"):
            sql_query = sql_query[len("```sql"): -len("```")].strip()
        elif sql_query.lower().startswith("```") and sql_query.lower().endswith("```"):
            sql_query = sql_query[len("```"): -len("```")].strip()

        print(f"Generated SQL Query: {sql_query}")
        return sql_query
    except Exception as e:
        print(f"Error generating SQL query with Gemini: {e}")
        # It's good practice to provide an informative message to the user
        raise ValueError(f"Could not generate SQL query: {e}. Please try rephrasing your question or check Gemini API setup.")


async def get_gemini_chat_response(user_message: str):
    """
    Uses Gemini to generate a response for a regular chat message, maintaining general conversation context.
    """
    if _gemini_chat_general_session is None:
        return "Sorry, Gemini model is not available for chat. Ensure it was initialized."

    try:
        # Send the user's message to the general chat session
        response = await _gemini_chat_general_session.send_message_async(user_message)
        return response.text.strip()
    except Exception as e:
        print(f"Error generating chat response with Gemini: {e}")
        return "Sorry, I'm having trouble processing that right now. Please try again later."
