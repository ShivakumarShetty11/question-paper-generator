"""
Pydantic schemas for structured question and diagram generation.
Defines all data models enforced at each pipeline stage.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator


# =====================================================================
# Pattern Schemas
# =====================================================================

class VariableDefinition(BaseModel):
    """Defines a variable used in a pattern and its valid range."""
    
    name: str = Field(..., description="Variable name (e.g., 'radius', 'angle')")
    type: str = Field(..., description="Data type: 'int', 'float', 'enum'")
    min_value: Optional[float] = Field(None, description="Minimum value for numeric types")
    max_value: Optional[float] = Field(None, description="Maximum value for numeric types")
    allowed_values: Optional[List[Any]] = Field(None, description="For enum types")
    unit: Optional[str] = Field(None, description="Unit of measurement (e.g., 'degrees', 'cm')")
    description: str = Field(..., description="Human-readable description")

    @validator('type')
    def validate_type(cls, v):
        if v not in ['int', 'float', 'enum', 'string']:
            raise ValueError("type must be 'int', 'float', 'enum', or 'string'")
        return v


class QuestionPattern(BaseModel):
    """Defines a reusable question pattern with diagram template."""
    
    pattern_id: int = Field(..., description="Unique pattern identifier (0-9)")
    pattern_name: str = Field(..., description="Descriptive pattern name")
    topic: str = Field(..., description="Academic topic (e.g., 'Coordinate Geometry')")
    
    diagram_description: str = Field(
        ...,
        description="Semantic description of diagram (NOT TikZ code)"
    )
    
    question_template: str = Field(
        ...,
        description="Question template with {variable} placeholders"
    )
    
    variables: List[VariableDefinition] = Field(
        ...,
        description="List of variables used in question and diagram"
    )
    
    grade_level: str = Field(..., description="Target grade: '9', '10', '11', '12', or '9-10', '11-12'")
    
    difficulty: str = Field(
        ...,
        description="Difficulty level: 'easy', 'medium', 'hard'"
    )
    
    learning_objective: str = Field(
        ...,
        description="What concept this pattern tests"
    )

    @validator('pattern_id')
    def validate_pattern_id(cls, v):
        if v < 0:
            raise ValueError("pattern_id must be non-negative")
        return v


class PatternSchema(BaseModel):
    """Container for question patterns generated for a topic."""
    
    topic: str = Field(..., description="Academic topic")
    patterns: List[QuestionPattern] = Field(
        ...,
        description="Question patterns for the topic"
    )
    generation_timestamp: str = Field(..., description="ISO 8601 timestamp of generation")
    model_used: str = Field(..., description="LLM model name (e.g., 'gpt-4')")

    @validator('patterns')
    def validate_pattern_count(cls, v):
        if len(v) < 1:
            raise ValueError("Must have at least 1 pattern")
        return v


# =====================================================================
# Question Instance Schemas
# =====================================================================

class QuestionInstance(BaseModel):
    """A single, fully specified question with variables and answer."""
    
    instance_id: int = Field(..., description="Instance number within pattern (0-9)")
    pattern_id: int = Field(..., description="Reference to parent pattern (0-9)")
    topic: str = Field(..., description="Academic topic")
    
    variables: Dict[str, Any] = Field(
        ...,
        description="Concrete variable values (e.g., {'radius': 5, 'angle': 30})"
    )
    
    question_text: str = Field(
        ...,
        description="Fully instantiated question with all variables filled in"
    )
    
    correct_answer: str = Field(
        ...,
        description="Correct final answer (may include units and explanation)"
    )
    
    @validator('correct_answer', pre=True)
    def convert_answer_to_string(cls, v):
        """Convert numeric answers to strings."""
        if isinstance(v, (int, float)):
            return str(v)
        return v
    
    tikz_code: str = Field(
        ...,
        description="Valid, compilable TikZ code for diagram (without wrapping)"
    )
    
    difficulty: str = Field(..., description="Difficulty: 'easy', 'medium', 'hard'")
    
    solvability_check: str = Field(
        default="pending",
        description="Status: 'pending', 'valid', 'invalid' (for validation)"
    )


class QuestionSet(BaseModel):
    """All 10 questions for a single pattern."""
    
    pattern_id: int = Field(..., description="Pattern ID (0-9)")
    pattern_name: str = Field(..., description="Pattern name for reference")
    questions: List[QuestionInstance] = Field(
        ...,
        description="Exactly 10 question instances"
    )
    generation_timestamp: str = Field(..., description="ISO 8601 timestamp")
    model_used: str = Field(..., description="LLM model name")

    @validator('questions')
    def validate_question_count(cls, v):
        if len(v) != 10:
            raise ValueError("Must have exactly 10 questions per pattern")
        return v


# =====================================================================
# Rendering & Output Schemas
# =====================================================================

class RenderedDiagram(BaseModel):
    """A rendered diagram with metadata."""
    
    instance_id: int = Field(..., description="Reference to question instance")
    pattern_id: int = Field(..., description="Reference to pattern")
    png_path: str = Field(..., description="Absolute path to rendered PNG")
    tikz_code: str = Field(..., description="Original TikZ code used")
    render_status: str = Field(
        ...,
        description="Status: 'success', 'failed', 'invalid_tikz'"
    )
    error_message: Optional[str] = Field(None, description="Error details if failed")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional render metadata from robust pipeline")


class PDFPage(BaseModel):
    """A single page in the final PDF (question + diagram)."""
    
    instance_id: int = Field(..., description="Question instance ID")
    question_text: str = Field(..., description="Question text")
    diagram_path: Optional[str] = Field(None, description="Path to diagram PNG")
    answer: str = Field(..., description="Correct answer")


class PatternPDF(BaseModel):
    """Final PDF document for a single pattern (contains up to 10 questions)."""
    
    pattern_id: int = Field(..., description="Pattern ID")
    pattern_name: str = Field(..., description="Pattern name")
    pdf_path: str = Field(..., description="Absolute path to generated PDF")
    pages: List[PDFPage] = Field(..., description="Up to 10 pages (one per question)")
    generation_timestamp: str = Field(..., description="ISO 8601 timestamp")

    @validator('pages')
    def validate_page_count(cls, v):
        # Allow 0-10 pages (some may fail due to rendering issues)
        if len(v) > 10:
            raise ValueError("Cannot have more than 10 pages per PDF")
        return v


class OutputManifest(BaseModel):
    """Complete metadata for all generated output."""
    
    topic: str = Field(..., description="Topic name")
    total_patterns: int = Field(..., description="Number of patterns generated")
    total_questions: int = Field(..., description="Total number of questions generated")
    pdfs: List[PatternPDF] = Field(..., description="Generated PDFs")
    diagrams_dir: str = Field(..., description="Directory containing all PNG diagrams")
    output_dir: str = Field(..., description="Root output directory")
    generation_timestamp: str = Field(..., description="ISO 8601 timestamp")

    @validator('pdfs')
    def validate_pdf_count(cls, v):
        if len(v) < 1:
            raise ValueError("Must have at least 1 PDF")
        return v


# =====================================================================
# Configuration Schemas
# =====================================================================

class LLMConfig(BaseModel):
    """Configuration for LLM calls."""
    
    provider: str = Field(default="openai", description="LLM provider")
    model: str = Field(default="gpt-4", description="Model identifier")
    temperature: float = Field(default=0.7, description="Sampling temperature")
    max_tokens: int = Field(default=4000, description="Max tokens per call")
    api_key: Optional[str] = Field(None, description="API key (from env if None)")


class TikZConfig(BaseModel):
    """Configuration for TikZ rendering."""
    
    dpi: int = Field(default=300, description="PNG output DPI")
    tectonic_path: Optional[str] = Field(None, description="Path to tectonic binary")
    temp_dir: str = Field(default="./temp", description="Temporary directory")
    keep_intermediate: bool = Field(default=False, description="Keep LaTeX and PDF files")


class PipelineConfig(BaseModel):
    """Overall pipeline configuration."""
    
    llm: LLMConfig = Field(default_factory=LLMConfig)
    tikz: TikZConfig = Field(default_factory=TikZConfig)
    output_dir: str = Field(default="./output", description="Output directory")
    validate_solvability: bool = Field(default=True, description="Validate answer correctness")
    parallel_rendering: bool = Field(default=True, description="Render diagrams in parallel")
    max_retries: int = Field(default=3, description="Retries for LLM calls")
