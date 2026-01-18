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
    # Only replace actual control characters (except newlines which we'll handle in TikZ fix)
    cleaned = []
    for char in response_text:
        # Replace control characters except newline, tab, carriage return
        if ord(char) < 32 and char not in ['\n', '\t', '\r']:
            cleaned.append(' ')  # Replace control chars with space
        else:
            cleaned.append(char)
    response_text = ''.join(cleaned)
    
    # Don't do any backslash escaping here - let fix_tikz_json_parsing handle it
    # This avoids double-escaping issues
    
    return response_text


def extract_json_from_markdown(response_text: str) -> str:
    """
    Extract JSON from markdown code blocks or from responses that start with text.
    
    Args:
        response_text: Response that may contain markdown code blocks or text before JSON
    
    Returns:
        JSON text, either extracted or original
    """
    # First, try to extract from markdown code blocks
    if "```json" in response_text:
        return response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        return response_text.split("```")[1].split("```")[0].strip()
    
    # If no markdown, look for JSON array or object in the text
    # Find the first occurrence of [ or { that starts a valid JSON
    import re
    
    # Look for JSON array pattern
    array_match = re.search(r'\[\s*\{', response_text)
    if array_match:
        start_pos = array_match.start()
        # Find the end of the JSON by counting braces
        brace_count = 0
        in_string = False
        escape_next = False
        
        for i, char in enumerate(response_text[start_pos:], start=start_pos):
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\' and in_string:
                escape_next = True
                continue
                
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
                
            if not in_string:
                if char == '[' or char == '{':
                    brace_count += 1
                elif char == ']' or char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return response_text[start_pos:i+1].strip()
    
    # Look for JSON object pattern
    object_match = re.search(r'\{\s*"', response_text)
    if object_match:
        start_pos = object_match.start()
        # Similar brace counting for object
        brace_count = 0
        in_string = False
        escape_next = False
        
        for i, char in enumerate(response_text[start_pos:], start=start_pos):
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\' and in_string:
                escape_next = True
                continue
                
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
                
            if not in_string:
                if char == '[' or char == '{':
                    brace_count += 1
                elif char == ']' or char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return response_text[start_pos:i+1].strip()
    
    # If no JSON found, return original
    return response_text.strip()


def fix_tikz_json_parsing(response_text: str) -> str:
    """
    Fix the specific JSON parsing issue where LLM generates unescaped quotes in TikZ code.
    
    The main issue is that the LLM generates TikZ code with unescaped quotes that break JSON parsing.
    """
    
    # Look for the specific pattern where tikz_code has unescaped quotes
    if '"tikz_code":' not in response_text:
        return response_text
    
    logger.debug(f"Applying TikZ JSON parsing fix to response with {response_text.count('tikz_code')} tikz_code fields")
    
    import re
    
    # Use a more robust approach: find all tikz_code fields and fix them individually
    def fix_single_tikz_field(text):
        """Fix a single tikz_code field"""
        # Find the start and end of the tikz_code content
        start_match = re.search(r'"tikz_code":\s*"', text)
        if not start_match:
            return text
        
        start_pos = start_match.end()
        # Find the end of the JSON string (looking for the closing quote)
        pos = start_pos
        brace_count = 0
        in_escape = False
        
        while pos < len(text):
            char = text[pos]
            if char == '\\' and not in_escape:
                in_escape = True
                pos += 1
            elif char == '\\' and in_escape:
                in_escape = False
                pos += 1
            elif char == '"' and not in_escape:
                # Found the end of the string
                end_pos = pos
                break
            elif char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
            elif brace_count == 0 and char in ',}':
                # End of the field
                end_pos = pos
                break
            else:
                pos += 1
        else:
            # Reached end of text
            end_pos = len(text) - 1
        
        # Extract the TikZ content
        tikz_content = text[start_pos:end_pos]
        
        # Fix the TikZ content for JSON
        # 1. First, escape any unescaped backslashes (but don't double-escape already escaped ones)
        tikz_content = re.sub(r'(?<!\\)\\', r'\\\\', tikz_content)
        # 2. Then, escape unescaped quotes (but NOT backslashes)
        tikz_content = tikz_content.replace('"', '\\"')
        # 3. Escape literal newlines as \n (but keep it as a single line)
        tikz_content = tikz_content.replace('\n', '\\n')
        # 4. Escape literal carriage returns
        tikz_content = tikz_content.replace('\r', '\\r')
        # 5. Escape other problematic characters
        tikz_content = tikz_content.replace('\t', '\\t')
        
        # Reconstruct the field
        return text[:start_pos] + f'"tikz_code": "{tikz_content}"' + text[end_pos + 1:]
    
    # Apply the fix repeatedly until no more tikz_code fields need fixing
    fixed_response = response_text
    max_iterations = 10  # Prevent infinite loops
    iterations = 0
    
    while '"tikz_code":' in fixed_response and iterations < max_iterations:
        new_response = fix_single_tikz_field(fixed_response)
        if new_response == fixed_response:
            break  # No more changes needed
        fixed_response = new_response
        iterations += 1
    
    logger.debug(f"Fixed response length: {len(fixed_response)} chars (iterations: {iterations})")
    return fixed_response


