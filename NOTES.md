# Fermi Project: Approach and Implementation Notes

## Overview
Fermi is an automated pipeline for generating 100 diagram-based mathematics and physics questions (10 patterns × 10 questions each) for Grades 9-12, complete with TikZ-rendered diagrams and compiled PDFs.

## Architectural Approach

### Pipeline Design
The system follows a 5-step pipeline architecture:
1. **Pattern Generation (LLM Call #1)**: Generate 10 diverse question patterns for a topic
2. **Question Generation (LLM Call #2)**: Generate 10 specific instances per pattern  
3. **TikZ Rendering**: Convert diagram specifications to publication-quality images
4. **PDF Assembly**: Combine questions and diagrams into 10 formatted PDFs
5. **Output Management**: Structure deliverables for easy access and validation

### Key Design Decisions

#### LLM Integration
- **Provider**: Groq API for fast, reliable inference
- **Models**: Llama 3.3 70B (primary), with fallback options
- **Prompt Engineering**: Multi-layered prompts ensuring topic relevance and diversity
- **Validation**: Robust JSON parsing with multiple fallback strategies

#### Diagram Rendering
- **Technology**: TikZ via Tectonic for deterministic, high-quality output
- **Pipeline**: TikZ → PDF → PNG (300 DPI) for maximum compatibility
- **Error Handling**: Multiple retry mechanisms and validation steps
- **Performance**: Parallel rendering with configurable worker pools

#### Data Management
- **Schemas**: Pydantic models for strict type validation
- **Persistence**: JSON intermediate files for debugging and reproducibility
- **Output Structure**: Clear separation of patterns, questions, diagrams, and PDFs

## Implementation Challenges

### 1. LLM Response Consistency
**Challenge**: Ensuring structured JSON output from creative LLM responses
**Solution**: 
- Multi-stage parsing with regex fallbacks
- Schema validation with detailed error reporting
- Retry logic with exponential backoff

### 2. TikZ Compilation Reliability
**Challenge**: Handling malformed TikZ code and compilation failures
**Solution**:
- Pre-validation of TikZ syntax
- Multiple compilation strategies (Tectonic fallbacks)
- Graceful degradation with error reporting

### 3. Topic Relevance Enforcement
**Challenge**: Preventing generic patterns that don't align with specific topics
**Solution**:
- Enhanced prompts with topic-specific examples
- Validation checks for topic keyword inclusion
- Pattern diversity scoring within topic constraints

### 4. PDF Assembly Complexity
**Challenge**: Integrating images, text, and formatting into professional documents
**Solution**:
- ReportLab with custom styling for educational content
- Page-per-question format for clarity
- Automatic image sizing and positioning

### 5. Performance Optimization
**Challenge**: Balancing quality with generation speed (100 questions = significant processing)
**Solution**:
- Parallel processing for independent tasks
- Configurable concurrency limits
- Progress tracking and resumption capabilities

## Technical Improvements Made

### Schema Restructuring
- Fixed `OutputManifest` to match pipeline expectations
- Updated `PDFPage` and `PatternPDF` for proper data flow
- Ensured type consistency across all components

### Dependency Management
- Added missing packages: `streamlit`, `groq`, `python-dotenv`
- Version pinning for reproducible builds
- Clear separation of runtime vs development dependencies

### Pipeline Enforcement
- Hardcoded exactly 10 patterns × 10 questions = 100 questions
- Validation at each pipeline stage
- Comprehensive error reporting and logging

### Output Structure Compliance
- Implemented required file naming conventions
- Proper directory structure for deliverables
- Metadata tracking for generation provenance

## Future Improvements

### Short-term
1. **Enhanced Validation**: Mathematical solvability checking
2. **Template System**: Reusable pattern templates for common topics
3. **Performance Caching**: LLM response caching for similar topics
4. **UI Improvements**: Real-time progress tracking in Streamlit

### Long-term
1. **Multi-modal Support**: Integration with diagram generation models
2. **Adaptive Difficulty**: Dynamic difficulty adjustment based on performance
3. **Export Formats**: Support for additional formats (LaTeX, HTML)
4. **Quality Metrics**: Automated question quality assessment

## Usage Notes

### Environment Setup
- Requires Groq API key in `.env` file
- Tectonic binary must be available in project directory
- Python 3.9+ with virtual environment recommended

### Running the Pipeline
```bash
# Web interface
streamlit run app.py

# Command line
python -m src.cli --topic "Coordinate Geometry" --output ./output/
```

### Output Structure
```
output/
├── {topic}_patterns.json       # 10 pattern definitions
├── {topic}_questions.json      # 100 question instances  
├── {topic}_manifest.json        # Generation metadata
├── diagrams/                    # 100 PNG images (300 DPI)
└── pattern_{00-09}_{topic}.pdf # 10 final PDFs
```

## Validation Checklist
- [x] Exactly 100 questions generated (10×10)
- [x] All questions are topic-relevant
- [x] Diagrams render successfully
- [x] PDFs are properly formatted
- [x] Intermediate files are saved
- [x] Error handling is robust
- [x] Dependencies are properly managed

---

**Project Status**: Production Ready  
**Last Updated**: 2025-01-18  
**Version**: 0.1.0
