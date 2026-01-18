"""
Utility functions for LLM response processing and JSON parsing.
"""

import json
import json5
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def escape_backslashes(text: str) -> str:
    """
    Escape unescaped backslashes in JSON strings.
    
    This handles LaTeX/TikZ commands like \\frac, \\draw, \\text, etc. that may appear
    in LLM responses but aren't properly escaped for JSON.
    
    Special handling: Protects LaTeX commands like \text, \theta, etc. from being
    interpreted as JSON escapes (\t, etc.)
    
    Args:
        text: Text potentially containing unescaped backslashes
    
    Returns:
        Text with properly escaped backslashes for JSON parsing
    """
    result = []
    i = 0
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text):
            next_char = text[i + 1]
            
            # Check if this is a LaTeX command (e.g., \text, \theta, \tau, etc.)
            # LaTeX commands start with \ followed by letters
            if next_char.isalpha():
                # This is a LaTeX command, escape the backslash
                result.append('\\\\')
                i += 1
            # Valid JSON escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
            elif next_char in ('"', '\\', '/', 'b', 'f', 'n', 'r', 'u'):
                # Only treat as JSON escape if it's actually meant to be one
                # For safety, escape these too unless they're clearly JSON
                result.append('\\\\')
                i += 1
            else:
                # Escape any other backslash
                result.append('\\\\')
                i += 1
        else:
            result.append(text[i])
            i += 1
    return ''.join(result)


def clean_response_text(response_text: str) -> str:
    """
    Clean and normalize LLM response text for JSON parsing.
    
    Handles:
    - Literal newlines and other control characters in JSON strings
    - Unescaped quotes and special characters
    - Unescaped backslashes (LaTeX/TikZ)
    
    Args:
        response_text: Raw response from LLM
    
    Returns:
        Cleaned text ready for JSON parsing
    """
    # Replace actual control characters with spaces (newlines, tabs, etc.)
    # This is needed because JSON doesn't allow literal newlines in strings
    cleaned = []
    for char in response_text:
        # Replace actual control characters with space
        if ord(char) < 32:
            cleaned.append(' ')  # Replace all control chars with space
        else:
            cleaned.append(char)
    response_text = ''.join(cleaned)
    
    # Escape unescaped backslashes (must do before JSON parsing)
    response_text = escape_backslashes(response_text)
    
    return response_text


def extract_json_from_markdown(response_text: str) -> str:
    """
    Extract JSON from markdown code blocks if present.
    
    Args:
        response_text: Response that may contain markdown code blocks
    
    Returns:
        JSON text, either extracted or original
    """
    if "```json" in response_text:
        return response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        return response_text.split("```")[1].split("```")[0].strip()
    return response_text


def fix_tikz_json_parsing(response_text: str) -> str:
    """
    Fix the specific JSON parsing issue where LLM generates unescaped quotes in TikZ code.
    
    The main issue is that the LLM generates TikZ code with unescaped quotes that break JSON parsing.
    """
    
    # Look for the specific pattern where tikz_code has unescaped quotes
    if '"tikz_code":' not in response_text:
        return response_text
    
    # Split by lines to handle multi-line TikZ code
    lines = response_text.split('\n')
    fixed_lines = []
    
    for i, line in enumerate(lines):
        if '"tikz_code":' in line:
            # This is the start of the problematic field
            # Extract the opening part
            before_tikz = line.split('"tikz_code":')[0]
            fixed_lines.append(before_tikz + '"tikz_code":')
            
            # Now collect all the TikZ code until we find the proper closing
            tikz_content_lines = []
            j = i + 1
            
            # Skip the quote that starts the TikZ code
            if j < len(lines) and lines[j].strip().startswith('"'):
                j += 1
            
            # Collect TikZ code lines until we hit a line that ends the JSON field
            while j < len(lines):
                current_line = lines[j].strip()
                tikz_content_lines.append(current_line)
                
                # Check if this line ends the TikZ code field
                if current_line.endswith('",') or current_line.endswith('"'):
                    break
                j += 1
            
            # Combine and escape the TikZ code
            if tikz_content_lines:
                tikz_content = '\n'.join(tikz_content_lines)
                # Remove the surrounding quotes if present
                if tikz_content.startswith('"') and tikz_content.endswith('"'):
                    tikz_content = tikz_content[1:-1]
                
                # Escape backslashes and quotes for JSON
                escaped_tikz = tikz_content.replace('\\', '\\\\').replace('"', '\\"')
                
                # Add the properly escaped TikZ code
                fixed_lines.append(f'"{escaped_tikz}"')
                
                # Add the rest of the lines
                if j + 1 < len(lines):
                    fixed_lines.extend(lines[j + 1:])
            break
        else:
            fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)


