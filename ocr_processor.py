from pypdf import PdfReader
import paddleocr
import logging
from pathlib import Path
import json
from datetime import datetime
from tqdm import tqdm
import argparse
import fitz  # PyMuPDF
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SmartPDFProcessor:
    def __init__(self):
        """Initialize with minimal settings first"""
        self.ocr = None  # Initialize OCR only when needed
        
    def _init_ocr(self):
        """Lazy initialization of OCR to save memory when not needed"""
        if self.ocr is None:
            logger.info("Initializing OCR engine...")
            self.ocr = paddleocr.PaddleOCR(
                use_angle_cls=False,  # Disable angle detection for speed
                lang='en',
                show_log=False,
                use_gpu=False  # Set to True if you have GPU
            )

    def _extract_text_with_pypdf(self, pdf_path: str) -> tuple:
        """Extract text using PyPDF"""
        reader = PdfReader(pdf_path)
        text_content = []
        
        for page in reader.pages:
            text = page.extract_text()
            if text.strip():
                text_content.append(text)
                
        return text_content, len(text_content) > 0

    def _extract_text_with_pymupdf(self, pdf_path: str) -> tuple:
        """Extract text using PyMuPDF (usually better quality)"""
        doc = fitz.open(pdf_path)
        text_content = []
        
        for page in doc:
            text = page.get_text()
            if text.strip():
                text_content.append(text)
                
        doc.close()
        return text_content, len(text_content) > 0

    def _run_ocr(self, pdf_path: str, page_numbers=None) -> list:
        """Run OCR on specific pages or all pages"""
        self._init_ocr()
        doc = fitz.open(pdf_path)
        text_content = []
        
        pages_to_process = page_numbers if page_numbers else range(len(doc))
        
        for page_num in tqdm(pages_to_process, desc="Running OCR"):
            page = doc[page_num]
            pix = page.get_pixmap()
            
            # Save page as temporary image
            temp_img = f"temp_page_{page_num}.png"
            pix.save(temp_img)
            
            # Run OCR
            result = self.ocr.ocr(temp_img)
            
            if result and result[0]:
                page_text = "\n".join([line[1][0] for line in result[0] if line])
                text_content.append(page_text)
                
            # Clean up
            Path(temp_img).unlink()
            
        doc.close()
        return text_content

    def _is_scanned_pdf(self, text_content: list, total_pages: int) -> bool:
        """Determine if PDF is likely scanned based on text extraction results"""
        if not text_content:
            return True
            
        # Check text density
        total_text = "\n".join(text_content)
        chars_per_page = len(total_text) / total_pages
        
        # Check for common patterns in digital PDFs
        has_common_patterns = bool(re.search(r'[A-Za-z]{3,}', total_text))
        
        return chars_per_page < 100 or not has_common_patterns

    def process_pdf(self, pdf_path: str, output_path: str = None, 
                   max_pages: int = None, force_ocr: bool = False) -> dict:
        """
        Smart PDF processing with automatic detection of PDF type
        
        Args:
            pdf_path: Path to PDF file
            output_path: Optional path to save results
            max_pages: Maximum number of pages to process
            force_ocr: Force OCR even if text is extractable
        """
        try:
            logger.info(f"Processing PDF: {pdf_path}")
            start_time = datetime.now()
            
            # Get basic PDF info
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            doc.close()
            
            pages_to_process = range(min(total_pages, max_pages or total_pages))
            
            # Try text extraction first
            text_content, success = self._extract_text_with_pymupdf(pdf_path)
            
            # Determine if we need OCR
            needs_ocr = force_ocr or self._is_scanned_pdf(text_content, total_pages)
            
            if needs_ocr:
                logger.info("PDF appears to be scanned or has poor text quality, using OCR...")
                text_content = self._run_ocr(pdf_path, pages_to_process)
            else:
                logger.info("Successfully extracted text without OCR")
            
            # Prepare output
            result = {
                "pdf_path": pdf_path,
                "total_pages": total_pages,
                "pages_processed": len(pages_to_process),
                "extraction_method": "ocr" if needs_ocr else "text_extraction",
                "processing_time": str(datetime.now() - start_time),
                "timestamp": str(datetime.now()),
                "pages": [
                    {
                        "page_number": i + 1,
                        "content": content
                    }
                    for i, content in enumerate(text_content)
                ],
                "raw_text": "\n\n".join(text_content)
            }
            
            # Save if output path provided
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved results to {output_path}")
            
            return result
            
        except Exception as e:
            logger.error(f"Processing failed: {str(e)}")
            raise

def main():
    parser = argparse.ArgumentParser(description='Smart PDF Processing')
    parser.add_argument('pdf_path', help='Path to PDF file')
    parser.add_argument('--output', '-o', help='Output JSON path')
    parser.add_argument('--max-pages', type=int, help='Maximum pages to process')
    parser.add_argument('--force-ocr', action='store_true', help='Force OCR processing')
    args = parser.parse_args()
    
    try:
        processor = SmartPDFProcessor()
        result = processor.process_pdf(
            args.pdf_path, 
            args.output,
            max_pages=args.max_pages,
            force_ocr=args.force_ocr
        )
        
        if not args.output:
            print(json.dumps(result, indent=2))
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()