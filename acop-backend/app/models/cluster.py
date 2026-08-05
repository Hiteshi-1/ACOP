import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Cluster(Base):
    __tablename__ = "clusters"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False, unique=True)
    provider = Column(String, default="on-prem")  # aws-eks, gcp-gke, azure-aks, on-prem
    region = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    node_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    nodes = relationship("Node", back_populates="cluster", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="cluster", cascade="all, delete-orphan")


class Node(Base):
    __tablename__ = "nodes"

    id = Column(String, primary_key=True, default=gen_uuid)
    cluster_id = Column(String, ForeignKey("clusters.id"), nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, default="worker")  # master, worker
    cpu_capacity = Column(String, nullable=True)
    memory_capacity = Column(String, nullable=True)
    status = Column(String, default="Ready")  # Ready, NotReady, Unknown
    created_at = Column(DateTime, default=datetime.utcnow)

    cluster = relationship("Cluster", back_populates="nodes")
