import streamlit as st
from frontend import api_utils, styles
from frontend.views import clothing_form
from closet_muse.domain import enums


# Garment types offered in the onboarding dropdown = the main clothing categories.
# Each maps to the natural noun used in the image-generation prompt (the model reads
# this text verbatim, so it must read like a garment, not like a category label).
GARMENT_TYPE_NOUNS = {
    enums.WomenClothingMainCategory.TOPS: "top",
    enums.WomenClothingMainCategory.BOTTOMS: "bottom",
    enums.WomenClothingMainCategory.ONE_PIECE: "one-piece garment",
    enums.WomenClothingMainCategory.FOOTWEAR: "shoes",
    enums.WomenClothingMainCategory.OUTERWEAR: "outerwear garment",
    enums.WomenClothingMainCategory.LOUNGEWEAR: "loungewear",
    enums.WomenClothingMainCategory.ACCESSORIES: "accessory",
}

# Mannequin forms offered in the onboarding dropdown, mapped to friendly labels.
MANNEQUIN_FORM_LABELS = {
    "full_front": "Full body · front",
    "full_side": "Full body · side",
    "top": "Upper body (head to hips)",
    "bottom": "Lower body (waist to feet)",
    "feet": "Below knees & feet",
}

# Sensible default mannequin form per garment type (still user-overridable).
# Categories without an obvious form fall back to "full_front" via .get(...).
DEFAULT_FORM_BY_GARMENT = {
    enums.WomenClothingMainCategory.TOPS: "top",
    enums.WomenClothingMainCategory.BOTTOMS: "bottom",
    enums.WomenClothingMainCategory.ONE_PIECE: "full_front",
    enums.WomenClothingMainCategory.FOOTWEAR: "feet",
    enums.WomenClothingMainCategory.OUTERWEAR: "top",
    enums.WomenClothingMainCategory.LOUNGEWEAR: "full_front",
    enums.WomenClothingMainCategory.ACCESSORIES: "full_front",
}


class OnboardWardrobe:
    def __init__(self, user_id: int):
        self.user_id = user_id

        # store generated clothing image
        if "clothing_image" not in st.session_state:
            st.session_state.clothing_image = None

        # attributes extracted from the uploaded photo(s)
        if "clothing_attributes" not in st.session_state:
            st.session_state.clothing_attributes = None

        # fingerprint of the uploaded photo set, used to reset stale previews
        if "onboard_upload_signature" not in st.session_state:
            st.session_state.onboard_upload_signature = ()

    @staticmethod
    def _upload_signature(uploads) -> tuple:
        """Fingerprint the uploaded files so a changed set can clear stale state."""
        return tuple(
            (photo.name, len(photo.getvalue())) for photo in (uploads or [])
        )

    @staticmethod
    def _default_form_for(garment_type: enums.WomenClothingMainCategory) -> str:
        """The sensible default mannequin form for a garment type."""
        return DEFAULT_FORM_BY_GARMENT.get(garment_type, "full_front")

    def _on_garment_type_change(self) -> None:
        """Snap the mannequin form to the new garment type's default.

        Streamlit keeps a keyed widget's stored value over its ``index``, so the
        form would otherwise stay on its first value when the category changes.
        Rewriting the key here keeps the two controls in sync; the user can still
        override the form afterwards (a manual change does not re-trigger this).
        """
        st.session_state.mannequin_form = self._default_form_for(
            st.session_state.garment_type
        )

    def display_image_generator(self):
        uploads = st.file_uploader(
            "Upload one or more photos of your clothing item",
            type=["png", "jpg", "jpeg"],
            accept_multiple_files=True,
            key="onboard_uploader",
            help=(
                "Add photos of the same item from different angles (front, back, "
                "and close-ups). The first photo is used as the primary reference."
            ),
        )

        # What to transfer and which mannequin to dress it on.
        cols = st.columns([5, 5])
        with cols[0]:
            garment_type = st.selectbox(
                "Garment type",
                options=list(enums.WomenClothingMainCategory),
                format_func=lambda category: category.value,
                key="garment_type",
                on_change=self._on_garment_type_change,
            )
        with cols[1]:
            mannequin_form = st.selectbox(
                "Mannequin form",
                options=list(MANNEQUIN_FORM_LABELS),
                index=list(MANNEQUIN_FORM_LABELS).index(
                    self._default_form_for(garment_type)
                ),
                format_func=lambda x: MANNEQUIN_FORM_LABELS[x],
                key="mannequin_form",
            )

        # Clear the preview and attributes whenever the uploaded set changes.
        signature = self._upload_signature(uploads)
        if signature != st.session_state.onboard_upload_signature:
            st.session_state.onboard_upload_signature = signature
            st.session_state.clothing_image = None
            st.session_state.clothing_attributes = None

        cols = st.columns([5, 5])
        with cols[0]:
            if uploads:
                thumb_cols = st.columns(min(len(uploads), 3))
                for index, photo in enumerate(uploads):
                    with thumb_cols[index % len(thumb_cols)]:
                        caption = "Primary photo" if index == 0 else f"Photo {index + 1}"
                        st.image(photo, caption=caption, width="stretch")
            else:
                st.caption("Your uploaded photos will appear here.")
        with cols[1]:
            if st.session_state.clothing_image is not None:
                st.image(
                    st.session_state.clothing_image,
                    caption="Generated Preview",
                    width="stretch",
                )
            else:
                st.caption("Your generated preview will appear here.")

        if st.button("Generate Preview", width="stretch", disabled=not uploads):
            if not uploads:
                st.error("Please upload at least one image first.")
                return

            with st.status("Hang on while we polish your clothing ...", expanded=True):
                st.write("Washing and ironing ...")

                response = api_utils.polish_clothing_image(
                    list(uploads), GARMENT_TYPE_NOUNS[garment_type], mannequin_form
                )
                if response.status_code != 200 or not response.content:
                    st.error("Failed to generate preview.")
                    return

                generated_image = api_utils.NamedBytesIO(response.content, "preview.png")
                st.session_state.clothing_image = generated_image

                st.write("Analyzing for details ...")
                attrs = api_utils.generate_clothing_attributes(list(uploads))
                st.session_state.clothing_attributes = attrs

                # Let the extracted category drive the Garment type dropdown so the
                # item lands in the same main category it was polished/detected as.
                if attrs is not None:
                    st.session_state.garment_type = attrs.main_category
                st.rerun()

    @st.fragment
    def display_clothing_form(self):
        attrs = st.session_state.clothing_attributes

        # CATEGORY — driven by the Garment type selection in the preview step
        # (which itself is pre-filled from the extracted attributes).
        main_category = st.session_state.get(
            "garment_type", list(enums.WomenClothingMainCategory)[0]
        )

        clothing_item = clothing_form.render_clothing_fields(
            attrs, main_category=main_category
        )

        # Submit button
        if st.button("Add Clothing Item", width="stretch"):
            api_utils.add_clothing_item(
                user_id=self.user_id,
                clothing=clothing_item,
                image=st.session_state.clothing_image,
            )
            label = clothing_item.sub_category or clothing_item.main_category.value
            st.success(f"Added {label} to your wardrobe!")

    def render(self):
        cols = st.columns([60, 40], border=False)

        with cols[0]:
            with styles.card("cm-card-upload"):
                styles.section_label("Add a piece")
                self.display_image_generator()

        with cols[1]:
            with styles.card("cm-card-details"):
                styles.section_label("Item details")
                self.display_clothing_form()


def run(user_id: int = 1):
    OnboardWardrobe(user_id).render()


# Streamlit executes this file as the page entrypoint, so render on import.
run()