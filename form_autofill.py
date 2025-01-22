import re
from difflib import SequenceMatcher
from datetime import datetime
from typing import Dict, Any, List

class FormAutofill:
    @staticmethod
    def _normalize_field_name(name: str) -> str:
        """Normalize field names for better matching"""
        return re.sub(r'[^a-z0-9]', '', name.lower())

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """Calculate similarity between two strings"""
        return SequenceMatcher(None, a, b).ratio()

    @staticmethod
    def _match_field(field_name: str, profile_fields: Dict[str, Any]) -> str:
        """Find the best matching field in profile data"""
        normalized_field = FormAutofill._normalize_field_name(field_name)
        
        # Try exact match first
        if normalized_field in profile_fields:
            return normalized_field
            
        # Find best matching field
        best_match = None
        best_score = 0.5  # Lower threshold for better matching
        
        for profile_field in profile_fields:
            normalized_profile = FormAutofill._normalize_field_name(profile_field)
            score = FormAutofill._similarity(normalized_field, normalized_profile)
            
            if score > best_score:
                best_score = score
                best_match = profile_field
                
        return best_match

    @staticmethod
    def autofill_form_fields(form_fields: List[Dict[str, Any]], profile_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Autofill form fields with matching profile data"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Profile data received: {profile_data}")
        filled_fields = []
        
        for field in form_fields:
            # Skip section headers
            if field.get('type') == 'section':
                filled_fields.append(field)
                continue
                
            field_name = field['name']
            field_value = field['value']
            
            logger.info(f"Processing field: {field_name}")
            
            # Find matching profile field
            matched_field = FormAutofill._match_field(field_name, profile_data)
            
            if matched_field:
                profile_value = profile_data[matched_field]
                logger.info(f"Matched {field_name} with profile field {matched_field}: {profile_value}")
                
                # Handle special field types
                if 'date' in field_name.lower() and isinstance(profile_value, str):
                    try:
                        # Convert to standard date format
                        dt = datetime.strptime(profile_value, '%Y-%m-%d')
                        field['value'] = dt.strftime('%d/%m/%Y')
                    except ValueError:
                        field['value'] = profile_value
                else:
                    field['value'] = profile_value
            else:
                logger.info(f"No match found for field: {field_name}")
                    
            filled_fields.append(field)
                
        return filled_fields
