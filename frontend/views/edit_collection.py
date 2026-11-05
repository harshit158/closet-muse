"""Edit Collection page: browse every wardrobe item and edit or delete it.

Kept separate from the Generate Outfit page so browsing/selecting for outfit
generation stays untouched by management concerns.
"""

import streamlit as st

from frontend import api_utils, styles
from frontend.views import clothing_form
from closet_muse.domain import enums, schemas
from closet_muse.settings import settings

# Number of item cards per row.
GRID_COLUMNS = 4


def _forget_selection(item: dict) -> None:
    """Drop the item from the Generate Outfit selection, if it was selected."""
    selections = st.session_state.get("clothing_selections", {})
    for key, selected in list(selections.items()):
        if selected and selected.get("id") == item["id"]:
            selections.pop(key, None)


def _reset_gallery_widgets() -> None:
    """Clear the Generate Outfit gallery widget state.

    Its ``image_select`` widgets store a selected index per category; after an
    item is removed that index can point past the end of the (now shorter)
    list. Clearing the keys lets the widgets re-initialise safely.
    """
    for category in enums.WomenClothingMainCategory:
        st.session_state.pop(category.name, None)


@st.dialog("Edit item", width="large")
def _edit_dialog(item: dict) -> None:
    defaults = schemas.ClothingBase(**item)
    edited = clothing_form.render_clothing_fields(
        defaults,
        key_prefix=f"edit_{item['id']}",
        show_category=True,
        main_category=defaults.main_category,
    )

    cols = st.columns(2)
    with cols[0]:
        if st.button("Save changes", type="primary", width="stretch"):
            payload = schemas.ClothingUpdate(
                **edited.model_dump(exclude={"image_path"})
            )
            api_utils.update_clothing_item(item["id"], payload)
            _forget_selection(item)
            _reset_gallery_widgets()
            st.rerun()
    with cols[1]:
        if st.button("Cancel", width="stretch"):
            st.rerun()


@st.dialog("Delete item")
def _delete_dialog(item: dict) -> None:
    label = item.get("sub_category") or item["main_category"]
    st.write(f"Delete **{label}** from your wardrobe? This can't be undone.")

    cols = st.columns(2)
    with cols[0]:
        if st.button("Delete", type="primary", width="stretch"):
            api_utils.delete_clothing_item(item["id"])
            _forget_selection(item)
            _reset_gallery_widgets()
            st.rerun()
    with cols[1]:
        if st.button("Cancel", width="stretch"):
            st.rerun()


class EditCollection:
    def __init__(self, user_id: int = 1):
        self.user_id = user_id

    def _fetch_items(self) -> list[dict]:
        return api_utils.list_clothing(self.user_id)

    def _image_bytes(self, item: dict) -> bytes | None:
        """Fetch an item's stored image; a missing file must not break the grid."""
        try:
            return api_utils.fetch_image(
                settings.storage_bucket_clothing, item["image_path"]
            )
        except Exception:  # noqa: BLE001 - surfaced as a placeholder in the card
            return None

    def _render_card(self, item: dict) -> None:
        image = self._image_bytes(item)
        if image is not None:
            st.image(image, width="stretch")
        else:
            styles.empty_state("Image unavailable", emoji="🖼️")

        label = item.get("sub_category") or item["main_category"]
        st.markdown(f'<p class="cm-item-label">{label}</p>', unsafe_allow_html=True)

        cols = st.columns(2)
        with cols[0]:
            if st.button(
                "Edit",
                key=f"edit_btn_{item['id']}",
                width="stretch",
                icon=":material/edit:",
            ):
                # Re-seed the form from the item's current values, discarding
                # any values left over from a previously cancelled edit.
                clothing_form.clear_fields(f"edit_{item['id']}")
                _edit_dialog(item)
        with cols[1]:
            if st.button(
                "Delete",
                key=f"delete_btn_{item['id']}",
                width="stretch",
                icon=":material/delete:",
            ):
                _delete_dialog(item)

    def _render_grid(self, items: list[dict]) -> None:
        for start in range(0, len(items), GRID_COLUMNS):
            row = items[start : start + GRID_COLUMNS]
            cols = st.columns(GRID_COLUMNS)
            for col, item in zip(cols, row):
                with col:
                    with styles.card(f"cm-card-item-{item['id']}"):
                        self._render_card(item)

    def render(self) -> None:
        items = self._fetch_items()
        with styles.card("cm-card-edit-collection"):
            styles.section_label(
                f"Edit Collection{styles.stat_badge(len(items))}"
            )
            if not items:
                styles.empty_state("Your wardrobe is empty", emoji="🧺")
                return
            self._render_grid(items)


def run(user_id: int = 1):
    EditCollection(user_id).render()


# Streamlit executes this file as the page entrypoint, so render on import.
run()
