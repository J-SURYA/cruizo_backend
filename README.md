# CRUIZO - Backend

## Cruizo - Premium Car Rentals | Fast, Easy, Affordable

An AI-powered Car Rental System (CRS) built with FastAPI and LangGraph framework.

## Prerequisites

- Python 3.13+
- PostgreSQL 14+ with pgvector extension
- MongoDB 6.0+
- Redis 7.0+
- Azure Storage Account
- OpenAI API Key or compatible LLM API
- uv (recommended) or pip package manager

### Installing uv

```bash
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Alternative: Using pip
pip install uv
```

## Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd cruizo_backend
```

### 2. Environment Setup

**Using uv (Recommended):**

```bash
# Create virtual environment and sync dependencies
uv sync

# Or manually create venv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

**Using pip:**

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

**Using uv:**

```bash
# Install from pyproject.toml
uv pip install -e .

# Or from requirements.txt
uv pip install -r requirements.txt
```

**Using pip:**

```bash
# Install from pyproject.toml
pip install -e .

# Or from requirements.txt
pip install -r requirements.txt
```

### 4. Setup PostgreSQL

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database and enable pgvector
CREATE DATABASE <postgres_db_name>;
\c <postgres_db_name>
CREATE EXTENSION IF NOT EXISTS vector;
\q
```

## Environment Variables

Create a `.env` file in the root directory. Use `.env.sample` as reference:

```bash
cp .env.sample .env
```

Update the following required variables in your `.env` file:

```env
# Database Configuration
POSTGRES_USER=postgres_user
POSTGRES_PASSWORD=postgres_password
POSTGRES_HOST=postgres_host
POSTGRES_PORT=postgres_port
POSTGRES_DB=postgres_db

MONGO_URI=mongo_uri
MONGO_DB=mongo_db

# Security & Authentication
ACCESS_TOKEN_SECRET_KEY=access_token_secret_key
REFRESH_TOKEN_SECRET_KEY=refresh_token_secret_key
PASSWORD_RESET_SECRET_KEY=password_reset_secret_key

# Super Admin Configuration
SUPER_ADMIN_NAME=super_admin_name
SUPER_ADMIN_EMAIL=super_admin_email
SUPER_ADMIN_USERNAME=super_admin_username
SUPER_ADMIN_PASSWORD=super_admin_password

# Location Configuration
HUB_LATITUDE=hub_latitiude
HUB_LONGITUDE=hub_longitude

# Email Configuration
MAIL_USERNAME=google_mail_username
MAIL_PASSWORD=google_mail_password
MAIL_FROM=sender_address
MAIL_FROM_NAME=sender_name

# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING=azure_storage_connection_string

# External APIs
GOOGLE_GEOCODING_API_KEY=google_geocoding_api_key
FRONTEND_URL=frontend_url

# Redis Configuration
REDIS_HOST=redis_host
REDIS_PORT=redis_port
REDIS_PASSWORD=redis_password

# LLM Configuration
OPENAI_API_KEY=openai_api_key
OPENAI_API_BASE_URL=openai_api_base_url
OPENAI_MODEL=openai_model
GROQ_API_KEY=groq_api_key
GROQ_MODEL=groq_model

# LangSmith Tracing
LANGSMITH_API_KEY=langsmith_api_key
LANGSMITH_PROJECT=langsmith_project
```

All other environment variables have default values set in `.env.sample`.

## Run Migrations

```bash
# Run database migrations
alembic upgrade head
```

## Run Project

**Using uv:**

```bash
# Development mode
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Using pip:**

```bash
# Development mode
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at:

- API Base URL: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Project Structure

```
crs_assistant/
│
├── alembic/                          # Database migration scripts
│   ├── versions/                     # Migration version files
│   ├── env.py                        # Alembic environment configuration
│   ├── README
│   └── script.py.mako                # Migration template
│
├── app/                              # Main application package
│   │
│   ├── api/                          # API layer
│   │   └── routes/                   # API route modules
│   │
│   ├── assistant/                    # LangGraph AI assistant
│   │   ├── agent.py                  # Main agent definition and graph
│   │   ├── schema.py                 # Assistant data schemas
│   │   ├── streaming.py              # Streaming response handlers
│   │   ├── nodes/                    # Agent nodes/steps
│   │   ├── prompts/                  # LLM prompt templates
│   │   └── tools/                    # Agent tools and functions
│   │
│   ├── auth/                         # Authentication module
│   │   ├── dependencies.py           # Auth dependencies for routes
│   │   └── security.py               # Security utilities (JWT, hashing)
│   │
│   ├── collections/                  # MongoDB collections
│   │   ├── backup_models.py          # Backup collection models
│   │   └── enums.py                  # Shared enumerations
│   │
│   ├── core/                         # Core configuration
│   │   ├── config.py                 # Settings and environment variables
│   │   └── dependencies.py           # Global dependencies
│   │
│   ├── crud/                         # Database CRUD operations
│   │
│   ├── database/                     # Database connections
│   │   ├── blob_storage.py           # Azure Blob Storage client
│   │   ├── session_mongo.py          # MongoDB connection
│   │   └── session_sql.py            # PostgreSQL connection & checkpointer
│   │
│   ├── middlewares/                  # Custom middlewares
│   │   ├── exception_handler.py      # Global exception handlers
│   │   └── rate_limit_middleware.py  # Rate limiting logic
│   │
│   ├── models/                       # SQLAlchemy ORM models
│   │   ├── base.py                   # Base model class
│   │
│   ├── schedulers/                   # Background job schedulers
│   │   ├── manager.py                # Scheduler manager - Handles all schedulers
│   │
│   ├── schemas/                      # Pydantic schemas
│   │
│   ├── services/                     # Business logic layer
│   │
│   ├── utils/                        # Utility functions
│   │
│   └── router.py                     # Main API router aggregator
│
├── static/                           # Static files
│   └── custom_swagger.html           # Custom Swagger UI
│
├── alembic.ini                       # Alembic configuration
├── langgraph.json                    # LangGraph configuration
├── main.py                           # Application entry point
├── pyproject.toml                    # Project dependencies (PEP 621)
├── requirements.txt                  # Python dependencies
└── README.md                         # This file
```
