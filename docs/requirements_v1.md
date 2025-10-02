# Benchmarking Framework – Technical Requirements

## 0. Scope & Goals
- **Goal**: Design and implement a unified, reproducible benchmarking framework for AI Factory workloads on MeluXina.
- **Workloads covered**:
  - File storage, relational DB (PostgreSQL), and object storage (S3-compatible)
  - Inference servers (vLLM, Triton)
  - Vector databases (Chroma, FAISS, Milvus, Weaviate)
- **Primary outputs**: comparable metrics (throughput, latency, resource usage, scalability), automated job orchestration, dashboards, and final reports.


## 1. Definitions
- **Trial**: a single benchmark run with a fixed configuration.
- **Scenario**: a set of trials varying one or more parameters (e.g., GPUs, batch size, concurrency).
- **SUT**: System Under Test (e.g., Triton serving a model, a Milvus cluster, PostgreSQL instance).
- **Driver**: the load generator client (Python process / Dask task / Spark job / Slurm array task).

## 2. Assumptions & Constraints
- Runs on **MeluXina** under **Slurm**; container runtime is **Apptainer** (.sif images). No root privileges on compute nodes.
- Compute nodes may have **restricted egress**; images must be pre-pulled/built on login nodes.
- Persistent storage available in `$HOME` (small, backed-up) and `$WORK` (larger, quota-based). Results must be stored in user/project space.
- GPU jobs scheduled on GPU partitions; multi-node runs rely on IB + NCCL (if applicable).

## 3. System Architecture (High-Level)
- **Orchestrator** (Python CLI): composes scenarios, prepares containers, generates Slurm job scripts, submits jobs, tracks status, collects artifacts.
- **Drivers** per component: storage, inference, vector DBs. Each driver exposes a unified interface.
- **Metrics plane**: in-process timers + optional Prometheus exporters; post-run parsers to JSON/CSV.
- **Visualization**: result post-processing + Grafana dashboards (reading from CSV/JSON or Prometheus TSDB if available).

## 4. Functional Requirements (FR)
### 4.1 Orchestration & Execution
- **FR-01**: Provide a Python CLI `bench` with subcommands: `plan`, `submit`, `status`, `collect`, `report`.
- **FR-02**: Accept a YAML config file describing scenarios (resources, datasets, model, concurrency, repetitions, warmup).
- **FR-03**: Autogenerate Slurm scripts with parameters from config; support job arrays for parameter sweeps.
- **FR-04**: Support single-node and multi-node jobs (Slurm `--nodes`, `--ntasks`, `--gres=gpu:X`, `--cpus-per-task`, `--mem`).
- **FR-05**: Execute workloads inside **Apptainer** with flags `--nv` for GPU and bind mounts for datasets & results.
- **FR-06**: Download/build containers **only on login nodes** and reuse `.sif` in jobs.
- **FR-07**: Provide retry policy for failed trials (configurable `max_retries`, exponential backoff).
- **FR-08**: Persist run metadata (git commit, timestamp, host, partition, Slurm job ID, container digest) to `results/<scenario>/<trial>/meta.json`.

### 4.2 Metrics & Artifacts
- **FR-09**: Collect **latency** (p50/p90/p99), **throughput** (ops/s or tokens/s), **resource usage** (GPU util/mem, CPU%, RAM), **errors** (error rate, timeouts).
- **FR-10**: Export metrics to structured files per trial: `metrics.json` and `metrics.csv` with a defined schema (see §6).
- **FR-11**: Optionally expose Prometheus metrics via a file-based exporter (`textfile` collector) when network services are disallowed.
- **FR-12**: Generate summary tables and plots for each scenario as part of `bench report` into `reports/<scenario>/`.

### 4.3 Reproducibility & Config Management
- **FR-13**: All runs must be reproducible: container digests pinned (e.g., `docker://nvcr.io/...@sha256:...` → `.sif`).
- **FR-14**: Random seeds captured in config and injected into drivers when relevant; report seed in `meta.json`.
- **FR-15**: Log full effective configuration (`effective_config.yaml`) per trial.

### 4.4 Storage Benchmarks
- **FR-16 (File I/O)**: Implement sequential and random read/write tests using configurable file sizes, thread counts; report MB/s, IOPS, latency.
- **FR-17 (PostgreSQL)**: Use `psycopg2`-based driver; run OLTP-like micro-benchmarks (reads/writes, indexed lookups, batch inserts); report TPS, p95 latency, CPU/IO wait.
- **FR-18 (S3/Object)**: Use S3 SDK against an S3-compatible endpoint; measure PUT/GET for object sizes (1KB–1GB), concurrency; report ops/s, p95 latency, transfer MB/s.

