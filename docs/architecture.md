# System Architecture Document

**Version:** 1.0  
**Date:** September 29, 2025

## 1. Introduction

This document describes the system architecture for the unified benchmarking framework. It focuses on the high-level design, component structure, data flows, and integration points. For other aspects of the project, see:

- Project overview and getting started: [`README.md`](../README.md)
- Technology specifications: [`tech-stack.md`](tech-stack.md)
- Recipe format details: [`recipe-guide.md`](recipe-guide.md)

## 2. Architectural Overview

### 2.1 High-Level Design

The framework consists of five core modules orchestrated through a unified interface:

```
                         User
                          │
                          ▼
                    Interface Layer
              (Recipe Validation & Orchestration)
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
    ┌─────────┐     ┌─────────┐     ┌─────────┐
    │ Servers │     │ Clients │     │ Monitors│
    └────┬────┘     └────┬────┘     └────┬────┘
         │               │               │
         └───────────────┴───────────────┘
                         │
                         ▼
              Cluster (SLURM / Kubernetes)
```

### 2.2 Design Principles

- **Modularity**: Each component operates independently with clear interfaces
- **Recipe-Driven**: All experiments defined through declarative configuration files
- **Cluster Agnostic**: Works with both SLURM and Kubernetes
- **Observable**: Real-time monitoring and logging throughout execution
- **Reproducible**: Complete experiment tracking with versioned configurations

### 2.3 Visual Architecture

For detailed visual representations of the system:

- **System Architecture Diagram**: [`../diagrams/system-overview.mmd`](../diagrams/system-overview.mmd)
  - High-level component overview
  - Module interactions
  - Data storage relationships

- **Data Flow Diagram**: [`../diagrams/data-flow.mmd`](../diagrams/data-flow.mmd)
  - Experiment execution lifecycle
  - Service container lifecycle
  - Parallel client request patterns

## 3. Core Components

### 3.1 Servers Module

**Purpose**: Manages the lifecycle of services being benchmarked.

**Responsibilities**:
- Deploy and configure target services (storage, inference engines, vector databases)
- Support single-node and multi-node deployments
- Provide health checking and service readiness verification
- Expose service endpoints for client connections

**Key Operations**:
- Start/stop services with configurable parameters
- List available and running services
- Health checking and readiness verification
- Service endpoint management

### 3.2 Clients Module

**Purpose**: Generates load against deployed services to measure performance.

**Responsibilities**:
- Launch distributed client workloads across compute nodes
- Implement service-specific benchmark protocols
- Collect performance metrics
- Support variable load patterns

**Key Operations**:
- Launch and manage distributed client workloads
- Configure variable load patterns
- Collect performance metrics from client perspective
- Control client lifecycle and status monitoring

### 3.3 Monitors Module

**Purpose**: Collects real-time performance metrics during experiments.

**Responsibilities**:
- Scrape metrics from services and infrastructure
- Track custom application-level metrics
- Aggregate and store data
- Generate visualization-ready datasets

**Key Operations**:
- Initialize and manage monitoring instances
- Collect and aggregate metrics
- Generate visualization-ready datasets
- Construct analysis reports from collected data

### 3.4 Logs Module

**Purpose**: Centralized collection and management of experiment logs.

**Responsibilities**:
- Aggregate logs from all services and clients
- Provide structured log storage and retrieval
- Enable log-based debugging and analysis
- Support log correlation across distributed components

**Key Operations**:
- Aggregate logs from distributed components
- Provide structured log storage and retrieval
- Enable filtering and correlation across services
- Export logs for offline analysis

**Log Categories**:
- **Application Logs**: Service output, application-specific logs
- **System Logs**: SLURM job output
- **Benchmark Logs**: Client execution traces, error details
- **Infrastructure Logs**: Cluster scheduler logs, network events

### 3.5 Interface Module

**Purpose**: Unified control plane for experiment orchestration.

**Responsibilities**:
- Parse and validate benchmark recipes
- Orchestrate multi-component experiment execution
- Provide user interaction through multiple interfaces
- Coordinate data flow between modules
- Generate comprehensive experiment reports

**Key Operations**:
- Recipe parsing and validation
- Experiment orchestration and lifecycle management
- Multi-interface support (CLI, API, Web UI)
- Report generation and data export

## 4. Experiment Workflow

### 4.1 Typical Execution Flow

```
1. User submits recipe
2. Interface validates configuration
3. Servers module deploys service
4. Monitors and Logs modules initialize
5. Clients module launches workload
6. Execution phase (services process requests)
7. Continuous metric and log collection
8. Teardown (stop clients, services, monitoring)
9. Report generation and data export
```

### 4.2 Data Storage Structure

```
/experiments/{experiment_id}/
├── recipe.yaml              # Experiment configuration
├── metadata.out             # Timestamps, user, cluster info
├── metrics/
│   ├── prometheus_data/     # Time-series metrics
│   └── summary.json         # Aggregated statistics
├── logs/                    # Logs
└── reports/
    ├── report.pdf           # Static report
    └── raw_results.csv      # Raw data export
```
## 5. Error Handling

### 5.1 Failure Recovery

| Scenario | Detection | Recovery |
|----------|-----------|----------|
| Service crash | Health check timeout | Restart with configurable retries |
| Client failure | Log errors | Continue with remaining clients |
| Monitor crash | Metric gaps | Restart monitor, mark data gap |
| Node failure | Cluster events | Reschedule on healthy nodes |
| Invalid recipe | Parse-time validation | Reject experiment, return errors |

### 5.2 Graceful Degradation

- Monitoring failure: Continue experiment with warning
- Logging failure: Attempt recovery, continue execution
- Partial client failure: Complete with reduced load