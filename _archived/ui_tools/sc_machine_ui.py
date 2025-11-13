import streamlit as st
import requests
from pathlib import Path
import json

# Set page config
st.set_page_config(
    page_title="SC-Machine Client",
    page_icon=":brain:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Page selection in sidebar
page = st.sidebar.radio("Navigation", ["Documentation", "API Client"])

# Session state for persistent variables
if 'server_url' not in st.session_state:
    st.session_state.server_url = ""
if 'token' not in st.session_state:
    st.session_state.token = ""
if 'server_connected' not in st.session_state:
    st.session_state.server_connected = False
if 'token_created' not in st.session_state:
    st.session_state.token_created = False

# Documentation Page
if page == "Documentation":
    st.title("SC-Machine API Documentation")
    
    try:
        # Get the directory where this script is located, then go up one level to project root
        script_dir = Path(__file__).parent
        readme_path = script_dir.parent / "README.md"
        
        with open(readme_path, "r", encoding="utf-8") as f:
            readme_content = f.read()
        st.markdown(readme_content)
    except FileNotFoundError:
        st.warning("README.md file not found. Here's some basic documentation instead.")
        st.markdown("""
        ## SC-Machine API
        
        This is a knowledge base query and management system that allows:
        
        - Querying a semantic knowledge base
        - Uploading new knowledge bases in zip format
        - Secure token-based authentication
        
        ### Endpoints
        
        - `POST /query`: Submit a query to the knowledge base
        - `POST /upload/kb_zip`: Upload a new knowledge base
        - `POST /upload/kb_nlp_text`: Upload plain text knowledge base for NLP processing
        - `POST /create_token`: Generate an access token
        
        ### Authentication
        
        The API uses bearer token authentication. You need to:
        1. First create a token using `/create_token`
        2. Use this token in the `Authorization` header for all other requests
        """)

# API Client Page
elif page == "API Client":
    st.title("SC-Machine API Client")
    
    # Server connection section
    with st.expander("Server Connection", expanded=not st.session_state.server_connected):
        st.session_state.server_url = st.text_input(
            "Server URL",
            value=st.session_state.server_url,
            placeholder="http://localhost:9001",
            help="Enter the base URL of your SC-Machine API server"
        )
        
        if st.button("Check Connection"):
            if not st.session_state.server_url:
                st.error("Please enter a server URL")
            else:
                with st.spinner("Connecting to server..."):
                    try:
                        response = requests.get(f"{st.session_state.server_url.rstrip('/')}/")
                        if response.status_code == 200:
                            st.session_state.server_connected = True
                            st.success("Connected to server successfully!")
                            st.json(response.json())
                        else:
                            st.error(f"Server returned status code {response.status_code}")
                    except requests.exceptions.RequestException as e:
                        st.error(f"Failed to connect to server: {str(e)}")
    
    if not st.session_state.server_connected:
        st.warning("Please connect to a server first")
        st.stop()
    
    # Token management section
    with st.expander("Token Management", expanded=not st.session_state.token_created):
        create_token_disabled = st.session_state.token_created
        if st.button("Create New Token", disabled=create_token_disabled):
            with st.spinner("Creating token..."):
                try:
                    response = requests.post(f"{st.session_state.server_url.rstrip('/')}/create_token")
                    if response.status_code == 200:
                        data = response.json()
                        if data['status'] == "success":
                            st.session_state.token = data['token']
                            st.session_state.token_created = True
                            st.success("Token created successfully!")
                            st.warning("Copy this token now as it won't be shown again:")
                            st.code(data['token'], language="text")
                        else:
                            st.error(data.get('message', 'Unknown error'))
                    else:
                        st.error(f"Server returned status code {response.status_code}")
                except requests.exceptions.RequestException as e:
                    st.error(f"Failed to create token: {str(e)}")
        
        if not st.session_state.token_created:
            st.session_state.token = st.text_input(
                "Enter Existing Token",
                value=st.session_state.token,
                type="password",
                help="If you already have a token, enter it here"
            )
            if st.session_state.token:
                st.session_state.token_created = True
                st.success("Using existing token")
    
    if not st.session_state.token_created:
        st.warning("Please create or enter a token to continue")
        st.stop()
    
    # API interaction tabs (query, upload ZIP, upload NLP text)
    tab1, tab2, tab3 = st.tabs(["Query Knowledge Base", "Upload Knowledge Base (ZIP)", "Upload NLP Text"])

    with tab1:
        st.subheader("Query the Knowledge Base")
        query_text = st.text_area("Enter your query", height=100)
        humanize = st.checkbox("Humanize response", value=True)
        
        if st.button("Submit Query"):
            if not query_text.strip():
                st.error("Please enter a query")
            else:
                with st.spinner("Processing query..."):
                    try:
                        headers = {
                            "Authorization": f"Bearer {st.session_state.token}"
                        }
                        payload = {"text": query_text}
                        url = f"{st.session_state.server_url.rstrip('/')}/query?humanize={'true' if humanize else 'false'}"
                        response = requests.post(url, json=payload, headers=headers)
                        
                        if response.status_code == 200:
                            data = response.json()
                            if data['status'] == "success":
                                st.success("Query successful!")
                                if isinstance(data['response'], str):
                                    st.markdown(data['response'])
                                else:
                                    st.json(data['response'])
                            else:
                                st.error(f"Query failed: {data.get('message', '')}")
                        else:
                            st.error(f"Server returned status code {response.status_code}")
                    except requests.exceptions.RequestException as e:
                        st.error(f"Failed to submit query: {str(e)}")

    with tab2:
        st.subheader("Upload Knowledge Base (ZIP)")
        uploaded_file = st.file_uploader(
            "Choose a ZIP file",
            type="zip",
            accept_multiple_files=False
        )
        
        if st.button("Upload ZIP File"):
            if not uploaded_file:
                st.error("Please select a file to upload")
            else:
                with st.spinner("Uploading and processing knowledge base..."):
                    try:
                        headers = {
                            "Authorization": f"Bearer {st.session_state.token}"
                        }
                        files = {
                            "file": (uploaded_file.name, uploaded_file, "application/zip")
                        }
                        url = f"{st.session_state.server_url.rstrip('/')}/upload/kb_zip"
                        response = requests.post(url, files=files, headers=headers)
                        
                        if response.status_code == 200:
                            data = response.json()
                            if data['status'] == "success":
                                st.success("Knowledge base uploaded successfully!")
                                st.json(data.get('response', {}))
                            else:
                                st.error(f"Upload failed: {data.get('message', '')}")
                        else:
                            st.error(f"Server returned status code {response.status_code}")
                    except requests.exceptions.RequestException as e:
                        st.error(f"Failed to upload file: {str(e)}")

    with tab3:
        st.subheader("Upload Knowledge Base via NLP Text")
        nlp_text = st.text_area(
            "Enter plain text knowledge base to be processed (JSON body: {'text': ...})",
            height=150
        )
        if st.button("Upload NLP Text"):
            if not nlp_text.strip():
                st.error("Please enter some text")
            else:
                with st.spinner("Processing NLP knowledge base upload..."):
                    try:
                        headers = {
                            "Authorization": f"Bearer {st.session_state.token}"
                        }
                        payload = {"text": nlp_text}
                        url = f"{st.session_state.server_url.rstrip('/')}/upload/kb_nlp_text"
                        response = requests.post(url, json=payload, headers=headers)
                        
                        if response.status_code == 200:
                            data = response.json()
                            if data['status'] == "success":
                                st.success("NLP knowledge base processed and loaded successfully!")
                                st.json(data.get('response', {}))
                            else:
                                st.error(f"Upload failed: {data.get('message', '')}")
                        else:
                            st.error(f"Server returned status code {response.status_code}")
                    except requests.exceptions.RequestException as e:
                        st.error(f"Failed to upload NLP text: {str(e)}")
