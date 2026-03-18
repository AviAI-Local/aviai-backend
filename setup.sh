#!/usr/bin/env bash
# setup-aviai.sh
# Checks and prepares the environment for the Aviai project
# Supports macOS (brew) + common Linux (apt/dnf/pacman)

set -u   # treat unset variables as error
# set -e intentionally disabled so the script runs to completion even on errors

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'  # No Color

echo -e "${CYAN}=== Aviai project setup checker / installer helper ===${NC}"
echo "Current time: $(date)"
echo ""

# ────────────────────────────────────────────────
# 1. Git
# ────────────────────────────────────────────────
echo -e "${YELLOW}1. Checking Git ...${NC}"
if command -v git >/dev/null 2>&1; then
    GIT_VERSION=$(git --version | awk '{print $3}')
    echo -e "${GREEN}✓ git ${GIT_VERSION} found${NC}"
else
    echo -e "${YELLOW}git not found → installing ...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]] && command -v brew >/dev/null 2>&1; then
        brew install git
    elif command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update -q && sudo apt-get install -y git
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y git
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -S --noconfirm git
    else
        echo -e "${RED}✗ Could not install git automatically${NC}"
        echo "Please install git manually: https://git-scm.com/downloads"
        exit 1
    fi

    if ! command -v git >/dev/null 2>&1; then
        echo -e "${RED}Failed to install git${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ git installed${NC}"
fi

# ────────────────────────────────────────────────
# 1b. Clone repository
# ────────────────────────────────────────────────
REPO_URL="https://github.com/AviAI-Local/aviai-backend.git"
REPO_DIR="aviai-backend"

echo -e "${YELLOW}1b. Checking repository ...${NC}"
if [ -d "${REPO_DIR}/.git" ]; then
    echo -e "${GREEN}✓ Repository already exists at ./${REPO_DIR}${NC}"
elif [ -d ".git" ] && git remote get-url origin 2>/dev/null | grep -q "aviai-backend"; then
    echo -e "${GREEN}✓ Already inside the aviai-backend repository${NC}"
    REPO_DIR="."
else
    echo "Cloning ${REPO_URL} ..."
    git clone "${REPO_URL}" "${REPO_DIR}" && \
        echo -e "${GREEN}✓ Repository cloned to ./${REPO_DIR}${NC}" || {
        echo -e "${RED}✗ Failed to clone repository${NC}"
        echo "Check your internet connection or access to: ${REPO_URL}"
        exit 1
    }
fi

# Change into the repository directory
if [ "$REPO_DIR" != "." ]; then
    echo -e "${CYAN}Changing to ${REPO_DIR} directory ...${NC}"
    cd "$REPO_DIR"
fi

# ────────────────────────────────────────────────
# 1. Python 3.12+
# ────────────────────────────────────────────────
echo -e "${YELLOW}3. Checking Python 3.12+ ...${NC}"

PYTHON_CMD=""
if command -v python3.12 >/dev/null 2>&1; then
    PYTHON_CMD="python3.12"
elif command -v python3 >/dev/null 2>&1 && python3 --version 2>&1 | grep -q "3.12"; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1 && python --version 2>&1 | grep -q "3.12"; then
    PYTHON_CMD="python"
fi

if [ -n "$PYTHON_CMD" ]; then
    echo -e "${GREEN}✓ Found ${PYTHON_CMD} $( ${PYTHON_CMD} --version | awk '{print $2}' )${NC}"
else
    echo -e "${RED}✗ Python 3.12 not found${NC}"
    echo "Please install Python 3.12 (recommended ways):"
    echo "  macOS:      brew install python@3.12"
    echo "  Ubuntu/Debian: sudo apt update && sudo apt install python3.12 python3.12-venv"
    echo "  Fedora:     sudo dnf install python3.12"
    echo "  Or from https://www.python.org/downloads/"
    echo ""
    exit 1
fi

