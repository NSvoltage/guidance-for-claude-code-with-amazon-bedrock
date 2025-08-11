#!/usr/bin/env python3
"""
Simplified Security Validation for Workflow System
Validates critical security controls without external dependencies.
"""
import os
import re
import sys
import json
import hashlib
from typing import List, Dict, Any, Tuple


class SecurityIssue:
    def __init__(self, severity: str, category: str, file_path: str, line_number: int, description: str):
        self.severity = severity  # CRITICAL, HIGH, MEDIUM, LOW
        self.category = category  # code_injection, template_injection, etc.
        self.file_path = file_path
        self.line_number = line_number
        self.description = description
    
    def __str__(self):
        return f"[{self.severity}] {self.category}: {self.description} ({self.file_path}:{self.line_number})"


class WorkflowSecurityAnalyzer:
    """Analyzes workflow system for security vulnerabilities"""
    
    def __init__(self):
        # Dangerous patterns that indicate security vulnerabilities
        self.dangerous_patterns = {
            'code_injection': [
                (r'eval\s*\(', 'CRITICAL', 'Use of eval() enables code injection'),
                (r'exec\s*\(', 'CRITICAL', 'Use of exec() enables code execution'),
                (r'compile\s*\(', 'HIGH', 'Use of compile() may enable code execution'),
                (r'__import__\s*\(', 'HIGH', 'Dynamic imports may be exploitable'),
                (r'getattr\s*\(\s*__builtins__', 'CRITICAL', 'Access to builtins enables code execution'),
                (r'globals\s*\(\s*\)', 'HIGH', 'Access to globals may expose sensitive data'),
                (r'locals\s*\(\s*\)', 'MEDIUM', 'Access to locals may expose sensitive data'),
            ],
            'template_injection': [
                (r'\{\{.*__class__.*\}\}', 'CRITICAL', 'Template accesses class hierarchy'),
                (r'\{\{.*__mro__.*\}\}', 'CRITICAL', 'Template accesses method resolution order'),
                (r'\{\{.*__subclasses__.*\}\}', 'CRITICAL', 'Template accesses subclasses'),
                (r'\{\{.*__globals__.*\}\}', 'CRITICAL', 'Template accesses globals'),
                (r'\{\{.*__builtins__.*\}\}', 'CRITICAL', 'Template accesses builtins'),
                (r'\{\{.*config.*\}\}', 'HIGH', 'Template may access configuration'),
            ],
            'shell_injection': [
                (r'subprocess\.call\([^)]*\+', 'HIGH', 'String concatenation in subprocess call'),
                (r'os\.system\([^)]*\+', 'CRITICAL', 'String concatenation in os.system'),
                (r'os\.popen\([^)]*\+', 'CRITICAL', 'String concatenation in os.popen'),
                (r'shell=True.*\+', 'HIGH', 'String concatenation with shell=True'),
            ],
            'path_traversal': [
                (r'open\([^)]*\.\.[^)]*\)', 'HIGH', 'Potential path traversal in file operations'),
                (r'os\.path\.join\([^)]*\.\.[^)]*\)', 'MEDIUM', 'Potential path traversal in path joining'),
                (r'\.\.\/.*\/etc\/', 'CRITICAL', 'Direct path traversal to system directories'),
                (r'\.\.\\.*\\windows\\', 'CRITICAL', 'Direct path traversal to Windows directories'),
            ],
            'information_disclosure': [
                (r'print\([^)]*password[^)]*\)', 'MEDIUM', 'Potential password disclosure in logs'),
                (r'print\([^)]*token[^)]*\)', 'MEDIUM', 'Potential token disclosure in logs'),
                (r'print\([^)]*secret[^)]*\)', 'MEDIUM', 'Potential secret disclosure in logs'),
                (r'logging\.[^(]*\([^)]*password[^)]*\)', 'MEDIUM', 'Potential password in logs'),
                (r'logger\.[^(]*\([^)]*token[^)]*\)', 'MEDIUM', 'Potential token in logs'),
            ],
            'unsafe_deserialization': [
                (r'pickle\.loads\s*\(', 'CRITICAL', 'Unsafe pickle deserialization'),
                (r'pickle\.load\s*\(', 'HIGH', 'Pickle deserialization may be unsafe'),
                (r'yaml\.load\s*\((?![^)]*Loader)', 'HIGH', 'Unsafe YAML loading without safe loader'),
                (r'json\.loads\([^)]*user[^)]*\)', 'MEDIUM', 'JSON deserialization of user input'),
            ]
        }
        
        # Security best practices to check
        self.security_checks = [
            ('input_validation', self._check_input_validation),
            ('error_handling', self._check_error_handling),
            ('logging_security', self._check_logging_security),
            ('resource_limits', self._check_resource_limits),
            ('authentication', self._check_authentication),
        ]
    
    def analyze_directory(self, directory: str) -> List[SecurityIssue]:
        """Analyze all Python files in directory for security issues"""
        issues = []
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    issues.extend(self.analyze_file(file_path))
        
        # Run additional security checks
        for check_name, check_func in self.security_checks:
            issues.extend(check_func(directory))
        
        return issues
    
    def analyze_file(self, file_path: str) -> List[SecurityIssue]:
        """Analyze single Python file for security vulnerabilities"""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                # Check each pattern category
                for category, patterns in self.dangerous_patterns.items():
                    for pattern, severity, description in patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            issues.append(SecurityIssue(
                                severity=severity,
                                category=category,
                                file_path=file_path,
                                line_number=line_num,
                                description=f"{description}: {line.strip()}"
                            ))
        
        except Exception as e:
            issues.append(SecurityIssue(
                severity='MEDIUM',
                category='file_access',
                file_path=file_path,
                line_number=0,
                description=f"Could not analyze file: {str(e)}"
            ))
        
        return issues
    
    def _check_input_validation(self, directory: str) -> List[SecurityIssue]:
        """Check for proper input validation"""
        issues = []
        
        # Look for input validation patterns
        validation_indicators = [
            'validate_input', 'sanitize_input', 'clean_input',
            'SecurityError', 'ValidationError', 'InputError'
        ]
        
        has_validation = False
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if any(indicator in content for indicator in validation_indicators):
                                has_validation = True
                                break
                    except:
                        continue
            if has_validation:
                break
        
        if not has_validation:
            issues.append(SecurityIssue(
                severity='HIGH',
                category='input_validation',
                file_path=directory,
                line_number=0,
                description='No input validation mechanisms detected'
            ))
        
        return issues
    
    def _check_error_handling(self, directory: str) -> List[SecurityIssue]:
        """Check for proper error handling"""
        issues = []
        
        # Look for bare except clauses which may hide errors
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                        
                        for line_num, line in enumerate(lines, 1):
                            if re.search(r'except\s*:', line):
                                issues.append(SecurityIssue(
                                    severity='MEDIUM',
                                    category='error_handling',
                                    file_path=file_path,
                                    line_number=line_num,
                                    description='Bare except clause may hide security errors'
                                ))
                    except:
                        continue
        
        return issues
    
    def _check_logging_security(self, directory: str) -> List[SecurityIssue]:
        """Check for secure logging practices"""
        issues = []
        
        # Check for potential log injection
        log_injection_patterns = [
            (r'log[^(]*\([^)]*\+[^)]*user[^)]*\)', 'User input concatenated in log'),
            (r'print\([^)]*\+[^)]*request[^)]*\)', 'Request data concatenated in output'),
            (r'logger\.[^(]*\([^)]*%[^)]*user[^)]*\)', 'Potential log injection via string formatting'),
        ]
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                        
                        for line_num, line in enumerate(lines, 1):
                            for pattern, description in log_injection_patterns:
                                if re.search(pattern, line):
                                    issues.append(SecurityIssue(
                                        severity='MEDIUM',
                                        category='logging_security',
                                        file_path=file_path,
                                        line_number=line_num,
                                        description=description
                                    ))
                    except:
                        continue
        
        return issues
    
    def _check_resource_limits(self, directory: str) -> List[SecurityIssue]:
        """Check for resource limit implementations"""
        issues = []
        
        resource_limit_indicators = [
            'resource.setrlimit', 'MAX_MEMORY', 'MAX_CPU', 'timeout=',
            'ResourceExhaustionError', 'memory_limit', 'cpu_limit'
        ]
        
        has_resource_limits = False
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if any(indicator in content for indicator in resource_limit_indicators):
                                has_resource_limits = True
                                break
                    except:
                        continue
            if has_resource_limits:
                break
        
        if not has_resource_limits:
            issues.append(SecurityIssue(
                severity='HIGH',
                category='resource_limits',
                file_path=directory,
                line_number=0,
                description='No resource limit mechanisms detected - DoS vulnerability'
            ))
        
        return issues
    
    def _check_authentication(self, directory: str) -> List[SecurityIssue]:
        """Check for authentication and authorization"""
        issues = []
        
        auth_indicators = [
            'SecurityContext', 'has_permission', 'authenticate',
            'authorize', 'permissions', 'access_control'
        ]
        
        has_auth = False
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if any(indicator in content for indicator in auth_indicators):
                                has_auth = True
                                break
                    except:
                        continue
            if has_auth:
                break
        
        if not has_auth:
            issues.append(SecurityIssue(
                severity='HIGH',
                category='authentication',
                file_path=directory,
                line_number=0,
                description='No authentication/authorization mechanisms detected'
            ))
        
        return issues
    
    def generate_security_report(self, issues: List[SecurityIssue]) -> str:
        """Generate comprehensive security report"""
        if not issues:
            return "✅ No security issues detected!"
        
        # Categorize issues by severity
        critical_issues = [i for i in issues if i.severity == 'CRITICAL']
        high_issues = [i for i in issues if i.severity == 'HIGH']
        medium_issues = [i for i in issues if i.severity == 'MEDIUM']
        low_issues = [i for i in issues if i.severity == 'LOW']
        
        report = []
        report.append("🔒 SECURITY ANALYSIS REPORT")
        report.append("=" * 50)
        report.append(f"Total Issues Found: {len(issues)}")
        report.append(f"  🔴 Critical: {len(critical_issues)}")
        report.append(f"  🟠 High: {len(high_issues)}")  
        report.append(f"  🟡 Medium: {len(medium_issues)}")
        report.append(f"  🟢 Low: {len(low_issues)}")
        report.append("")
        
        if critical_issues:
            report.append("🔴 CRITICAL ISSUES (MUST FIX IMMEDIATELY):")
            report.append("-" * 50)
            for issue in critical_issues:
                report.append(f"  {issue}")
            report.append("")
        
        if high_issues:
            report.append("🟠 HIGH PRIORITY ISSUES:")
            report.append("-" * 30)
            for issue in high_issues:
                report.append(f"  {issue}")
            report.append("")
        
        if medium_issues:
            report.append("🟡 MEDIUM PRIORITY ISSUES:")
            report.append("-" * 30)
            for issue in medium_issues:
                report.append(f"  {issue}")
            report.append("")
        
        # Security recommendations
        report.append("💡 SECURITY RECOMMENDATIONS:")
        report.append("-" * 30)
        
        if critical_issues:
            report.append("  1. HALT ALL DEPLOYMENT - Critical vulnerabilities present")
            report.append("  2. Replace eval() calls with safe expression evaluators")
            report.append("  3. Implement input sanitization for all user inputs")
        
        if any(i.category == 'template_injection' for i in issues):
            report.append("  4. Use restricted Jinja2 environment for templates")
            report.append("  5. Whitelist allowed template functions and variables")
        
        if any(i.category == 'shell_injection' for i in issues):
            report.append("  6. Use parameterized commands instead of string concatenation")
            report.append("  7. Validate all shell commands against whitelist")
        
        report.append("  8. Implement comprehensive input validation")
        report.append("  9. Add resource limits and DoS protection")
        report.append("  10. Enable security audit logging")
        
        return "\n".join(report)


def main():
    """Run security analysis on workflow system"""
    print("🔍 Starting Security Analysis of Workflow System...")
    
    # Analyze the workflow directory
    workflow_dir = os.path.join(os.path.dirname(__file__))
    analyzer = WorkflowSecurityAnalyzer()
    
    print(f"📁 Analyzing directory: {workflow_dir}")
    issues = analyzer.analyze_directory(workflow_dir)
    
    # Generate and display report
    report = analyzer.generate_security_report(issues)
    print(report)
    
    # Determine if deployment should be blocked
    critical_issues = [i for i in issues if i.severity == 'CRITICAL']
    high_issues = [i for i in issues if i.severity == 'HIGH']
    
    print("\n" + "=" * 50)
    if critical_issues:
        print("❌ DEPLOYMENT BLOCKED - Critical security vulnerabilities detected!")
        print("   Fix all CRITICAL issues before any deployment.")
        return False
    elif len(high_issues) > 3:
        print("⚠️  DEPLOYMENT NOT RECOMMENDED - Multiple high-risk vulnerabilities")
        print("   Address HIGH priority issues before production deployment.")
        return False
    else:
        print("✅ Security analysis complete - No critical issues detected")
        print("   Review and address any medium/low priority issues.")
        return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)