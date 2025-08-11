#!/usr/bin/env python3
"""
Workflow Validation and Testing System
Comprehensive validation, testing, and quality assurance for workflow definitions and executions.
"""
import os
import sys
import json
import yaml
import asyncio
import tempfile
import shutil
import subprocess
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import logging

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from parser.workflow_parser import WorkflowParser, WorkflowDefinition, WorkflowStep
from engine.workflow_engine import WorkflowEngine, StepResult, ExecutionStatus
from observability.workflow_telemetry import get_workflow_telemetry, WorkflowTelemetryCollector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """Represents a workflow validation issue"""
    severity: str  # error, warning, info
    category: str  # syntax, logic, performance, security
    message: str
    location: Optional[str] = None
    suggestion: Optional[str] = None
    code: Optional[str] = None


@dataclass
class WorkflowTestCase:
    """Test case for workflow execution"""
    name: str
    description: str
    inputs: Dict[str, Any]
    expected_outputs: Dict[str, Any] = field(default_factory=dict)
    expected_status: str = "completed"
    expected_steps: Optional[List[str]] = None
    mock_responses: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 300
    tags: List[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of workflow validation"""
    valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    score: float = 0.0
    recommendations: List[str] = field(default_factory=list)
    
    def add_issue(self, issue: ValidationIssue):
        """Add validation issue"""
        self.issues.append(issue)
        if issue.severity == "error":
            self.valid = False
    
    def get_issues_by_severity(self, severity: str) -> List[ValidationIssue]:
        """Get issues by severity level"""
        return [issue for issue in self.issues if issue.severity == severity]
    
    def get_issues_by_category(self, category: str) -> List[ValidationIssue]:
        """Get issues by category"""
        return [issue for issue in self.issues if issue.category == category]


class WorkflowValidator:
    """Comprehensive workflow validation system"""
    
    def __init__(self, parser: Optional[WorkflowParser] = None):
        self.parser = parser or WorkflowParser()
        self.validation_rules = self._load_validation_rules()
    
    def validate_workflow(self, workflow: WorkflowDefinition) -> ValidationResult:
        """Perform comprehensive workflow validation"""
        result = ValidationResult(valid=True)
        
        # Syntax validation
        self._validate_syntax(workflow, result)
        
        # Logic validation
        self._validate_logic(workflow, result)
        
        # Performance validation
        self._validate_performance(workflow, result)
        
        # Security validation
        self._validate_security(workflow, result)
        
        # Best practices validation
        self._validate_best_practices(workflow, result)
        
        # Calculate overall score
        result.score = self._calculate_score(result)
        
        # Generate recommendations
        result.recommendations = self._generate_recommendations(result)
        
        return result
    
    def _validate_syntax(self, workflow: WorkflowDefinition, result: ValidationResult):
        """Validate workflow syntax and structure"""
        
        # Check required fields
        if not workflow.name:
            result.add_issue(ValidationIssue(
                severity="error",
                category="syntax",
                message="Workflow name is required",
                suggestion="Add a 'name' field to the workflow definition"
            ))
        
        if not workflow.version:
            result.add_issue(ValidationIssue(
                severity="error", 
                category="syntax",
                message="Workflow version is required",
                suggestion="Add a 'version' field with semantic versioning (e.g., '1.0.0')"
            ))
        
        # Validate step IDs
        step_ids = [step.id for step in workflow.steps]
        duplicate_ids = set([x for x in step_ids if step_ids.count(x) > 1])
        
        if duplicate_ids:
            result.add_issue(ValidationIssue(
                severity="error",
                category="syntax",
                message=f"Duplicate step IDs found: {', '.join(duplicate_ids)}",
                suggestion="Ensure all step IDs are unique within the workflow"
            ))
        
        # Validate step names follow conventions
        invalid_step_ids = []
        for step_id in step_ids:
            if not step_id.replace('_', '').replace('-', '').isalnum():
                invalid_step_ids.append(step_id)
        
        if invalid_step_ids:
            result.add_issue(ValidationIssue(
                severity="warning",
                category="syntax", 
                message=f"Step IDs should use alphanumeric characters, hyphens, or underscores: {', '.join(invalid_step_ids)}",
                suggestion="Use kebab-case or snake_case for step IDs"
            ))
    
    def _validate_logic(self, workflow: WorkflowDefinition, result: ValidationResult):
        """Validate workflow logic and dependencies"""
        
        step_ids = set(step.id for step in workflow.steps)
        
        # Check dependency references
        for step in workflow.steps:
            for dependency in step.depends_on:
                if dependency not in step_ids:
                    result.add_issue(ValidationIssue(
                        severity="error",
                        category="logic",
                        message=f"Step '{step.id}' depends on unknown step '{dependency}'",
                        location=f"step:{step.id}",
                        suggestion=f"Ensure step '{dependency}' exists or remove the dependency"
                    ))
        
        # Check for circular dependencies (already done in parser, but double-check)
        if len(workflow.execution_order) != len(workflow.steps):
            result.add_issue(ValidationIssue(
                severity="error",
                category="logic",
                message="Circular dependency detected in workflow steps",
                suggestion="Review step dependencies to ensure no circular references"
            ))
        
        # Check output references
        for output_name, output_config in workflow.outputs.items():
            if output_config.from_step:
                step_ref = output_config.from_step.split('.')[0]
                if step_ref not in step_ids:
                    result.add_issue(ValidationIssue(
                        severity="error",
                        category="logic",
                        message=f"Workflow output '{output_name}' references unknown step '{step_ref}'",
                        suggestion=f"Ensure step '{step_ref}' exists or update the output reference"
                    ))
        
        # Check for unused steps (no dependents and no outputs referenced)
        used_steps = set(workflow.execution_order[:1])  # First step is always used
        
        for step in workflow.steps:
            for dependency in step.depends_on:
                used_steps.add(dependency)
        
        for output_config in workflow.outputs.values():
            if output_config.from_step:
                step_ref = output_config.from_step.split('.')[0]
                used_steps.add(step_ref)
        
        unused_steps = step_ids - used_steps
        if unused_steps:
            result.add_issue(ValidationIssue(
                severity="warning",
                category="logic",
                message=f"Potentially unused steps detected: {', '.join(unused_steps)}",
                suggestion="Consider removing unused steps or connecting them to the workflow"
            ))
    
    def _validate_performance(self, workflow: WorkflowDefinition, result: ValidationResult):
        """Validate workflow performance characteristics"""
        
        # Check for excessive step count
        if len(workflow.steps) > 50:
            result.add_issue(ValidationIssue(
                severity="warning",
                category="performance",
                message=f"Workflow has {len(workflow.steps)} steps, which may impact performance",
                suggestion="Consider breaking large workflows into smaller, reusable workflows"
            ))
        
        # Check for long-running steps without timeouts
        for step in workflow.steps:
            if step.type in ['claude_code', 'shell'] and step.timeout > 1800:  # 30 minutes
                result.add_issue(ValidationIssue(
                    severity="warning",
                    category="performance", 
                    message=f"Step '{step.id}' has a long timeout ({step.timeout}s)",
                    location=f"step:{step.id}",
                    suggestion="Consider reducing timeout or splitting into smaller operations"
                ))
        
        # Check for missing cache configuration on expensive operations
        for step in workflow.steps:
            if step.type == 'claude_code' and not step.cache.get('enabled', True):
                result.add_issue(ValidationIssue(
                    severity="info",
                    category="performance",
                    message=f"Claude Code step '{step.id}' has caching disabled",
                    location=f"step:{step.id}",
                    suggestion="Enable caching for expensive Claude Code operations"
                ))
        
        # Check for potential parallelization opportunities
        sequential_steps = []
        for i, step_id in enumerate(workflow.execution_order[1:], 1):
            step = next(s for s in workflow.steps if s.id == step_id)
            prev_step_id = workflow.execution_order[i-1]
            
            if len(step.depends_on) == 1 and step.depends_on[0] == prev_step_id:
                sequential_steps.append((prev_step_id, step_id))
        
        if len(sequential_steps) > 3:
            result.add_issue(ValidationIssue(
                severity="info",
                category="performance",
                message="Multiple sequential steps detected - consider parallelization",
                suggestion="Review if some steps can be executed in parallel"
            ))
    
    def _validate_security(self, workflow: WorkflowDefinition, result: ValidationResult):
        """Validate workflow security aspects"""
        
        # Check for elevated security profiles
        elevated_steps = []
        for step in workflow.steps:
            if hasattr(step, 'security_profile') and step.security_profile == 'elevated':
                elevated_steps.append(step.id)
        
        if elevated_steps:
            result.add_issue(ValidationIssue(
                severity="warning",
                category="security",
                message=f"Steps using elevated security profile: {', '.join(elevated_steps)}",
                suggestion="Ensure elevated permissions are necessary and properly justified"
            ))
        
        # Check for shell commands that might be risky
        risky_commands = ['rm -rf', 'sudo', 'curl', 'wget', 'eval', 'exec']
        for step in workflow.steps:
            if step.type == 'shell' and step.command:
                for risky_cmd in risky_commands:
                    if risky_cmd in step.command:
                        result.add_issue(ValidationIssue(
                            severity="warning", 
                            category="security",
                            message=f"Step '{step.id}' contains potentially risky command: {risky_cmd}",
                            location=f"step:{step.id}",
                            suggestion="Review command for security implications"
                        ))
        
        # Check for hardcoded secrets or credentials
        sensitive_patterns = ['password', 'token', 'key', 'secret', 'api_key']
        for step in workflow.steps:
            step_data = str(step.__dict__)
            for pattern in sensitive_patterns:
                if pattern in step_data.lower():
                    result.add_issue(ValidationIssue(
                        severity="warning",
                        category="security",
                        message=f"Step '{step.id}' may contain hardcoded sensitive information",
                        location=f"step:{step.id}",
                        suggestion="Use environment variables or secure parameter storage"
                    ))
    
    def _validate_best_practices(self, workflow: WorkflowDefinition, result: ValidationResult):
        """Validate workflow best practices"""
        
        # Check for description
        if not workflow.description:
            result.add_issue(ValidationIssue(
                severity="info",
                category="best_practices",
                message="Workflow lacks description",
                suggestion="Add a description to document the workflow purpose"
            ))
        
        # Check for step descriptions
        undocumented_steps = [step.id for step in workflow.steps if not step.description]
        if undocumented_steps:
            result.add_issue(ValidationIssue(
                severity="info",
                category="best_practices",
                message=f"Steps without descriptions: {', '.join(undocumented_steps)}",
                suggestion="Add descriptions to document step purposes"
            ))
        
        # Check for error handling
        steps_without_retry = [
            step.id for step in workflow.steps 
            if step.type in ['shell', 'claude_code', 'webhook'] and not step.retry
        ]
        
        if steps_without_retry:
            result.add_issue(ValidationIssue(
                severity="info",
                category="best_practices",
                message=f"Steps without retry configuration: {', '.join(steps_without_retry)}",
                suggestion="Consider adding retry logic for fault tolerance"
            ))
        
        # Check for version format
        if workflow.version and not self._is_semantic_version(workflow.version):
            result.add_issue(ValidationIssue(
                severity="info",
                category="best_practices",
                message="Workflow version doesn't follow semantic versioning",
                suggestion="Use semantic versioning format (e.g., '1.0.0')"
            ))
    
    def _calculate_score(self, result: ValidationResult) -> float:
        """Calculate overall workflow quality score (0-100)"""
        base_score = 100.0
        
        # Deduct points for issues
        for issue in result.issues:
            if issue.severity == "error":
                base_score -= 20
            elif issue.severity == "warning": 
                base_score -= 5
            elif issue.severity == "info":
                base_score -= 1
        
        return max(0.0, base_score)
    
    def _generate_recommendations(self, result: ValidationResult) -> List[str]:
        """Generate improvement recommendations"""
        recommendations = []
        
        error_count = len(result.get_issues_by_severity("error"))
        warning_count = len(result.get_issues_by_severity("warning"))
        
        if error_count > 0:
            recommendations.append(f"Fix {error_count} critical error(s) before deploying")
        
        if warning_count > 0:
            recommendations.append(f"Address {warning_count} warning(s) to improve reliability")
        
        # Category-specific recommendations
        security_issues = result.get_issues_by_category("security")
        if security_issues:
            recommendations.append("Review security implications of flagged operations")
        
        performance_issues = result.get_issues_by_category("performance")
        if performance_issues:
            recommendations.append("Optimize workflow for better performance")
        
        return recommendations
    
    def _is_semantic_version(self, version: str) -> bool:
        """Check if version follows semantic versioning"""
        import re
        pattern = r'^\d+\.\d+(\.\d+)?(-[a-zA-Z0-9-]+)?(\+[a-zA-Z0-9-]+)?$'
        return bool(re.match(pattern, version))
    
    def _load_validation_rules(self) -> Dict[str, Any]:
        """Load validation rules configuration"""
        # In production, load from configuration file
        return {
            "max_steps": 50,
            "max_timeout": 3600,
            "required_fields": ["name", "version", "steps"],
            "security_patterns": ["password", "token", "key", "secret"],
            "risky_commands": ["rm -rf", "sudo", "curl", "eval"]
        }


class WorkflowTester:
    """Workflow execution testing system"""
    
    def __init__(self, engine: Optional[WorkflowEngine] = None):
        self.engine = engine or WorkflowEngine()
        self.test_results: Dict[str, Dict[str, Any]] = {}
    
    async def run_test_suite(
        self,
        workflow: WorkflowDefinition,
        test_cases: List[WorkflowTestCase],
        parallel: bool = False
    ) -> Dict[str, Any]:
        """Run complete test suite for workflow"""
        
        suite_results = {
            "workflow_name": workflow.name,
            "workflow_version": workflow.version,
            "total_tests": len(test_cases),
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "test_results": {}
        }
        
        if parallel and len(test_cases) > 1:
            # Run tests in parallel
            tasks = [
                self._run_single_test(workflow, test_case, f"test_{i}")
                for i, test_case in enumerate(test_cases)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                test_name = test_cases[i].name
                if isinstance(result, Exception):
                    suite_results["errors"] += 1
                    suite_results["test_results"][test_name] = {
                        "status": "error",
                        "error": str(result)
                    }
                else:
                    suite_results["test_results"][test_name] = result
                    if result["status"] == "passed":
                        suite_results["passed"] += 1
                    else:
                        suite_results["failed"] += 1
        else:
            # Run tests sequentially
            for test_case in test_cases:
                try:
                    result = await self._run_single_test(workflow, test_case, test_case.name)
                    suite_results["test_results"][test_case.name] = result
                    
                    if result["status"] == "passed":
                        suite_results["passed"] += 1
                    else:
                        suite_results["failed"] += 1
                        
                except Exception as e:
                    suite_results["errors"] += 1
                    suite_results["test_results"][test_case.name] = {
                        "status": "error",
                        "error": str(e)
                    }
        
        # Calculate success rate
        suite_results["success_rate"] = (
            suite_results["passed"] / suite_results["total_tests"] * 100
            if suite_results["total_tests"] > 0 else 0
        )
        
        return suite_results
    
    async def _run_single_test(
        self,
        workflow: WorkflowDefinition,
        test_case: WorkflowTestCase,
        execution_id: str
    ) -> Dict[str, Any]:
        """Run single workflow test case"""
        
        test_result = {
            "name": test_case.name,
            "status": "failed",
            "execution_time": 0.0,
            "expected_status": test_case.expected_status,
            "actual_status": None,
            "expected_outputs": test_case.expected_outputs,
            "actual_outputs": {},
            "issues": []
        }
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Apply mocks if specified
            with self._apply_mocks(test_case.mock_responses):
                # Execute workflow
                execution = await asyncio.wait_for(
                    self.engine.execute_workflow(workflow, test_case.inputs, execution_id),
                    timeout=test_case.timeout
                )
                
                test_result["actual_status"] = execution.status.value
                test_result["actual_outputs"] = execution.outputs
                
                # Check status
                status_match = execution.status.value == test_case.expected_status
                
                # Check outputs
                outputs_match = self._compare_outputs(
                    test_case.expected_outputs,
                    execution.outputs
                )
                
                # Check expected steps executed
                steps_match = True
                if test_case.expected_steps:
                    executed_steps = list(execution.step_results.keys())
                    steps_match = set(test_case.expected_steps).issubset(set(executed_steps))
                
                # Determine overall result
                if status_match and outputs_match and steps_match:
                    test_result["status"] = "passed"
                else:
                    if not status_match:
                        test_result["issues"].append(f"Status mismatch: expected {test_case.expected_status}, got {execution.status.value}")
                    if not outputs_match:
                        test_result["issues"].append("Output values don't match expected results")
                    if not steps_match:
                        test_result["issues"].append("Expected steps were not executed")
                
                # Add execution details
                test_result["step_results"] = {
                    step_id: {
                        "status": result.status.value,
                        "duration": result.duration_seconds,
                        "cached": result.cached
                    }
                    for step_id, result in execution.step_results.items()
                }
                
        except asyncio.TimeoutError:
            test_result["issues"].append(f"Test timed out after {test_case.timeout} seconds")
        except Exception as e:
            test_result["issues"].append(f"Test execution failed: {str(e)}")
        
        finally:
            test_result["execution_time"] = asyncio.get_event_loop().time() - start_time
        
        return test_result
    
    def _apply_mocks(self, mock_responses: Dict[str, Any]):
        """Apply mock responses for testing"""
        # This is a simplified mock system
        # In production, you'd want more sophisticated mocking
        return MockContext(mock_responses)
    
    def _compare_outputs(self, expected: Dict[str, Any], actual: Dict[str, Any]) -> bool:
        """Compare expected vs actual outputs"""
        if not expected:  # If no expected outputs specified, assume pass
            return True
        
        for key, expected_value in expected.items():
            if key not in actual:
                return False
            
            actual_value = actual[key]
            
            # Handle different comparison types
            if isinstance(expected_value, dict) and expected_value.get("type") == "regex":
                import re
                pattern = expected_value.get("pattern", "")
                if not re.match(pattern, str(actual_value)):
                    return False
            elif isinstance(expected_value, dict) and expected_value.get("type") == "range":
                min_val = expected_value.get("min", float('-inf'))
                max_val = expected_value.get("max", float('inf'))
                if not (min_val <= actual_value <= max_val):
                    return False
            else:
                # Direct comparison
                if actual_value != expected_value:
                    return False
        
        return True
    
    def generate_test_report(self, suite_results: Dict[str, Any]) -> str:
        """Generate human-readable test report"""
        report = []
        report.append(f"# Workflow Test Report")
        report.append(f"**Workflow:** {suite_results['workflow_name']} v{suite_results['workflow_version']}")
        report.append(f"**Tests:** {suite_results['total_tests']}")
        report.append(f"**Success Rate:** {suite_results['success_rate']:.1f}%")
        report.append("")
        
        report.append("## Summary")
        report.append(f"- ✅ Passed: {suite_results['passed']}")
        report.append(f"- ❌ Failed: {suite_results['failed']}")
        report.append(f"- 💥 Errors: {suite_results['errors']}")
        report.append("")
        
        report.append("## Test Results")
        for test_name, result in suite_results['test_results'].items():
            status_icon = "✅" if result['status'] == 'passed' else "❌"
            report.append(f"### {status_icon} {test_name}")
            
            if result['status'] == 'passed':
                report.append(f"- Execution time: {result['execution_time']:.2f}s")
            else:
                report.append(f"- Status: {result['status']}")
                if 'issues' in result:
                    for issue in result['issues']:
                        report.append(f"  - {issue}")
            
            report.append("")
        
        return "\n".join(report)


class MockContext:
    """Mock context for testing"""
    
    def __init__(self, mock_responses: Dict[str, Any]):
        self.mock_responses = mock_responses
        self.patches = []
    
    def __enter__(self):
        # Apply mocks based on mock_responses
        # This is a simplified implementation
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clean up patches
        for patch_obj in self.patches:
            try:
                patch_obj.stop()
            except:
                pass


def create_sample_test_cases() -> List[WorkflowTestCase]:
    """Create sample test cases for demonstration"""
    return [
        WorkflowTestCase(
            name="basic_execution",
            description="Test basic workflow execution with minimal inputs",
            inputs={"target_file": "src/example.py", "target_coverage": 80},
            expected_status="completed",
            expected_outputs={
                "coverage_achieved": {"type": "range", "min": 80, "max": 100}
            }
        ),
        WorkflowTestCase(
            name="high_coverage_target",
            description="Test workflow with high coverage target",
            inputs={"target_file": "src/complex.py", "target_coverage": 95},
            expected_status="completed"
        ),
        WorkflowTestCase(
            name="invalid_file",
            description="Test workflow with non-existent file",
            inputs={"target_file": "nonexistent.py", "target_coverage": 80},
            expected_status="failed"
        )
    ]


async def main():
    """CLI interface for workflow validation and testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Workflow Validator and Tester")
    parser.add_argument("workflow_file", help="Path to workflow YAML file")
    parser.add_argument("--validate", action="store_true", help="Validate workflow")
    parser.add_argument("--test", action="store_true", help="Run workflow tests")
    parser.add_argument("--test-config", help="Path to test configuration file")
    parser.add_argument("--output", help="Output file for results")
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")
    
    args = parser.parse_args()
    
    try:
        # Parse workflow
        workflow_parser = WorkflowParser()
        workflow = workflow_parser.parse_workflow(args.workflow_file)
        
        results = {}
        
        # Validation
        if args.validate:
            print("🔍 Validating workflow...")
            validator = WorkflowValidator(workflow_parser)
            validation_result = validator.validate_workflow(workflow)
            
            results["validation"] = {
                "valid": validation_result.valid,
                "score": validation_result.score,
                "issues": [
                    {
                        "severity": issue.severity,
                        "category": issue.category,
                        "message": issue.message,
                        "location": issue.location,
                        "suggestion": issue.suggestion
                    }
                    for issue in validation_result.issues
                ],
                "recommendations": validation_result.recommendations
            }
            
            print(f"Validation Score: {validation_result.score:.1f}/100")
            print(f"Issues Found: {len(validation_result.issues)}")
            
            for issue in validation_result.issues:
                severity_icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(issue.severity, "•")
                print(f"  {severity_icon} [{issue.category}] {issue.message}")
                if issue.suggestion:
                    print(f"    💡 {issue.suggestion}")
        
        # Testing
        if args.test:
            print("🧪 Running workflow tests...")
            
            # Load test cases
            if args.test_config and os.path.exists(args.test_config):
                with open(args.test_config, 'r') as f:
                    test_config = yaml.safe_load(f)
                    test_cases = [WorkflowTestCase(**case) for case in test_config.get('test_cases', [])]
            else:
                test_cases = create_sample_test_cases()
            
            # Run tests
            tester = WorkflowTester()
            suite_results = await tester.run_test_suite(workflow, test_cases, args.parallel)
            
            results["testing"] = suite_results
            
            # Print results
            print(f"Test Results: {suite_results['success_rate']:.1f}% success rate")
            print(f"Passed: {suite_results['passed']}, Failed: {suite_results['failed']}, Errors: {suite_results['errors']}")
            
            # Generate and display report
            report = tester.generate_test_report(suite_results)
            print("\n" + report)
        
        # Save results
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"📄 Results saved to: {args.output}")
        
        # Exit with appropriate code
        if args.validate and not results.get("validation", {}).get("valid", True):
            sys.exit(1)
        if args.test and results.get("testing", {}).get("success_rate", 100) < 100:
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())