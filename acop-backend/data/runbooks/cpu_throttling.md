# Runbook: CPU Throttling / High Latency

## Symptoms
- CPU usage sustained above 85-90% of the pod's CPU limit
- Increased request latency without corresponding increase in traffic
- `container_cpu_cfs_throttled_seconds_total` trending upward

## Likely Root Causes
1. CPU limit set too conservatively relative to real workload
2. Inefficient code path (e.g., N+1 queries, unoptimized loops) consuming excess CPU
3. Noisy-neighbor effect from co-located workloads on the same node

## Recommended Remediation
- **Immediate**: `scale_deployment` to add replicas and spread load
- **Alternative**: `patch_config` to raise the CPU limit/request if node capacity allows
- **Long-term**: Profile hot code paths; consider node affinity/anti-affinity rules to reduce noisy-neighbor contention

## Confidence Signals
High confidence when CPU usage and request latency rise together while request
volume stays flat — this rules out a genuine traffic-driven cause.
