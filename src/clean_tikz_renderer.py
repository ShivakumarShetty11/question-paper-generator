"""
Clean TikZ Rendering Pipeline
Based on the reference architecture: TikZ → Standalone TEX → PDF → PNG
"""

import os
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Optional
import pypdfium2 as pdfium
from PIL import Image

logger = logging.getLogger(__name__)


class CleanTikZRenderer:
    """Clean TikZ renderer following the reference architecture."""
    
    # Simple standalone template - no complex fixes
    LATEX_TEMPLATE = r"""
\documentclass[tikz,border=2pt]{standalone}
\usepackage{tikz}
\usepackage{amssymb}
\usepackage{amsmath}
\begin{document}

\begin{tikzpicture}
%TIKZ_CODE%
\end{tikzpicture}

\end{document}
"""
    
    def __init__(
        self,
        temp_dir: str = "./temp",
        dpi: int = 300,
        tectonic_path: Optional[str] = None
    ):
        """
        Initialize clean TikZ renderer.
        
        Args:
            temp_dir: Directory for temporary files
            dpi: Output PNG DPI resolution
            tectonic_path: Path to tectonic binary
        """
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        self.dpi = dpi
        self.tectonic_path = tectonic_path or self._find_tectonic()
        
        if not self.tectonic_path:
            raise RuntimeError("tectonic binary not found. Install with: cargo install tectonic")
    
    def render(self, tikz_code: str, output_png: str) -> bool:
        """
        Render TikZ code to PNG using the clean pipeline.
        
        Args:
            tikz_code: Raw TikZ code from LLM
            output_png: Path to output PNG file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Step 1: Write standalone .tex file
            tex_file = self._write_tex_file(tikz_code)
            logger.info(f"Created TEX file: {tex_file}")
            
            # Step 2: Compile to PDF with Tectonic
            pdf_file = self._compile_to_pdf(tex_file)
            if not pdf_file:
                return False
            logger.info(f"Compiled to PDF: {pdf_file}")
            
            # Step 3: Convert PDF to PNG
            success = self._pdf_to_png(pdf_file, output_png)
            if success:
                logger.info(f"Converted to PNG: {output_png}")
            
            # Step 4: Cleanup
            self._cleanup(tex_file, pdf_file)
            
            return success
            
        except Exception as e:
            logger.error(f"Render failed: {e}")
            return False
    
    def _write_tex_file(self, tikz_code: str) -> Path:
        """Step 1: Write standalone .tex file."""
        # Simple validation - no complex fixes
        if not tikz_code or len(tikz_code.strip()) < 5:
            raise ValueError("TikZ code is empty or too short")
        
        # Basic safety check
        if tikz_code.count('{') != tikz_code.count('}'):
            raise ValueError("Mismatched braces in TikZ code")
        
        # Insert TikZ code into template
        latex_source = self.LATEX_TEMPLATE.replace("%TIKZ_CODE%", tikz_code)
        
        # Write to temporary file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.tex',
            dir=self.temp_dir,
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(latex_source)
            return Path(f.name)
    
    def _compile_to_pdf(self, tex_file: Path) -> Optional[Path]:
        """Step 2: Compile to PDF using Tectonic."""
        try:
            # Run tectonic
            result = subprocess.run(
                [self.tectonic_path, str(tex_file)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.temp_dir  # Run in temp directory
            )
            
            if result.returncode != 0:
                logger.error(f"Tectonic compilation failed:")
                logger.error(f"STDOUT: {result.stdout}")
                logger.error(f"STDERR: {result.stderr}")
                return None
            
            # Check if PDF was created
            pdf_file = tex_file.with_suffix('.pdf')
            if pdf_file.exists():
                return pdf_file
            else:
                logger.error("PDF file was not created")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("Tectonic compilation timeout")
            return None
        except Exception as e:
            logger.error(f"Tectonic execution failed: {e}")
            return None
    
    def _pdf_to_png(self, pdf_file: Path, output_png: str) -> bool:
        """Step 3: Convert PDF to PNG at 300 DPI."""
        try:
            # Open PDF
            pdf = pdfium.PdfDocument(str(pdf_file), password=None)
            
            # Render first page at 300 DPI
            page = pdf[0]
            scale = self.dpi / 72.0  # Convert DPI to scale factor
            bitmap = page.render(scale=scale, rotation=0)
            
            # Convert to PIL and save
            pil_image = bitmap.to_pil()
            pil_image.save(output_png, "PNG", quality=95)
            
            pdf.close()
            return True
            
        except Exception as e:
            logger.error(f"PDF to PNG conversion failed: {e}")
            return False
    
    def _cleanup(self, tex_file: Path, pdf_file: Path):
        """Step 4: Cleanup temporary files."""
        try:
            if tex_file.exists():
                tex_file.unlink()
            if pdf_file.exists():
                pdf_file.unlink()
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")
    
    @staticmethod
    def _find_tectonic() -> Optional[str]:
        """Find tectonic binary."""
        candidates = [
            "tectonic",
            "tectonic.exe",
            os.path.expanduser("~/.cargo/bin/tectonic"),
            os.path.expanduser("~/.cargo/bin/tectonic.exe"),
        ]
        
        for cmd in candidates:
            try:
                result = subprocess.run(
                    [cmd, "--version"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return cmd
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        
        return None


class SimpleTikZValidator:
    """Simple validator for TikZ code."""
    
    @staticmethod
    def validate(tikz_code: str) -> Tuple[bool, Optional[str]]:
        """
        Basic validation of TikZ code.
        
        Args:
            tikz_code: TikZ code snippet
        
        Returns:
            (is_valid, error_message)
        """
        if not tikz_code or len(tikz_code.strip()) < 5:
            return False, "TikZ code is empty or too short"
        
        if tikz_code.count('{') != tikz_code.count('}'):
            return False, "Mismatched braces in TikZ code"
        
        # Basic forbidden patterns check
        forbidden = [
            "import", "require", "usepackage", "documentclass", 
            "begin{document}", "end{document}", "tikzset"
        ]
        
        code_lower = tikz_code.lower()
        for pattern in forbidden:
            if pattern in code_lower:
                return False, f"Forbidden pattern detected: {pattern}"
        
        return True, None
