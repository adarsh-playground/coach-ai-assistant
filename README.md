# coach-ai-assistant
Coaches can query for athletes in plain english eg. give me clients with gpa greater than 3.5 who are from illinois, play football as linebacker.

# setup
Environment variables
export GEMINI_API_KEY=<your geminiapi key>

export DB_USER=<dbuser>
export DB_PASSWORD=<db password>
export DB_HOST=<db host>
export DB_PORT=<db port>
export DB_NAME=<db name>

# run backend
uvicorn main:app --reload --port 8000  

# run frontend
npm start
