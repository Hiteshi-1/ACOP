# Runbook: Node NotReady

## Symptoms
- Node condition `Ready` transitions to `False` or `Unknown`
- Pods scheduled on the node become `Unknown` or get evicted
- Kubelet heartbeat missed for multiple consecutive intervals

## Likely Root Causes
1. Kubelet crash or network partition between node and control plane
2. Node resource exhaustion (disk pressure, memory pressure) triggering eviction thresholds
3. Underlying infrastructure failure (cloud provider host issue, hardware fault)

## Recommended Remediation
- **Immediate**: `drain_node` to safely evict and reschedule workloads onto healthy nodes
- **Follow-up**: Investigate kubelet logs and node system logs for root cause
- **If infrastructure fault confirmed**: Cordon permanently and replace the node via the cluster autoscaler / node pool

## Confidence Signals
High confidence in infrastructure-level failure when multiple unrelated pods across
different deployments fail simultaneously on the same node.
