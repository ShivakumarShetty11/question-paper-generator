"""
PDF Assembly Module
Combines rendered diagrams with question text into final PDFs.
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib import colors
from PIL import Image as PILImage

from .schemas import QuestionSet, RenderedDiagram, PatternPDF, PDFPage

logger = logging.getLogger(__name__)


class PDFBuilder:
    """Builds final PDF with questions and diagrams."""
    
    def __init__(
        self,
        page_size: str = "letter",
        margin: float = 0.5,
        diagram_width: float = 4.5
    ):
        """
        Initialize PDF builder.
        
        Args:
            page_size: 'letter' or 'a4'
            margin: Margin in inches
            diagram_width: Diagram width in inches
        """
        self.page_size = letter if page_size.lower() == "letter" else A4
        self.margin_inches = margin
        self.margin = margin * inch
        self.diagram_width = diagram_width * inch
        
        # Styles
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        
        # Title style
        self.styles.add(ParagraphStyle(
            name='PatternTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Question style
        self.styles.add(ParagraphStyle(
            name='Question',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#333333'),
            spaceAfter=6,
            leftIndent=0,
            fontName='Helvetica'
        ))
        
        # Answer style
        self.styles.add(ParagraphStyle(
            name='Answer',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666'),
            spaceAfter=12,
            leftIndent=20,
            fontName='Helvetica-Oblique'
        ))
    
    def build_pdf(
        self,
        question_set: QuestionSet,
        rendered_diagrams: List[RenderedDiagram],
        output_pdf: str
    ) -> PatternPDF:
        """
        Build PDF from question set and rendered diagrams.
        
        Args:
            question_set: QuestionSet with 10 questions
            rendered_diagrams: List of RenderedDiagram objects
            output_pdf: Path to output PDF file
        
        Returns:
            PatternPDF with metadata
        """
        
        # Validate counts (allow flexibility for now)
        if len(question_set.questions) < 1:
            raise ValueError(f"Expected at least 1 question, got {len(question_set.questions)}")
        
        if len(rendered_diagrams) < 1:
            raise ValueError(f"Expected at least 1 diagram, got {len(rendered_diagrams)}")
        
        if len(question_set.questions) != len(rendered_diagrams):
            logger.warning(f"Mismatch: {len(question_set.questions)} questions vs {len(rendered_diagrams)} diagrams")
        
        logger.info(f"Building PDF for pattern {question_set.pattern_id}: {question_set.pattern_name} ({len(question_set.questions)} questions)")
        
        # Create document
        doc = SimpleDocTemplate(
            output_pdf,
            pagesize=self.page_size,
            leftMargin=self.margin,
            rightMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin
        )
        
        # Build story (content)
        story = []
        pages = []
        
        # Title
        title = Paragraph(
            f"Pattern {question_set.pattern_id}: {question_set.pattern_name}",
            self.styles['PatternTitle']
        )
        story.append(title)
        story.append(Spacer(1, 0.3 * inch))
        
        # Questions with diagrams
        for i, question in enumerate(question_set.questions):
            diagram = rendered_diagrams[i]
            
            # Question text (always include)
            q_text = Paragraph(
                f"<b>Question {i+1}:</b> {question.question_text}",
                self.styles['Question']
            )
            story.append(q_text)
            story.append(Spacer(1, 0.1 * inch))
            
            # Try to load diagram if it rendered successfully
            if diagram and diagram.success:
                try:
                    if Path(diagram.png_path).exists():
                        logger.info(f"Loading diagram: {diagram.png_path}")
                        
                        # Validate PNG file before embedding
                        validation_result = self._validate_png_for_embedding(diagram.png_path)
                        if not validation_result["valid"]:
                            logger.error(f"PNG validation failed: {validation_result['error']}")
                            # Continue without image rather than failing the entire PDF
                        else:
                            # Convert to absolute path for ReportLab compatibility
                            abs_path = str(Path(diagram.png_path).absolute())
                            logger.info(f"Absolute path: {abs_path}")
                            
                            # Get actual image dimensions and scale proportionally
                            pil_img = PILImage.open(abs_path)
                            img_width_px, img_height_px = pil_img.size
                            logger.info(f"Original image size: {img_width_px}x{img_height_px}px")
                            
                            # Calculate aspect ratio and fit to reasonable size
                            max_width = 4.0 * inch  # Reasonable max width for page
                            aspect_ratio = img_height_px / img_width_px
                            
                            # Use appropriate width - prioritize diagram_width but respect max_width
                            img_width = min(self.diagram_width, max_width)
                            img_height = img_width * aspect_ratio
                            
                            # Ensure image isn't too tall
                            max_height = 3.0 * inch
                            if img_height > max_height:
                                img_height = max_height
                                img_width = img_height / aspect_ratio
                            
                            # Create image with proper dimensions
                            logger.info(f"Final image size: {img_width/inch:.2f}x{img_height/inch:.2f} inches")
                            img = Image(abs_path, width=img_width, height=img_height)
                            
                            # Simply add the image (no table centering for now)
                            story.append(img)
                            story.append(Spacer(1, 0.15 * inch))
                            logger.info(f"Successfully added image to story")
                    else:
                        logger.warning(f"Diagram file not found: {diagram.png_path}")
                except Exception as e:
                    logger.error(f"Failed to load image {diagram.png_path}: {e}")
                    import traceback
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    # Continue without image rather than failing the entire PDF
            else:
                logger.warning(f"Diagram {i} failed to render (status: {diagram.success if diagram else 'None'}), skipping image")
                if diagram and diagram.error_message:
                    logger.warning(f"Render error: {diagram.error_message}")
            
            # Answer below the image
            answer = Paragraph(
                f"<b>Answer:</b> {question.correct_answer}",
                self.styles['Answer']
            )
            story.append(answer)
            story.append(Spacer(1, 0.2 * inch))
            
            # Page break after every question except the last
            if i < 9:
                story.append(PageBreak())
            
            # Add to pages list (always include questions)
            diagram_path = None
            if diagram and diagram.success:
                diagram_path = diagram.png_path
            
            pages.append(PDFPage(
                page_number=i+1,
                question_id=question.instance_id,
                question_text=question.question_text,
                tikz_code=question.tikz_code,
                answer=question.correct_answer,
                image_path=diagram_path or ""
            ))
        
        # Build PDF
        try:
            doc.build(story)
            logger.info(f"Successfully built PDF: {output_pdf}")
        except Exception as e:
            logger.error(f"Failed to build PDF: {e}")
            raise
        
        # Create metadata object
        return PatternPDF(
            pattern_id=question_set.pattern_id,
            pattern_name=question_set.pattern_name,
            pdf_path=output_pdf,
            pages=pages,
            generation_time=0.0  # TODO: Add timing
        )
    
    def _validate_png_for_embedding(self, png_path: str) -> dict:
        """
        Validate PNG file before embedding in PDF.
        
        Args:
            png_path: Path to PNG file
        
        Returns:
            {"valid": bool, "error": str|null}
        """
        try:
            path = Path(png_path)
            
            # Check file exists
            if not path.exists():
                return {"valid": False, "error": "PNG file does not exist"}
            
            # Check file size
            file_size = path.stat().st_size
            if file_size == 0:
                return {"valid": False, "error": "PNG file is empty"}
            
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                return {"valid": False, "error": f"PNG file too large: {file_size / 1024 / 1024:.1f}MB"}
            
            # Try to open with PIL to validate
            with PILImage.open(png_path) as img:
                # Check image dimensions
                if img.size[0] == 0 or img.size[1] == 0:
                    return {"valid": False, "error": f"Invalid image dimensions: {img.size}"}
                
                # Check image mode
                if img.mode not in ['RGB', 'RGBA', 'L']:
                    return {"valid": False, "error": f"Unsupported image mode: {img.mode}"}
                
                # Verify it's actually a PNG
                if img.format != 'PNG':
                    return {"valid": False, "error": f"Expected PNG format, got {img.format}"}
            
            return {"valid": True, "error": None}
            
        except Exception as e:
            return {"valid": False, "error": f"PNG validation failed: {str(e)}"}
    
    @staticmethod
    def get_image_dimensions(
        image_path: str
    ) -> Tuple[float, float]:
        """
        Get image dimensions (width, height) in inches.
        
        Args:
            image_path: Path to image file
        
        Returns:
            (width_inches, height_inches)
        """
        try:
            with PILImage.open(image_path) as img:
                width_px, height_px = img.size
                # Assume 300 DPI
                width_in = width_px / 300.0
                height_in = height_px / 300.0
                return width_in, height_in
        except Exception as e:
            logger.error(f"Failed to get image dimensions: {e}")
            return 3.0, 3.0  # Default
