"""
General entry point for client workload execution.
Selects and runs the correct service-specific executor using the factory/registry.
"""
import argparse
from benchmark.service_factory import ServiceFactory
import benchmark.service_registry

def main():
    parser = argparse.ArgumentParser(description="General Workload Executor")
    parser.add_argument("--service", type=str, required=True, help="Service type")
    parser.add_argument("--port", type=int, default=6000, help="Port to run workload executor")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout in seconds")
    args = parser.parse_args()

    executor = ServiceFactory.create_workload_executor(args.service, port=args.port)
    executor.run()

if __name__ == "__main__":
    main()
