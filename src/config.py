"""
Configuration and constants for the pipeline.
Loads from .env file and environment variables, with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from .schemas import PipelineConfig, LLMConfig, TikZConfig

# Load environment variables from .env file
load_dotenv()


# =====================================================================
# Paths
# =====================================================================

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
OUTPUT_DIR = PROJECT_ROOT / "output"
TEMP_DIR = OUTPUT_DIR / "temp"
DIAGRAMS_DIR = OUTPUT_DIR / "diagrams"


# =====================================================================
# Configuration Factory
# =====================================================================

def get_pipeline_config() -> PipelineConfig:
    """
    Load pipeline configuration from environment and defaults.
    
    Environment Variables:
        - FERMI_OUTPUT_DIR: Output directory (default: ./output)
        - FERMI_TEMP_DIR: Temporary directory (default: ./output/temp)
        - GROQ_API_KEY: Groq API key (required for LLM calls)
        - FERMI_MODEL: LLM model (default: llama-3.3-70b-versatile)
        - FERMI_TEMP: LLM temperature (default: 0.7)
        - TECTONIC_PATH: Path to tectonic binary
    """
    
    output_dir = os.getenv("FERMI_OUTPUT_DIR", str(OUTPUT_DIR))
    temp_dir = os.getenv("FERMI_TEMP_DIR", str(TEMP_DIR))
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable not set")
    
    llm_config = LLMConfig(
        provider="groq",
        model=os.getenv("FERMI_MODEL", "llama-3.1-8b-instant"),
        temperature=float(os.getenv("FERMI_TEMP", "0.7")),
        max_tokens=int(os.getenv("FERMI_MAX_TOKENS", "8000")),
        api_key=api_key
    )
    
    tikz_config = TikZConfig(
        dpi=int(os.getenv("FERMI_DPI", "300")),
        tectonic_path=os.getenv("TECTONIC_PATH"),
        temp_dir=temp_dir,
        keep_intermediate=os.getenv("FERMI_KEEP_INTERMEDIATE", "false").lower() == "true"
    )
    
    return PipelineConfig(
        llm=llm_config,
        tikz=tikz_config,
        output_dir=output_dir,
        validate_solvability=os.getenv("FERMI_VALIDATE", "true").lower() == "true",
        parallel_rendering=os.getenv("FERMI_PARALLEL", "true").lower() == "true",
        max_retries=int(os.getenv("FERMI_MAX_RETRIES", "3"))
    )


# =====================================================================
# Constants
# =====================================================================

PATTERNS_PER_TOPIC = 10
QUESTIONS_PER_PATTERN = 10
TOTAL_QUESTIONS = PATTERNS_PER_TOPIC * QUESTIONS_PER_PATTERN

GRADE_LEVELS = ["9", "10", "11", "12", "9-10", "10-11", "11-12", "9-12"]
DIFFICULTY_LEVELS = ["easy", "medium", "hard"]

# =====================================================================
# LLM Prompts
# =====================================================================

PATTERN_GENERATION_SYSTEM_PROMPT = """
You are an expert educational content designer specializing in creating 
mathematics and physics questions for high school students (Grades 9-12).

Your task is to generate 10 HIGHLY DISTINCT question patterns for a given topic.
Each pattern must be DEEPLY ROOTED in the specific topic provided and test different aspects of that topic.

CRITICAL TOPIC RELEVANCE REQUIREMENTS:
- EVERY pattern must be directly related to the specific topic (e.g., if topic is "Quadratic Equations", ALL patterns should be about quadratic equations)
- Do NOT create generic patterns that could apply to multiple topics
- Ensure patterns cover the full scope of the topic (concepts, applications, problem types)
- Each pattern should explore a different facet or application of the topic

TOPIC-SPECIFIC PATTERN EXAMPLES:
- For "Quadratic Equations": solving by factoring, quadratic formula, graphing parabolas, word problems, discriminant analysis, vertex form, completing square, real-world applications, comparison of roots, quadratic inequalities
- For "Coordinate Geometry": distance formula, midpoint formula, slope analysis, line equations, circle equations, area calculations, transformations, intersection points, geometric proofs, coordinate proofs
- For "Trigonometry": right triangle trig, unit circle, trig identities, trig graphs, law of sines/cosines, trig equations, real-world applications, inverse trig, trig proofs, area/perimeter problems

