"""Import the pinned framework without its examples loading an implicit .env."""

import os

_previous = os.environ.get("PYTHON_DOTENV_DISABLED")
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
try:
    from hello_agents import Config, HelloAgentsLLM, Message
    from hello_agents.context import ContextBuilder, ContextConfig
    from hello_agents.context.builder import ContextPacket
    from hello_agents.core import Agent
    from hello_agents.tools import Tool, ToolParameter, ToolRegistry
finally:
    if _previous is None:
        os.environ.pop("PYTHON_DOTENV_DISABLED", None)
    else:
        os.environ["PYTHON_DOTENV_DISABLED"] = _previous

__all__ = [
    "Config",
    "HelloAgentsLLM",
    "Message",
    "ContextBuilder",
    "ContextConfig",
    "ContextPacket",
    "Agent",
    "Tool",
    "ToolParameter",
    "ToolRegistry",
]
