### Installation

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh
# or on macOS: brew install uv
# or on Windows: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install dependencies using uv (recommended)
uv sync

# Activate the virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Download NLTK data (for sentence tokenization)
python -c "import nltk; nltk.download('punkt_tab')"
```

#### Install and Setup Ollama

```bash
# Install and start Ollama
# Follow instructions at https://ollama.ai
ollama pull gemma3  # or any other model you prefer
```

```bash
python -m ensurepip --upgrade --default-pip
```

### Usage

#### Basic Usage
```bash
python app.py
```


4. **Install PostgreSQL and Create Database:**
   - Download and install PostgreSQL from the official website: [https://www.postgresql.org/download/](https://www.postgresql.org/download/)
   - After installation, open the PostgreSQL shell (psql) and run:
     ```sql
     CREATE DATABASE aviai;
     ```
   - Make sure to remember your PostgreSQL username and password for later configuration.

5. **Set up environment variables:**
   - Create a `.env` file in the root directory of the project
   - Add the following environment variables with your database credentials:
     ```env
      DB_USER=postgres
      DB_PASSWORD=123456789
      DB_HOST=localhost
      DB_PORT=5432
      DB_NAME=aviai
     ```
   - Replace `username`, `password`, and other values with your actual database credentials and configuration

## Database Migration (Alembic)

### 1. First-Time Alembic Setup 
If you are setting up Alembic for the very first time in a new project (no `migrations/` folder exists):

1. **Initialize Alembic:**
   ```bash
   alembic init migrations
   ```
2. **Configure Alembic:**
   - Edit `alembic.ini` and set the `sqlalchemy.url` to match your database connection string from the `.env` file, or ensure your config system is set up to read from environment variables.
   - In `migrations/env.py`, import your Base metadata (e.g., from `app.database.config import Base`) and set `target_metadata = Base.metadata`.
   - Import all model modules in `migrations/env.py` (e.g., `from app.database import models`) to ensure Alembic can detect all models for autogeneration.
3. **Generate the initial migration:**
   ```bash
   alembic revision --autogenerate -m "Initial migration"
   ```
4. **Apply the initial migration:**
   ```bash
   alembic upgrade head
   ```

---

### 2. Applying Migrations with an Existing `migrations/` Folder
If the `migrations/` folder is already present:

1. **Ensure your `.env` file is properly configured** with your database credentials.
2. **Run Alembic migrations to create all tables:**
   ```bash
   alembic upgrade head
   ```
   This will apply all migrations to your database using your credentials from the `.env` file.

**Note:**
- You do **not** need to run `alembic init` if the `migrations/` folder is already present.
- If you encounter errors, check your database credentials in the `.env` file and ensure your database is running.

---

### 3. Regular Migration Workflow (For Ongoing Development)
To update your database schema after making changes to your models:

1. **Generate a new migration script:**
   ```bash
   alembic revision --autogenerate -m "Describe your migration, e.g. Add character_name to usecase"
   ```
   This will create a new migration file in the `migrations/versions/` directory.
2. **Review the migration script:**
   Open the generated file in `migrations/versions/` and ensure the changes are correct.
3. **Apply the migration to your database:**
   ```bash
   alembic upgrade head
   ```
   This will apply all pending migrations to your database.
