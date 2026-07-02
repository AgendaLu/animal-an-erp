#!/bin/bash
# Web application startup script for Animal-AN ERP
# Supports development and production modes

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check Python
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 not found. Please install Python 3.9+"
    exit 1
fi

# Check virtual environment
if [ ! -d "$PROJECT_ROOT/.venv" ]; then
    log_warning "Virtual environment not found. Creating..."
    python3 -m venv "$PROJECT_ROOT/.venv"
fi

# Activate virtual environment
log_info "Activating virtual environment..."
source "$PROJECT_ROOT/.venv/bin/activate"

# Install dependencies
if [ ! -f "$PROJECT_ROOT/.venv/INSTALLED" ]; then
    log_info "Installing dependencies..."
    pip install -q -e "$PROJECT_ROOT"
    touch "$PROJECT_ROOT/.venv/INSTALLED"
fi

# Get environment
ENVIRONMENT="${ANIMAL_AN_ENV:-development}"
log_info "Running in $ENVIRONMENT environment"

# Initialize database
log_info "Initializing database..."
python3 -c "from models.database import db_manager; db_manager.init_db()"

# Parse command line arguments
UVICORN_ARGS="web.app:app --host 127.0.0.1 --port 8000"

if [ "$ENVIRONMENT" = "development" ]; then
    log_info "Development mode: auto-reload enabled"
    UVICORN_ARGS="$UVICORN_ARGS --reload"
elif [ "$ENVIRONMENT" = "production" ]; then
    log_info "Production mode: listening on 0.0.0.0:8000"
    UVICORN_ARGS="web.app:app --host 0.0.0.0 --port 8000 --workers 4"
fi

# Start web server
log_info "Starting FastAPI web server..."
log_info "Open browser: http://127.0.0.1:8000"
log_info "API docs:     http://127.0.0.1:8000/api/docs"

python3 -m uvicorn $UVICORN_ARGS
