#!/usr/bin/env python3
"""
Comprehensive test script for recipe validator.
Tests various validation scenarios with errors, warnings, and user interactions.
"""
import sys
from pathlib import Path
from unittest.mock import patch

# Make sure the project root is on sys.path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from validate_recipe import RecipeValidator, validate_single_recipe


class Colors:
    """ANSI color codes for test output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class TestRunner:
    """Test runner for recipe validation."""
    
    def __init__(self):
        self.test_dir = Path(__file__).parent / "test_recipes"
        self.validator = None
        self.passed = 0
        self.failed = 0
    
    def setup(self):
        """Setup test environment."""
        print(f"{Colors.BOLD}{'='*70}{Colors.RESET}")
        print(f"{Colors.BOLD}Recipe Validator Test Suite{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")
        
        # Create validator
        try:
            self.validator = RecipeValidator()
            print(f"{Colors.GREEN}✓{Colors.RESET} RecipeValidator initialized successfully\n")
        except Exception as e:
            print(f"{Colors.RED}✗{Colors.RESET} Failed to create RecipeValidator: {e}")
            sys.exit(1)
    
    def run_test(self, test_name: str, recipe_file: str, 
                 expected_valid: bool, expected_errors: int, 
                 expected_warnings: int, user_response: str = None,
                 description: str = ""):
        """
        Run a single validation test.
        
        Args:
            test_name: Name of the test
            recipe_file: Recipe filename (relative to test_recipes/)
            expected_valid: Whether recipe should be valid
            expected_errors: Expected number of errors
            expected_warnings: Expected number of warnings
            user_response: Mock user input for warnings ('y' or 'n')
            description: Test description
        """
        print(f"{Colors.BLUE}{Colors.BOLD}Test: {test_name}{Colors.RESET}")
        if description:
            print(f"  {description}")
        print(f"  Recipe: {recipe_file}")
        
        recipe_path = self.test_dir / recipe_file
        
        if not recipe_path.exists():
            print(f"{Colors.RED}✗ FAILED{Colors.RESET} - Recipe file not found: {recipe_path}\n")
            self.failed += 1
            return
        
        # Run validation
        is_valid, errors, warnings = self.validator.validate_recipe(recipe_path)
        
        # Check results
        errors_match = len(errors) == expected_errors
        warnings_match = len(warnings) == expected_warnings
        
        # For tests with user interaction
        if user_response and warnings:
            with patch('builtins.input', return_value=user_response):
                final_valid = validate_single_recipe(
                    recipe_path,
                    interactive=True,
                    color=False,
                    verbose=False
                )
        else:
            final_valid = is_valid
        
        valid_match = final_valid == expected_valid
        
        # Print results
        print(f"  Expected: valid={expected_valid}, errors={expected_errors}, warnings={expected_warnings}")
        print(f"  Actual:   valid={final_valid}, errors={len(errors)}, warnings={len(warnings)}")
        
        # Show errors
        if errors:
            print(f"  {Colors.RED}Errors:{Colors.RESET}")
            for error in errors:
                print(f"    - {error}")
        
        # Show warnings
        if warnings:
            print(f"  {Colors.YELLOW}Warnings:{Colors.RESET}")
            for warning in warnings:
                print(f"    - {warning}")
        
        # Test result
        if valid_match and errors_match and warnings_match:
            print(f"{Colors.GREEN}✓ PASSED{Colors.RESET}\n")
            self.passed += 1
        else:
            print(f"{Colors.RED}✗ FAILED{Colors.RESET}")
            if not valid_match:
                print(f"  Validity mismatch: expected {expected_valid}, got {final_valid}")
            if not errors_match:
                print(f"  Error count mismatch: expected {expected_errors}, got {len(errors)}")
            if not warnings_match:
                print(f"  Warning count mismatch: expected {expected_warnings}, got {len(warnings)}")
            print()
            self.failed += 1
    
    def print_summary(self):
        """Print test summary."""
        total = self.passed + self.failed
        print(f"{Colors.BOLD}{'='*70}{Colors.RESET}")
        print(f"{Colors.BOLD}Test Summary{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*70}{Colors.RESET}")
        print(f"Total tests:  {total}")
        print(f"{Colors.GREEN}Passed:{Colors.RESET}       {self.passed}")
        print(f"{Colors.RED}Failed:{Colors.RESET}       {self.failed}")
        print(f"{Colors.BOLD}{'='*70}{Colors.RESET}")
        
        if self.failed == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}All tests passed!{Colors.RESET}\n")
            return 0
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}Some tests failed.{Colors.RESET}\n")
            return 1

def main():
    """Run all validation tests."""
    runner = TestRunner()
    runner.setup()
    
    # Test 1: Perfect recipe (no errors, no warnings)
    runner.run_test(
        test_name="Perfect Recipe",
        recipe_file="perfect.yaml",
        expected_valid=True,
        expected_errors=0,
        expected_warnings=0,
        description="Recipe with optimal configuration, no issues"
    )
    
    # Test 2: Recipe with only warnings (user accepts)
    runner.run_test(
        test_name="Warnings Only - User Accepts",
        recipe_file="warnings_only.yaml",
        expected_valid=True,
        expected_errors=0,
        expected_warnings=9,  # Updated count
        user_response='y',
        description="Recipe with warnings, user chooses to proceed"
    )
    
    # Test 3: Recipe with only warnings (user rejects)
    runner.run_test(
        test_name="Warnings Only - User Rejects",
        recipe_file="warnings_only.yaml",
        expected_valid=False,
        expected_errors=0,
        expected_warnings=9,  # Updated count
        user_response='n',
        description="Recipe with warnings, user chooses not to proceed"
    )
    
    # Test 4: Recipe with only errors
    runner.run_test(
        test_name="Errors Only",
        recipe_file="errors_only.yaml",
        expected_valid=False,
        expected_errors=14,  # Updated count (includes schema + semantic errors)
        expected_warnings=1,  # Has 1 warning about duration
        description="Recipe with blocking errors"
    )
    
    # Test 5: Recipe with both errors and warnings
    runner.run_test(
        test_name="Errors and Warnings",
        recipe_file="errors_and_warnings.yaml",
        expected_valid=False,
        expected_errors=8,  # Updated count
        expected_warnings=3,  # Updated count
        description="Recipe with both errors and warnings"
    )
    
    # Test 6: Invalid YAML syntax
    runner.run_test(
        test_name="Invalid YAML Syntax",
        recipe_file="invalid.yaml",
        expected_valid=False,
        expected_errors=1,
        expected_warnings=0,
        description="File with invalid YAML syntax"
    )
    
    # Test 7: Missing required fields
    runner.run_test(
        test_name="Missing Required Fields",
        recipe_file="missing_required.yaml",
        expected_valid=False,
        expected_errors=4,  # Schema will report missing fields
        expected_warnings=0,
        description="Recipe missing required top-level fields"
    )
    
    # Test 8: Edge case - minimal valid recipe
    runner.run_test(
        test_name="Minimal Valid Recipe",
        recipe_file="minimal_valid.yaml",
        expected_valid=True,
        expected_errors=0,
        expected_warnings=0,
        user_response='y',
        description="Minimal recipe with only required fields"
    )
    
    # Print summary and exit
    exit_code = runner.print_summary()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()