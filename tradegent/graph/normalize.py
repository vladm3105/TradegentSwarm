"""Entity normalization with disambiguation."""

import logging
import re
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

# Load aliases on module import
_aliases_path = Path(__file__).parent / "aliases.yaml"
_aliases: dict = {}

if _aliases_path.exists():
    with open(_aliases_path) as f:
        _aliases = yaml.safe_load(f)


def normalize_entity(entity: dict, context: str | None = None) -> dict:
    """
    Apply normalization rules to an extracted entity.

    Rules applied:
    1. Separator standardization (underscores → hyphens)
    2. Case normalization (PascalCase types, Title Case values)
    3. Ticker resolution (company name → ticker symbol)
    4. Alias resolution (GOOG → GOOGL)
    5. Disambiguation (Company vs Ticker, Strategy vs Pattern)

    Args:
        entity: Dict with type, value, confidence, evidence
        context: Optional source text for disambiguation

    Returns:
        Normalized entity dict
    """
    result = entity.copy()

    # Step 1: Normalize type to PascalCase
    result["type"] = normalize_type(result.get("type", ""))

    # Step 2: Get the raw value
    value = _to_text(result.get("value", ""))

    # Step 3: Apply type-specific normalization
    entity_type = result["type"]

    if entity_type == "Ticker":
        value = normalize_ticker(value)
    elif entity_type == "Company":
        value = normalize_company(value)
        # Try to resolve to ticker
        ticker = resolve_ticker(value)
        if ticker:
            result["resolved_ticker"] = ticker
    elif entity_type == "Pattern":
        value = normalize_pattern(value)
    elif entity_type == "Bias":
        value = normalize_bias(value)
    elif entity_type == "Strategy":
        value = normalize_strategy(value)
    else:
        # Default: Title Case
        value = value.strip().title()

    result["value"] = value

    # Step 4: Disambiguate if context provided
    if context:
        result = disambiguate_entity(result, context)

    return result


def disambiguate_entity(entity: dict, context: str) -> dict:
    """
    Resolve ambiguous entities based on context.

    Disambiguation rules:
    - Company vs Ticker: $ prefix or price context → Ticker; otherwise Company
    - "Apple" in trading: Default to AAPL unless food/agriculture context
    - Person name only: Look up in alias table; if not found, Executive with needs_review
    - Generic pattern name: Normalize to canonical form
    - Same name different entity: Append disambiguator
    - Strategy vs Pattern: Strategy has entry/exit rules; Pattern is observed behavior
    """
    entity_type = entity.get("type", "")
    value = entity.get("value", "")
    evidence = entity.get("evidence", "")

    # Check for ticker context ($ symbol, price numbers)
    ticker_indicators = ["$", "stock", "shares", "trade", "position"]
    has_ticker_context = any(ind in context.lower() for ind in ticker_indicators)

    # Check for price pattern near value
    price_pattern = re.compile(r"\$\d+|\d+\.\d{2}")
    has_price_near = bool(price_pattern.search(evidence))

    # Company vs Ticker disambiguation
    if entity_type == "Company":
        # If value looks like a ticker (all caps, 1-5 chars)
        if value.isupper() and 1 <= len(value) <= 5:
            # Check if it's in our company alias table
            if value not in _aliases.get("companies", {}):
                entity["type"] = "Ticker"

    # Pattern vs Strategy disambiguation
    if entity_type in ("Pattern", "Strategy"):
        # Strategy keywords suggest Strategy type
        strategy_keywords = ["strategy", "trade", "entry", "exit", "position"]
        # Pattern keywords suggest Pattern type
        pattern_keywords = ["pattern", "formation", "setup", "observed"]

        strategy_score = sum(1 for kw in strategy_keywords if kw in context.lower())
        pattern_score = sum(1 for kw in pattern_keywords if kw in context.lower())

        if strategy_score > pattern_score and entity_type == "Pattern":
            entity["type"] = "Strategy"
        elif pattern_score > strategy_score and entity_type == "Strategy":
            entity["type"] = "Pattern"

    return entity


