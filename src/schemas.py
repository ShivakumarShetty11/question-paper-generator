"""
Pydantic schemas for structured question and diagram generation.
Defines all data models enforced at each pipeline stage.
"""

from typing import List, Dict, Any, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field, validator

if TYPE_CHECKING:
    from typing import ForwardRef

# =====================================================================
# Configuration Schemas
# =====================================================================

class LLMConfig(BaseModel):
    """Configuration for LLM interactions."""
    
    provider: str = Field(default="groq", description="LLM provider")
    model: str = Field(default="llama-3.3-70b-versatile", description="LLM model name")
    temperature: float = Field(default=0.7, description="Sampling temperature")
    max_tokens: int = Field(default=8000, description="Maximum tokens per response")
    timeout: int = Field(default=60, description="Request timeout in seconds")
    api_key: str = Field(..., description="API key")

class TikZConfig(BaseModel):
    """Configuration for TikZ rendering."""
    
    dpi: int = Field(default=300, description="Output DPI")
    temp_dir: str = Field(default="output/temp", description="Temporary directory")
    cleanup_temp: bool = Field(default=True, description="Whether to clean up temp files")
    tectonic_binary: str = Field(default="tectonic", description="Path to tectonic binary")
    tectonic_path: Optional[str] = Field(None, description="Path to tectonic binary")
    keep_intermediate: bool = Field(default=False, description="Whether to keep intermediate files")

class PipelineConfig(BaseModel):
    """Configuration for entire pipeline."""
    
    patterns_per_topic: int = Field(default=1, description="Number of patterns to generate per topic")
    questions_per_pattern: int = Field(default=10, description="Number of questions to generate per pattern")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    validate_output: bool = Field(default=True, description="Whether to validate output")
    parallel_processing: bool = Field(default=False, description="Whether to process patterns in parallel")
    llm: LLMConfig = Field(..., description="LLM configuration")
    tikz: TikZConfig = Field(..., description="TikZ configuration")
    output_dir: str = Field(..., description="Output directory")
    validate_solvability: bool = Field(default=True, description="Whether to validate solvability")
    parallel_rendering: bool = Field(default=True, description="Whether to render in parallel")

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
    pattern_name: str = Field(..., description="Human-readable pattern name")
    diagram_description: str = Field(..., description="Visual diagram description")
    question_template: str = Field(..., description="Template with variable placeholders")
    variables: List[VariableDefinition] = Field(..., description="List of variables")
    difficulty: str = Field(..., description="Difficulty level")
    learning_objective: str = Field(..., description="Learning goal")
    image_dependency: Optional[str] = Field(default="high", description="How critical the image is")
    topic_relevance: Optional[str] = Field(default="high", description="Topic relevance score")
    diversity_score: Optional[str] = Field(default="high", description="Diversity score")
    sample_questions: List[Dict[str, Any]] = Field(default_factory=list, description="Sample questions")

# Alias for backward compatibility
PatternSchema = QuestionPattern

class PatternCollection(BaseModel):
    """Collection of question patterns for a topic."""
    
    model_config = {"protected_namespaces": ()}
    
    topic: str = Field(..., description="Academic topic")
    patterns: List[QuestionPattern] = Field(..., description="List of question patterns")
    generation_timestamp: str = Field(..., description="When patterns were generated")
    model_used: str = Field(..., description="LLM model used")

# =====================================================================
# Question Instance Schemas
# =====================================================================

class Question(BaseModel):
    """A single, fully specified question with variables and answer."""
    
    instance_id: int = Field(..., description="Instance number within pattern (0-9)")
    pattern_id: int = Field(..., description="Reference to parent pattern (0-9)")
    topic: str = Field(..., description="Academic topic")
    question_text: str = Field(..., description="The actual question text")
    correct_answer: str = Field(..., description="The correct answer")
    tikz_code: str = Field(..., description="Complete TikZ drawing code")
    difficulty: str = Field(..., description="Difficulty level")
    solvability_check: str = Field(default="pending", description="Whether question can be solved")
    variables: Dict[str, Any] = Field(..., description="Variable values for this instance")

class QuestionSet(BaseModel):
    """All 10 questions for a single pattern."""
    
    pattern_id: int = Field(..., description="Pattern ID (0-9)")
    pattern_name: str = Field(..., description="Pattern name")
    questions: List[Question] = Field(..., description="List of 10 question instances")
    topic: str = Field(..., description="Academic topic")
    generation_metadata: Dict[str, Any] = Field(default_factory=dict, description="Generation metadata")

# Alias for backward compatibility
QuestionInstance = Question

class RenderedDiagram(BaseModel):
    """A rendered TikZ diagram."""
    
    tikz_code: str = Field(..., description="Original TikZ code")
    pdf_path: str = Field(..., description="Path to rendered PDF")
    png_path: str = Field(..., description="Path to rendered PNG")
    render_time: float = Field(..., description="Time taken to render")
    success: bool = Field(..., description="Whether rendering was successful")
    error_message: Optional[str] = Field(None, description="Error message if rendering failed")

class PDFPage(BaseModel):
    """A single page in a generated PDF."""
    
    page_number: int = Field(..., description="Page number (1-based)")
    question_id: int = Field(..., description="Question instance ID")
    question_text: str = Field(..., description="Question text")
    tikz_code: str = Field(..., description="TikZ code for the diagram")
    answer: str = Field(..., description="Answer text")
    image_path: str = Field(..., description="Path to rendered image")

class PatternPDF(BaseModel):
    """A PDF containing all questions for a pattern."""
    
    pattern_id: int = Field(..., description="Pattern ID")
    pattern_name: str = Field(..., description="Pattern name")
    pdf_path: str = Field(..., description="Path to generated PDF")
    pages: List[PDFPage] = Field(..., description="List of pages in this PDF")
    generation_time: float = Field(..., description="Time taken to generate PDF")

# =====================================================================
# Output Schemas
# =====================================================================

class OutputManifest(BaseModel):
    """Complete output manifest for all patterns and questions."""
    
    topic: str = Field(..., description="Academic topic")
    total_patterns: int = Field(..., description="Total number of patterns")
    total_questions: int = Field(..., description="Total number of questions")
    pdfs: List[PatternPDF] = Field(..., description="Generated PDFs")
    diagrams_dir: str = Field(..., description="Directory containing diagram images")
    output_dir: str = Field(..., description="Output directory")
    generation_timestamp: str = Field(..., description="When generation was completed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
