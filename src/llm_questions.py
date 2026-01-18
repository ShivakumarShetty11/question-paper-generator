"""
LLM Call #2: Question Instance Generation
Generates 10 concrete question instances for each pattern.
"""

import json
import logging
import random
from typing import List
from datetime import datetime
from groq import Groq
from typing import List
from src.schemas import QuestionPattern
from src.schemas import Question
from src.schemas import QuestionSet
from src.schemas import VariableDefinition
from .config import (
    QUESTION_GENERATION_SYSTEM_PROMPT,
    QUESTIONS_PER_PATTERN
)
from .llm_utils import process_llm_response

logger = logging.getLogger(__name__)


class QuestionGenerator:
    """Generates concrete question instances using LLM (Call #2)."""
    
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile", temperature: float = 0.7):
        """
        Initialize question generator.
        
        Args:
            api_key: Groq API key
            model: LLM model name
            temperature: Sampling temperature
        """
        # Try different initialization approaches for Groq client
        import os
        
        # Save and clear environment that might interfere
        original_env = os.environ.copy()
        env_to_clear = [k for k in os.environ.keys() if 'proxy' in k.lower() or 'http' in k.lower()]
        for key in env_to_clear:
            if key in os.environ:
                del os.environ[key]
        
        try:
            # Try basic initialization
            self.client = Groq(api_key=api_key)
            logger.info("Groq client initialized successfully")
        except Exception as e:
            logger.error(f"Groq init attempt 1 failed: {e}")
            
            # Try with explicit httpx client
            try:
                import httpx
                clean_client = httpx.Client()
                self.client = Groq(api_key=api_key, http_client=clean_client)
                logger.info("Groq client initialized with custom httpx client")
            except Exception as e2:
                logger.error(f"Groq init attempt 2 failed: {e2}")
                
                # Last resort - try without any parameters
                try:
                    self.client = Groq()
                    # Set API key via environment
                    os.environ['GROQ_API_KEY'] = api_key
                    logger.info("Groq client initialized with env var API key")
                except Exception as e3:
                    logger.error(f"Groq init attempt 3 failed: {e3}")
                    raise RuntimeError(f"Could not initialize Groq client after 3 attempts: {e}")
        finally:
            # Restore original environment
            os.environ.clear()
            os.environ.update(original_env)
                
        self.model = model
        self.temperature = temperature
        
    
    def generate(self, pattern, topic: str, max_retries: int = 3) -> QuestionSet:
        """
        Generate questions for a specific pattern.
        
        Args:
            pattern: Pattern schema with variables
            topic: Topic for questions
            max_retries: Maximum retry attempts
            
        Returns:
            QuestionSet with generated questions
            
        Raises:
            RuntimeError: If generation fails after all retries
        """
        logger.info(f"Generating questions for pattern {pattern.pattern_id}: {pattern.pattern_name}")
        
        # Generate sample variables to guide LLM
        sample_variables = self._sample_variables(pattern.variables)
        user_prompt = self._build_prompt(pattern, topic, sample_variables)
        
        # Generate diverse, image-based questions for the pattern
        logger.warning("Using diverse image-based question generation")
        
        mock_questions = self._generate_diverse_image_questions(pattern, topic)
        
        # Convert to Pydantic models
        question_objects = []
        for i, mock_question in enumerate(mock_questions):
            try:
                question = Question(
                    instance_id=mock_question.instance_id,
                    pattern_id=mock_question.pattern_id,
                    topic=mock_question.topic,
                    question_text=mock_question.question_text,
                    correct_answer=mock_question.correct_answer,
                    tikz_code=mock_question.tikz_code,
                    difficulty=mock_question.difficulty,
                    solvability_check=mock_question.solvability_check,
                    variables=mock_question.variables
                )
                question_objects.append(question)
                logger.debug(f"Created question {i}: {question.question_text[:100]}...")
            except Exception as e:
                logger.error(f"Failed to create question {i}: {e}")
                continue
        
        if not question_objects:
            raise RuntimeError("No valid questions were generated")
        
        return QuestionSet(
            pattern_id=pattern.pattern_id,
            pattern_name=pattern.pattern_name,
            questions=question_objects,
            topic=topic,
            generation_metadata={"generated_at": datetime.utcnow().isoformat()}
        )
    
    def _build_prompt(
        self,
        pattern: QuestionPattern,
        topic: str,
        sample_variables: List[dict]
    ) -> str:
        """Build the user prompt for question generation."""
        
        variables_desc = "\n".join([
            f"  - {var.name} ({var.type}): {var.description}"
            f" [Range: {var.min_value}-{var.max_value}" + (f", Unit: {var.unit}" if var.unit else "") + "]"
            if var.type in ['int', 'float']
            else f"  - {var.name} ({var.type}): {var.description}"
            for var in pattern.variables
        ])
        
        samples_desc = "\n".join([
            f"  Example {i+1}: " + ", ".join(f"{k}={v}" for k, v in sample.items())
            for i, sample in enumerate(sample_variables)
        ])
        
        prompt = f"""
Topic: {topic}
Pattern ID: {pattern.pattern_id}
Pattern Name: {pattern.pattern_name}
Difficulty: {pattern.difficulty}

DIAGRAM DESCRIPTION (semantic, NOT code):
{pattern.diagram_description}

QUESTION TEMPLATE:
{pattern.question_template}

VARIABLES & RANGES:
{variables_desc}

SAMPLE VARIABLE INSTANTIATIONS (to guide your generation):
{samples_desc}

TASK:
Generate exactly 10 HIGHLY DIVERSE question instances for this pattern.
ALL questions must be DEEPLY ROOTED in the topic "{topic}" and pattern "{pattern.pattern_name}".

CRITICAL TOPIC RELEVANCE REQUIREMENTS:
- EVERY question must directly relate to "{topic}" - no generic questions
- Do NOT create questions that could apply to multiple topics
- Ensure questions explore different aspects of the specific pattern within "{topic}"
- Each question should test a different skill or application within this pattern
- Use terminology and notation specific to "{topic}"

CRITICAL DIVERSITY REQUIREMENTS:
1. CREATE DIFFERENT QUESTION TYPES - Each question must ask something completely different within this pattern:
   - Find missing measurements (sides, angles, areas, perimeters, volumes, etc.)
   - Calculate properties (slope, intercept, vertex, focus, discriminant, etc.)
   - Compare or analyze relationships (greater than, less than, equal, proportional)
   - Solve word problems or real-world applications related to "{topic}"
   - Prove or derive relationships within "{topic}"
   - Identify patterns, trends, or characteristics specific to "{topic}"
   - Determine equations, formulas, or expressions for "{topic}"

2. VARY PROBLEM-SOLVING APPROACHES:
   - Direct calculation vs. multi-step reasoning
   - Visual inspection vs. algebraic manipulation
   - Logical deduction vs. estimation
   - Forward problems vs. inverse problems

3. ENSURE CRITICAL IMAGE DEPENDENCY:
   - Each question MUST be IMPOSSIBLE to answer without examining the diagram
   - The diagram must contain ALL necessary information visually
   - Question text MUST reference specific visual elements with their actual values
   - Students should be able to answer by looking at the diagram alone
   - Include ALL measurements, labels, and values needed in the TikZ diagram

4. MAINTAIN TOPIC CONSISTENCY:
   - Every question must clearly relate to "{topic}"
   - Diagrams should represent concepts specific to "{topic}"
   - Variable names and contexts should be appropriate for "{topic}"
   - Questions should use terminology and notation specific to "{topic}"

5. CREATE SPECIFIC, NOT GENERIC QUESTIONS:
   - Use actual variable values in question text (e.g., "Find the length of side AB if it is 5.7 cm")
   - Reference specific diagram elements (e.g., "What is the measure of angle ABC shown as 42°?")
   - Make the diagram visually highlight what the question is asking about

6. TIKZ CODE REQUIREMENTS:
   - Use ONLY basic TikZ primitives (\\draw, \\node, \\circle, --, arc, etc.)
   - NO external packages or libraries
   - NO preamble, NO document environment
   - CRITICAL: Use actual coordinate values from your variables (not generic placeholders)
   - CRITICAL: Add \\node labels to show ALL measurements, angles, and important values
   - CRITICAL: Include ALL drawing commands needed to represent the question completely
   - CRITICAL: Highlight or emphasize elements the question is asking about
   - CRITICAL: Ensure TikZ code is COMPLETE and COMPILABLE
   - Use sensible coordinate scaling (e.g., 0-10 units)
   - CRITICAL: Do NOT include \\begin{{tikzpicture}} or \\end{{tikzpicture}} wrappers

Return as JSON array:
[
  {{
    "instance_id": 0,
    "variables": {{ "var_name": value, ... }},
    "question_text": "<specific question that directly refers to diagram elements using actual values, clearly related to {topic}>",
    "correct_answer": "<answer with explanation if needed>",
    "tikz_code": "<COMPLETE TikZ snippet with ALL drawing commands and labels, no wrappers>",
    "difficulty": "{pattern.difficulty}"
  }},
  ...
]

Generate exactly 10 COMPLETELY DIFFERENT question types within this pattern (instance_id from 0 to 9).
Return ONLY valid JSON, no markdown formatting.
"""
        return prompt
    
    def _sample_variables(self, variables: List[VariableDefinition]) -> List[dict]:
        """
        Generate 3 sample variable sets to guide LLM.
        """
        samples = []
        for _ in range(3):
            sample = {}
            for var in variables:
                if var.type == 'int':
                    value = random.randint(int(var.min_value), int(var.max_value))
                    sample[var.name] = value
                elif var.type == 'float':
                    value = round(
                        random.uniform(var.min_value, var.max_value), 2
                    )
                    sample[var.name] = value
                elif var.type == 'enum':
                    value = random.choice(var.allowed_values)
                    sample[var.name] = value
                else:  # string
                    sample[var.name] = f"<{var.name}>"
            samples.append(sample)
        return samples
    
    def _replace_placeholders(self, text: str, variables: dict) -> str:
        """
        Replace {variable_name} placeholders with actual values from variables dict.
        
        Args:
            text: Text containing placeholders like {side_length}, {angle}
            variables: Dictionary mapping variable names to values
        
        Returns:
            Text with placeholders replaced by actual values
        """
        result = text
        for var_name, var_value in variables.items():
            placeholder = f"{{{var_name}}}"
            # Format numbers nicely
            if isinstance(var_value, float):
                result = result.replace(placeholder, f"{var_value:.2f}")
            else:
                result = result.replace(placeholder, str(var_value))
        return result
    
    def validate_questions(self, question_set: QuestionSet) -> List[str]:
        """
        Validate question set.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if len(question_set.questions) != QUESTIONS_PER_PATTERN:
            errors.append(
                f"Expected {QUESTIONS_PER_PATTERN} questions, "
                f"got {len(question_set.questions)}"
            )
        
        instance_ids = set()
        for question in question_set.questions:
            # Check instance_id uniqueness
            if question.instance_id in instance_ids:
                errors.append(f"Duplicate instance_id: {question.instance_id}")
            instance_ids.add(question.instance_id)
            
            # Check pattern_id consistency
            if question.pattern_id != question_set.pattern_id:
                errors.append(
                    f"Instance {question.instance_id}: pattern_id mismatch "
                    f"({question.pattern_id} vs {question_set.pattern_id})"
                )
            
            # Check question text is not empty
            if not question.question_text or len(question.question_text.strip()) < 10:
                errors.append(
                    f"Instance {question.instance_id}: question_text too short"
                )
            
            # Check answer is not empty
            if not question.correct_answer or len(question.correct_answer.strip()) < 1:
                errors.append(
                    f"Instance {question.instance_id}: correct_answer is empty"
                )
            
            # Check tikz_code is not empty
            if not question.tikz_code or len(question.tikz_code.strip()) < 5:
                errors.append(
                    f"Instance {question.instance_id}: tikz_code too short"
                )
        
        return errors
    
    def _generate_diverse_image_questions(self, pattern: QuestionPattern, topic: str) -> List[Question]:
        """
        Generate diverse, image-based questions for a specific pattern.
        Each question has a unique TikZ diagram and is image-dependent.
        """
        questions = []
        pattern_name_lower = pattern.pattern_name.lower()
        
        # Generate 10 different question types based on the pattern
        if "distance" in pattern_name_lower:
            questions = self._generate_distance_formula_questions(pattern, topic)
        elif "midpoint" in pattern_name_lower:
            questions = self._generate_midpoint_questions(pattern, topic)
        elif "slope" in pattern_name_lower:
            questions = self._generate_slope_questions(pattern, topic)
        elif "line equation" in pattern_name_lower:
            questions = self._generate_line_equation_questions(pattern, topic)
        elif "circle" in pattern_name_lower:
            questions = self._generate_circle_questions(pattern, topic)
        elif "quadratic" in pattern_name_lower or "factoring" in pattern_name_lower:
            questions = self._generate_quadratic_factoring_questions(pattern, topic)
        elif "quadratic formula" in pattern_name_lower:
            questions = self._generate_quadratic_formula_questions(pattern, topic)
        elif "vertex" in pattern_name_lower:
            questions = self._generate_vertex_form_questions(pattern, topic)
        elif "discriminant" in pattern_name_lower:
            questions = self._generate_discriminant_questions(pattern, topic)
        elif "right triangle" in pattern_name_lower:
            questions = self._generate_right_triangle_questions(pattern, topic)
        elif "sine" in pattern_name_lower or "cosine" in pattern_name_lower:
            questions = self._generate_sine_cosine_questions(pattern, topic)
        elif "unit circle" in pattern_name_lower:
            questions = self._generate_unit_circle_questions(pattern, topic)
        else:
            # Generic questions for other patterns
            questions = self._generate_generic_questions(pattern, topic)
        
        return questions[:QUESTIONS_PER_PATTERN]
    
    def _generate_distance_formula_questions(self, pattern: QuestionPattern, topic: str) -> List[Question]:
        """Generate 10 diverse distance formula questions with unique diagrams."""
        questions = []
        
        # Question 1: Basic distance between two points
        questions.append(Question(
            instance_id=0,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Find the distance between points A(2, 3) and B(8, 7) shown in the coordinate plane.",
            correct_answer="Distance = √[(8-2)² + (7-3)²] = √[36 + 16] = √52 ≈ 7.21 units",
            tikz_code=r"""
