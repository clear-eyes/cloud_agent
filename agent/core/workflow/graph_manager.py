import os
import sys
from pathlib import Path
# 这里没有 sys.path.insert！我们期望调用者 (main.py) 正确设置 sys.path。

import asyncio
from typing import Literal

from langgraph.graph import StateGraph, START, END
from agent.core.workflow.state import AgentState
from agent.agents.orchestrator import OrchestratorAgent
from agent.agents.product_agent import ProductAgentNode
from agent.agents.billing_agent import BillingAgentNode
from agent.agents.promotion_agent import PromotionAgentNode
from agent.agents.recommendation_agent import RecommendationAgent
from agent.agents.finops_agent import FinOpsAgentNode

class AgentGraphManager:
    """
    负责组装 LangGraph 多 Agent 编排。
    支持 FinOps 工作流的跨 Agent 协同状态交接 (State Handoff)。
    """
    def __init__(self):
        self.orchestrator = OrchestratorAgent()
        self.product_node = ProductAgentNode()
        self.billing_node = BillingAgentNode()
        self.promotion_node = PromotionAgentNode()
        self.recommendation_node = RecommendationAgent()
        self.finops_node = FinOpsAgentNode()

    def _route_condition(self, state: AgentState) -> str:
        """根据 Orchestrator 的决策决定走向哪个 Agent 节点。"""
        return state.get("next_agent", "product_agent")

    def _billing_post_condition(self, state: AgentState) -> str:
        """
        BillingAgent 节点执行完后的条件判断：
        如果是在执行 FinOps 工作流，就把接力棒交给 FinOps Agent；
        如果是普通账单查询，直接结束。
        """
        if state.get("metadata", {}).get("is_finops_workflow"):
            return "finops_agent"
        return END

    def build_graph(self) -> StateGraph:
        """构建状态图"""
        builder = StateGraph(AgentState)

        # 1. 添加节点
        builder.add_node("orchestrator", self.orchestrator.route)
        builder.add_node("product_agent", self.product_node)
        builder.add_node("billing_agent", self.billing_node)
        builder.add_node("promotion_agent", self.promotion_node)
        builder.add_node("recommendation_agent", self.recommendation_node)
        builder.add_node("finops_agent", self.finops_node)

        # 2. 定义边
        builder.add_edge(START, "orchestrator")

        # Orchestrator 之后，根据 condition 路由到不同的基础 Agent
        builder.add_conditional_edges(
            "orchestrator",
            self._route_condition,
            {
                "product_agent": "product_agent",
                "billing_agent": "billing_agent",
                "promotion_agent": "promotion_agent",
                "recommendation_agent": "recommendation_agent"
            }
        )

        # 3. 跨 Agent 协同边 (State Handoff)
        # BillingAgent 结束后，动态判断是否需要继续传递给 FinOpsAgent
        builder.add_conditional_edges(
            "billing_agent",
            self._billing_post_condition,
            {
                "finops_agent": "finops_agent",
                END: END
            }
        )

        # 各个子 Agent 执行完毕后，流程结束
        builder.add_edge("product_agent", END)
        builder.add_edge("promotion_agent", END)
        builder.add_edge("recommendation_agent", END)
        builder.add_edge("finops_agent", END)

        return builder.compile()

async def test_graph():
    manager = AgentGraphManager()
    graph = manager.build_graph()

    print("🚀 正在启动云平台智能客服系统 (Multi-Agent 编排模式)...")
    print("="*60)
    
    # 模拟第一轮对话
    state: AgentState = {
        "messages": [("user", "什么是VPC？")],
        "user_id": "user_1001",
        "session_id": "test_session_1",
        "memory_context": "",
        "next_agent": "",
        "metadata": {}
    }
    print(f"👤 用户: {state['messages'][0][1]}")
    
    result = await graph.ainvoke(state)
    print(f"🤖 AI: {result['messages'][-1].content}\n")

    # 模拟第二轮对话，测试路由
    state["messages"] = result["messages"]
    state["messages"].append(("user", "那帮我查一下我最近买了哪些机器？"))
    
    print(f"👤 用户: {state['messages'][-1][1]}")
    result = await graph.ainvoke(state)
    print(f"🤖 AI: {result['messages'][-1].content}\n")

if __name__ == "__main__":
    asyncio.run(test_graph())
