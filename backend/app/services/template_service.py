import re
from typing import List, Dict, Any

class TemplateService:
    @staticmethod
    def extract_variables(content: str) -> List[str]:
        """Extract variable names like {{name}}, {{plan}} from template text."""
        matches = re.findall(r"\{\{([a-zA-Z0-9_]+)\}\}", content)
        # Deduplicate while preserving order
        seen = set()
        variables = []
        for m in matches:
            if m not in seen:
                seen.add(m)
                variables.append(m)
        return variables

    @staticmethod
    def render_template(content: str, contact_data: Dict[str, Any], variables_mapping: Dict[str, str] = None) -> str:
        """
        Renders template text by replacing {{variable}} with contact attributes or custom_fields.
        """
        variables_mapping = variables_mapping or {}
        rendered = content

        # Standard fields on contact
        std_fields = {
            "name": contact_data.get("name", ""),
            "phone": contact_data.get("phone", ""),
            "email": contact_data.get("email", ""),
        }
        custom_fields = contact_data.get("custom_fields", {}) or {}

        def replace_var(match):
            var_name = match.group(1)
            mapped_key = variables_mapping.get(var_name, var_name)
            
            if mapped_key in std_fields and std_fields[mapped_key]:
                return str(std_fields[mapped_key])
            if mapped_key in custom_fields and custom_fields[mapped_key]:
                return str(custom_fields[mapped_key])
            if var_name in custom_fields and custom_fields[var_name]:
                return str(custom_fields[var_name])
            if var_name in std_fields and std_fields[var_name]:
                return str(std_fields[var_name])
            
            return f"[{var_name}]"

        return re.sub(r"\{\{([a-zA-Z0-9_]+)\}\}", replace_var, rendered)
