
# Benchmarking Framework – Technical Requirements (v2, Recipe-aligned)
 
## 0. Scope & Goals
- **Goal**: Design and implement a unified, reproducible benchmarking framework for AI Factory workloads on MeluXina.
- **Workloads covered**:
  - File storage, relational DB (PostgreSQL), and object storage (S3-compatible)
  - Inference servers (vLLM, Triton)
  - Vector databases (Chroma, FAISS, Milvus, Weaviate) 
- **Primary outputs**: comparable metrics (throughput, latency, resource usage, scalability), automated job orchestration, dashboards, and final reports.

## 1. Definitions
- **Recipe**: a YAML file that declares a scenario, requested Slurm resources, workload parameters, artifacts, bind mounts, and metadata.
- **Trial**: a single benchmark run with a fixed, fully-expanded set of parameters derived from the recipe.
- **Scenario**: a set of trials produced by parameter sweeps declared in the recipe.
- **SUT**: System Under Test (e.g., Triton serving a model, a Milvus cluster, PostgreSQL instance).
- **Driver**: the load generator client (Python process / Slurm array task / Dask-Spark executor).

## 2. Assumptions & Constraints
- Runs on **MeluXina** under **Slurm**; container runtime is **Apptainer** (.sif images). No root on compute nodes.
- Images are pre-pulled/built on login nodes and referenced by absolute path at run time.
- Persistent storage in `$HOME` (small, backed-up) and `$WORK` (larger, quota-based); results are stored in user/project space.
- GPU jobs scheduled on GPU partitions; multi-node runs rely on IB + NCCL (if applicable).

## 3. System Architecture (High-Level)
- **Orchestrator** (Python CLI): reads recipes, validates, expands sweeps into trials, generates Slurm job scripts, submits jobs, tracks status, collects artifacts.
- **Drivers** per component: storage, inference, vector DBs. Each driver reads parameters from the recipe.
- **Metrics plane**: in-process timers + optional Prometheus exporters; post-run parsers to JSON/CSV.
- **Visualization**: result post-processing + optional Grafana dashboards (from CSV/JSON or Prometheus TSDB).

## 4. Functional Requirements (FR)

### 4.1 Orchestration & Execution
- **FR-01**: Provide a Python CLI `bench` with subcommands: `plan`, `submit`, `status`, `collect`, `report`.
- **FR-02 (Recipes)**: Accept a **Recipe** (YAML) with these top-level fields and semantics:

  - `scenario` (string, required)

  - `partition`, `account`, `qos` (Slurm scheduling)

  - `repetitions` (integer ≥ 1)

  - `resources`: `nodes`, `gpus`, `cpus_per_task`, `mem_gb` (positive integers)

  - `workload`: 

    - `component`: one of `storage|inference|vectordb`

    - `service`: one of `triton|vllm|postgres|s3|milvus|faiss|weaviate|chroma|fileio`

    - Optional per-service fields (e.g., `model`, `prompt_len`, `gen_tokens`, `batch`, `concurrency`, `dataset`)

  - `artifacts`: `container` (absolute path to `.sif`), optional `dataset`

  - `binds`: list of host→container bind strings (e.g., `$WORK/data:/data`)

  - `metadata`: optional (`seed`, `git_commit`, `notes`) 

  The orchestrator must honor these fields verbatim when generating jobs.
- **FR-02a (Validation)**: Recipes are validated before submission:

  - Required: `scenario`, `partition`, `account`, `resources`, `workload`

  - `workload.service` must be a member of the allowed list

  - Resource values are positive integers

  - `artifacts.container` ends with `.sif`

  - If `resources.gpus > 0` then `partition == "gpu"`

  On failure, the CLI exits non-zero with actionable messages.
