import pathlib

_APP_DIR = pathlib.Path.home() / "Library" / "Application Support" / "InternApplier"
_MODELS_FILE = _APP_DIR / "models.txt"
_SETTINGS_FILE = _APP_DIR / "settings.json"
_PROMPTS_DIR = pathlib.Path(__file__).parent.parent.parent / "prompts"
_APP_PROMPTS_DIR = _APP_DIR / "prompts"
