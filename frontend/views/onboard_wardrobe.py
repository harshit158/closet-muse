import streamlit as st
from frontend import api_utils, styles
from frontend.views import clothing_form
from closet_muse.domain import enums, schemas

# Namespace for the item-details widgets. It must NOT be "onboard":
# ``clothing_form.clear_fields`` matches by prefix, so that would also wipe the
# uploader and the upload-signature bookkeeping.
FORM_KEY_PREFIX = "onboard_form"


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
# Each form has a straight-on front image and a three-quarter tilted image; the
# garment is applied to both so the try-on model sees two perspectives.
MANNEQUIN_FORM_LABELS = {
    "face": "Head, neck & shoulders",
    "top": "Upper body (head to hips)",
    "full": "Full body",
    "bottom": "Lower body (waist to feet)",
    "feet": "Below knees & feet",
}

# Sensible default mannequin form per garment type (still user-overridable).
# Categories without an obvious form fall back to "full" via .get(...).
DEFAULT_FORM_BY_GARMENT = {
    enums.WomenClothingMainCategory.TOPS: "top",
    enums.WomenClothingMainCategory.BOTTOMS: "bottom",
    enums.WomenClothingMainCategory.ONE_PIECE: "full",
    enums.WomenClothingMainCategory.FOOTWEAR: "feet",
    enums.WomenClothingMainCategory.OUTERWEAR: "top",
    enums.WomenClothingMainCategory.LOUNGEWEAR: "full",
    enums.WomenClothingMainCategory.ACCESSORIES: "face",
}


