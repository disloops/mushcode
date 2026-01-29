#!/usr/bin/env python

# MIT License
# Copyright (c) 2026 Matt Westfall (@disloops)

"""
OpenAI provider implementation using the modern Responses API.

This uses the new Responses API (client.responses.create) which is OpenAI's
recommended approach for new projects. It supports both standard and reasoning
models with a cleaner interface.
"""

import os
import logging
from typing import List, Dict, Optional

from .base import BaseLLMProvider, CompletionResult, FinishReason

logger = logging.getLogger('mush_gpt.providers.openai')


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI API provider implementation using the Responses API.

    Uses the modern OpenAI Responses API which provides:
    - Cleaner separation of instructions vs input
    - Better support for reasoning models (o3, gpt-5)
    - Simplified response handling via output_text
    """

    # Map Responses API status to our normalized enum
    STATUS_MAP = {
        'completed': FinishReason.STOP,
        'incomplete': FinishReason.LENGTH,
        'failed': FinishReason.ERROR,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        Initialize the OpenAI provider.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model to use (defaults to OPENAI_MODEL env var, required)
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model or os.getenv('OPENAI_MODEL')

        if not self.api_key:
            raise ValueError("OpenAI API key not provided and OPENAI_API_KEY not set")

        if not self.model:
            raise ValueError("OpenAI model not provided and OPENAI_MODEL not set")

        # Import and initialize client
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
            logger.info(f"OpenAI provider initialized with model: {self.model}")
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

    @property
    def provider_name(self) -> str:
        return "openai"

    def complete(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> CompletionResult:
        """
        Generate a completion using OpenAI's Responses API.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            system_prompt: Optional system prompt (passed as instructions).
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            **kwargs: Additional arguments passed to the API.

        Returns:
            CompletionResult with the generated content.
        """
        try:
            # Validate max_tokens is provided (required by config)
            if max_tokens is None:
                raise ValueError("max_tokens is required")

            # Build input for Responses API
            # Convert messages to the format expected by Responses API
            api_input = []
            for msg in messages:
                role = msg["role"]
                # Map 'assistant' to 'assistant' and 'user' to 'user'
                # Map 'system' to 'developer' (higher priority in Responses API)
                if role == "system":
                    role = "developer"
                api_input.append({
                    "role": role,
                    "content": msg["content"]
                })

            # If no messages, provide a minimal input
            if not api_input:
                api_input = "Please respond according to your instructions."

            # Build API call parameters
            api_params = {
                "model": self.model,
                "input": api_input,
                "max_output_tokens": max_tokens,
            }

            # Add instructions (system prompt) if provided
            if system_prompt:
                api_params["instructions"] = system_prompt

            # Add temperature (note: some reasoning models may ignore this)
            if temperature != 1.0:
                api_params["temperature"] = temperature

            # Make API call using Responses API
            response = self.client.responses.create(**api_params)

            # Extract content using output_text convenience property
            # (aggregates all text from output[].content[] where type="output_text")
            content = response.output_text or ""

            # Determine finish reason from response status
            raw_status = getattr(response, 'status', 'completed')
            finish_reason = self.STATUS_MAP.get(
                raw_status,
                FinishReason.STOP
            )

            # If completed but empty content, may indicate content filtering
            if raw_status == 'completed' and not content.strip():
                # Check if there's any output at all - if output exists but
                # no text, something filtered it
                if hasattr(response, 'output') and response.output:
                    finish_reason = FinishReason.CONTENT_FILTER

            logger.debug(f"OpenAI completion: {len(content)} chars, status: {raw_status}")

            return CompletionResult(
                content=content,
                finish_reason=finish_reason,
                raw_response=response
            )

        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return CompletionResult(
                content="",
                finish_reason=FinishReason.ERROR,
                error=str(e)
            )

