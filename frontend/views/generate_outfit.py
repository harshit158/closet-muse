import streamlit as st
from glob import glob
from io import BytesIO
from dataclasses import dataclass
from typing import List, Optional
from streamlit_image_select import image_select
from backend.generate_image import generate_fashion_image
from backend.db import supabase
from backend.types import WomenClothingMainCategory
from backend.models import Clothing, ClothingWithImage
from backend.settings import settings
from collections import defaultdict
from PIL import Image

@dataclass
class OutfitGenerator:
    MODEL_PATH: str = "assets/model3.jpg"
    CATEGORY_DISPLAY_RANK = {category: rank for rank, category in enumerate(WomenClothingMainCategory)}
    
    def __init__(self):
        # store selected categories
        if "category_selections" not in st.session_state:
            st.session_state.category_selections = []
            
        # store selected clothing items
        if "clothing_selections" not in st.session_state:
            st.session_state.clothing_selections = defaultdict()

    def _get_clothing_count(self, category: WomenClothingMainCategory) -> int:
        """Get the number of clothing items for a given category."""
        
        response = (
            supabase.schema(settings.app_name).table("clothing") # TODO: don't hardcode table name
            .select("*")
            .eq("main_category", category.name)
            .execute()
        )

        return len(response.data)
    
    def display_category_checkboxes(self) -> None:
        """Display category checkboxes in the given container."""
        st.subheader("Select Category")
        
         # display checkboxes for each category
        for category in WomenClothingMainCategory:
            total_clothing = self._get_clothing_count(category)
            label = f"({total_clothing}) {category.value}"
            if st.checkbox(label=label, value=bool(total_clothing)):
                if category not in st.session_state.category_selections:
                    st.session_state.category_selections.append(category)
            else:
                if category in st.session_state.category_selections:
                    st.session_state.category_selections.remove(category)
                    self.reset_clothing_selection(category)

    def reset_clothing_selection(self, category: WomenClothingMainCategory) -> None:
        """Reset clothing selection for a given category."""
        st.session_state.clothing_selections.pop(category.value, None)

    def _download_image(self, image_path: str) -> BytesIO:
        image_name = image_path.split("/", 1)[1]
        image=supabase.storage.from_(settings.s3_bucket_clothing).download(image_name)
        return BytesIO(image)

    def fetch_clothings(self, category: WomenClothingMainCategory) -> list[ClothingWithImage]:
        response = (
            supabase.schema(settings.app_name).table("clothing")
            .select("*")
            .eq("main_category", category.name)
            .execute()
        )

        clothings = [ClothingWithImage(clothing=Clothing(**item)) for item in response.data]
        for clothing in clothings:
            clothing.image_data = self._download_image(clothing.clothing.image_path).getvalue()
        return clothings

    def display_wardrobe(self) -> None:
        """Display wardrobe items for selected categories."""
        st.subheader("Wardrobe")
        with st.container(height=800, border=True):
            sorted_categories = sorted(st.session_state.category_selections, key=lambda x: self.CATEGORY_DISPLAY_RANK[x])
            for main_category in sorted_categories:
                st.markdown(f"**{main_category.value}**")
                with st.container(height=220, horizontal=True):
                    clothings = self.fetch_clothings(main_category)
                    if clothings:
                        clothing_images = [Image.open(BytesIO(clothing.image_data)) for clothing in clothings]
                        img_idx = image_select("", clothing_images, use_container_width=False, key=main_category.name, return_value="index")

                        st.session_state.clothing_selections[main_category.value] = clothings[img_idx]

    def display_selected_clothings(self) -> None:
        """Display currently selected items."""
        st.subheader("Selected Items")
        with st.container(height=800, border=True, horizontal_alignment="center"):
            # sorted_selections = sorted(st.session_state.category_selections, key=lambda x: self.CATEGORY_DISPLAY_RANK[x])
            for category in self.CATEGORY_DISPLAY_RANK:
                if category.value in st.session_state.clothing_selections:
                    clothing = st.session_state.clothing_selections[category.value]
                    caption = f"{clothing.clothing.main_category} ({clothing.clothing.sub_category})"
                    st.image(clothing.image_data, caption=caption, width=200)

    def display_preview(self) -> None:
        """Display model preview and generation controls."""
        st.subheader("You look beautiful")
        model_placeholder = st.empty()

        with model_placeholder.container():
            st.image(self.MODEL_PATH, width=850)

        with st.container(horizontal=True):
            if st.button("Generate", width="stretch"):
                self.generate_outfit(model_placeholder)

            if st.button("Surprise Me", width="stretch"):
                self.generate_surprise_outfit(model_placeholder)
    
    def generate_outfit(self, placeholder) -> None:
        """Generate outfit based on selected items."""
        with st.spinner("Generating your outfit..."):
            image = generate_fashion_image(
                st.session_state.clothing_selections, 
                model_path=self.MODEL_PATH
            )
            if image:
                with placeholder.container():
                    st.image(image, width=850)
            else:
                st.error("Failed to generate outfit.")

    def generate_surprise_outfit(self, placeholder) -> None:
        """Generate surprise outfit (placeholder for future implementation)."""
        pass
    
    def render(self) -> None:
        """Main render method."""
        cols = st.columns([15, 30, 20, 30], border=False)

        # Category selection column
        with cols[0]:
            self.display_category_checkboxes()
        
        # Wardrobe display column
        with cols[1]:
            self.display_wardrobe()
        
        # Display selections
        with cols[2]:
            self.display_selected_clothings()
        
        # Preview and generation column
        with cols[3]:
            self.display_preview()

def run():
    OutfitGenerator().render()

if __name__ == "__main__":
    run()