import asyncio
import json
import sys
import os
from typing import Any

from app.infra.cache import semantic_cache

# 初始化 Agent 和 Graph
AGENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent")
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)



# Global variables for graph and memory
graph: Any = None
memory: Any = None
_initialization_lock: asyncio.Lock | None = None

async def init_agent_system():
    """Initialize heavy AI and storage dependencies only when chat is used."""
    global graph, memory, _initialization_lock
    if graph is None:
        if _initialization_lock is None:
            _initialization_lock = asyncio.Lock()

        async with _initialization_lock:
            # A concurrent request may have completed initialization while waiting.
            if graph is not None:
                return

            # These imports pull in LangChain, Neo4j and Milvus.  Keeping them
            # here lets Uvicorn accept connections immediately after it starts.
            from agent.core import AgentGraphManager, MemoryManager
            from agent.config import get_settings

            print("🚀 首次聊天请求：初始化 Multi-Agent 图编排...")
            graph_manager = AgentGraphManager()
            initialized_graph = graph_manager.build_graph()

            print("🧠 初始化 Memory 系统...")
            settings = get_settings()
            initialized_memory = MemoryManager(
                redis_url=settings.redis_url,
                redis_ttl=settings.redis_ttl,
                milvus_host=settings.milvus_host,
                milvus_port=settings.milvus_port,
                milvus_api_key=settings.milvus_api_key,
                embedding_api_key=settings.dashscope_api_key,
            )
            await initialized_memory.initialize()
            await semantic_cache.initialize()
            graph = initialized_graph
            memory = initialized_memory
            print("✅ Agent 系统初始化完成！")

async def _extract_memory_context(user_id: str, session_id: str, query: str) -> str:
    context_parts = []
    if memory and memory.short_term.available:
        history = await memory.short_term.get_messages(user_id, session_id)
        if history:
            recent_history = history[-10:] if len(history) > 10 else history
            context_parts.append("【近期对话历史】:")
            for msg in recent_history:
                role = "User" if msg["role"] == "user" else "Assistant"
                context_parts.append(f"{role}: {msg['content']}")
    
    if memory and memory.long_term.available:
        prefs = await memory.long_term.retrieve_relevant(user_id, query)
        if prefs:
            context_parts.append("\n【用户长期偏好/背景】:")
            for p in prefs:
                context_parts.append(f"- {p}")
                
    return "\n".join(context_parts)

async def stream_chat(query: str, user_id: str, session_id: str):
    # Deliberately lazy: application startup stays fast while the first chat
    # request still waits for a fully initialized, usable agent graph.
    await init_agent_system()
    cache_hit = await semantic_cache.get_cache(query, user_id)
    if cache_hit:
        response_text = cache_hit["answer"]
        print(
            f"⚡ 语义缓存命中: {cache_hit['level']} distance={cache_hit['distance']:.4f} matched='{cache_hit['matched_question']}'"
        )
    else:
        print("🏃 进入 Agent 工作流推理...")
        mem_context = await _extract_memory_context(user_id, session_id, query)
        state = {
            "messages": [("user", query)],
            "user_id": user_id,
            "session_id": session_id,
            "memory_context": mem_context,
            "next_agent": "",
            "metadata": {}
        }
        config = {"configurable": {"user_id": user_id}}
        result = await asyncio.to_thread(asyncio.run, graph.ainvoke(state, config=config)) if not asyncio.iscoroutinefunction(graph.ainvoke) else await graph.ainvoke(state, config=config)
        response_text = result["messages"][-1].content
    
    # 保存短时记忆
    if memory and memory.short_term.available:
        turn = [
            {"role": "user", "content": query},
            {"role": "assistant", "content": response_text},
        ]
        await memory.save_conversation(user_id, session_id, turn)
        
    # 流式返回大模型结果
    chunk_size = 5
    for i in range(0, len(response_text), chunk_size):
        chunk = response_text[i:i+chunk_size]
        yield f"data: {json.dumps({'content': chunk})}\n\n"
        await asyncio.sleep(0.02)
        
    yield f"data: {json.dumps({'done': True})}\n\n"
