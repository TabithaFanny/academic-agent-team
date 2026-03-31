"""Built-in model client implementations."""

from academic_agent_team.core.clients.anthropic_client import AnthropicClient
from academic_agent_team.core.clients.deepseek_client import DeepSeekClient
from academic_agent_team.core.clients.minimax_client import MiniMaxClient
from academic_agent_team.core.clients.mock_client import MockClient
from academic_agent_team.core.clients.ollama_client import OllamaClient
from academic_agent_team.core.clients.openai_client import OpenAIClient
from academic_agent_team.core.clients.zhipu_client import ZhipuClient

__all__ = [
    "AnthropicClient",
    "DeepSeekClient",
    "MiniMaxClient",
    "MockClient",
    "OllamaClient",
    "OpenAIClient",
    "ZhipuClient",
]
