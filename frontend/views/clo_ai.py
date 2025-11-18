import streamlit as st
from frontend.utils import style_text

def display_clo_ai():
    with st.container(horizontal_alignment="center"):
        style_text("Chat with Clo AI", level=1, align="center", color="#000000", background_color="#FFFFFF")
        style_text("(Coming Soon 😉)", level=3, align="center", color="#000000", background_color="#FFFFFF")
    
if __name__ == "__main__":
    display_clo_ai()