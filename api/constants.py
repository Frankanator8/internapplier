from pathlib import Path


# --- Application paths ---
APP_DIR = Path.home() / "Library" / "Application Support" / "InternApplier"
RESUME_DATA_FILE = APP_DIR / "resume.json"
INTERVIEW_TEMPLATE_FILE = APP_DIR / "interview_template.json"
INTERVIEW_FEEDBACK_FILE = APP_DIR / "interview_feedback.json"
MODELS_FILE = APP_DIR / "models.txt"
SETTINGS_FILE = APP_DIR / "settings.json"
TOKEN_USAGE_FILE = APP_DIR / "token_usage.json"
APP_PROMPTS_DIR = APP_DIR / "prompts"
ENV_FILE = APP_DIR / ".env"
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# --- Server ---
SERVER_HOST = "127.0.0.1"
DEFAULT_SERVER_PORT = 8765

# --- Application status ---
STATUS_OPTIONS = [
    "Added",
    "Materials Prepped",
    "Applied",
    "Phone Screen",
    "Interview",
    "Offer",
    "Rejected",
]
DEFAULT_STATUS = "Added"

# --- Form schema fields ---
LINE_FIELDS = [
    "first_name", "last_name", "preferred_name", "pronouns",
    "email", "phone", "address1", "address2", "city", "state",
    "postal_code", "country", "linkedin", "website", "github",
    "earliest_start_date", "desired_salary", "date_of_birth",
]
COMBO_FIELDS = [
    "employment_status", "work_authorization", "require_sponsorship",
    "willing_to_relocate", "gender", "ethnicity", "veteran_status",
    "disability_status",
]
ALL_FIELDS = LINE_FIELDS + COMBO_FIELDS

# --- Web scraper ---
SCRAPER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_SCRAPER_CANDIDATE_PATHS = [
    "/", "/about", "/about-us", "/company", "/values",
    "/mission", "/careers", "/team", "/news", "/blog",
]
SCRAPER_MAX_PAGES = 5
SCRAPER_MAX_TOTAL_CHARS = 15000

# --- AI provider defaults ---
DEFAULT_BASIC_MODEL = "google/gemini-2.0-flash-exp:free"
DEFAULT_FAST_MODEL = "google/gemini-2.0-flash-exp:free"
DEFAULT_POWERFUL_MODEL = "openai/gpt-4o-mini"
DEFAULT_RESUME_PAGE_CAP = 1
DEFAULT_RESUME_OUTPUT_DIR = Path.home() / "Documents" / "Resumes"
DEFAULT_MAX_GENERATION_ATTEMPTS = 3
DEFAULT_AUTO_RESYNC_PROMPTS = False

# --- AI provider error handling ---
OPENROUTER_KEY_INFO_URL = "https://openrouter.ai/api/v1/auth/key"
OPENROUTER_KEY_INFO_TIMEOUT = 3.0

# --- Resume generation ---
DEFAULT_RESUME_SCORE_THRESHOLD = 9.5
AGENT_MAX_LOG_EXCERPT = 1500

# --- Applications heatmap ---
DEFAULT_HEATMAP_DAY_THRESHOLDS = [1, 2, 3, 4]
DEFAULT_HEATMAP_WEEK_THRESHOLDS = [1, 3, 6, 10]
