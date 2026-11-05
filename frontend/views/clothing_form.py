"""Shared clothing attribute form fields.

Both the onboarding flow (Add to Collection) and the edit dialog (Edit
Collection) render the same set of attribute widgets, so they live here to
keep the two in lockstep.
"""

import streamlit as st

from closet_muse.domain import enums, schemas


def _index_of(options: list, value: str | None) -> int | None:
    """Index of the option whose ``.value`` matches ``value`` (or ``None``)."""
    if value is None:
        return None
    for index, option in enumerate(options):
        if option.value == value:
            return index
    return None


def clear_fields(key_prefix: str, keep: tuple[str, ...] = ()) -> None:
    """Drop any stored widget values for a form prefix.

    Call this right before opening a dialog so the form re-seeds from the
    item's current values instead of restoring a previous (possibly cancelled)
    edit. Do NOT call it on every dialog render — that would wipe in-progress
    input, since interacting with a dialog widget reruns the dialog function.

    ``keep`` names widgets whose stored value must survive (e.g. the category
    selectbox that triggered the reset — popping its own key would revert the
    user's just-made selection on the next rerun).
    """
    prefix = f"{key_prefix}_"
    for key in [key for key in st.session_state if key.startswith(prefix)]:
        if key[len(prefix):] in keep:
            continue
        st.session_state.pop(key, None)


def render_clothing_fields(
    defaults: schemas.ClothingBase | None = None,
    *,
    key_prefix: str | None = None,
    show_category: bool = False,
    main_category: enums.WomenClothingMainCategory | None = None,
) -> schemas.ClothingBase:
    """Render the clothing attribute widgets and return the entered values.

    ``defaults`` pre-fills every field (used by the edit dialog). ``key_prefix``
    namespaces the widget keys so the same form can appear in more than one
    place without collisions; when omitted the widgets use Streamlit's
    auto-generated keys (the onboarding form relies on this). When
    ``show_category`` is true the main category is editable; otherwise
    ``main_category`` is used as-is.
    """

    def _key(name: str) -> str | None:
        return f"{key_prefix}_{name}" if key_prefix else None

    if show_category:
        categories = list(enums.WomenClothingMainCategory)
        main_category = st.selectbox(
            "Category",
            options=categories,
            index=_index_of(
                categories, main_category.value if main_category else None
            ),
            format_func=lambda category: category.value,
            key=_key("main_category"),
            on_change=clear_fields,
            args=(key_prefix, ("main_category",)) if key_prefix else (),
        )

    main_category = main_category or list(enums.WomenClothingMainCategory)[0]

    # SUB CATEGORY
    sub_categories = list(enums.CATEGORY_MAPPING.get(main_category, []))
    sub_category = st.selectbox(
        "Sub-category",
        index=_index_of(sub_categories, defaults.sub_category if defaults else None),
        options=sub_categories,
        format_func=lambda x: x.value,
        key=_key("sub_category"),
    )

    # COLOR + MATERIAL
    cols = st.columns([20, 80])
    with cols[0]:
        color = st.text_input(
            "Color (optional)",
            value=defaults.color if defaults else None,
            key=_key("color"),
        )
    with cols[1]:
        material = st.selectbox(
            "Material (optional)",
            index=_index_of(
                list(enums.Material),
                defaults.material.value if (defaults and defaults.material) else None,
            ),
            options=list(enums.Material),
            format_func=lambda x: x.value,
            key=_key("material"),
        )

    # PATTERN
    pattern = st.selectbox(
        "Pattern (optional)",
        index=_index_of(
            list(enums.Pattern),
            defaults.pattern.value if (defaults and defaults.pattern) else None,
        ),
        options=list(enums.Pattern),
        format_func=lambda x: x.value,
        key=_key("pattern"),
    )

    # BRAND
    brand = st.text_input(
        "Brand (optional)",
        value=defaults.brand if defaults else None,
        key=_key("brand"),
    )

    # SIZE
    size = st.text_input(
        "Size (optional)",
        value=defaults.size if defaults else None,
        key=_key("size"),
    )

    # SEASON
    season = st.selectbox(
        "Season (optional)",
        index=_index_of(
            list(enums.Season),
            defaults.season.value if (defaults and defaults.season) else None,
        ),
        options=list(enums.Season),
        format_func=lambda x: x.value if x else "",
        key=_key("season"),
    )

    # DESCRIPTION
    description = st.text_area(
        "Description (optional)",
        value=defaults.description if defaults else None,
        key=_key("description"),
    )

    return schemas.ClothingBase(
        main_category=main_category,
        sub_category=sub_category,
        color=color or None,
        material=material,
        pattern=pattern,
        brand=brand or None,
        size=size or None,
        season=season,
        description=description or None,
    )