- **FR-03 (Parameter sweeps)**: Any array-valued fields (e.g., `batch: [1,4,8]`, `concurrency: [1,8,32]`, `prompt_len`) expand into a Cartesian product of **trials**. `bench plan` shows the expanded trial plan.
- **FR-04 (Execution workflow)**: `bench submit` performs: (1) validate recipe; (2) generate Slurm scripts from `resources`/`partition`/`account`/`qos`; (3) run containers via Apptainer with `-B` binds and `--nv` if GPUs; (4) persist results under `$WORK/results/<scenario>/<trial_id>/`.
- **FR-05 (Apptainer & containers)**: Containers are pre-built/pulled on login nodes; recipes reference absolute `.sif` paths; runs reuse those paths in compute jobs.
- **FR-06 (Retries)**: Provide retry policy for failed trials (`max_retries`, exponential backoff) configurable in CLI or recipe metadata.
- **FR-07 (Metadata & provenance)**: Record `seed`, `git_commit`, Slurm IDs, node lists, container digest, and full **effective** configuration per trial.

### 4.2 Metrics & Artifacts
- **FR-09**: Collect **latency** (p50/p90/p99), **throughput** (ops/s or tokens/s), **resource usage** (GPU util/mem, CPU%, RAM), **errors** (error rate, timeouts).
- **FR-10**: Export metrics to `metrics.json` and `metrics.csv` per trial using the schema in §6.
- **FR-11**: Optionally expose Prometheus metrics via a file-based exporter when network endpoints are disallowed.
- **FR-12**: Generate summary tables and plots for each scenario as part of `bench report` into `reports/<scenario>/`.

### 4.3 Reproducibility & Config Management
- **FR-13**: Pin container digests when building `.sif`; record digest in each trial’s metadata.
- **FR-14**: Capture and inject random seeds where relevant; record in `meta.json`.
- **FR-15**: Persist the full `effective_config.yaml` for every trial (post-expansion).

### 4.4 Storage Benchmarks
- **FR-16 (File I/O)**: Sequential and random read/write tests with configurable file sizes and thread counts; report MB/s, IOPS, latency.
- **FR-17 (PostgreSQL)**: `psycopg2`-based micro-benchmarks (reads/writes, indexed lookups, batch inserts); report TPS, p95 latency, CPU/IO wait.
- **FR-18 (S3/Object)**: S3 SDK against S3-compatible endpoint; measure PUT/GET across object sizes (1KB–1GB) and concurrency; report ops/s, p95 latency, throughput MB/s.

### 4.5 Inference Servers
- **FR-19 (Triton)**: Support TensorRT/ONNX/PyTorch backends; test per-model batch sizes and dynamic shapes; report items/s or tokens/s, latency distribution, GPU util.
- **FR-20 (vLLM)**: Text-generation benchmarks (e.g., Mistral, Llama); vary prompt length, output length, batch size, concurrency.
- **FR-21**: Support **server** mode (driver → HTTP/gRPC) and **embedded** mode (driver launches server in-job and tears it down).

### 4.6 Vector Databases
- **FR-22**: Benchmark Chroma, FAISS, Milvus, Weaviate via a unified interface: build index, ingest dataset, run KNN queries under concurrency.
- **FR-23**: Report ingest throughput (vectors/s), query latency (p50/p95/p99), recall@K (if ground truth available), and memory footprint.
- **FR-24**: Allow single-node and distributed configurations where supported (e.g., Milvus cluster).

### 4.7 Load Generators & Scaling
- **FR-25**: Implement drivers that can run as (a) local Python processes, (b) Slurm array tasks, and (c) Dask/Spark executors when available.
- **FR-26**: Provide parameter sweeps over concurrency, batch size, model, dataset size, GPU count; produce scaling curves.

### 4.8 Reporting & Dashboards
- **FR-27**: Produce HTML/Markdown reports per scenario with tables, charts, and configuration snapshots.
- **FR-28**: Provide Grafana dashboards (JSON) when Prometheus is available; otherwise generate static plots.
- **FR-29**: Compare services side-by-side under identical load; highlight best/median/worst with statistical significance where applicable.

