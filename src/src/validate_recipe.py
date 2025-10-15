#!/usr/bin/env python3
"""
This script validates benchmark recipe YAML files against the JSON schema.
Returns True if valid (or warnings accepted), False otherwise.

Usage:
    python validate_recipe.py recipe.yaml
    python validate_recipe.py recipe.yaml --no-interactive
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from enum import Enum

import yaml
from jsonschema import Draft7Validator, ValidationError, validators


class IssueLevel(Enum):
    """Severity levels for validation issues."""
    ERROR = "ERROR"
    WARNING = "WARNING"


class ValidationIssue:
    """Represents a validation issue with severity level."""
    
    def __init__(self, level: IssueLevel, message: str, path: str = "root"):
        self.level = level
        self.message = message
        self.path = path
    
    def __str__(self):
        return f"[{self.path}] {self.message}"
    
    def __repr__(self):
        return f"ValidationIssue({self.level}, {self.message})"


class RecipeValidator:
    """Validates benchmark recipes against JSON schema."""
    
    def __init__(self, schema_path: Optional[Path] = None):
        """
        Initialize validator with schema.
        
        Args:
            schema_path: Path to schema file. If None, uses default schema location.
        """
        if schema_path is None:
            # Default schema location
            schema_path = Path(__file__).parent / "schemas" / "recipe-format.yaml"
        
        self.schema_path = schema_path
        self.schema = self._load_schema()
        self.validator = self._create_validator()
    
    def _load_schema(self) -> Dict:
        """Load and parse schema file."""
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")
        
        with open(self.schema_path, 'r') as f:
            schema = yaml.safe_load(f)
        
        return schema
    
    def _create_validator(self) -> Draft7Validator:
        """Create JSON schema validator with custom error messages."""
        # Extend validator with default values
        def set_defaults(validator, properties, instance, schema):
            """Set default values for missing properties."""
            # Add null check for invalid YAML
            if instance is None or not isinstance(instance, dict):
                for error in Draft7Validator.VALIDATORS["properties"](
                    validator, properties, instance, schema
                ):
                    yield error
                return
            
            for property, subschema in properties.items():
                if "default" in subschema:
                    instance.setdefault(property, subschema["default"])
            
            for error in Draft7Validator.VALIDATORS["properties"](
                validator, properties, instance, schema
            ):
                yield error
        
        all_validators = dict(Draft7Validator.VALIDATORS)
        all_validators["properties"] = set_defaults
        
        ValidatorWithDefaults = validators.create(
            meta_schema=Draft7Validator.META_SCHEMA,
            validators=all_validators
        )
        
        return ValidatorWithDefaults(self.schema)

    def validate_recipe(self, recipe_path: Path) -> Tuple[bool, List[ValidationIssue], List[ValidationIssue]]:
        """
        Validate a single recipe file.
        
        Args:
            recipe_path: Path to recipe YAML file
            
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        # Check file exists
        if not recipe_path.exists():
            errors.append(ValidationIssue(
                IssueLevel.ERROR,
                f"Recipe file not found: {recipe_path}",
                "file"
            ))
            return False, errors, warnings
        
        # Load recipe
        try:
            with open(recipe_path, 'r') as f:
                recipe = yaml.safe_load(f)
        except yaml.YAMLError as e:
            errors.append(ValidationIssue(
                IssueLevel.ERROR,
                f"Invalid YAML syntax: {e}",
                "file"
            ))
            return False, errors, warnings
        except Exception as e:
            errors.append(ValidationIssue(
                IssueLevel.ERROR,
                f"Error reading file: {e}",
                "file"
            ))
            return False, errors, warnings
        
        # Validate against schema
        try:
            self.validator.validate(recipe)
        except ValidationError as e:
            errors.append(self._format_validation_error(e))
            # Collect all validation errors
            for error in self.validator.iter_errors(recipe):
                if error != e:  # Don't duplicate the main error
                    errors.append(self._format_validation_error(error))
        
        # Additional semantic validations
        semantic_errors, semantic_warnings = self._validate_semantics(recipe)
        errors.extend(semantic_errors)
        warnings.extend(semantic_warnings)
        
        is_valid = len(errors) == 0
        return is_valid, errors, warnings
    
    def _format_validation_error(self, error: ValidationError) -> ValidationIssue:
        """Format validation error with helpful context."""
        path = " -> ".join(str(p) for p in error.path) if error.path else "root"
        return ValidationIssue(IssueLevel.ERROR, error.message, path)
    
    def _validate_semantics(self, recipe: Dict) -> Tuple[List[ValidationIssue], List[ValidationIssue]]:
        """
        Perform additional semantic validations beyond schema.
        
        Args:
            recipe: Parsed recipe dictionary
            
        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []
        
        # Validate orchestration node allocation
        if "orchestration" in recipe:
            e, w = self._validate_node_allocation(recipe["orchestration"])
            errors.extend(e)
            warnings.extend(w)
        
        # Validate resource requirements
        if "resources" in recipe and "orchestration" in recipe:
            e, w = self._validate_resources(recipe)
            errors.extend(e)
            warnings.extend(w)
        
        # Validate workload configuration
        if "workload" in recipe:
            e, w = self._validate_workload(recipe["workload"])
            errors.extend(e)
            warnings.extend(w)
        
        # Validate client distribution strategy
        if "orchestration" in recipe:
            e, w = self._validate_client_distribution(recipe["orchestration"])
            errors.extend(e)
            warnings.extend(w)
        
        return errors, warnings
    
    def _validate_node_allocation(self, orchestration: Dict) -> Tuple[List[ValidationIssue], List[ValidationIssue]]:
        """Validate node allocation adds up correctly."""
        errors = []
        warnings = []
        
        if "node_allocation" not in orchestration:
            return errors, warnings
        
        allocation = orchestration["node_allocation"]
        
        server_nodes = allocation.get("servers", {}).get("nodes", 0)
        client_nodes = allocation.get("clients", {}).get("nodes", 0)
        monitor_nodes = allocation.get("monitors", {}).get("nodes", 0)
        
        calculated_total = server_nodes + client_nodes + monitor_nodes
        
        # ERRORS (blocking)
        if server_nodes < 1:
            errors.append(ValidationIssue(
                IssueLevel.ERROR,
                "At least 1 server node is required",
                "orchestration.node_allocation.servers.nodes"
            ))
        
        if client_nodes < 1:
            errors.append(ValidationIssue(
                IssueLevel.ERROR,
                "At least 1 client node is required",
                "orchestration.node_allocation.clients.nodes"
            ))
        
        if monitor_nodes != 1:
            errors.append(ValidationIssue(
                IssueLevel.ERROR,
                f"Exactly 1 monitor node is required (got {monitor_nodes})",
                "orchestration.node_allocation.monitors.nodes"
            ))
        
        if client_nodes > server_nodes * 10:
            warnings.append(ValidationIssue(
                IssueLevel.WARNING,
                f"Client-to-server ratio is very high ({client_nodes}:{server_nodes}). "
                "Consider if this many clients are necessary.",
                "orchestration.node_allocation"
            ))
        
        return errors, warnings
    
    def _validate_resources(self, recipe: Dict) -> Tuple[List[ValidationIssue], List[ValidationIssue]]:
        """Validate resource requirements are reasonable."""
        errors = []
        warnings = []
        
        resources = recipe["resources"]
        
        # Validate server resources
        if "servers" in resources:
            server_res = resources["servers"]
            
            # ERRORS
            if server_res.get("gpus", 0) < 0:
                errors.append(ValidationIssue(
                    IssueLevel.ERROR,
                    "GPU count cannot be negative",
                    "resources.servers.gpus"
                ))
            
            if server_res.get("cpus_per_task", 0) < 1:
                errors.append(ValidationIssue(
                    IssueLevel.ERROR,
                    "At least 1 CPU per task is required",
                    "resources.servers.cpus_per_task"
                ))
            
            if server_res.get("mem_gb", 0) < 1:
                errors.append(ValidationIssue(
                    IssueLevel.ERROR,
                    "At least 1GB memory is required",
                    "resources.servers.mem_gb"
                ))
            
            # WARNINGS
            if server_res.get("gpus", 0) > 8:
                warnings.append(ValidationIssue(
                    IssueLevel.WARNING,
                    f"{server_res['gpus']} GPUs per server node is unusually high. "
                    "Typical HPC nodes have 1-8 GPUs.",
                    "resources.servers.gpus"
                ))
            
            if server_res.get("mem_gb", 0) > 512:
                warnings.append(ValidationIssue(
                    IssueLevel.WARNING,
                    f"{server_res['mem_gb']}GB memory per server is very high. "
                    "Verify this is intentional.",
                    "resources.servers.mem_gb"
                ))
            
            if server_res.get("cpus_per_task", 0) > 128:
                warnings.append(ValidationIssue(
                    IssueLevel.WARNING,
                    f"{server_res['cpus_per_task']} CPUs per task is very high. "
                    "Typical nodes have 32-128 cores.",
                    "resources.servers.cpus_per_task"
                ))
        
        # Validate client resources
        if "clients" in resources:
            client_res = resources["clients"]
            
            # WARNINGS
            if client_res.get("gpus", 0) > 0:
                warnings.append(ValidationIssue(
                    IssueLevel.WARNING,
                    "Clients typically don't need GPUs. "
                    "Consider setting gpus: 0 unless doing client-side processing.",
                    "resources.clients.gpus"
                ))
            
            if client_res.get("mem_gb", 0) > 64:
                warnings.append(ValidationIssue(
                    IssueLevel.WARNING,
                    f"{client_res['mem_gb']}GB memory per client is high. "
                    "Clients typically need less memory than servers.",
                    "resources.clients.mem_gb"
                ))
        
        return errors, warnings
    
    def _validate_workload(self, workload: Dict) -> Tuple[List[ValidationIssue], List[ValidationIssue]]:
        """Validate workload configuration is consistent."""
        errors = []
        warnings = []
        
        component = workload.get("component")
        service = workload.get("service")
        
        # Validate component-service compatibility
        valid_services = {
            "inference": ["triton", "vllm"],
            "storage": ["postgres", "s3", "fileio"],
            "vectordb": ["milvus", "faiss", "weaviate", "chroma"]
        }
        
        # ERRORS
        if component in valid_services:
            if service not in valid_services[component]:
                errors.append(ValidationIssue(
                    IssueLevel.ERROR,
                    f"Service '{service}' is not valid for component '{component}'. "
                    f"Valid services: {valid_services[component]}",
                    "workload.service"
                ))
        
        # Validate inference-specific requirements
        if component == "inference":
            if "model" not in workload:
                errors.append(ValidationIssue(
                    IssueLevel.ERROR,
                    "Inference workload requires 'model' parameter",
                    "workload.model"
                ))
            if "prompt_len" not in workload:
                errors.append(ValidationIssue(
                    IssueLevel.ERROR,
                    "Inference workload requires 'prompt_len' parameter",
                    "workload.prompt_len"
                ))
        
        # Validate duration format
        if "duration" in workload:
            duration = workload["duration"]
            if not self._is_valid_duration(duration):
                errors.append(ValidationIssue(
                    IssueLevel.ERROR,
                    f"Invalid duration format: '{duration}'. "
                    "Use format like '10m', '2h', or '300s'",
                    "workload.duration"
                ))
        
        # WARNINGS
        if "duration" in workload:
            duration_val, duration_unit = self._parse_duration(workload["duration"])
            
            if duration_unit == 's' and duration_val < 60:
                warnings.append(ValidationIssue(
                    IssueLevel.WARNING,
                    f"Workload duration ({workload['duration']}) is very short. "
                    "Consider at least 1-2 minutes for stable metrics.",
                    "workload.duration"
                ))
            
            if duration_unit == 'h' and duration_val > 4:
                warnings.append(ValidationIssue(
                    IssueLevel.WARNING,
                    f"Workload duration ({workload['duration']}) is very long. "
                    "This will consume significant compute resources.",
                    "workload.duration"
                ))
        
        if "warmup" in workload:
            warmup = workload["warmup"]
            if self._is_valid_duration(warmup):
                warmup_val, warmup_unit = self._parse_duration(warmup)
                if warmup_unit == 's' and warmup_val < 10:
                    warnings.append(ValidationIssue(
                        IssueLevel.WARNING,
                        f"Warmup period ({warmup}) is very short. "
                        "Consider at least 30s for service stabilization.",
                        "workload.warmup"
                    ))
        
        if "target_rps" in workload:
            target_rps = workload["target_rps"]
            if target_rps > 10000:
                warnings.append(ValidationIssue(
                    IssueLevel.WARNING,
                    f"Target RPS ({target_rps}) is very high. "
                    "Ensure you have sufficient client nodes to generate this load.",
                    "workload.target_rps"
                ))
        
        return errors, warnings
    
    def _validate_client_distribution(self, orchestration: Dict) -> Tuple[List[ValidationIssue], List[ValidationIssue]]:
        """Validate client distribution strategy is properly configured."""
        errors = []
        warnings = []
        
        if "node_allocation" not in orchestration:
            return errors, warnings
        
        clients = orchestration["node_allocation"].get("clients", {})
        strategy = clients.get("distribution_strategy", "round-robin")
        
        # ERRORS
        if strategy == "static" and "target_mapping" not in clients:
            errors.append(ValidationIssue(
                IssueLevel.ERROR,
                "Static distribution strategy requires 'target_mapping' configuration",
                "orchestration.node_allocation.clients.target_mapping"
            ))
        
        # WARNINGS
        clients_per_node = clients.get("clients_per_node", 1)
        if clients_per_node > 100:
            warnings.append(ValidationIssue(
                IssueLevel.WARNING,
                f"{clients_per_node} clients per node is very high. "
                "This may cause resource contention and skewed results.",
                "orchestration.node_allocation.clients.clients_per_node"
            ))
        
        if clients_per_node == 1:
            warnings.append(ValidationIssue(
                IssueLevel.WARNING,
                "Only 1 client per node may not generate sufficient load. "
                "Consider increasing clients_per_node for better resource utilization.",
                "orchestration.node_allocation.clients.clients_per_node"
            ))
        
        return errors, warnings
    
    @staticmethod
    def _is_valid_duration(duration: str) -> bool:
        """Check if duration string is valid (e.g., '10m', '2h', '300s')."""
        import re
        pattern = r'^\d+[smh]$'
        return bool(re.match(pattern, duration))
    
    @staticmethod
    def _parse_duration(duration: str) -> Tuple[int, str]:
        """Parse duration string into value and unit."""
        import re
        match = re.match(r'^(\d+)([smh])$', duration)
        if match:
            return int(match.group(1)), match.group(2)
        return 0, 's'


def print_issues(issues: List[ValidationIssue], level: IssueLevel, color: bool = True):
    """
    Print validation issues with optional color coding.
    
    Args:
        issues: List of validation issues
        level: Issue level to filter by
        color: Whether to use ANSI color codes
    """
    # ANSI color codes
    RED = '\033[91m' if color else ''
    YELLOW = '\033[93m' if color else ''
    RESET = '\033[0m' if color else ''
    
    filtered = [i for i in issues if i.level == level]
    if not filtered:
        return
    
    if level == IssueLevel.ERROR:
        symbol = "✗"
        color_code = RED
        label = "ERRORS"
    else:
        symbol = "⚠"
        color_code = YELLOW
        label = "WARNINGS"
    
    print(f"\n{color_code}{symbol} {label}:{RESET}")
    for issue in filtered:
        print(f"  {color_code}{symbol}{RESET} {issue}")


def ask_user_confirmation(warnings: List[ValidationIssue]) -> bool:
    """
    Ask user if they want to proceed despite warnings.
    
    Args:
        warnings: List of warning issues
        
    Returns:
        True if user wants to proceed, False otherwise
    """
    if not warnings:
        return True
    
    print(f"\n{'='*70}")
    print(f"Found {len(warnings)} warning(s). These are not blocking but should be reviewed.")
    
    while True:
        response = input("\nDo you want to proceed anyway? [y/N]: ").strip().lower()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no', '']:
            return False
        else:
            print("Please answer 'y' or 'n'")


def validate_single_recipe(
    recipe_path: Path,
    schema_path: Optional[Path] = None,
    interactive: bool = True,
    color: bool = True,
    verbose: bool = False
) -> bool:
    """
    Validate a single recipe file.
    
    Args:
        recipe_path: Path to recipe YAML file
        schema_path: Optional custom schema path
        interactive: Ask for confirmation on warnings
        color: Use ANSI color codes for output
        verbose: Print detailed output
        
    Returns:
        True if validation passed (or warnings accepted), False otherwise
    """
    validator = RecipeValidator(schema_path)
    
    GREEN = '\033[92m' if color else ''
    RED = '\033[91m' if color else ''
    YELLOW = '\033[93m' if color else ''
    RESET = '\033[0m' if color else ''
    
    if verbose:
        print(f"\n{'='*70}")
        print(f"Validating: {recipe_path}")
        print(f"{'='*70}")
    
    is_valid, errors, warnings = validator.validate_recipe(recipe_path)
    
    # Print errors
    if errors:
        print_issues(errors, IssueLevel.ERROR, color)
    
    # Print warnings
    if warnings:
        print_issues(warnings, IssueLevel.WARNING, color)
    
    if is_valid:
        if warnings:
            # Has warnings but no errors
            if interactive:
                if ask_user_confirmation(warnings):
                    if verbose:
                        print(f"\n{GREEN}✓ Recipe validated with warnings (user accepted){RESET}")
                    return True
                else:
                    if verbose:
                        print(f"\n{YELLOW}⊘ Recipe skipped by user due to warnings{RESET}")
                    return False
            else:
                if verbose:
                    print(f"\n{GREEN}✓ Recipe validated with warnings{RESET}")
                return True
        else:
            # No errors, no warnings
            if verbose:
                print(f"\n{GREEN}✓ Recipe is valid{RESET}")
            return True
    else:
        # Has errors
        if verbose:
            print(f"\n{RED}✗ Recipe is invalid{RESET}")
        return False


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Validate benchmark recipes against schema",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate single recipe (interactive)
  %(prog)s recipe.yaml
  
  # Validate without asking about warnings
  %(prog)s recipe.yaml --no-interactive
  
  # Validate with custom schema
  %(prog)s recipe.yaml --schema my_schema.yaml
  
  # Quiet mode (only return exit code)
  %(prog)s recipe.yaml --quiet
        """
    )
    
    parser.add_argument(
        "recipe",
        type=Path,
        help="Recipe file to validate"
    )
    
    parser.add_argument(
        "--schema",
        type=Path,
        help="Path to custom schema file (default: schemas/recipe-format.yaml)"
    )
    
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Don't ask for confirmation on warnings (treat warnings as non-blocking)"
    )
    
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output"
    )
    
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress all output (only return exit code)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed validation results"
    )
    
    args = parser.parse_args()
    
    # Validate recipe
    try:
        is_valid = validate_single_recipe(
            args.recipe,
            args.schema,
            interactive=not args.no_interactive,
            color=not args.no_color,
            verbose=args.verbose and not args.quiet
        )
        
        # Exit code: 0 if valid, 1 if invalid
        sys.exit(0 if is_valid else 1)
        
    except FileNotFoundError as e:
        if not args.quiet:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        if not args.quiet:
            print(f"Unexpected error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()