from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cluster import Cluster, Node
from app.schemas.cluster import ClusterCreate, ClusterUpdate, ClusterOut, ClusterDetailOut, NodeCreate, NodeOut
from app.core.security import get_current_user

router = APIRouter(prefix="/clusters", tags=["Clusters"])


@router.post("", response_model=ClusterOut, status_code=201)
def create_cluster(payload: ClusterCreate, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    existing = db.query(Cluster).filter(Cluster.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="A cluster with this name already exists.")
    cluster = Cluster(**payload.model_dump())
    db.add(cluster)
    db.commit()
    db.refresh(cluster)
    return cluster


@router.get("", response_model=List[ClusterOut])
def list_clusters(db: Session = Depends(get_db)):
    return db.query(Cluster).order_by(Cluster.created_at.desc()).all()


@router.get("/{cluster_id}", response_model=ClusterDetailOut)
def get_cluster(cluster_id: str, db: Session = Depends(get_db)):
    cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return cluster


@router.patch("/{cluster_id}", response_model=ClusterOut)
def update_cluster(cluster_id: str, payload: ClusterUpdate, db: Session = Depends(get_db),
                    user: str = Depends(get_current_user)):
    cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cluster, field, value)
    db.commit()
    db.refresh(cluster)
    return cluster


@router.delete("/{cluster_id}", status_code=204)
def delete_cluster(cluster_id: str, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    db.delete(cluster)
    db.commit()


@router.post("/{cluster_id}/nodes", response_model=NodeOut, status_code=201)
def add_node(cluster_id: str, payload: NodeCreate, db: Session = Depends(get_db),
             user: str = Depends(get_current_user)):
    cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    node = Node(cluster_id=cluster_id, **payload.model_dump())
    db.add(node)
    cluster.node_count = db.query(Node).filter(Node.cluster_id == cluster_id).count() + 1
    db.commit()
    db.refresh(node)
    return node


@router.get("/{cluster_id}/nodes", response_model=List[NodeOut])
def list_nodes(cluster_id: str, db: Session = Depends(get_db)):
    return db.query(Node).filter(Node.cluster_id == cluster_id).all()


@router.get("/{cluster_id}/live-pods")
def live_pods(cluster_id: str, db: Session = Depends(get_db)):
    """Returns live pod status from the Kubernetes cluster (or mock data)."""
    from app.k8s.operations import k8s_ops
    cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return {"cluster_id": cluster_id, "pods": k8s_ops.list_pods()}


@router.get("/{cluster_id}/live-nodes")
def live_nodes(cluster_id: str, db: Session = Depends(get_db)):
    """Returns live node status from the Kubernetes cluster (or mock data)."""
    from app.k8s.operations import k8s_ops
    cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return {"cluster_id": cluster_id, "nodes": k8s_ops.list_nodes()}
