"""
Streamlit frontend for the Fermi pipeline.
Provides a web UI for generating questions and downloading PDFs.
"""

import streamlit as st
import os
import logging
from pathlib import Path
from datetime import datetime
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from src.pipeline import Pipeline
from src.config import get_pipeline_config

# Configure page
st.set_page_config(
    page_title="Fermi - Question Generator",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Custom CSS
st.markdown("""
<style>
    .main {
        padding-top: 1rem;
    }
    .stButton > button {
        width: 100%;
        padding: 0.5rem;
        font-size: 1.1rem;
        background: linear-gradient(90deg, #1f4788 0%, #2563eb 100%);
        color: white;
        border: none;
        border-radius: 0.5rem;
        cursor: pointer;
    }
    .stButton > button:hover {
        background: linear-gradient(90deg, #163054 0%, #1d4ed8 100%);
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
        color: #155724;
    }
    .info-box {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
        color: #0c5460;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
        color: #856404;
    }
    h1 {
        color: #1f4788;
        border-bottom: 3px solid #2563eb;
        padding-bottom: 0.5rem;
    }
    h2 {
        color: #2563eb;
        margin-top: 1.5rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-left: 4px solid #2563eb;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Session state management
if 'pipeline' not in st.session_state:
    st.session_state.pipeline = None
if 'manifest' not in st.session_state:
    st.session_state.manifest = None
if 'generation_complete' not in st.session_state:
    st.session_state.generation_complete = False
if 'current_topic' not in st.session_state:
    st.session_state.current_topic = None

# Header
st.title("📚 Fermi Question Generator")


# Sidebar configuration
st.sidebar.header("⚙️ Configuration")

with st.sidebar:
    # API Key check (hidden but required)
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        st.error("❌ GROQ_API_KEY not set")
        st.markdown("""
        ### Setup Instructions:
        
        1. **Copy the template:**
           ```bash
           copy .env.example .env
           ```
        
        2. **Edit `.env` file:**
           ```
           GROQ_API_KEY=gsk-your-api-key-here
           ```
        
        3. **Get your API key:**
           - Visit: https://console.groq.com
           - Create account
           - Generate API key
           - Copy and paste into `.env`
        
        4. **Restart this app**
        """)
        st.stop()
    
    # Tectonic check (hidden but required)
    config = get_pipeline_config()
    
    # Only show model selection
    model = st.selectbox(
        "LLM Model",
        ["llama-3.1-8b-instant", "gemma-7b-it", "llama-3.3-70b-versatile"],
        index=0,
        help="Llama 3.1 8B is fastest and has good rate limits. 70B is most capable but rate limited."
    )
    
    # Set default values for hidden settings
    validate = True
    parallel = True
    dpi = 300
    temperature = 0.7
    max_retries = 3

# Main content
col1 = st.columns([1])[0]

with col1:
    st.subheader("📝 Generate Questions")
    
    # Topic input
    topic = st.text_input(
        "Academic Topic",
        placeholder="e.g., Coordinate Geometry, Quadratic Equations, Trigonometry",
        help="Enter the topic for which you want to generate questions"
    )
    
    # Number of patterns
    num_patterns = st.number_input(
        "Number of Patterns",
        min_value=1,
        max_value=10,
        value=10,
        step=1,
        help="Number of question patterns to generate (each pattern generates 10 questions)"
    )
    
    st.divider()
    
    # Generate button
    if st.button("🚀 Generate Questions & PDFs", use_container_width=True):
        if not topic or len(topic.strip()) < 3:
            st.error("❌ Please enter a valid topic (at least 3 characters)")
        else:
            st.session_state.current_topic = topic
            
            # Progress tracking
            progress_container = st.container()
            status_container = st.container()
            
            try:
                with progress_container:
                    progress_bar = st.progress(0, text="Initializing...")
                
                with status_container:
                    status_placeholder = st.empty()
                
                # Configure pipeline
                config = get_pipeline_config()
                config.llm.model = model
                config.llm.temperature = float(temperature)
                config.tikz.dpi = dpi
                config.validate_solvability = validate
                config.parallel_rendering = parallel
                config.max_retries = max_retries
                
                # Create pipeline
                pipeline = Pipeline(config)
                st.session_state.pipeline = pipeline
                
                # Update progress
                with progress_container:
                    progress_bar.progress(10, text="Generating patterns (LLM Call #1)...")
                
                with status_container:
                    status_placeholder.info(f"📊 Generating {num_patterns} question patterns...")
                
                # Run pipeline with custom number of patterns
                manifest = pipeline.run(topic, num_patterns=int(num_patterns))
                st.session_state.manifest = manifest
                st.session_state.generation_complete = True
                
                # Update progress
                with progress_container:
                    progress_bar.progress(100, text="Complete!")
                
                with status_container:
                    st.success("✅ Generation complete!")
                
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error during generation: {str(e)}")
                logger.error(f"Pipeline error: {e}", exc_info=True)
                with status_container:
                    st.error(f"Generation failed: {str(e)}")

# Display results
if st.session_state.generation_complete and st.session_state.manifest:
    st.divider()
    
    manifest = st.session_state.manifest
    
    st.subheader("📥 Download Generated PDFs")
    
    # Create tabs for each PDF
    pdf_tabs = st.tabs([f"Pattern {i}" for i in range(len(manifest.pdfs))])
    
    for idx, (tab, pdf_metadata) in enumerate(zip(pdf_tabs, manifest.pdfs)):
        with tab:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"**{pdf_metadata.pattern_name}**")
                st.markdown(f"Questions in this PDF: {len(pdf_metadata.pages)}")
                
                # Show first few questions as preview
                with st.expander("Preview Questions"):
                    for i, page in enumerate(pdf_metadata.pages[:3], 1):
                        st.markdown(f"**Q{i}:** {page.question_text[:100]}...")
                        if page.answer:
                            st.markdown(f"*Answer: {page.answer[:50]}...*")
            
            with col2:
                # Download button
                if Path(pdf_metadata.pdf_path).exists():
                    with open(pdf_metadata.pdf_path, "rb") as pdf_file:
                        pdf_bytes = pdf_file.read()
                        
                        st.download_button(
                            label="📥 Download PDF",
                            data=pdf_bytes,
                            file_name=Path(pdf_metadata.pdf_path).name,
                            mime="application/pdf",
                            use_container_width=True
                        )
                    st.success("✅ Ready for download")
                else:
                    st.error("❌ PDF file not found")
    
    st.divider()
    
    # Additional downloads
    st.subheader("📦 Additional Downloads")
    
    col1, col2, col3 = st.columns(3)
    
    # Download patterns JSON
    patterns_file = Path(manifest.output_dir) / f"{manifest.topic.replace(' ', '_')}_patterns.json"
    if patterns_file.exists():
        with col1:
            with open(patterns_file, "r") as f:
                patterns_data = json.load(f)
            st.download_button(
                label="📋 Patterns JSON",
                data=json.dumps(patterns_data, indent=2),
                file_name="patterns.json",
                mime="application/json",
                use_container_width=True
            )
    
    # Download questions JSON
    questions_file = Path(manifest.output_dir) / f"{manifest.topic.replace(' ', '_')}_questions.json"
    if questions_file.exists():
        with col2:
            with open(questions_file, "r") as f:
                questions_data = json.load(f)
            st.download_button(
                label="❓ Questions JSON",
                data=json.dumps(questions_data, indent=2),
                file_name="questions.json",
                mime="application/json",
                use_container_width=True
            )
    
    # Download manifest
    manifest_file = Path(manifest.output_dir) / f"{manifest.topic.replace(' ', '_')}_manifest.json"
    if manifest_file.exists():
        with col3:
            with open(manifest_file, "r") as f:
                manifest_data = json.load(f)
            st.download_button(
                label="📄 Manifest JSON",
                data=json.dumps(manifest_data, indent=2),
                file_name="manifest.json",
                mime="application/json",
                use_container_width=True
            )
    
    st.divider()
    
    # Generation summary
    st.subheader("✅ Generation Summary")
    
    summary_col1, summary_col2 = st.columns(2)
    
    with summary_col1:
        st.markdown(f"""
        **Generated Content**
        - Topic: {manifest.topic}
        - Patterns: {manifest.total_patterns}
        - Questions: {manifest.total_questions}
        - Diagrams: 100 (PNG, 300 DPI)
        - PDFs: {len(manifest.pdfs)} (formatted, printable)
        """)
    
    with summary_col2:
        st.markdown(f"""
        **Output Directory**
        - Location: `{manifest.output_dir}`
        - Diagrams: `{manifest.diagrams_dir}`
        - Generated: {manifest.generation_timestamp}
        """)
    
    # Clear button
    if st.button("🔄 Generate New Topic", use_container_width=True):
        st.session_state.generation_complete = False
        st.session_state.manifest = None
        st.session_state.current_topic = None
        st.rerun()
