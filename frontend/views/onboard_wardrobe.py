import streamlit as st
from frontend import api_utils
from backend import types
from PIL import Image
from io import BytesIO

def display_image_generator():
    image = st.file_uploader("Upload an image of your clothing item", type=["png", "jpg", "jpeg"])

    cols = st.columns([5, 5])
    with cols[0]:
        original_image_placeholder = st.empty()
    with cols[1]:
        generated_image_placeholder = st.empty()

    if image:
        original_image_placeholder.image(image, caption="Uploaded Image", use_container_width=True)
        generated_image_placeholder.image(image, caption="Generated Preview", use_container_width=True)

    if st.button("Generate Preview", width="stretch"):
        with st.spinner("Generating preview..."):
            if image:
                response = api_utils.generate_clothing_image(image)
                if response.status_code == 200 and response.content:
                    # If the API call is successful, display the generated image
                    generated_image = Image.open(BytesIO(response.content))
                    generated_image_placeholder.image(generated_image, caption="Generated Preview", use_container_width=True)
                else:
                    st.error("Failed to generate preview.")
            else:
                st.error("Please upload an image first.")

@st.fragment
def display_clothing_form():
    st.text("Add Clothing Item Details")
    
    # Initialize session state for category if not exists
    if 'main_category' not in st.session_state:
        st.session_state.main_category = list(types.WomenClothingMainCategory)[0]
    
    # Main category with session state
    main_category = st.selectbox(
        "Category", 
        options=list(types.WomenClothingMainCategory),
        format_func=lambda x: x.value,
        key='main_category'
    )
    
    # Dynamic subcategory based on main category
    sub_categories = types.CATEGORY_MAPPING[main_category]
    sub_category = st.selectbox(
        "Sub-category",
        options=list(sub_categories),
        format_func=lambda x: x.value
    )

    # Optional fields
    cols = st.columns([20, 80])
    with cols[0]:
        color = st.color_picker("Color (optional)")
    with cols[1]:
        material = st.selectbox(
            "Material (optional)",
            options=["", "Cotton", "Silk", "Wool", "Polyester", "Denim", "Leather", "Other"]
        )
    pattern = st.selectbox(
        "Pattern (optional)",
        options=["", "Solid", "Striped", "Floral", "Plaid", "Polka dot", "Other"]
    )
    brand = st.text_input("Brand (optional)")
    size = st.text_input("Size (optional)")
    season = st.selectbox(
        "Season (optional)",
        options=[""] + [season for season in types.Season],
        format_func=lambda x: x.value if x else ""
    )

    # Submit button
    if st.button("Add Clothing Item", use_container_width=True):
        clothing_item = {
            "main_category": main_category.value,
            "sub_category": sub_category.value,
            "color": color if color != "#000000" else None,
            "material": material if material else None,
            "pattern": pattern if pattern else None,
            "brand": brand if brand else None,
            "size": size if size else None,
            "season": season.value if season and season != "" else None
        }
        
        st.success(f"Added {sub_category.value} to your wardrobe!")
        st.write(clothing_item)

def run():
    cols = st.columns([60, 40], border=True)
    
    with cols[0]:
        display_image_generator()

    with cols[1]:
        display_clothing_form()

if __name__ == "__main__":
    run()