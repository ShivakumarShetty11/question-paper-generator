#!/usr/bin/env python3
"""
Test script to verify diverse question generation with images
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.llm_questions import QuestionGenerator
from src.llm_patterns import PatternGenerator

def test_diverse_questions():
    """Test that questions are now diverse and image-based."""
    
    # Test question generation
    generator = QuestionGenerator("test_key", "llama-3.1-8b-instant", 0.7)
    pattern_generator = PatternGenerator("test_key", "llama-3.1-8b-instant", 0.7)
    
    print("Testing Distance Formula Questions with Images:")
    print("=" * 60)
    
    # Get patterns first
    patterns = pattern_generator.generate("Coordinate Geometry", "9-12", 1)
    if patterns.patterns:
        pattern = patterns.patterns[0]
        
        # Generate questions for this pattern
        question_set = generator.generate(pattern, "Coordinate Geometry")
        
        for i, question in enumerate(question_set.questions[:3]):  # Show first 3
            print(f"\nQuestion {i+1}:")
            print(f"  Text: {question.question_text}")
            print(f"  Answer: {question.correct_answer}")
            print(f"  TikZ Code: {question.tikz_code[:100]}...")
            print(f"  Variables: {question.variables}")
            print(f"  Difficulty: {question.difficulty}")
    
    print("\n" + "=" * 60)
    print("Testing Quadratic Factoring Questions with Images:")
    print("=" * 60)
    
    # Get quadratic patterns
    patterns2 = pattern_generator.generate("Quadratic Equations", "9-12", 1)
    if patterns2.patterns:
        pattern2 = patterns2.patterns[0]
        
        # Generate questions for this pattern
        question_set2 = generator.generate(pattern2, "Quadratic Equations")
        
        for i, question in enumerate(question_set2.questions[:3]):  # Show first 3
            print(f"\nQuestion {i+1}:")
            print(f"  Text: {question.question_text}")
            print(f"  Answer: {question.correct_answer}")
            print(f"  TikZ Code: {question.tikz_code[:100]}...")
            print(f"  Variables: {question.variables}")
            print(f"  Difficulty: {question.difficulty}")

if __name__ == "__main__":
    test_diverse_questions()
