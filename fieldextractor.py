import datetime
import os
import logging
import json
from pathlib import Path
from typing import Dict, Optional
from openai import OpenAI
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FieldExtractor:
    PROMPT_TEMPLATE = """You are a form data extraction assistant. Analyze this form text and extract all relevant fields.

Form text:
{text}

Required fields to extract (include any additional fields you find):
- Full Name
- Address (including street, city, state, zip)
- Phone Number
- Email
- Date of Birth
- Social Security Number (if present)
- Employment Status (if present)
- Income Information (if present)
- Emergency Contact (if present)

Important instructions:
1. Return ONLY a JSON object with the extracted fields
2. Use null for missing fields
3. Maintain the exact formatting found in the form
4. Include any additional fields you find that seem important
5. Group related fields into objects where appropriate

Return the JSON object only, no other text."""

    def __init__(self):
        load_dotenv()
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable not set")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )

    def clean_api_response(self, text: str) -> str:
        """
        Clean the API response text to ensure it contains valid JSON.
        """
        # Remove any potential markdown code block markers
        text = text.replace('```json', '').replace('```', '').strip()
        
        # Find the first '{' and last '}' to extract just the JSON object
        start = text.find('{')
        end = text.rfind('}')
        
        if start == -1 or end == -1:
            raise ValueError("No valid JSON object found in response")
            
        return text[start:end + 1]

    def extract_fields(self, ocr_result: Dict, output_path: Optional[str] = None) -> Dict:
        """
        Extract form fields from OCR result using DeepSeek API.
        
        Args:
            ocr_result: Dictionary containing OCR results
            output_path: Optional path to save extracted fields
            
        Returns:
            Dictionary of extracted fields
        """
        try:
            logger.info("Extracting fields from OCR result...")

            # Combine text into a single string for processing
            text_list = ocr_result.get("text", [])
            if not text_list or not isinstance(text_list, list):
                raise ValueError("OCR result must contain a 'text' field as a list of strings.")
            text = "\n".join(text_list).strip()
            if not text:
                raise ValueError("No valid text found in OCR result.")

            # Call DeepSeek API
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{
                    "role": "user",
                    "content": self.PROMPT_TEMPLATE.format(text=text)
                }],
                max_tokens=1024,
                temperature=0.7
            )

            # Log the API response for debugging
            logger.info("Raw API Response:")
            logger.info(f"Response content: {response.choices[0].message.content if response.choices else 'No content'}")

            # Get the response content and clean it
            if not response.choices or not response.choices[0].message:
                raise ValueError("The API returned an empty response")
                
            content = response.choices[0].message.content.strip()
            if not content:
                raise ValueError("The API returned empty content")

            # Clean and parse the response
            try:
                cleaned_content = self.clean_api_response(content)
                logger.info(f"Cleaned content: {cleaned_content}")
                result = json.loads(cleaned_content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed even after cleaning. Content: {cleaned_content}")
                logger.error(f"JSON error: {str(e)}")
                raise ValueError(f"Failed to parse API response as JSON: {str(e)}")
            
            # Add metadata
            output = {
                "source_pdf": ocr_result.get("pdf_path"),
                "timestamp": str(datetime.datetime.now()),
                "extracted_fields": result
            }

            # Save if output path provided
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(output, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved extracted fields to {output_path}")

            return output

        except Exception as e:
            logger.error(f"Field extraction failed: {str(e)}")
            raise

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Extract fields from OCR result')
    parser.add_argument('ocr_path', help='Path to OCR JSON file')
    parser.add_argument('--output', '-o', help='Output JSON path')
    args = parser.parse_args()

    try:
        # Load OCR result
        with open(args.ocr_path, 'r', encoding='utf-8') as f:
            ocr_result = json.load(f)

        # Extract fields
        extractor = FieldExtractor()
        result = extractor.extract_fields(ocr_result, args.output)
        if not args.output:
            print(json.dumps(result, indent=2))

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()