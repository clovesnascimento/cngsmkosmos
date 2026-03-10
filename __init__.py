# KOSMOS Agent Package
"""Motor cognitivo KOSMOS com Firecracker MicroVM Sandbox + DeepSeek LLM."""

from .main import KosmosEngine
from .microvm_sandbox import MicroVMSandbox, MicroVMPool
from .microvm_config import MicroVMConfig
from .tool_router import ToolRouter
from .planner_tot import ToTPlanner
from .agents import ProposerAgent, ReviewerAgent
from .reflexion import Reflexion
from .memory import EpisodicMemory
from .jupyter_executor import JupyterExecutor
from .llm_client import DeepSeekClient, LLMConfig, get_llm_client, set_api_key

__version__ = "2.0.0"
__all__ = [
    "KosmosEngine",
    "MicroVMSandbox",
    "MicroVMPool",
    "MicroVMConfig",
    "ToolRouter",
    "ToTPlanner",
    "ProposerAgent",
    "ReviewerAgent",
    "Reflexion",
    "EpisodicMemory",
    "JupyterExecutor",
    "DeepSeekClient",
    "LLMConfig",
    "get_llm_client",
    "set_api_key",
]
