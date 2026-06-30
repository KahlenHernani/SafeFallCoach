"""
LLM Provider Interface — Re-export shim.

All implementations now live in the top-level llm_providers/ package.
This file re-exports them for backward compatibility so existing imports
like `from .llm_provider import OvisProvider` continue to work.
"""

from llm_providers import (
    LLMFeedbackResult,
    LLMProvider,
    OvisProvider,
)

__all__ = ['LLMProvider', 'LLMFeedbackResult', 'OvisProvider']
