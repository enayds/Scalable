import streamlit as st

# Navigation menu
st.set_page_config(page_title="NHS Scraper App", page_icon="🔍")
st.sidebar.title("📂 Navigation")
page = st.sidebar.selectbox("Choose a scraper", ["🏠 Home", "🧰 Trac Jobs", "💼 NHS Jobs"])

# Route to correct module
if page == "🏠 Home":
    st.title("🔍 NHS Job Scraper Hub")
    st.markdown("""
Welcome to the **NHS Job Scraper Hub**.

Use the menu on the left to switch between:
- 🧰 Trac Jobs
- 💼 NHS Jobs
""")

elif page == "🧰 Trac Jobs":
    import trac

elif page == "💼 NHS Jobs":
    import nhs
