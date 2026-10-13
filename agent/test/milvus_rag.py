import os
import sys
import argparse
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_milvus import Milvus
from pymilvus import connections

# ==============================================================================
# 修复 pymilvus 2.6.x 与 langchain-milvus 0.3.x 之间的兼容性问题
# (MilvusClient 连接不注册到 connections 导致的 ConnectionNotExistException)
# ==============================================================================
original_fetch = connections._fetch_handler
def patched_fetch(alias):
    try:
        return original_fetch(alias)
    except Exception:
        from pymilvus.client.connection_manager import ConnectionManager
        mgr = ConnectionManager.get_instance()
        for mc in mgr._registry.values():
            if f"cm-{id(mc.handler)}" == alias:
                return mc.handler
        for mc in mgr._dedicated.values():
            if f"cm-{id(mc.handler)}" == alias:
                return mc.handler
        raise
connections._fetch_handler = patched_fetch
# ==============================================================================

# ==============================================================================
# 环境配置加载
# ==============================================================================
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path)

# 获取并校验配置
api_key = os.getenv("DASHSCOPE_API_KEY")
base_url = os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
milvus_host = os.getenv("MILVUS_HOST", "localhost")
milvus_port = os.getenv("MILVUS_PORT", "19530")

if not api_key:
    raise ValueError("❌ 环境变量中未找到 DASHSCOPE_API_KEY")

# 初始化 Embedding 模型 (使用 DashScope 的 text-embedding-v2)
embeddings = DashScopeEmbeddings(
    dashscope_api_key=api_key,
    model="text-embedding-v2"
)

# Milvus 连接配置
MILVUS_URI = f"http://{milvus_host}:{milvus_port}"
COLLECTION_NAME = "cloud_product_docs"

# ==============================================================================
# 核心功能类：Milvus RAG 管理器
# ==============================================================================
class MilvusRAGManager:
    def __init__(self):
        self.vector_store = None
        self._init_or_connect()

    def _init_or_connect(self):
        """连接到现有的 Milvus Collection，如果不存在则在使用时自动创建"""
        print(f"🔌 连接 Milvus 向量数据库: {MILVUS_URI}")
        
        self.vector_store = Milvus(
            embedding_function=embeddings,
            connection_args={"uri": MILVUS_URI},
            collection_name=COLLECTION_NAME,
            auto_id=True,
            drop_old=False # 默认不删除旧数据，实现增量更新
        )

    def ingest_documents(self, data_dir: str):
        """
        读取目录下的所有 Markdown 文档，分块并存入 Milvus
        """
        if not os.path.exists(data_dir):
            print(f"❌ 目录不存在: {data_dir}")
            return

        print(f"📂 正在加载目录中的 Markdown 文档: {data_dir}")
        # 1. 加载文档
        loader = DirectoryLoader(data_dir, glob="*.md", loader_cls=TextLoader, loader_kwargs={'encoding': 'utf-8'})
        documents = loader.load()
        print(f"✅ 成功加载 {len(documents)} 份文档。")

        # 2. 文本分块 (Chunking)
        # 使用递归字符拆分器，保留上下文连贯性
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,       # 向量检索的 chunk 通常比知识图谱小，以提高检索精度
            chunk_overlap=50,
            separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""]
        )
        docs = text_splitter.split_documents(documents)
        print(f"🔪 文档已切分为 {len(docs)} 个 Chunk 片段。")

        # 3. 写入 Milvus (计算 Embedding 并存储)
        print(f"🧠 正在调用大模型计算向量并存入 Milvus (Collection: {COLLECTION_NAME})...")
        
        # 增量导入: 自动处理嵌入和索引建立
        # 必须保留 from_documents 返回的新实例。首次运行时，初始化阶段集合
        # 尚不存在，旧实例的 search_params 为空；继续使用旧实例查询会触发
        # langchain-milvus 的 search_params 数量断言。
        self.vector_store = Milvus.from_documents(
            docs, 
            embeddings, 
            connection_args={"uri": MILVUS_URI}, 
            collection_name=COLLECTION_NAME, 
            drop_old=True # 这里我们选择覆盖旧集合以保持数据干净，如果想增量改 False
        )
        print(f"🎉 成功将 {len(docs)} 条向量数据入库！")

    def query(self, question: str, top_k: int = 3):
        """
        根据用户问题，在 Milvus 中进行向量相似度检索
        """
        print(f"🔍 正在检索问题: '{question}'")
        
        # 执行相似度搜索
        results = self.vector_store.similarity_search_with_score(question, k=top_k)
        
        if not results:
            print("⚠️ 未找到相关的文档片段。")
            return []

        print(f"\n✅ 找到 {len(results)} 条相关片段:")
        formatted_results = []
        for i, (doc, score) in enumerate(results):
            # score 在 LangChain 的 Milvus 实现中，通常是距离（越小越相似），具体取决于 metric_type
            source = doc.metadata.get('source', 'Unknown')
            filename = os.path.basename(source)
            content = doc.page_content.strip()
            
            print(f"\n--- [片段 {i+1}] 来源: {filename} (相关度得分: {score:.4f}) ---")
            print(f"{content[:200]}...") # 打印前200个字符预览
            
            formatted_results.append({
                "content": content,
                "source": filename,
                "score": score
            })
            
        return formatted_results

# ==============================================================================
# 内部直接执行入口
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="CloudAgent Milvus RAG 初始化与查询")
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="重新切分 mock_data 文档、计算 Embedding 并覆盖写入 Milvus",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="要入库的 Markdown 目录；默认使用项目根目录下的 mock_data",
    )
    parser.add_argument(
        "--question",
        default="五天无理由退款有什么限制条件吗？",
        help="入库完成后或仅查询模式下要检索的问题",
    )
    args = parser.parse_args()

    # 实例化 RAG 管理器
    manager = MilvusRAGManager()
    
    # 只有显式指定 --ingest 时才重新入库，避免普通查询重复产生 API 费用。
    if args.ingest:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        data_dir = args.data_dir or os.path.join(base_dir, "mock_data")
        manager.ingest_documents(data_dir)
    
    # 执行查询
    manager.query(args.question, top_k=3)

if __name__ == "__main__":
    main()
