from __future__ import annotations

import sys
import argparse
from datetime import datetime
from pathlib import Path
from loguru import logger

# Add root folder to pythonpath
sys.path.append(str(Path(__file__).parent.parent))

from app.config import settings
from app.ingestion.reader import DocxReader
from app.llm.fallback import LLMFallback
from app.matching.matcher import SectionMatcher
from app.reports.generator import ReportGenerator
from app.segmentation.segmenter import DocumentSegmenter
from app.template.renderer import DocxRenderer


def setup_logging() -> None:
    """Configures the loguru logging formats and paths."""
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    log_file = settings.log_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Configure logger
    logger.remove()  # Remove default handler
    
    # Add console logger
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    
    # Add file logger
    logger.add(
        str(log_file),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        encoding="utf-8"
    )
    
    logger.info(f"Logging initialized. Log file saved at: {log_file}")


def process_document(
    file_path: Path,
    reader: DocxReader,
    segmenter: DocumentSegmenter,
    matcher: SectionMatcher,
    renderer: DocxRenderer,
    fallback_client: LLMFallback,
) -> dict[str, Any]:
    """Processes a single .docx file through ingestion, segmentation, matching, and rendering."""
    file_name = file_path.name
    logger.info(f"==== Start processing document: {file_name} ====")
    
    result = {
        "file_name": file_name,
        "success": False,
        "error_message": None,
        "mappings": {},
        "unmatched_sections": [],
        "llm_fallback_triggered": False,
        "timestamp": datetime.now().isoformat(),
    }
    
    try:
        # 1. Ingest blocks
        blocks = reader.read(str(file_path))
        
        # 2. Segment into headed sections
        sections = segmenter.segment(blocks)
        
        # 3. Match against canonical headings
        mappings = matcher.match_document(sections)
        
        # Extract unmatched source sections to keep track of them
        unmatched_source = mappings.pop("unmatched", [])
        result["unmatched_sections"] = unmatched_source
        
        # 4. Check for missing required canonical sections
        missing_canonicals = []
        for canonical in matcher.canonical_sections:
            if not mappings[canonical]:
                missing_canonicals.append(canonical)
                
        # 5. Fallback logic if LLM is enabled and sections are missing
        llm_extractions = {}
        if missing_canonicals and fallback_client.enabled:
            logger.info(f"Missing canonical sections: {missing_canonicals}. Triggering LLM extraction.")
            result["llm_fallback_triggered"] = True
            
            # Combine all paragraph text of the document to pass to the LLM
            full_document_text = "\n\n".join(sec.get_text() for sec in sections)
            
            for missing_section in missing_canonicals:
                extracted_content = fallback_client.extract_section_content(
                    document_text=full_document_text,
                    section_name=missing_section
                )
                if extracted_content:
                    llm_extractions[missing_section] = extracted_content

        # 6. Render standardized document
        output_file_name = f"std_{file_path.stem}.docx"
        output_path = renderer.render(
            mappings=mappings,
            llm_extractions=llm_extractions,
            output_file_name=output_file_name
        )
        
        # Populate mapping info for reports (convert DocumentSection to string metadata)
        report_mappings = {}
        for canonical, matches in mappings.items():
            report_mappings[canonical] = [
                (sec, score, status) for sec, score, status in matches
            ]
        
        result["mappings"] = report_mappings
        result["success"] = True
        logger.info(f"==== Successfully standardized document: {file_name} -> {output_path.name} ====")
        
    except Exception as e:
        logger.exception(f"Error standardizing document {file_name}: {e}")
        result["success"] = False
        result["error_message"] = str(e)
        
    return result


def parse_args() -> argparse.Namespace:
    """Parses command-line arguments for the standardization tool."""
    parser = argparse.ArgumentParser(description="AI-assisted Word Document Standardization Tool")
    parser.add_argument(
        "--template", "-t",
        type=str,
        default=None,
        help="Path to standard template .docx file"
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        default=None,
        help="Path to input .docx file or directory containing .docx files"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Path to output directory"
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        default=None,
        help="Enable OpenAI LLM fallback for unmatched sections"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        default=None,
        help="Disable OpenAI LLM fallback"
    )
    return parser.parse_args()


def main() -> None:
    # Set up folders and logs
    if sys.platform.startswith("win"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
            
    setup_logging()
    
    args = parse_args()
    
    # Override settings dynamically based on CLI args
    template_path = Path(args.template) if args.template else settings.template_path
    
    if args.output:
        settings.output_dir = Path(args.output)
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        
    if args.use_llm is not None:
        settings.use_llm_fallback = True
    elif args.no_llm is not None:
        settings.use_llm_fallback = False
        
    logger.info("Initializing standardization components...")
    
    # 1. Initialize Renderer with specified template path
    renderer = DocxRenderer(template_path=template_path)
    
    # 2. Get dynamic canonical sections from template
    canonical_sections = list(renderer.placeholder_mapping.keys())
    logger.info(f"Using template sections: {canonical_sections}")
    
    # 3. Initialize Matcher with dynamic canonical sections
    matcher = SectionMatcher(canonical_sections=canonical_sections)
    
    reader = DocxReader()
    segmenter = DocumentSegmenter()
    fallback_client = LLMFallback()
    report_gen = ReportGenerator()
    
    # Resolve input path
    input_arg = args.input if args.input else str(settings.input_dir)
    input_path = Path(input_arg)
    
    word_files = []
    if input_path.is_file():
        if input_path.suffix.lower() == ".docx" and not input_path.name.startswith("~$"):
            word_files.append(input_path)
    elif input_path.is_dir():
        word_files = [
            f for f in input_path.iterdir()
            if f.is_file() and f.suffix.lower() == ".docx" and not f.name.startswith("~$")
        ]
    else:
        logger.error(f"Input path '{input_arg}' does not exist or is not a valid directory/file.")
        print(f"\nĐường dẫn đầu vào '{input_arg}' không hợp lệ hoặc không tồn tại.")
        return
        
    if not word_files:
        logger.warning(f"No .docx files found to process at: {input_path}")
        print(f"\nKhông tìm thấy tệp tin Word cần chuẩn hóa tại: {input_path.absolute()}")
        return

    logger.info(f"Found {len(word_files)} document(s) to process.")
    
    run_results = []
    for file_path in word_files:
        res = process_document(
            file_path=file_path,
            reader=reader,
            segmenter=segmenter,
            matcher=matcher,
            renderer=renderer,
            fallback_client=fallback_client
        )
        run_results.append(res)
        
    # Generate visual HTML report
    report_path = report_gen.generate(run_results)
    
    # Print console summary
    successful = sum(1 for r in run_results if r["success"])
    print(f"\n==================================================")
    print(f"Hoàn thành xử lý {len(run_results)} tài liệu:")
    print(f"  - Thành công: {successful}")
    print(f"  - Thất bại: {len(run_results) - successful}")
    print(f"Báo cáo chi tiết đã lưu tại: {report_path.absolute()}")
    print(f"==================================================")


if __name__ == "__main__":
    main()
