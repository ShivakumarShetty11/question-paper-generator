"""
Fermi: Automated Diagram-Based Question Generation Pipeline
"""

__version__ = "0.1.0"
__author__ = "Fermi Team"

from .pipeline import Pipeline
from .config import get_pipeline_config
from .schemas import (
    PatternSchema,
    QuestionSet,
    OutputManifest
)

__all__ = [
    'Pipeline',
    'get_pipeline_config',
    'PatternSchema',
    'QuestionSet',
    'OutputManifest'
]
