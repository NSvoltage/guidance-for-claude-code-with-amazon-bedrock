#!/usr/bin/env python3
"""
Enhanced OpenTelemetry tracer for Claude Code Enterprise
Provides comprehensive span instrumentation with detailed user attribution,
cost tracking, and performance metrics.
"""

import os
import sys
import json
import time
import uuid
import hashlib
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.semconv.trace import SpanAttributes
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    # Mock classes for when OTEL is not available
    class MockSpan:
        def set_attribute(self, key: str, value: Any) -> None: pass
        def set_status(self, status: Any) -> None: pass
        def add_event(self, name: str, attributes: Optional[Dict] = None) -> None: pass
        def __enter__(self): return self
        def __exit__(self, *args): pass


# Span attribute keys following OpenTelemetry semantic conventions
class ClaudeCodeAttributes:
    # User and organization attributes
    USER_ID = "claude.user.id"
    USER_EMAIL = "claude.user.email"  
    USER_NAME = "claude.user.name"
    USER_TEAM = "claude.user.team"
    USER_DEPARTMENT = "claude.user.department"
    USER_ROLE = "claude.user.role"
    
    # Enterprise governance attributes
    SECURITY_PROFILE = "claude.security.profile"
    POLICY_VERSION = "claude.security.policy_version"
    ENTERPRISE_ORG = "claude.enterprise.organization"
    
    # Operation attributes
    OPERATION_TYPE = "claude.operation.type"
    OPERATION_ID = "claude.operation.id"
    OPERATION_STEP = "claude.operation.step"
    OPERATION_WORKFLOW = "claude.operation.workflow"
    
    # Model and request attributes
    MODEL_ID = "claude.model.id"
    MODEL_PROVIDER = "claude.model.provider" 
    REQUEST_TOKENS_INPUT = "claude.request.tokens.input"
    REQUEST_TOKENS_OUTPUT = "claude.request.tokens.output"
    REQUEST_TOKENS_TOTAL = "claude.request.tokens.total"
    
    # Performance attributes
    CACHE_HIT = "claude.cache.hit"
    CACHE_KEY = "claude.cache.key"
    LATENCY_MODEL_MS = "claude.latency.model_ms"
    LATENCY_TOTAL_MS = "claude.latency.total_ms"
    
    # Cost attributes
    COST_ESTIMATE_USD = "claude.cost.estimate_usd"
    COST_INPUT_USD = "claude.cost.input_usd"
    COST_OUTPUT_USD = "claude.cost.output_usd"
    COST_CACHE_SAVINGS_USD = "claude.cost.cache_savings_usd"
    
    # Context attributes
    PROJECT_NAME = "claude.project.name"
    PROJECT_PATH = "claude.project.path"
    REPOSITORY_URL = "claude.repository.url"
    BRANCH_NAME = "claude.repository.branch"
    
    # Quality and success attributes
    SUCCESS = "claude.operation.success"
    ERROR_TYPE = "claude.error.type"
    ERROR_MESSAGE = "claude.error.message"
    RETRY_COUNT = "claude.operation.retry_count"


@dataclass
class UserContext:
    """User context extracted from authentication tokens"""
    user_id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    team: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    organization: Optional[str] = None
    security_profile: Optional[str] = None


@dataclass  
class ModelContext:
    """Model and request context"""
    model_id: Optional[str] = None
    provider: str = "anthropic"
    tokens_input: int = 0
    tokens_output: int = 0
    cache_hit: bool = False
    cache_key: Optional[str] = None
    
    @property
    def tokens_total(self) -> int:
        return self.tokens_input + self.tokens_output


@dataclass
class CostContext:
    """Cost tracking context"""
    input_cost_per_token: float = 0.000008  # Default Claude 3 pricing
    output_cost_per_token: float = 0.000024
    cache_savings_multiplier: float = 0.9  # 90% savings on cache hits
    
    def calculate_cost(self, model_ctx: ModelContext) -> Dict[str, float]:
        """Calculate detailed cost breakdown"""
        input_cost = model_ctx.tokens_input * self.input_cost_per_token
        output_cost = model_ctx.tokens_output * self.output_cost_per_token
        total_cost = input_cost + output_cost
        
        cache_savings = 0.0
        if model_ctx.cache_hit:
            cache_savings = input_cost * self.cache_savings_multiplier
            total_cost -= cache_savings
            
        return {
            "input_usd": input_cost,
            "output_usd": output_cost, 
            "total_usd": total_cost,
            "cache_savings_usd": cache_savings
        }


