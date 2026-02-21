"""
Document validation against JSON schemas.

Validates trading documents (YAML) against predefined JSON schemas
before ingestion into RAG (pgvector) and Graph (Neo4j) systems.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

try:
    from jsonschema import Draft7Validator, ValidationError

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    Draft7Validator = None
    ValidationError = Exception

log = logging.getLogger(__name__)

# Schema directory - relative to project root
SCHEMA_DIR = Path(__file__).parent.parent.parent / "tradegent_knowledge" / "schemas"

# Map document paths to schema files
SCHEMA_MAP = {
    "earnings": "earnings-analysis.json",
    "analysis": "stock-analysis.json",
    "trades": "trade-journal.json",
    "strategies": "strategy.json",
    "tickers": "ticker.json",
    "ticker-profiles": "ticker.json",
    "learnings": "learning.json",
    "research": "research.json",
    "watchlist": "watchlist.json",
    "scanners": "scanner-config.json",
    "reviews": "post-trade-review.json",
}


@dataclass
class ValidationResult:
    """Result of document validation."""

    valid: bool
    file_path: str
    schema_name: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    document: dict | None = None

    @property
    def error_summary(self) -> str:
        """Get summary of validation errors."""
        if not self.errors:
            return ""
        return "; ".join(self.errors[:3])  # First 3 errors


class DocumentValidator:
    """Validates trading documents against JSON schemas."""

    def __init__(self, schema_dir: Path | None = None):
        """
        Initialize validator.

        Args:
            schema_dir: Directory containing JSON schemas.
                       Defaults to tradegent_knowledge/schemas/
        """
        self.schema_dir = schema_dir or SCHEMA_DIR
        self._schema_cache: dict[str, dict] = {}

        if not HAS_JSONSCHEMA:
            log.warning("jsonschema not installed - validation disabled")

    def load_schema(self, schema_name: str) -> dict | None:
        """Load and cache a JSON schema."""
        if schema_name in self._schema_cache:
            return self._schema_cache[schema_name]

        schema_path = self.schema_dir / schema_name
        if not schema_path.exists():
            log.warning(f"Schema not found: {schema_path}")
            return None

        try:
            with open(schema_path) as f:
                schema = json.load(f)
            self._schema_cache[schema_name] = schema
            return schema
        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON schema {schema_name}: {e}")
            return None

    def get_schema_for_file(self, file_path: str) -> str | None:
        """Determine which schema to use based on file path."""
        return get_schema_for_path(file_path)

    def validate(self, file_path: str) -> ValidationResult:
        """
        Validate a document against its schema.

        Args:
            file_path: Path to YAML document

        Returns:
            ValidationResult with validation status and any errors
        """
        path = Path(file_path)
        result = ValidationResult(valid=False, file_path=str(path))

        # Check file exists
        if not path.exists():
            result.errors.append(f"File not found: {path}")
            return result

        # Check file extension
        if path.suffix not in (".yaml", ".yml"):
            result.valid = True
            result.warnings.append("Not a YAML file - skipped validation")
            return result

        # Determine schema
        schema_name = self.get_schema_for_file(str(path))
        if not schema_name:
            result.valid = True
            result.warnings.append("No schema mapping - skipped validation")
            return result

        result.schema_name = schema_name

        # Load document
        try:
            with open(path) as f:
                doc = yaml.safe_load(f)

            if doc is None:
                result.errors.append("Empty document")
                return result

            result.document = doc

        except yaml.YAMLError as e:
            result.errors.append(f"YAML parse error: {e}")
            return result

        # Skip schema validation if jsonschema not available
        if not HAS_JSONSCHEMA:
            result.valid = True
            result.warnings.append("jsonschema not installed - schema validation skipped")
            return result

        # Load schema and validate
        schema = self.load_schema(schema_name)
        if not schema:
            result.valid = True
            result.warnings.append(f"Schema {schema_name} not found - skipped")
            return result

        try:
            validator = Draft7Validator(schema)
            errors = list(validator.iter_errors(doc))

            if errors:
                for error in errors[:5]:  # Limit to 5 errors
                    path_str = ".".join(str(p) for p in error.absolute_path)
                    if path_str:
                        result.errors.append(f"{path_str}: {error.message}")
                    else:
                        result.errors.append(error.message)
                return result

            result.valid = True
            return result

        except Exception as e:
            result.errors.append(f"Validation error: {e}")
            return result

    def validate_dict(self, doc: dict, schema_name: str) -> ValidationResult:
        """
        Validate a dictionary against a specific schema.

        Args:
            doc: Document as dictionary
            schema_name: Name of schema file

        Returns:
            ValidationResult
        """
        result = ValidationResult(
            valid=False,
            file_path="<dict>",
            schema_name=schema_name,
            document=doc,
        )

        if not HAS_JSONSCHEMA:
            result.valid = True
            result.warnings.append("jsonschema not installed")
            return result

        schema = self.load_schema(schema_name)
        if not schema:
            result.valid = True
            result.warnings.append(f"Schema {schema_name} not found")
            return result

        try:
            validator = Draft7Validator(schema)
            errors = list(validator.iter_errors(doc))

            if errors:
                for error in errors[:5]:
                    path_str = ".".join(str(p) for p in error.absolute_path)
                    if path_str:
                        result.errors.append(f"{path_str}: {error.message}")
                    else:
                        result.errors.append(error.message)
                return result

            result.valid = True
            return result

        except Exception as e:
            result.errors.append(f"Validation error: {e}")
            return result


def get_schema_for_path(file_path: str) -> str | None:
    """
    Determine which schema to use based on file path.

    Looks at the directory structure to map to appropriate schema.
    Checks from most specific (nearest to file) to least specific (root).
    Supports paths like:
    - tradegent_knowledge/knowledge/analysis/earnings/NVDA_20250120.yaml -> earnings-analysis.json
    - knowledge/trades/TRD-2025-001.yaml -> trade-journal.json
    - earnings/AAPL_Q1_2025.yaml -> earnings-analysis.json

    Args:
        file_path: Path to document

    Returns:
        Schema filename or None if no mapping found
    """
    path = Path(file_path)
    parts = path.parts

    # Look for known directory names, starting from most specific (leaf-first)
    for part in reversed(parts):
        part_lower = part.lower()
        if part_lower in SCHEMA_MAP:
            return SCHEMA_MAP[part_lower]

        # Handle compound paths like "analysis/earnings"
        for key in SCHEMA_MAP:
            if key in part_lower:
                return SCHEMA_MAP[key]

    return None


def validate_document(file_path: str) -> ValidationResult:
    """
    Convenience function to validate a single document.

    Args:
        file_path: Path to YAML document

    Returns:
        ValidationResult
    """
    validator = DocumentValidator()
    return validator.validate(file_path)


# Global validator instance for reuse
_validator: DocumentValidator | None = None


def get_validator() -> DocumentValidator:
    """Get or create global validator instance."""
    global _validator
    if _validator is None:
        _validator = DocumentValidator()
    return _validator
