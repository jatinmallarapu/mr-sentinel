# Compare serving runtimes on the same workload

vLLM is the initial Helm backend. SGLang can be configured as an external backend. Hold the model revision, workload hash, host, and generation settings fixed when comparing the engines. A model-ready Kubernetes probe says nothing about relative quality or throughput.