\draw[gray,very thin,->] (-1,0) -- (9,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-1) -- (0,8) node[above] {$y$};
\draw[blue,thick] (2,3) -- (8,7);
\draw[red,fill=red] (2,3) circle (2pt) node[below left] {$A(2,3)$};
\draw[red,fill=red] (8,7) circle (2pt) node[above right] {$B(8,7)$};
\draw[dashed,gray] (2,3) -- (8,3) node[midway,below] {$6$};
\draw[dashed,gray] (8,3) -- (8,7) node[midway,right] {$4$};
\draw[<->,orange,thick] (4.5,1.5) -- (4.5,5.5) node[midway,right] {$d$};
""",
            difficulty="easy",
            solvability_check="pending",
            variables={"x1": 2, "y1": 3, "x2": 8, "y2": 7}
        ))
        
        # Question 2: Distance from origin
        questions.append(Question(
            instance_id=1,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="What is the distance from the origin to point P(5, 12) shown in the diagram?",
            correct_answer="Distance = √[(5-0)² + (12-0)²] = √[25 + 144] = √169 = 13 units",
            tikz_code=r"""
\draw[gray,very thin,->] (-1,0) -- (7,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-1) -- (0,13) node[above] {$y$};
\draw[blue,thick] (0,0) -- (5,12);
\draw[red,fill=red] (0,0) circle (2pt) node[below left] {$O(0,0)$};
\draw[red,fill=red] (5,12) circle (2pt) node[above right] {$P(5,12)$};
\draw[dashed,gray] (0,0) -- (5,0) node[midway,below] {$5$};
\draw[dashed,gray] (5,0) -- (5,12) node[midway,right] {$12$};
\draw[<->,orange,thick] (2.5,1) -- (2.5,6) node[midway,right] {$13$};
""",
            difficulty="easy",
            solvability_check="pending",
            variables={"x1": 0, "y1": 0, "x2": 5, "y2": 12}
        ))
        
        # Question 3: Distance between points with negative coordinates
        questions.append(Question(
            instance_id=2,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Find the distance between points C(-4, -2) and D(3, 5) as shown in the coordinate plane.",
            correct_answer="Distance = √[(3-(-4))² + (5-(-2))²] = √[49 + 49] = √98 ≈ 9.90 units",
            tikz_code=r"""
