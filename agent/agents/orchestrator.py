"""
 * 小滴课堂,愿景：让技术不再难学
 * @Remark 有问题联系我【xdclass68】
 * 源码-笔记-技术交流群,官网 https://xdclass.net
"""
import os
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from agent.core import AgentState


class OrchestratorAgent:
    """
    中心路由节点 (Orchestrator/Router)
    负责分析用户意图，并将请求分发给相应的专门 Agent。
    """
    def __init__(self):
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        load_dotenv(dotenv_path)

        # 路由节点不需要复杂的工具，只需一个基础大模型来做分类决策
        self.llm = ChatOpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            model=os.getenv("MODEL", "qwen-plus"),
            base_url=os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            temperature=0.1,
        )

    async def route(self, state: AgentState) -> Dict[str, Any]:
        """
        根据用户的最新输入，决定路由走向。
        """
        # 获取最新的一条用户消息
        messages = state.get("messages", [])
        if not messages:
            last_message = ""
        else:
            # langgraph 内部有时候会把 tuple 转成实际的 BaseMessage 子类
            last_msg_obj = messages[-1]
            if isinstance(last_msg_obj, tuple):
                last_message = last_msg_obj[1]
            elif hasattr(last_msg_obj, "content"):
                last_message = last_msg_obj.content
            else:
                last_message = str(last_msg_obj)
        memory_context = state.get("memory_context", "")

        system_prompt = f"""你是一个智能客服系统的总路由（Orchestrator）。
            你的任务是根据用户的提问，决定将问题分发给哪个专业的 Agent 处理。
            
            当前可用的子 Agent 有：
            1. "product_agent" : 负责云产品介绍、资源规格说明、概念解释、操作指南等（非个人资产查询）。
            2. "billing_agent" : 负责查询用户个人的云资源实例状态、购买的机器、订单记录、账单明细等。
            3. "promotion_agent" : 负责处理想要分享产品、推广返佣、获取产品活动链接、获取海报等营销类需求。
            4. "recommendation_agent" : 负责根据用户的业务需求（如Java+MySQL、高并发、特定预算、选型推荐）提供专业的云产品选型与推荐，包含具体的实例型号和配置建议。
            5. "finops_agent_trigger" : 当用户表达“账单太贵”、“需要降本增效”、“资源闲置”、“帮我优化一下成本/服务器”等意图时选择此项。
            
            路由细则（高优先级）：
            - 用户问“某业务场景该选哪个实例/规格是否够用/推荐具体型号”（如 Java + MySQL，8核16G够不够）时，必须路由到 product_agent。
            - 只有在用户明确要求“深度调研报告/长篇架构对比/竞品调研文档/详细评估报告”时，才路由到 deep_research_agent。
            - “推荐商品/推荐型号/选型建议/买哪款合适”默认属于 recommendation_agent，不要归给 product_agent。
            
            【背景记忆】：
            {memory_context}
            
            请仅输出你要路由到的名称（必须是: product_agent, billing_agent, promotion_agent, recommendation_agent, finops_agent_trigger 中的一个），不要输出任何其他解释性文字。
            如果你无法判断，默认输出 product_agent。
            """

        response = await self.llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=last_message)
        ])
        
        decision = response.content.strip().lower()
        if "finops" in decision:
            next_node = "billing_agent" # FinOps 流程的第一步是交给 Billing 去查实例
            state["metadata"]["is_finops_workflow"] = True
            print("🧭 [Orchestrator] 识别到成本优化意图，触发 FinOps 工作流 (第 1 步: 获取实例数据)")
        elif "billing" in decision:
            next_node = "billing_agent"
            state["metadata"]["is_finops_workflow"] = False
            print("🧭 [Orchestrator] 识别到常规账单查询意图，路由至: billing_agent")
        elif "promotion" in decision:
            next_node = "promotion_agent"
            print("🧭 [Orchestrator] 识别到营销推广意图，路由至: promotion_agent")
        elif "recommendation" in decision:
            next_node = "recommendation_agent"
            print("🧭 [Orchestrator] 识别到选型推荐意图，路由至: recommendation_agent")
        else:
            next_node = "product_agent"
            print("🧭 [Orchestrator] 默认或识别到产品咨询意图，路由至: product_agent")
            
        # 返回更新后的 state
        return {"next_agent": next_node, "metadata": state.get("metadata", {})}
