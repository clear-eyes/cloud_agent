"""用于提取实体和关系的基于 LLM 的文档解析器。"""

import json
import logging
from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_community.chat_models import ChatTongyi

from agent.config import get_settings
from .models import (
    Product,
    InstanceType,
    Region,
    Image,
    BillingMode,
    DatabaseEngine,
    StorageType,
    Relation,
)

logger = logging.getLogger(__name__)


def get_extraction_prompt(document_content: str) -> str:
    """获取带有文档内容的提取提示词。"""
    return f"""你是一个专业的云产品知识抽取助手。请从以下产品文档中提取实体和关系，输出为JSON格式。

## 实体类型

1. **Product**（产品）
   - id: 产品ID（小写英文，如 ecs, rds）
   - name: 产品名称
   - category: 类别（计算/数据库/存储/网络）
   - description: 产品描述
   - features: 功能特性列表
   - use_cases: 适用场景列表

2. **InstanceType**（实例规格）
   - id: 规格ID（如 ecs.g7.large）
   - name: 规格名称
   - product_id: 所属产品ID
   - vcpu: vCPU核数
   - memory_gb: 内存GB数
   - bandwidth_gbps: 网络带宽Gbps
   - storage_type: 存储类型（ESSD/SSD/高效云盘）
   - price_per_hour: 按量付费每小时价格（元）

3. **Region**（地域）
   - id: 地域ID（如 cn-beijing）
   - name: 地域名称
   - region_type: domestic（国内）或 international（国际）
   - availability_zones: 可用区列表

4. **Image**（镜像）
   - id: 镜像ID（如 centos-7-9）
   - name: 镜像名称
   - os_type: Linux 或 Windows
   - version: 版本号
   - architecture: 架构（x86_64/arm64）

5. **BillingMode**（计费模式）
   - id: 计费模式ID（pay-as-you-go/subscription）
   - name: 计费模式名称
   - description: 描述
   - billing_cycle: 计费周期（小时/月/年）

6. **DatabaseEngine**（数据库引擎）
   - id: 引擎ID（如 mysql-8-0）
   - name: 引擎名称
   - engine_type: 引擎类型（MySQL/PostgreSQL/SQLServer）
   - version: 版本号
   - product_id: 所属产品ID

7. **StorageType**（存储类型）
   - id: 存储类型ID（cloud-ssd/cloud-essd/local-ssd）
   - name: 存储类型名称
   - performance_level: 性能级别（低/中/高/极高）
   - use_case: 适用场景

## 关系类型

- **BELONGS_TO**: 实例属于产品，引擎属于产品
- **AVAILABLE_IN**: 产品可用地域
- **SUPPORTS_BILLING**: 实例支持计费模式（带price属性）
- **COMPATIBLE_WITH**: 镜像兼容产品，规格兼容引擎
- **SUPPORTS_STORAGE**: 规格支持存储类型

## 输出格式

```json
{{
  "entities": {{
    "products": [...],
    "instance_types": [...],
    "regions": [...],
    "images": [...],
    "billing_modes": [...],
    "database_engines": [...],
    "storage_types": [...]
  }},
  "relations": [
    {{"source_id": "...", "target_id": "...", "type": "BELONGS_TO", "properties": {{...}}}}
  ]
}}
```

## 待解析文档

{document_content}

请只输出JSON，不要有任何其他文字说明。"""


