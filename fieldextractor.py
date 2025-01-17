import datetime
import os
import logging
import json
import re
from pathlib import Path
from typing import Dict, Optional, Union
from openai import OpenAI
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fieldextractor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FieldExtractor:
    PROMPT_TEMPLATE = """You are a visa application form data extraction assistant. Analyze this form data and extract all relevant fields.

Form data:
{text}

Required fields to extract (include any additional fields you find):
- Applicant Information:
  - Full Name
  - Date of Birth
  - Nationality
  - Passport Number
  - Current Address
  - Phone Number
  - Email
- Family Details:
  - Spouse Information (if present)
  - Children Information (if present)
  - Family in Destination Country (if present)
- Travel Information:
  - Purpose of Visit
  - Intended Arrival Date
  - Intended Departure Date
  - Previous Visits (if present)
- Employment/Education:
  - Current Occupation
  - Employer/School Name
  - Address
  - Contact Information
- Additional Information:
  - Criminal History (if present)
  - Health Information (if present)
  - Financial Support Details

Important instructions:
1. Return ONLY a JSON object with the extracted fields
2. Use null for missing fields
3. Maintain the exact formatting found in the data
4. Include any additional fields you find that seem important
5. Group related fields into nested objects where appropriate
6. Ensure all field names are valid Python identifiers
7. Pay special attention to family details and relationships
8. Extract all text sections even if they don't match specific fields

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

    def _validate_extracted_fields(self, fields: Dict) -> bool:
        """Validate the structure of extracted fields"""
        required_fields = {
            'full_name',
            'date_of_birth',
            'nationality',
            'passport_number',
            'current_address',
            'phone_number',
            'email'
        }
        return all(field in fields for field in required_fields)

    def clean_api_response(self, text: str) -> Union[str, None]:
        """Clean and validate the API response text to ensure it contains valid JSON."""
        try:
            # Remove any potential markdown code block markers
            text = text.replace('```json', '').replace('```', '').strip()
            
            # Remove any trailing commas that might break JSON parsing
            text = re.sub(r',\s*}', '}', text)
            text = re.sub(r',\s*]', ']', text)
            
            # Find the first '{' and last '}' to extract just the JSON object
            start = text.find('{')
            end = text.rfind('}')
            
            if start == -1 or end == -1:
                logger.error("No valid JSON object found in response")
                return None
                
            json_str = text[start:end + 1]
            
            # Validate JSON by attempting to parse it
            json.loads(json_str)
            
            return json_str
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON validation failed: {str(e)}")
            logger.error(f"Problematic JSON content: {text}")
            return None

    def extract_fields(self, data: Union[Dict, str]) -> Dict:
        """Extract form fields using DeepSeek API with robust error handling."""
        try:
            # Log the input data
            logger.info("Starting field extraction")
            
            # Convert input data to string if it's a dict
            input_text = json.dumps(data) if isinstance(data, dict) else str(data)
            
            # Prepare the API request with formatted prompt
            formatted_prompt = self.PROMPT_TEMPLATE.format(text=input_text)
            
            request_messages = [
                {"role": "system", "content": formatted_prompt},
                {"role": "user", "content": input_text}
            ]
            
            logger.debug("Sending API request")
            
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=request_messages,
                max_tokens=1024,
                temperature=0.1  # Lower temperature for more consistent output
            )
            
            if not response.choices or not response.choices[0].message:
                logger.error("Empty response from API")
                raise ValueError("Empty response from API")
                
            response_text = response.choices[0].message.content
            logger.debug(f"Raw API response content: {response_text}")
            
            # Clean and parse the response
            cleaned_response = self.clean_api_response(response_text)
            if not cleaned_response:
                raise ValueError("Failed to clean API response")
                
            extracted_fields = json.loads(cleaned_response)
            
            # Validate the extracted fields
            if not self._validate_extracted_fields(extracted_fields):
                logger.warning("Missing required fields in response")
            
            logger.info("Successfully extracted fields")
            return {
                "extracted_fields": extracted_fields,
                "raw_response": response_text,
                "status": "success"
            }
                
        except Exception as e:
            logger.error(f"Field extraction failed: {str(e)}", exc_info=True)
            return {
                "extracted_fields": {},
                "raw_response": "",
                "status": "error",
                "error": str(e)
            }
