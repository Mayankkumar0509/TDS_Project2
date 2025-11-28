import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Paths
BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
LOGS_DIR = BASE_DIR / "logs"

# Ensure directories exist
TEMP_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Environment variables
QUIZ_SECRET = os.getenv("QUIZ_SECRET", "default_dev_secret_do_not_use")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "5"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "180"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# AIML Configuration (OpenAI-compatible)
AIML_BASE_URL = os.getenv("AIML_BASE_URL", "https://aipipe.org/openai/v1")
AIML_MODEL = os.getenv("AIML_MODEL", "gpt-4o-mini")
AIML_API_KEY = os.getenv("AIML_API_KEY", "")

# Browser settings
BROWSER_TIMEOUT_MS = 30000  # 30 sec for page load
NETWORK_IDLE_TIMEOUT_MS = 5000  # Wait for network idle

# Submission settings
MAX_SUBMISSION_SIZE = 1024 * 1024  # 1MB
MAX_RETRIES = 3

# Allowed schemes for security
ALLOWED_SCHEMES = {"http", "https"}

# Common task patterns
TASK_PATTERNS = {
    "sum": r"sum|total|add|aggregate",
    "count": r"count|how many|number of",
    "average": r"average|mean|median",
    "extract": r"extract|find|identify|list",
}