"""Tests for intent classification."""
from tradegent_ui.agent.intent_classifier import (
    Intent,
    classify_intent,
    detect_multi_intent,
    extract_tickers,
)


class TestExtractTickers:
    """Tests for ticker extraction."""

    def test_extract_single_ticker(self):
        assert extract_tickers("Analyze NVDA") == ["NVDA"]

    def test_extract_multiple_tickers(self):
        assert extract_tickers("Compare NVDA and AAPL") == ["NVDA", "AAPL"]

    def test_exclude_common_words(self):
        tickers = extract_tickers("I want to BUY NVDA")
        assert "I" not in tickers
        assert "BUY" not in tickers
        assert "NVDA" in tickers

    def test_no_tickers(self):
        assert extract_tickers("show my positions") == []

    def test_extract_ticker_from_count_follow_up(self):
        assert extract_tickers("how many nvda only?") == ["NVDA"]


class TestClassifyIntent:
    """Tests for intent classification."""

    def test_analysis_intent(self):
        result = classify_intent("analyze NVDA")
        assert result.intent == Intent.ANALYSIS
        assert result.confidence > 0.5
        assert "NVDA" in result.tickers

    def test_portfolio_intent(self):
        result = classify_intent("show my positions")
        assert result.intent == Intent.PORTFOLIO
        assert result.confidence > 0.5

    def test_trade_intent(self):
        result = classify_intent("I bought AAPL at $150")
        assert result.intent == Intent.TRADE
        assert "AAPL" in result.tickers

    def test_research_intent(self):
        result = classify_intent("what do you know about ZIM")
        assert result.intent == Intent.RESEARCH
        assert "ZIM" in result.tickers

    def test_unknown_intent(self):
        result = classify_intent("blah blah xyz nonsense query")
        assert result.intent == Intent.UNKNOWN or result.requires_clarification

    def test_system_intent(self):
        result = classify_intent("system health status")
        assert result.intent == Intent.SYSTEM

    def test_system_count_follow_up_intent(self):
        result = classify_intent("how many nvda only?")
        assert result.intent == Intent.SYSTEM
        assert "NVDA" in result.tickers

    def test_analysis_intent_with_recommendation_typo(self):
        result = classify_intent("what is average recomendation for nvda?")
        assert result.intent == Intent.ANALYSIS
        assert "NVDA" in result.tickers

    def test_system_intent_for_schedule_command(self):
        result = classify_intent("disable schedule 3")
        assert result.intent == Intent.SYSTEM


class TestMultiIntent:
    """Tests for multi-intent detection."""

    def test_single_intent(self):
        results = detect_multi_intent("analyze NVDA")
        assert len(results) == 1
        assert results[0].intent == Intent.ANALYSIS

    def test_multi_intent_and(self):
        results = detect_multi_intent("analyze NVDA and show my positions")
        assert len(results) == 2
        intents = {r.intent for r in results}
        assert Intent.ANALYSIS in intents
        assert Intent.PORTFOLIO in intents

    def test_multi_intent_comma(self):
        results = detect_multi_intent("show positions, analyze AAPL")
        assert len(results) >= 1  # At least one should be detected