def manually_fix_tikz_quotes(response_text: str) -> str:
    """
    Manual fallback to fix unescaped quotes in TikZ code.
    This is a more aggressive approach for when other fixes fail.
    """
    import re
    
    # Find all tikz_code fields and fix their quotes
    pattern = r'"tikz_code":\s*"([^"]*(?:\\.[^"]*)*)"'
    
    def fix_tikz_match(match):
        tikz_content = match.group(1)
        # Escape any unescaped quotes within the TikZ code
        escaped = re.sub(r'(?<!\\)"', r'\\"', tikz_content)
        return f'"tikz_code": "{escaped}"'
    
    # Apply the fix
    fixed = re.sub(pattern, fix_tikz_match, response_text, flags=re.DOTALL)
    
    # If no tikz_code field was found, try a more general approach
    if fixed == response_text:
        # Look for any JSON string that contains TikZ-like content and fix quotes
        lines = response_text.split('\n')
        fixed_lines = []
        in_tikz = False
        
        for line in lines:
            if '"tikz_code":' in line:
                in_tikz = True
                fixed_lines.append(line)
            elif in_tikz and line.strip().endswith('",'):
                in_tikz = False
                # Fix quotes in this line before adding
                fixed_line = re.sub(r'(?<!\\)"', r'\\"', line.rstrip('",')) + '",'
                fixed_lines.append(fixed_line)
            elif in_tikz:
                # We're inside TikZ code, escape quotes
                fixed_line = re.sub(r'(?<!\\)"', r'\\"', line)
                fixed_lines.append(fixed_line)
            else:
                fixed_lines.append(line)
        
        fixed = '\n'.join(fixed_lines)
    
    return fixed


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
    
    # Check if response is empty or starts with non-JSON
    if not response_text.strip():
        raise ValueError("Empty response from LLM")
    
    # Log the first character to debug the "Unexpected H" error
    first_char = response_text.strip()[0] if response_text.strip() else 'EMPTY'
    logger.debug(f"First character of response: '{first_char}' (ASCII: {ord(first_char) if first_char != 'EMPTY' else 'N/A'})")
    
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
        logger.debug(f"Error location: line {e.lineno}, column {e.colno}")
        
        # Strategy 2: json5.loads() (more lenient)
        try:
            return json5.loads(response_text)
        except Exception as e2:
            logger.debug(f"JSON5 parsing failed: {e2}")
            
            # Strategy 3: Apply aggressive cleaning and try again
            try:
                cleaned_response = clean_response_text(response_text)
                extracted_json = extract_json_from_markdown(cleaned_response)
                return json5.loads(extracted_json)
            except Exception as e3:
                logger.debug(f"Aggressive cleaning failed: {e3}")
                
                # Strategy 4: Manual quote escaping for TikZ code
                try:
                    manual_fixed = manually_fix_tikz_quotes(response_text)
                    return json5.loads(manual_fixed)
                except Exception as e4:
                    logger.debug(f"Manual TikZ fix failed: {e4}")
                    
                    # Strategy 5: Try to reconstruct JSON from partial data
                    try:
                        return reconstruct_json_from_partial(response_text)
                    except Exception as e5:
                        logger.debug(f"JSON reconstruction failed: {e5}")
                        logger.error(f"Failed to parse response. Raw content: {repr(response_text[:500])}")
                        raise ValueError(f"Invalid JSON response from LLM: {e}")


