# Todo App Backend

Backend API for the Todo application with PostgreSQL database.

## Features
- RESTful API endpoints for todo management
- CRUD operations for todos
- Data persistence with PostgreSQL

## Prerequisites
- Python 3.8+
- PostgreSQL database

## Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/MaxPeng324/todo-backend.git
   cd todo-backend
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` file and set your database credentials:
   ```
   DB_HOST=localhost
   DB_NAME=todo_app
   DB_USER=your_username
   DB_PASSWORD=your_password
   ```

5. Initialize the database:
   ```bash
   python init_db.py
   ```

6. Run the application:
   ```bash
   python app.py
   ```

The backend will be running on `http://localhost:5000`

## API Endpoints

- `GET /api/todos` - Get all todos
- `POST /api/todos` - Create a new todo
- `PUT /api/todos/<id>` - Update a todo
- `DELETE /api/todos/<id>` - Delete a todo
- `GET /` - Health check

## Environment Variables

- `DB_HOST`: Database host (default: localhost)
- `DB_NAME`: Database name (default: todo_app)
- `DB_USER`: Database user (default: postgres)
- `DB_PASSWORD`: Database password (default: password)

## Frontend Integration

To connect with the frontend Todo app, ensure the `API_BASE_URL` in the frontend's `app.js` points to your backend server.

By default, the frontend expects the backend to be running on `http://localhost:5000/api`.