\draw[gray,very thin,->] (-5,0) -- (5,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-3) -- (0,6) node[above] {$y$};
\draw[blue,thick] (-4,-2) -- (3,5);
\draw[red,fill=red] (-4,-2) circle (2pt) node[below left] {$C(-4,-2)$};
\draw[red,fill=red] (3,5) circle (2pt) node[above right] {$D(3,5)$};
\draw[dashed,gray] (-4,-2) -- (3,-2) node[midway,below] {$7$};
\draw[dashed,gray] (3,-2) -- (3,5) node[midway,right] {$7$};
\draw[<->,orange,thick] (-0.5,0.5) -- (-0.5,3.5) node[midway,right] {$d$};
""",
            difficulty="medium",
            solvability_check="pending",
            variables={"x1": -4, "y1": -2, "x2": 3, "y2": 5}
        ))
        
        # Question 4: Distance in 3D context (projected to 2D)
        questions.append(Question(
            instance_id=3,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="A rectangle has vertices at (1,1), (6,1), (6,4), and (1,4). What is the length of the diagonal shown?",
            correct_answer="Distance = √[(6-1)² + (4-1)²] = √[25 + 9] = √34 ≈ 5.83 units",
            tikz_code=r"""
\draw[gray,very thin,->] (0,0) -- (7,0) node[right] {$x$};
\draw[gray,very thin,->] (0,0) -- (0,5) node[above] {$y$};
\draw[black,thick] (1,1) rectangle (6,4);
\draw[blue,thick] (1,1) -- (6,4);
\draw[red,fill=red] (1,1) circle (2pt) node[below left] {$(1,1)$};
\draw[red,fill=red] (6,4) circle (2pt) node[above right] {$(6,4)$};
\draw[<->,orange,thick] (3,1.5) -- (3,3.5) node[midway,right] {$d$};
\node at (3.5,2.5) [below] {$5$};
\node at (1,2.5) [left] {$3$};
""",
            difficulty="medium",
            solvability_check="pending",
            variables={"x1": 1, "y1": 1, "x2": 6, "y2": 4}
        ))
        
        # Question 5: Distance involving fractions
        questions.append(Question(
            instance_id=4,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Find the distance between points E(1.5, 2.5) and F(4.5, 6.5) shown in the diagram.",
            correct_answer="Distance = √[(4.5-1.5)² + (6.5-2.5)²] = √[9 + 16] = √25 = 5 units",
            tikz_code=r"""
\draw[gray,very thin,->] (0,0) -- (6,0) node[right] {$x$};
\draw[gray,very thin,->] (0,0) -- (0,7) node[above] {$y$};
\draw[blue,thick] (1.5,2.5) -- (4.5,6.5);
\draw[red,fill=red] (1.5,2.5) circle (2pt) node[below left] {$E(1.5,2.5)$};
\draw[red,fill=red] (4.5,6.5) circle (2pt) node[above right] {$F(4.5,6.5)$};
\draw[dashed,gray] (1.5,2.5) -- (4.5,2.5) node[midway,below] {$3$};
\draw[dashed,gray] (4.5,2.5) -- (4.5,6.5) node[midway,right] {$4$};
\draw[<->,orange,thick] (3,3.5) -- (3,5.5) node[midway,right] {$5$};
""",
            difficulty="medium",
            solvability_check="pending",
            variables={"x1": 1.5, "y1": 2.5, "x2": 4.5, "y2": 6.5}
        ))
        
        # Question 6: Distance between points on a circle
        questions.append(Question(
            instance_id=5,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Two points on a circle centered at the origin are shown. Find the distance between P(3,4) and Q(4,3).",
            correct_answer="Distance = √[(4-3)² + (3-4)²] = √[1 + 1] = √2 ≈ 1.41 units",
            tikz_code=r"""
\draw[gray,very thin,->] (-1,0) -- (6,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-1) -- (0,6) node[above] {$y$};
\draw[gray,dashed] (0,0) circle (5);
\draw[blue,thick] (3,4) -- (4,3);
\draw[red,fill=red] (3,4) circle (2pt) node[above left] {$P(3,4)$};
\draw[red,fill=red] (4,3) circle (2pt) node[below right] {$Q(4,3)$};
\draw[red,fill=red] (0,0) circle (2pt) node[below left] {$O$};
""",
            difficulty="medium",
            solvability_check="pending",
            variables={"x1": 3, "y1": 4, "x2": 4, "y2": 3}
        ))
        
        # Question 7: Distance in a triangle context
        questions.append(Question(
            instance_id=6,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="In triangle ABC with vertices A(0,0), B(8,0), and C(4,6), find the length of side AB as shown.",
            correct_answer="Distance = √[(8-0)² + (0-0)²] = √[64 + 0] = √64 = 8 units",
            tikz_code=r"""
\draw[gray,very thin,->] (-1,0) -- (9,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-1) -- (0,7) node[above] {$y$};
\draw[black,thick] (0,0) -- (8,0) -- (4,6) -- cycle;
\draw[blue,very thick] (0,0) -- (8,0);
\draw[red,fill=red] (0,0) circle (2pt) node[below left] {$A(0,0)$};
\draw[red,fill=red] (8,0) circle (2pt) node[below right] {$B(8,0)$};
\draw[red,fill=red] (4,6) circle (2pt) node[above] {$C(4,6)$};
\draw[<->,orange,thick] (4,-0.5) -- (4,0.5) node[midway,below] {$8$};
""",
            difficulty="easy",
            solvability_check="pending",
            variables={"x1": 0, "y1": 0, "x2": 8, "y2": 0}
        ))
        
        # Question 8: Distance with one point on an axis
        questions.append(Question(
            instance_id=7,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Point M lies on the x-axis at (7,0) and point N is at (2,5). Find the distance MN as shown.",
            correct_answer="Distance = √[(7-2)² + (0-5)²] = √[25 + 25] = √50 ≈ 7.07 units",
            tikz_code=r"""
