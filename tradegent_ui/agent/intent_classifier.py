"""Intent classification for user queries."""
import re
from enum import Enum
from dataclasses import dataclass, field


class Intent(Enum):
    """Supported user intents."""

    ANALYSIS = "analysis"
    TRADE = "trade"
    PORTFOLIO = "portfolio"
    RESEARCH = "research"
    SYSTEM = "system"  # Health, status, help
    UNKNOWN = "unknown"


# Intent patterns - keywords that indicate each intent
INTENT_PATTERNS: dict[Intent, list[str]] = {
    Intent.ANALYSIS: [
        "analyze",
        "analysis",
        "run analysis",
        "check",
        "evaluate",
        "forecast",
        "validate",
        "compare analyses",
        "gate result",
        "do nothing gate",
        "expected value",
        "recommendation",
    ],
    Intent.TRADE: [
        "buy",
        "sell",
        "bought",
        "sold",
        "journal",
        "execute",
        "order",
        "place order",
        "trade",
        "entry",
        "exit",
        "position entry",
        "close position",
        "stop loss",
        "take profit",
    ],
    Intent.PORTFOLIO: [
        "positions",
        "pnl",
        "p&l",
        "profit",
        "loss",
        "account",
        "watchlist",
        "open orders",
        "portfolio",
        "holdings",
        "balance",
        "margin",
        "buying power",
        "show my",
        "what do i own",
        "what am i holding",
    ],
    Intent.RESEARCH: [
        "search",
        "find",
        "what do you know",
        "context",
        "peers",
        "sector",
        "competitors",
        "news",
        "profile",
        "history",
        "tell me about",
        "information on",
        "look up",
        "research",
    ],
    Intent.SYSTEM: [
        "health",
        "status",
        "help",
        "ping",
        "version",
        "connected",
        "restart",
    ],
}

# Ticker pattern: 1-5 uppercase letters
TICKER_PATTERN = re.compile(r"\b([A-Z]{1,5})\b")

# Common words to exclude from ticker detection
TICKER_EXCLUSIONS = {
    "I",
    "A",
    "AN",
    "THE",
    "AND",
    "OR",
    "BUT",
    "FOR",
    "TO",
    "IN",
    "ON",
    "AT",
    "BY",
    "IS",
    "IT",
    "MY",
    "ME",
    "DO",
    "IF",
    "SO",
    "UP",
    "AM",
    "PM",
    "US",
    "UK",
    "EU",
    "CEO",
    "CFO",
    "COO",
    "CTO",
    "IPO",
    "ETF",
    "NYSE",
    "NASDAQ",
    "SEC",
    "FDA",
    "GDP",
    "CPI",
    "API",
    "USD",
    "EUR",
    "GBP",
    "BUY",
    "SELL",
    "HOLD",
    "LONG",
    "SHORT",
    "PUT",
    "CALL",
}


@dataclass
class ClassificationResult:
    """Result of intent classification."""

    intent: Intent
    confidence: float  # 0-1
    tickers: list[str] = field(default_factory=list)
    requires_clarification: bool = False
    original_query: str = ""
    matched_patterns: list[str] = field(default_factory=list)

    def is_confident(self) -> bool:
        """Return True if classification is confident enough to proceed."""
        return self.confidence >= 0.6 and not self.requires_clarification


def extract_tickers(query: str) -> list[str]:
    """Extract potential stock tickers from query.

    Args:
        query: User query

    Returns:
        List of potential tickers (deduplicated, ordered by appearance)
    """
    matches = TICKER_PATTERN.findall(query)
    tickers = []
    seen = set()

    for match in matches:
        if match not in TICKER_EXCLUSIONS and match not in seen:
            tickers.append(match)
            seen.add(match)

    return tickers


def classify_intent(query: str) -> ClassificationResult:
    """Classify user intent from query.

    Uses keyword matching with confidence scoring.
    Falls back to UNKNOWN if no patterns match.

    Args:
        query: User query string

    Returns:
        ClassificationResult with intent, confidence, and extracted tickers
    """
    query_lower = query.lower()
    tickers = extract_tickers(query)

    # Score each intent based on pattern matches
    scores: dict[Intent, tuple[int, list[str]]] = {}

    for intent, patterns in INTENT_PATTERNS.items():
        matched = []
        for pattern in patterns:
            if pattern in query_lower:
                matched.append(pattern)
        scores[intent] = (len(matched), matched)

    # Find best intent
    best_intent = Intent.UNKNOWN
    best_score = 0
    best_patterns: list[str] = []

    for intent, (score, patterns) in scores.items():
        if score > best_score:
            best_intent = intent
            best_score = score
            best_patterns = patterns

    # Calculate confidence
    total_matches = sum(score for score, _ in scores.values())

    if total_matches == 0:
        return ClassificationResult(
            intent=Intent.UNKNOWN,
            confidence=0.0,
            tickers=tickers,
            requires_clarification=True,
            original_query=query,
        )

    confidence = best_score / max(total_matches, 1)

    # Boost confidence if only one intent matched
    if sum(1 for score, _ in scores.values() if score > 0) == 1:
        confidence = min(confidence + 0.2, 1.0)

    # Require clarification if low confidence
    requires_clarification = confidence < 0.6

    return ClassificationResult(
        intent=best_intent,
        confidence=confidence,
        tickers=tickers,
        requires_clarification=requires_clarification,
        original_query=query,
        matched_patterns=best_patterns,
    )


def detect_multi_intent(query: str) -> list[ClassificationResult]:
    """Detect multiple intents in a single query.

    Splits query on conjunctions and classifies each part.

    Args:
        query: User query that may contain multiple intents

    Returns:
        List of ClassificationResult, one per detected intent
    """
    # Split on common conjunctions
    parts = re.split(r"\s+and\s+|\s+also\s+|\s+then\s+|\s*,\s*", query, flags=re.IGNORECASE)

    results = []
    seen_intents = set()

    for part in parts:
        part = part.strip()
        if not part:
            continue

        result = classify_intent(part)

        # Skip duplicates and unknowns
        if result.intent != Intent.UNKNOWN and result.intent not in seen_intents:
            results.append(result)
            seen_intents.add(result.intent)

    # If no valid intents found, classify the whole query
    if not results:
        results = [classify_intent(query)]

    return results


def get_clarification_prompt(result: ClassificationResult) -> str:
    """Generate a clarification prompt for ambiguous queries.

    Args:
        result: Classification result requiring clarification

    Returns:
        Prompt string to ask user for clarification
    """
    if result.intent == Intent.UNKNOWN:
        return (
            "I'm not sure what you'd like me to do. Would you like to:\n"
            "- **Analyze** a stock (e.g., 'analyze NVDA')\n"
            "- **View portfolio** (e.g., 'show my positions')\n"
            "- **Research** a topic (e.g., 'what do you know about ZIM')\n"
            "- **Trade** (e.g., 'I bought AAPL at $150')"
        )

    ticker_hint = f" for {result.tickers[0]}" if result.tickers else ""

    prompts = {
        Intent.ANALYSIS: f"Would you like me to run an analysis{ticker_hint}?",
        Intent.TRADE: f"Would you like to log a trade{ticker_hint} or place an order?",
        Intent.PORTFOLIO: "Would you like to see your positions, P&L, or watchlist?",
        Intent.RESEARCH: f"What would you like to know about{ticker_hint or ' this topic'}?",
    }

    return prompts.get(result.intent, "Could you please clarify your request?")
