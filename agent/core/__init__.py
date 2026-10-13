"""核心 Agent 框架组件。"""

from .mcp.mcp_manager import MCPManager
from .workflow.state import AgentOutput, AgentState
from .memory.memory_manager import MemoryManager

__all__ = ["AgentOutput", "AgentState", "MCPManager", "AgentGraphManager", "MemoryManager"]


def __getattr__(name: str):
    """Delay graph imports so individual Agent modules can import AgentState."""
    if name == "AgentGraphManager":
        from .workflow.graph_manager import AgentGraphManager

        return AgentGraphManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
