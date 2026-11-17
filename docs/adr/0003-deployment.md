# Start with one Kubernetes GPU pod

The GPU deployment uses Recreate because the smallest test cluster may have only one GPU. A second replica requires a second GPU. Ray Serve becomes worth evaluating when mixed model deployments, replica placement, or queue-based scaling make manual deployment management cumbersome.
