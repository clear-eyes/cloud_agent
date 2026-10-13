"""知识图谱实体的数据模型。"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Product:
    """云产品实体。"""
    id: str
    name: str
    category: str
    description: str
    features: list[str] = field(default_factory=list)
    use_cases: list[str] = field(default_factory=list)


@dataclass
class InstanceType:
    """实例规格实体。"""
    id: str
    name: str
    product_id: str
    vcpu: int
    memory_gb: int
    bandwidth_gbps: float
    storage_type: str
    price_per_hour: float


@dataclass
class Region:
    """云地域实体。"""
    id: str
    name: str
    region_type: Literal["domestic", "international"]
    availability_zones: list[str] = field(default_factory=list)


@dataclass
class Image:
    """操作系统镜像实体。"""
    id: str
    name: str
    os_type: Literal["Linux", "Windows"]
    version: str
    architecture: str = "x86_64"


@dataclass
class BillingMode:
    """计费模式实体。"""
    id: str
    name: str
    description: str
    billing_cycle: str


@dataclass
class DatabaseEngine:
    """RDS 数据库引擎实体。"""
    id: str
    name: str
    engine_type: str
    version: str
    product_id: str


@dataclass
class StorageType:
    """存储类型实体。"""
    id: str
    name: str
    performance_level: str
    use_case: str


@dataclass
class Relation:
    """实体间的关系。"""
    source_id: str
    target_id: str
    relation_type: Literal[
        "BELONGS_TO",
        "AVAILABLE_IN", 
        "SUPPORTS_BILLING",
        "COMPATIBLE_WITH",
        "SUPPORTS_STORAGE",
    ]
    properties: dict = field(default_factory=dict)
