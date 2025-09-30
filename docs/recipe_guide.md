# Benchmark Recipe Guide

This guide explains how to write configuration files ("recipes") for the benchmarking framework. Recipes are YAML files that describe what workload to run, what resources to request from Slurm, and how to manage artifacts and results.

---

## 1. Basic Structure

A recipe is a YAML file with the following top-level fields:

```yaml
scenario: unique_name
partition: gpu
account: pXXXXX
qos: normal
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
  git_commit: abc1234
  notes: first trial run
```

---

## 2. Field Explanations

### scenario
Unique identifier for the benchmark scenario. Appears in results directories.

### partition / account / qos
Slurm scheduling parameters:
- `partition`: Which Slurm partition (e.g., `gpu`, `cpu`).
- `account`: Your MeluXina project account (e.g., `p123456`).
- `qos`: Optional QoS class (e.g., `normal`, `debug`).

### repetitions
How many times to repeat each trial.

### resources
Maps directly to Slurm flags:
- `nodes` → `--nodes`
- `gpus` → `--gres=gpu:X`
- `cpus_per_task` → `--cpus-per-task`
- `mem_gb` → `--mem`

### workload
Defines the benchmark workload.
- `component`: one of `storage`, `inference`, `vectordb`.
- `service`: specific system under test (`triton`, `vllm`, `postgres`, `s3`, `milvus`, `faiss`, `weaviate`, `chroma`, `fileio`).
- Optional workload-specific fields:
  - `model` (inference only)
  - `prompt_len`, `gen_tokens` (inference only)
  - `batch` and `concurrency` (all clients)
  - `dataset` (storage/vector DBs)

### artifacts
Paths to necessary files:
- `container`: Absolute path to the `.sif` container (pre-built on login node).
- `dataset`: Input dataset file, if needed.

### binds
Bind mounts for Apptainer, mapping host directories into the container.

### metadata
Optional metadata for reproducibility and tracking:
- `seed`: Random seed.
- `git_commit`: Commit hash of the benchmark code.
- `notes`: Free-form notes.

---

## 3. Validation Rules

- `scenario`, `partition`, `account`, `resources`, and `workload` are required.
- Services must be one of the allowed list.
- Resource values must be positive integers.
- Container paths must end in `.sif`.
- If `gpus > 0`, partition should be `gpu`.

Validation is performed by the **Interface module** using the schema in `schemas/recipe-format.yaml`.

---

## 4. Parameter Sweeps

Arrays in fields (`batch: [1,4,8]`, `concurrency: [1,8,32]`) expand into multiple trials automatically. Each trial is a unique combination of parameters.

---

## 5. Execution Workflow

1. User runs `bench submit -c config.yaml`.
2. CLI validates config against schema.
3. Orchestrator generates Slurm scripts with specified resources.
4. Containers are run with Apptainer, using provided binds.
5. Results are saved under `$WORK/results/<scenario>/<trial_id>/`.
6. Metadata, metrics, and logs are stored alongside.

---

## 6. Example Recipes

### Inference (vLLM)
```yaml
scenario: llm_vllm_baseline
partition: gpu
account: p123456
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

### Storage (PostgreSQL)
```yaml
scenario: postgres_micro
partition: cpu
account: p123456
resources:
  nodes: 1
  gpus: 0
  cpus_per_task: 4
  mem_gb: 16
workload:
  component: storage
  service: postgres
  dataset: $WORK/data/pg_benchmark.sql
artifacts:
  container: $WORK/containers/postgres.sif
binds:
  - "$WORK/data:/data"
  - "$WORK/results:/results"
```

---

## 7. Best Practices
- Keep scenarios small for debugging; scale up once validated.
- Pin containers by digest for reproducibility.
- Always include `metadata.seed` for experiments with randomness.
- Store large datasets in `$WORK`, not `$HOME`.

---

This specification ensures that all experiments are **reproducible**, **validated**, and **portable** across MeluXina and other HPC systems.

