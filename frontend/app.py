import streamlit as st
from glob import glob
from streamlit_image_select import image_select
from backend.generate_image import generate_fashion_image

st.set_page_config(layout="wide")

st.title("ClosetMuse")

cols = st.columns([10, 50, 30, 10], border=False)

st.session_state["selections"] = []

DRESS_DIR = "../assets/dress_images/"

with cols[1]:
    with st.container(height=600, border=True):
        if st.checkbox("Top", value=True):
            with st.container(horizontal=True, height=210):
                img_paths = glob(f"{DRESS_DIR}top/*.png")
                img = image_select("", img_paths, use_container_width=False, key="tops")
                st.session_state["selections"].append(img)
        
        # if st.checkbox("Bottoms", value=True):
        #     with st.container(horizontal=True, height=210):
        #         img_paths = glob(f"{DRESS_DIR}bottoms/*.png")
        #         img = image_select("", img_paths, use_container_width=False, key="bottoms")
        #         st.session_state["selections"].append(img)
        
        if st.checkbox("Sweater", value=True):
            with st.container(horizontal=True, height=210):
                img_paths = glob(f"{DRESS_DIR}sweater/*.png")
                img = image_select("", img_paths, use_container_width=False, key="sweater")
                st.session_state["selections"].append(img)
        
        if st.checkbox("Jacket", value=True):
            with st.container(horizontal=True, height=210):
                img_paths = glob(f"{DRESS_DIR}jacket/*.png")
                img = image_select("", img_paths, use_container_width=False, key="jacket")
                st.session_state["selections"].append(img)
    
    with st.container(height=300, border=True, horizontal=True):
        for img in st.session_state["selections"]:
            st.image(img, width=200)

with cols[-2]:
    st.subheader("You look beautiful")
    model_placeholder = st.empty()
    with model_placeholder.container():
        st.image("../assets/model3.jpg", width=850)
    st.container()
    
    with st.container(horizontal=True):
        if st.button("Generate", use_container_width=True):
            with st.spinner("Generating your outfit..."):
                image = generate_fashion_image(st.session_state["selections"], model_path="../assets/model3.jpg")
            
            with model_placeholder.container():
                st.image(image, width=850)

        if st.button("Surprise Me", use_container_width=True):
            pass