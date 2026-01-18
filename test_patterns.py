#!/usr/bin/env python3
"""
Test script to verify diverse pattern generation
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.llm_patterns import PatternGenerator

def test_diverse_patterns():
    """Test that patterns are now diverse for different topics"""
    
    # Test coordinate geometry patterns
    generator = PatternGenerator("test_key", "llama-3.1-8b-instant", 0.7)
    
    print("Testing Coordinate Geometry Patterns:")
    print("=" * 50)
    
    patterns = generator.generate("Coordinate Geometry", "9-12", 5)
    
    for i, pattern in enumerate(patterns.patterns):
        print(f"\nPattern {i+1}:")
        print(f"  Name: {pattern.pattern_name}")
        print(f"  Question: {pattern.question_template}")
        print(f"  Variables: {[var.name for var in pattern.variables]}")
        print(f"  Difficulty: {pattern.difficulty}")
    
    print("\n" + "=" * 50)
    print("Testing Quadratic Equations Patterns:")
    print("=" * 50)
    
    patterns2 = generator.generate("Quadratic Equations", "9-12", 5)
    
    for i, pattern in enumerate(patterns2.patterns):
        print(f"\nPattern {i+1}:")
        print(f"  Name: {pattern.pattern_name}")
        print(f"  Question: {pattern.question_template}")
        print(f"  Variables: {[var.name for var in pattern.variables]}")
        print(f"  Difficulty: {pattern.difficulty}")

    print("\n" + "=" * 50)
    print("Testing Trigonometry Patterns:")
    print("=" * 50)
    
    patterns3 = generator.generate("Trigonometry", "9-12", 3)
    
    for i, pattern in enumerate(patterns3.patterns):
        print(f"\nPattern {i+1}:")
        print(f"  Name: {pattern.pattern_name}")
        print(f"  Question: {pattern.question_template}")
        print(f"  Variables: {[var.name for var in pattern.variables]}")
        print(f"  Difficulty: {pattern.difficulty}")

if __name__ == "__main__":
    test_diverse_patterns()
