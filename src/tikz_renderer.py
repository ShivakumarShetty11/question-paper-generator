"""
TikZ Rendering Subsystem
Converts TikZ code to PDF and PNG with pixel-perfect determinism.
"""

import os
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Optional
import pypdfium2 as pdfium
from PIL import Image
import io

# Set debug level for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TikZRenderer:
    """Renders TikZ diagrams to PNG via LaTeX and Tectonic."""
    
    # LaTeX template for standalone TikZ compilation
    LATEX_TEMPLATE = r"""
\documentclass[tikz,border=0pt,12pt]{standalone}
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
        tectonic_path: Optional[str] = None,
        keep_intermediate: bool = False
    ):
        """
        Initialize TikZ renderer.
        
        Args:
            temp_dir: Directory for temporary LaTeX/PDF files
            dpi: Output PNG DPI resolution
            tectonic_path: Path to tectonic binary (auto-detect if None)
            keep_intermediate: Keep LaTeX and PDF files for debugging
        """
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        self.dpi = dpi
        self.keep_intermediate = keep_intermediate
        
        # Locate tectonic binary
        self.tectonic_path = tectonic_path or self._find_tectonic()
        if not self.tectonic_path:
            raise RuntimeError("tectonic binary not found. Install with: cargo install tectonic")
    
    def render(self, tikz_code: str, output_png: str) -> bool:
        """
        Render TikZ code to PNG.
        
        Args:
            tikz_code: TikZ code snippet (without document wrapper)
            output_png: Path to output PNG file
        
        Returns:
            True if successful, False otherwise
        """
        
        try:
            # Fix mathematical expressions in TikZ code
            tikz_code = self._fix_math_expressions(tikz_code)
            
            # Log the processed TikZ code for debugging
            logger.debug(f"Processed TikZ code: {tikz_code}")
            
            # Create LaTeX source
            latex_source = self.LATEX_TEMPLATE.replace("%TIKZ_CODE%", tikz_code)
            
            # Log the LaTeX source for debugging
            logger.debug(f"LaTeX source (first 500 chars): {latex_source[:500]}")
            
            # Temporary file for LaTeX
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.tex',
                dir=self.temp_dir,
                delete=False,
                encoding='utf-8'  # Use UTF-8 encoding for Unicode support
            ) as tex_file:
                tex_file.write(latex_source)
                tex_path = Path(tex_file.name)
            
            logger.debug(f"Created LaTeX file: {tex_path}")
            
            # Compile with Tectonic
            pdf_path = tex_path.with_suffix('.pdf')
            if not self._compile_tectonic(str(tex_path)):
                logger.error(f"Tectonic compilation failed for {tex_path}")
                return False
            
            if not pdf_path.exists():
                logger.error(f"PDF not generated: {pdf_path}")
                return False
            
            logger.debug(f"Generated PDF: {pdf_path}")
            
            # Convert PDF to PNG
            if not self._pdf_to_png(str(pdf_path), output_png):
                logger.error(f"PDF to PNG conversion failed")
                return False
            
            logger.info(f"Successfully rendered diagram to {output_png}")
            
            # Cleanup intermediate files if not keeping them
            if not self.keep_intermediate:
                # Add retry mechanism for file deletion (Windows file locking)
                for i in range(5):
                    try:
                        tex_path.unlink()
                        break
                    except (PermissionError, OSError) as e:
                        logger.warning(f"Failed to delete {tex_path}, retrying...: {e}")
                        import time
                        time.sleep(0.1 * (2 ** i)) # Exponential backoff
                
                for i in range(5):
                    try:
                        pdf_path.unlink()
                        break
                    except (PermissionError, OSError) as e:
                        logger.warning(f"Failed to delete {pdf_path}, retrying...: {e}")
                        import time
                        time.sleep(0.1 * (2 ** i)) # Exponential backoff
            
            return True
            
        except Exception as e:
            logger.error(f"Render failed: {e}")
            return False
    
    def _fix_math_expressions(self, tikz_code: str) -> str:
        """
        Fix mathematical expressions in TikZ code to be LaTeX-compatible.

        Args:
            tikz_code: Raw TikZ code from LLM

        Returns:
            Fixed TikZ code with proper math mode
        """
        import re

        logger.debug(f"Original TikZ code (before fixes): {tikz_code}")

        # Fix 0: Fix corrupted LaTeX commands from string processing
        # When LLM generates \text, Python might interpret \t as tab
        # Look for patterns like "   ext{" and fix to "\text{"
        tikz_code = re.sub(r'\s+ext\{', r' \\text{', tikz_code)  # Fix spacing + ext{ → \text{
        tikz_code = re.sub(r',\s*ext\{', r', \\text{', tikz_code)  # Fix ,ext{ → ,\text{
        tikz_code = tikz_code.replace('\\,ext{', '\\,\\text{')  # Fix \,ext{ → \,\text{
        logger.debug(f"After LaTeX command fix: {tikz_code}")

        # Fix 1: Convert Unicode degree symbol (°) to LaTeX $..^\circ$
        # Replace patterns like "68°" with "$68^\circ$"
        tikz_code = re.sub(r'(\d+\.?\d*)°', r'$\1^\\circ$', tikz_code)
        logger.debug(f"After Unicode degree symbol fix: {tikz_code}")
        
        # Fix 2: Convert Greek letters to LaTeX commands
        greek_map = {
            'α': r'$\alpha$', 'β': r'$\beta$', 'γ': r'$\gamma$', 'δ': r'$\delta$',
            'ε': r'$\epsilon$', 'ζ': r'$\zeta$', 'η': r'$\eta$', 'θ': r'$\theta$',
            'ι': r'$\iota$', 'κ': r'$\kappa$', 'λ': r'$\lambda$', 'μ': r'$\mu$',
            'ν': r'$\nu$', 'ξ': r'$\xi$', 'π': r'$\pi$', 'ρ': r'$\rho$',
            'σ': r'$\sigma$', 'τ': r'$\tau$', 'υ': r'$\upsilon$', 'φ': r'$\phi$',
            'χ': r'$\chi$', 'ψ': r'$\psi$', 'ω': r'$\omega$',
        }
        for greek_char, latex_cmd in greek_map.items():
            tikz_code = tikz_code.replace(greek_char, latex_cmd)
        logger.debug(f"After Greek letter fix: {tikz_code}")
        
        # Fix 3: Fix LaTeX ^\circ that's not already in math mode
        # Only process if we didn't already add $ signs in Fix 1
        def _wrap_circ_in_math_mode(match):
            full_match_content = match.group(0)  # e.g., "{90^\circ}"
            
            # Check if already wrapped by counting $
            if '$' in full_match_content:
                return full_match_content  # Already fixed, don't touch it
            
            # Not in math mode, wrap it
            return re.sub(r'(\d+\.?\d*)\s*\^\s*\\circ', r'$\1^\\circ$', full_match_content)

        # Apply the fix to content within curly braces that don't already have $
        tikz_code = re.sub(
            r'\{[^}$]*?\d+\.?\d*\s*\^\s*\\circ[^}$]*?\}',
            _wrap_circ_in_math_mode,
            tikz_code
        )
        logger.debug(f"After LaTeX \\circ fix: {tikz_code}")

        # Fix 4: Simple approach - just fix basic measurement patterns
        # Replace measurements like "5.5 cm" with "$5.5$ cm" in node content
        tikz_code = re.sub(r'\{([0-9]+\.[0-9]+)\s*cm\}', r'{$\1$ cm}', tikz_code)
        tikz_code = re.sub(r'\{([0-9]+\.[0-9]+)\s*units\}', r'{$\1$ units}', tikz_code)
        # Also handle whole numbers
        tikz_code = re.sub(r'\{([0-9]+)\s*cm\}', r'{$\1$ cm}', tikz_code)
        tikz_code = re.sub(r'\{([0-9]+)\s*units\}', r'{$\1$ units}', tikz_code)
        logger.debug(f"After simple measurement fix: {tikz_code}")
        
        logger.debug(f"Fixed TikZ code (after all fixes): {tikz_code}")

        return tikz_code
    
    def _compile_tectonic(self, tex_path: str) -> bool:
        """
        Compile LaTeX source with Tectonic.
        
        Returns:
            True if successful
        """
        try:
            result = subprocess.run(
                [self.tectonic_path, tex_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"Tectonic stderr: {result.stderr}")
                return False
            
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("Tectonic compilation timeout")
            return False
        except Exception as e:
            logger.error(f"Tectonic execution failed: {e}")
            return False
    
    def _pdf_to_png(self, pdf_path: str, output_png: str, dpi: Optional[int] = None) -> bool:
        """
        Convert PDF to PNG using pypdfium2.
        
        Args:
            pdf_path: Path to PDF file
            output_png: Path to output PNG
            dpi: DPI (defaults to self.dpi)
        
        Returns:
            True if successful
        """
        pdf = None
        try:
            dpi = dpi or self.dpi
            
            # Open PDF using correct pypdfium2 API
            pdf = pdfium.PdfDocument(open(pdf_path, 'rb'))
            
            # Render first page at specified DPI with improved scaling
            page = pdf.get_page(0)
            
            # Get natural page size first
            page_width = page.get_width()
            page_height = page.get_height()
            
            # Calculate scale to achieve target DPI with reasonable size
            target_dpi = dpi
            base_dpi = 72.0  # PDF base DPI
            
            # Use a moderate scale to prevent oversized images but maintain quality
            scale_factor = min(target_dpi / base_dpi, 3.0)  # Increased cap to 3x for better visibility
            
            bitmap = page.render(
                scale=scale_factor,
                rotation=0
            )
            
            # Convert to PIL Image and save
            pil_image = bitmap.to_pil()
            pil_image.save(output_png, "PNG", quality=95)
            
            logger.debug(f"Converted PDF to PNG: {output_png}")
            return True
            
        except Exception as e:
            logger.error(f"PDF to PNG conversion failed: {e}")
            return False
        finally:
            # Ensure PDF is properly closed
            if pdf is not None:
                try:
                    pdf.close()
                except:
                    pass
    
    @staticmethod
    def _find_tectonic() -> Optional[str]:
        """
        Locate tectonic binary in system PATH.
        
        Returns:
            Path to tectonic binary, or None if not found
        """
        # Try common locations
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


class TikZValidator:
    """Validates TikZ code for compilation safety."""
    
    from .config import FORBIDDEN_TIKZ_PATTERNS
    
    @staticmethod
    def validate(tikz_code: str) -> Tuple[bool, Optional[str]]:
        """
        Validate TikZ code for forbidden patterns.
        
        Args:
            tikz_code: TikZ code snippet
        
        Returns:
            (is_valid, error_message)
        """
        from .config import FORBIDDEN_TIKZ_PATTERNS
        
        if not tikz_code or len(tikz_code.strip()) < 5:
            return False, "TikZ code is empty or too short"
        
        code_lower = tikz_code.lower()
        for pattern in FORBIDDEN_TIKZ_PATTERNS:
            if pattern.lower() in code_lower:
                return False, f"Forbidden pattern detected: {pattern}"
        
        # Check for basic syntax
        if tikz_code.count('{') != tikz_code.count('}'):
            return False, "Mismatched braces in TikZ code"
        
        return True, None
