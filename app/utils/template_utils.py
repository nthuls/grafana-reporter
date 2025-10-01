# app/utils/template_utils.py
import os
import yaml
from typing import List, Dict, Any, Optional

class TemplateManager:
    """Utility for loading and managing query templates from YAML files"""
    
    def __init__(self, templates_dir: str = "templates"):
        """Initialize the template manager with the templates directory path"""
        self.templates_dir = templates_dir
        os.makedirs(self.templates_dir, exist_ok=True)
        self.default_template_path = os.path.join(self.templates_dir, "default_templates.yaml")
    
    def load_templates(self) -> List[Dict[str, Any]]:
        """Load all templates from YAML files in the templates directory"""
        templates = []
        
        # Load default templates if they exist
        if os.path.exists(self.default_template_path):
            default_templates = self._load_yaml_file(self.default_template_path)
            if default_templates and "templates" in default_templates:
                templates.extend(default_templates["templates"])
        
        # Load additional template files
        for filename in os.listdir(self.templates_dir):
            if filename.endswith(".yaml") and filename != "default_templates.yaml":
                file_path = os.path.join(self.templates_dir, filename)
                file_templates = self._load_yaml_file(file_path)
                if file_templates and "templates" in file_templates:
                    templates.extend(file_templates["templates"])
        
        return templates
    
    def save_template(self, template: Dict[str, Any], filename: Optional[str] = None) -> bool:
        """Save a new template to a YAML file"""
        if not filename:
            # Use the default templates file
            file_path = self.default_template_path
            
            # Load existing templates
            existing_templates = {"templates": []}
            if os.path.exists(file_path):
                existing_templates = self._load_yaml_file(file_path) or {"templates": []}
                if "templates" not in existing_templates:
                    existing_templates["templates"] = []
            
            # Add the new template
            existing_templates["templates"].append(template)
            
            # Save back to the file
            return self._save_yaml_file(existing_templates, file_path)
        else:
            # Use the specified file
            if not filename.endswith(".yaml"):
                filename += ".yaml"
            file_path = os.path.join(self.templates_dir, filename)
            
            # Create a new file with just this template
            return self._save_yaml_file({"templates": [template]}, file_path)
    
    def _load_yaml_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Load YAML content from a file"""
        try:
            with open(file_path, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading YAML file {file_path}: {str(e)}")
            return None
    
    def _save_yaml_file(self, content: Dict[str, Any], file_path: str) -> bool:
        """Save content to a YAML file"""
        try:
            with open(file_path, "w") as f:
                yaml.dump(content, f, default_flow_style=False)
            return True
        except Exception as e:
            print(f"Error saving YAML file {file_path}: {str(e)}")
            return False