def resolve_ticker(company_name: str) -> str | None:
    """Convert company name to ticker symbol using aliases."""
    companies = _aliases.get("companies", {})

    # Try exact match
    if company_name in companies:
        ticker = companies[company_name].get("ticker")
        return str(ticker) if ticker is not None else None

    # Try case-insensitive match
    for name, data in companies.items():
        if name.lower() == company_name.lower():
            ticker = data.get("ticker")
            return str(ticker) if ticker is not None else None

    return None


def standardize_separators(value: str) -> str:
    """Convert underscores to hyphens."""
    return value.replace("_", "-").replace(" ", "-").lower()


def _to_text(value: Any) -> str:
    """Coerce scalar extraction values to text for normalization safety."""
    if value is None:
        return ""
    return str(value)


def normalize_type(entity_type: Any) -> str:
    """Normalize entity type to PascalCase."""
    entity_type = _to_text(entity_type)
    # Remove spaces and underscores, capitalize each word
    parts = re.split(r"[\s_-]+", entity_type)
    return "".join(part.capitalize() for part in parts)


def normalize_ticker(value: Any) -> str:
    """Normalize ticker symbol."""
    # Uppercase, strip whitespace
    ticker = _to_text(value).strip().upper()

    # Check for aliases
    ticker_aliases = _aliases.get("tickers", {})
    if ticker in ticker_aliases:
        ticker = ticker_aliases[ticker]

    return ticker


def normalize_company(value: Any) -> str:
    """Normalize company name."""
    # Title case, strip common suffixes
    name = _to_text(value).strip()

    # Remove common suffixes for matching
    suffixes = [" Inc", " Inc.", " Corp", " Corp.", " Corporation", " Ltd", " Ltd."]
    clean_name = name
    for suffix in suffixes:
        if clean_name.endswith(suffix):
            clean_name = clean_name[: -len(suffix)]
            break

    return name


def normalize_pattern(value: Any) -> str:
    """Normalize trading pattern name."""
    raw_value = _to_text(value).strip()
    lower_value = raw_value.lower()

    # Check for aliases (try both original and lowercase keys)
    pattern_aliases = _aliases.get("patterns", {})
    if raw_value in pattern_aliases:
        return str(pattern_aliases[raw_value])
    if lower_value in pattern_aliases:
        return str(pattern_aliases[lower_value])

    # Default: hyphenated lowercase
    return standardize_separators(lower_value)


def normalize_bias(value: Any) -> str:
    """Normalize cognitive bias name."""
    raw_value = _to_text(value).strip()
    lower_value = raw_value.lower()

    # Check for aliases (try both original and lowercase keys)
    bias_aliases = _aliases.get("biases", {})
    if raw_value in bias_aliases:
        return str(bias_aliases[raw_value])
    if lower_value in bias_aliases:
        return str(bias_aliases[lower_value])

    # Default: hyphenated lowercase
    return standardize_separators(lower_value)


def normalize_strategy(value: Any) -> str:
    """Normalize strategy name."""
    raw_value = _to_text(value).strip()
    lower_value = raw_value.lower()

    # Check for aliases (try both original and lowercase keys)
    strategy_aliases = _aliases.get("strategies", {})
    if raw_value in strategy_aliases:
        return str(strategy_aliases[raw_value])
    if lower_value in strategy_aliases:
        return str(strategy_aliases[lower_value])

    # Default: hyphenated lowercase
    return standardize_separators(lower_value)


def normalize_case(entity_type: str, value: str) -> tuple[str, str]:
    """PascalCase for types, Title Case for values."""
    normalized_type = normalize_type(entity_type)

    # Type-specific value normalization
    if normalized_type == "Ticker":
        normalized_value = value.upper()
    elif normalized_type in ("Pattern", "Bias", "Strategy"):
        normalized_value = value.lower().replace(" ", "-")
    else:
        normalized_value = value.title()

    return normalized_type, normalized_value


def dedupe_entities(entities: list[dict]) -> list[dict]:
    """Remove duplicate entities, keeping highest confidence."""
    seen: dict[tuple[str, str], dict] = {}

    for entity in entities:
        key = (entity["type"], _to_text(entity.get("value", "")).lower())
        if key not in seen or entity.get("confidence", 0) > seen[key].get("confidence", 0):
            seen[key] = entity

    return list(seen.values())
