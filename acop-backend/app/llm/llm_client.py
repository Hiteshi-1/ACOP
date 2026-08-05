"""
LLM provider facade. The rest of the app (agents, chat route) imports
`llm_client` from here and never needs to know whether Gemini or Claude
is active — swap providers by changing LLM_PROVIDER in .env, nothing else.
"""
from app.config import settings
from app.core.logging_config import logger

if settings.LLM_PROVIDER == "anthropic":
    from app.llm.claude_client import claude_client as llm_client
    logger.info("LLM provider: Anthropic Claude")
else:
    from app.llm.gemini_client import gemini_client as llm_client
    logger.info("LLM provider: Google Gemini (free tier)")

__all__ = ["llm_client"]