# ────────────────────────────────────────────────
# 4. uv (Astral)
# ────────────────────────────────────────────────
echo -e "${YELLOW}4. Checking uv ...${NC}"
if command -v uv >/dev/null 2>&1; then
    UV_VERSION=$(uv --version 2>/dev/null | head -1 || echo "unknown")
    echo -e "${GREEN}✓ uv is installed (${UV_VERSION})${NC}"
else
    echo -e "${YELLOW}uv not found → installing ...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]] && command -v brew >/dev/null 2>&1; then
        brew install uv
    else
        curl -LsSf https://astral.sh/uv/install.sh | sh
        # Add to PATH if needed (installer usually does this, but just in case)
        export PATH="$HOME/.cargo/bin:$PATH"
    fi

    if ! command -v uv >/dev/null 2>&1; then
        echo -e "${RED}Failed to install uv${NC}"
        echo "Please install manually: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
    echo -e "${GREEN}✓ uv installed${NC}"
fi

# ────────────────────────────────────────────────
# 5. PostgreSQL 16+ client tools (psql)
# ────────────────────────────────────────────────
echo -e "${YELLOW}5. Checking PostgreSQL client (psql) 16+ ...${NC}"
if command -v psql >/dev/null 2>&1; then
    PG_VERSION=$(psql --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    if [[ "${PG_VERSION%%.*}" -ge 16 ]]; then
        echo -e "${GREEN}✓ psql ${PG_VERSION} found${NC}"
    else
        echo -e "${YELLOW}Warning: psql found but version ${PG_VERSION} < 16${NC}"
        echo "Some features may require PostgreSQL 16+. Consider upgrading."
    fi
else
    echo -e "${RED}✗ psql not found${NC}"
    echo "Install PostgreSQL 16+:"
    echo "  macOS:      brew install postgresql@16"
    echo "  Ubuntu:     sudo apt install postgresql-16"
    echo "  Fedora:     sudo dnf install postgresql16"
    echo "  Arch:       sudo pacman -S postgresql"
    echo "After install, make sure 'psql' is in PATH and server is running."
    exit 1
fi

# Optional: quick check if server seems reachable (very basic)
if pg_isready -q >/dev/null 2>&1; then
    echo -e "  ${GREEN}PostgreSQL server appears to be running locally${NC}"
else
    echo -e "  ${YELLOW}PostgreSQL server not responding on localhost${NC}"
    echo "  → Start it (e.g. brew services start postgresql@16  or  sudo systemctl start postgresql)"
fi

# ────────────────────────────────────────────────
# 6. FFmpeg
# ────────────────────────────────────────────────
echo -e "${YELLOW}6. Checking FFmpeg ...${NC}"
if command -v ffmpeg >/dev/null 2>&1; then
    FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -1 | awk '{print $3}' || echo "unknown")
    echo -e "${GREEN}✓ ffmpeg ${FFMPEG_VERSION} found${NC}"
else
    echo -e "${RED}✗ ffmpeg not found${NC}"
    if [[ "$OSTYPE" == "darwin"* ]] && command -v brew >/dev/null 2>&1; then
        echo "Installing via brew ..."
        brew install ffmpeg
    else
        echo "Please install ffmpeg:"
        echo "  Ubuntu/Debian: sudo apt install ffmpeg"
        echo "  Fedora:        sudo dnf install ffmpeg"
        echo "  Arch:          sudo pacman -S ffmpeg"
        echo "  Or from https://ffmpeg.org/download.html"
        exit 1
    fi
fi

# ────────────────────────────────────────────────
# 7. Ollama
# ────────────────────────────────────────────────
echo -e "${YELLOW}7. Checking Ollama ...${NC}"
if command -v ollama >/dev/null 2>&1; then
    OLLAMA_VERSION=$(ollama -v 2>/dev/null || echo "unknown")
    echo -e "${GREEN}✓ ollama ${OLLAMA_VERSION} found${NC}"

    # Quick check if server is probably running
    if curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        echo -e "  ${GREEN}Ollama server appears to be running${NC}"
    else
        echo -e "  ${YELLOW}Ollama binary found but server not responding on localhost:11434${NC}"
        echo "  → Run:  ollama serve  (in another terminal)"
    fi
