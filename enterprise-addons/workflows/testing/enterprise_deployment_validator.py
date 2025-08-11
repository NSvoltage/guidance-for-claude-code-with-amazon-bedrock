#!/usr/bin/env python3
"""
Enterprise Deployment Validator
Comprehensive validation tool for enterprise workflow deployment scenarios.
"""
import os
import sys
import json
import tempfile
import asyncio
import logging
from typing import Dict, Any, List, Tuple
from pathlib import Path
from dataclasses import dataclass
import subprocess
import time

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from engine.secure_workflow_engine import (
        SecureWorkflowEngine, SecurityContext, create_secure_workflow_engine,
        create_development_engine, create_production_engine, create_plan_only_engine
    )
    from config.workflow_config import (
        load_workflow_config, ConfigurationManager, SecurityProfileConfig
    )
    from parser.workflow_parser import WorkflowParser, WorkflowDefinition
    COMPONENTS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import workflow components: {e}")
    COMPONENTS_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a single validation test"""
    test_name: str
    passed: bool
    message: str
    details: Dict[str, Any] = None
    execution_time: float = 0.0
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


class EnterpriseDeploymentValidator:
    """Comprehensive validator for enterprise deployment scenarios"""
    
    def __init__(self):
        self.results: List[ValidationResult] = []
        self.config_manager = ConfigurationManager() if COMPONENTS_AVAILABLE else None
        
    def run_all_validations(self) -> Tuple[int, int, List[ValidationResult]]:
        """Run all enterprise validation tests"""
        
        print("🏢 Enterprise Deployment Validation Suite")
        print("=" * 60)
        
        validation_groups = [
            ("System Requirements", self._validate_system_requirements),
            ("Configuration Management", self._validate_configuration),
            ("Security Profiles", self._validate_security_profiles),
            ("Engine Initialization", self._validate_engine_initialization),
            ("Workflow Processing", self._validate_workflow_processing),
            ("Security Controls", self._validate_security_controls),
            ("Performance & Scalability", self._validate_performance),
            ("Enterprise Integration", self._validate_enterprise_integration),
            ("Deployment Scenarios", self._validate_deployment_scenarios),
            ("Monitoring & Observability", self._validate_monitoring),
        ]
        
        total_tests = 0
        passed_tests = 0
        
        for group_name, validation_func in validation_groups:
            print(f"\n📋 {group_name}")
            print("-" * len(group_name))
            
            group_results = validation_func()
            self.results.extend(group_results)
            
            group_passed = sum(1 for r in group_results if r.passed)
            group_total = len(group_results)
            
            total_tests += group_total
            passed_tests += group_passed
            
            status = "✅" if group_passed == group_total else "⚠️" if group_passed > 0 else "❌"
            print(f"  {status} {group_passed}/{group_total} tests passed")
        
        return passed_tests, total_tests, self.results
    
    def _validate_system_requirements(self) -> List[ValidationResult]:
        """Validate system requirements and dependencies"""
        results = []
        
        # Python version check
        start_time = time.time()
        python_version = sys.version_info
        passed = python_version >= (3, 8)
        results.append(ValidationResult(
            "Python Version (>=3.8)",
            passed,
            f"Python {python_version.major}.{python_version.minor}.{python_version.micro}",
            {"version": f"{python_version.major}.{python_version.minor}.{python_version.micro}"},
            time.time() - start_time
        ))
        
        # Required dependencies
        dependencies = [
            ("PyYAML", "yaml"),
            ("Jinja2", "jinja2"),
            ("SimpleEval", "simpleeval"),
            ("JSONSchema", "jsonschema"),
        ]
        
        for dep_name, module_name in dependencies:
            start_time = time.time()
            try:
                __import__(module_name)
                results.append(ValidationResult(
                    f"Dependency: {dep_name}",
                    True,
                    "Available",
                    {"module": module_name},
                    time.time() - start_time
                ))
            except ImportError:
                results.append(ValidationResult(
                    f"Dependency: {dep_name}",
                    False,
                    f"Module '{module_name}' not found - install with 'pip install {dep_name}'",
                    {"module": module_name},
                    time.time() - start_time
                ))
        
        # File system permissions
        start_time = time.time()
        try:
            temp_dir = tempfile.mkdtemp()
            test_file = os.path.join(temp_dir, "test.txt")
            with open(test_file, "w") as f:
                f.write("test")
            os.unlink(test_file)
            os.rmdir(temp_dir)
            
            results.append(ValidationResult(
                "File System Access",
                True,
                "Read/write permissions available",
                {"temp_dir": temp_dir},
                time.time() - start_time
            ))
        except Exception as e:
            results.append(ValidationResult(
                "File System Access",
                False,
                f"File system access failed: {str(e)}",
                {"error": str(e)},
                time.time() - start_time
            ))
        
        return results
    
    def _validate_configuration(self) -> List[ValidationResult]:
        """Validate configuration management"""
        results = []
        
        if not COMPONENTS_AVAILABLE:
            results.append(ValidationResult(
                "Configuration Loading",
                False,
                "Components not available for testing",
                {},
                0.0
            ))
            return results
        
        # Configuration loading
        start_time = time.time()
        try:
            config = load_workflow_config()
            results.append(ValidationResult(
                "Configuration Loading",
                True,
                f"Config loaded: {config.environment} environment, {config.security_profile} profile",
                {
                    "environment": config.environment,
                    "security_profile": config.security_profile,
                    "debug_mode": config.enable_debug_mode
                },
                time.time() - start_time
            ))
        except Exception as e:
            results.append(ValidationResult(
                "Configuration Loading",
                False,
                f"Configuration loading failed: {str(e)}",
                {"error": str(e)},
                time.time() - start_time
            ))
        
        # Environment variable override
        start_time = time.time()
        original_profile = os.getenv('CLAUDE_SECURITY_PROFILE')
        try:
            os.environ['CLAUDE_SECURITY_PROFILE'] = 'elevated'
            # Clear cache to force reload
            if hasattr(self.config_manager, '_config_cache'):
                self.config_manager._config_cache = None
                
            config = load_workflow_config()
            passed = config.security_profile == 'elevated'
            
            results.append(ValidationResult(
                "Environment Variable Override",
                passed,
                f"Profile override {'successful' if passed else 'failed'}: {config.security_profile}",
                {"overridden_profile": config.security_profile},
                time.time() - start_time
            ))
        finally:
            if original_profile:
                os.environ['CLAUDE_SECURITY_PROFILE'] = original_profile
            else:
                os.environ.pop('CLAUDE_SECURITY_PROFILE', None)
        
        # Configuration validation
        start_time = time.time()
        try:
            config = load_workflow_config()
            issues = self.config_manager.validate_configuration(config)
            
            critical_issues = [issue for issue in issues if 'ERROR' in issue]
            passed = len(critical_issues) == 0
            
            results.append(ValidationResult(
                "Configuration Validation",
                passed,
                f"Validation {'passed' if passed else 'failed'}: {len(issues)} issues found",
                {
                    "total_issues": len(issues),
                    "critical_issues": len(critical_issues),
                    "issues": issues[:5]  # First 5 issues
                },
                time.time() - start_time
            ))
        except Exception as e:
            results.append(ValidationResult(
                "Configuration Validation",
                False,
                f"Validation failed: {str(e)}",
                {"error": str(e)},
                time.time() - start_time
            ))
        
        return results
    
    def _validate_security_profiles(self) -> List[ValidationResult]:
        """Validate security profile configurations"""
        results = []
        
        if not COMPONENTS_AVAILABLE:
            results.append(ValidationResult(
                "Security Profiles",
                False,
                "Components not available for testing",
                {},
                0.0
            ))
            return results
        
        profiles = ['plan_only', 'restricted', 'standard', 'elevated']
        
        for profile_name in profiles:
            start_time = time.time()
            try:
                profile_config = self.config_manager.get_security_profile(profile_name)
                
                # Validate profile has required attributes
                required_attrs = [
                    'name', 'description', 'max_concurrent_workflows', 
                    'allow_shell_execution', 'validation_strictness'
                ]
                
                missing_attrs = [attr for attr in required_attrs if not hasattr(profile_config, attr)]
                passed = len(missing_attrs) == 0
                
                results.append(ValidationResult(
                    f"Security Profile: {profile_name}",
                    passed,
                    f"Profile {'valid' if passed else 'invalid'}: {profile_config.description}",
                    {
                        "name": profile_config.name,
                        "max_concurrent": profile_config.max_concurrent_workflows,
                        "allow_shell": profile_config.allow_shell_execution,
                        "strictness": profile_config.validation_strictness,
                        "missing_attrs": missing_attrs
                    },
                    time.time() - start_time
                ))
                
            except Exception as e:
                results.append(ValidationResult(
                    f"Security Profile: {profile_name}",
                    False,
                    f"Profile loading failed: {str(e)}",
                    {"error": str(e)},
                    time.time() - start_time
                ))
        
        return results
    
    def _validate_engine_initialization(self) -> List[ValidationResult]:
        """Validate workflow engine initialization"""
        results = []
        
        if not COMPONENTS_AVAILABLE:
            results.append(ValidationResult(
                "Engine Initialization",
                False,
                "Components not available for testing",
                {},
                0.0
            ))
            return results
        
        # Test factory functions
        factory_tests = [
            ("Development Engine", create_development_engine),
            ("Production Engine", create_production_engine),
            ("Plan-Only Engine", create_plan_only_engine),
        ]
        
        for test_name, factory_func in factory_tests:
            start_time = time.time()
            try:
                engine = factory_func()
                status = engine.get_engine_status()
                
                results.append(ValidationResult(
                    test_name,
                    True,
                    f"Engine initialized: {status['security_profile']} profile",
                    status,
                    time.time() - start_time
                ))
                
            except Exception as e:
                results.append(ValidationResult(
                    test_name,
                    False,
                    f"Engine initialization failed: {str(e)}",
                    {"error": str(e)},
                    time.time() - start_time
                ))
        
        # Test direct initialization with profiles
        for profile in ['restricted', 'standard']:
            start_time = time.time()
            try:
                engine = create_secure_workflow_engine(profile)
                status = engine.get_engine_status()
                
                passed = status['security_profile'] == profile
                results.append(ValidationResult(
                    f"Engine with {profile} profile",
                    passed,
                    f"Profile {'correctly set' if passed else 'incorrectly set'}: {status['security_profile']}",
                    status,
                    time.time() - start_time
                ))
                
            except Exception as e:
                results.append(ValidationResult(
                    f"Engine with {profile} profile",
                    False,
                    f"Engine initialization failed: {str(e)}",
                    {"error": str(e)},
                    time.time() - start_time
                ))
        
        return results
    
    def _validate_workflow_processing(self) -> List[ValidationResult]:
        """Validate workflow parsing and processing"""
        results = []
        
        if not COMPONENTS_AVAILABLE:
            results.append(ValidationResult(
                "Workflow Processing",
                False,
                "Components not available for testing",
                {},
                0.0
            ))
            return results
        
        # Create a simple test workflow
        test_workflow_yaml = """
