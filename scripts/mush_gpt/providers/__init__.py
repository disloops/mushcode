#!/usr/bin/env python

# MIT License
# Copyright (c) 2026 Matt Westfall (@disloops)

"""
LLM Provider abstraction layer.

This module provides a unified interface for different LLM providers,
allowing easy switching between OpenAI, Gemini, and potentially others
via environment configuration.

Usage:
    from providers import get_provider

    provider = get_provider()  # Returns configured provider
    result = provider.complete(
        messages=[{"role": "user", "content": "Hello!"}],
        system_prompt="You are helpful.",
        temperature=0.7,
        max_tokens=1000
    )

    if result.is_success:
        print(result.content)
"""

import os
import logging
from typing import Dict, Optional

from .base import BaseLLMProvider, CompletionResult, FinishReason

logger = logging.getLogger('mush_gpt.providers')

VALID_LLM_PROVIDERS = ('openai', 'gemini')

# Default provider (LLM_PROVIDER) and named instances for reuse across endpoints
_provider_instance: Optional[BaseLLMProvider] = None
_named_instances: Dict[str, BaseLLMProvider] = {}


def get_provider(
    provider_name: Optional[str] = None,
    force_new: bool = False
) -> BaseLLMProvider:
    """
    Get the configured LLM provider.

    Args:
        provider_name: Override provider selection ('openai' or 'gemini').
                      If not specified, uses LLM_PROVIDER env var.
        force_new: If True, create a new instance without caching.

    Returns:
        Configured LLM provider instance.

    Raises:
        ValueError: If provider is not recognized or misconfigured.
    """
    global _provider_instance

    provider = (provider_name or os.getenv('LLM_PROVIDER', '')).lower().strip()

    if not provider:
        raise ValueError(
            "LLM_PROVIDER environment variable is required. "
            "Set to 'openai' or 'gemini' in your mush_gpt.env file."
        )

    if provider not in VALID_LLM_PROVIDERS:
        raise ValueError(
            f"Unknown LLM provider: '{provider}'. "
            f"Valid options: {', '.join(VALID_LLM_PROVIDERS)}"
        )

    if not force_new:
        if provider_name is None and _provider_instance is not None:
            return _provider_instance
        cached = _named_instances.get(provider)
        if cached is not None:
            return cached

    logger.info(f"Initializing LLM provider: {provider}")

    if provider == 'openai':
        from .openai_provider import OpenAIProvider
        new_instance = OpenAIProvider()

    elif provider == 'gemini':
        from .gemini_provider import GeminiProvider
        new_instance = GeminiProvider()

    if not force_new:
        _named_instances[provider] = new_instance
        if provider_name is None:
            _provider_instance = new_instance

    return new_instance


def reset_provider():
    """Reset cached provider instances. Useful for testing or reconfiguration."""
    global _provider_instance, _named_instances
    _provider_instance = None
    _named_instances.clear()


# Export commonly used classes
__all__ = [
    'get_provider',
    'reset_provider',
    'VALID_LLM_PROVIDERS',
    'BaseLLMProvider',
    'CompletionResult',
    'FinishReason',
]
