# Runbook: Pod OOMKilled / Memory Leak

## Symptoms
- Pod restart count increasing steadily over time
- Memory usage climbs continuously without plateauing before each restart
- Container status shows `OOMKilled` in last termination reason

## Likely Root Causes
1. Application-level memory leak (unclosed connections, growing caches, unbounded queues)
2. Memory limit set too low for legitimate peak load
3. Large batch job or request spike exceeding allocated memory

## Recommended Remediation
- **Immediate**: `restart_pod` to clear the leaked memory and restore service
- **Short-term**: `scale_deployment` horizontally to distribute load while root cause is fixed
- **Long-term**: Profile the application heap, fix the leak, and adjust memory limits/requests based on observed usage patterns

## Confidence Signals
High confidence in memory leak diagnosis when restart frequency correlates tightly with
memory usage trajectory reaching >90% shortly before each restart.
