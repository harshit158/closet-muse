import streamlit as st
from io import BytesIO
from dataclasses import dataclass
from typing import ClassVar
from streamlit_image_select import image_select
from frontend import api_utils, styles
from closet_muse.domain.enums import WomenClothingMainCategory
from closet_muse.settings import settings
from PIL import Image


@st.cache_data(show_spinner=False)
def _fetch_image_cached(bucket: str, path: str) -> bytes:
    """Fetch an image once and reuse the bytes across reruns/sessions."""
    return api_utils.fetch_image(bucket, path)


@st.cache_data(show_spinner=False)
def _model_view_bytes(path: str, max_width: int = 900) -> bytes:
    """Load a model view once as a small JPEG.

    The source PNGs are ~2.5 MB each and Streamlit re-encodes them on every
    rerun, which made the carousel arrows feel sluggish. Downscaling once and
    handing Streamlit ready-made JPEG bytes keeps each arrow click snappy.
    """
    with Image.open(path) as img:
        img = img.convert("RGB")
        if img.width > max_width:
            height = round(img.height * max_width / img.width)
            img = img.resize((max_width, height), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=88, optimize=True)
        return buffer.getvalue()


@dataclass
class OutfitGenerator:
    user_id: int = 1
    # view name -> image path, in display order: left, center, right
    MODEL_VIEWS: ClassVar[dict[str, str]] = settings.model_image_views
    CATEGORY_DISPLAY_RANK = {category: rank for rank, category in enumerate(WomenClothingMainCategory)}

    def __init__(self, user_id: int = 1):
        self.user_id = user_id

        # store selected categories
        if "category_selections" not in st.session_state:
            st.session_state.category_selections = []

        # store selected clothing items (category value -> clothing dict)
        if "clothing_selections" not in st.session_state:
            st.session_state.clothing_selections = {}

        # index of the model photo shown in the "Your Look" carousel
        if "look_index" not in st.session_state:
            st.session_state.look_index = 0

        # generated outfit image (PIL); when set it replaces the carousel
        if "generated_outfit" not in st.session_state:
            st.session_state.generated_outfit = None

    def _clothing_count(self, category: WomenClothingMainCategory) -> int:
        """Get the number of clothing items for a given category."""
        return self.counts.get(category.name, 0)

    def display_category_pills(self) -> None:
        """Display the category selector as a horizontal multi-select pill bar."""
        self.counts = api_utils.clothing_counts(self.user_id)
        options = list(WomenClothingMainCategory)
        default = [c for c in options if self._clothing_count(c) > 0]

        selected = st.pills(
            "Categories",
            options=options,
            selection_mode="multi",
            default=default,
            format_func=lambda c: f"{c.value} · {self._clothing_count(c)}",
            key="category_pills",
            label_visibility="collapsed",
        )
        selected = selected or []

        # Sync the widget state back into session state, clearing any
        # clothing selection for categories that were just deselected.
        for category in options:
            if category in selected:
                if category not in st.session_state.category_selections:
                    st.session_state.category_selections.append(category)
            elif category in st.session_state.category_selections:
                st.session_state.category_selections.remove(category)
                self.reset_clothing_selection(category)

    def reset_clothing_selection(self, category: WomenClothingMainCategory) -> None:
        """Reset clothing selection for a given category."""
        st.session_state.clothing_selections.pop(category.value, None)

    def _download_image(self, image_path: str) -> BytesIO:
        data = _fetch_image_cached(settings.storage_bucket_clothing, image_path)
        return BytesIO(data)

    def fetch_clothings(self, category: WomenClothingMainCategory) -> list[dict]:
        return api_utils.list_clothing(self.user_id, main_category=category)

    def display_wardrobe(self) -> None:
        """Display the wardrobe gallery for the selected categories."""
        sorted_categories = sorted(
            st.session_state.category_selections,
            key=lambda x: self.CATEGORY_DISPLAY_RANK[x],
        )
        if not sorted_categories:
            styles.empty_state("Pick a category to see your pieces", emoji="🧺")
            return

        for main_category in sorted_categories:
            clothings = self.fetch_clothings(main_category)
            st.markdown(
                f'<p class="cm-section-label">{main_category.value}'
                f'{styles.stat_badge(len(clothings))}</p>',
                unsafe_allow_html=True,
            )
            if not clothings:
                styles.empty_state("Nothing here yet", emoji="👗")
                continue

            clothing_images = [
                Image.open(self._download_image(c["image_path"])) for c in clothings
            ]
            captions = [c.get("sub_category") or "" for c in clothings]
            img_idx = image_select(
                "",
                clothing_images,
                captions=captions,
                use_container_width=False,
                key=main_category.name,
                return_value="index",
            )

            st.session_state.clothing_selections[main_category.value] = clothings[img_idx]

    def _tray_items(self) -> list[dict]:
        """Build the thumbnail tray payload for the current selection."""
        items = []
        for category in self.CATEGORY_DISPLAY_RANK:
            clothing = st.session_state.clothing_selections.get(category.value)
            if clothing is not None:
                label = clothing.get("sub_category") or category.value
                items.append(
                    {
                        "label": label,
                        "image": self._download_image(clothing["image_path"]).getvalue(),
                    }
                )
        return items

    def display_selected_clothings(self) -> None:
        """Display currently selected items as a compact thumbnail tray."""
        items = self._tray_items()
        if not items:
            styles.empty_state("Your selected pieces will appear here", emoji="✨")
            return
        styles.thumb_tray(items)

    @st.fragment
    def display_look_panel(self) -> None:
        """Show the generated look, or the model-photo carousel when idle.

        Rendered as a fragment so the carousel arrows only rerun this panel
        instead of the whole page (which re-downloads the wardrobe gallery).
        """
        generated = st.session_state.get("generated_outfit")
        if generated is not None:
            st.image(generated, width="stretch")
            if st.button("Back to photos", width="stretch"):
                st.session_state.generated_outfit = None
                st.rerun(scope="fragment")
            return

        views = list(self.MODEL_VIEWS.items())
        index = min(max(st.session_state.look_index, 0), len(views) - 1)
        _, path = views[index]
        st.image(_model_view_bytes(path), width="stretch")

        with st.container(horizontal=True):
            if st.button(
                "◀",
                key="look_prev",
                disabled=index == 0,
                width="stretch",
            ):
                st.session_state.look_index = index - 1
                st.rerun(scope="fragment")
            if st.button(
                "▶",
                key="look_next",
                disabled=index == len(views) - 1,
                width="stretch",
            ):
                st.session_state.look_index = index + 1
                st.rerun(scope="fragment")

    def display_preview(self) -> None:
        """Display generation controls."""
        with st.container(horizontal=True):
            if st.button("Generate", width="stretch", type="primary"):
                self.generate_outfit()

            if st.button("Surprise Me", width="stretch"):
                self.generate_surprise_outfit()

    def generate_outfit(self) -> None:
        """Generate outfit based on selected items."""
        clothing_ids = [
            str(c["id"]) for c in st.session_state.clothing_selections.values()
        ]
        if not clothing_ids:
            st.warning("Select at least one clothing item first.")
            return

        with st.spinner("Generating your outfit..."):
            image = api_utils.generate_outfit(self.user_id, clothing_ids)
        if image:
            st.session_state.generated_outfit = image
            st.rerun()
        else:
            st.error("Failed to generate outfit.")

    def generate_surprise_outfit(self) -> None:
        """Generate surprise outfit (placeholder for future implementation)."""
        pass

    def render(self) -> None:
        """Main render method — Studio / Canvas layout."""
        cols = st.columns([42, 24, 34], border=False)

        # Column 1 — categories + wardrobe
        with cols[0]:
            with styles.card("cm-card-categories"):
                styles.eyebrow("Categories")
                self.display_category_pills()

            with styles.card("cm-card-wardrobe"):
                styles.section_label("Wardrobe")
                self.display_wardrobe()

        # Column 2 — selected pieces
        with cols[1]:
            with styles.card("cm-card-selected"):
                styles.section_label("Selected pieces")
                self.display_selected_clothings()

        # Column 3 — your look (sticky)
        with cols[2]:
            with styles.sticky_panel("cm-card-look-panel"):
                styles.eyebrow("Your Look")
                self.display_look_panel()
                self.display_preview()


def run(user_id: int = 1):
    OutfitGenerator(user_id).render()


# Streamlit executes this file as the page entrypoint, so render on import.
run()