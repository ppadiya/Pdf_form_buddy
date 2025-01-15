import os
import pytesseract
from pdf2image import convert_from_path
from PyPDF2 import PdfReader
import pdfplumber
from transformers import pipeline
import logging

logger = logging.getLogger(__name__)

class PDFProcessor:
    def __init__(self):
        # Initialize AI models
        self.field_detector = pipeline(
            "token-classification", 
            model="dslim/bert-base-NER"
        )
        
    def extract_text(self, pdf_path):
        """Extract text from PDF using PyPDF2 with OCR fallback"""
        try:
            # First try regular text extraction
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            
            # If no text found, try OCR
            if not text.strip():
                images = convert_from_path(pdf_path)
                text = ""
                for image in images:
                    text += pytesseract.image_to_string(image) + "\n"
            
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            return ""

    def detect_form_fields(self, pdf_path):
        """Detect form fields using pdfplumber and AI"""
        try:
            detected_fields = []
            with pdfplumber.open(pdf_path) as pdf:
                for page_number, page in enumerate(pdf.pages):
                    # Extract text and form fields
                    text = page.extract_text()
                    form_fields = page.extract_words()
                    
                    # Process each word/field with AI
                    for field in form_fields:
                        field_text = field['text']
                        # Use AI to detect if this is a form field
                        ai_result = self.field_detector(field_text)
                        if any(ent['entity'] in ['B-FIELD', 'I-FIELD'] for ent in ai_result):
                            detected_fields.append({
                                'text': field_text,
                                'coordinates': (field['x0'], field['top'], field['x1'], field['bottom']),
                                'page': page_number + 1
                            })
            
            return detected_fields
        except Exception as e:
            logger.error(f"Error detecting form fields: {str(e)}")
            return []

    def process_pdf(self, pdf_path):
        """Main processing function that combines text extraction and field detection"""
        try:
            # Get raw text
            text = self.extract_text(pdf_path)
            
            # Detect fields using AI and pdfplumber
            detected_fields = self.detect_form_fields(pdf_path)
            
            # Process detected fields
            fields = []
            for field in detected_fields:
                field_text = field['text']
                fields.append({
                    'name': field_text.lower().replace(' ', '_'),
                    'label': field_text,
                    'type': 'text',  # Could be enhanced to detect field types
                    'required': True
                })
            
            return {
                'fields': fields,
                'raw_text': text
            }
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return {'fields': [], 'raw_text': ''}