else
    echo -e "${RED}✗ ollama not found${NC}"
    echo "Install Ollama from official site: https://ollama.com/download"
    echo "Linux one-liner example:"
    echo "  curl -fsSL https://ollama.com/install.sh | sh"
    echo "macOS: download .dmg or use brew install ollama (if tap available)"
    echo "After install → run 'ollama serve' and pull your model"
    # We don't auto-install because it's a bigger decision (service/daemon)
    exit 1
fi

# ────────────────────────────────────────────────
# 8. Create virtual environment + sync dependencies
# ────────────────────────────────────────────────
echo -e "${YELLOW}8. Setting up Python virtual environment ...${NC}"

if [ -d ".venv" ] && [ -f ".venv/bin/python" ] || [ -f ".venv/Scripts/python.exe" ]; then
    echo -e "${GREEN}✓ .venv already exists${NC}"
else
    echo "Creating venv with Python 3.12 ..."
    uv venv --python 3.12 .venv
fi

# Activate (in the same script - subshell style)
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null || {
    echo -e "${RED}Failed to activate .venv${NC}"
    exit 1
}

echo "Running uv sync ..."
uv sync

# ────────────────────────────────────────────────
# 9. NLTK data
# ────────────────────────────────────────────────
echo -e "${YELLOW}9. Downloading NLTK punkt_tab ...${NC}"
python -c "import nltk; nltk.download('punkt_tab', quiet=True)" && \
    echo -e "${GREEN}✓ NLTK data ready${NC}" || \
    echo -e "${RED}NLTK download failed${NC}"

# ────────────────────────────────────────────────
# 10. .env file reminder
# ────────────────────────────────────────────────
echo -e "${YELLOW}10. .env file${NC}"
if [ -f ".env" ]; then
    echo -e "${GREEN}✓ .env already exists${NC}"
    # Check if DB_PASSWORD is empty and update it
    if grep -q "^DB_PASSWORD=$" .env; then
        echo -e "${YELLOW}→ DB_PASSWORD is empty, setting default password...${NC}"
        sed -i.bak "s/^DB_PASSWORD=$/DB_PASSWORD=aviai/" .env && rm -f .env.bak
        echo -e "${GREEN}✓ DB_PASSWORD set to: aviai${NC}"
    fi
else
    echo -e "${YELLOW}→ .env not found — creating template ...${NC}"

    # Prompt user for SECRET_KEY
    echo -e "${CYAN}Enter your SECRET_KEY (or press Enter to generate one automatically):${NC}"
    read -r USER_SECRET_KEY

    if [ -z "$USER_SECRET_KEY" ]; then
        # Generate a random secret key
        USER_SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
        echo -e "${GREEN}✓ Generated SECRET_KEY${NC}"
    else
        echo -e "${GREEN}✓ Using provided SECRET_KEY${NC}"
    fi

    cat > .env << EOF
DB_USER=postgres
DB_PASSWORD=aviai
DB_HOST=localhost
DB_PORT=5432
DB_NAME=aviai_db
SECRET_KEY="${USER_SECRET_KEY}"
ALGORITHM=HS256
OLLAMA_MODEL_URL=http://localhost:11434
EOF
    echo -e "${GREEN}✓ .env file created${NC}"
fi