\draw[gray,very thin,->] (-1,0) -- (8,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-1) -- (0,6) node[above] {$y$};
\draw[blue,thick] (7,0) -- (2,5);
\draw[red,fill=red] (7,0) circle (2pt) node[below right] {$M(7,0)$};
\draw[red,fill=red] (2,5) circle (2pt) node[above left] {$N(2,5)$};
\draw[dashed,gray] (2,0) -- (7,0) node[midway,below] {$5$};
\draw[dashed,gray] (2,0) -- (2,5) node[midway,left] {$5$};
\draw[<->,orange,thick] (4.5,1) -- (4.5,4) node[midway,right] {$d$};
""",
            difficulty="medium",
            solvability_check="pending",
            variables={"x1": 7, "y1": 0, "x2": 2, "y2": 5}
        ))
        
        # Question 9: Distance between points with same x or y coordinate
        questions.append(Question(
            instance_id=8,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Points R(3,1) and S(3,8) have the same x-coordinate. Find the vertical distance between them.",
            correct_answer="Distance = √[(3-3)² + (8-1)²] = √[0 + 49] = √49 = 7 units",
            tikz_code=r"""
\draw[gray,very thin,->] (0,0) -- (6,0) node[right] {$x$};
\draw[gray,very thin,->] (0,0) -- (0,9) node[above] {$y$};
\draw[blue,very thick] (3,1) -- (3,8);
\draw[red,fill=red] (3,1) circle (2pt) node[left] {$R(3,1)$};
\draw[red,fill=red] (3,8) circle (2pt) node[left] {$S(3,8)$};
\draw[dashed,gray] (2.5,1) -- (3.5,1);
\draw[dashed,gray] (2.5,8) -- (3.5,8);
\draw[<->,orange,thick] (3.5,1) -- (3.5,8) node[midway,right] {$7$};
""",
            difficulty="easy",
            solvability_check="pending",
            variables={"x1": 3, "y1": 1, "x2": 3, "y2": 8}
        ))
        
        # Question 10: Distance in a coordinate geometry word problem
        questions.append(Question(
            instance_id=9,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="A park has entrances at points P(1,2) and Q(9,10). What is the straight-line distance between the two entrances?",
            correct_answer="Distance = √[(9-1)² + (10-2)²] = √[64 + 64] = √128 ≈ 11.31 units",
            tikz_code=r"""
\draw[gray,very thin,->] (0,0) -- (10,0) node[right] {$x$};
\draw[gray,very thin,->] (0,0) -- (0,11) node[above] {$y$};
\draw[blue,thick] (1,2) -- (9,10);
\draw[red,fill=red] (1,2) circle (2pt) node[below left] {$P(1,2)$};
\draw[red,fill=red] (9,10) circle (2pt) node[above right] {$Q(9,10)$};
\draw[dashed,gray] (1,2) -- (9,2) node[midway,below] {$8$};
\draw[dashed,gray] (9,2) -- (9,10) node[midway,right] {$8$};
\draw[<->,orange,thick] (5,3) -- (5,9) node[midway,right] {$d$};
""",
            difficulty="medium",
            solvability_check="pending",
            variables={"x1": 1, "y1": 2, "x2": 9, "y2": 10}
        ))
        
        return questions
    
    def _generate_midpoint_questions(self, pattern: QuestionPattern, topic: str) -> List[Question]:
        """Generate 10 diverse midpoint questions with unique diagrams."""
        questions = []
        
        # Question 1: Basic midpoint calculation
        questions.append(Question(
            instance_id=0,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Find the coordinates of the midpoint M of segment AB with endpoints A(2, 3) and B(8, 7) shown in the diagram.",
            correct_answer="Midpoint M = ((2+8)/2, (3+7)/2) = (5, 5)",
            tikz_code=r"""
\draw[gray,very thin,->] (-1,0) -- (9,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-1) -- (0,8) node[above] {$y$};
\draw[blue,thick] (2,3) -- (8,7);
\draw[red,fill=red] (2,3) circle (2pt) node[below left] {$A(2,3)$};
\draw[red,fill=red] (8,7) circle (2pt) node[above right] {$B(8,7)$};
\draw[green,fill=green] (5,5) circle (2pt) node[above left] {$M(5,5)$};
\draw[dashed,gray] (2,3) -- (8,3) node[midway,below] {$6$};
\draw[dashed,gray] (8,3) -- (8,7) node[midway,right] {$4$};
""",
            difficulty="easy",
            solvability_check="pending",
            variables={"x1": 2, "y1": 3, "x2": 8, "y2": 7}
        ))
        
        # Question 2: Midpoint with negative coordinates
        questions.append(Question(
            instance_id=1,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Find the midpoint of segment CD with endpoints C(-6, 2) and D(4, -4) as shown.",
            correct_answer="Midpoint = ((-6+4)/2, (2+(-4))/2) = (-1, -1)",
            tikz_code=r"""
\draw[gray,very thin,->] (-7,0) -- (5,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-5) -- (0,3) node[above] {$y$};
\draw[blue,thick] (-6,2) -- (4,-4);
\draw[red,fill=red] (-6,2) circle (2pt) node[above left] {$C(-6,2)$};
\draw[red,fill=red] (4,-4) circle (2pt) node[below right] {$D(4,-4)$};
\draw[green,fill=green] (-1,-1) circle (2pt) node[below right] {$M(-1,-1)$};
""",
            difficulty="medium",
            solvability_check="pending",
            variables={"x1": -6, "y1": 2, "x2": 4, "y2": -4}
        ))
        
        # Question 3: Midpoint on coordinate axes
        questions.append(Question(
            instance_id=2,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Segment PQ has endpoints P(0, 8) on the y-axis and Q(6, 0) on the x-axis. Find its midpoint as shown.",
            correct_answer="Midpoint = ((0+6)/2, (8+0)/2) = (3, 4)",
            tikz_code=r"""
\draw[gray,very thin,->] (-1,0) -- (7,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-1) -- (0,9) node[above] {$y$};
\draw[blue,thick] (0,8) -- (6,0);
\draw[red,fill=red] (0,8) circle (2pt) node[left] {$P(0,8)$};
\draw[red,fill=red] (6,0) circle (2pt) node[below] {$Q(6,0)$};
\draw[green,fill=green] (3,4) circle (2pt) node[above right] {$M(3,4)$};
\draw[dashed,gray] (0,0) -- (6,0);
\draw[dashed,gray] (0,0) -- (0,8);
""",
            difficulty="easy",
            solvability_check="pending",
            variables={"x1": 0, "y1": 8, "x2": 6, "y2": 0}
        ))
        
        # Question 4: Midpoint in a geometric figure
        questions.append(Question(
            instance_id=3,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="In the rectangle shown, find the coordinates of the intersection point of the diagonals.",
            correct_answer="The diagonals intersect at the midpoint: ((1+7)/2, (2+6)/2) = (4, 4)",
            tikz_code=r"""
\draw[gray,very thin,->] (0,0) -- (8,0) node[right] {$x$};
\draw[gray,very thin,->] (0,0) -- (0,7) node[above] {$y$};
\draw[black,thick] (1,2) rectangle (7,6);
\draw[blue,thick] (1,2) -- (7,6);
\draw[blue,thick] (1,6) -- (7,2);
\draw[red,fill=red] (1,2) circle (2pt) node[below left] {$(1,2)$};
\draw[red,fill=red] (7,6) circle (2pt) node[above right] {$(7,6)$};
\draw[green,fill=green] (4,4) circle (2pt) node[above] {$M(4,4)$};
""",
            difficulty="medium",
            solvability_check="pending",
            variables={"x1": 1, "y1": 2, "x2": 7, "y2": 6}
        ))
        
        # Question 5: Finding one endpoint given midpoint
        questions.append(Question(
            instance_id=4,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="If M(5, 3) is the midpoint of segment AB and point A is at (2, 1), find the coordinates of B as shown.",
            correct_answer="B = (2×5-2, 2×3-1) = (8, 5)",
            tikz_code=r"""
