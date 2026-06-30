"""
LLM Providers — Shared package for all LLM backends.

Used by both active_learning_engine/ and skeletal_overlay/.

Usage:
    from llm_providers import OvisProvider
"""

from .base import LLMFeedbackResult, LLMProvider
from .ovis import OvisProvider

__all__ = ['LLMProvider', 'LLMFeedbackResult', 'OvisProvider']