### 4.5 Inference Servers
- **FR-19 (Triton)**: Support TensorRT/ONNX/PyTorch backends; test per-model batch sizes, dynamic shapes; report throughput (items/s, tokens/s), latency distribution, GPU util.
- **FR-20 (vLLM)**: Run text-generation benchmarks over specified models (e.g., Mistral, Llama); vary prompt length, output length, batch size, concurrency.
- **FR-21**: Support **server** mode (driver → HTTP/gRPC) and **embedded** mode (driver launches server inside job and tears it down).

### 4.6 Vector Databases
- **FR-22**: Benchmark Chroma, FAISS, Milvus, Weaviate via a unified interface: build index, ingest dataset, run KNN queries under concurrency.
- **FR-23**: Report ingest throughput (vectors/s), query latency (p50/p95/p99), recall@K (if ground truth available), and memory footprint.
- **FR-24**: Allow single-node and distributed configurations where supported (e.g., Milvus cluster).

### 4.7 Load Generators & Scaling
- **FR-25**: Implement drivers that can run as (a) local Python processes, (b) Slurm array tasks, and (c) Dask/Spark executors when cluster frameworks are available.
- **FR-26**: Provide parameter sweeps over: concurrency, batch size, model, dataset size, GPU count; produce scaling curves.

### 4.8 Reporting & Dashboards
- **FR-27**: Produce HTML/Markdown reports per scenario with tables, charts, and configuration snapshots.
- **FR-28**: Provide Grafana dashboards (JSON) for time-series if Prometheus is available; otherwise generate static plots.
- **FR-29**: Compare services side-by-side under identical load; highlight best/median/worst with statistical significance (t-test or bootstrap CI where applicable).

## 5. Non-Functional Requirements (NFR)
- **NFR-01 Performance**: Orchestrator overhead < 5% of end-to-end runtime for single-node tests.
- **NFR-02 Portability**: All components run via Apptainer without root; no Docker daemon dependency on compute nodes.
- **NFR-03 Observability**: Logs are structured (JSON lines) and timestamped; each trial has a unique ID.
- **NFR-04 Reliability**: Failed trials are detectable and re-runnable; partial results do not corrupt summaries.
- **NFR-05 Usability**: Single command to reproduce a scenario: `bench submit -c configs/<scenario>.yaml`.

## 6. Data & Metrics Schema
**metrics.json** (per trial):
```json
{
  "trial_id": "uuid",
  "timestamp": "iso8601",
  "component": "storage|inference|vectordb",
  "service": "triton|vllm|postgres|s3|milvus|faiss|weaviate|chroma|fileio",
  "config": { "gpus": 1, "batch": 32, "concurrency": 8, "nodes": 1 },
  "throughput": { "value": 123.4, "unit": "items_per_s" },
  "latency_ms": { "p50": 10.2, "p90": 15.8, "p99": 30.1 },
  "resource": { "gpu_util": 0.76, "gpu_mem_mb": 11000, "cpu_util": 0.55, "ram_mb": 20480 },
  "errors": { "rate": 0.0, "timeouts": 0 },
  "notes": "optional"
}
```

## 7. Target Services (Justification & Feasibility)
- **Inference**: Triton (production-grade, GPU-optimized), vLLM (efficient LLM serving). Both have public images; reproducible; GPU-friendly.
- **Storage**: PostgreSQL (mature RDBMS with clear drivers), S3-compatible object store (ubiquitous; SDK-driven; size & concurrency sweeps).
- **Vector DBs**: FAISS (baseline library), Milvus & Weaviate (cluster-ready), Chroma (lightweight). Each has container images and Python clients.