class OnboardWardrobe:
    def __init__(self, user_id: int):
        self.user_id = user_id

        # store generated clothing images (front + three-quarter perspectives)
        if "clothing_image" not in st.session_state:
            st.session_state.clothing_image = None
        if "clothing_image_tilted" not in st.session_state:
            st.session_state.clothing_image_tilted = None

        # attributes extracted from the uploaded photo(s)
        if "clothing_attributes" not in st.session_state:
            st.session_state.clothing_attributes = None

        # Pending preview-generation request, recorded by the upload card and
        # consumed by the previews card (which renders after it). This lets the
        # status and the generated images appear together in the previews card.
        if "onboard_preview_request" not in st.session_state:
            st.session_state.onboard_preview_request = None

        # Error from the last failed preview generation, surfaced in the card.
        if "onboard_preview_error" not in st.session_state:
            st.session_state.onboard_preview_error = None

        # Bumped whenever the detail widgets must re-seed from the current
        # attributes. It is part of their keys, so a bump creates NEW widgets
        # (see ``_reset_form``).
        if "onboard_details_generation" not in st.session_state:
            st.session_state.onboard_details_generation = 0

        # fingerprint of the uploaded photo set, used to reset stale previews
        if "onboard_upload_signature" not in st.session_state:
            st.session_state.onboard_upload_signature = ()

    @staticmethod
    def _upload_signature(uploads) -> tuple:
        """Fingerprint the uploaded files so a changed set can clear stale state."""
        return tuple(
            (photo.name, len(photo.getvalue())) for photo in (uploads or [])
        )

    @property
    def _form_key_prefix(self) -> str:
        """Widget-key namespace for the detail form, unique per generation."""
        return f"{FORM_KEY_PREFIX}_{st.session_state.onboard_details_generation}"

    def _reset_form(self) -> None:
        """Make the detail widgets re-seed from the current attributes.

        Popping the widget keys is not enough: Streamlit restores a keyed
        widget's value from the frontend even when its ``session_state`` entry
        is gone, so the fields would keep showing the previous (empty) values
        until some unrelated rerun. Bumping the generation changes every key,
        which makes them brand-new widgets that take their value from
        ``defaults``.
        """
        st.session_state.onboard_details_generation += 1
        clothing_form.clear_fields(FORM_KEY_PREFIX)

    @staticmethod
    def _default_form_for(garment_type: enums.WomenClothingMainCategory) -> str:
        """The sensible default mannequin form for a garment type."""
        return DEFAULT_FORM_BY_GARMENT.get(garment_type, "full")

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

        # Clear the previews, attributes and detail fields whenever the uploaded
        # set changes. This runs before the details form is built (row 2), so
        # dropping its widget keys here is safe.
        signature = self._upload_signature(uploads)
        if signature != st.session_state.onboard_upload_signature:
            st.session_state.onboard_upload_signature = signature
            st.session_state.clothing_image = None
            st.session_state.clothing_image_tilted = None
            st.session_state.clothing_attributes = None
            st.session_state.onboard_preview_request = None
            st.session_state.onboard_preview_error = None
            self._reset_form()

        if uploads:
            thumb_cols = st.columns(min(len(uploads), 3))
            for index, photo in enumerate(uploads):
                with thumb_cols[index % len(thumb_cols)]:
                    caption = "Primary photo" if index == 0 else f"Photo {index + 1}"
                    st.image(photo, caption=caption, width="stretch")
        else:
            st.caption("Your uploaded photos will appear here.")

        if st.button("Generate Preview", width="stretch", disabled=not uploads):
            # The previews card renders AFTER this one, so record the request
            # instead of generating here: the status box and the resulting
            # images then both live in the "Generated previews" card, and no
            # extra rerun is needed (the card consumes it in this same run).
            st.session_state.onboard_preview_request = {
                "photos": [
                    api_utils.NamedBytesIO(photo.getvalue(), photo.name)
                    for photo in uploads
                ],
                "garment_noun": GARMENT_TYPE_NOUNS[garment_type],
                "mannequin_form": mannequin_form,
            }
            st.session_state.onboard_preview_error = None

    def _generate_previews(self, slot) -> None:
        """Run the pending preview request behind a plain spinner in ``slot``.

        The spinner stands in for the previews: no label text, just a ring
        centred in the card. It is dropped as soon as generation finishes so
        the card settles on the images (or on the error message).
        """
        request = st.session_state.onboard_preview_request
        st.session_state.onboard_preview_request = None
        st.session_state.onboard_preview_error = None

        views = None
        try:
            with slot.container(key="cm-preview-loader"):
                with st.spinner(""):
                    views = api_utils.polish_clothing_image(
                        request["photos"],
                        request["garment_noun"],
                        request["mannequin_form"],
                    )
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            st.session_state.onboard_preview_error = (
                f"Failed to generate preview: {exc}"
            )
        finally:
            slot.empty()

        if views is None:
            return

        st.session_state.clothing_image = api_utils.NamedBytesIO(
            views["front"], "preview_front.png"
        )
        st.session_state.clothing_image_tilted = api_utils.NamedBytesIO(
            views["tilted"], "preview_tilted.png"
        )

    def display_previews(self) -> None:
        """Render the generating status, then the generated previews.

        Both perspectives are generated together, so they are shown side by
        side: the try-on model uses both to read the garment's fit.
        """
        if st.session_state.onboard_preview_request is not None:
            self._generate_previews(st.empty())

        error = st.session_state.onboard_preview_error
        if error:
            st.error(error)

        previews = (
            ("Front view", st.session_state.clothing_image),
            ("Three-quarter view", st.session_state.clothing_image_tilted),
        )

        if all(image is None for _, image in previews):
            styles.empty_state("Your generated previews will appear here.", "✨")
            return

        preview_cols = st.columns(2)
        for preview_col, (caption, image) in zip(preview_cols, previews):
            with preview_col:
                if image is not None:
                    st.image(image, caption=caption, width="stretch")
                else:
                    st.caption(f"{caption} will appear here.")

    @st.fragment
    def display_clothing_form(self) -> schemas.ClothingBase:
        """Render the details card: extract action, then the attribute fields.

        Extraction is its own step, independent of preview generation, so it
        lives here next to the fields it fills. The button sits ABOVE the
        widgets, so the extraction can bump the form generation before the
        widgets are built and they seed from the new values in the same run.
        """
        uploads = st.session_state.get("onboard_uploader") or []

        # CATEGORY — driven by the Garment type selection in the preview step.
        main_category = st.session_state.get(
            "garment_type", list(enums.WomenClothingMainCategory)[0]
        )

        if st.button("Extract details", width="stretch", disabled=not uploads):
            with st.spinner("Reading the garment details ..."):
                try:
                    attrs = api_utils.generate_clothing_attributes(
                        list(uploads), main_category
                    )
                except Exception as exc:  # noqa: BLE001 - surfaced to the UI
                    st.error(f"Failed to extract details: {exc}")
                else:
                    st.session_state.clothing_attributes = attrs
                    # Re-seed the form from the new extraction (a re-run
                    # overwrites the form).
                    self._reset_form()

        attrs = st.session_state.clothing_attributes

        return clothing_form.render_clothing_fields(
            attrs,
            key_prefix=self._form_key_prefix,
            main_category=main_category,
            layout="grid",
        )

    def render(self):
        # Row 1: what to add (left) next to the generated previews (right).
        top = st.columns([55, 45], border=False)

        with top[0]:
            with styles.card("cm-card-upload"):
                styles.section_label("Add a piece")
                self.display_image_generator()

        with top[1]:
            with styles.card("cm-card-previews"):
                styles.section_label("Generated previews")
                self.display_previews()

        # Row 2: the item's attributes, spanning the full page width.
        with styles.card("cm-card-details"):
            styles.section_label("Item details")
            clothing_item = self.display_clothing_form()

        # The save action commits BOTH the previews and the details, so it sits
        # outside the details card rather than inside it.
        if st.button(
            "Add Clothing Item",
            width="stretch",
            disabled=st.session_state.clothing_image is None,
        ):
            api_utils.add_clothing_item(
                user_id=self.user_id,
                clothing=clothing_item,
                image=st.session_state.clothing_image,
                image_tilted=st.session_state.clothing_image_tilted,
            )
            label = clothing_item.sub_category or clothing_item.main_category.value
            st.success(f"Added {label} to your wardrobe!")


def run(user_id: int = 1):
    OnboardWardrobe(user_id).render()


# Streamlit executes this file as the page entrypoint, so render on import.
run()