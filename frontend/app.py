import streamlit as st
from frontend import utils
from backend.settings import settings

def init():
    st.set_page_config(layout="wide")

def display_header():
    title_container = st.container(horizontal_alignment="center")
    with title_container:
        # utils.style_text("Closet Muse", level=1, align="center", color="#000000", background_color="#FFFFFF")
        st.image("assets/logo/title_logo.png", width=600)
    st.divider()

def display_sidebar():
    st.sidebar.image("assets/logo/sidebar_logo.png")
    with st.sidebar, st.container(horizontal_alignment="center"):
        st.text(settings.personal_note)

def display_navigation():
    pages = {
        "Home": [
            st.Page("views/generate_outfit.py", title="Generate Outfit"),
            st.Page("views/clo_ai.py", title="Chat with Clo AI"),
        ],
        "Manage Wardrobe": [
            st.Page("views/onboard_wardrobe.py", title="Add to collection"),
        ]
    }

    pg = st.navigation(pages, position="top")
    pg.run()

def run_app():
    # Initialize the app    
    init()
    
    # Display sidebar
    display_sidebar()
    
    # Display the title header
    display_header()
    
    # Display navigation menu
    display_navigation()

if __name__ == "__main__":
    run_app()