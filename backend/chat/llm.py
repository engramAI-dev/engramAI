"""Single abstraction layer for all LLM calls.

All code that needs to call the Anthropic API MUST go through this module.
Never import anthropic directly in routes or other modules.
"""