def reconstruct_json_from_partial(response_text: str) -> Any:
    """
    Attempt to reconstruct valid JSON from malformed LLM response.
    This is a last resort when all other parsing strategies fail.
    """
    import json5
    import re
    
    logger.debug("Attempting JSON reconstruction from partial data")
    
    # Try to extract individual objects from the response
    objects = []
    
    # First, try to find complete JSON objects
    # Look for patterns that start with { and end with }
    object_starts = []
    pos = 0
    while pos < len(response_text):
        if response_text[pos] == '{':
            object_starts.append(pos)
        pos += 1
    
    # Extract objects between start positions
    for i, start_pos in enumerate(object_starts):
        # Find the end of this object
        end_pos = start_pos + 1
        brace_count = 1
        in_string = False
        
        while end_pos < len(response_text):
            char = response_text[end_pos]
            
            if char == '"' and not in_string:
                in_string = True
            elif char == '"' and in_string:
                # Check if it's escaped
                if end_pos > 0 and response_text[end_pos - 1] == '\\':
                    in_string = False
                else:
                    # End of string
                    in_string = False
            elif char == '{' and not in_string:
                brace_count += 1
            elif char == '}' and not in_string:
                brace_count -= 1
                if brace_count == 0:
                    # End of object
                    break
            end_pos += 1
        
        if end_pos < len(response_text):
            obj_text = response_text[start_pos:end_pos + 1]
            
            try:
                # Apply comprehensive fixes to this object
                fixed_obj = obj_text
                
                # Fix common TikZ code issues
                # 1. Fix unescaped quotes in tikz_code fields
                tikz_pattern = r'"tikz_code":\s*"([^"]*)"'
                def fix_tikz_content(content):
                    # Escape backslashes first
                    content = re.sub(r'(?<!\\)\\', r'\\\\', content)
                    # Then escape quotes
                    content = content.replace('"', '\\"')
                    # Escape other control characters
                    content = content.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
                    return content
                
                def replace_tikz_match(m):
                    return f'"tikz_code": "{fix_tikz_content(m.group(1))}"'
                
                fixed_obj = re.sub(tikz_pattern, replace_tikz_match, fixed_obj)
                
                # Fix other common JSON issues
                # 2. Fix trailing commas before closing braces
                fixed_obj = re.sub(r',\s*}', '}', fixed_obj)
                # 3. Fix missing commas between objects
                fixed_obj = re.sub(r'}\s*{', '},{', fixed_obj)
                # 4. Fix unescaped quotes in general
                fixed_obj = re.sub(r'(?<!\\)"', r'\\"', fixed_obj)
                # 5. Fix double-escaped backslashes
                fixed_obj = re.sub(r'\\\\\\\\', r'\\\\', fixed_obj)
                
                # Try to parse the fixed object
                obj = json5.loads(fixed_obj)
                objects.append(obj)
                logger.debug(f"Successfully reconstructed object {i+1}: {len(obj)} fields")
            except Exception as e:
                logger.debug(f"Failed to reconstruct object {i+1}: {e}")
                # Try a simpler approach - extract key-value pairs
                try:
                    simple_obj = extract_simple_kv_pairs(obj_text)
                    if simple_obj:
                        objects.append(simple_obj)
                        logger.debug(f"Successfully reconstructed simple object {i+1}: {len(simple_obj)} fields")
                except Exception as e2:
                    logger.debug(f"Simple KV extraction failed for object {i+1}: {e2}")
    
    if objects:
        logger.debug(f"Successfully reconstructed {len(objects)} objects")
        return objects
    else:
        # If no objects found, try to extract array directly
        try:
            # Look for array pattern
            array_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if array_match:
                array_text = array_match.group(0)
                # Apply fixes to the array
                fixed_array = array_text
                # Fix TikZ code in array
                def fix_tikz_array_content(content):
                    # Escape backslashes first
                    content = re.sub(r'(?<!\\)\\', r'\\\\', content)
                    # Then escape quotes
                    content = content.replace('"', '\\"')
                    # Escape other control characters
                    content = content.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
                    return content
                
                fixed_array = re.sub(r'"tikz_code":\s*"([^"]*)"', 
                                    lambda m: '"tikz_code": "' + fix_tikz_array_content(m.group(1)) + '"', 
                                    fixed_array)
                # Fix other issues
                fixed_array = re.sub(r'(?<!\\)"', r'\\"', fixed_array)
                fixed_array = re.sub(r',\s*]', ']', fixed_array)
                fixed_array = re.sub(r'\\\\\\\\', r'\\\\', fixed_array)
                
                result = json5.loads(fixed_array)
                logger.debug(f"Successfully reconstructed array: {len(result)} items")
                return result
        except Exception as e:
            logger.debug(f"Array reconstruction failed: {e}")
    
    raise ValueError("Failed to reconstruct any valid JSON from response")


def extract_simple_kv_pairs(text: str) -> dict:
    """
    Extract simple key-value pairs from malformed JSON text.
    """
    import re
    
    try:
        # Look for key: value patterns
        kv_pattern = r'"([^"]+)"\s*:\s*"([^"]*)"'
        matches = re.findall(kv_pattern, text)
        
        result = {}
        for key, value in matches:
            # Clean up the value
            clean_value = value.replace('\\"', '"').replace('\\\\', '\\')
            result[key] = clean_value
        
        # Add tikz_code if present (special handling)
        if 'tikz_code' in text and 'tikz_code' not in result:
            # Extract tikz_code content manually
            tikz_start = text.find('"tikz_code":')
            if tikz_start != -1:
                # Find the start of the content
                content_start = text.find('"', tikz_start)
                if content_start != -1:
                    # Find the end of the content
                    content_end = text.find('"', content_start + 1)
                    if content_end != -1:
                        tikz_content = text[content_start + 1:content_end]
                        # Clean the TikZ content
                        clean_tikz = tikz_content.replace('\\"', '"').replace('\\\\', '\\')
                        clean_tikz = clean_tikz.replace('\n', '\\n').replace('\r', '\\r')
                        result['tikz_code'] = clean_tikz
        
        return result if result else None
    except Exception as e:
        logger.debug(f"Simple KV extraction failed: {e}")
        return None


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