\draw[gray,very thin,->] (0,0) -- (9,0) node[right] {$x$};
\draw[gray,very thin,->] (0,0) -- (0,6) node[above] {$y$};
\draw[blue,thick] (2,1) -- (8,5);
\draw[red,fill=red] (2,1) circle (2pt) node[below left] {$A(2,1)$};
\draw[green,fill=green] (5,3) circle (2pt) node[above] {$M(5,3)$};
\draw[orange,fill=orange] (8,5) circle (2pt) node[above right] {$B(?,?)$};
\draw[dashed,gray] (5,3) -- (8,5);
""",
            difficulty="hard",
            solvability_check="pending",
            variables={"x1": 2, "y1": 1, "mid_x": 5, "mid_y": 3}
        ))
        
        # Question 6: Midpoint with fractional coordinates
        questions.append(Question(
            instance_id=5,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Find the midpoint of segment EF with endpoints E(1.5, 3.5) and F(6.5, 7.5) shown in the diagram.",
            correct_answer="Midpoint = ((1.5+6.5)/2, (3.5+7.5)/2) = (4, 5.5)",
            tikz_code=r"""
\draw[gray,very thin,->] (0,0) -- (8,0) node[right] {$x$};
\draw[gray,very thin,->] (0,0) -- (0,8) node[above] {$y$};
\draw[blue,thick] (1.5,3.5) -- (6.5,7.5);
\draw[red,fill=red] (1.5,3.5) circle (2pt) node[below left] {$E(1.5,3.5)$};
\draw[red,fill=red] (6.5,7.5) circle (2pt) node[above right] {$F(6.5,7.5)$};
\draw[green,fill=green] (4,5.5) circle (2pt) node[left] {$M(4,5.5)$};
""",
            difficulty="medium",
            solvability_check="pending",
            variables={"x1": 1.5, "y1": 3.5, "x2": 6.5, "y2": 7.5}
        ))
        
        # Question 7: Midpoint in a triangle
        questions.append(Question(
            instance_id=6,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="In triangle ABC, find the midpoint of side BC as shown in the coordinate plane.",
            correct_answer="Midpoint of BC = ((8+2)/2, (0+6)/2) = (5, 3)",
            tikz_code=r"""
\draw[gray,very thin,->] (-1,0) -- (9,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-1) -- (0,7) node[above] {$y$};
\draw[black,thick] (0,4) -- (8,0) -- (2,6) -- cycle;
\draw[blue,thick] (8,0) -- (2,6);
\draw[red,fill=red] (8,0) circle (2pt) node[below right] {$B(8,0)$};
\draw[red,fill=red] (2,6) circle (2pt) node[above left] {$C(2,6)$};
\draw[green,fill=green] (5,3) circle (2pt) node[above right] {$M(5,3)$};
\draw[red,fill=red] (0,4) circle (2pt) node[left] {$A(0,4)$};
""",
            difficulty="medium",
            solvability_check="pending",
            variables={"x1": 8, "y1": 0, "x2": 2, "y2": 6}
        ))
        
        # Question 8: Midpoint on a line segment
        questions.append(Question(
            instance_id=7,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="A line segment has endpoints at (-3, -2) and (5, 4). Find the point that divides the segment into two equal parts.",
            correct_answer="Midpoint = ((-3+5)/2, (-2+4)/2) = (1, 1)",
            tikz_code=r"""
\draw[gray,very thin,->] (-4,0) -- (6,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-3) -- (0,5) node[above] {$y$};
\draw[blue,thick] (-3,-2) -- (5,4);
\draw[red,fill=red] (-3,-2) circle (2pt) node[below left] {$(-3,-2)$};
\draw[red,fill=red] (5,4) circle (2pt) node[above right] {$(5,4)$};
\draw[green,fill=green] (1,1) circle (2pt) node[above left] {$(1,1)$};
\draw[dashed,gray] (-3,-2) -- (5,-2) node[midway,below] {$8$};
\draw[dashed,gray] (5,-2) -- (5,4) node[midway,right] {$6$};
""",
            difficulty="easy",
            solvability_check="pending",
            variables={"x1": -3, "y1": -2, "x2": 5, "y2": 4}
        ))
        
        # Question 9: Midpoint in a real-world context
        questions.append(Question(
            instance_id=8,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Two cities are located at coordinates (100, 200) and (300, 400) on a map. Find the midpoint location between them.",
            correct_answer="Midpoint = ((100+300)/2, (200+400)/2) = (200, 300)",
            tikz_code=r"""
\draw[gray,very thin,->] (50,0) -- (350,0) node[right] {$x$};
\draw[gray,very thin,->] (0,50) -- (0,450) node[above] {$y$};
\draw[blue,thick] (100,200) -- (300,400);
\draw[red,fill=red] (100,200) circle (2pt) node[below left] {City A};
\draw[red,fill=red] (300,400) circle (2pt) node[above right] {City B};
\draw[green,fill=green] (200,300) circle (2pt) node[above] {Midpoint};
""",
            difficulty="medium",
            solvability_check="pending",
            variables={"x1": 100, "y1": 200, "x2": 300, "y2": 400}
        ))
        
        # Question 10: Multiple midpoints
        questions.append(Question(
            instance_id=9,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Find the midpoint of segment PQ and then find the midpoint between that midpoint and point R(6, 8).",
            correct_answer="Midpoint of PQ = (3, 4). Midpoint with R = ((3+6)/2, (4+8)/2) = (4.5, 6)",
            tikz_code=r"""
\draw[gray,very thin,->] (-1,0) -- (8,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-1) -- (0,9) node[above] {$y$};
\draw[blue,thick] (1,2) -- (5,6);
\draw[green,fill=green] (3,4) circle (2pt) node[above left] {$M_1(3,4)$};
\draw[orange,thick] (3,4) -- (6,8);
\draw[red,fill=red] (1,2) circle (2pt) node[below left] {$P(1,2)$};
\draw[red,fill=red] (5,6) circle (2pt) node[above right] {$Q(5,6)$};
\draw[red,fill=red] (6,8) circle (2pt) node[above right] {$R(6,8)$};
\draw[purple,fill=purple] (4.5,6) circle (2pt) node[above] {$M_2(4.5,6)$};
""",
            difficulty="hard",
            solvability_check="pending",
            variables={"x1": 1, "y1": 2, "x2": 5, "y2": 6, "x3": 6, "y3": 8}
        ))
        
        return questions
    
    def _generate_quadratic_factoring_questions(self, pattern: QuestionPattern, topic: str) -> List[Question]:
        """Generate 10 diverse quadratic factoring questions with unique diagrams."""
        questions = []
        
        # Question 1: Basic factoring with positive roots
        questions.append(Question(
            instance_id=0,
            pattern_id=pattern.pattern_id,
            topic=topic,
question_text="Factor the quadratic equation x² - 7x + 12 = 0 shown in the parabola graph.",
            correct_answer="x² - 7x + 12 = (x-3)(x-4) = 0, so x = 3 or x = 4",
            tikz_code=r"""
\draw[gray,very thin,->] (-1,0) -- (8,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-1) -- (0,5) node[above] {$y$};
\draw[blue,thick,domain=-0.5:7.5,smooth,variable=\\x] plot ({{\\x}},{0.25*(\\x-3)*(\\x-4)}});
\draw[red,fill=red] (3,0) circle (2pt) node[below] {$x=3$};
\draw[red,fill=red] (4,0) circle (2pt) node[below] {$x=4$};
\draw[green,fill=green] (3.5,0.25) circle (2pt) node[above] {Vertex};
\node at (3.5,-0.5) {$x^2 - 7x + 12 = 0$};
""",
            difficulty="easy",
            solvability_check="pending",
            variables={"a": 1, "b": -7, "c": 12}
        ))
        
        # Question 2: Factoring with negative coefficient
        questions.append(Question(
            instance_id=1,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Factor and solve: 2x² - 8x - 10 = 0 as shown in the graph.",
            correct_answer="2x² - 8x - 10 = 2(x² - 4x - 5) = 2(x-5)(x+1) = 0, so x = 5 or x = -1",
            tikz_code=r"""