def parse_json_response(response_text: str) -> Any:
    """
    Parse JSON response from LLM with multiple fallback strategies.
    
    Args:
        response_text: Response text containing JSON
    
    Returns:
        Parsed JSON data (list or dict)
    
    Raises:
        ValueError: If JSON cannot be parsed
    """
    import json
    import json5
    import logging
    import re
    
    logger.debug(f"Attempting to parse JSON response: {response_text[:200]}...")
    
    # First, try the specialized TikZ fix
    try:
        fixed_response = fix_tikz_json_parsing(response_text)
        if fixed_response != response_text:
            logger.debug("Applied TikZ JSON parsing fix")
        response_text = fixed_response
    except Exception as e:
        logger.debug(f"TikZ JSON fix failed: {e}")
    
    # Strategy 1: Standard json.loads()
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.debug(f"Standard JSON parsing failed: {e}")
        
        # Strategy 2: json5.loads() (more lenient)
        try:
            return json5.loads(response_text)
        except Exception:
            logger.debug("JSON5 parsing failed")
            raise ValueError(f"Invalid JSON response from LLM: {e}")
                elif '"' in line and not line.rstrip().endswith('"'):
                    string_lines[i] = line.rstrip() + '"'
                else:
                    string_lines[i] = line + '"'
            
            cleaned = '\n'.join(string_lines)
            
            # Fix degree symbols and other special characters in TikZ
            cleaned = re.sub(r':([^"]*\d+\.?\d*)°?\]', r':\1]', cleaned)  # Fix :59.93°] to :59.93]
            
            # Fix trailing commas before closing brackets
            cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)
            
            # Fix missing quotes around keys (but not in TikZ code)
            # Be more careful to avoid breaking TikZ code
            final_lines = cleaned.split('\n')
            for i, line in enumerate(final_lines):
                # Skip lines that look like TikZ code
                if '\\draw' in line or '\\node' in line or 'tikzpicture' in line:
                    continue
                # Fix missing quotes around keys in non-TikZ lines
                final_lines[i] = re.sub(r'(\w+):', r'"\1":', line)
            
            cleaned = '\n'.join(final_lines)
            
            # Fix incomplete strings by adding closing quotes
            string_lines = cleaned.split('\n')
            for i, line in enumerate(string_lines):
                # Count quotes in line
                quote_count = line.count('"')
                if quote_count % 2 == 1:  # Odd number of quotes
                    # Add closing quote if line ends with incomplete string
                    if line.rstrip().endswith('"'):
                        pass  # Already ends with quote
                    elif '"' in line and not line.rstrip().endswith('"'):
                        string_lines[i] = line.rstrip() + '"'
                    else:
                        string_lines[i] = line + '"'
            
            cleaned = '\n'.join(string_lines)
            
            # Try parsing cleaned JSON
            try:
                return json5.loads(cleaned)
            except Exception as e:
                logger.error(f"Response text (first 500 chars): {response_text[:500]}")
                logger.error(f"Cleaned response (first 500 chars): {cleaned[:500]}")
                raise ValueError(f"Invalid JSON response from LLM: {e}")


def process_llm_response(response_text: str) -> Any:
    """
    Complete LLM response processing pipeline.
    
    Cleans, extracts markdown, and parses JSON in a single call.
    
    Args:
        response_text: Raw response from LLM
    
    Returns:
        Parsed JSON data
    
    Raises:
        ValueError: If processing fails
    """
    response_text = clean_response_text(response_text)
    response_text = extract_json_from_markdown(response_text)
    return parse_json_response(response_text)
