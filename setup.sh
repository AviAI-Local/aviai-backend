#!/usr/bin/env bash
# setup-aviai.sh
# Checks and prepares the environment for the Aviai project
# Supports macOS (brew) + common Linux (apt/dnf/pacman)

set -u   # treat unset variables as error
set -e   # exit on error

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

# ────────────────────────────────────────────────
# 2. VS Code
# ────────────────────────────────────────────────
echo -e "${YELLOW}2. Checking VS Code (code) ...${NC}"
if command -v code >/dev/null 2>&1; then
    CODE_VERSION=$(code --version 2>/dev/null | head -1 || echo "unknown")
    echo -e "${GREEN}✓ VS Code ${CODE_VERSION} found${NC}"
else
    echo -e "${YELLOW}VS Code not found → attempting install ...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]] && command -v brew >/dev/null 2>&1; then
        brew install --cask visual-studio-code
    elif command -v apt-get >/dev/null 2>&1; then
        # Add Microsoft's apt repository and install
        sudo apt-get install -y wget gpg apt-transport-https
        wget -qO- https://packages.microsoft.com/keys/microsoft.asc \
            | gpg --dearmor | sudo tee /usr/share/keyrings/packages.microsoft.gpg >/dev/null
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/packages.microsoft.gpg] \
https://packages.microsoft.com/repos/code stable main" \
            | sudo tee /etc/apt/sources.list.d/vscode.list >/dev/null
        sudo apt-get update -q && sudo apt-get install -y code
    elif command -v dnf >/dev/null 2>&1; then
        sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc
        sudo tee /etc/yum.repos.d/vscode.repo >/dev/null <<'REPO'
[code]
name=Visual Studio Code
baseurl=https://packages.microsoft.com/yumrepos/vscode
enabled=1
gpgcheck=1
gpgkey=https://packages.microsoft.com/keys/microsoft.asc
REPO
        sudo dnf install -y code
    elif command -v pacman >/dev/null 2>&1; then
        # code is in the AUR; try yay/paru if available
        if command -v yay >/dev/null 2>&1; then
            yay -S --noconfirm visual-studio-code-bin
        elif command -v paru >/dev/null 2>&1; then
            paru -S --noconfirm visual-studio-code-bin
        else
            echo -e "${YELLOW}Arch: install VS Code via AUR (yay -S visual-studio-code-bin)${NC}"
        fi
    else
        echo -e "${YELLOW}Could not install VS Code automatically${NC}"
        echo "Please download it from: https://code.visualstudio.com/download"
    fi

    if command -v code >/dev/null 2>&1; then
        echo -e "${GREEN}✓ VS Code installed${NC}"
    else
        echo -e "${YELLOW}⚠ VS Code not detected in PATH after install attempt${NC}"
        echo "  You may need to restart your terminal or install manually."
    fi
fi

# ────────────────────────────────────────────────
# 3. Python 3.12+
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
else
    echo -e "${YELLOW}→ .env not found — creating template ...${NC}"
    cat > .env << 'EOF'
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=aviai
SECRET_KEY=change_me_to_the_correct_key
ALGORITHM=HS256
OLLAMA_MODEL_URL=http://localhost:11434
EOF
    echo -e "${CYAN}Please edit .env now (especially password, secret key)${NC}"
fi

# ────────────────────────────────────────────────
# 11. Database
# ────────────────────────────────────────────────
echo -e "${YELLOW}11. Checking/creating database 'aviai' ...${NC}"
if psql -lqt | cut -d \| -f 1 | grep -qw "aviai"; then
    echo -e "${GREEN}✓ Database 'aviai' already exists${NC}"
else
    echo -e "${YELLOW}Creating database aviai ...${NC}"
    createdb aviai 2>/dev/null || sudo -u postgres createdb aviai || {
        echo -e "${RED}Failed to create database${NC}"
        echo "Try manually:"
        echo "  createdb aviai"
        echo "  or  sudo -u postgres createdb aviai"
    }
fi

# ────────────────────────────────────────────────
# 12. Alembic migrations
# ────────────────────────────────────────────────
echo -e "${YELLOW}12. Running Alembic migrations ...${NC}"
if [ -f "alembic.ini" ] || [ -d "alembic" ]; then
    alembic upgrade head && echo -e "${GREEN}✓ Migrations applied${NC}" || {
        echo -e "${RED}Alembic failed — check alembic.ini and .env${NC}"
    }
else
    echo -e "${YELLOW}alembic.ini / alembic folder not found — skipping${NC}"
fi

# ────────────────────────────────────────────────
# Final instructions
# ────────────────────────────────────────────────
echo ""
echo -e "${GREEN}=== Setup checks finished ===${NC}"
echo "To start the server:"
echo "  source .venv/bin/activate     # or .venv\\Scripts\\activate on Windows"
echo "  cd src"
echo "  uvicorn main:app --reload --port 8000"
echo ""
echo -e "${CYAN}Don't forget to:${NC}"
echo "  • Edit .env (especially passwords & keys)"
echo "  • Make sure Ollama is running + desired model is pulled"
echo "  • Start PostgreSQL if not running"
echo ""

read