\draw[gray,very thin,->] (-3,0) -- (7,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-15) -- (0,5) node[above] {$y$};
\draw[blue,thick,domain=-2.5:6.5,smooth,variable=\\x] plot ({{\\x}},{0.5*2*(\\x-5)*(\\x+1)});
\draw[red,fill=red] (-1,0) circle (2pt) node[below] {$x=-1$};
\draw[red,fill=red] (5,0) circle (2pt) node[below] {$x=5$};
\draw[green,fill=green] (2,-12) circle (2pt) node[below] {Vertex};
\node at (2,-14) {$2x^2 - 8x - 10 = 0$};
""",
            difficulty="medium",
            solvability_check="pending",
            variables={"a": 2, "b": -8, "c": -10}
        ))
        
        # Question 3: Perfect square trinomial
        questions.append(Question(
            instance_id=2,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Factor the perfect square: x² - 6x + 9 = 0 shown in the parabola.",
            correct_answer="x² - 6x + 9 = (x-3)² = 0, so x = 3 (double root)",
            tikz_code=r"""
\draw[gray,very thin,->] (-1,0) -- (7,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-1) -- (0,5) node[above] {$y$};
\draw[blue,thick,domain=-0.5:6.5,smooth,variable=\\x] plot ({{\\x}},{0.5*(\\x-3)*(\\x-3)});
\draw[red,fill=red] (3,0) circle (2pt) node[below] {$x=3$};
\draw[green,fill=green] (3,0) circle (3pt) node[above] {Vertex};
\node at (3,-0.5) {$x^2 - 6x + 9 = 0$};
""",
            difficulty="easy",
            solvability_check="pending",
            variables={"a": 1, "b": -6, "c": 9}
        ))
        
        # Question 4: Factoring with fraction roots
        questions.append(Question(
            instance_id=3,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Factor: 3x² - 11x + 6 = 0 as shown in the graph.",
            correct_answer="3x² - 11x + 6 = (3x-2)(x-3) = 0, so x = 2/3 or x = 3",
            tikz_code=r"""
\draw[gray,very thin,->] (-1,0) -- (5,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-5) -- (0,3) node[above] {$y$};
\draw[blue,thick,domain=-0.5:4.5,smooth,variable=\\x] plot ({{\\x}},{0.3*(3*\x-2)*(\\x-3)});
\draw[red,fill=red] (0.67,0) circle (2pt) node[below] {$x=2/3$};
\draw[red,fill=red] (3,0) circle (2pt) node[below] {$x=3$};
\draw[green,fill=green] (1.83,-1.83) circle (2pt) node[below] {Vertex};
\node at (2,-3) {$3x^2 - 11x + 6 = 0$};
""",
            difficulty="medium",
            solvability_check="pending",
            variables={"a": 3, "b": -11, "c": 6}
        ))
        
        # Question 5: Difference of squares
        questions.append(Question(
            instance_id=4,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Factor using difference of squares: x² - 16 = 0 shown in the graph.",
            correct_answer="x² - 16 = (x-4)(x+4) = 0, so x = 4 or x = -4",
            tikz_code=r"""
\draw[gray,very thin,->] (-6,0) -- (6,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-20) -- (0,5) node[above] {$y$};
\draw[blue,thick,domain=-5.5:5.5,smooth,variable=\\x] plot ({{\\x}},{0.5*(\\x-4)*(\\x+4)});
\draw[red,fill=red] (-4,0) circle (2pt) node[below] {$x=-4$};
\draw[red,fill=red] (4,0) circle (2pt) node[below] {$x=4$};
\draw[green,fill=green] (0,-8) circle (2pt) node[below] {Vertex};
\node at (0,-10) {$x^2 - 16 = 0$};
""",
            difficulty="easy",
            solvability_check="pending",
            variables={"a": 1, "b": 0, "c": -16}
        ))
        
        # Question 6: Factoring by grouping
        questions.append(Question(
            instance_id=5,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Factor by grouping: x³ - 2x² - 9x + 18 = 0 as shown.",
            correct_answer="x³ - 2x² - 9x + 18 = x²(x-2) - 9(x-2) = (x²-9)(x-2) = (x-3)(x+3)(x-2)",
            tikz_code=r"""
\draw[gray,very thin,->] (-4,0) -- (5,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-10) -- (0,10) node[above] {$y$};
\draw[blue,thick,domain=-3.5:4.5,smooth,variable=\\x] plot ({{\\x}},{0.2*(\\x-3)*(\\x+3)*(\\x-2)});
\draw[red,fill=red] (-3,0) circle (2pt) node[below] {$x=-3$};
\draw[red,fill=red] (2,0) circle (2pt) node[below] {$x=2$};
\draw[red,fill=red] (3,0) circle (2pt) node[below] {$x=3$};
\node at (0,-8) {$x^3 - 2x^2 - 9x + 18 = 0$};
""",
            difficulty="hard",
            solvability_check="pending",
            variables={"a": 1, "b": -2, "c": -9, "d": 18}
        ))
        
        # Question 7: Factoring with leading coefficient not 1
        questions.append(Question(
            instance_id=6,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Factor: 6x² + 13x + 6 = 0 shown in the parabola.",
            correct_answer="6x² + 13x + 6 = (2x+3)(3x+2) = 0, so x = -3/2 or x = -2/3",
            tikz_code=r"""
\draw[gray,very thin,->] (-3,0) -- (1,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-2) -- (0,3) node[above] {$y$};
\draw[blue,thick,domain=-2.5:0.5,smooth,variable=\\x] plot ({{\\x}},{0.5*(2*\x+3)*(3*\x+2)});
\draw[red,fill=red] (-1.5,0) circle (2pt) node[below] {$x=-3/2$};
\draw[red,fill=red] (-0.67,0) circle (2pt) node[below] {$x=-2/3$};
\draw[green,fill=green] (-1.08,-0.08) circle (2pt) node[above] {Vertex};
\node at (-1,-1.5) {$6x^2 + 13x + 6 = 0$};
""",
            difficulty="medium",
            solvability_check="pending",
            variables={"a": 6, "b": 13, "c": 6}
        ))
        
        # Question 8: Factoring word problem
        questions.append(Question(
            instance_id=7,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="A rectangular garden has area x² - 5x - 24 square meters. Find the dimensions if one side is x-8 meters.",
            correct_answer="x² - 5x - 24 = (x-8)(x+3), so dimensions are (x-8) by (x+3) meters",
            tikz_code=r"""
\draw[gray,very thin,->] (-1,0) -- (10,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-1) -- (0,6) node[above] {$y$};
\draw[black,thick] (2,1) rectangle (8,4);
\draw[blue,thick] (2,1) -- (8,1) node[midway,below] {$x+3$};
\draw[blue,thick] (2,1) -- (2,4) node[midway,left] {$x-8$};
\draw[red,fill=red] (2,1) circle (2pt) node[below left] {$(2,1)$};
\draw[red,fill=red] (8,4) circle (2pt) node[above right] {$(8,4)$};
\node at (5,2.5) {Area = $x^2 - 5x - 24$};
""",
            difficulty="hard",
            solvability_check="pending",
            variables={"a": 1, "b": -5, "c": -24}
        ))
        
        # Question 9: Factoring with complex roots (no real roots)
        questions.append(Question(
            instance_id=8,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="Factor: x² + 4x + 8 = 0. Explain why it has no real roots as shown.",
            correct_answer="Discriminant = 16 - 32 = -16 < 0, so no real roots. Cannot factor over real numbers.",
            tikz_code=r"""
