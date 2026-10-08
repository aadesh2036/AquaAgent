# ml/ — features, predictor, anomaly, localisation, SageMaker (modules 04, 05, 06)

- `features/`: GraphSample builder + train-only scalers (§7.7). **04**
- `predictor/`: baseline → MLP → GNN (T2); `train.py` runs identically locally and in SageMaker script mode; `predict.py` returns the §7.9 response. **04**
- `anomaly/`: LOO residuals, RTCA dual threshold, sensor-fault rule, tuning (val only, then freeze), classifier (T2). **05**
- `localisation/`: physics signature dictionary + cosine matcher with zone aggregation. **05**
- `sagemaker/`: `launch_training.py`, `deploy_endpoint.py`, `inference.py`, `smoke_invoke.py`. **06**
- `evaluation/`: §9.5 metrics, hop-distance error. **04/05**

Inputs to any model come **only** from `sensors.measured_value`, `context` and `graph` (BACKBONE §11).
