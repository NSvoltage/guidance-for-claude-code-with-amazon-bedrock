#!/usr/bin/env python3
"""
Secure Workflow Execution Engine for Claude Code Enterprise
Production-ready workflow engine with comprehensive security controls,
resource management, and enterprise-grade error handling.
"""
import os
import sys
import json
import subprocess
import asyncio
import uuid
import time
import hashlib
import tempfile
import shutil
import logging
import resource
import signal
from typing import Dict, Any, List, Optional, Tuple, Union, Set
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
import re
from contextlib import asynccontextmanager
import secrets
import threading
from functools import wraps

# Secure expression evaluator
try:
    from simpleeval import simple_eval, DEFAULT_FUNCTIONS, DEFAULT_NAMES
    SIMPLEEVAL_AVAILABLE = True
except ImportError:
    SIMPLEEVAL_AVAILABLE = False

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from parser.workflow_parser import WorkflowDefinition, WorkflowStep, WorkflowParser

# Configure secure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(process)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# Security configuration with environment variable support
class SecurityConfig:
    def __init__(self):
        self.MAX_WORKFLOW_DURATION = int(os.getenv('CLAUDE_WORKFLOW_MAX_DURATION', '3600'))  # 1 hour default
        self.MAX_STEP_DURATION = int(os.getenv('CLAUDE_STEP_MAX_DURATION', '1800'))        # 30 minutes default
        self.MAX_MEMORY_MB = int(os.getenv('CLAUDE_MAX_MEMORY_MB', '1024'))                # 1GB default
        self.MAX_FILE_SIZE_MB = int(os.getenv('CLAUDE_MAX_FILE_SIZE_MB', '100'))           # 100MB default
        self.MAX_CACHE_ENTRIES = int(os.getenv('CLAUDE_MAX_CACHE_ENTRIES', '1000'))        # Cache size limit
        self.MAX_LOG_LENGTH = int(os.getenv('CLAUDE_MAX_LOG_LENGTH', '1000'))              # Log line limit
        self.ENABLE_DETAILED_LOGGING = os.getenv('CLAUDE_DETAILED_LOGGING', 'false').lower() == 'true'
        self.SECURITY_PROFILE = os.getenv('CLAUDE_SECURITY_PROFILE', 'restricted')
        
        # Developer-friendly validation
        if self.MAX_WORKFLOW_DURATION < 60:
            logger.warning("MAX_WORKFLOW_DURATION is very low (<60s). Consider increasing for production.")
        if self.MAX_MEMORY_MB < 256:
            logger.warning("MAX_MEMORY_MB is very low (<256MB). This may cause workflow failures.")

# Global security configuration
SECURITY_CONFIG = SecurityConfig()


class SecurityError(Exception):
    """Security-related error"""
    pass


class ResourceExhaustionError(Exception):
    """Resource limits exceeded"""
    pass


class WorkflowTimeoutError(Exception):
    """Workflow execution timeout"""
    pass


class ExecutionStatus(Enum):
    """Workflow/Step execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CACHED = "cached"
    TIMEOUT = "timeout"
    TERMINATED = "terminated"


@dataclass
class SecurityContext:
    """Security context for workflow execution"""
    user_id: str
    permissions: Set[str]
    security_profile: str
    audit_trail: List[str] = field(default_factory=list)
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission"""
        return permission in self.permissions or "admin" in self.permissions
    
    def log_security_event(self, event: str):
        """Log security-related event"""
        timestamp = datetime.now(timezone.utc).isoformat()
        sanitized_event = self._sanitize_log_entry(event)
        self.audit_trail.append(f"{timestamp}: {sanitized_event}")
        logger.info(f"Security event for {self.user_id}: {sanitized_event}")
    
    def _sanitize_log_entry(self, entry: str) -> str:
        """Sanitize log entry to prevent log injection"""
        # Remove control characters and limit length
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', entry)
        return sanitized[:MAX_LOG_LENGTH]


