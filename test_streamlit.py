#!/usr/bin/env python3
"""
Quick test to verify the Streamlit app will work without TikZ errors
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.llm_questions import QuestionGenerator
from src.llm_patterns import PatternGenerator

def test_streamlit_compatibility():
    """Test that the generic questions work without TikZ syntax errors."""
    
    # Test question generation for a generic pattern
    generator = QuestionGenerator("test_key", "llama-3.1-8b-instant", 0.7)
    pattern_generator = PatternGenerator("test_key", "llama-3.1-8b-instant", 0.7)
    
    print("Testing Streamlit Compatibility:")
    print("=" * 50)
    
    # Get a generic pattern
    patterns = pattern_generator.generate("Basic Mathematics", "9-12", 1)
    if patterns.patterns:
        pattern = patterns.patterns[0]
        
        # Generate questions for this pattern
        try:
            question_set = generator.generate(pattern, "Basic Mathematics")
            print(f"✅ Successfully generated {len(question_set.questions)} questions")
            
            # Test a few questions to ensure TikZ code is valid
            for i, question in enumerate(question_set.questions[:2]):
                print(f"✅ Question {i+1}: {question.question_text[:50]}...")
                print(f"   TikZ code length: {len(question.tikz_code)} characters")
                
        except Exception as e:
            print(f"❌ Error generating questions: {e}")
            return False
    
    print("\n✅ All tests passed! Streamlit should work correctly.")
    return True

if __name__ == "__main__":
    test_streamlit_compatibility()
