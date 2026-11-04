import streamlit as st
from frontend import api_utils, styles
from closet_muse.domain import enums, schemas


# Garment types offered in the onboarding dropdown, mapped to the noun used in the prompt.
GARMENT_TYPE_LABELS = {
    "top": "Top",
    "bottom": "Bottom",
    "full": "Full / Dress",
    "footwear": "Footwear (shoes)",
}

# Mannequin forms offered in the onboarding dropdown, mapped to friendly labels.
MANNEQUIN_FORM_LABELS = {
    "full_front": "Full body · front",
    "full_side": "Full body · side",
    "top": "Upper body (head to hips)",
    "bottom": "Lower body (waist to feet)",
    "feet": "Below knees & feet",
}

# Sensible default mannequin form for each garment type (still user-overridable).
DEFAULT_FORM_BY_GARMENT = {
    "top": "top",
    "bottom": "bottom",
    "full": "full_front",
    "footwear": "feet",
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
                options=list(GARMENT_TYPE_LABELS),
                format_func=lambda x: GARMENT_TYPE_LABELS[x],
                key="garment_type",
            )
        with cols[1]:
            mannequin_form = st.selectbox(
                "Mannequin form",
                options=list(MANNEQUIN_FORM_LABELS),
                index=list(MANNEQUIN_FORM_LABELS).index(DEFAULT_FORM_BY_GARMENT[garment_type]),
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
                    list(uploads), garment_type, mannequin_form
                )
                if response.status_code != 200 or not response.content:
                    st.error("Failed to generate preview.")
                    return

                generated_image = api_utils.NamedBytesIO(response.content, "preview.png")
                st.session_state.clothing_image = generated_image

                st.write("Analyzing for details ...")
                st.session_state.clothing_attributes = api_utils.generate_clothing_attributes(
                    list(uploads)
                )
                st.rerun()

    @st.fragment
    def display_clothing_form(self):
        # Initialize session state for category if not exists
        if 'main_category' not in st.session_state:
            st.session_state.main_category = list(enums.WomenClothingMainCategory)[0]

        attrs = st.session_state.clothing_attributes

        # CATEGORY
        index = (
            list(enums.WomenClothingMainCategory).index(attrs.main_category)
            if attrs is not None
            else None
        )
        main_category = st.selectbox(
            "Category",
            index=index,
            options=list(enums.WomenClothingMainCategory),
            format_func=lambda x: x.value
        )

        # SUB CATEGORY
        sub_categories = enums.CATEGORY_MAPPING.get(main_category, [])
        sub_category = st.selectbox(
            "Sub-category",
            index=None,
            options=list(sub_categories),
            format_func=lambda x: x.value
        )

        # COLOR
        cols = st.columns([20, 80])
        with cols[0]:
            value = attrs.color if attrs is not None else None
            color = st.text_input("Color (optional)", value=value)

        # MATERIAL
        index = (
            list(enums.Material).index(attrs.material)
            if (attrs is not None and attrs.material)
            else None
        )
        with cols[1]:
            material = st.selectbox(
                "Material (optional)",
                index=index,
                options=list(enums.Material),
                format_func=lambda x: x.value
            )

        # PATTERN
        index = (
            list(enums.Pattern).index(attrs.pattern)
            if (attrs is not None and attrs.pattern)
            else None
        )
        pattern = st.selectbox(
            "Pattern (optional)",
            index=index,
            options=list(enums.Pattern),
            format_func=lambda x: x.value
        )

        # BRAND
        brand = st.text_input("Brand (optional)")

        # SIZE
        size = st.text_input("Size (optional)")

        # SEASON
        index = (
            list(enums.Season).index(attrs.season)
            if (attrs is not None and attrs.season)
            else None
        )
        season = st.selectbox(
            "Season (optional)",
            index=index,
            options=list(enums.Season),
            format_func=lambda x: x.value if x else ""
        )

        # DESCRIPTION
        value = attrs.description if attrs is not None else None
        description = st.text_area("Description (optional)", value=value)

        # Submit button
        if st.button("Add Clothing Item", width="stretch"):
            clothing_item = schemas.ClothingBase(
                main_category=main_category,
                sub_category=sub_category,
                color=color if color else None,
                material=material if material else None,
                pattern=pattern if pattern else None,
                brand=brand if brand else None,
                size=size if size else None,
                season=season if season else None,
                description=description if description else None
            )

            api_utils.add_clothing_item(
                user_id=self.user_id,
                clothing=clothing_item,
                image=st.session_state.clothing_image,
            )
            st.success(f"Added {sub_category.value} to your wardrobe!")

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