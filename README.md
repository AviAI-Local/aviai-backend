### Installation

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh
# or on macOS: brew install uv
# or on Windows: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Clone the repository
git clone https://github.com/vndee/local-talking-llm.git
cd local-talking-llm

# Install dependencies using uv (recommended)
uv sync

# Activate the virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Download NLTK data (for sentence tokenization)
python -c "import nltk; nltk.download('punkt_tab')"
```

```bash
brew install espeak
uv pip install kokoro
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