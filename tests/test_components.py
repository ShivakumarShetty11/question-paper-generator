"""
Unit tests for pipeline components.
"""

import unittest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.schemas import (
    VariableDefinition,
    QuestionPattern,
    PatternSchema,
    QuestionInstance,
    QuestionSet
)
from src.tikz_renderer import TikZValidator
from src.validator import QuestionValidator, SolvabilityChecker


class TestVariableDefinition(unittest.TestCase):
    """Test variable definition schema."""
    
    def test_valid_int_variable(self):
        var = VariableDefinition(
            name="radius",
            type="int",
            min_value=1,
            max_value=10,
            description="Circle radius in cm"
        )
        self.assertEqual(var.name, "radius")
        self.assertEqual(var.type, "int")
    
    def test_valid_float_variable(self):
        var = VariableDefinition(
            name="angle",
            type="float",
            min_value=0.0,
            max_value=360.0,
            unit="degrees",
            description="Angle in degrees"
        )
        self.assertEqual(var.type, "float")
        self.assertEqual(var.unit, "degrees")
    
    def test_invalid_type_raises_error(self):
        with self.assertRaises(ValueError):
            VariableDefinition(
                name="x",
                type="invalid_type",
                description="Test"
            )


class TestQuestionPattern(unittest.TestCase):
    """Test question pattern schema."""
    
    def setUp(self):
        self.valid_pattern = {
            "pattern_id": 0,
            "pattern_name": "Circle Area",
            "topic": "Geometry",
            "diagram_description": "A circle with radius r labeled",
            "question_template": "Find the area of a circle with radius {radius} cm",
            "variables": [
                {
                    "name": "radius",
                    "type": "int",
                    "min_value": 1,
                    "max_value": 10,
                    "description": "Radius in cm"
                }
            ],
            "grade_level": "9",
            "difficulty": "easy",
            "learning_objective": "Calculate circle area"
        }
    
    def test_valid_pattern(self):
        pattern = QuestionPattern(**self.valid_pattern)
        self.assertEqual(pattern.pattern_id, 0)
        self.assertEqual(pattern.pattern_name, "Circle Area")
    
    def test_invalid_pattern_id_raises_error(self):
        self.valid_pattern['pattern_id'] = 15
        with self.assertRaises(ValueError):
            QuestionPattern(**self.valid_pattern)


class TestPatternSchema(unittest.TestCase):
    """Test pattern schema (collection of 10 patterns)."""
    
    def test_must_have_exactly_10_patterns(self):
        patterns = [
            QuestionPattern(
                pattern_id=i,
                pattern_name=f"Pattern {i}",
                topic="Math",
                diagram_description="Test diagram",
                question_template="Test question",
                variables=[],
                grade_level="9",
                difficulty="easy",
                learning_objective="Test"
            )
            for i in range(8)  # Only 8 patterns
        ]
        
        with self.assertRaises(ValueError):
            PatternSchema(
                topic="Math",
                patterns=patterns,
                generation_timestamp="2024-01-17T00:00:00",
                model_used="gpt-4"
            )


class TestQuestionInstance(unittest.TestCase):
    """Test question instance schema."""
    
    def setUp(self):
        self.valid_instance = {
            "instance_id": 0,
            "pattern_id": 0,
            "topic": "Geometry",
            "variables": {"radius": 5},
            "question_text": "Find the area of a circle with radius 5 cm",
            "correct_answer": "78.54 cm²",
            "tikz_code": r"\draw (0,0) circle (2);",
            "difficulty": "easy"
        }
    
    def test_valid_instance(self):
        instance = QuestionInstance(**self.valid_instance)
        self.assertEqual(instance.instance_id, 0)
        self.assertEqual(instance.variables["radius"], 5)
    
    def test_solvability_check_default_value(self):
        instance = QuestionInstance(**self.valid_instance)
        self.assertEqual(instance.solvability_check, "pending")


class TestTikZValidator(unittest.TestCase):
    """Test TikZ code validation."""
    
    def test_valid_simple_tikz(self):
        tikz_code = r"\draw (0,0) circle (2);"
        is_valid, error = TikZValidator.validate(tikz_code)
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_tikz_with_forbidden_pattern(self):
        tikz_code = r"\usepackage{tikzlibrary}"
        is_valid, error = TikZValidator.validate(tikz_code)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
    
    def test_empty_tikz_code(self):
        tikz_code = ""
        is_valid, error = TikZValidator.validate(tikz_code)
        self.assertFalse(is_valid)
    
    def test_mismatched_braces(self):
        tikz_code = r"\draw (0,0) {circle (2);"
        is_valid, error = TikZValidator.validate(tikz_code)
        self.assertFalse(is_valid)
        self.assertIn("brace", error.lower())


class TestQuestionValidator(unittest.TestCase):
    """Test question validation."""
    
    def setUp(self):
        self.valid_instance = QuestionInstance(
            instance_id=0,
            pattern_id=0,
            topic="Geometry",
            variables={"radius": 5},
            question_text="Find the area of a circle with radius 5 cm?",
            correct_answer="78.54 cm²",
            tikz_code=r"\draw (0,0) circle (2);",
            difficulty="easy"
        )
    
    def test_validate_valid_instance(self):
        is_valid, errors = QuestionValidator.validate_instance(self.valid_instance)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_empty_question_text(self):
        self.valid_instance.question_text = ""
        is_valid, errors = QuestionValidator.validate_instance(self.valid_instance)
        self.assertFalse(is_valid)
        self.assertTrue(any("question_text" in err for err in errors))
    
    def test_validate_empty_answer(self):
        self.valid_instance.correct_answer = ""
        is_valid, errors = QuestionValidator.validate_instance(self.valid_instance)
        self.assertFalse(is_valid)


class TestSolvabilityChecker(unittest.TestCase):
    """Test solvability checking."""
    
    def setUp(self):
        self.valid_instance = QuestionInstance(
            instance_id=0,
            pattern_id=0,
            topic="Geometry",
            variables={"radius": 5},
            question_text="Find the area of a circle with radius 5 cm?",
            correct_answer="78.54 cm²",
            tikz_code=r"\draw (0,0) circle (2);",
            difficulty="easy"
        )
    
    def test_valid_question_is_solvable(self):
        status, error = SolvabilityChecker.check(self.valid_instance)
        self.assertEqual(status, "valid")
        self.assertIsNone(error)
    
    def test_empty_answer_is_invalid(self):
        self.valid_instance.correct_answer = ""
        status, error = SolvabilityChecker.check(self.valid_instance)
        self.assertEqual(status, "invalid")
        self.assertIsNotNone(error)
    
    def test_trivial_answer_is_invalid(self):
        self.valid_instance.correct_answer = "unknown"
        status, error = SolvabilityChecker.check(self.valid_instance)
        self.assertEqual(status, "invalid")


if __name__ == '__main__':
    unittest.main()