## 8. MeluXina Integration Requirements
- **MR-01**: Slurm partitions, QoS, and account are configurable per scenario (`partition`, `qos`, `account`).
- **MR-02**: Jobs request resources explicitly (`--gres=gpu:X`, `--cpus-per-task`, `--mem`, `--nodes`).
- **MR-03**: Use `module load apptainer` (or site-specific module name) before `apptainer exec`.
- **MR-04**: All `.sif` images are built/pulled on login nodes and referenced by absolute path in jobs (e.g., `$WORK/containers/<name>.sif`).
- **MR-05**: Bind-mount datasets and results directories: `apptainer exec -B $WORK/data:/data -B $WORK/results:/results ...`.
- **MR-06**: Network services are optional; prefer embedded/localhost mode; if servers are used, document SSH tunneling requirements.
- **MR-07**: Multi-node GPU runs set NCCL envs as needed (e.g., `NCCL_IB_HCA`, `NCCL_DEBUG=INFO`).
- **MR-08**: Log Slurm IDs and node lists; store Slurm stdout/err in `logs/` with pattern `%x_%j`.

## 9. Security & Access
- Use user-scoped credentials only; no secrets in repo. Endpoints/keys are read from environment or secrets files outside VCS.
- Containers run under user UID; no `--writable` images on compute nodes.

## 10. Example Config (YAML)
```yaml
scenario: llm_vllm_baseline
partition: gpu
account: pXXXXX
repetitions: 3
resources:
  nodes: 1
  gpus: 1
  cpus_per_task: 8
  mem_gb: 32
workload:
  component: inference
  service: vllm
  model: mistral-7b-instruct
  prompt_len: [128, 512]
  gen_tokens: [128]
  batch: [1, 4, 8]
  concurrency: [1, 8, 32]
artifacts:
  container: $WORK/containers/vllm.sif
  dataset: $WORK/data/prompts.jsonl
binds:
  - "$WORK/data:/data"
  - "$WORK/results:/results"
```

## 11. Acceptance Criteria (Mapping)
- **AC-01**: Every challenge objective appears as at least one FR/MR item.
- **AC-02**: Requirements are parameterized and testable (explicit metrics, schema, and resource flags).
- **AC-03**: Target services list is justified and runnable via Apptainer on MeluXina.
- **AC-04**: A sample scenario (`§10`) runs end-to-end (dry-run acceptable before cluster access).

## 12. Timeline Alignment
- **Month 1**: Finalize §2–§8; produce initial containers; dry-run `plan` and config parsing.
- **Month 2**: Implement drivers for storage/inference/vector DBs; metrics schema; first reports.
- **Month 3**: Execute Slurm scenarios; collect multi-node scaling; refine dashboards.
- **Month 4**: Comparative analysis; final reports and best-practice guidance.

## 13. Risks & Mitigations
- **Image egress blocked** → Pre-pull on login; mirror to `$WORK/containers/`.
- **Service exposure policies** → Prefer embedded mode and file-based metrics export.
- **Quota limits** → Configurable dataset sizes and retention policy for logs.
- **Model licensing** → Use OSS/permissive models; record license in metadata.

## 14. Done Checklist
- [ ] CLI scaffold with `plan/submit/status/collect/report`
- [ ] YAML config loader & validation
- [ ] Slurm generator (single/multi-node, arrays)
- [ ] Apptainer exec wrapper with bind mounts
- [ ] Drivers: storage (file/PG/S3), inference (Triton/vLLM), vector DBs (FAISS/Milvus/Weaviate/Chroma)
- [ ] Metrics capture & schema
- [ ] Reports & (optional) Grafana dashboards
- [ ] Sample configs & example results



## 15. Module-Specific Functional Requirements (from challenge docs)
The framework is decomposed into five modules; each module exposes a consistent lifecycle and CLI/API. Requirements are specific, measurable, and testable.

### 15.1 Servers Module
- **SVR-01 Start/Stop**: Start and stop one or more services (file/S3/PostgreSQL, Triton, vLLM, FAISS/Milvus/Weaviate/Chroma) on SLURM; exit codes reflect success.
- **SVR-02 Scale**: Support single-node and multi-node deployments (config: `nodes`, `ntasks`, `gres`, `cpus`, `mem`).
- **SVR-03 List & Inspect**: `servers list` shows available recipes with versions; `servers ps` lists running instances with Slurm JobIDs.
- **SVR-04 Health & Readiness**: `servers check <id>` returns HTTP 200 or TCP-ready within a configurable timeout; surfaces endpoint(s) for clients.
- **SVR-05 Recipes**: Services defined declaratively (container image digest, env, ports, binds); validation schema provided.
- **SVR-06 Teardown Safety**: On failure or cancel, resources are cleaned (jobs cancelled, temp dirs removed).

