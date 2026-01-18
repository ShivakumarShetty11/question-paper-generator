# Fermi: Automated Diagram-Based Question Generation Pipeline

An advanced automated pipeline that generates **100 diagram-based mathematics and physics questions** for Grades 9–12, complete with programmatically rendered TikZ diagrams and compiled PDFs.

## 🌟 Key Features

- **AI-Powered Generation**: Uses Groq LLM to generate diverse, topic-specific question patterns and instances
- **Deterministic Diagram Rendering**: TikZ → PDF → PNG with pixel-perfect reproducibility  
- **Streamlined Web Interface**: Clean Streamlit UI with minimal configuration
- **Topic-Relevant Content**: Enhanced prompts ensure all questions are deeply rooted in the specified topic
- **Image-Dependent Questions**: Every question requires diagram examination for answers
- **Automated PDF Assembly**: 10 professional PDFs, one per pattern, with integrated diagrams
- **Robust Error Handling**: Comprehensive validation and fallback mechanisms

## 🏗️ Architecture

```
Topic Input
 └── Pattern Generator (LLM Call #1)
      └── 10 Topic-Specific Pattern Schemas
           └── Question Generator (LLM Call #2)  
                └── 100 Diverse Question Objects
                     ├── TikZ Renderer
                     │    └── PNG Images (300 DPI)
                     └── PDF Builder
                          └── 10 Final PDFs
```

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- Groq API key (get free at [console.groq.com](https://console.groq.com))
- Git

### Installation & Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd fermi
```

2. **Create virtual environment**
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac  
source .venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Setup API key**
```bash
# Create .env file from template
copy .env.example .env
```

Edit `.env` and add your Groq API key:
```env
GROQ_API_KEY=gsk-your-api-key-here
```

### Running the Application

#### Web Interface (Recommended)
```bash
streamlit run app.py
```
Open your browser to **http://localhost:8501**

#### Command Line Interface
```bash
# Generate questions for a topic
python generate.py --topic "Quadratic Equations" --output ./output/
```

## 📁 Project Structure

```
fermi/
├── app.py                        # Streamlit web UI (simplified interface)
├── generate.py                   # CLI entry point
├── requirements.txt              # Python dependencies
├── pyproject.toml               # Project configuration
├── .env.example                  # Environment variables template
├── src/                          # Core source code
│   ├── pipeline.py               # Main pipeline orchestrator
│   ├── config.py                 # Configuration and enhanced prompts
│   ├── schemas.py                # Pydantic data models
│   ├── llm_patterns.py           # Pattern generation (LLM Call #1)
│   ├── llm_questions.py          # Question generation (LLM Call #2)
│   ├── llm_utils.py              # LLM response processing utilities
│   ├── robust_tikz_renderer.py   # Enhanced TikZ rendering
│   ├── pdf_builder.py            # PDF assembly and formatting
│   └── cli.py                    # Command-line interface
├── output/                       # Generated PDFs and diagrams
├── tests/                        # Unit tests
└── tectonic.exe                  # TikZ compiler (Windows)
```

## 🎯 Usage Guide

### Web Interface

1. **Launch the app**: `streamlit run app.py`
2. **Select LLM Model**: Choose from available Groq models in the sidebar
3. **Enter Topic**: Input your academic topic (e.g., "Quadratic Equations", "Coordinate Geometry")
4. **Configure Options**: Set number of patterns (1-10)
5. **Generate**: Click "Generate Questions & PDFs"
6. **Download**: Access generated PDFs and JSON data from the interface

### Available LLM Models

- **llama-3.3-70b-versatile** (Recommended) - Most reliable, best quality
- **llama-3.1-8b-instant** - Fast generation, good for testing
- **gemma-7b-it** - Alternative option

## 🔧 Configuration

### Environment Variables

Configure using `.env` file:

```env
# Required
GROQ_API_KEY=gsk-your-api-key-here

# Optional
FERMI_MODEL=llama-3.3-70b-versatile
FERMI_TEMP=0.7
FERMI_DPI=300
FERMI_PARALLEL=true
FERMI_VALIDATE=true
FERMI_MAX_RETRIES=3
TECTONIC_PATH=./tectonic.exe
```

### Output Structure

```
output/
├── {topic}_patterns.json       # Generated patterns
├── {topic}_questions.json      # All question instances  
├── {topic}_manifest.json        # Generation metadata
├── diagrams/                    # PNG images (300 DPI)
│   ├── pattern_00_question_00.png
│   └── ...
└── pattern_{00-09}_{topic}.pdf # 10 final PDFs
```

## 🧪 Advanced Features

### Enhanced Prompt Engineering

The system uses sophisticated prompts that ensure:

- **Topic Relevance**: All patterns and questions are deeply rooted in the specified topic
- **Diversity**: 10 completely different problem types per pattern
- **Image Dependency**: Questions cannot be answered without examining diagrams
- **Educational Value**: Questions test different cognitive skills and problem-solving approaches

### Robust TikZ Rendering

- **Deterministic Output**: Same input always produces identical diagrams
- **Error Recovery**: Multiple fallback strategies for compilation issues
- **High Quality**: 300 DPI output with proper scaling
- **Self-Contained**: No external LaTeX dependencies

### Validation & Quality Assurance

- **Schema Validation**: Strict Pydantic models ensure data integrity
- **Content Validation**: Questions are checked for solvability and completeness
- **Visual Validation**: Diagrams are verified for proper rendering
- **JSON Parsing**: Robust parsing with multiple fallback strategies

## 🐛 Troubleshooting

### Common Issues

1. **API Key Errors**
   - Ensure `.env` file contains valid Groq API key
   - Check for extra spaces or special characters

2. **TikZ Compilation Errors**
   - Diagram rendering failures are automatically retried
   - Check `tectonic.exe` is in project directory
   - Ensure sufficient disk space for temporary files

3. **JSON Parsing Errors**
   - System includes multiple parsing fallback strategies
   - Invalid LLM responses are automatically cleaned
   - Check logs for detailed error information

4. **Memory Issues**
   - Reduce `FERMI_PARALLEL=false` for lower memory usage
   - Decrease number of patterns for large topics
   - Close other applications during generation

### Debug Mode

Enable detailed logging:
```bash
export FERMI_DEBUG=true
streamlit run app.py
```

## 📚 Educational Applications

- **Homework Generation**: Create varied practice problems
- **Assessment Creation**: Generate diverse question types for tests
- **Study Materials**: Produce visual learning aids with diagrams
- **Curriculum Development**: Explore different aspects of mathematical topics

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 Related Resources

- [Groq API Documentation](https://console.groq.com/docs)
- [TikZ/PGF Manual](https://ctan.org/pkg/pgf)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

## 📈 Performance

- **Generation Time**: ~2-5 minutes for 100 questions (depends on topic complexity)
- **Memory Usage**: ~500MB during peak generation
- **Output Size**: ~10-20MB for complete question sets
- **Success Rate**: >95% for most mathematical topics

---

**Version**: 0.1.0  
**Status**: Production Ready  
**Last Updated**: 2024
