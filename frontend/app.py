import streamlit as st
from frontend import utils
from backend.settings import settings

def init():
    st.set_page_config(layout="wide")

def display_header():
    utils.style_text("Closet Muse", level=1, align="center", color="#000000", background_color="#FFFFFF")
    st.divider()

def display_sidebar():
    st.divider()
    st.sidebar.text(settings.personal_note)

def display_navigation():
    pages = [
            st.Page("views/onboard_wardrobe.py", title="Onboard your wardrobe"),
            st.Page("views/generate_outfit.py", title="Generate an outfit"),
        ]

    pg = st.navigation(pages)
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