# Load .env variables into the shell — parse manually to avoid CRLF issues on Windows
while IFS='=' read -r key value; do
    # Skip comments and blank lines
    [[ "$key" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$key" ]] && continue
    # Strip carriage return (\r) from key and value
    key="${key//$'\r'/}"
    value="${value//$'\r'/}"
    key="${key// /}"   # strip spaces from key
    # Only export valid shell variable names
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && export "$key=$value"
done < .env

# Provide defaults in case .env is missing keys
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-aviai}"

# ────────────────────────────────────────────────
# 11. Database role + database
# ────────────────────────────────────────────────
echo -e "${YELLOW}11. Checking/creating database '${DB_NAME}' ...${NC}"

PG_SUPER="-h ${DB_HOST} -p ${DB_PORT} -U postgres"
PG_OPTS="-h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER}"

# Create the role if it doesn't exist (requires postgres superuser)
ROLE_EXISTS=$(psql ${PG_SUPER} -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" 2>/dev/null)
if [ "$ROLE_EXISTS" = "1" ]; then
    echo -e "${GREEN}✓ Role '${DB_USER}' already exists${NC}"
    # Update password to match .env
    echo -e "${YELLOW}Updating password for role '${DB_USER}' ...${NC}"
    if psql ${PG_SUPER} -c "ALTER ROLE \"${DB_USER}\" WITH PASSWORD '${DB_PASSWORD}';" 2>/dev/null; then
        echo -e "${GREEN}✓ Password updated${NC}"
    else
        echo -e "${YELLOW}Could not update password — continuing anyway${NC}"
    fi
else
    echo -e "${YELLOW}Creating role '${DB_USER}' ...${NC}"
    CREATE_ROLE_RESULT=$(psql ${PG_SUPER} -c "CREATE ROLE \"${DB_USER}\" WITH LOGIN PASSWORD '${DB_PASSWORD}';" 2>&1)
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Role '${DB_USER}' created${NC}"
    elif echo "$CREATE_ROLE_RESULT" | grep -q "already exists"; then
        echo -e "${GREEN}✓ Role '${DB_USER}' already exists${NC}"
        # Update password to match .env
        psql ${PG_SUPER} -c "ALTER ROLE \"${DB_USER}\" WITH PASSWORD '${DB_PASSWORD}';" 2>/dev/null
    else
        echo -e "${RED}Failed to create role '${DB_USER}' — you may need to run manually:${NC}"
        echo "  psql -h ${DB_HOST} -p ${DB_PORT} -U postgres -c \"CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD 'yourpassword';\""
    fi
fi

# Create the database if it doesn't exist
DB_EXISTS=$(psql ${PG_SUPER} -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" 2>/dev/null)
if [ "$DB_EXISTS" = "1" ]; then
    echo -e "${GREEN}✓ Database '${DB_NAME}' already exists${NC}"
else
    echo -e "${YELLOW}Creating database '${DB_NAME}' ...${NC}"
    CREATE_RESULT=$(psql ${PG_SUPER} -c "CREATE DATABASE \"${DB_NAME}\" OWNER \"${DB_USER}\";" 2>&1)
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Database '${DB_NAME}' created${NC}"
    elif echo "$CREATE_RESULT" | grep -q "already exists"; then
        echo -e "${GREEN}✓ Database '${DB_NAME}' already exists${NC}"
    else
        echo -e "${RED}Failed to create database '${DB_NAME}'${NC}"
        echo "Try manually:"
        echo "  psql -h ${DB_HOST} -p ${DB_PORT} -U postgres -c \"CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};\""
    fi
fi

# ────────────────────────────────────────────────
# 12. Alembic migrations
# ────────────────────────────────────────────────
echo -e "${YELLOW}12. Running Alembic migrations ...${NC}"
if [ -f "alembic.ini" ] || [ -d "alembic" ]; then
    alembic upgrade heads && echo -e "${GREEN}✓ Migrations applied${NC}" || {
        echo -e "${RED}Alembic failed — check alembic.ini and .env${NC}"
    }
else
    echo -e "${YELLOW}alembic.ini / alembic folder not found — skipping${NC}"
fi

# ────────────────────────────────────────────────
# 13. Start the server
# ────────────────────────────────────────────────
echo -e "${YELLOW}13. Starting the server ...${NC}"
cd src
echo -e "${GREEN}Server starting on http://localhost:8000${NC}"
echo -e "${CYAN}Press Ctrl+C to stop the server${NC}"
uvicorn main:app --reload --port 8000

# ────────────────────────────────────────────────
# Final instructions
# ────────────────────────────────────────────────
echo ""
echo -e "${GREEN}=== Setup checks finished ===${NC}"
echo ""
echo -e "${CYAN}Don't forget to:${NC}"
echo "  • Edit .env (especially passwords & keys)"
echo "  • Make sure Ollama is running + desired model is pulled"
echo "  • Start PostgreSQL if not running"
echo ""
