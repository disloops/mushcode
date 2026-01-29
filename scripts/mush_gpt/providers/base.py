#!/usr/bin/env python

# MIT License
# Copyright (c) 2026 Matt Westfall (@disloops)

"""
Base classes for LLM provider abstraction.

This module defines the common interface that all LLM providers must implement,
allowing easy switching between providers (OpenAI, Gemini, etc.) via configuration.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum


class FinishReason(Enum):
    """Normalized finish reasons across all providers."""
    STOP = "stop"              # Normal completion
    LENGTH = "length"          # Hit max tokens
    CONTENT_FILTER = "content_filter"  # Safety/content filter triggered
    ERROR = "error"            # An error occurred
    UNKNOWN = "unknown"        # Unknown/unmapped reason


@dataclass
class CompletionResult:
    """
    Standardized result from an LLM completion.

    Attributes:
        content: The generated text content
        finish_reason: Normalized reason for completion ending
        raw_response: Original provider response (for debugging)
        error: Error message if finish_reason is ERROR
    """
    content: str
    finish_reason: FinishReason
    raw_response: Any = None
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """Check if completion was successful."""
        return self.finish_reason == FinishReason.STOP

    @property
    def is_filtered(self) -> bool:
        """Check if content was filtered."""
        return self.finish_reason == FinishReason.CONTENT_FILTER

    @property
    def is_truncated(self) -> bool:
        """Check if content was truncated due to length."""
        return self.finish_reason == FinishReason.LENGTH


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All provider implementations must inherit from this class and implement
    the complete() method.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this provider (e.g., 'openai', 'gemini')."""
        pass

    @abstractmethod
    def complete(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> CompletionResult:
        """
        Generate a completion from the given messages.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
                     Roles should be 'user' or 'assistant'.
            system_prompt: Optional system prompt to set context/behavior.
            temperature: Sampling temperature (0.0 to 2.0, default 1.0).
            max_tokens: Maximum tokens to generate (required).
            **kwargs: Provider-specific additional arguments.

        Returns:
            CompletionResult with the generated content and metadata.

        Example:
            result = provider.complete(
                messages=[{"role": "user", "content": "Hello!"}],
                system_prompt="You are a helpful assistant.",
                temperature=0.7,
                max_tokens=1000
            )
            if result.is_success:
                print(result.content)
        """
        pass

    def validate_messages(self, messages: List[Dict[str, str]]) -> bool:
        """
        Validate message format.

        Args:
            messages: List of message dicts to validate.

        Returns:
            True if valid, False otherwise.
        """
        if not messages:
            return True  # Empty messages list is valid

        valid_roles = {'user', 'assistant', 'system'}
        for msg in messages:
            if not isinstance(msg, dict):
                return False
            if 'role' not in msg or 'content' not in msg:
                return False
            if msg['role'] not in valid_roles:
                return False

        return True

