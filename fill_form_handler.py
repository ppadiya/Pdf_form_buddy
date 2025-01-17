import logging
import re
from flask import render_template, flash
from flask_wtf import FlaskForm
from wtforms import StringField, validators
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class FillFormHandler:
    @staticmethod
    def _create_field_validators(field_name: str) -> List:
        """Create appropriate validators for each field type"""
        validators_list = [validators.DataRequired()]
        
        if 'email' in field_name.lower():
            validators_list.append(validators.Email())
        elif 'phone' in field_name.lower():
            validators_list.append(validators.Regexp(r'^\+?1?\d{9,15}$'))
        elif 'ssn' in field_name.lower():
            validators_list.append(validators.Regexp(r'^\d{3}-?\d{2}-?\d{4}$'))
            
        return validators_list

    @staticmethod
    def _sanitize_field_name(name: str) -> str:
        """Convert field name to valid Python identifier"""
        # Replace invalid characters with underscore
        name = re.sub(r'\W|^(?=\d)', '_', name)
        return name.lower()

    @staticmethod
    def handle_fill_form(extracted_fields: Dict[str, Any], raw_text: str, raw_response: str = None) -> str:
        """Handle the fill form page rendering with extracted fields"""
        try:
            logger.info("Processing form fields")
            
            if not extracted_fields:
                logger.warning("No extracted fields found")
                flash("No form fields could be extracted", "warning")
                extracted_fields = {}

            
            class DynamicForm(FlaskForm):
                pass

            def process_fields(fields: Dict[str, Any], prefix: str = '') -> List[Dict]:
                """Recursively process fields to handle nested structures"""
                form_fields = []
                
                for field_name, field_value in fields.items():
                    full_name = f"{prefix}_{field_name}" if prefix else field_name
                    sanitized_name = FillFormHandler._sanitize_field_name(full_name)
                    
                    if isinstance(field_value, dict):
                        # Add section heading
                        form_fields.append({
                            'type': 'section',
                            'label': field_name.replace('_', ' ').title(),
                            'name': sanitized_name
                        })
                        # Recursively process nested fields
                        form_fields.extend(process_fields(field_value, sanitized_name))
                    else:
                        # Determine field type and validators
                        validators_list = FillFormHandler._create_field_validators(field_name)
                        
                        # Create form field
                        field_info = {
                            'name': sanitized_name,
                            'label': field_name.replace('_', ' ').title(),
                            'type': 'text',
                            'value': str(field_value) if field_value is not None else '',
                            'required': True
                        }
                        
                        # Add field to dynamic form
                        setattr(
                            DynamicForm,
                            sanitized_name,
                            StringField(
                                field_info['label'],
                                validators=validators_list
                            )
                        )
                        
                        form_fields.append(field_info)
                
                return form_fields

            # Process fields recursively
            form_fields = process_fields(extracted_fields)
            
            if not form_fields:
                logger.warning("No form fields generated")
                flash("No form fields could be generated", "warning")
                return render_template(
                    'fill_form.html',
                    error="No form fields could be generated"
                )
            
            # Create form instance
            form = DynamicForm()
            
            logger.info(f"Generated {len(form_fields)} form fields")
            
            return render_template(
                'fill_form.html',
                form=form,
                form_fields=form_fields,
                raw_text=raw_text
            )
            
        except Exception as e:
            logger.error(f"Error handling fill form: {str(e)}", exc_info=True)
            flash(f"An error occurred while processing the form: {str(e)}", "error")
            return render_template(
                'fill_form.html',
                error="An error occurred while processing the form"
            )