### 15.2 Clients Module
- **CLI-01 Launch**: Launch distributed clients as Slurm jobs/arrays targeting a specific server endpoint.
- **CLI-02 Load Patterns**: Support open/closed loop with parameters: `concurrency`, `rps`, `batch`, `duration`, `warmup`.
- **CLI-03 Protocols**: Implement per-service drivers (e.g., HTTP/gRPC for Triton/vLLM; SQL for PostgreSQL; S3 API for object; vector DB SDKs).
- **CLI-04 Metrics**: Emit latency histograms (p50/p90/p99) and throughput at 1s intervals; write `metrics.json/csv` per trial.
- **CLI-05 Fault Tolerance**: If a client shard fails, remaining shards continue; failure rate included in results.

### 15.3 Monitors Module
- **MON-01 Provision**: Start/stop monitoring instance(s) via Slurm; configurable scrape interval (≥1s).
- **MON-02 Sources**: Collect app-level metrics and system metrics (GPU util/mem via `nvidia-smi dmon` or DCGM; CPU/RAM via psutil/Node Exporter).
- **MON-03 Storage**: Persist time series to `$WORK/metrics/<experiment>/`; support Prometheus textfile collector if network endpoints are disabled.
- **MON-04 Reporting**: Produce aggregations (min/avg/max/percentiles) and export `summary.json` per experiment.

### 15.4 Logs Module
- **LOG-01 Aggregation**: Collect stdout/stderr from all jobs to `$WORK/logs/<experiment>/` with pattern `%x_%j.{out,err}`.
- **LOG-02 Retrieval**: `logs get <experiment>` packages logs into a tarball; supports filters by component and time range.
- **LOG-03 Correlation**: Add trial IDs and timestamps to each line (JSONL) to enable cross-component correlation.

### 15.5 Interface Module
- **INT-01 Recipe Validation**: Validate recipes against JSONSchema; fail-fast with actionable errors.
- **INT-02 Orchestration**: `bench start <recipe>` performs ordered lifecycle: servers → monitors/logs → clients → teardown.
- **INT-3 Status**: `bench status` shows component state and key endpoints; `bench stop` terminates all associated jobs.
- **INT-04 Reporting**: `bench report` creates HTML/Markdown with tables, charts, and config snapshots.

## 16. Target Services (selection & feasibility)
- **Storage**: File I/O (sequential/random), PostgreSQL (psycopg2), S3-compatible object store (SDK).
- **Inference**: **Triton Inference Server**, **vLLM** (LLMs). Images pinned by digest and converted to `.sif`.
- **Vector DBs**: **FAISS** (baseline), **Milvus**, **Weaviate**, **Chroma**. Each with container recipe and client driver.
**Justification**: Coverage of core AI Factory components; strong community support; mature containers; clear KPIs (throughput, latency, scaling).

## 17. MeluXina Integration (detailed)
- **MLX-01 Scheduler**: All jobs use Slurm with explicit resources (`--partition`, `--account`, `--qos`, `--nodes`, `--gres=gpu:X`, `--cpus-per-task`, `--mem`).
- **MLX-02 Containers**: Use `module load apptainer`; images pre-pulled on login node and stored at `$WORK/containers/*.sif`.
- **MLX-03 Binds**: Bind datasets and results: `-B $WORK/data:/data -B $WORK/results:/results`.
- **MLX-04 Networking**: Default to embedded mode (no external ports). If server mode is required, document SSH tunneling and site policy.
- **MLX-05 Multi-node**: Enable NCCL/IB for distributed inference where supported (env vars documented per recipe).
- **MLX-06 Quotas**: Respect filesystem quotas; configurable retention (log pruning) and data sizes.

## 18. Acceptance Traceability Matrix
| Challenge Objective | Requirement(s) |
|---|---|
| Unified benchmarking framework | FR-01..FR-08, INT-01..INT-04 |
| Include storage, inference, vector DBs | FR-16..FR-24, 16 |
| Reproducible, modular scenarios (Slurm) | FR-02..FR-05, FR-13..FR-15, MLX-01..MLX-03 |
| Comparative insights & scalability | FR-22..FR-29 |
| Monitoring & reporting | MON-01..MON-04, LOG-01..LOG-03, FR-27..FR-29 |
| MeluXina integration | MR-01..MR-08, MLX-01..MLX-06 |

## 19. Open Questions
- Confirm exact **partition/QoS/account** names on MeluXina.
- Confirm **VPN/jumphost** policy for any server-mode benchmarks.
- Decide datasets and sizes for storage and vector DB tests (to fit quotas/time).