## 5. Non-Functional Requirements (NFR)
- **NFR-01 Performance**: Orchestrator overhead < 5% of end-to-end runtime for single-node tests.
- **NFR-02 Portability**: All components run via Apptainer without root; no Docker daemon on compute nodes.
- **NFR-03 Observability**: Logs are structured (JSONL) and timestamped; each trial has a unique ID; Slurm IDs and node lists are captured.
- **NFR-04 Reliability**: Failed trials are detectable and re-runnable; partial results do not corrupt summaries.
- **NFR-05 Usability**: Single command to reproduce a scenario: `bench submit -c <recipe>.yaml`.
- **NFR-06 Recipe Portability**: A valid recipe executes unchanged across MeluXina users/projects except for `account` and filesystem path adjustments.
- **NFR-07 Schema Stability**: Recipe fields and validation rules are versioned; changes are backward-compatible or accompanied by a migration note.

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
- **Storage**: PostgreSQL (mature RDBMS), S3-compatible object store (ubiquitous; SDK-driven; size & concurrency sweeps).
- **Vector DBs**: FAISS (baseline library), Milvus & Weaviate (cluster-ready), Chroma (lightweight). Each has container images and Python clients.

## 8. MeluXina Integration Requirements
- **MR-01**: Slurm partitions, QoS, and account are configurable per recipe (`partition`, `qos`, `account`).
- **MR-02**: Jobs request resources explicitly (`--gres=gpu:X`, `--cpus-per-task`, `--mem`, `--nodes`).
- **MR-03**: `module load apptainer` (or site-specific module) before `apptainer exec`.
- **MR-04**: `.sif` images are pre-built/pulled on login nodes and referenced by absolute path (e.g., `$WORK/containers/<name>.sif`).
- **MR-05**: Bind-mount datasets and results: `-B $WORK/data:/data -B $WORK/results:/results` (recipe-driven, not hard-coded).
- **MR-06**: Prefer embedded/localhost mode; if servers are exposed, document SSH tunneling and site policies.
- **MR-07**: Multi-node GPU runs set NCCL envs as needed; document any envs per recipe.

## 9. Security & Access
- User-scoped credentials only; no secrets in repo. Endpoints/keys read from environment or secrets files outside VCS.
- Containers run under user UID; no `--writable` images on compute nodes.

## 10. Example Recipe (YAML)
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
metadata:
  seed: 42
  git_commit: abc123
  notes: "first trial run"
```

## 11. Acceptance Criteria
- **AC-01**: Every challenge objective appears as at least one FR/MR item.
- **AC-02**: Requirements are parameterized and testable (explicit metrics, schema, and resource flags).
- **AC-02b (Recipe validation)**: Submitting a recipe with an invalid `service`, missing required field, or container path without `.sif` fails validation with an actionable error.
- **AC-03**: Target services list is justified and runnable via Apptainer on MeluXina.
- **AC-04**: A sample recipe (`§10`) runs end-to-end (dry-run acceptable before cluster access).
- **AC-04b (Sweeps)**: A recipe declaring sweep fields expands to multiple Slurm array tasks; `bench status` shows each **trial** separately.
- **AC-05 (Artifacts & provenance)**: Each trial directory contains `metrics.json/csv`, `meta.json` with digest/Slurm IDs, and `effective_config.yaml`.

## 12. Timeline Alignment (informative)
- **Month 1**: Finalize §2–§8; produce initial containers; dry-run `plan` and recipe parsing/validation.
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
- [ ] Recipe loader & **schema-based validation**
- [ ] Slurm generator (single/multi-node, arrays) driven by recipe fields
- [ ] Apptainer exec wrapper with recipe-driven bind mounts
- [ ] Drivers: storage (file/PG/S3), inference (Triton/vLLM), vector DBs (FAISS/Milvus/Weaviate/Chroma)
- [ ] Metrics capture & schema
- [ ] Reports & (optional) Grafana dashboards
- [ ] Sample recipes & example results
