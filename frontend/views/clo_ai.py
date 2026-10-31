import streamlit as st
from frontend import styles


def display_clo_ai():
    with styles.card("cm-card-clo-ai"):
        styles.eyebrow("Clo AI")
        styles.empty_state(
            "Chat with Clo AI is coming soon — your personal stylist will be here shortly.",
            emoji="👗",
        )


# Streamlit executes this file as the page entrypoint, so render on import.
display_clo_ai()
