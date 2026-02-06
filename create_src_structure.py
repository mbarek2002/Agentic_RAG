from pathlib import Path

BASE = Path("src")

# Folders to create
folders = [
    "db/interfaces",
    "models",
    "repositories",
    "routers",
    "schemas",
    "services/ollama",
]

# Files to create
files = [
    # db
    "db/__init__.py",
    "db/factory.py",
    "db/interfaces/__init__.py",
    "db/interfaces/base.py",
    "db/interfaces/postgresql.py",

    # models
    "models/__init__.py",
    "models/paper.py",

    # repositories
    "repositories/__init__.py",
    "repositories/paper.py",

    # routers
    "routers/__init__.py",
    "routers/ask.py",
    "routers/papers.py",
    "routers/ping.py",

    # schemas
    "schemas/__init__.py",
    "schemas/ask.py",
    "schemas/health.py",
    "schemas/paper.py",

    # services
    "services/__init__.py",
    "services/ollama/__init__.py",
    "services/ollama/client.py",

    # root
    "config.py",
]

# Create base dir
BASE.mkdir(exist_ok=True)

# Create folders
for folder in folders:
    (BASE / folder).mkdir(parents=True, exist_ok=True)

# Create files
for file in files:
    path = BASE / file
    if not path.exists():
        path.touch()

print("✅ src structure verified / created successfully.")
