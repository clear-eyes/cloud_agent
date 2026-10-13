"""用于将数据导入 Neo4j 的知识图谱摄入器。"""

import logging
from typing import Any

from .client import Neo4jClient
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


class KnowledgeGraphIngestor:
    """用于将云产品知识导入 Neo4j 的摄入器。
    
    示例：
        client = Neo4jClient()
        await client.connect()
        
        ingestor = KnowledgeGraphIngestor(client)
        
        # 摄入产品
        products = [Product(id="ecs", name="ECS", ...)]
        await ingestor.ingest_products(products)
        
        # 摄入关系
        relations = [Relation(source_id="ecs", target_id="cn-beijing", ...)]
        await ingestor.ingest_relations(relations)
        
        await client.close()
    """
    
    def __init__(self, client: Neo4jClient) -> None:
        """使用 Neo4j 客户端初始化摄入器。
        
        参数：
            client: 已连接的 Neo4jClient 实例。
        """
        self.client = client
    
    async def ingest_products(self, products: list[Product]) -> int:
        """摄入产品实体。
        
        参数：
            products: 产品实体列表。
            
        返回：
            摄入的产品数量。
        """
        if not products:
            return 0
        
        query = """
        UNWIND $products AS product
        MERGE (p:Product {id: product.id})
        SET p.name = product.name,
            p.category = product.category,
            p.description = product.description,
            p.features = product.features,
            p.use_cases = product.use_cases,
            p.updated_at = datetime()
        RETURN count(p) AS count
        """
        
        params = {
            "products": [
                {
                    "id": p.id,
                    "name": p.name,
                    "category": p.category,
                    "description": p.description,
                    "features": p.features,
                    "use_cases": p.use_cases,
                }
                for p in products
            ]
        }
        
        result = await self.client.execute_query(query, params)
        count = result[0]["count"] if result else 0
        logger.info("Ingested %d products", count)
        return count
    
    async def ingest_instance_types(self, instances: list[InstanceType]) -> int:
        """摄入实例规格实体。
        
        参数：
            instances: 实例规格实体列表。
            
        返回：
            摄入的实例数量。
        """
        if not instances:
            return 0
        
        query = """
        UNWIND $instances AS inst
        MERGE (i:InstanceType {id: inst.id})
        SET i.name = inst.name,
            i.vcpu = inst.vcpu,
            i.memory_gb = inst.memory_gb,
            i.bandwidth_gbps = inst.bandwidth_gbps,
            i.storage_type = inst.storage_type,
            i.price_per_hour = inst.price_per_hour,
            i.updated_at = datetime()
        WITH i, inst
        MATCH (p:Product {id: inst.product_id})
        MERGE (i)-[:BELONGS_TO]->(p)
        RETURN count(i) AS count
        """
        
        params = {
            "instances": [
                {
                    "id": i.id,
                    "name": i.name,
                    "product_id": i.product_id,
                    "vcpu": i.vcpu,
                    "memory_gb": i.memory_gb,
                    "bandwidth_gbps": i.bandwidth_gbps,
                    "storage_type": i.storage_type,
                    "price_per_hour": i.price_per_hour,
                }
                for i in instances
            ]
        }
        
        result = await self.client.execute_query(query, params)
        count = result[0]["count"] if result else 0
        logger.info("Ingested %d instance types", count)
        return count
    
    async def ingest_regions(self, regions: list[Region]) -> int:
        """摄入地域实体。
        
        参数：
            regions: 地域实体列表。
            
        返回：
            摄入的地域数量。
        """
        if not regions:
            return 0
        
        query = """
        UNWIND $regions AS region
        MERGE (r:Region {id: region.id})
        SET r.name = region.name,
            r.region_type = region.region_type,
            r.availability_zones = region.availability_zones,
            r.updated_at = datetime()
        RETURN count(r) AS count
        """
        
        params = {
            "regions": [
                {
                    "id": r.id,
                    "name": r.name,
                    "region_type": r.region_type,
                    "availability_zones": r.availability_zones,
                }
                for r in regions
            ]
        }
        
        result = await self.client.execute_query(query, params)
        count = result[0]["count"] if result else 0
        logger.info("Ingested %d regions", count)
        return count
    
    async def ingest_images(self, images: list[Image]) -> int:
        """摄入镜像实体。
        
        参数：
            images: 镜像实体列表。
            
        返回：
            摄入的镜像数量。
        """
        if not images:
            return 0
        
        query = """
        UNWIND $images AS image
        MERGE (i:Image {id: image.id})
        SET i.name = image.name,
            i.os_type = image.os_type,
            i.version = image.version,
            i.architecture = image.architecture,
            i.updated_at = datetime()
        RETURN count(i) AS count
        """
        
        params = {
            "images": [
                {
                    "id": img.id,
                    "name": img.name,
                    "os_type": img.os_type,
                    "version": img.version,
                    "architecture": img.architecture,
                }
                for img in images
            ]
        }
        
        result = await self.client.execute_query(query, params)
        count = result[0]["count"] if result else 0
        logger.info("Ingested %d images", count)
        return count
    
    async def ingest_billing_modes(self, modes: list[BillingMode]) -> int:
        """摄入计费模式实体。
        
        参数：
            modes: 计费模式实体列表。
            
        返回：
            摄入的计费模式数量。
        """
        if not modes:
            return 0
        
        query = """
        UNWIND $modes AS mode
        MERGE (b:BillingMode {id: mode.id})
        SET b.name = mode.name,
            b.description = mode.description,
            b.billing_cycle = mode.billing_cycle,
            b.updated_at = datetime()
        RETURN count(b) AS count
        """
        
        params = {
            "modes": [
                {
                    "id": m.id,
                    "name": m.name,
                    "description": m.description,
                    "billing_cycle": m.billing_cycle,
                }
                for m in modes
            ]
        }
        
        result = await self.client.execute_query(query, params)
        count = result[0]["count"] if result else 0
        logger.info("Ingested %d billing modes", count)
        return count
    
    async def ingest_database_engines(self, engines: list[DatabaseEngine]) -> int:
        """摄入数据库引擎实体。
        
        参数：
            engines: 数据库引擎实体列表。
            
        返回：
            摄入的数据库引擎数量。
        """
        if not engines:
            return 0
        
        query = """
        UNWIND $engines AS engine
        MERGE (e:DatabaseEngine {id: engine.id})
        SET e.name = engine.name,
            e.engine_type = engine.engine_type,
            e.version = engine.version,
            e.updated_at = datetime()
        WITH e, engine
        MATCH (p:Product {id: engine.product_id})
        MERGE (e)-[:BELONGS_TO]->(p)
        RETURN count(e) AS count
        """
        
        params = {
            "engines": [
                {
                    "id": e.id,
                    "name": e.name,
                    "engine_type": e.engine_type,
                    "version": e.version,
                    "product_id": e.product_id,
                }
                for e in engines
            ]
        }
        
        result = await self.client.execute_query(query, params)
        count = result[0]["count"] if result else 0
        logger.info("Ingested %d database engines", count)
        return count
    
    async def ingest_storage_types(self, storage_types: list[StorageType]) -> int:
        """摄入存储类型实体。
        
        参数：
            storage_types: 存储类型实体列表。
            
        返回：
            摄入的存储类型数量。
        """
        if not storage_types:
            return 0
        
        query = """
        UNWIND $storage_types AS st
        MERGE (s:StorageType {id: st.id})
        SET s.name = st.name,
            s.performance_level = st.performance_level,
            s.use_case = st.use_case,
            s.updated_at = datetime()
        RETURN count(s) AS count
        """
        
        params = {
            "storage_types": [
                {
                    "id": st.id,
                    "name": st.name,
                    "performance_level": st.performance_level,
                    "use_case": st.use_case,
                }
                for st in storage_types
            ]
        }
        
        result = await self.client.execute_query(query, params)
        count = result[0]["count"] if result else 0
        logger.info("Ingested %d storage types", count)
        return count
    
    async def ingest_relations(self, relations: list[Relation]) -> int:
        """摄入实体间的关系。
        
        参数：
            relations: 关系实体列表。
            
        返回：
            摄入的关系数量。
        """
        if not relations:
            return 0
        
        # 按类型分组关系以进行批量处理
        relations_by_type: dict[str, list[Relation]] = {}
        for rel in relations:
            if rel.relation_type not in relations_by_type:
                relations_by_type[rel.relation_type] = []
            relations_by_type[rel.relation_type].append(rel)
        
        total_count = 0
        
        for rel_type, rels in relations_by_type.items():
            query = f"""
            UNWIND $relations AS rel
            MATCH (a {{id: rel.source_id}})
            MATCH (b {{id: rel.target_id}})
            MERGE (a)-[r:{rel_type}]->(b)
            SET r += rel.properties,
                r.updated_at = datetime()
            RETURN count(r) AS count
            """
            
            params = {
                "relations": [
                    {
                        "source_id": r.source_id,
                        "target_id": r.target_id,
                        "properties": r.properties,
                    }
                    for r in rels
                ]
            }
            
            result = await self.client.execute_query(query, params)
            count = result[0]["count"] if result else 0
            total_count += count
            logger.debug("Ingested %d %s relations", count, rel_type)
        
        logger.info("Ingested %d total relations", total_count)
        return total_count
    
    async def ingest_all(
        self,
        products: list[Product] | None = None,
        instance_types: list[InstanceType] | None = None,
        regions: list[Region] | None = None,
        images: list[Image] | None = None,
        billing_modes: list[BillingMode] | None = None,
        database_engines: list[DatabaseEngine] | None = None,
        storage_types: list[StorageType] | None = None,
        relations: list[Relation] | None = None,
    ) -> dict[str, int]:
        """摄入所有实体类型和关系。
        
        参数：
            products: 产品实体列表。
            instance_types: 实例规格实体列表。
            regions: 地域实体列表。
            images: 镜像实体列表。
            billing_modes: 计费模式实体列表。
            database_engines: 数据库引擎实体列表。
            storage_types: 存储类型实体列表。
            relations: 关系实体列表。
            
        返回：
            包含摄入实体数量的字典。
        """
        stats = {}
        
        # 首先创建约束
        await self.client.create_constraints()
        
        # 按顺序摄入实体（节点在关系之前）
        stats["products"] = await self.ingest_products(products or [])
        stats["instance_types"] = await self.ingest_instance_types(instance_types or [])
        stats["regions"] = await self.ingest_regions(regions or [])
        stats["images"] = await self.ingest_images(images or [])
        stats["billing_modes"] = await self.ingest_billing_modes(billing_modes or [])
        stats["database_engines"] = await self.ingest_database_engines(database_engines or [])
        stats["storage_types"] = await self.ingest_storage_types(storage_types or [])
        
        # 最后摄入关系
        stats["relations"] = await self.ingest_relations(relations or [])
        
        logger.info("Knowledge graph ingestion complete: %s", stats)
        return stats
