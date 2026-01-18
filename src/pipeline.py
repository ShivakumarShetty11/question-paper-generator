"""
Pipeline Orchestrator
Coordinates all components: LLM calls, rendering, validation, and PDF assembly.
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import get_pipeline_config, PATTERNS_PER_TOPIC, QUESTIONS_PER_PATTERN
from .schemas import (
    PatternCollection,
    QuestionSet,
    RenderedDiagram,
    OutputManifest,
    PatternPDF,
    QuestionInstance
)
from .llm_patterns import PatternGenerator
from .llm_questions import QuestionGenerator
from .robust_tikz_renderer import RobustTikZRenderer, RobustTikZValidator
from .pdf_builder import PDFBuilder
from .validator import QuestionValidator, SolvabilityChecker, ConsistencyChecker

logger = logging.getLogger(__name__)


class Pipeline:
    """Main pipeline orchestrator."""
    
    def __init__(self, config=None):
        """
        Initialize pipeline.
        
        Args:
            config: PipelineConfig (uses default if None)
        """
        self.config = config or get_pipeline_config()
        
        # Initialize components
        self.pattern_generator = PatternGenerator(
            api_key=self.config.llm.api_key,
            model=self.config.llm.model,
            temperature=self.config.llm.temperature
        )
        
        self.question_generator = QuestionGenerator(
            api_key=self.config.llm.api_key,
            model=self.config.llm.model,
            temperature=self.config.llm.temperature
        )
        
        self.tikz_renderer = RobustTikZRenderer(
            temp_dir=self.config.tikz.temp_dir,
            dpi=self.config.tikz.dpi,
            tectonic_path=self.config.tikz.tectonic_path,
            keep_intermediate=getattr(self.config.tikz, 'keep_intermediate', False),
            max_retries=getattr(self.config.tikz, 'max_retries', 3)
        )
        
        self.pdf_builder = PDFBuilder()
        
        # Create output directories
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.diagrams_dir = self.output_dir / "diagrams"
        self.diagrams_dir.mkdir(parents=True, exist_ok=True)
    
    def run(self, topic: str, grade_level: str = "9-12", num_patterns: int = 10) -> OutputManifest:
        """
        Run complete pipeline for a topic.
        
        Args:
            topic: Academic topic (e.g., "Coordinate Geometry")
            grade_level: Target grade level
            num_patterns: Number of patterns to generate (default: 10)
        
        Returns:
            OutputManifest with all generated PDFs and metadata
        """
        
        # Set default number of patterns
        if num_patterns is None:
            num_patterns = 10
        
        # Enforce exactly 10 patterns as per project requirements
        num_patterns = 10
        
        logger.info(f"Starting pipeline for topic: {topic}")
        logger.info(f"Grade level: {grade_level}")
        logger.info(f"Number of patterns: {num_patterns}")
        
        # Step 1: Generate patterns
        logger.info("Step 1: Generating question patterns...")
        pattern_schema = self._generate_patterns(topic, grade_level, num_patterns)
        
        # Save patterns
        patterns_file = self.output_dir / f"{topic.replace(' ', '_')}_patterns.json"
        self._save_json(pattern_schema.dict(), str(patterns_file))
        logger.info(f"Patterns saved to {patterns_file}")
        
        # Step 2: Generate questions for each pattern
        logger.info("Step 2: Generating question instances...")
        all_question_sets: List[QuestionSet] = []
        for pattern in pattern_schema.patterns:
            question_set = self._generate_questions(pattern, topic)
            all_question_sets.append(question_set)
        
        # Save all questions
        questions_file = self.output_dir / f"{topic.replace(' ', '_')}_questions.json"
        questions_data = [qs.dict() for qs in all_question_sets]
        self._save_json(questions_data, str(questions_file))
        logger.info(f"Questions saved to {questions_file}")
        
        # Step 3: Render diagrams
        logger.info("Step 3: Rendering diagrams...")
        all_rendered_diagrams: List[List[RenderedDiagram]] = []
        for pattern_idx, question_set in enumerate(all_question_sets):
            diagrams = self._render_diagrams(question_set, pattern_idx)
            all_rendered_diagrams.append(diagrams)
        
        # Step 4: Build PDFs
        logger.info("Step 4: Building PDFs...")
        all_pdfs: List[PatternPDF] = []
        for pattern_idx, (question_set, diagrams) in enumerate(
            zip(all_question_sets, all_rendered_diagrams)
        ):
            pdf_path = (
                self.output_dir / 
                f"pattern_{pattern_idx:02d}_{question_set.pattern_name.replace(' ', '_')}.pdf"
            )
            pdf_metadata = self._build_pdf(question_set, diagrams, str(pdf_path))
            all_pdfs.append(pdf_metadata)
        
        # Step 5: Create output manifest
        logger.info("Step 5: Creating output manifest...")
        manifest = OutputManifest(
            topic=topic,
            total_patterns=num_patterns,
            total_questions=num_patterns * QUESTIONS_PER_PATTERN,
            pdfs=all_pdfs,
            diagrams_dir=str(self.diagrams_dir),
            output_dir=str(self.output_dir),
            generation_timestamp=datetime.utcnow().isoformat()
        )
        
        # Save manifest
        manifest_file = self.output_dir / f"{topic.replace(' ', '_')}_manifest.json"
        self._save_json(manifest.dict(), str(manifest_file))
        logger.info(f"Manifest saved to {manifest_file}")
        
        logger.info("Pipeline completed successfully!")
        return manifest
    
    def _generate_patterns(
        self,
        topic: str,
        grade_level: str,
        num_patterns: int = None
    ) -> PatternCollection:
        """Generate patterns using LLM."""
        
        if num_patterns is None:
            num_patterns = PATTERNS_PER_TOPIC
        
        try:
            schema = self.pattern_generator.generate(topic, str(grade_level), num_patterns)
            
            # Validate
            errors = self.pattern_generator.validate_patterns(schema)
            if errors:
                logger.warning(f"Pattern validation warnings: {errors}")
            
            return schema
        
        except Exception as e:
            logger.error(f"Pattern generation failed: {e}")
            raise
    
    def _generate_questions(
        self,
        pattern,
        topic: str
    ) -> QuestionSet:
        """Generate questions for a pattern."""
        
        try:
            question_set = self.question_generator.generate(pattern, topic)
            
            # Validate
            errors = self.question_generator.validate_questions(question_set)
            if errors:
                logger.warning(f"Question validation warnings: {errors}")
            
            # Check solvability
            if self.config.validate_solvability:
                for question in question_set.questions:
                    status, error = SolvabilityChecker.check(question)
                    question.solvability_check = status
                    if error:
                        logger.warning(
                            f"Question {question.instance_id} solvability check failed: {error}"
                        )
            
            return question_set
        
        except Exception as e:
            logger.error(f"Question generation failed: {e}")
            raise
    
    def _render_diagrams(
        self,
        question_set: QuestionSet,
        pattern_idx: int
    ) -> List[RenderedDiagram]:
        """Render all diagrams for a question set."""
        
        rendered = []
        
        if self.config.parallel_rendering:
            rendered = self._render_diagrams_parallel(question_set, pattern_idx)
        else:
            rendered = self._render_diagrams_sequential(question_set, pattern_idx)
        
        return rendered
    
    def _render_diagrams_sequential(
        self,
        question_set: QuestionSet,
        pattern_idx: int
    ) -> List[RenderedDiagram]:
        """Render diagrams sequentially."""
        
        rendered = []
        for question in question_set.questions:
            diagram = self._render_single_diagram(question, pattern_idx)
            rendered.append(diagram)
        
        return rendered
    
    def _render_diagrams_parallel(
        self,
        question_set: QuestionSet,
        pattern_idx: int
    ) -> List[RenderedDiagram]:
        """Render diagrams in parallel."""
        
        rendered = [None] * len(question_set.questions)
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(
                    self._render_single_diagram, question, pattern_idx
                ): i
                for i, question in enumerate(question_set.questions)
            }
            
            for future in as_completed(futures):
                idx = futures[future]
                rendered[idx] = future.result()
        
        return rendered
    
    def _render_single_diagram(
        self,
        question: QuestionInstance,
        pattern_idx: int
    ) -> RenderedDiagram:
        """Render a single diagram."""
        
        output_png = (
            self.diagrams_dir /
            f"pattern_{pattern_idx:02d}_question_{question.instance_id:02d}.png"
        )
        
        # Validate TikZ code
        is_valid, error = RobustTikZValidator.validate(question.tikz_code)
        if not is_valid:
            return RenderedDiagram(
                tikz_code=question.tikz_code,
                pdf_path="",  # Empty since we don't generate PDFs for individual diagrams
                png_path="",
                render_time=0.0,
                success=False,
                error_message=error
            )
        
        # Render using robust pipeline
        render_result = self.tikz_renderer.render(question.tikz_code, str(output_png))
        
        return RenderedDiagram(
            tikz_code=question.tikz_code,
            pdf_path=str(output_png).replace('.png', '.pdf'),  # Convert PNG path to PDF path
            png_path=str(output_png),
            render_time=render_result.get("render_time", 0.0),
            success=render_result["success"],
            error_message=None if render_result["success"] else "; ".join(render_result["errors"])
        )
    
    def _build_pdf(
        self,
        question_set: QuestionSet,
        diagrams: List[RenderedDiagram],
        output_path: str
    ) -> PatternPDF:
        """Build PDF for a question set."""
        
        try:
            pdf_metadata = self.pdf_builder.build_pdf(
                question_set,
                diagrams,
                output_path
            )
            return pdf_metadata
        
        except Exception as e:
            logger.error(f"PDF building failed: {e}")
            raise
    
    @staticmethod
    def _save_json(data: dict, filepath: str):
        """Save data to JSON file."""
        
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved JSON to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save JSON: {e}")
            raise
