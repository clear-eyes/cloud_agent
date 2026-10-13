"""多智能体系统的工作流编排。"""

from .state import AgentOutput, AgentState

__all__ = ["AgentOutput", "AgentState", "AgentGraphManager"]


def __getattr__(name: str):
    """延迟加载图管理器，避免它与 ``agent.core`` 的初始化形成循环导入。"""
    if name == "AgentGraphManager":
        from .graph_manager import AgentGraphManager

        return AgentGraphManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
