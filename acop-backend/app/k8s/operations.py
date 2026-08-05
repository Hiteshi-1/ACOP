"""
Concrete Kubernetes operations invoked by the Remediation Agent.
Every function works in both real-cluster mode and mock mode, so the
same agent code path is exercised whether or not a live cluster is attached.
"""
import random
from datetime import datetime
from typing import Dict, List

from kubernetes.client import ApiException

from app.config import settings
from app.core.logging_config import logger
from app.k8s.client import k8s_manager


class K8sOperations:
    def __init__(self):
        self.namespace = settings.K8S_NAMESPACE

    # ---------------- READ OPERATIONS ----------------

    def list_pods(self) -> List[Dict]:
        if k8s_manager.is_mock():
            return self._mock_pods()
        try:
            pods = k8s_manager.core_v1.list_namespaced_pod(self.namespace)
            return [
                {
                    "name": p.metadata.name,
                    "status": p.status.phase,
                    "restart_count": sum(cs.restart_count for cs in (p.status.container_statuses or [])),
                    "node": p.spec.node_name,
                }
                for p in pods.items
            ]
        except ApiException as e:
            logger.error(f"list_pods failed: {e}")
            return []

    def list_nodes(self) -> List[Dict]:
        if k8s_manager.is_mock():
            return self._mock_nodes()
        try:
            nodes = k8s_manager.core_v1.list_node()
            result = []
            for n in nodes.items:
                ready = any(c.type == "Ready" and c.status == "True" for c in n.status.conditions)
                result.append({
                    "name": n.metadata.name,
                    "status": "Ready" if ready else "NotReady",
                    "cpu_capacity": n.status.capacity.get("cpu"),
                    "memory_capacity": n.status.capacity.get("memory"),
                })
            return result
        except ApiException as e:
            logger.error(f"list_nodes failed: {e}")
            return []

    # ---------------- WRITE / REMEDIATION OPERATIONS ----------------

    def restart_pod(self, pod_name: str, grace_period_seconds: int = 30) -> Dict:
        if k8s_manager.is_mock():
            logger.info(f"[MOCK] Restarting pod '{pod_name}' (grace={grace_period_seconds}s)")
            return {"success": True, "message": f"Pod '{pod_name}' restarted (mock)", "timestamp": str(datetime.utcnow())}
        try:
            k8s_manager.core_v1.delete_namespaced_pod(
                name=pod_name, namespace=self.namespace, grace_period_seconds=grace_period_seconds
            )
            return {"success": True, "message": f"Pod '{pod_name}' deleted; controller will recreate it."}
        except ApiException as e:
            logger.error(f"restart_pod failed: {e}")
            return {"success": False, "message": str(e)}

    def scale_deployment(self, deployment_name: str, replicas: int) -> Dict:
        if k8s_manager.is_mock():
            logger.info(f"[MOCK] Scaling deployment '{deployment_name}' to {replicas} replicas")
            return {"success": True, "message": f"Deployment '{deployment_name}' scaled to {replicas} (mock)"}
        try:
            body = {"spec": {"replicas": replicas}}
            k8s_manager.apps_v1.patch_namespaced_deployment_scale(
                name=deployment_name, namespace=self.namespace, body=body
            )
            return {"success": True, "message": f"Deployment '{deployment_name}' scaled to {replicas} replicas."}
        except ApiException as e:
            logger.error(f"scale_deployment failed: {e}")
            return {"success": False, "message": str(e)}

    def drain_node(self, node_name: str) -> Dict:
        if k8s_manager.is_mock():
            logger.info(f"[MOCK] Draining node '{node_name}'")
            return {"success": True, "message": f"Node '{node_name}' cordoned and drained (mock)"}
        try:
            body = {"spec": {"unschedulable": True}}
            k8s_manager.core_v1.patch_node(node_name, body)
            return {"success": True, "message": f"Node '{node_name}' cordoned. Manual pod eviction recommended."}
        except ApiException as e:
            logger.error(f"drain_node failed: {e}")
            return {"success": False, "message": str(e)}

    def rollback_deployment(self, deployment_name: str) -> Dict:
        if k8s_manager.is_mock():
            logger.info(f"[MOCK] Rolling back deployment '{deployment_name}'")
            return {"success": True, "message": f"Deployment '{deployment_name}' rolled back to previous revision (mock)"}
        # Real rollback requires reading revision history from the ReplicaSet annotations;
        # left as an extension point using AppsV1Api.read_namespaced_deployment + patch.
        return {"success": False, "message": "Real-cluster rollback not implemented — extend with revision history lookup."}

    def patch_config(self, resource_name: str, patch: Dict) -> Dict:
        if k8s_manager.is_mock():
            logger.info(f"[MOCK] Patching config for '{resource_name}': {patch}")
            return {"success": True, "message": f"Config patched for '{resource_name}' (mock)"}
        try:
            k8s_manager.core_v1.patch_namespaced_config_map(resource_name, self.namespace, {"data": patch})
            return {"success": True, "message": f"ConfigMap '{resource_name}' patched."}
        except ApiException as e:
            logger.error(f"patch_config failed: {e}")
            return {"success": False, "message": str(e)}

    # ---------------- MOCK DATA GENERATORS ----------------

    @staticmethod
    def _mock_pods() -> List[Dict]:
        names = ["api-gateway", "auth-service", "payment-worker", "notification-svc", "cache-redis"]
        return [
            {
                "name": f"{n}-{random.randint(1000,9999)}",
                "status": random.choice(["Running", "Running", "Running", "CrashLoopBackOff"]),
                "restart_count": random.choice([0, 0, 1, 3, 7]),
                "node": f"node-{random.randint(1,3)}",
            }
            for n in names
        ]

    @staticmethod
    def _mock_nodes() -> List[Dict]:
        return [
            {"name": f"node-{i}", "status": "Ready", "cpu_capacity": "4", "memory_capacity": "16Gi"}
            for i in range(1, 4)
        ]


k8s_ops = K8sOperations()
