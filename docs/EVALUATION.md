# PHOENIX Routing Evaluation Framework

## Evaluation Methodology

The PHOENIX evaluation framework evaluates three distinct evacuation routing modes across synthetic and recorded emergency scenarios:

| Mode | Decision Logic | Dynamic Hazard Reaction | Temporal Growth Prediction |
| :--- | :--- | :--- | :--- |
| **Static Routing** | Classical shortest distance (Dijkstra) | None | None |
| **Reactive Routing** | Shortest path penalizing active hazard zones above threshold | Yes (Immediate) | None |
| **Predictive Routing** | Shortest path penalizing both active hazard and predicted smoke growth blockage | Yes (Immediate) | Yes (Temporal smoke growth trend) |

## Benchmark Metrics

1. **Evacuation Travel Cost / Time**: Normalized cumulative travel cost.
2. **Blocked Route Selection Rate**: Frequency with which an occupant is guided into an impassable or high-risk edge.
3. **Time to First Reroute**: Elapsed time before the system recommends a safe alternative route.
4. **Route Oscillation Count**: Unnecessary switching between equal-cost candidate routes.
5. **Prediction Lead Time**: Advance warning time provided before a corridor becomes completely blocked.
6. **Inference & Routing Latency**: Milliseconds per perception frame and graph computation step.
