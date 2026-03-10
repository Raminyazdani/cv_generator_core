import os

# -------------------------
# Settings
# -------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CVS_PATH = os.path.join(BASE_DIR, "data", "cvs")
COVER_LETTER_PATH = os.path.join(BASE_DIR, "data", "cover_letter_datas")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
RESULT_DIR = os.path.join(BASE_DIR, "result")
LANG_ENGINE_DIR = os.path.join(BASE_DIR, "Lang_engine")
CACHE_FILE = os.path.join(BASE_DIR, ".cvgen_cache.json")

# RTL languages
RTL_LANGUAGES = {"fa", "ar", "he"}

# Toggle whether template-inserted comments are emitted
SHOW_COMMENTS = True

# Global verbose flag (set by command-line argument)
VERBOSE = False


# -------------------------
# Verbose Logging
# -------------------------
def log_verbose(message):
    """Print message only if verbose mode is enabled."""
    if VERBOSE:
        print(message)
