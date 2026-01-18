"""
Validation subsystem for questions and diagrams.
Ensures schema correctness, variable consistency, and TikZ compilability.
"""

import logging
import json
from typing import List, Dict, Tuple, Any, Optional

from .schemas import QuestionInstance, QuestionSet
from .tikz_renderer import TikZValidator

logger = logging.getLogger(__name__)


class QuestionValidator:
    """Validates questions for correctness and consistency."""
    
    @staticmethod
    def validate_instance(question: QuestionInstance) -> Tuple[bool, List[str]]:
        """
        Validate a single question instance.
        
        Args:
            question: QuestionInstance to validate
        
        Returns:
            (is_valid, error_list)
        """
        errors = []
        
        # Check text fields
        if not question.question_text or len(question.question_text.strip()) < 10:
            errors.append("question_text is empty or too short")
        
        if not question.correct_answer or len(question.correct_answer.strip()) < 1:
            errors.append("correct_answer is empty")
        
        # Check variables
        if not isinstance(question.variables, dict):
            errors.append("variables must be a dictionary")
        elif len(question.variables) == 0:
            errors.append("variables dictionary is empty")
        
        # Validate TikZ code
        tikz_valid, tikz_error = TikZValidator.validate(question.tikz_code)
        if not tikz_valid:
            errors.append(f"TikZ validation failed: {tikz_error}")
        
        # Check variable-text consistency (heuristic)
        for var_name, var_value in question.variables.items():
            var_str = str(var_value)
            if var_str not in question.question_text and str(var_name) not in question.question_text:
                # Note: Variables might not appear literally in text,
                # but their values should
                logger.debug(
                    f"Variable '{var_name}={var_value}' may not be used in question text"
                )
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_set(question_set: QuestionSet) -> Tuple[bool, List[str]]:
        """
        Validate entire question set.
        
        Args:
            question_set: QuestionSet to validate
        
        Returns:
            (is_valid, error_list)
        """
        errors = []
        
        # Check count
        if len(question_set.questions) != 10:
            errors.append(f"Expected 10 questions, got {len(question_set.questions)}")
        
        # Check uniqueness and consistency
        instance_ids = set()
        for i, question in enumerate(question_set.questions):
            # Check instance_id
            if question.instance_id in instance_ids:
                errors.append(f"Duplicate instance_id: {question.instance_id}")
            instance_ids.add(question.instance_id)
            
            # Check pattern_id consistency
            if question.pattern_id != question_set.pattern_id:
                errors.append(
                    f"Instance {i}: pattern_id mismatch "
                    f"({question.pattern_id} vs {question_set.pattern_id})"
                )
            
            # Validate individual question
            valid, q_errors = QuestionValidator.validate_instance(question)
            if not valid:
                errors.extend([f"Instance {i}: {err}" for err in q_errors])
        
        return len(errors) == 0, errors


class SolvabilityChecker:
    """
    Checks if a question is actually solvable.
    
    This is a heuristic checker that validates:
    - Answer is not empty or trivial
    - Question contains enough information
    - Answer seems reasonable for the question type
    """
    
    @staticmethod
    def check(question: QuestionInstance) -> Tuple[str, Optional[str]]:
        """
        Check if a question is solvable.
        
        Args:
            question: QuestionInstance to check
        
        Returns:
            (status, error_message) where status is 'valid', 'invalid', or 'pending'
        """
        
        # Check answer
        answer = question.correct_answer.strip()
        if not answer or answer.lower() == "unknown" or answer.lower() == "n/a":
            return "invalid", "Answer is empty or trivial"
        
        # Check question text
        question_text = question.question_text.strip()
        if not question_text:
            return "invalid", "Question text is empty"
        
        # Check question marks or is worded as a question
        if not any(char in question_text for char in ["?", "Find", "Calculate", "Determine", "Solve"]):
            logger.warning(f"Question may not be properly worded: {question_text[:50]}...")
        
        # Check that variables are used in both question and diagram
        if len(question.variables) == 0:
            return "invalid", "No variables defined"
        
        vars_in_question = 0
        for var_name in question.variables.keys():
            if var_name in question_text:
                vars_in_question += 1
        
        if vars_in_question == 0:
            logger.warning(f"No variables found in question text")
        
        # Check answer length
        if len(answer) < 2:
            return "invalid", "Answer too short"
        
        if len(answer) > 1000:
            logger.warning(f"Answer is very long: {len(answer)} chars")
        
        # If all checks pass
        return "valid", None
    
    @staticmethod
    def check_set(question_set: QuestionSet) -> Dict[int, Tuple[str, Optional[str]]]:
        """
        Check solvability of all questions in a set.
        
        Returns:
            Dict mapping instance_id -> (status, error_message)
        """
        results = {}
        for question in question_set.questions:
            status, error = SolvabilityChecker.check(question)
            results[question.instance_id] = (status, error)
        return results


class ConsistencyChecker:
    """
    Checks consistency between question text, variables, and diagram code.
    """
    
    @staticmethod
    def check_variable_consistency(
        question: QuestionInstance,
        pattern_variables: Dict[str, Any]
    ) -> List[str]:
        """
        Check if instance variables match pattern variable definitions.
        
        Args:
            question: QuestionInstance
            pattern_variables: Dict mapping variable name -> VariableDefinition
        
        Returns:
            List of consistency errors
        """
        errors = []
        
        # Check that all instance variables are defined in pattern
        for var_name, var_value in question.variables.items():
            if var_name not in pattern_variables:
                errors.append(f"Variable '{var_name}' not defined in pattern")
        
        # Check that all pattern variables are instantiated
        for var_name in pattern_variables.keys():
            if var_name not in question.variables:
                errors.append(f"Pattern variable '{var_name}' not instantiated")
        
        return errors
    
    @staticmethod
    def check_variable_usage(question: QuestionInstance) -> List[str]:
        """
        Check that all variables appear in question text or diagram code.
        
        Args:
            question: QuestionInstance
        
        Returns:
            List of unused variables
        """
        unused = []
        
        combined_text = (question.question_text + " " + question.tikz_code).lower()
        
        for var_name in question.variables.keys():
            if var_name.lower() not in combined_text:
                unused.append(var_name)
        
        return unused