name: validation-test
version: 1.0
description: Simple test workflow for validation
inputs:
  test_input:
    type: string
    required: true
    default: "test_value"
steps:
  - id: echo-step
    type: shell
    command: "echo 'Test: {{ inputs.test_input }}'"
    outputs:
      result:
        type: string
        from: stdout
outputs:
  final_result:
    type: string
    from: echo-step.outputs.result
"""
        
        # Test workflow parsing
        start_time = time.time()
        try:
            parser = WorkflowParser()
            
            # Create temporary workflow file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write(test_workflow_yaml)
                temp_workflow_path = f.name
            
            try:
                workflow = parser.parse_workflow(temp_workflow_path)
                
                results.append(ValidationResult(
                    "Workflow Parsing",
                    True,
                    f"Workflow parsed successfully: {workflow.name}",
                    {
                        "workflow_name": workflow.name,
                        "step_count": len(workflow.steps),
                        "input_count": len(workflow.inputs),
                        "output_count": len(workflow.outputs)
                    },
                    time.time() - start_time
                ))
                
                # Test workflow validation
                start_time = time.time()
                validation_issues = parser.validate_workflow(workflow)
                passed = len(validation_issues) == 0
                
                results.append(ValidationResult(
                    "Workflow Validation",
                    passed,
                    f"Validation {'passed' if passed else 'failed'}: {len(validation_issues)} issues",
                    {
                        "issue_count": len(validation_issues),
                        "issues": validation_issues[:3]  # First 3 issues
                    },
                    time.time() - start_time
                ))
                
            finally:
                os.unlink(temp_workflow_path)
                
        except Exception as e:
            results.append(ValidationResult(
                "Workflow Parsing",
                False,
                f"Workflow parsing failed: {str(e)}",
                {"error": str(e)},
                time.time() - start_time
            ))
        
        return results
    
    def _validate_security_controls(self) -> List[ValidationResult]:
        """Validate security controls and validation"""
        results = []
        
        if not COMPONENTS_AVAILABLE:
            results.append(ValidationResult(
                "Security Controls",
                False,
                "Components not available for testing",
                {},
                0.0
            ))
            return results
        
        from engine.secure_workflow_engine import SecureInputValidator
        
        # Test input validation
        validator = SecureInputValidator.create_for_profile('standard')
        
        # Test safe inputs (should pass)
        safe_inputs = [
            "echo 'hello world'",
            "npm install",
            "python script.py",
            "{{ inputs.filename }}",
        ]
        
        for safe_input in safe_inputs:
            start_time = time.time()
            try:
                validator.validate_string_input(safe_input, "test")
                results.append(ValidationResult(
                    f"Safe Input: {safe_input[:20]}...",
                    True,
                    "Input correctly allowed",
                    {"input": safe_input},
                    time.time() - start_time
                ))
            except Exception as e:
                results.append(ValidationResult(
                    f"Safe Input: {safe_input[:20]}...",
                    False,
                    f"Safe input incorrectly blocked: {str(e)}",
                    {"input": safe_input, "error": str(e)},
                    time.time() - start_time
                ))
        
        # Test dangerous inputs (should be blocked)
        dangerous_inputs = [
            "eval('malicious code')",
            "__import__('os').system('rm -rf /')",
            "{{ config.__class__ }}",
            "../../../etc/passwd",
        ]
        
        for dangerous_input in dangerous_inputs:
            start_time = time.time()
            try:
                validator.validate_string_input(dangerous_input, "test")
                results.append(ValidationResult(
                    f"Dangerous Input: {dangerous_input[:20]}...",
                    False,
                    "Dangerous input incorrectly allowed",
                    {"input": dangerous_input},
                    time.time() - start_time
                ))
            except Exception:
                results.append(ValidationResult(
                    f"Dangerous Input: {dangerous_input[:20]}...",
                    True,
                    "Dangerous input correctly blocked",
                    {"input": dangerous_input},
                    time.time() - start_time
                ))
        
        return results
    
    def _validate_performance(self) -> List[ValidationResult]:
        """Validate performance and scalability features"""
        results = []
        
        if not COMPONENTS_AVAILABLE:
            results.append(ValidationResult(
                "Performance Features",
                False,
                "Components not available for testing",
                {},
                0.0
            ))
            return results
        
        # Test engine creation performance
        start_time = time.time()
        try:
            engines = []
            for i in range(10):
                engines.append(create_secure_workflow_engine('standard'))
            
            creation_time = time.time() - start_time
            passed = creation_time < 1.0  # Should create 10 engines in under 1 second
            
            results.append(ValidationResult(
                "Engine Creation Performance",
                passed,
                f"Created 10 engines in {creation_time:.3f}s",
                {
                    "engine_count": len(engines),
                    "total_time": creation_time,
                    "avg_time_per_engine": creation_time / len(engines)
                },
                creation_time
            ))
            
        except Exception as e:
            results.append(ValidationResult(
                "Engine Creation Performance",
                False,
                f"Performance test failed: {str(e)}",
                {"error": str(e)},
                time.time() - start_time
            ))
        
        # Test configuration caching
        start_time = time.time()
        try:
            config1 = load_workflow_config()
            config2 = load_workflow_config()
            
            # Should be fast due to caching
            load_time = time.time() - start_time
            passed = load_time < 0.1  # Should be very fast with caching
            
            results.append(ValidationResult(
                "Configuration Caching",
                passed,
                f"Configuration loaded twice in {load_time:.3f}s",
                {"load_time": load_time},
                load_time
            ))
            
        except Exception as e:
            results.append(ValidationResult(
                "Configuration Caching",
                False,
                f"Caching test failed: {str(e)}",
                {"error": str(e)},
                time.time() - start_time
            ))
        
        return results
    
    def _validate_enterprise_integration(self) -> List[ValidationResult]:
        """Validate enterprise integration features"""
        results = []
        
        # Test security context creation
        start_time = time.time()
        try:
            if COMPONENTS_AVAILABLE:
                security_context = SecurityContext(
                    user_id="test-enterprise-user",
                    permissions={"workflow.execute", "shell.execute"},
                    security_profile="standard"
                )
                
                # Test permission checks
                has_workflow_perm = security_context.has_permission("workflow.execute")
                has_shell_perm = security_context.has_permission("shell.execute")
                lacks_admin_perm = not security_context.has_permission("admin.full")
                
                passed = has_workflow_perm and has_shell_perm and lacks_admin_perm
                
                results.append(ValidationResult(
                    "Security Context & Permissions",
                    passed,
                    f"Permission system {'working correctly' if passed else 'failed'}",
                    {
                        "has_workflow": has_workflow_perm,
                        "has_shell": has_shell_perm,
                        "lacks_admin": lacks_admin_perm
                    },
                    time.time() - start_time
                ))
            else:
                results.append(ValidationResult(
                    "Security Context & Permissions",
                    False,
                    "Components not available for testing",
                    {},
                    time.time() - start_time
                ))
                
        except Exception as e:
            results.append(ValidationResult(
                "Security Context & Permissions",
                False,
                f"Security context test failed: {str(e)}",
                {"error": str(e)},
                time.time() - start_time
            ))
        
        # Test audit logging
        start_time = time.time()
        try:
            if COMPONENTS_AVAILABLE:
                security_context = SecurityContext(
                    user_id="audit-test-user",
                    permissions=set(),
                    security_profile="standard"
                )
                
                security_context.log_security_event("Test audit event")
                security_context.log_security_event("Another test event with data")
                
                passed = len(security_context.audit_trail) >= 2
                
                results.append(ValidationResult(
                    "Audit Trail Logging",
                    passed,
                    f"Audit logging {'working' if passed else 'failed'}: {len(security_context.audit_trail)} events",
                    {
                        "event_count": len(security_context.audit_trail),
                        "sample_events": security_context.audit_trail[:2]
                    },
                    time.time() - start_time
                ))
            else:
                results.append(ValidationResult(
                    "Audit Trail Logging",
                    False,
                    "Components not available for testing",
                    {},
                    time.time() - start_time
                ))
                
        except Exception as e:
            results.append(ValidationResult(
                "Audit Trail Logging",
                False,
                f"Audit logging test failed: {str(e)}",
                {"error": str(e)},
                time.time() - start_time
            ))
        
        return results
    
    def _validate_deployment_scenarios(self) -> List[ValidationResult]:
        """Validate common enterprise deployment scenarios"""
        results = []
        
        # Test development environment scenario
        start_time = time.time()
        original_env = os.getenv('CLAUDE_WORKFLOW_ENVIRONMENT')
        try:
            os.environ['CLAUDE_WORKFLOW_ENVIRONMENT'] = 'development'
            if hasattr(self.config_manager, '_config_cache'):
                self.config_manager._config_cache = None
            
            if COMPONENTS_AVAILABLE:
                config = load_workflow_config()
                passed = config.environment == 'development'
                
                results.append(ValidationResult(
                    "Development Environment",
                    passed,
                    f"Development config {'loaded correctly' if passed else 'failed'}: {config.environment}",
                    {
                        "environment": config.environment,
                        "debug_mode": config.enable_debug_mode,
                        "security_profile": config.security_profile
                    },
                    time.time() - start_time
                ))
            else:
                results.append(ValidationResult(
                    "Development Environment",
                    False,
                    "Components not available for testing",
                    {},
                    time.time() - start_time
                ))
                
        finally:
            if original_env:
                os.environ['CLAUDE_WORKFLOW_ENVIRONMENT'] = original_env
            else:
                os.environ.pop('CLAUDE_WORKFLOW_ENVIRONMENT', None)
        
        # Test production environment scenario
        start_time = time.time()
        try:
            os.environ['CLAUDE_WORKFLOW_ENVIRONMENT'] = 'production'
            os.environ['CLAUDE_ENABLE_DEBUG'] = 'false'
            if hasattr(self.config_manager, '_config_cache'):
                self.config_manager._config_cache = None
            
            if COMPONENTS_AVAILABLE:
                config = load_workflow_config()
                passed = (config.environment == 'production' and 
                         not config.enable_debug_mode)
                
                results.append(ValidationResult(
                    "Production Environment",
                    passed,
                    f"Production config {'loaded correctly' if passed else 'failed'}",
                    {
                        "environment": config.environment,
                        "debug_disabled": not config.enable_debug_mode,
                        "security_profile": config.security_profile
                    },
                    time.time() - start_time
                ))
            else:
                results.append(ValidationResult(
                    "Production Environment",
                    False,
                    "Components not available for testing",
                    {},
                    time.time() - start_time
                ))
                
        finally:
            # Clean up environment
            for env_var in ['CLAUDE_WORKFLOW_ENVIRONMENT', 'CLAUDE_ENABLE_DEBUG']:
                os.environ.pop(env_var, None)
            if original_env:
                os.environ['CLAUDE_WORKFLOW_ENVIRONMENT'] = original_env
        
        return results
    
    def _validate_monitoring(self) -> List[ValidationResult]:
        """Validate monitoring and observability features"""
        results = []
        
        # Test logging configuration
        start_time = time.time()
        try:
            # Test that logging is properly configured
            test_logger = logging.getLogger('test.validator')
            test_logger.info("Test log message")
            
            results.append(ValidationResult(
                "Logging Configuration",
                True,
                "Logging system is properly configured",
                {"logger_name": test_logger.name},
                time.time() - start_time
            ))
            
        except Exception as e:
            results.append(ValidationResult(
                "Logging Configuration",
                False,
                f"Logging configuration failed: {str(e)}",
                {"error": str(e)},
                time.time() - start_time
            ))
        
        # Test status reporting
        start_time = time.time()
        try:
            if COMPONENTS_AVAILABLE:
                engine = create_secure_workflow_engine('standard')
                status = engine.get_engine_status()
                
                required_fields = ['security_profile', 'max_concurrent_workflows', 'active_workflows']
                has_required = all(field in status for field in required_fields)
                
                results.append(ValidationResult(
                    "Status Reporting",
                    has_required,
                    f"Status reporting {'working' if has_required else 'incomplete'}",
                    status,
                    time.time() - start_time
                ))
            else:
                results.append(ValidationResult(
                    "Status Reporting",
                    False,
                    "Components not available for testing",
                    {},
                    time.time() - start_time
                ))
                
        except Exception as e:
            results.append(ValidationResult(
                "Status Reporting",
                False,
                f"Status reporting failed: {str(e)}",
                {"error": str(e)},
                time.time() - start_time
            ))
        
        return results
    
    def generate_report(self, results: List[ValidationResult]) -> str:
        """Generate comprehensive validation report"""
        
        passed_count = sum(1 for r in results if r.passed)
        total_count = len(results)
        success_rate = (passed_count / total_count * 100) if total_count > 0 else 0
        
        report = []
        report.append("🏢 ENTERPRISE DEPLOYMENT VALIDATION REPORT")
        report.append("=" * 60)
        report.append(f"Overall Status: {passed_count}/{total_count} tests passed ({success_rate:.1f}%)")
        report.append(f"Total Execution Time: {sum(r.execution_time for r in results):.3f}s")
        report.append("")
        
        # Group results by test category
        categories = {}
        for result in results:
            category = result.test_name.split(':')[0] if ':' in result.test_name else "General"
            if category not in categories:
                categories[category] = []
            categories[category].append(result)
        
        # Report by category
        for category, cat_results in categories.items():
            cat_passed = sum(1 for r in cat_results if r.passed)
            cat_total = len(cat_results)
            
            report.append(f"📋 {category}")
            report.append("-" * len(category))
            
            for result in cat_results:
                status = "✅" if result.passed else "❌"
                report.append(f"  {status} {result.test_name}: {result.message}")
                if not result.passed and result.details:
                    error_detail = result.details.get('error', 'No additional details')
                    report.append(f"      Error: {error_detail}")
            
            report.append(f"  Summary: {cat_passed}/{cat_total} passed")
            report.append("")
        
        # Recommendations
        failed_results = [r for r in results if not r.passed]
        if failed_results:
            report.append("💡 RECOMMENDATIONS:")
            report.append("-" * 20)
            
            # Dependency issues
            dep_failures = [r for r in failed_results if 'Dependency' in r.test_name]
            if dep_failures:
                report.append("1. Install missing dependencies:")
                for failure in dep_failures:
                    if 'pip install' in failure.message:
                        report.append(f"   {failure.message}")
            
            # Configuration issues
            config_failures = [r for r in failed_results if 'Configuration' in r.test_name]
            if config_failures:
                report.append("2. Fix configuration issues:")
                for failure in config_failures:
                    report.append(f"   - {failure.message}")
            
            # Security issues
            security_failures = [r for r in failed_results if 'Security' in r.test_name]
            if security_failures:
                report.append("3. Address security configuration:")
                for failure in security_failures:
                    report.append(f"   - {failure.message}")
            
            report.append("")
        
        # Deployment readiness
        critical_failures = [r for r in failed_results 
                           if any(critical in r.test_name for critical in 
                                 ['Python Version', 'Dependency', 'Configuration Loading'])]
        
        if critical_failures:
            report.append("🚨 DEPLOYMENT READINESS: NOT READY")
            report.append("   Critical issues must be resolved before deployment")
        elif failed_results:
            report.append("⚠️  DEPLOYMENT READINESS: READY WITH WARNINGS")
            report.append("   Non-critical issues should be addressed")
        else:
            report.append("✅ DEPLOYMENT READINESS: READY FOR PRODUCTION")
            report.append("   All validation tests passed successfully")
        
        return "\n".join(report)


def main():
    """Main CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enterprise Deployment Validator")
    parser.add_argument("--output", "-o", help="Output file for detailed report")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--category", help="Run only specific category of tests")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    validator = EnterpriseDeploymentValidator()
    passed_count, total_count, results = validator.run_all_validations()
    
    if args.json:
        # Output as JSON
        json_results = []
        for result in results:
            json_results.append({
                "test_name": result.test_name,
                "passed": result.passed,
                "message": result.message,
                "details": result.details,
                "execution_time": result.execution_time
            })
        
        output_data = {
            "summary": {
                "passed": passed_count,
                "total": total_count,
                "success_rate": (passed_count / total_count * 100) if total_count > 0 else 0
            },
            "results": json_results
        }
        
        json_output = json.dumps(output_data, indent=2)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(json_output)
        else:
            print(json_output)
    
    else:
        # Generate text report
        report = validator.generate_report(results)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(report)
            print(f"Detailed report saved to: {args.output}")
        else:
            print(report)
    
    # Exit code based on results
    if passed_count == total_count:
        print("\n✅ All validations passed - system is ready for enterprise deployment")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total_count - passed_count} validation(s) failed - review issues before deployment")
        sys.exit(1)


if __name__ == "__main__":
    main()