CRITICAL DIVERSITY REQUIREMENTS:
- Each pattern must represent a fundamentally DIFFERENT problem-solving approach within the topic
- Vary the mathematical operations required (calculation, proof, comparison, analysis, etc.)
- Vary the visual representation style (graphs, diagrams, charts, geometric figures)
- Vary the cognitive skill tested (recall, application, analysis, synthesis)
- Ensure NO two patterns are just minor variations of each other

Each pattern must:
1. Represent a UNIQUE conceptual problem type within the topic (no overlap between patterns)
2. REQUIRE a diagram to be fully understood and solvable
3. Be appropriate for specified grade level
4. Be solvable and unambiguous
5. Test DIFFERENT skills/concepts within the topic

CRITICAL: Return your response as a valid JSON array with exactly 10 pattern objects.
- Do NOT include markdown formatting (no ```json or ```)
- Do NOT include any explanatory text
- Do NOT include trailing commas
- Ensure all brackets and braces are properly matched
- Double-check that the JSON is valid before responding
- CRITICAL: Do NOT use mathematical expressions like "2 * Math.PI" in JSON values
- Use simple numeric values instead (e.g., "6.28" instead of "2 * Math.PI")

Each pattern object must include:
- pattern_id (0-9)
- pattern_name (descriptive and unique, clearly indicating the topic)
- diagram_description (semantic, NOT code, describes visual elements needed for this specific topic)
- question_template (with {variable} placeholders, clearly related to the topic)
- variables (list of variable definitions with ranges)
- difficulty (easy/medium/hard)
- learning_objective (specific skill being tested within the topic)

CRITICAL: Each variable in the variables list MUST include ALL of these fields:
- name (string)
- type (string: "int", "float", "enum", or "string")
- min_value (number, required for int/float types)
- max_value (number, required for int/float types)
- unit (string, optional)
- description (string, REQUIRED - describes what the variable represents in the context of the topic)
- allowed_values (list, required only for enum type)

Example of CORRECT JSON format for "Quadratic Equations":
[
  {
    "pattern_id": 0,
    "pattern_name": "Solving Quadratic Equations by Factoring",
    "diagram_description": "A parabola graph showing x-intercepts and vertex",
    "question_template": "Find the roots of the quadratic equation {a}x² + {b}x + {c} = 0 by factoring.",
    "variables": [
      {
        "name": "a",
        "type": "int",
        "min_value": 1,
        "max_value": 5,
        "unit": "",
        "description": "Coefficient of x² term"
      }
    ],
    "difficulty": "medium",
    "learning_objective": "Test ability to solve quadratic equations using factoring method"
  }
]
"""

QUESTION_GENERATION_SYSTEM_PROMPT = """
You are an expert in creating fully-specified mathematics and physics 
questions with accompanying TikZ diagrams.

Your task is to generate 10 HIGHLY DIVERSE question instances for a given pattern.
Each instance must be a COMPLETELY DIFFERENT TYPE of question within the same pattern concept.
ALL questions must be DEEPLY ROOTED in the specific topic and pattern provided.

CRITICAL TOPIC RELEVANCE REQUIREMENTS:
- EVERY question must directly relate to the specific topic (e.g., if topic is "Quadratic Equations", ALL questions must be about quadratic equations)
- Do NOT create generic questions that could apply to multiple topics
- Ensure questions explore different aspects of the specific pattern within the topic
- Each question should test a different skill or application within the pattern

TOPIC-SPECIFIC QUESTION EXAMPLES:
For "Quadratic Equations - Solving by Factoring" pattern:
- Q1: Find the roots when the quadratic is easily factorable
- Q2: Find the roots when factoring requires common factor extraction
- Q3: Find the roots when factoring involves difference of squares
- Q4: Find the roots when factoring involves perfect square trinomials
- Q5: Find the roots when factoring requires grouping
- Q6: Find the sum and product of roots from factored form
- Q7: Find the roots when coefficients are fractions
- Q8: Find the roots when the equation represents a real-world scenario
- Q9: Find the roots and verify by substitution
- Q10: Find the roots and determine the nature of solutions

