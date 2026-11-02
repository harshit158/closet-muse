"""Central styling for the Closet Muse Streamlit frontend.

Call :func:`inject_css` once (from ``frontend.app.init``) to load the design
tokens, fonts and shared component styles. Use :func:`card` to wrap column
content in a styled surface instead of Streamlit's default ``border=True``.
"""

import streamlit as st

# ---------------------------------------------------------------------------
# Design tokens (Light & Airy — Rose Taupe palette)
# ---------------------------------------------------------------------------
PRIMARY = "#9C6B6B"          # dusty rose
PRIMARY_DARK = "#7E5252"
SECONDARY = "#B8927A"        # warm taupe / terracotta
BACKGROUND = "#FAF7F4"       # warm off-white
SURFACE = "#FFFFFF"
TEXT = "#2E2A26"
TEXT_MUTED = "#8A8078"
BORDER = "#E8E0D9"

# Convenience aliases for view code that wants the palette in Python.
PALETTE = {
    "primary": PRIMARY,
    "primary_dark": PRIMARY_DARK,
    "secondary": SECONDARY,
    "background": BACKGROUND,
    "surface": SURFACE,
    "text": TEXT,
    "text_muted": TEXT_MUTED,
    "border": BORDER,
}


def inject_css() -> None:
    """Inject fonts, CSS variables and global component styles."""

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700&family=Inter:wght@300;400;500;600&display=swap');

        :root {{
            --cm-primary: {PRIMARY};
            --cm-primary-dark: {PRIMARY_DARK};
            --cm-secondary: {SECONDARY};
            --cm-bg: {BACKGROUND};
            --cm-surface: {SURFACE};
            --cm-text: {TEXT};
            --cm-text-muted: {TEXT_MUTED};
            --cm-border: {BORDER};

            --cm-radius: 16px;
            --cm-radius-sm: 10px;
            --cm-shadow: 0 6px 24px rgba(46, 42, 38, 0.08);
            --cm-shadow-hover: 0 10px 30px rgba(46, 42, 38, 0.14);

            /* Layout offsets — keep the pinned hero + pinned panels aligned.
               --cm-header-h is the native Streamlit toolbar height; the hero
               pins directly under it, and the cards pin under the hero. */
            --cm-header-h: 3.75rem;
            --cm-hero-h: 4.35rem;
            --cm-panel-top: calc(var(--cm-header-h) + var(--cm-hero-h) + 0.5rem);
            --cm-space: 1.25rem;
        }}

        /* ---- Base ---- */
        html, body, [class*="css"] {{
            font-family: 'Inter', sans-serif;
            color: var(--cm-text);
        }}

        .stApp {{
            background-color: var(--cm-bg);
        }}

        h1, h2, h3, h4, h5, h6 {{
            font-family: 'Playfair Display', serif;
            color: var(--cm-text);
            letter-spacing: 0.2px;
        }}

        /* ---- Hero (compact horizontal band) ---- */
        /* The hero is pinned so it never scrolls away; every other pinned
           panel uses --cm-panel-top to sit just below it. */
        [data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] .cm-hero) {{
            position: sticky;
            top: var(--cm-header-h);
            z-index: 4;
            background: var(--cm-bg);
        }}
        .cm-hero {{
            background: linear-gradient(135deg, #F3E7E2 0%, #EFE2DA 45%, #E9DDD2 100%);
            border-radius: var(--cm-radius);
            padding: 0.85rem 1.5rem;
            margin-bottom: 0.5rem;
            box-shadow: var(--cm-shadow);
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 0.5rem 1.25rem;
        }}
        .cm-hero img {{
            display: block;
            height: 42px;
            width: auto;
        }}
        .cm-hero-tagline {{
            margin: 0;
            font-family: 'Inter', sans-serif;
            font-size: 0.78rem;
            font-weight: 400;
            letter-spacing: 2.5px;
            text-transform: uppercase;
            color: var(--cm-primary-dark);
        }}

        /* ---- Cards (keyed container: st.container(key="cm-card-...")) ---- */
        [class*="st-key-cm-card"] {{
            background: var(--cm-surface);
            border: 1px solid var(--cm-border);
            border-radius: var(--cm-radius);
            padding: var(--cm-space);
            box-shadow: var(--cm-shadow);
        }}
        .cm-card {{
            background: var(--cm-surface);
            border: 1px solid var(--cm-border);
            border-radius: var(--cm-radius);
            padding: var(--cm-space);
            box-shadow: var(--cm-shadow);
            height: 100%;
        }}
        .cm-card-title {{
            font-family: 'Playfair Display', serif;
            font-size: 1.15rem;
            font-weight: 600;
            color: var(--cm-text);
            margin: 0 0 0.75rem 0;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--cm-border);
        }}

        /* Streamlit column containers styled as cards */
        div[data-testid="stColumn"] .cm-fill {{
            height: 100%;
        }}

        /* ---- Buttons ---- */
        .stButton > button {{
            border-radius: var(--cm-radius-sm);
            font-weight: 500;
            transition: all 0.18s ease;
            border: 1px solid var(--cm-primary);
        }}
        .stButton > button[kind="primary"],
        .stButton > button[data-testid="stBaseButton-primary"] {{
            background-color: var(--cm-primary);
            color: #fff;
            border-color: var(--cm-primary);
        }}
        .stButton > button:hover {{
            transform: translateY(-1px);
            box-shadow: var(--cm-shadow-hover);
            border-color: var(--cm-primary-dark);
        }}

        /* ---- Inputs ---- */
        .stTextInput input,
        .stTextArea textarea,
        .stSelectbox div[data-baseweb="select"] > div {{
            border-radius: var(--cm-radius-sm) !important;
            border-color: var(--cm-border) !important;
        }}

        /* ---- Upload dropzone ---- */
        [data-testid="stFileUploaderDropzone"] {{
            background-color: #FBF6F3;
            border: 2px dashed var(--cm-secondary);
            border-radius: var(--cm-radius);
        }}

        /* ---- Chips / badges ---- */
        .cm-chip {{
            display: inline-block;
            background: #F5EAE5;
            color: var(--cm-primary-dark);
            border-radius: 999px;
            padding: 0.15rem 0.75rem;
            margin: 0.15rem 0.25rem 0.15rem 0;
            font-size: 0.85rem;
            font-weight: 500;
        }}

        /* ---- Section headings ---- */
        .cm-section-title {{
            font-family: 'Playfair Display', serif;
            font-size: 1.3rem;
            font-weight: 600;
            color: var(--cm-text);
            margin: 0 0 0.5rem 0;
        }}

        /* ---- Empty state ---- */
        .cm-empty {{
            text-align: center;
            color: var(--cm-text-muted);
            padding: 2rem 1rem;
            font-size: 0.95rem;
        }}
        .cm-empty .cm-empty-emoji {{
            display: block;
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}

        /* ---- Navigation (top tabs) polish ---- */
        [data-testid="stTabs"] button,
        div[data-testid="stNavLink"] {{
            font-weight: 500;
        }}

        /* ---- Sidebar note ---- */
        .cm-sidebar-note {{
            text-align: center;
            color: var(--cm-text-muted);
            font-size: 0.8rem;
            padding: 0.75rem 0.5rem;
            margin-top: 1rem;
            border-top: 1px solid var(--cm-border);
        }}

        /* ---- Eyebrow / section labels ---- */
        .cm-eyebrow {{
            font-family: 'Inter', sans-serif;
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 1.6px;
            text-transform: uppercase;
            color: var(--cm-text-muted);
            margin: 0 0 0.6rem 0;
        }}
        .cm-section-label {{
            display: flex;
            align-items: center;
            gap: 0.6rem;
            font-family: 'Playfair Display', serif;
            font-size: 1.05rem;
            font-weight: 600;
            color: var(--cm-text);
            margin: 0.5rem 0 0.85rem 0;
        }}
        .cm-section-label::after {{
            content: "";
            flex: 1;
            height: 1px;
            background: var(--cm-border);
        }}

        /* ---- Stat badge ---- */
        .cm-badge {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 1.35rem;
            height: 1.35rem;
            padding: 0 0.45rem;
            border-radius: 999px;
            background: #F5EAE5;
            color: var(--cm-primary-dark);
            font-family: 'Inter', sans-serif;
            font-size: 0.72rem;
            font-weight: 600;
        }}

        /* ---- Category pills ---- */
        [data-testid="stPills"] {{
            gap: 0.4rem;
        }}
        [data-testid="stPills"] button {{
            border-radius: 999px !important;
            border: 1px solid var(--cm-border) !important;
            background: var(--cm-surface) !important;
            color: var(--cm-text) !important;
            font-weight: 500;
            padding: 0.3rem 0.9rem !important;
            transition: all 0.16s ease;
        }}
        [data-testid="stPills"] button:hover {{
            border-color: var(--cm-primary) !important;
            transform: translateY(-1px);
        }}
        [data-testid="stBaseButton-pillsActive"] {{
            background: var(--cm-primary) !important;
            border-color: var(--cm-primary) !important;
            color: #fff !important;
            box-shadow: var(--cm-shadow);
        }}

        /* ---- Sticky columns (Studio layout) ----
           Only the wardrobe gallery should scroll. The categories card,
           the "Selected pieces" column and the "Your Look" panel all stay
           pinned so the selection context never leaves the screen. */
        div[data-testid="stColumn"]:has([class*="st-key-cm-card-look-panel"]),
        div[data-testid="stColumn"]:has([class*="st-key-cm-card-selected"]) {{
            position: sticky;
            top: var(--cm-panel-top);
            align-self: flex-start;
        }}

        /* Pin the categories card to the top of the first column so it stays
           put while the wardrobe gallery beneath it scrolls.
           NOTE: the card is itself a flex item, and `position: sticky` on a
           flex item defaults to `align-self: stretch` — the stretched box has
           no free space to travel in, so the card would never actually pin.
           Pinning the parent wrapper (which is NOT a flex item) and letting
           the card stretch to its height keeps the card pinned at full width. */
        div[data-testid="stLayoutWrapper"]:has(> [class*="st-key-cm-card-categories"]) {{
            position: sticky;
            top: var(--cm-panel-top);
            z-index: 3;
        }}

        /* ---- Only the wardrobe gallery scrolls ----
           The categories card, the "Selected pieces" column and the "Your
           Look" panel are all pinned, so scrolling the page only moves the
           garment groups (everything below the category pills). */

        /* Streamlit 1.50 bug: st.image(width="stretch") collapses to a tiny
           width when rendered inside st.empty().container(). Force images in
           the look panel to fill their container. */
        [class*="st-key-cm-card-look-panel"] [data-testid="stElementContainer"]:has(img),
        [class*="st-key-cm-card-look-panel"] [data-testid="stFullScreenFrame"],
        [class*="st-key-cm-card-look-panel"] [data-testid="stImage"],
        [class*="st-key-cm-card-look-panel"] [data-testid="stImageContainer"] {{
            width: 100% !important;
        }}
        [class*="st-key-cm-card-look-panel"] [data-testid="stImage"] img {{
            width: 100% !important;
            height: auto !important;
        }}

        /* ---- Selected-items thumbnail tray ---- */
        .cm-tray {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.6rem;
            margin: 0.25rem 0 0.9rem 0;
        }}
        .cm-tray-item {{
            width: 76px;
            border-radius: var(--cm-radius-sm);
            overflow: hidden;
            border: 1px solid var(--cm-border);
            background: var(--cm-surface);
            box-shadow: var(--cm-shadow);
        }}
        .cm-tray-item img {{
            display: block;
            width: 100%;
            height: 76px;
            object-fit: cover;
        }}
        .cm-tray-label {{
            display: block;
            font-size: 0.6rem;
            text-align: center;
            padding: 0.2rem 0.15rem;
            color: var(--cm-text-muted);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def card(key: str, title: str | None = None):
    """Return a styled card container (uses a keyed ``st.container``).

    Use as a context manager::

        with styles.card("cm-card-wardrobe", "Wardrobe"):
            ...
    """
    container = st.container(key=key)
    if title:
        container.markdown(
            f'<p class="cm-card-title">{title}</p>', unsafe_allow_html=True
        )
    return container


def hero(image_path: str, tagline: str = "") -> None:
    """Render a full-width gradient hero band with a centered logo."""
    import base64
    from pathlib import Path

    path = Path(image_path)
    if path.exists():
        encoded = base64.b64encode(path.read_bytes()).decode()
        img_tag = f'<img src="data:image/png;base64,{encoded}" alt="Closet Muse" />'
    else:
        img_tag = ""

    tagline_html = f'<p class="cm-hero-tagline">{tagline}</p>' if tagline else ""
    st.markdown(
        f'<div class="cm-hero">{img_tag}{tagline_html}</div>',
        unsafe_allow_html=True,
    )


def empty_state(message: str, emoji: str = "🧺") -> None:
    st.markdown(
        f'<div class="cm-empty"><span class="cm-empty-emoji">{emoji}</span>{message}</div>',
        unsafe_allow_html=True,
    )


def chips(items: list[str]) -> None:
    """Render a list of strings as inline pill chips."""
    if not items:
        return
    html = "".join(f'<span class="cm-chip">{item}</span>' for item in items)
    st.markdown(html, unsafe_allow_html=True)


def sidebar_note(note: str | None = None) -> None:
    """Render a centered note at the bottom of the sidebar."""
    if not note:
        return
    with st.sidebar:
        st.markdown(
            f'<div class="cm-sidebar-note">{note}</div>', unsafe_allow_html=True
        )


def eyebrow(text: str) -> None:
    """Render a small uppercase section eyebrow."""
    st.markdown(f'<p class="cm-eyebrow">{text}</p>', unsafe_allow_html=True)


def section_label(text: str) -> None:
    """Render a serif section label with a trailing rule."""
    st.markdown(f'<p class="cm-section-label">{text}</p>', unsafe_allow_html=True)


def stat_badge(count: int) -> str:
    """Return an inline HTML badge for a count (embed inside other HTML)."""
    return f'<span class="cm-badge">{count}</span>'


def thumb_tray(items: list[dict]) -> None:
    """Render selected items as a compact thumbnail tray.

    Each item is a dict with ``label`` (str) and ``image`` (bytes).
    """
    if not items:
        return
    import base64

    cells = []
    for item in items:
        encoded = base64.b64encode(item["image"]).decode()
        label = item.get("label", "")
        cells.append(
            '<div class="cm-tray-item">'
            f'<img src="data:image/png;base64,{encoded}" alt="{label}" />'
            f'<span class="cm-tray-label">{label}</span>'
            "</div>"
        )
    st.markdown(
        f'<div class="cm-tray">{"".join(cells)}</div>', unsafe_allow_html=True
    )


def sticky_panel(key: str = "cm-card-look-panel", title: str | None = None):
    """Return a keyed card container that sticks to the top while scrolling.

    Stickiness is applied via CSS to the parent column (see :func:`inject_css`),
    so the key must be ``cm-card-look-panel`` for the default rule to match.
    """
    return card(key, title)
