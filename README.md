# AviAI Backend

Local LLM + STT + TTS pipeline for cognitive interview simulation.

## Quick Start with Docker

### 1. Prerequisites
- Docker & Docker Compose
- Ollama installed on host machine

### 2. Setup Ollama (on host)
```bash
# Install Ollama: https://ollama.ai
ollama pull gemma3

# Start Ollama with binding to all interfaces (required for Docker access)
OLLAMA_HOST=0.0.0.0 ollama serve
```
> **Note**: Ollama must bind to `0.0.0.0` so Docker can connect via `host.docker.internal`.

### 3. Create `.env` file
```env
DB_USER=postgres
DB_PASSWORD=your_password
DB_NAME=aviai_db
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256

OLLAMA_MODEL_URL=http://localhost:11434
OLLAMA_MODEL_NAME=gemma3

RECORDING_DB_URL=/recordings
```

### 4. Run
```bash
docker-compose up --build
```

API available at: http://localhost:8000/docs

### Docker Commands
```bash
# Start Ollama on host (required before running Docker)
OLLAMA_HOST=0.0.0.0 ollama serve

# Build and run
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop
docker-compose down

# Reset database (delete volume)
docker-compose down -v
```

---

## Local Development (Alternative)

### 1. Prerequisites
- Python 3.12+
- PostgreSQL 16+
- Ollama

### 2. Install uv
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: brew install uv (macOS)
```

### 3. Setup Python environment
```bash
uv python install 3.12
uv venv --python 3.12 .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv sync
```

### 4. Download NLTK data
```bash
python -c "import nltk; nltk.download('punkt_tab')"
```

### 5. Setup PostgreSQL
```sql
CREATE DATABASE aviai;
```

### 6. Create `.env` file
```env
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=aviai
SECRET_KEY=your_secret_key
ALGORITHM=algroithm
OLLAMA_MODEL_URL=url
```

### 7. Run migrations
```bash
alembic upgrade head
```

### 8. Start server
```bash
cd src
uvicorn main:app --reload --port 8000
```

---

## Database Migrations

```bash
# Apply existing migrations
alembic upgrade head

# Create new migration after model changes
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

---

## Project Structure

```
.
├── src/
│   ├── main.py              # FastAPI app
│   ├── account/             # Account management
│   ├── auth/                # Authentication (JWT)
│   ├── agent/               # LLM agent & sessions
│   ├── scenario/            # Interview scenarios
│   ├── note/                # Notes management
│   ├── handlers/            # Document & analysis handlers
│   └── database/            # DB config & models
├── alembic/                 # Database migrations
├── recordings/              # Session recordings (mounted volume)
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/v1/auth` | Authentication (login, register) |
| `/api/v1/account` | Account management |
| `/api/v1/scenario` | Interview scenarios |
| `/api/v1/session` | Interview sessions |
| `/api/v1/conversation` | Conversation history |
| `/api/v1/note` | Notes |
| `/api/v1/document` | Document processing |
| `/api/v1/analysis` | Conversation analysis |
| `/api/v1/recording` | Recording upload |
| `/recordings/*` | Static recording files |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_USER` | PostgreSQL username | - |
| `DB_PASSWORD` | PostgreSQL password | - |
| `DB_HOST` | Database host | `localhost` |
| `DB_PORT` | Database port | `5432` |
| `DB_NAME` | Database name | - |
| `SECRET_KEY` | JWT secret key | - |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `OLLAMA_MODEL_URL` | Ollama API URL | `http://localhost:11434` |
| `OLLAMA_MODEL_NAME` | Ollama model name | `gemma3` |
| `RECORDING_DB_URL` | Path to store recordings | `/recordings` |
