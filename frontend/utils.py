import streamlit as st

def style_text(
    text: str,
    level: int = 1,
    align: str = "center",
    color: str = "#0E6909",
    background_color: str = "#A7A9A7",
):
    """
    Display a styled heading (h1-h6) in Streamlit using HTML and CSS.

    Args:
        text (str): The heading text.
        level (int): Heading level (1–6). Default: 1.
        align (str): Text alignment - 'left', 'center', or 'right'.
        font_size (str | None): Custom font size (e.g., '32px', '2.5rem'). Defaults to browser default for chosen h-level.
        color (str): Text color.
        background_color (str): Background color.
        font_family (str): Font family.
        padding (str): Padding around text.
        border_radius (str): Rounded corners for background.
    """

    # Ensure heading level is between 1 and 6
    level = max(1, min(level, 6))

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