#!/usr/bin/env python

# MIT License
# Copyright (c) 2026 Matt Westfall (@disloops)

"""
Google Gemini provider implementation using the google-genai SDK.

This uses the new unified Google Gen AI SDK (google-genai), not the legacy
google-generativeai package. Install via: pip install google-genai

The new SDK provides a cleaner API where system instructions are passed
per-request rather than at model instantiation time.
"""

import os
import logging
from typing import List, Dict, Optional, Any

from .base import BaseLLMProvider, CompletionResult, FinishReason

logger = logging.getLogger('mush_gpt.providers.gemini')


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini API provider implementation.

    Uses the google-genai SDK (the new unified SDK, not the legacy
    google-generativeai package) to communicate with Gemini's API.
    """

    # Map Gemini finish reasons to our normalized enum
    # The SDK returns these as enum members with .name attribute
    FINISH_REASON_MAP = {
        'STOP': FinishReason.STOP,
        'MAX_TOKENS': FinishReason.LENGTH,
        'SAFETY': FinishReason.CONTENT_FILTER,
        'RECITATION': FinishReason.CONTENT_FILTER,
        'BLOCKLIST': FinishReason.CONTENT_FILTER,
        'PROHIBITED_CONTENT': FinishReason.CONTENT_FILTER,
        'SPII': FinishReason.CONTENT_FILTER,
        'OTHER': FinishReason.UNKNOWN,
        'FINISH_REASON_UNSPECIFIED': FinishReason.UNKNOWN,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        Initialize the Gemini provider.

        Args:
            api_key: Google API key (defaults to GOOGLE_API_KEY env var)
            model: Model to use (defaults to GEMINI_MODEL env var, required)
        """
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        self.model_name = model or os.getenv('GEMINI_MODEL')

        if not self.api_key:
            raise ValueError("Google API key not provided and GOOGLE_API_KEY not set")

        if not self.model_name:
            raise ValueError("Gemini model not provided and GEMINI_MODEL not set")

        # Import and initialize the new google-genai SDK
        try:
            from google import genai
            from google.genai import types
            self._client = genai.Client(api_key=self.api_key)
            self._types = types
            logger.info(f"Gemini provider initialized with model: {self.model_name}")
        except ImportError:
            raise ImportError(
                "google-genai package not installed. "
                "Run: pip install google-genai"
            )

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _convert_messages_to_gemini(
        self,
        messages: List[Dict[str, str]]
    ) -> List[Any]:
        """
        Convert OpenAI-style messages to Gemini Content format.

        OpenAI: {"role": "user/assistant", "content": "..."}
        Gemini: Content(role="user/model", parts=[Part(text="...")])
        """
        from google.genai import types

        gemini_contents = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            # Skip system messages (handled via system_instruction config)
            if role == "system":
                continue

            # Map assistant -> model (Gemini's terminology)
            if role == "assistant":
                role = "model"

            # Preprocess user input to handle Gemini quirks
            if role == "user":
                content = self._preprocess_input(content)

            gemini_contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=content)]
                )
            )

        return gemini_contents

    def _preprocess_input(self, content: str) -> str:
        """
        Preprocess user input to handle Gemini-specific quirks.
        
        Gemini interprets '...' as a continuation signal, which causes
        it to refuse processing. Strip ellipsis from start of content
        and from start of quoted speech within content.
        """
        if not content:
            return content
        
        # Strip leading ellipsis from start of content
        content = content.lstrip()
        if content.startswith('...'):
            content = content[3:].lstrip()
        
        # Strip ellipsis from start of quoted speech (e.g., 'says, "...')
        content = content.replace('says, "...', 'says, "')
        content = content.replace("says, '...", "says, '")
        content = content.replace('"...', '"')
        
        return content

    def _clean_response(self, content: str) -> str:
        """
        Clean up Gemini-specific response formatting quirks.
        
        Gemini has some output patterns that differ from OpenAI:
        - Sometimes adds trailing newline before closing quote: "text\n"
        - Sometimes wraps entire response in quotes: "response"
        
        This method normalizes these to match OpenAI's cleaner output.
        """
        if not content:
            return content
        
        # Normalize line endings
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove trailing quote on its own line (pattern: text\n")
        if content.endswith('\n"') or content.endswith("\n'"):
            content = content[:-2]
        
        # Strip whitespace
        content = content.strip()
        
        # Remove wrapping quotes if Gemini added them
        if len(content) >= 2:
            if (content.startswith('"') and content.endswith('"')) or \
               (content.startswith("'") and content.endswith("'")):
                content = content[1:-1].strip()
        
        return content

    def _build_safety_settings(self) -> List[Any]:
        """
        Build safety settings for the request.

        Maximally permissive settings - only blocking the most extreme content.
        We don't enforce morality, kindness, or quality - only legal compliance.
        """
        from google.genai import types

        return [
            # Don't block harassment - roleplay may involve conflict
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="BLOCK_NONE"
            ),
            # Don't block hate speech - characters may have flaws
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="BLOCK_NONE"
            ),
            # Only block the most extreme sexual content
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="BLOCK_ONLY_HIGH"
            ),
            # Only block extreme violence/dangerous content
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_ONLY_HIGH"
            ),
        ]

    def complete(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> CompletionResult:
        """
        Generate a completion using Gemini's API.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            system_prompt: Optional system prompt (passed as system_instruction).
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            **kwargs: Additional arguments (currently unused).

        Returns:
            CompletionResult with the generated content.
        """
        try:
            # Validate max_tokens is provided (required by config)
            if max_tokens is None:
                raise ValueError("max_tokens is required")

            # Build generation config
            config = self._types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                top_p=1.0,
                safety_settings=self._build_safety_settings(),
            )

            # Add system instruction if provided
            if system_prompt:
                config.system_instruction = system_prompt

            # Convert messages to Gemini format
            gemini_contents = self._convert_messages_to_gemini(messages)

            # Handle empty messages case (e.g., /cmd endpoint)
            # Gemini requires at least one content item
            if not gemini_contents:
                gemini_contents = [
                    self._types.Content(
                        role="user",
                        parts=[self._types.Part(text="Please respond according to your instructions.")]
                    )
                ]

            # Make API call
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=gemini_contents,
                config=config
            )

            # Extract content
            try:
                content = response.text
            except (ValueError, AttributeError):
                # response.text raises ValueError if blocked or no content
                content = ""

            # Apply Gemini-specific cleanup
            content = self._clean_response(content)

            # Get finish reason
            raw_reason = "STOP"  # Default
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    finish_reason_val = candidate.finish_reason
                    # Handle both enum and string representations
                    if hasattr(finish_reason_val, 'name'):
                        raw_reason = finish_reason_val.name
                    else:
                        raw_reason = str(finish_reason_val)
            elif not content:
                # No candidates and no content usually means blocked
                raw_reason = "SAFETY"

            finish_reason = self.FINISH_REASON_MAP.get(
                raw_reason,
                FinishReason.UNKNOWN
            )

            logger.debug(f"Gemini completion: {len(content)} chars, reason: {raw_reason}")

            return CompletionResult(
                content=content,
                finish_reason=finish_reason,
                raw_response=response
            )

        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            return CompletionResult(
                content="",
                finish_reason=FinishReason.ERROR,
                error=str(e)
            )
