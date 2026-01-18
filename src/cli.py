"""
Command-line interface for the content generation pipeline.
"""

import argparse
import logging
import sys
from pathlib import Path

from .pipeline import Pipeline
from .config import get_pipeline_config


def setup_logging(verbose: bool = False):
    """Configure logging."""
    
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('fermi.log')
        ]
    )


def main():
    """Main CLI entry point."""
    
    parser = argparse.ArgumentParser(
        description='Automated diagram-based question generation pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.cli --topic "Coordinate Geometry" --output ./output/
  python -m src.cli --topic "Force and Motion" --grade 10-11 --output ./my_output/
  python -m src.cli --topic "Quadratic Equations" --verbose
        """
    )
    
    parser.add_argument(
        '--topic',
        required=True,
        help='Academic topic for question generation (e.g., "Coordinate Geometry")'
    )
    
    parser.add_argument(
        '--grade',
        default='9-12',
        choices=['9', '10', '11', '12', '9-10', '10-11', '11-12', '9-12'],
        help='Target grade level (default: 9-12)'
    )
    
    parser.add_argument(
        '--output',
        default='./output',
        help='Output directory for PDFs and diagrams (default: ./output)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable debug logging'
    )
    
    parser.add_argument(
        '--model',
        default='gpt-4',
        help='LLM model to use (default: gpt-4)'
    )
    
    parser.add_argument(
        '--validate',
        action='store_true',
        default=True,
        help='Validate solvability of questions'
    )
    
    parser.add_argument(
        '--no-validate',
        dest='validate',
        action='store_false',
        help='Skip solvability validation'
    )
    
    parser.add_argument(
        '--parallel',
        action='store_true',
        default=True,
        help='Render diagrams in parallel'
    )
    
    parser.add_argument(
        '--no-parallel',
        dest='parallel',
        action='store_false',
        help='Render diagrams sequentially'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Fermi: Diagram-Based Question Generation Pipeline")
        logger.info(f"Topic: {args.topic}")
        logger.info(f"Grade Level: {args.grade}")
        logger.info(f"Output Directory: {args.output}")
        
        # Get configuration
        config = get_pipeline_config()
        config.output_dir = args.output
        config.llm.model = args.model
        config.validate_solvability = args.validate
        config.parallel_rendering = args.parallel
        
        # Create pipeline and run
        pipeline = Pipeline(config)
        manifest = pipeline.run(args.topic, args.grade)
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("="*60)
        logger.info(f"Topic: {manifest.topic}")
        logger.info(f"Total Patterns: {manifest.total_patterns}")
        logger.info(f"Total Questions: {manifest.total_questions}")
        logger.info(f"Output Directory: {manifest.output_dir}")
        logger.info(f"PDFs Generated: {len(manifest.pdfs)}")
        logger.info("\nGenerated PDFs:")
        for pdf in manifest.pdfs:
            logger.info(f"  - {pdf.pdf_path}")
        logger.info("="*60 + "\n")
        
        return 0
    
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