class ClaudeCodeTracer:
    """Enhanced OpenTelemetry tracer for Claude Code operations"""
    
    def __init__(self, service_name: str = "claude-code-enterprise"):
        self.service_name = service_name
        self.tracer = None
        self._user_context = UserContext()
        self._cost_context = CostContext()
        
        if OTEL_AVAILABLE:
            self._initialize_tracer()
        
    def _initialize_tracer(self):
        """Initialize OpenTelemetry tracer with enterprise resource attributes"""
        # Create resource with service information
        resource = Resource.create({
            "service.name": self.service_name,
            "service.version": self._get_version(),
            "deployment.environment": os.getenv("DEPLOYMENT_ENVIRONMENT", "production"),
            "claude.enterprise.enabled": "true"
        })
        
        # Set up tracer provider
        trace.set_tracer_provider(TracerProvider(resource=resource))
        
        # Configure OTLP exporter
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        exporter = OTLPSpanExporter(endpoint=endpoint)
        
        # Add span processor
        span_processor = BatchSpanProcessor(exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)
        
        # Get tracer
        self.tracer = trace.get_tracer(self.service_name)
        
    def _get_version(self) -> str:
        """Get Claude Code version"""
        return os.getenv("CLAUDE_CODE_VERSION", "1.0.0")
        
    def update_user_context(self, user_ctx: UserContext):
        """Update user context for all subsequent spans"""
        self._user_context = user_ctx
        
    def update_cost_context(self, cost_ctx: CostContext):
        """Update cost calculation context"""
        self._cost_context = cost_ctx

    @contextmanager
    def span(self, 
             operation_name: str,
             operation_type: str,
             model_ctx: Optional[ModelContext] = None,
             project_ctx: Optional[Dict[str, str]] = None,
             **additional_attributes):
        """Create an enhanced span with comprehensive attributes"""
        
        if not OTEL_AVAILABLE or not self.tracer:
            yield MockSpan()
            return
            
        operation_id = str(uuid.uuid4())
        start_time = time.time()
        
        with self.tracer.start_as_current_span(operation_name) as span:
            try:
                # Set basic operation attributes
                span.set_attribute(ClaudeCodeAttributes.OPERATION_TYPE, operation_type)
                span.set_attribute(ClaudeCodeAttributes.OPERATION_ID, operation_id)
                span.set_attribute(SpanAttributes.HTTP_USER_AGENT, f"claude-code-enterprise/{self._get_version()}")
                
                # Set user and organization attributes
                self._set_user_attributes(span)
                
                # Set model and request attributes  
                if model_ctx:
                    self._set_model_attributes(span, model_ctx)
                    self._set_cost_attributes(span, model_ctx)
                
                # Set project context
                if project_ctx:
                    self._set_project_attributes(span, project_ctx)
                
                # Set additional custom attributes
                for key, value in additional_attributes.items():
                    span.set_attribute(key, value)
                
                yield span
                
                # Mark as successful
                span.set_attribute(ClaudeCodeAttributes.SUCCESS, True)
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                # Record error information
                span.set_attribute(ClaudeCodeAttributes.SUCCESS, False)
                span.set_attribute(ClaudeCodeAttributes.ERROR_TYPE, type(e).__name__)
                span.set_attribute(ClaudeCodeAttributes.ERROR_MESSAGE, str(e))
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
            finally:
                # Always record timing
                total_latency = int((time.time() - start_time) * 1000)
                span.set_attribute(ClaudeCodeAttributes.LATENCY_TOTAL_MS, total_latency)

    def _set_user_attributes(self, span):
        """Set user and organization attributes"""
        ctx = self._user_context
        
        if ctx.user_id:
            # Hash user ID for privacy while maintaining correlation
            user_hash = hashlib.sha256(ctx.user_id.encode()).hexdigest()[:16]
            span.set_attribute(ClaudeCodeAttributes.USER_ID, user_hash)
            
        if ctx.email:
            # Hash email domain for privacy
            domain = ctx.email.split('@')[-1] if '@' in ctx.email else 'unknown'
            span.set_attribute("claude.user.domain", domain)
            
        if ctx.name:
            span.set_attribute(ClaudeCodeAttributes.USER_NAME, ctx.name)
        if ctx.team:
            span.set_attribute(ClaudeCodeAttributes.USER_TEAM, ctx.team)
        if ctx.department:  
            span.set_attribute(ClaudeCodeAttributes.USER_DEPARTMENT, ctx.department)
        if ctx.role:
            span.set_attribute(ClaudeCodeAttributes.USER_ROLE, ctx.role)
        if ctx.organization:
            span.set_attribute(ClaudeCodeAttributes.ENTERPRISE_ORG, ctx.organization)
        if ctx.security_profile:
            span.set_attribute(ClaudeCodeAttributes.SECURITY_PROFILE, ctx.security_profile)

    def _set_model_attributes(self, span, model_ctx: ModelContext):
        """Set model and request attributes"""
        span.set_attribute(ClaudeCodeAttributes.MODEL_ID, model_ctx.model_id or "unknown")
        span.set_attribute(ClaudeCodeAttributes.MODEL_PROVIDER, model_ctx.provider)
        span.set_attribute(ClaudeCodeAttributes.REQUEST_TOKENS_INPUT, model_ctx.tokens_input)
        span.set_attribute(ClaudeCodeAttributes.REQUEST_TOKENS_OUTPUT, model_ctx.tokens_output)  
        span.set_attribute(ClaudeCodeAttributes.REQUEST_TOKENS_TOTAL, model_ctx.tokens_total)
        span.set_attribute(ClaudeCodeAttributes.CACHE_HIT, model_ctx.cache_hit)
        
        if model_ctx.cache_key:
            span.set_attribute(ClaudeCodeAttributes.CACHE_KEY, model_ctx.cache_key)

    def _set_cost_attributes(self, span, model_ctx: ModelContext):
        """Set cost tracking attributes"""
        cost_breakdown = self._cost_context.calculate_cost(model_ctx)
        
        span.set_attribute(ClaudeCodeAttributes.COST_INPUT_USD, cost_breakdown["input_usd"])
        span.set_attribute(ClaudeCodeAttributes.COST_OUTPUT_USD, cost_breakdown["output_usd"])
        span.set_attribute(ClaudeCodeAttributes.COST_ESTIMATE_USD, cost_breakdown["total_usd"])
        span.set_attribute(ClaudeCodeAttributes.COST_CACHE_SAVINGS_USD, cost_breakdown["cache_savings_usd"])

    def _set_project_attributes(self, span, project_ctx: Dict[str, str]):
        """Set project and repository context"""
        if "name" in project_ctx:
            span.set_attribute(ClaudeCodeAttributes.PROJECT_NAME, project_ctx["name"])
        if "path" in project_ctx:
            span.set_attribute(ClaudeCodeAttributes.PROJECT_PATH, project_ctx["path"])
        if "repository_url" in project_ctx:
            span.set_attribute(ClaudeCodeAttributes.REPOSITORY_URL, project_ctx["repository_url"])
        if "branch" in project_ctx:
            span.set_attribute(ClaudeCodeAttributes.BRANCH_NAME, project_ctx["branch"])

    def record_event(self, span, event_name: str, attributes: Optional[Dict[str, Any]] = None):
        """Record a span event with timestamps"""
        if not OTEL_AVAILABLE:
            return
            
        event_attributes = attributes or {}
        event_attributes["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        span.add_event(event_name, event_attributes)

    def record_cache_metrics(self, span, cache_operation: str, hit: bool, latency_ms: int):
        """Record cache-specific metrics"""
        span.set_attribute(f"claude.cache.operation", cache_operation)
        span.set_attribute(f"claude.cache.hit", hit)  
        span.set_attribute(f"claude.cache.latency_ms", latency_ms)
        
        self.record_event(span, "cache_lookup", {
            "operation": cache_operation,
            "hit": hit,
            "latency_ms": latency_ms
        })

    def record_security_event(self, span, event_type: str, details: Dict[str, Any]):
        """Record security-related events"""
        span.set_attribute("claude.security.event_type", event_type)
        
        # Add security event with sanitized details
        sanitized_details = {k: v for k, v in details.items() 
                           if k not in ["password", "token", "key", "secret"]}
        
        self.record_event(span, f"security_{event_type}", sanitized_details)


# Global tracer instance
_global_tracer: Optional[ClaudeCodeTracer] = None

def get_tracer() -> ClaudeCodeTracer:
    """Get or create global tracer instance"""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = ClaudeCodeTracer()
    return _global_tracer


def trace_claude_operation(operation_name: str, operation_type: str = "claude_request"):
    """Decorator for tracing Claude Code operations"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            
            with tracer.span(operation_name, operation_type) as span:
                try:
                    result = func(*args, **kwargs)
                    
                    # Record success metrics
                    if hasattr(result, 'tokens_used'):
                        model_ctx = ModelContext(
                            tokens_input=getattr(result, 'tokens_input', 0),
                            tokens_output=getattr(result, 'tokens_output', 0)
                        )
                        tracer._set_model_attributes(span, model_ctx)
                        tracer._set_cost_attributes(span, model_ctx)
                    
                    return result
                    
                except Exception as e:
                    # Error details already recorded by span context manager
                    raise
                    
        return wrapper
    return decorator


# Convenience functions for common operations
def trace_model_request(model_id: str, tokens_input: int, tokens_output: int, cache_hit: bool = False):
    """Create a span for model request with automatic cost calculation"""
    tracer = get_tracer()
    model_ctx = ModelContext(
        model_id=model_id,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        cache_hit=cache_hit
    )
    return tracer.span("model_request", "claude_inference", model_ctx=model_ctx)


def trace_file_operation(operation: str, file_path: str):
    """Create a span for file operations"""
    tracer = get_tracer()
    return tracer.span(f"file_{operation}", "file_operation", 
                      file_path=file_path,
                      operation_step=operation)


def trace_shell_command(command: str, working_dir: str = None):
    """Create a span for shell command execution"""
    tracer = get_tracer()
    attributes = {"shell_command": command[:100]}  # Truncate long commands
    if working_dir:
        attributes["working_directory"] = working_dir
    return tracer.span("shell_exec", "shell_operation", **attributes)