import streamlit as st

from frontend.styles import PALETTE


def style_text(
    text: str,
    level: int = 1,
    align: str = "center",
    color: str | None = None,
    background_color: str | None = None,
) -> None:
    """
    Display a styled heading (h1-h6) in Streamlit using HTML and CSS.

    Colors default to the shared Rose Taupe design tokens so views stay on
    brand. Arguments are kept for backwards compatibility with existing calls.

    Args:
        text (str): The heading text.
        level (int): Heading level (1–6). Default: 1.
        align (str): Text alignment - 'left', 'center', or 'right'.
        color (str | None): Text color. Defaults to the brand text token.
        background_color (str | None): Background color. Defaults to transparent.
    """

    # Ensure heading level is between 1 and 6
    level = max(1, min(level, 6))

    color = color or PALETTE["text"]
    background_color = background_color or "transparent"

    html_code = f"""
    <div style="text-align: {align};">
        <h{level} style="
            display: inline-block;
            color: {color};
            background-color: {background_color};
        ">
            {text}
        </h{level}>
    </div>
    """

    st.markdown(html_code, unsafe_allow_html=True)