class KnowledgeGraphParser:
    """用于从文档中提取知识图谱实体的解析器。
    
    示例：
        parser = KnowledgeGraphParser()
        
        # 从文件解析
        result = await parser.parse_file("data/raw_documents/ecs_product_manual.txt")
        
        # 从文本解析
        with open("document.txt") as f:
            result = await parser.parse_text(f.read())
        
        # 访问提取的实体
        products = result["products"]
        instance_types = result["instance_types"]
        relations = result["relations"]
    """
    
    def __init__(self, llm: BaseChatModel | None = None) -> None:
        """使用 LLM 初始化解析器。
        
        参数：
            llm: LangChain 聊天模型。如果为 None，则使用 ChatTongyi。
        """
        settings = get_settings()
        self.llm = llm or ChatTongyi(**settings.get_model_config())
    
    async def parse_text(self, text: str) -> dict[str, list[Any]]:
        """解析文档文本并提取实体。
        
        参数：
            text: 文档内容。
            
        返回：
            包含提取的实体和关系的字典。
        """
        prompt = get_extraction_prompt(text)
        
        logger.info("Sending document to LLM for extraction...")
        response = await self.llm.ainvoke(prompt)
        content = response.content
        
        # 从响应中提取 JSON
        try:
            # 尝试查找 JSON 块
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()
            
            data = json.loads(json_str)
            
            # 转换为模型实例
            result = self._convert_to_models(data)
            
            logger.info(
                "Extraction complete: %d products, %d instances, %d regions, %d relations",
                len(result.get("products", [])),
                len(result.get("instance_types", [])),
                len(result.get("regions", [])),
                len(result.get("relations", [])),
            )
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON: %s", e)
            logger.error("Response content: %s", content[:500])
            raise
    
    async def parse_file(self, file_path: str | Path) -> dict[str, list[Any]]:
        """解析文档文件并提取实体。
        
        参数：
            file_path: 文档文件的路径。
            
        返回：
            包含提取的实体和关系的字典。
        """
        file_path = Path(file_path)
        logger.info("Parsing file: %s", file_path)
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        return await self.parse_text(content)
    
    def _convert_to_models(self, data: dict) -> dict[str, list[Any]]:
        """将原始 JSON 数据转换为模型实例。
        
        参数：
            data: 解析后的 JSON 数据。
            
        返回：
            包含模型实例的字典。
        """
        entities = data.get("entities", {})
        relations_data = data.get("relations", [])
        
        result = {}
        
        # 转换产品
        result["products"] = [
            Product(**p) for p in entities.get("products", [])
        ]
        
        # 转换实例规格
        result["instance_types"] = [
            InstanceType(**i) for i in entities.get("instance_types", [])
        ]
        
        # 转换地域
        result["regions"] = [
            Region(**r) for r in entities.get("regions", [])
        ]
        
        # 转换镜像
        result["images"] = [
            Image(**i) for i in entities.get("images", [])
        ]
        
        # 转换计费模式
        result["billing_modes"] = [
            BillingMode(**b) for b in entities.get("billing_modes", [])
        ]
        
        # 转换数据库引擎
        result["database_engines"] = [
            DatabaseEngine(**d) for d in entities.get("database_engines", [])
        ]
        
        # 转换存储类型
        result["storage_types"] = [
            StorageType(**s) for s in entities.get("storage_types", [])
        ]
        
        # 转换关系
        result["relations"] = [
            Relation(
                source_id=r["source_id"],
                target_id=r["target_id"],
                relation_type=r["type"],
                properties=r.get("properties", {}),
            )
            for r in relations_data
        ]
        
        return result


async def main():
    """KnowledgeGraphParser 的示例用法。"""
    import asyncio
    
    # Sample document
    sample_doc = """
# 弹性计算服务 ECS

ECS 是一种可扩展的云计算服务。

## 实例规格

- ecs.g7.large: 2核8GB, 1Gbps带宽, 0.12元/小时
- ecs.g7.xlarge: 4核16GB, 1.5Gbps带宽, 0.24元/小时

## 地域

- 华北2（北京）: cn-beijing
- 华东2（上海）: cn-shanghai

## 计费方式

- 按量付费: 按小时计费
- 包年包月: 按月计费
"""
    
    parser = KnowledgeGraphParser()
    result = await parser.parse_text(sample_doc)
    
    print("提取结果:")
    print(f"  产品: {len(result['products'])}")
    print(f"  实例规格: {len(result['instance_types'])}")
    print(f"  地域: {len(result['regions'])}")
    print(f"  计费模式: {len(result['billing_modes'])}")
    print(f"  关系: {len(result['relations'])}")
    
    # Print first product
    if result['products']:
        print("\n第一个产品:")
        p = result['products'][0]
        print(f"  ID: {p.id}")
        print(f"  名称: {p.name}")
        print(f"  类别: {p.category}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