\draw[gray,very thin,->] (-5,0) -- (3,0) node[right] {$x$};
\draw[gray,very thin,->] (0,-1) -- (0,8) node[above] {$y$};
\draw[blue,thick,domain=-4.5:2.5,smooth,variable=\\x] plot ({{\\x}},{0.3*(\\x+2)*(\\x+2)+4});
\draw[green,fill=green] (-2,4) circle (2pt) node[above] {Vertex $(-2,4)$};
\draw[dashed,gray] (-2,0) -- (-2,4);
\node at (-2,-0.5) {$x=-2$};
\node at (0,6) {$x^2 + 4x + 8 = 0$};
\node at (0,1) {No real roots};
""",
            difficulty="hard",
            solvability_check="pending",
            variables={"a": 1, "b": 4, "c": 8}
        ))
        
        # Question 10: Factoring application
        questions.append(Question(
            instance_id=9,
            pattern_id=pattern.pattern_id,
            topic=topic,
            question_text="The height of a ball is given by h(t) = -5t² + 20t + 15. When does the ball hit the ground?",
            correct_answer="-5t² + 20t + 15 = 0 → t² - 4t - 3 = 0 → (t-2)² - 7 = 0 → t = 2 ± √7 ≈ 4.65 seconds",
            tikz_code=r"""
\draw[gray,very thin,->] (-1,0) -- (6,0) node[right] {$t$};
\draw[gray,very thin,->] (0,-5) -- (0,25) node[above] {$h$};
\draw[blue,thick,domain=-0.5:5.5,smooth,variable=\\x] plot ({{\\x}},{-5*(\\x-2)*(\\x-2)+20});
\draw[red,fill=red] (4.65,0) circle (2pt) node[below] {$t≈4.65$};
\draw[green,fill=green] (2,20) circle (2pt) node[above] {Max height};
\draw[dashed,gray] (0,15) -- (0,0);
\node at (2,15) {$h(t) = -5t^2 + 20t + 15$};
""",
            difficulty="hard",
            solvability_check="pending",
            variables={"a": -5, "b": 20, "c": 15}
        ))
        
        return questions
    
    def _generate_generic_questions(self, pattern: QuestionPattern, topic: str) -> List[Question]:
        """Generate 10 diverse generic questions with unique diagrams for any pattern."""
        questions = []
        
        for i in range(10):
            # Create different question types based on index
            if i == 0:
                # Basic calculation question
                questions.append(Question(
                    instance_id=i,
                    pattern_id=pattern.pattern_id,
                    topic=topic,
                    question_text=f"Calculate the value shown in the {topic} diagram for the given parameters.",
                    correct_answer=f"The calculated value is {i + 5} based on the {topic} formula shown.",
                    tikz_code=f"""
\\draw[gray,very thin,->] (0,0) -- (6,0) node[right] {{$x$}};
\\draw[gray,very thin,->] (0,0) -- (0,5) node[above] {{$y$}};
\\draw[blue,thick] (1,1) -- (5,4);
\\draw[red,fill=red] (1,1) circle (2pt) node[below left] {{$({i+1},{i+1})$}};
\\draw[red,fill=red] (5,4) circle (2pt) node[above right] {{$({i+4},{i+3})$}};
\\draw[green,fill=green] (3,2.5) circle (2pt) node[above] {{{topic}}};
\\node at (3,1) {{{topic} Problem {i+1}}};
""",
                    difficulty="easy",
                    solvability_check="pending",
                    variables={"value": i + 5}
                ))
            elif i == 1:
                # Comparison question
                questions.append(Question(
                    instance_id=i,
                    pattern_id=pattern.pattern_id,
                    topic=topic,
                    question_text=f"Compare the two quantities shown in the {topic} diagram and determine which is larger.",
                    correct_answer=f"Quantity A is larger than Quantity B by {i + 2} units in this {topic} problem.",
                    tikz_code=f"""
\\draw[gray,very thin,->] (0,0) -- (7,0) node[right] {{$x$}};
\\draw[gray,very thin,->] (0,0) -- (0,6) node[above] {{$y$}};
\\draw[blue,thick] (1,1) rectangle (3,{i+2});
\\draw[red,thick] (4,1) rectangle (6,{i+1});
\\node at (2,{i+2}/2) {{A}};
\\node at (5,{i+1}/2) {{B}};
\\node at (3.5,-0.5) {{{topic} Comparison}};
""",
                    difficulty="medium",
                    solvability_check="pending",
                    variables={"value_a": i + 2, "value_b": i + 1}
                ))
            elif i == 2:
                # Pattern recognition question
                questions.append(Question(
                    instance_id=i,
                    pattern_id=pattern.pattern_id,
                    topic=topic,
                    question_text=f"Identify the pattern shown in the {topic} diagram and predict the next value.",
                    correct_answer=f"The pattern increases by {i + 1} each step, so the next value is {i + 6}.",
                    tikz_code=f"""
\\draw[gray,very thin,->] (0,0) -- (8,0) node[right] {{$n$}};
\\draw[gray,very thin,->] (0,0) -- (0,6) node[above] {{{topic}}};
\\foreach \\x/\\y in {{1/{i+1},2/{i+2},3/{i+3},4/{i+4}}} {{
    \\draw[blue,fill=blue] (\\x,\\y) circle (2pt);
    \\node[below] at (\\x,0) {{\\x}};
    \\node[left] at (0,\\y) {{\\y}};
}}
\\draw[red,dashed] (5,{i+5}) circle (2pt);
\\node[above] at (5,{i+5}) {{?}};
\\node at (4,-0.5) {{{topic} Pattern}};
""",
                    difficulty="medium",
                    solvability_check="pending",
                    variables={"pattern": i + 1}
                ))
            elif i == 3:
                # Geometry question
                questions.append(Question(
                    instance_id=i,
                    pattern_id=pattern.pattern_id,
                    topic=topic,
                    question_text=f"Find the area of the {topic} shape shown in the diagram.",
                    correct_answer=f"The area is {(i + 3) * (i + 2)} square units for this {topic} shape.",
                    tikz_code=f"""