class SecureInputValidator:
    """Secure input validation system with configurable strictness"""
    
    def __init__(self, strictness_level: str = "standard"):
        """Initialize validator with configurable strictness.
        
        Args:
            strictness_level: 'permissive', 'standard', 'strict', or 'paranoid'
        """
        self.strictness_level = strictness_level
        self._configure_patterns()
    
    def _configure_patterns(self):
        """Configure dangerous patterns based on strictness level"""
        # Base dangerous patterns that should always be blocked
        base_patterns = [
            r'__import__',
            r'exec\s*\(',
            r'eval\s*\(',
            r'getattr\s*\(.*__builtins__',
            r'globals\s*\(\)',
            r'__builtins__',
            r'__globals__',
            r'\.mro\(\)',
            r'\.subclasses\(\)',
        ]
        
        # Additional patterns based on strictness
        standard_patterns = [
            r'compile\s*\(',
            r'getattr\s*\(',
            r'setattr\s*\(',
            r'delattr\s*\(',
            r'locals\s*\(',
            r'vars\s*\(',
            r'dir\s*\(',
            r'subprocess',
            r'os\.system',
            r'os\.popen',
            r'os\.spawn',
            r'os\.exec',
            r'commands\.',
            r'importlib',
        ]
        
        strict_patterns = [
            r'open\s*\(',
            r'file\s*\(',
            r'input\s*\(',
            r'raw_input\s*\(',
        ]
        
        # Configure based on strictness level
        self.DANGEROUS_PATTERNS = base_patterns.copy()
        
        if self.strictness_level in ['standard', 'strict', 'paranoid']:
            self.DANGEROUS_PATTERNS.extend(standard_patterns)
            
        if self.strictness_level in ['strict', 'paranoid']:
            self.DANGEROUS_PATTERNS.extend(strict_patterns)
    
    # Safe shell command patterns
    SAFE_COMMANDS = {
        'pytest', 'npm', 'git', 'python', 'python3', 'pip', 'pip3',
        'node', 'yarn', 'docker', 'kubectl', 'terraform', 'ansible',
        'mvn', 'gradle', 'make', 'cargo', 'go', 'rustc', 'javac'
    }
    
        self.pattern_regex = re.compile('|'.join(self.DANGEROUS_PATTERNS), re.IGNORECASE)
    
    @classmethod
    def create_for_profile(cls, security_profile: str):
        """Create validator configured for specific security profile.
        
        Args:
            security_profile: 'plan_only', 'restricted', 'standard', 'elevated'
        """
        profile_mapping = {
            'plan_only': 'paranoid',
            'restricted': 'strict', 
            'standard': 'standard',
            'elevated': 'permissive'
        }
        strictness = profile_mapping.get(security_profile, 'standard')
        return cls(strictness)
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of validation configuration for debugging"""
        return {
            'strictness_level': self.strictness_level,
            'pattern_count': len(self.DANGEROUS_PATTERNS),
            'patterns': self.DANGEROUS_PATTERNS[:5] + ['...'] if len(self.DANGEROUS_PATTERNS) > 5 else self.DANGEROUS_PATTERNS
        }
    
    def validate_string_input(self, value: str, context: str = "") -> str:
        """Validate string input for security issues"""
        if not isinstance(value, str):
            raise SecurityError(f"Expected string input in {context}")
        
        # Check for dangerous patterns
        match = self.pattern_regex.search(value)
        if match:
            if SECURITY_CONFIG.ENABLE_DETAILED_LOGGING:
                logger.warning(f"Blocked dangerous pattern '{match.group()}' in {context}")
            raise SecurityError(
                f"Security violation in {context}: Potentially dangerous content detected. "
                f"Pattern blocked for security. Check security profile settings."
            )
        
        # Configurable length limits based on strictness
        max_length = self._get_max_length()
        if len(value) > max_length:
            raise SecurityError(
                f"Input too long in {context} (max {max_length} characters for {self.strictness_level} profile)"
            )
        
        return value
    
    def _get_max_length(self) -> int:
        """Get maximum string length based on strictness level"""
        limits = {
            'permissive': 50000,
            'standard': 10000,
            'strict': 5000,
            'paranoid': 2000
        }
        return limits.get(self.strictness_level, 10000)
    
    def validate_file_path(self, path: str) -> str:
        """Validate file path for security"""
        if not isinstance(path, str):
            raise SecurityError("File path must be string")
        
        # Normalize path
        normalized = os.path.normpath(path)
        
        # Prevent path traversal
        if '..' in normalized or normalized.startswith('/'):
            raise SecurityError(f"Invalid file path: {path}")
        
        # Prevent access to sensitive directories
        sensitive_dirs = ['etc', 'proc', 'sys', 'dev', 'root', 'home']
        path_parts = Path(normalized).parts
        if any(part in sensitive_dirs for part in path_parts):
            raise SecurityError(f"Access to sensitive directory denied: {path}")
        
        return normalized
    
    def validate_shell_command(self, command: str) -> str:
        """Validate shell command for security"""
        command = self.validate_string_input(command, "shell command")
        
        # Extract first command
        first_command = command.strip().split()[0] if command.strip() else ""
        
        # Check if it's a safe command
        if first_command and first_command not in self.SAFE_COMMANDS:
            logger.warning(f"Potentially unsafe command: {first_command}")
        
        # Check for dangerous shell patterns
        dangerous_shell_patterns = [
            r';\s*rm\s+-rf',
            r'&&\s*rm\s+-rf', 
            r'\|\s*sh',
            r'\|\s*bash',
            r'>\s*/dev/',
            r'curl.*\|\s*sh',
            r'wget.*\|\s*sh',
            r'\$\([^)]*\)',  # Command substitution
            r'`[^`]*`',      # Backtick command substitution
        ]
        
        for pattern in dangerous_shell_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                raise SecurityError(f"Dangerous shell pattern detected: {pattern}")
        
        return command
    
    def validate_template_content(self, template: str) -> str:
        """Validate template content for injection attacks"""
        template = self.validate_string_input(template, "template")
        
        # Check for template injection patterns
        injection_patterns = [
            r'\{\{.*__.*\}\}',
            r'\{\{.*class.*\}\}',
            r'\{\{.*mro.*\}\}',
            r'\{\{.*subclasses.*\}\}',
            r'\{\{.*globals.*\}\}',
            r'\{\{.*builtins.*\}\}',
            r'\{\{.*import.*\}\}',
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, template, re.IGNORECASE):
                raise SecurityError(f"Template injection pattern detected: {pattern}")
        
        return template


class SecureExpressionEvaluator:
    """Secure expression evaluator replacing eval()"""
    
    def __init__(self):
        if SIMPLEEVAL_AVAILABLE:
            # Configure safe evaluation environment
            self.safe_names = DEFAULT_NAMES.copy()
            self.safe_functions = DEFAULT_FUNCTIONS.copy()
            
            # Remove dangerous functions
            dangerous_functions = ['__import__', 'exec', 'eval', 'compile', 'open', 'file']
            for func in dangerous_functions:
                self.safe_functions.pop(func, None)
                self.safe_names.pop(func, None)
        else:
            logger.error("simpleeval not available - expression evaluation will be limited")
    
    def evaluate_condition(self, expression: str, context: Dict[str, Any]) -> bool:
        """Safely evaluate boolean condition"""
        if not SIMPLEEVAL_AVAILABLE:
            # Fallback to very basic evaluation
            return self._basic_boolean_eval(expression, context)
        
        try:
            # Sanitize expression
            expression = expression.strip()
            if not expression:
                return False
            
            # Simple boolean checks first
            if expression.lower() in ['true', '1', 'yes']:
                return True
            if expression.lower() in ['false', '0', 'no', '']:
                return False
            
            # Use simpleeval for complex expressions
            result = simple_eval(
                expression,
                names=context,
                functions=self.safe_functions
            )
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Expression evaluation failed: {e}")
            raise SecurityError(f"Invalid expression: {expression}")
    
    def _basic_boolean_eval(self, expression: str, context: Dict[str, Any]) -> bool:
        """Basic boolean evaluation fallback"""
        expression = expression.strip().lower()
        
        # Basic boolean values
        if expression in ['true', '1', 'yes']:
            return True
        if expression in ['false', '0', 'no', '']:
            return False
        
        # Simple variable lookup
        if expression in context:
            return bool(context[expression])
        
        # Simple comparisons (very limited)
        comparison_ops = ['==', '!=', '>', '<', '>=', '<=']
        for op in comparison_ops:
            if op in expression:
                parts = expression.split(op, 1)
                if len(parts) == 2:
                    left = parts[0].strip()
                    right = parts[1].strip()
                    
                    # Simple value comparison
                    left_val = context.get(left, left)
                    right_val = context.get(right, right)
                    
                    try:
                        if op == '==':
                            return str(left_val) == str(right_val)
                        elif op == '!=':
                            return str(left_val) != str(right_val)
                        # Add other operators as needed
                    except:
                        pass
        
        logger.warning(f"Could not evaluate expression safely: {expression}")
        return False


class ResourceManager:
    """Manages resource limits and quotas"""
    
    def __init__(self):
        self.active_workflows: Dict[str, Dict[str, Any]] = {}
        self.resource_lock = threading.Lock()
    
    def allocate_resources(self, execution_id: str, limits: Dict[str, Any]) -> bool:
        """Allocate resources for workflow execution"""
        with self.resource_lock:
            if len(self.active_workflows) >= 100:  # Max concurrent workflows
                raise ResourceExhaustionError("Maximum concurrent workflows exceeded")
            
            # Set resource limits
            try:
                # Memory limit
                memory_limit = limits.get('memory_mb', MAX_MEMORY_MB)
                resource.setrlimit(resource.RLIMIT_AS, (memory_limit * 1024 * 1024, -1))
                
                # CPU time limit
                cpu_limit = limits.get('cpu_seconds', MAX_WORKFLOW_DURATION)
                resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, -1))
                
                self.active_workflows[execution_id] = {
                    'allocated_at': time.time(),
                    'limits': limits
                }
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to allocate resources: {e}")
                return False
    
    def release_resources(self, execution_id: str):
        """Release resources for workflow"""
        with self.resource_lock:
            self.active_workflows.pop(execution_id, None)
    
    def check_resource_usage(self, execution_id: str) -> Dict[str, Any]:
        """Check current resource usage"""
        if execution_id not in self.active_workflows:
            return {}
        
        try:
            usage = resource.getrusage(resource.RUSAGE_SELF)
            return {
                'memory_mb': usage.ru_maxrss / 1024,  # Convert to MB
                'cpu_time': usage.ru_utime + usage.ru_stime,
                'execution_id': execution_id
            }
        except Exception as e:
            logger.error(f"Failed to get resource usage: {e}")
            return {}


class SecureStepResult:
    """Secure step execution result with sanitized data"""
    
    def __init__(self, step_id: str, status: ExecutionStatus):
        self.step_id = step_id
        self.status = status
        self.started_at = datetime.now(timezone.utc)
        self.completed_at: Optional[datetime] = None
        self.duration_seconds: float = 0.0
        self.outputs: Dict[str, Any] = {}
        self.error: Optional[str] = None
        self.cached: bool = False
        self.cache_key: Optional[str] = None
        self.sanitized_stdout: Optional[str] = None
        self.exit_code: Optional[int] = None
    
    def set_completed(self, outputs: Dict[str, Any] = None):
        """Mark step as completed"""
        self.completed_at = datetime.now(timezone.utc)
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        self.status = ExecutionStatus.COMPLETED
        if outputs:
            self.outputs = self._sanitize_outputs(outputs)
    
    def set_failed(self, error: str):
        """Mark step as failed"""
        self.completed_at = datetime.now(timezone.utc)
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        self.status = ExecutionStatus.FAILED
        self.error = self._sanitize_error(error)
    
    def _sanitize_outputs(self, outputs: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize step outputs"""
        sanitized = {}
        for key, value in outputs.items():
            if isinstance(value, str):
                # Remove potential secrets and limit size
                sanitized_value = re.sub(r'(password|token|key|secret)=\S+', '[REDACTED]', str(value), flags=re.IGNORECASE)
                sanitized[key] = sanitized_value[:1000]  # Limit size
            elif isinstance(value, (int, float, bool)):
                sanitized[key] = value
            else:
                sanitized[key] = str(value)[:1000]
        return sanitized
    
    def _sanitize_error(self, error: str) -> str:
        """Sanitize error message"""
        if not isinstance(error, str):
            error = str(error)
        
        # Remove potential secrets
        sanitized = re.sub(r'(password|token|key|secret)[=:]\s*\S+', '[REDACTED]', error, flags=re.IGNORECASE)
        return sanitized[:500]  # Limit error message length


