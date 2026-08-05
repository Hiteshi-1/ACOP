"""
Kubernetes API client initialization.
Supports three modes via K8S_MODE env var:
  - "incluster": use in-pod service account (when ACOP itself runs inside k8s)
  - "kubeconfig": use local ~/.kube/config (dev machine with cluster access)
  - "mock": no real cluster — operations.py returns realistic simulated data
"""
from kubernetes import client, config as k8s_config

from app.config import settings
from app.core.logging_config import logger


class K8sClientManager:
    def __init__(self):
        self.mode = settings.K8S_MODE
        self.core_v1: client.CoreV1Api | None = None
        self.apps_v1: client.AppsV1Api | None = None
        self._init_client()

    def _init_client(self):
        if self.mode == "incluster":
            try:
                k8s_config.load_incluster_config()
                self.core_v1 = client.CoreV1Api()
                self.apps_v1 = client.AppsV1Api()
                logger.info("Kubernetes client initialized in in-cluster mode.")
            except Exception as e:
                logger.error(f"Failed to load in-cluster config, falling back to mock: {e}")
                self.mode = "mock"
        elif self.mode == "kubeconfig":
            try:
                k8s_config.load_kube_config(config_file=settings.KUBECONFIG_PATH)
                self.core_v1 = client.CoreV1Api()
                self.apps_v1 = client.AppsV1Api()
                logger.info("Kubernetes client initialized from kubeconfig.")
            except Exception as e:
                logger.error(f"Failed to load kubeconfig, falling back to mock: {e}")
                self.mode = "mock"
        else:
            logger.info("Kubernetes client running in MOCK mode (no real cluster attached).")

    def is_mock(self) -> bool:
        return self.mode == "mock"


k8s_manager = K8sClientManager()
