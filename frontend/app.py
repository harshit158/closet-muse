import sys
from pathlib import Path

# Streamlit only adds the running script's own directory (frontend/) to
# sys.path, so the project root must be added explicitly for the `frontend`
# package to be importable regardless of how the app is launched.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from frontend import api_utils, styles, utils
from closet_muse.settings import settings

from foundry.observability import ObservabilityConfig, get_logger, get_tracer, init_observability
config = ObservabilityConfig(app_name=settings.app_name)
init_observability(config)

logger = get_logger(__name__)
tracer = get_tracer(__name__)

# The app is single-user local; every view hardcodes this id.
USER_ID = 1

def init():
    st.set_page_config(layout="wide", page_title="Closet Muse", page_icon="👗")
    styles.inject_css()
    logger.info("Initialized the app")

def _load_credits() -> int | None:
    """Return the user's credit balance, fetching it once per session.

    Cached in ``st.session_state`` because the hero renders on every rerun and the
    balance only changes when a generation succeeds (which writes the new value back).
    A backend that is down must not break the page shell, so a failed fetch returns
    ``None`` and the hero simply omits the pill.
    """
    if "credits" not in st.session_state:
        try:
            st.session_state.credits = api_utils.fetch_user(USER_ID).get("credits")
        except Exception as exc:  # noqa: BLE001 - the shell must still render
            logger.warning("Could not load credit balance: %s", exc)
            return None
    return st.session_state.credits

def display_header():
    styles.hero(
        "assets/logo/title_logo.png",
        tagline="Your personal AI stylist",
        credits=_load_credits(),
    )

def display_navigation():
    pages = {
        "Wardrobe": [
            st.Page("views/generate_outfit.py", title="Generate Outfit"),
            st.Page("views/onboard_wardrobe.py", title="Add to Collection"),
            st.Page("views/edit_collection.py", title="Edit Collection"),
        ],
        "Coming Soon": [
            st.Page("views/clo_ai.py", title="Chat with Clo AI"),
            st.Page("views/shop.py", title="Shop"),
        ],
    }

    pg = st.navigation(pages, position="top")
    pg.run()

def run_app():
    # Initialize the app    
    init()
    
    # Display the title header
    display_header()
    
    # Display navigation menu
    display_navigation()

    # Display personal note in the sidebar
    styles.sidebar_note(settings.personal_note)

if __name__ == "__main__":
    run_app()