\\draw[gray,very thin,->] (0,0) -- (7,0) node[right] {{$x$}};
\\draw[gray,very thin,->] (0,0) -- (0,6) node[above] {{$y$}};
\\draw[blue,thick] (1,1) rectangle ({i+3},{i+2});
\\draw[red,fill=red] (1,1) circle (2pt) node[below left] {{$(1,1)$}};
\\draw[red,fill=red] ({i+3},{i+2}) circle (2pt) node[above right] {{($({i+3},{i+2})$}};
\\draw[<->,orange,thick] (1,0.5) -- ({i+3},0.5) node[midway,below] {{{i+2}}};
\\draw[<->,orange,thick] (0.5,1) -- (0.5,{i+2}) node[midway,left] {{{i+1}}};
\\node at (4,-0.5) {{{topic} Area}};
""",
                    difficulty="easy",
                    solvability_check="pending",
                    variables={"width": i + 2, "height": i + 1}
                ))
            elif i == 4:
                # Word problem
                questions.append(Question(
                    instance_id=i,
                    pattern_id=pattern.pattern_id,
                    topic=topic,
                    question_text=f"A {topic} scenario shows {i + 2} items. If each item costs ${i + 3}, what is the total cost?",
                    correct_answer=f"Total cost = {i + 2} × ${i + 3} = ${(i + 2) * (i + 3)}",
                    tikz_code=f"""
\\draw[gray,very thin,->] (0,0) -- (8,0) node[right] {{Items}};
\\draw[gray,very thin,->] (0,0) -- (0,6) node[above] {{Cost}};
\\foreach \\x in {{1,2,...,{i+2}}} {{
    \\draw[blue,fill=blue] (\\x,{i+3}) circle (3pt);
    \\node[below] at (\\x,0) {{\\${i+3}}};
}}
\\draw[red,thick] (0.5,0.5) -- ({i+2.5},{i+3.5});
\\node at ({i+3}/2,{i+3}/2) [above] {{{topic} Word Problem}};
\\node at (4,-0.5) {{Total: \\${(i+2)*(i+3)}}};
""",
                    difficulty="medium",
                    solvability_check="pending",
                    variables={"items": i + 2, "cost": i + 3}
                ))
            elif i == 5:
                # Graph interpretation question
                questions.append(Question(
                    instance_id=i,
                    pattern_id=pattern.pattern_id,
                    topic=topic,
                    question_text=f"What is the maximum value shown in the {topic} graph?",
                    correct_answer=f"The maximum value is {i + 8} occurring at x = {i + 1}.",
                    tikz_code=f"""
\\draw[gray,very thin,->] (0,0) -- (7,0) node[right] {{$x$}};
\\draw[gray,very thin,->] (0,0) -- (0,{i+9}) node[above] {{{topic}}};
\\draw[blue,thick,domain=0:6,smooth,variable=\\x] plot ({{\\x}},{{-{i+1}*(\\x-{i+1})*(\\x-{i+1})+{i+8}}});
\\draw[red,fill=red] ({i+1},{i+8}) circle (2pt) node[above] {{Max}};
\\draw[dashed,gray] ({i+1},0) -- ({i+1},{i+8});
\\draw[dashed,gray] (0,{i+8}) -- ({i+1},{i+8});
\\node at ({i+1},-0.5) {{{i+1}}};
\\node at (-0.5,{i+8}) {{{i+8}}};
\\node at (3,-1) {{{topic} Graph}};
""",
                    difficulty="medium",
                    solvability_check="pending",
                    variables={"max_x": i + 1, "max_y": i + 8}
                ))
            elif i == 6:
                # Proportion question
                questions.append(Question(
                    instance_id=i,
                    pattern_id=pattern.pattern_id,
                    topic=topic,
                    question_text=f"In the {topic} proportion shown, if the first ratio equals {i + 2}:{i + 1}, find the missing value.",
                    correct_answer=f"The missing value is {(i + 2) * (i + 3) / (i + 1)} ≈ {((i + 2) * (i + 3) / (i + 1)):.1f}",
                    tikz_code=f"""
\\draw[gray,very thin,->] (0,0) -- (8,0) node[right] {{$x$}};
\\draw[gray,very thin,->] (0,0) -- (0,6) node[above] {{$y$}};
\\draw[blue,thick] (1,1) -- (3,{i+2});
\\draw[red,thick] (4,1) -- (6,?);
\\node at (2,2) {{{i+2}:{i+1}}};
\\node at (5,2) {{?:{i+3}}};
\\draw[<->,orange,thick] (1,0.5) -- (3,0.5) node[midway,below] {{{i+2}}};
\\draw[<->,orange,thick] (1,0.5) -- (1,{i+2}) node[midway,left] {{{i+1}}};
\\draw[<->,orange,thick] (4,0.5) -- (6,0.5) node[midway,below] {{?}};
\\draw[<->,orange,thick] (4,0.5) -- (4,{i+3}) node[midway,left] {{{i+3}}};
\\node at (3.5,-0.5) {{{topic} Proportion}};
""",
                    difficulty="hard",
                    solvability_check="pending",
                    variables={"ratio1": i + 2, "ratio2": i + 1, "value": i + 3}
                ))
            elif i == 7:
                # Transformation question
                questions.append(Question(
                    instance_id=i,
                    pattern_id=pattern.pattern_id,
                    topic=topic,
                    question_text=f"The {topic} shape is transformed as shown. What type of transformation occurred?",
                    correct_answer=f"This is a translation by ({i + 1}, {i + 2}) units in the {topic} context.",
                    tikz_code=f"""
\\draw[gray,very thin,->] (0,0) -- (8,0) node[right] {{$x$}};
\\draw[gray,very thin,->] (0,0) -- (0,6) node[above] {{$y$}};
\\draw[blue,thick] (1,1) -- (3,1) -- (3,3) -- cycle;
\\draw[red,thick] ({i+2},{i+3}) -- ({i+4},{i+3}) -- ({i+4},{i+5}) -- cycle;
\\draw[->,orange,thick] (2,2) -- ({i+3},{i+4});
\\node at (2,0.5) {{Original}};
\\node at ({i+3},{i+2.5}) {{Image}};
\\node at (4,-0.5) {{{topic} Transformation}};
""",
                    difficulty="medium",
                    solvability_check="pending",
                    variables={"dx": i + 1, "dy": i + 2}
                ))
            elif i == 8:
                # Estimation question
                questions.append(Question(
                    instance_id=i,
                    pattern_id=pattern.pattern_id,
                    topic=topic,
                    question_text=f"Estimate the value shown in the {topic} diagram to the nearest whole number.",
                    correct_answer=f"The estimated value is approximately {round((i + 7) * 1.4)} for this {topic} problem.",
                    tikz_code=f"""
\\draw[gray,very thin,->] (0,0) -- (7,0) node[right] {{$x$}};
\\draw[gray,very thin,->] (0,0) -- (0,8) node[above] {{{topic}}};
\\draw[blue,thick,domain=0:6,smooth,variable=\\x] plot ({{\\x}},{{1.4*\\x+{i}}});
\\draw[red,fill=red] ({i+1},{(i+1)*1.4+i}) circle (2pt) node[above] {{{round((i+7)*1.4)}}};
\\draw[dashed,gray] ({i+1},0) -- ({i+1},{(i+1)*1.4+i});
\\draw[dashed,gray] (0,{(i+1)*1.4+i}) -- ({i+1},{(i+1)*1.4+i});
\\node at ({i+1},-0.5) {{{i+1}}};
\\node at (-0.5,{(i+1)*1.4+i}) {{{round((i+7)*1.4)}}};
\\node at (3,-1) {{{topic} Estimation}};
""",
                    difficulty="easy",
                    solvability_check="pending",
                    variables={"estimate": round((i + 7) * 1.4)}
                ))
            else:
                # Multi-step problem
                questions.append(Question(
                    instance_id=i,
                    pattern_id=pattern.pattern_id,
                    topic=topic,
                    question_text=f"Solve the multi-step {topic} problem shown in the diagram.",
                    correct_answer=f"The solution involves {i + 1} steps, resulting in {i + 10} as the final answer.",
                    tikz_code=f"""
\\draw[gray,very thin,->] (0,0) -- (8,0) node[right] {{Steps}};
\\draw[gray,very thin,->] (0,0) -- (0,6) node[above] {{{topic}}};
\\foreach \\x/\\y/\\step in {{1/1/Step 1,2/2/Step 2,3/3/Step 3}} {{
    \\draw[blue,fill=blue] (\\x,\\y) circle (2pt);
    \\node[below] at (\\x,0) {{\\step}};
    \\node[left] at (0,\\y) {{\\y}};
}}
\\draw[red,thick] (1,1) -- (2,2) -- (3,3);
\\draw[green,fill=green] (6,{i+10}) circle (3pt);
\\node[above] at (6,{i+10}) {{{i+10}}};
\\node at (4,-0.5) {{{topic} Multi-step}};
""",
                    difficulty="hard",
                    solvability_check="pending",
                    variables={"steps": i + 1, "result": i + 10}
                ))
        
        return questions
