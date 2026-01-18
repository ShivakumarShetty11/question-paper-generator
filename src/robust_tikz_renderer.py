"""
Robust TikZ Rendering Pipeline
Follows the exact 5-step pipeline:
1. Generate TikZ code from the LLM (based on image specification)
2. Write it into a standalone .tex file
3. Compile with Tectonic
4. Convert to PNG with pypdfium2
5. Embed in the final PDF
"""

import os
import logging
import subprocess
import tempfile
import re
import json
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import pypdfium2 as pdfium
from PIL import Image
import io
import time

logger = logging.getLogger(__name__)


class RobustTikZRenderer:
    """
    Robust TikZ renderer that follows the exact 5-step pipeline.
    Designed to minimize errors and provide comprehensive error reporting.
    """
    
    # Enhanced standalone template with better error handling
    LATEX_TEMPLATE = r"""
\documentclass[tikz,border=2pt,12pt]{standalone}
\usepackage{tikz}
\usepackage{amssymb}
\usepackage{amsmath}
\usepackage{unicode-math}
\usepackage{fontspec}
\usetikzlibrary{arrows.meta,positioning,shapes.geometric,calc}

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
        keep_intermediate: bool = False,
        max_retries: int = 3
    ):
        """
        Initialize robust TikZ renderer.
        
        Args:
            temp_dir: Directory for temporary files
            dpi: Output PNG DPI resolution
            tectonic_path: Path to tectonic binary
            keep_intermediate: Keep intermediate files for debugging
            max_retries: Maximum number of retries for each step
        """
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        self.dpi = dpi
        self.keep_intermediate = keep_intermediate
        self.max_retries = max_retries
        
        # Locate tectonic binary
        self.tectonic_path = tectonic_path or self._find_tectonic()
        if not self.tectonic_path:
            raise RuntimeError("tectonic binary not found. Install with: cargo install tectonic")
        
        logger.info(f"Initialized RobustTikZRenderer with DPI={dpi}, temp_dir={temp_dir}")
    
    def render(self, tikz_code: str, output_png: str) -> Dict[str, Any]:
        """
        Render TikZ code to PNG using the robust 5-step pipeline.
        
        Args:
            tikz_code: Raw TikZ code from LLM
            output_png: Path to output PNG file
        
        Returns:
            Dictionary with render status, metadata, and error details
        """
        start_time = time.time()
        render_metadata = {
            "success": False,
            "output_png": output_png,
            "tikz_code": tikz_code,
            "steps_completed": [],
            "errors": [],
            "warnings": [],
            "execution_time": 0,
            "intermediate_files": {}
        }
        
        try:
            logger.info(f"Starting robust TikZ rendering pipeline")
            logger.debug(f"Original TikZ code: {tikz_code[:200]}...")
            
            # Step 1: Generate and clean TikZ code
            cleaned_tikz, step1_errors = self._generate_clean_tikz_code(tikz_code)
            render_metadata["steps_completed"].append("tikz_code_generation")
            render_metadata["warnings"].extend(step1_errors)
            
            # Step 2: Write standalone .tex file
            tex_file, step2_errors = self._write_standalone_tex_file(cleaned_tikz)
            render_metadata["steps_completed"].append("tex_file_creation")
            render_metadata["intermediate_files"]["tex"] = str(tex_file)
            render_metadata["errors"].extend(step2_errors)
            
            if not tex_file:
                raise RuntimeError("Failed to create TEX file")
            
            # Step 3: Compile with Tectonic
            pdf_file, step3_errors = self._compile_with_tectonic(tex_file)
            render_metadata["steps_completed"].append("tectonic_compilation")
            if pdf_file:
                render_metadata["intermediate_files"]["pdf"] = str(pdf_file)
            render_metadata["errors"].extend(step3_errors)
            
            if not pdf_file:
                raise RuntimeError("Tectonic compilation failed")
            
            # Step 4: Convert to PNG with pypdfium2
            png_success, step4_errors = self._convert_to_png_with_pypdfium2(pdf_file, output_png)
            render_metadata["steps_completed"].append("png_conversion")
            render_metadata["errors"].extend(step4_errors)
            
            if not png_success:
                raise RuntimeError("PDF to PNG conversion failed")
            
            # Step 5: Validate final PNG (embedding preparation)
            png_validated, step5_errors = self._validate_final_png(output_png)
            render_metadata["steps_completed"].append("png_validation")
            render_metadata["errors"].extend(step5_errors)
            
            if not png_validated:
                raise RuntimeError("Final PNG validation failed")
            
            # Success!
            render_metadata["success"] = True
            logger.info(f"Successfully rendered TikZ to {output_png}")
            
        except Exception as e:
            render_metadata["errors"].append(f"Pipeline failed: {str(e)}")
            logger.error(f"TikZ rendering pipeline failed: {e}")
        
        finally:
            # Cleanup intermediate files if not keeping them
            if not self.keep_intermediate:
                self._cleanup_intermediate_files(render_metadata["intermediate_files"])
            
            # Calculate execution time
            render_metadata["execution_time"] = time.time() - start_time
            
            # Log completion
            if render_metadata["success"]:
                logger.info(f"Pipeline completed successfully in {render_metadata['execution_time']:.2f}s")
            else:
                logger.error(f"Pipeline failed after {render_metadata['execution_time']:.2f}s")
                logger.error(f"Errors: {render_metadata['errors']}")
        
        return render_metadata
    
    def _generate_clean_tikz_code(self, tikz_code: str) -> Tuple[str, list]:
        """
        Step 1: Generate and clean TikZ code from LLM output.
        
        Args:
            tikz_code: Raw TikZ code from LLM
        
        Returns:
            (cleaned_tikz_code, errors)
        """
        errors = []
        
        try:
            if not tikz_code or len(tikz_code.strip()) < 5:
                raise ValueError("TikZ code is empty or too short")
            
            # Apply comprehensive cleaning
            cleaned = self._clean_tikz_code(tikz_code)
            
            # Validate cleaned code
            is_valid, validation_error = self._validate_tikz_code(cleaned)
            if not is_valid:
                errors.append(f"TikZ validation warning: {validation_error}")
            
            logger.debug(f"Cleaned TikZ code: {cleaned[:200]}...")
            return cleaned, errors
            
        except Exception as e:
            errors.append(f"TikZ code cleaning failed: {str(e)}")
            return tikz_code, errors
    
    def _write_standalone_tex_file(self, tikz_code: str) -> Tuple[Optional[Path], list]:
        """
        Step 2: Write TikZ code into a standalone .tex file.
        
        Args:
            tikz_code: Cleaned TikZ code
        
        Returns:
            (tex_file_path, errors)
        """
        errors = []
        
        for attempt in range(self.max_retries):
            try:
                # Insert TikZ code into template
                latex_source = self.LATEX_TEMPLATE.replace("%TIKZ_CODE%", tikz_code)
                
                # Create temporary file with unique name
                timestamp = int(time.time() * 1000)
                tex_filename = f"tikz_render_{timestamp}_{attempt}.tex"
                tex_path = self.temp_dir / tex_filename
                
                # Write with UTF-8 encoding
                with open(tex_path, 'w', encoding='utf-8') as f:
                    f.write(latex_source)
                
                # Verify file was created and is readable
                if not tex_path.exists() or tex_path.stat().st_size == 0:
                    raise RuntimeError("TEX file creation failed")
                
                logger.debug(f"Created TEX file: {tex_path}")
                return tex_path, errors
                
            except Exception as e:
                errors.append(f"TEX file creation (attempt {attempt + 1}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))  # Brief delay before retry
        
        return None, errors
    
    def _compile_with_tectonic(self, tex_file: Path) -> Tuple[Optional[Path], list]:
        """
        Step 3: Compile standalone .tex file with Tectonic.
        
        Args:
            tex_file: Path to TEX file
        
        Returns:
            (pdf_file_path, errors)
        """
        errors = []
        pdf_file = tex_file.with_suffix('.pdf')
        
        for attempt in range(self.max_retries):
            try:
                # Clean up any existing PDF
                if pdf_file.exists():
                    pdf_file.unlink()
                
                # Run tectonic with comprehensive error capture
                result = subprocess.run(
                    [self.tectonic_path, tex_file.name],  # Use just the filename, not full path
                    capture_output=True,
                    text=True,
                    timeout=60,  # Increased timeout
                    cwd=str(tex_file.parent),  # Run in the directory containing the tex file
                    env={**os.environ, "TEXINPUTS": f"{tex_file.parent}{os.pathsep}"},
                    encoding='utf-8',  # Explicitly set UTF-8 encoding
                    errors='replace'  # Handle encoding errors gracefully
                )
                
                # Log detailed output for debugging
                if result.stdout:
                    logger.debug(f"Tectonic STDOUT: {result.stdout}")
                if result.stderr:
                    logger.debug(f"Tectonic STDERR: {result.stderr}")
                
                if result.returncode != 0:
                    error_msg = f"Tectonic failed (attempt {attempt + 1}): {result.stderr}"
                    errors.append(error_msg)
                    
                    # Try to extract more specific error information
                    if "Error:" in result.stderr:
                        specific_error = [line for line in result.stderr.split('\n') if 'Error:' in line]
                        if specific_error:
                            errors.append(f"Specific error: {specific_error[0].strip()}")
                    
                    if attempt < self.max_retries - 1:
                        time.sleep(0.2 * (attempt + 1))  # Exponential backoff
                    continue
                
                # Check if PDF was created and is valid
                if not pdf_file.exists():
                    errors.append(f"Tectonic completed but PDF not created (attempt {attempt + 1})")
                    continue
                
                if pdf_file.stat().st_size == 0:
                    errors.append(f"PDF created but empty (attempt {attempt + 1})")
                    pdf_file.unlink()
                    continue
                
                logger.debug(f"Successfully compiled PDF: {pdf_file}")
                return pdf_file, errors
                
            except subprocess.TimeoutExpired:
                errors.append(f"Tectonic timeout (attempt {attempt + 1})")
                if attempt < self.max_retries - 1:
                    time.sleep(1.0 * (attempt + 1))
            except Exception as e:
                errors.append(f"Tectonic execution failed (attempt {attempt + 1}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))
        
        return None, errors
    
    def _convert_to_png_with_pypdfium2(self, pdf_file: Path, output_png: str) -> Tuple[bool, list]:
        """
        Step 4: Convert PDF to PNG using pypdfium2 with robust error handling.
        
        Args:
            pdf_file: Path to PDF file
            output_png: Output PNG path
        
        Returns:
            (success, errors)
        """
        errors = []
        pdf_doc = None
        
        for attempt in range(self.max_retries):
            try:
                # Ensure output directory exists
                output_path = Path(output_png)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Open PDF with error handling
                try:
                    pdf_doc = pdfium.PdfDocument(str(pdf_file))
                except Exception as e:
                    errors.append(f"Failed to open PDF (attempt {attempt + 1}): {str(e)}")
                    if attempt < self.max_retries - 1:
                        time.sleep(0.1 * (attempt + 1))
                    continue
                
                # Get first page
                try:
                    page = pdf_doc[0]
                except Exception as e:
                    errors.append(f"Failed to get PDF page (attempt {attempt + 1}): {str(e)}")
                    if attempt < self.max_retries - 1:
                        time.sleep(0.1 * (attempt + 1))
                    continue
                
                # Calculate scale factor for target DPI
                scale_factor = self.dpi / 72.0
                
                # Render page with error handling
                try:
                    bitmap = page.render(
                        scale=scale_factor,
                        rotation=0,
                        crop=(0, 0, 0, 0)
                    )
                except Exception as e:
                    errors.append(f"Failed to render PDF page (attempt {attempt + 1}): {str(e)}")
                    if attempt < self.max_retries - 1:
                        time.sleep(0.1 * (attempt + 1))
                    continue
                
                # Convert to PIL Image and save
                try:
                    pil_image = bitmap.to_pil()
                    
                    # Validate image
                    if pil_image.size[0] == 0 or pil_image.size[1] == 0:
                        raise RuntimeError("Rendered image has zero dimensions")
                    
                    # Save with high quality
                    pil_image.save(output_png, "PNG", quality=95, optimize=True)
                    
                    # Verify saved file
                    if not Path(output_png).exists():
                        raise RuntimeError("PNG file was not saved")
                    
                    if Path(output_png).stat().st_size == 0:
                        raise RuntimeError("PNG file is empty")
                    
                    logger.debug(f"Successfully converted PDF to PNG: {output_png}")
                    return True, errors
                    
                except Exception as e:
                    errors.append(f"Failed to save PNG (attempt {attempt + 1}): {str(e)}")
                    if attempt < self.max_retries - 1:
                        time.sleep(0.1 * (attempt + 1))
                    continue
                
            except Exception as e:
                errors.append(f"PDF to PNG conversion failed (attempt {attempt + 1}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))
            
            finally:
                # Always close PDF document
                if pdf_doc is not None:
                    try:
                        pdf_doc.close()
                    except:
                        pass
                    pdf_doc = None
        
        return False, errors
    
    def _validate_final_png(self, output_png: str) -> Tuple[bool, list]:
        """
        Step 5: Validate final PNG for embedding in PDF.
        
        Args:
            output_png: Path to output PNG file
        
        Returns:
            (is_valid, errors)
        """
        errors = []
        
        try:
            png_path = Path(output_png)
            
            # Check file exists
            if not png_path.exists():
                errors.append("PNG file does not exist")
                return False, errors
            
            # Check file size
            file_size = png_path.stat().st_size
            if file_size == 0:
                errors.append("PNG file is empty")
                return False, errors
            
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                errors.append(f"PNG file too large: {file_size / 1024 / 1024:.1f}MB")
            
            # Try to open with PIL to validate
            try:
                with Image.open(output_png) as img:
                    # Check image dimensions
                    if img.size[0] == 0 or img.size[1] == 0:
                        errors.append(f"Invalid image dimensions: {img.size}")
                        return False, errors
                    
                    # Check image mode
                    if img.mode not in ['RGB', 'RGBA', 'L']:
                        errors.append(f"Unexpected image mode: {img.mode}")
                    
                    logger.debug(f"PNG validation passed: {img.size}, mode={img.mode}, size={file_size}")
                    
            except Exception as e:
                errors.append(f"PIL validation failed: {str(e)}")
                return False, errors
            
            return True, errors
            
        except Exception as e:
            errors.append(f"PNG validation failed: {str(e)}")
            return False, errors
    
    def _clean_tikz_code(self, tikz_code: str) -> str:
        """
        Clean and fix common issues in LLM-generated TikZ code.
        """
        # Remove common problematic patterns
        tikz_code = tikz_code.strip()
        
        # Fix escaped characters that might have been double-escaped
        tikz_code = tikz_code.replace('\\\\', '\\')
        
        # Fix Unicode degree symbol
        tikz_code = re.sub(r'(\d+\.?\d*)°', r'$\1^\\circ$', tikz_code)
        
        # Fix Greek letters
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
        
        # Fix mathematical expressions in node content - more conservative approach
        # Handle specific, safe patterns only
        math_patterns = [
            # Measurements with units (safe)
            (r'\{([0-9]+\.[0-9]+)\s*cm\}', r'{$\1$ cm}'),
            (r'\{([0-9]+)\s*cm\}', r'{$\1$ cm}'),
            (r'\{([0-9]+\.[0-9]+)\s*units\}', r'{$\1$ units}'),
            (r'\{([0-9]+)\s*units\}', r'{$\1$ units}'),
        ]
        
        for pattern, replacement in math_patterns:
            tikz_code = re.sub(pattern, replacement, tikz_code)
        
        # Fix corrupted LaTeX commands
        tikz_code = re.sub(r'\s+ext\{', r' \\text{', tikz_code)
        tikz_code = re.sub(r',\s*ext\{', r', \\text{', tikz_code)
        
        # Remove the aggressive node math fixing that was causing issues
        # The conservative approach above is safer
        
        return tikz_code
    
    def _validate_tikz_code(self, tikz_code: str) -> Tuple[bool, Optional[str]]:
        """
        Basic validation of TikZ code.
        """
        if not tikz_code or len(tikz_code.strip()) < 5:
            return False, "TikZ code is empty or too short"
        
        if tikz_code.count('{') != tikz_code.count('}'):
            return False, "Mismatched braces in TikZ code"
        
        # Check for forbidden patterns
        forbidden_patterns = [
            '\\input', '\\include', '\\write', '\\read', '\\openout',
            '\\closeout', '\\shell', '\\immediate', '\\def', '\\xdef',
            '\\edef', '\\let', '\\newcommand', '\\renewcommand'
        ]
        
        code_lower = tikz_code.lower()
        for pattern in forbidden_patterns:
            if pattern in code_lower:
                return False, f"Forbidden pattern detected: {pattern}"
        
        return True, None
    
    def _cleanup_intermediate_files(self, files: Dict[str, str]):
        """
        Clean up intermediate files if not keeping them.
        """
        for file_type, file_path in files.items():
            try:
                path = Path(file_path)
                if path.exists():
                    path.unlink()
                    logger.debug(f"Cleaned up {file_type} file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup {file_type} file {file_path}: {e}")
    
    @staticmethod
    def _find_tectonic() -> Optional[str]:
        """
        Locate tectonic binary in system PATH.
        """
        candidates = [
            "tectonic",
            "tectonic.exe",
            os.path.expanduser("~/.cargo/bin/tectonic"),
            os.path.expanduser("~/.cargo/bin/tectonic.exe"),
            str(Path.cwd() / "tectonic.exe"),  # Local tectonic.exe
        ]
        
        for cmd in candidates:
            try:
                result = subprocess.run(
                    [cmd, "--version"],
                    capture_output=True,
                    timeout=10
                )
                if result.returncode == 0:
                    logger.info(f"Found tectonic binary: {cmd}")
                    return cmd
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        
        return None


class RobustTikZValidator:
    """
    Enhanced validator for TikZ code with comprehensive checks.
    """
    
    @staticmethod
    def validate(tikz_code: str) -> Tuple[bool, Optional[str]]:
        """
        Comprehensive validation of TikZ code.
        
        Returns:
            (is_valid, error_message)
        """
        if not tikz_code or len(tikz_code.strip()) < 5:
            return False, "TikZ code is empty or too short"
        
        # Basic syntax checks
        if tikz_code.count('{') != tikz_code.count('}'):
            return False, "Mismatched braces in TikZ code"
        
        if tikz_code.count('[') != tikz_code.count(']'):
            return False, "Mismatched brackets in TikZ code"
        
        # Security checks
        forbidden_patterns = [
            '\\input', '\\include', '\\write', '\\read', '\\openout',
            '\\closeout', '\\shell', '\\immediate', '\\def', '\\xdef',
            '\\edef', '\\let', '\\newcommand', '\\renewcommand',
            '\\usepackage', '\\documentclass', '\\begin{document}', '\\end{document}'
        ]
        
        code_lower = tikz_code.lower()
        for pattern in forbidden_patterns:
            if pattern in code_lower:
                return False, f"Forbidden pattern detected: {pattern}"
        
        # Check for basic TikZ structure
        if not any(keyword in tikz_code.lower() for keyword in ['\\draw', '\\node', '\\coordinate', '\\path']):
            return False, "No TikZ drawing commands found"
        
        return True, None
