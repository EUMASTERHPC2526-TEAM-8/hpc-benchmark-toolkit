#!/usr/bin/env python3
"""
HPC Module Configuration Loader

This module handles loading HPC module configurations from various sources:
1. Recipe YAML files (modules field)
2. Environment variables (HPC_MODULES)
3. Configuration files (hpc_modules.yaml)
4. Default configurations

Usage:
    from module_config import get_modules_for_recipe
    modules = get_modules_for_recipe(recipe_dict, service="ollama")
"""

import os
import yaml
from pathlib import Path
from typing import List, Dict, Optional


def load_hpc_modules_config(config_path: Optional[Path] = None) -> Dict:
    """
    Load HPC modules configuration from file.
    
    Args:
        config_path: Path to hpc_modules.yaml file. If None, looks in project root.
        
    Returns:
        Dictionary containing module configurations
    """
    if config_path is None:
        # Look for config file in project root
        project_root = Path(__file__).parent.parent
        config_path = project_root / "hpc_modules.yaml"
    
    if not config_path.exists():
        # Return default configuration
        return {
            "default": ["python3", "apptainer"],
            "meluxina": ["python/3.9", "apptainer/1.2.0"],
            "services": {
                "ollama": ["python3", "apptainer"],
                "vllm": ["python3", "apptainer", "cuda/11.8"]
            }
        }
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def get_modules_from_env() -> Optional[List[str]]:
    """
    Get modules from environment variable HPC_MODULES.
    
    Returns:
        List of modules or None if not set
    """
    modules_str = os.environ.get('HPC_MODULES')
    if not modules_str:
        return None
    
    # Support both comma-separated and space-separated
    if ',' in modules_str:
        return [m.strip() for m in modules_str.split(',')]
    else:
        return [m.strip() for m in modules_str.split()]


def get_modules_for_recipe(recipe: Dict, service: Optional[str] = None, 
                          cluster: Optional[str] = None) -> List[str]:
    """
    Get modules to load for a recipe, with fallback hierarchy.
    
    Priority order:
    1. Recipe modules field
    2. Environment variable HPC_MODULES
    3. Service-specific modules from config
    4. Cluster-specific modules from config
    5. Default modules from config
    
    Args:
        recipe: Recipe dictionary
        service: Service name (e.g., "ollama", "vllm")
        cluster: Cluster name (e.g., "meluxina", "pizdaint")
        
    Returns:
        List of modules to load
    """
    # 1. Check recipe modules field
    if "modules" in recipe and recipe["modules"]:
        return recipe["modules"]
    
    # 2. Check environment variable
    env_modules = get_modules_from_env()
    if env_modules:
        return env_modules
    
    # 3. Load config file
    config = load_hpc_modules_config()
    
    # 4. Check service-specific modules
    if service and "services" in config and service in config["services"]:
        return config["services"][service]
    
    # 5. Check cluster-specific modules
    if cluster and cluster in config:
        return config[cluster]
    
    # 6. Use default modules
    return config.get("default", ["python3", "apptainer"])


def generate_module_load_commands(modules: List[str]) -> str:
    """
    Generate bash commands to load modules.
    
    Args:
        modules: List of module names to load
        
    Returns:
        Bash script fragment for loading modules
    """
    if not modules:
        return ""
    
    commands = []
    commands.append("echo \"Loading HPC modules...\"")
    
    for module in modules:
        commands.append(f"module load {module}")
        commands.append(f"echo \"✓ Loaded module: {module}\"")
    
    # Verify Python is available
    commands.append("")
    commands.append("# Verify Python is available")
    commands.append("if ! command -v python3 &> /dev/null; then")
    commands.append("    echo \"✗ Python3 not found after module loading\"")
    commands.append("    echo \"  Available modules:\"")
    commands.append("    module avail 2>&1 | head -20")
    commands.append("    exit 1")
    commands.append("fi")
    commands.append("echo \"Python version: $(python3 --version)\"")
    
    return "\n".join(commands)


def main():
    """Test the module configuration system."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test HPC module configuration")
    parser.add_argument("--recipe", type=Path, help="Recipe file to test")
    parser.add_argument("--service", help="Service name")
    parser.add_argument("--cluster", help="Cluster name")
    parser.add_argument("--env", help="Environment variable value")
    
    args = parser.parse_args()
    
    # Set environment variable if provided
    if args.env:
        os.environ['HPC_MODULES'] = args.env
    
    # Load recipe if provided
    recipe = {}
    if args.recipe and args.recipe.exists():
        with open(args.recipe, 'r') as f:
            recipe = yaml.safe_load(f)
    
    # Get modules
    modules = get_modules_for_recipe(recipe, args.service, args.cluster)
    
    print(f"Modules to load: {modules}")
    print("\nGenerated commands:")
    print(generate_module_load_commands(modules))


if __name__ == "__main__":
    main()
