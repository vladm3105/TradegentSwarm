"""Conversation context management for follow-up questions."""
import re
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
from typing import Any

from .intent_classifier import Intent, ClassificationResult


@dataclass
class Message:
    """A single message in the conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    intent: Intent | None = None
    tickers: list[str] = field(default_factory=list)
    tool_results: dict[str, Any] | None = None
    a2ui_components: list[dict] | None = None


@dataclass
class ConversationContext:
    """Maintains conversation state for follow-up questions.

    Tracks:
    - Current and recent tickers mentioned
    - Last intent for context
    - Last tool results for reference
    - Message history for context window
    """

    session_id: str
    current_ticker: str | None = None
    recent_tickers: deque = field(default_factory=lambda: deque(maxlen=10))
    last_intent: Intent | None = None
    last_tool_results: dict[str, Any] | None = None
    messages: list[Message] = field(default_factory=list)
    max_messages: int = 50
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def add_message(
        self,
        role: str,
        content: str,
        intent: Intent | None = None,
        tickers: list[str] | None = None,
        tool_results: dict[str, Any] | None = None,
        a2ui_components: list[dict] | None = None,
    ):
        """Add a message to the conversation history.

        Args:
            role: "user" or "assistant"
            content: Message content
            intent: Classified intent (for user messages)
            tickers: Tickers mentioned
            tool_results: Results from tool calls
            a2ui_components: A2UI components generated
        """
        message = Message(
            role=role,
            content=content,
            intent=intent,
            tickers=tickers or [],
            tool_results=tool_results,
            a2ui_components=a2ui_components,
        )
        self.messages.append(message)

        # Trim old messages
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

        self.updated_at = datetime.utcnow()

    def update_from_classification(
        self, result: ClassificationResult, tool_results: dict[str, Any] | None = None
    ):
        """Update context after processing a query.

        Args:
            result: Intent classification result
            tool_results: Results from tool execution
        """
        # Update ticker tracking
        if result.tickers:
            self.current_ticker = result.tickers[0]
            for t in result.tickers:
                if t not in self.recent_tickers:
                    self.recent_tickers.append(t)

        # Update intent
        self.last_intent = result.intent

        # Store tool results
        if tool_results:
            self.last_tool_results = tool_results

        self.updated_at = datetime.utcnow()

    def resolve_pronouns(self, query: str) -> str:
        """Replace pronouns with actual ticker references.

        Handles: it, that stock, the stock, this one, that one

        Args:
            query: User query with potential pronouns

        Returns:
            Query with pronouns replaced by current ticker
        """
        if not self.current_ticker:
            return query

        # Patterns to replace
        replacements = [
            (r"\bit\b", self.current_ticker),
            (r"\bthat stock\b", self.current_ticker),
            (r"\bthe stock\b", self.current_ticker),
            (r"\bthis one\b", self.current_ticker),
            (r"\bthat one\b", self.current_ticker),
            (r"\bthis ticker\b", self.current_ticker),
            (r"\bthat ticker\b", self.current_ticker),
            (r"\bsame stock\b", self.current_ticker),
            (r"\bsame ticker\b", self.current_ticker),
        ]

        result = query
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        return result

    def get_context_summary(self) -> str:
        """Get a summary of the current context for LLM prompts.

        Returns:
            Summary string with current state
        """
        parts = []

        if self.current_ticker:
            parts.append(f"Current ticker: {self.current_ticker}")

        if self.recent_tickers:
            recent = list(self.recent_tickers)[-5:]
            if recent:
                parts.append(f"Recent tickers: {', '.join(recent)}")

        if self.last_intent:
            parts.append(f"Last intent: {self.last_intent.value}")

        if self.last_tool_results:
            # Summarize tool results
            tools_used = list(self.last_tool_results.keys())
            parts.append(f"Last tools used: {', '.join(tools_used)}")

        return "\n".join(parts) if parts else "No previous context"

    def get_recent_messages(self, n: int = 5) -> list[dict]:
        """Get recent messages for LLM context.

        Args:
            n: Number of recent messages to return

        Returns:
            List of message dicts with role and content
        """
        recent = self.messages[-n:] if len(self.messages) > n else self.messages
        return [{"role": msg.role, "content": msg.content} for msg in recent]

    def clear(self):
        """Clear conversation context."""
        self.current_ticker = None
        self.recent_tickers.clear()
        self.last_intent = None
        self.last_tool_results = None
        self.messages.clear()
        self.updated_at = datetime.utcnow()


class ContextStore:
    """Store for managing multiple conversation contexts by session."""

    def __init__(self):
        self._contexts: dict[str, ConversationContext] = {}

    def get(self, session_id: str) -> ConversationContext:
        """Get or create context for a session.

        Args:
            session_id: Unique session identifier

        Returns:
            ConversationContext for the session
        """
        if session_id not in self._contexts:
            self._contexts[session_id] = ConversationContext(session_id=session_id)
        return self._contexts[session_id]

    def delete(self, session_id: str):
        """Delete context for a session.

        Args:
            session_id: Session to delete
        """
        self._contexts.pop(session_id, None)

    def cleanup_stale(self, max_age_hours: int = 24):
        """Remove stale contexts older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours before cleanup
        """
        now = datetime.utcnow()
        stale = []

        for session_id, context in self._contexts.items():
            age = (now - context.updated_at).total_seconds() / 3600
            if age > max_age_hours:
                stale.append(session_id)

        for session_id in stale:
            del self._contexts[session_id]


# Global context store
context_store = ContextStore()