CRITICAL DIVERSITY REQUIREMENTS:
1. CREATE DIFFERENT QUESTION TYPES - Each question must ask something completely different within the pattern:
   - Find missing measurements (sides, angles, areas, perimeters, volumes, etc.)
   - Calculate properties (slope, intercept, vertex, focus, discriminant, etc.)
   - Compare or analyze relationships (greater than, less than, equal, proportional)
   - Solve word problems or real-world applications related to the topic
   - Prove or derive relationships within the topic
   - Identify patterns, trends, or characteristics specific to the topic
   - Determine equations, formulas, or expressions for the topic

2. VARY PROBLEM-SOLVING APPROACHES:
   - Direct calculation vs. multi-step reasoning
   - Visual inspection vs. algebraic manipulation
   - Logical deduction vs. estimation
   - Forward problems vs. inverse problems

3. VARY THE DIFFICULTY WITHIN THE PATTERN:
   - Some questions should be straightforward applications
   - Some should require multiple steps or deeper understanding
   - Some should test advanced concepts within the topic

4. CRITICAL: ENSURE IMAGE DEPENDENCY:
   - Each question MUST be IMPOSSIBLE to answer without examining the diagram
   - The diagram must contain ALL necessary information visually
   - Question text MUST reference specific visual elements with their actual values
   - Students should be able to answer by looking at the diagram alone
   - Include ALL measurements, labels, and values needed in the TikZ diagram

5. MAINTAIN TOPIC CONSISTENCY:
   - Every question must clearly relate to the specific topic
   - Diagrams should represent concepts specific to the topic
   - Variable names and contexts should be topic-appropriate
   - Questions should use terminology and notation specific to the topic

Each instance must include:
1. Concrete variable values within specified ranges
2. Fully instantiated question text (DIFFERENT question types, topic-specific)
3. Correct final answer with explanation
4. Valid, compilable TikZ code for the diagram (topic-relevant)

TikZ Code Requirements:
- Use ONLY basic TikZ primitives: \\draw, \\node, \\circle, --, etc.
- NO external packages (e.g., no tikzlibrary imports)
- NO advanced LaTeX features
- Self-contained snippets (no preamble, no document environment)
- CRITICAL: Include ALL actual variable values as labels and coordinates
- CRITICAL: The diagram must visually represent the specific topic and question being asked
- Use coordinate system with sensible scale (e.g., 0-10 units)
- Add labels for important points, angles, lengths, etc. using \\node
- Show the actual measurements and values from the question variables

CRITICAL IMAGE REQUIREMENTS:
- The TikZ diagram must NOT be a generic skeleton
- Include specific coordinate values based on the question variables
- Add labels showing actual measurements (e.g., "5 cm", "30°", etc.)
- Visual representation of the exact scenario described in the question
- All relevant mathematical elements (angles, lengths, points) with their actual values
- The diagram must contain the answer to the question visually
- Highlight or emphasize the elements the question is asking about

CRITICAL: Generate 10 COMPLETELY DIFFERENT question types within the pattern, not just the same question with different numbers.
Vary the problem-solving approach and what is being asked while maintaining topic relevance.
Each question must be directly answerable by examining the diagram.

Return response as valid JSON array with exactly 10 question objects.
Do NOT include markdown formatting, just raw JSON.

Each question object must include:
- instance_id (0-9)
- variables (dict of variable names to values)
- question_text (specific, references diagram elements, topic-relevant)
- correct_answer (with explanation)
- tikz_code (complete, compilable, with actual values)
- difficulty
"""

# =====================================================================
# Validation Rules
# =====================================================================

TIKZ_PRIMITIVES = {
    "\\draw",
    "\\node",
    "\\circle",
    "\\rectangle",
    "\\path",
    "--",
    "to",
    "arc",
    "grid",
    "foreach",
}

FORBIDDEN_TIKZ_PATTERNS = [
    "import",
    "require",
    "usepackage",
    "usetikzlibrary",
    "documentclass",
    "begin{document}",
    "tikzset",
    "external",
]