class SecureWorkflowEngine:
    """Secure workflow execution engine with comprehensive security controls"""
    
    def __init__(self, parser: Optional[WorkflowParser] = None, security_profile: str = None):
        """Initialize secure workflow engine.
        
        Args:
            parser: Optional workflow parser instance
            security_profile: Security profile to use ('plan_only', 'restricted', 'standard', 'elevated')
        """
        self.security_profile = security_profile or SECURITY_CONFIG.SECURITY_PROFILE
        self.parser = parser or WorkflowParser()
        self.validator = SecureInputValidator.create_for_profile(self.security_profile)
        self.evaluator = SecureExpressionEvaluator()
        self.resource_manager = ResourceManager()
        
        # Secure storage
        self.executions: Dict[str, Dict[str, Any]] = {}
        self.step_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_lock = threading.Lock()
        
        # Security settings based on profile
        profile_settings = {
            'plan_only': {'max_concurrent': 10, 'audit_enabled': True, 'allow_execution': False},
            'restricted': {'max_concurrent': 25, 'audit_enabled': True, 'allow_execution': True},
            'standard': {'max_concurrent': 50, 'audit_enabled': True, 'allow_execution': True},
            'elevated': {'max_concurrent': 100, 'audit_enabled': True, 'allow_execution': True}
        }
        
        settings = profile_settings.get(self.security_profile, profile_settings['standard'])
        self.max_concurrent_workflows = settings['max_concurrent']
        self.audit_enabled = settings['audit_enabled']
        self.allow_execution = settings['allow_execution']
        
        if SECURITY_CONFIG.ENABLE_DETAILED_LOGGING:
            logger.info(f"Initialized SecureWorkflowEngine with profile '{self.security_profile}'")
            logger.info(f"Configuration: {self.get_engine_status()}")
        
        # Initialize cache cleanup
        self._start_cache_cleanup_timer()
    
    def get_engine_status(self) -> Dict[str, Any]:
        """Get current engine status and configuration for debugging"""
        return {
            'security_profile': self.security_profile,
            'max_concurrent_workflows': self.max_concurrent_workflows,
            'audit_enabled': self.audit_enabled,
            'allow_execution': self.allow_execution,
            'active_workflows': len(self.executions),
            'cache_size': len(self.step_cache),
            'validator_config': self.validator.get_validation_summary()
        }
    
    async def execute_workflow_securely(
        self,
        workflow: WorkflowDefinition,
        inputs: Dict[str, Any],
        security_context: SecurityContext,
        execution_id: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Execute workflow with comprehensive security controls"""
        
        if execution_id is None:
            execution_id = str(uuid.uuid4())
        
        # Validate inputs
        self._validate_workflow_inputs(workflow, inputs, security_context)
        
        # Check permissions
        if not security_context.has_permission("workflow.execute"):
            raise SecurityError("User lacks permission to execute workflows")
        
        # Allocate resources
        resource_limits = security_context.resource_limits or {
            'memory_mb': MAX_MEMORY_MB,
            'cpu_seconds': MAX_WORKFLOW_DURATION
        }
        
        if not self.resource_manager.allocate_resources(execution_id, resource_limits):
            raise ResourceExhaustionError("Failed to allocate resources for workflow")
        
        try:
            # Create execution record
            execution_record = {
                'execution_id': execution_id,
                'workflow_name': workflow.name,
                'workflow_version': workflow.version,
                'status': ExecutionStatus.RUNNING,
                'started_at': datetime.now(timezone.utc),
                'security_context': asdict(security_context),
                'step_results': {},
                'inputs': self._sanitize_inputs(inputs),
                'outputs': {}
            }
            
            self.executions[execution_id] = execution_record
            security_context.log_security_event(f"Workflow execution started: {workflow.name}")
            
            # Execute with timeout
            result = await asyncio.wait_for(
                self._execute_workflow_steps(workflow, inputs, security_context, execution_id),
                timeout=resource_limits.get('cpu_seconds', MAX_WORKFLOW_DURATION)
            )
            
            execution_record['status'] = ExecutionStatus.COMPLETED
            execution_record['completed_at'] = datetime.now(timezone.utc)
            execution_record['outputs'] = result
            
            security_context.log_security_event(f"Workflow execution completed: {workflow.name}")
            
            return execution_record
            
        except asyncio.TimeoutError:
            security_context.log_security_event(f"Workflow execution timeout: {workflow.name}")
            raise WorkflowTimeoutError(f"Workflow {workflow.name} exceeded time limit")
            
        except SecurityError:
            security_context.log_security_event(f"Security violation in workflow: {workflow.name}")
            raise
            
        except Exception as e:
            security_context.log_security_event(f"Workflow execution failed: {workflow.name} - {str(e)}")
            raise
            
        finally:
            self.resource_manager.release_resources(execution_id)
    
    async def _execute_workflow_steps(
        self,
        workflow: WorkflowDefinition,
        inputs: Dict[str, Any],
        security_context: SecurityContext,
        execution_id: str
    ) -> Dict[str, Any]:
        """Execute workflow steps securely"""
        
        context = {
            'inputs': inputs,
            'workflow': {
                'name': workflow.name,
                'version': workflow.version
            },
            'execution_id': execution_id,
            'steps': {}
        }
        
        execution_record = self.executions[execution_id]
        
        # Execute steps in dependency order
        for step_id in workflow.execution_order:
            step = next(s for s in workflow.steps if s.id == step_id)
            
            # Check if step should be executed
            if step.when and not self._should_execute_step(step.when, context, security_context):
                result = SecureStepResult(step_id, ExecutionStatus.SKIPPED)
                result.set_completed()
                execution_record['step_results'][step_id] = asdict(result)
                context['steps'][step_id] = asdict(result)
                continue
            
            # Execute step securely
            try:
                result = await self._execute_step_securely(step, context, security_context)
                execution_record['step_results'][step_id] = asdict(result)
                context['steps'][step_id] = asdict(result)
                
                if result.status == ExecutionStatus.FAILED:
                    raise Exception(f"Step {step_id} failed: {result.error}")
                
            except Exception as e:
                security_context.log_security_event(f"Step execution failed: {step_id} - {str(e)}")
                raise
        
        # Extract workflow outputs
        outputs = {}
        for output_name, output_config in workflow.outputs.items():
            if output_config.from_step:
                output_value = self._extract_output_value(output_config.from_step, context)
                outputs[output_name] = output_value
        
        return outputs
    
    async def _execute_step_securely(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        security_context: SecurityContext
    ) -> SecureStepResult:
        """Execute individual step with security controls"""
        
        result = SecureStepResult(step.id, ExecutionStatus.RUNNING)
        
        try:
            # Check cache first
            if step.cache.get('enabled', True):
                cache_key = self._generate_cache_key(step, context)
                cached_result = self._get_cached_result(cache_key)
                
                if cached_result:
                    result.cached = True
                    result.cache_key = cache_key
                    result.outputs = cached_result.get('outputs', {})
                    result.set_completed()
                    return result
            
            # Execute based on step type
            if step.type == 'shell':
                await self._execute_shell_step(step, context, security_context, result)
            elif step.type == 'assert':
                await self._execute_assert_step(step, context, security_context, result)
            elif step.type == 'template':
                await self._execute_template_step(step, context, security_context, result)
            else:
                raise SecurityError(f"Unsupported step type: {step.type}")
            
            # Cache successful results
            if (result.status == ExecutionStatus.COMPLETED and 
                step.cache.get('enabled', True)):
                self._cache_result(result.cache_key or cache_key, result)
            
        except Exception as e:
            result.set_failed(str(e))
            security_context.log_security_event(f"Step {step.id} failed: {str(e)}")
        
        return result
    
    async def _execute_shell_step(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        security_context: SecurityContext,
        result: SecureStepResult
    ):
        """Execute shell command step with security controls"""
        
        if not security_context.has_permission("shell.execute"):
            raise SecurityError("User lacks permission to execute shell commands")
        
        # Validate and sanitize command
        raw_command = step.command or ""
        sanitized_command = self.validator.validate_shell_command(raw_command)
        
        # Render template safely
        try:
            # Use secure template rendering (implementation would need secure Jinja2 setup)
            rendered_command = self._render_template_securely(sanitized_command, context)
        except Exception as e:
            raise SecurityError(f"Template rendering failed: {e}")
        
        # Execute in secure environment
        try:
            process = await asyncio.create_subprocess_shell(
                rendered_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._create_secure_environment(step.environment),
                cwd=self._validate_working_directory(step.working_directory),
                preexec_fn=self._drop_privileges  # Drop privileges before execution
            )
            
            # Wait with timeout
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=min(step.timeout, MAX_STEP_DURATION)
            )
            
            result.sanitized_stdout = self._sanitize_output(stdout_bytes.decode('utf-8', errors='ignore'))
            stderr_content = self._sanitize_output(stderr_bytes.decode('utf-8', errors='ignore'))
            result.exit_code = process.returncode
            
            if process.returncode == 0:
                # Extract outputs if defined
                outputs = {}
                for output_name, output_config in step.outputs.items():
                    outputs[output_name] = result.sanitized_stdout.strip()
                
                result.set_completed(outputs)
            else:
                result.set_failed(f"Command failed with exit code {process.returncode}: {stderr_content}")
                
        except asyncio.TimeoutError:
            if 'process' in locals():
                process.kill()
                await process.wait()
            result.set_failed(f"Command timed out after {step.timeout} seconds")
        
        security_context.log_security_event(f"Shell command executed: {step.id}")
    
    async def _execute_assert_step(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        security_context: SecurityContext,
        result: SecureStepResult
    ):
        """Execute assertion step with secure evaluation"""
        
        condition = step.condition or ""
        
        try:
            # Validate condition expression
            self.validator.validate_string_input(condition, "assertion condition")
            
            # Safely evaluate condition
            assertion_passed = self.evaluator.evaluate_condition(condition, context)
            
            if assertion_passed:
                result.set_completed({'assertion_result': True})
            else:
                if step.on_failure == 'fail':
                    result.set_failed(step.message or f"Assertion failed: {condition}")
                elif step.on_failure == 'warn':
                    result.set_completed({
                        'assertion_result': False,
                        'warning': step.message or f"Assertion failed: {condition}"
                    })
                else:  # continue
                    result.status = ExecutionStatus.SKIPPED
                    result.set_completed({'assertion_result': False})
        
        except Exception as e:
            result.set_failed(f"Assertion evaluation error: {str(e)}")
        
        security_context.log_security_event(f"Assertion executed: {step.id}")
    
    async def _execute_template_step(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        security_context: SecurityContext,
        result: SecureStepResult
    ):
        """Execute template generation step"""
        
        if not security_context.has_permission("file.write"):
            raise SecurityError("User lacks permission to write files")
        
        try:
            # Validate template content
            template_content = self.validator.validate_template_content(step.template or "")
            output_path = self.validator.validate_file_path(step.output or "")
            
            # Render template securely
            rendered_content = self._render_template_securely(template_content, context)
            
            # Write to secure location
            secure_output_path = self._create_secure_file_path(output_path)
            
            # Check file size limit
            if len(rendered_content.encode('utf-8')) > MAX_FILE_SIZE_MB * 1024 * 1024:
                raise SecurityError(f"Generated file too large (max {MAX_FILE_SIZE_MB}MB)")
            
            # Write file securely
            os.makedirs(os.path.dirname(secure_output_path), mode=0o755, exist_ok=True)
            with open(secure_output_path, 'w', encoding='utf-8') as f:
                f.write(rendered_content)
            
            # Set restrictive permissions
            os.chmod(secure_output_path, 0o644)
            
            result.set_completed({
                'output_file': secure_output_path,
                'template_size': len(rendered_content)
            })
            
        except Exception as e:
            result.set_failed(f"Template execution error: {str(e)}")
        
        security_context.log_security_event(f"Template generated: {step.id}")
    
    def _should_execute_step(self, condition: str, context: Dict[str, Any], security_context: SecurityContext) -> bool:
        """Determine if step should be executed based on condition"""
        try:
            return self.evaluator.evaluate_condition(condition, context)
        except Exception as e:
            security_context.log_security_event(f"Step condition evaluation failed: {str(e)}")
            return False
    
    def _validate_workflow_inputs(self, workflow: WorkflowDefinition, inputs: Dict[str, Any], security_context: SecurityContext):
        """Validate workflow inputs against security policies"""
        
        # Check required inputs
        for input_name, input_config in workflow.inputs.items():
            if input_config.required and input_name not in inputs:
                raise SecurityError(f"Required input missing: {input_name}")
            
            if input_name in inputs:
                # Validate input type and content
                input_value = inputs[input_name]
                if isinstance(input_value, str):
                    self.validator.validate_string_input(input_value, f"input {input_name}")
        
        security_context.log_security_event(f"Workflow inputs validated: {len(inputs)} inputs")
    
    def _sanitize_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize inputs for logging"""
        sanitized = {}
        sensitive_keys = ['password', 'token', 'key', 'secret', 'credential']
        
        for key, value in inputs.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = '[REDACTED]'
            else:
                sanitized[key] = str(value)[:100]  # Limit length
        
        return sanitized
    
    def _render_template_securely(self, template: str, context: Dict[str, Any]) -> str:
        """Render template with security controls"""
        # This would need a secure Jinja2 setup with restricted environment
        # For now, implement basic variable substitution
        
        result = template
        pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9._]*)\s*\}\}'
        
        def replace_var(match):
            var_name = match.group(1)
            keys = var_name.split('.')
            value = context
            
            try:
                for key in keys:
                    value = value[key]
                return str(value) if value is not None else ""
            except (KeyError, TypeError):
                return match.group(0)  # Return original if not found
        
        return re.sub(pattern, replace_var, result)
    
    def _create_secure_environment(self, extra_env: Dict[str, str]) -> Dict[str, str]:
        """Create secure environment for command execution"""
        
        # Start with minimal safe environment
        safe_env = {
            'PATH': '/usr/local/bin:/usr/bin:/bin',
            'HOME': '/tmp',
            'USER': 'workflow-runner',
            'SHELL': '/bin/sh',
            'LANG': 'en_US.UTF-8'
        }
        
        # Add validated extra environment variables
        for key, value in extra_env.items():
            if re.match(r'^[A-Z_][A-Z0-9_]*$', key):  # Valid env var name
                safe_env[key] = self.validator.validate_string_input(str(value), f"env var {key}")
        
        return safe_env
    
    def _validate_working_directory(self, working_dir: Optional[str]) -> Optional[str]:
        """Validate and secure working directory"""
        if not working_dir:
            return None
        
        validated_dir = self.validator.validate_file_path(working_dir)
        
        # Ensure directory exists and is accessible
        if not os.path.exists(validated_dir):
            os.makedirs(validated_dir, mode=0o755, exist_ok=True)
        
        return validated_dir
    
    def _create_secure_file_path(self, file_path: str) -> str:
        """Create secure file path in controlled location"""
        validated_path = self.validator.validate_file_path(file_path)
        
        # Create in secure workspace
        workspace = os.path.join(tempfile.gettempdir(), 'workflow-workspace')
        os.makedirs(workspace, mode=0o755, exist_ok=True)
        
        secure_path = os.path.join(workspace, validated_path)
        
        # Ensure we don't escape the workspace
        if not os.path.commonpath([workspace, secure_path]).startswith(workspace):
            raise SecurityError(f"File path escapes secure workspace: {file_path}")
        
        return secure_path
    
    def _drop_privileges(self):
        """Drop privileges before executing commands"""
        try:
            # This would be implemented based on the deployment environment
            # For example, switching to a non-privileged user
            pass
        except Exception as e:
            logger.warning(f"Failed to drop privileges: {e}")
    
    def _sanitize_output(self, output: str) -> str:
        """Sanitize command output"""
        if not output:
            return ""
        
        # Remove potential secrets
        sanitized = re.sub(
            r'(password|token|key|secret|credential)[=:\s]+\S+',
            '[REDACTED]',
            output,
            flags=re.IGNORECASE
        )
        
        # Limit size
        return sanitized[:5000]
    
    def _generate_cache_key(self, step: WorkflowStep, context: Dict[str, Any]) -> str:
        """Generate secure cache key"""
        key_components = [
            step.id,
            step.type,
            json.dumps(step.inputs, sort_keys=True, default=str),
            json.dumps(context.get('inputs', {}), sort_keys=True, default=str)
        ]
        
        key_string = '|'.join(str(c) for c in key_components)
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get result from cache with TTL check"""
        with self.cache_lock:
            if cache_key not in self.step_cache:
                return None
            
            cached_data = self.step_cache[cache_key]
            
            # Check TTL
            cached_at = cached_data.get('cached_at', 0)
            ttl = cached_data.get('ttl', 3600)  # Default 1 hour
            
            if time.time() - cached_at > ttl:
                del self.step_cache[cache_key]
                return None
            
            return cached_data
    
    def _cache_result(self, cache_key: str, result: SecureStepResult):
        """Cache step result with size limits"""
        with self.cache_lock:
            # Enforce cache size limits
            if len(self.step_cache) >= MAX_CACHE_ENTRIES:
                # Remove oldest entries
                oldest_keys = sorted(
                    self.step_cache.keys(),
                    key=lambda k: self.step_cache[k].get('cached_at', 0)
                )[:10]
                
                for old_key in oldest_keys:
                    del self.step_cache[old_key]
            
            self.step_cache[cache_key] = {
                'outputs': result.outputs,
                'cached_at': time.time(),
                'ttl': 3600  # 1 hour default
            }
    
    def _extract_output_value(self, reference: str, context: Dict[str, Any]) -> Any:
        """Safely extract output value from step reference"""
        try:
            parts = reference.split('.')
            value = context
            
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return None
            
            return value
        except Exception:
            return None
    
    def _start_cache_cleanup_timer(self):
        """Start background cache cleanup"""
        def cleanup_cache():
            while True:
                try:
                    time.sleep(300)  # Cleanup every 5 minutes
                    with self.cache_lock:
                        current_time = time.time()
                        expired_keys = []
                        
                        for key, data in self.step_cache.items():
                            cached_at = data.get('cached_at', 0)
                            ttl = data.get('ttl', 3600)
                            
                            if current_time - cached_at > ttl:
                                expired_keys.append(key)
                        
                        for key in expired_keys:
                            del self.step_cache[key]
                        
                        if expired_keys:
                            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
                            
                except Exception as e:
                    logger.error(f"Cache cleanup error: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_cache, daemon=True)
        cleanup_thread.start()


# Factory functions for secure engine creation
def create_secure_workflow_engine(security_profile: str = None) -> SecureWorkflowEngine:
    """Create a secure workflow engine with specified security profile.
    
    Args:
        security_profile: Security profile to use ('plan_only', 'restricted', 'standard', 'elevated')
        
    Returns:
        Configured SecureWorkflowEngine instance
    """
    return SecureWorkflowEngine(security_profile=security_profile)

def create_development_engine() -> SecureWorkflowEngine:
    """Create workflow engine suitable for development with relaxed security"""
    return SecureWorkflowEngine(security_profile='elevated')

def create_production_engine() -> SecureWorkflowEngine:
    """Create workflow engine suitable for production with standard security"""
    return SecureWorkflowEngine(security_profile='standard')

def create_plan_only_engine() -> SecureWorkflowEngine:
    """Create workflow engine for plan-only mode with maximum security"""
    return SecureWorkflowEngine(security_profile='plan_only')


if __name__ == "__main__":
    # Example usage
    async def main():
        engine = create_secure_workflow_engine()
        
        # Create security context
        security_context = SecurityContext(
            user_id="test-user",
            permissions={"workflow.execute", "shell.execute", "file.write"},
            security_profile="restricted"
        )
        
        # This would need a proper workflow definition
        print("Secure workflow engine initialized")
    
    asyncio.run(main())