# EUMaster4HPC Unified Benchmarking Framework

**Version:** 1.0  
**Date:** September 29, 2025

## Overview

A unified benchmarking framework for evaluating AI Factory components on the MeluXina supercomputer. The framework enables systematic performance evaluation of storage systems, inference engines, and retrieval systems using both SLURM and Kubernetes orchestration.

### Key Features

- **Recipe-Driven Configuration**: Declarative YAML-based experiment definitions
- **Multi-Orchestrator Support**: Works with both SLURM and Kubernetes
- **Real-Time Monitoring**: Comprehensive metrics collection and visualization
- **Modular Architecture**: Five independent modules (Servers, Clients, Monitors, Logs, Interface)
- **Reproducible Experiments**: Complete experiment tracking and versioning

## Documentation Structure

### Core Documentation

- **[`docs/architecture.md`](docs/architecture.md)** - System Architecture Document
  - High-level system design
  - Component descriptions and responsibilities
  - Data flows and integration points
  - Design decisions and trade-offs

- **[`docs/tech-stack.md`](docs/tech-stack.md)** - Technology Stack Document
  - Programming languages and frameworks
  - Dependencies and libraries
  - External services and tools
  - Development environment setup

- **[`docs/recipe-guide.md`](docs/recipe-guide.md)** - Recipe Configuration Guide
  - Recipe format and structure
  - Configuration options and parameters
  - Example recipes for common scenarios
  - Best practices and tips

- **[`docs/requirements.md`](docs/requirements.md)** - Technical Requirements Document
  - Functional and non-functional requirements
  - Module specifications
  - Performance criteria

### Diagrams

- **System Architecture Diagram**: [`./diagrams/system-overview.mmd`](./diagrams/system-overview.mmd)
  - High-level component overview
  - Module interactions
  - Data storage relationships

- **Data Flow Diagram**: [`./diagrams/data-flow.mmd`](./diagrams/data-flow.mmd)
  - Experiment execution lifecycle
  - Service container lifecycle
  - Parallel client request patterns

### API and Schema Documentation

- **[`schemas/recipe-format.yaml`](schemas/recipe-format.yaml)** - Recipe Schema Definition
  - JSON Schema for recipe validation
  - Field descriptions and constraints
  - Required vs. optional parameters

### Deployment Documentation

- **[`docs/deployment.md`](docs/deployment.md)** - Installation & Setup *(TODO)*
  - Installation instructions
  - Configuration steps
  - Cluster-specific setup (SLURM/Kubernetes)
  - Environment requirements

## Project Structure

```
repo/
├── docs/                       # Documentation
│   ├── architecture.md         # System architecture
│   ├── tech-stack.md           # Technology specifications
│   ├── recipe-guide.md         # Recipe format guide
│   ├── requirements.md         # Technical requirements
│   └── deployment.md           # Installation guide (TODO)
│
├── schemas/                    # Configuration schemas
│   └── recipe-format.yaml      # Recipe JSON schema
│
├── diagrams/                   # Architecture diagrams
│   ├── data-flow.mmd           # Data flow schema
│   └── system-overview.mmd     # High-level architecture
│
└── README.md                   # This file
```