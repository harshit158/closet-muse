import streamlit as st
from glob import glob
from io import BytesIO
from dataclasses import dataclass
from typing import List, Optional
from streamlit_image_select import image_select
from backend.generate_image import generate_fashion_image
from backend.db import supabase
from backend.types import WomenClothingMainCategory
from backend.settings import settings
from collections import defaultdict
from PIL import Image

@dataclass
class OutfitGenerator:
    DRESS_DIR: str = "assets/dress_images/"
    MODEL_PATH: str = "assets/model3.jpg"
    CATEGORY_DISPLAY_RANK = {category: rank for rank, category in enumerate(WomenClothingMainCategory)}
    
    def __init__(self):
        # store selected categories
        if "category_selections" not in st.session_state:
            st.session_state.category_selections = []
            
        # store selected clothing items
        if "clothing_selections" not in st.session_state:
            st.session_state.clothing_selections = defaultdict()

    def display_select_category(self) -> None:
        """Display category checkboxes in the given container."""
        st.subheader("Select Category")
        
         # display checkboxes for each category
        for category in WomenClothingMainCategory:
            if st.checkbox(category.value, value=False):
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

    def fetch_clothing_images(self, category: WomenClothingMainCategory) -> list[Image.Image]:
        response = (
            supabase.schema(settings.app_name).table(settings.s3_bucket_clothing)
            .select("main_category", "image_path")
            .eq("main_category", category.name)
            .execute()
        )
        
        items = response.data
        images = [self._download_image(item["image_path"]) for item in items]
        pil_images = [Image.open(img) for img in images]
        return pil_images

    def display_wardrobe(self) -> None:
        """Display wardrobe items for selected categories."""
        st.subheader("Wardrobe")
        with st.container(height=800, border=True):
            sorted_categories = sorted(st.session_state.category_selections, key=lambda x: self.CATEGORY_DISPLAY_RANK[x])
            for main_category in sorted_categories:
                st.markdown(f"**{main_category.value}**")
                with st.container(height=220, horizontal=True):
                    images = self.fetch_clothing_images(main_category)
                    if images:
                        img = image_select("", images, use_container_width=False, 
                                        key=main_category.name)

                        st.session_state.clothing_selections[main_category.value] = img
    
    def display_selected_items(self) -> None:
        """Display currently selected items."""
        st.subheader("Selected Items")
        with st.container(height=800, border=True, horizontal_alignment="center"):
            for category, img in st.session_state.clothing_selections.items():
                st.image(img, caption=category, width=200)

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
                st.session_state.selections, 
                model_path=self.MODEL_PATH
            )
            with placeholder.container():
                st.image(image, width=850)
    
    def generate_surprise_outfit(self, placeholder) -> None:
        """Generate surprise outfit (placeholder for future implementation)."""
        pass
    
    def render(self) -> None:
        """Main render method."""
        cols = st.columns([15, 30, 20, 30], border=False)

        # Category selection column
        with cols[0]:
            self.display_select_category()
        
        # Wardrobe display column
        with cols[1]:
            self.display_wardrobe()
        
        # Display selections
        with cols[2]:
            self.display_selected_items()
        
        # Preview and generation column
        with cols[3]:
            self.display_preview()

def run():
    generator = OutfitGenerator()
    generator.render()

if __name__ == "__main__":
    run()