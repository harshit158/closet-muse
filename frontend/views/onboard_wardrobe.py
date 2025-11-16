import streamlit as st
from frontend import api_utils
from backend import models, types


class OnboardWardrobe:
    def __init__(self):
        # store generated clothing image
        if "clothing_image" not in st.session_state:
            st.session_state.clothing_image = None
            
    def display_image_generator(self):
        image = st.file_uploader("Upload an image of your clothing item", type=["png", "jpg", "jpeg"])

        cols = st.columns([5, 5])
        with cols[0]:
            original_image_placeholder = st.empty()
        with cols[1]:
            generated_image_placeholder = st.empty()

        if image:
            original_image_placeholder.image(image, caption="Uploaded Image", width="stretch")
            generated_image_placeholder.image(image, caption="Generated Preview", width="stretch")

        if st.button("Generate Preview", width="stretch"):
            if not image:
                st.error("Please upload an image first.")
            else:    
                with st.status("Hang on while we polish your clothing ...", expanded=True) as status:
                    st.write("Washing and ironing ...")
                    generated_image = image
                    st.session_state.clothing_image = generated_image
                    generated_image_placeholder.image(generated_image, caption="Generated Preview", width="stretch")
                    
                    st.write("Analyzing for details ...")
                    self.clothing_attributes = api_utils.generate_clothing_attributes(generated_image)
                    st.write(self.clothing_attributes)
                    # response = api_utils.generate_clothing_image(image)
                    # if response.status_code == 200 and response.content:
                    #     generated_image = Image.open(BytesIO(response.content))
                    #     generated_image_placeholder.image(generated_image, caption="Generated Preview", width="stretch")
                    # else:
                    #     st.error("Failed to generate preview.")

        
    @st.fragment
    def display_clothing_form(self):
        st.text("Add Clothing Item Details")
        
        # Initialize session state for category if not exists
        if 'main_category' not in st.session_state:
            st.session_state.main_category = list(types.WomenClothingMainCategory)[0]
        
        # CATEGORY
        index = list(types.WomenClothingMainCategory).index(self.clothing_attributes.main_category) if hasattr(self, "clothing_attributes") else None
        main_category = st.selectbox(
            "Category",
            index=index,
            options=list(types.WomenClothingMainCategory),
            format_func=lambda x: x.value
        )
        
        # SUB CATEGORY
        sub_categories = types.CATEGORY_MAPPING.get(main_category, [])
        sub_category = st.selectbox(
            "Sub-category",
            index=None,
            options=list(sub_categories),
            format_func=lambda x: x.value
        )

        # COLOR
        cols = st.columns([20, 80])
        with cols[0]:
            value = self.clothing_attributes.color if hasattr(self, "clothing_attributes") else None
            color = st.text_input("Color (optional)", value=value)
        
        # MATERIAL
        index = list(types.Material).index(self.clothing_attributes.material) if (hasattr(self, "clothing_attributes") and self.clothing_attributes.material) else None
        with cols[1]:
            material = st.selectbox(
                "Material (optional)",
                index=index,
                options=list(types.Material),
                format_func=lambda x: x.value
            )
        
        # PATTERN
        index = list(types.Pattern).index(self.clothing_attributes.pattern) if (hasattr(self, "clothing_attributes") and self.clothing_attributes.pattern) else None
        pattern = st.selectbox(
            "Pattern (optional)", 
            index=index,
            options=list(types.Pattern),
            format_func=lambda x: x.value
        )
        
        # BRAND
        brand = st.text_input("Brand (optional)")
        
        # SIZE
        size = st.text_input("Size (optional)")
        
        # SEASON
        index = list(types.Season).index(self.clothing_attributes.season) if (hasattr(self, "clothing_attributes") and self.clothing_attributes.season) else None
        season = st.selectbox(
            "Season (optional)",
            index=index,
            options=[season for season in types.Season],
            format_func=lambda x: x.value if x else ""
        )

        # Submit button
        if st.button("Add Clothing Item", width="stretch"):
            clothing_item = models.ClothingBase(
                main_category=main_category,
                sub_category=sub_category,
                color=color if color  else None,
                material=material if material else None,
                pattern=pattern if pattern else None,
                brand=brand if brand else None,
                size=size if size else None,
                season=season if season and season != "" else None
            )

            api_utils.add_clothing_item(user_id=1, clothing=clothing_item, image=st.session_state.clothing_image)
            st.success(f"Added {sub_category.value} to your wardrobe!")
            st.write(clothing_item)
    
    def render(self):
        cols = st.columns([60, 40], border=True)
    
        with cols[0]:
            self.display_image_generator()

        with cols[1]:
            self.display_clothing_form()

def run():
    OnboardWardrobe().render()

if __name__ == "__main__":
    run()