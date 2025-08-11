#!/usr/bin/env python3
"""
Workflow Observability Integration
Integrates workflow execution with Phase 1 observability system for comprehensive monitoring.
"""
import os
import sys
import json
import time
import uuid
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from contextlib import contextmanager

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../observability'))

# Import Phase 1 observability components
try:
    from spans.claude_code_tracer import ClaudeCodeTracer, get_tracer, ClaudeCodeAttributes
    from monitoring_integration import ComprehensiveMonitor
    from alerting.anomaly_detection_engine import get_anomaly_engine, record_metric_anomaly
    from metrics.productivity_metrics import ProductivityTracker
    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False
    # Mock classes for when observability is not available
    class MockTracer:
        def span(self, *args, **kwargs): return MockSpan()
    class MockSpan:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def set_attribute(self, *args): pass
    class MockMonitor:
        def track_completion(self, *args): pass


# Workflow-specific span attributes
class WorkflowAttributes:
    # Workflow identification
    WORKFLOW_NAME = "workflow.name"
    WORKFLOW_VERSION = "workflow.version"
    WORKFLOW_EXECUTION_ID = "workflow.execution.id"
    WORKFLOW_TYPE = "workflow.type"
    
    # Step identification
    STEP_ID = "workflow.step.id"
    STEP_TYPE = "workflow.step.type"
    STEP_INDEX = "workflow.step.index"
    STEP_TOTAL = "workflow.step.total"
    
    # Execution context
    EXECUTION_MODE = "workflow.execution.mode"  # normal, resume, dry_run
    RESUME_FROM_STEP = "workflow.resume.from_step"
    
    # Performance metrics
    STEP_DURATION_MS = "workflow.step.duration_ms"
    WORKFLOW_DURATION_MS = "workflow.duration_ms"
    STEP_CACHE_HIT = "workflow.step.cache_hit"
    STEP_RETRY_COUNT = "workflow.step.retry_count"
    
    # State and results
    STEP_STATUS = "workflow.step.status"
    WORKFLOW_STATUS = "workflow.status"
    STEP_OUTPUT_COUNT = "workflow.step.output_count"
    STEP_ERROR_TYPE = "workflow.step.error_type"
    
    # Business metrics
    FILES_PROCESSED = "workflow.files.processed"
    LINES_CHANGED = "workflow.lines.changed"
    TESTS_ADDED = "workflow.tests.added"
    ERRORS_FIXED = "workflow.errors.fixed"
    COVERAGE_IMPROVEMENT = "workflow.coverage.improvement"


@dataclass
class WorkflowMetrics:
    """Workflow execution metrics"""
    execution_id: str
    workflow_name: str
    workflow_version: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "running"
    
    # Step metrics
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    cached_steps: int = 0
    
    # Performance metrics
    total_duration_ms: float = 0.0
    step_durations: Dict[str, float] = None
    cache_hit_rate: float = 0.0
    
    # Business metrics
    files_processed: int = 0
    lines_changed: int = 0
    productivity_score: float = 0.0
    
    def __post_init__(self):
        if self.step_durations is None:
            self.step_durations = {}


class WorkflowTelemetryCollector:
    """Collects and manages workflow telemetry data"""
    
    def __init__(self, enable_tracing: bool = True, enable_metrics: bool = True):
        self.enable_tracing = enable_tracing and OBSERVABILITY_AVAILABLE
        self.enable_metrics = enable_metrics and OBSERVABILITY_AVAILABLE
        
        # Initialize observability components
        if OBSERVABILITY_AVAILABLE:
            self.tracer = get_tracer()
            self.monitor = ComprehensiveMonitor()
            self.productivity_tracker = ProductivityTracker()
            self.anomaly_engine = get_anomaly_engine()
        else:
            self.tracer = MockTracer()
            self.monitor = MockMonitor()
        
        # Metrics storage
        self.workflow_metrics: Dict[str, WorkflowMetrics] = {}
        self.active_spans: Dict[str, Any] = {}
    
    @contextmanager
    def workflow_execution_span(
        self,
        workflow_name: str,
        workflow_version: str,
        execution_id: str,
        inputs: Dict[str, Any],
        execution_mode: str = "normal",
        resume_from_step: Optional[str] = None
    ):
        """Create a span for entire workflow execution"""
        
        # Initialize workflow metrics
        metrics = WorkflowMetrics(
            execution_id=execution_id,
            workflow_name=workflow_name,
            workflow_version=workflow_version,
            started_at=datetime.now(timezone.utc)
        )
        self.workflow_metrics[execution_id] = metrics
        
        if not self.enable_tracing:
            yield None
            return
        
        span_name = f"workflow_execution:{workflow_name}"
        
        with self.tracer.span(span_name, "workflow_execution") as span:
            # Set workflow attributes
            span.set_attribute(WorkflowAttributes.WORKFLOW_NAME, workflow_name)
            span.set_attribute(WorkflowAttributes.WORKFLOW_VERSION, workflow_version)
            span.set_attribute(WorkflowAttributes.WORKFLOW_EXECUTION_ID, execution_id)
            span.set_attribute(WorkflowAttributes.EXECUTION_MODE, execution_mode)
            
            if resume_from_step:
                span.set_attribute(WorkflowAttributes.RESUME_FROM_STEP, resume_from_step)
            
            # Add input parameters as attributes (sanitized)
            for key, value in inputs.items():
                if not self._is_sensitive_key(key):
                    span.set_attribute(f"workflow.input.{key}", str(value)[:100])
            
            # Store span for access by step spans
            self.active_spans[execution_id] = span
            
            try:
                yield span
                
                # Set final workflow attributes
                final_metrics = self.workflow_metrics[execution_id]
                final_metrics.completed_at = datetime.now(timezone.utc)
                final_metrics.total_duration_ms = (
                    final_metrics.completed_at - final_metrics.started_at
                ).total_seconds() * 1000
                
                span.set_attribute(WorkflowAttributes.WORKFLOW_STATUS, final_metrics.status)
                span.set_attribute(WorkflowAttributes.WORKFLOW_DURATION_MS, final_metrics.total_duration_ms)
                span.set_attribute("workflow.steps.total", final_metrics.total_steps)
                span.set_attribute("workflow.steps.completed", final_metrics.completed_steps)
                span.set_attribute("workflow.steps.failed", final_metrics.failed_steps)
                span.set_attribute("workflow.steps.cached", final_metrics.cached_steps)
                span.set_attribute("workflow.cache.hit_rate", final_metrics.cache_hit_rate)
                
                # Record workflow completion metrics
                if self.enable_metrics:
                    self._record_workflow_completion(final_metrics)
                
            except Exception as e:
                final_metrics = self.workflow_metrics[execution_id]
                final_metrics.status = "failed"
                final_metrics.completed_at = datetime.now(timezone.utc)
                
                span.set_attribute(WorkflowAttributes.WORKFLOW_STATUS, "failed")
                span.set_attribute("workflow.error.type", type(e).__name__)
                span.set_attribute("workflow.error.message", str(e)[:200])
                
                # Record failure metrics
                if self.enable_metrics:
                    self._record_workflow_failure(final_metrics, str(e))
                
                raise
            
            finally:
                if execution_id in self.active_spans:
                    del self.active_spans[execution_id]
    
    @contextmanager
    def step_execution_span(
        self,
        execution_id: str,
        step_id: str,
        step_type: str,
        step_index: int,
        total_steps: int,
        step_inputs: Dict[str, Any] = None
    ):
        """Create a span for individual step execution"""
        
        if execution_id not in self.workflow_metrics:
            # If workflow span wasn't created, create minimal metrics
            self.workflow_metrics[execution_id] = WorkflowMetrics(
                execution_id=execution_id,
                workflow_name="unknown",
                workflow_version="unknown",
                started_at=datetime.now(timezone.utc)
            )
        
        metrics = self.workflow_metrics[execution_id]
        step_start_time = datetime.now(timezone.utc)
        
        if not self.enable_tracing:
            yield None
            return
        
        span_name = f"workflow_step:{step_id}"
        
        with self.tracer.span(span_name, "workflow_step") as span:
            # Set step attributes
            span.set_attribute(WorkflowAttributes.WORKFLOW_EXECUTION_ID, execution_id)
            span.set_attribute(WorkflowAttributes.STEP_ID, step_id)
            span.set_attribute(WorkflowAttributes.STEP_TYPE, step_type)
            span.set_attribute(WorkflowAttributes.STEP_INDEX, step_index)
            span.set_attribute(WorkflowAttributes.STEP_TOTAL, total_steps)
            
            # Add step inputs (sanitized)
            if step_inputs:
                for key, value in step_inputs.items():
                    if not self._is_sensitive_key(key):
                        span.set_attribute(f"workflow.step.input.{key}", str(value)[:100])
            
            try:
                yield span
                
                # Calculate step duration
                step_end_time = datetime.now(timezone.utc)
                duration_ms = (step_end_time - step_start_time).total_seconds() * 1000
                
                # Update metrics
                metrics.completed_steps += 1
                metrics.step_durations[step_id] = duration_ms
                
                # Set final step attributes
                span.set_attribute(WorkflowAttributes.STEP_DURATION_MS, duration_ms)
                span.set_attribute(WorkflowAttributes.STEP_STATUS, "completed")
                
                # Record step completion
                if self.enable_metrics:
                    self._record_step_completion(execution_id, step_id, step_type, duration_ms)
                
            except Exception as e:
                # Calculate step duration for failed step
                step_end_time = datetime.now(timezone.utc)
                duration_ms = (step_end_time - step_start_time).total_seconds() * 1000
                
                # Update metrics
                metrics.failed_steps += 1
                metrics.step_durations[step_id] = duration_ms
                
                # Set error attributes
                span.set_attribute(WorkflowAttributes.STEP_STATUS, "failed")
                span.set_attribute(WorkflowAttributes.STEP_DURATION_MS, duration_ms)
                span.set_attribute(WorkflowAttributes.STEP_ERROR_TYPE, type(e).__name__)
                span.set_attribute("workflow.step.error.message", str(e)[:200])
                
                # Record step failure
                if self.enable_metrics:
                    self._record_step_failure(execution_id, step_id, step_type, str(e))
                
                raise
    
    def record_step_cache_hit(self, execution_id: str, step_id: str, cache_key: str):
        """Record that a step used cached results"""
        if execution_id in self.workflow_metrics:
            self.workflow_metrics[execution_id].cached_steps += 1
        
        if self.enable_tracing and execution_id in self.active_spans:
            # Add cache event to workflow span
            span = self.active_spans[execution_id]
            span.add_event("step_cache_hit", {
                "step_id": step_id,
                "cache_key": cache_key[:16] + "...",  # Truncate for privacy
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        # Record cache metrics
        if self.enable_metrics:
            record_metric_anomaly("workflow.cache.hit", 1.0, {
                "execution_id": execution_id,
                "step_id": step_id,
                "workflow_name": self.workflow_metrics.get(execution_id, {}).workflow_name
            })
    
    def record_business_metrics(
        self,
        execution_id: str,
        metrics: Dict[str, Union[int, float]]
    ):
        """Record business-specific metrics for the workflow"""
        if execution_id not in self.workflow_metrics:
            return
        
        workflow_metrics = self.workflow_metrics[execution_id]
        
        # Update workflow metrics with business data
        if "files_processed" in metrics:
            workflow_metrics.files_processed = metrics["files_processed"]
        if "lines_changed" in metrics:
            workflow_metrics.lines_changed = metrics["lines_changed"]
        if "productivity_score" in metrics:
            workflow_metrics.productivity_score = metrics["productivity_score"]
        
        # Add to active span if available
        if self.enable_tracing and execution_id in self.active_spans:
            span = self.active_spans[execution_id]
            for key, value in metrics.items():
                span.set_attribute(f"workflow.business.{key}", value)
        
        # Record individual metrics for anomaly detection
        if self.enable_metrics:
            for metric_name, value in metrics.items():
                record_metric_anomaly(f"workflow.{metric_name}", float(value), {
                    "execution_id": execution_id,
                    "workflow_name": workflow_metrics.workflow_name
                })
    
    def record_step_outputs(self, execution_id: str, step_id: str, outputs: Dict[str, Any]):
        """Record step execution outputs"""
        if not self.enable_tracing or execution_id not in self.active_spans:
            return
        
        span = self.active_spans[execution_id]
        
        # Record output count and types
        span.add_event("step_outputs", {
            "step_id": step_id,
            "output_count": len(outputs),
            "output_types": [type(v).__name__ for v in outputs.values()],
            "output_keys": list(outputs.keys())
        })
    
    def get_workflow_metrics(self, execution_id: str) -> Optional[WorkflowMetrics]:
        """Get workflow metrics by execution ID"""
        return self.workflow_metrics.get(execution_id)
    
    def get_all_workflow_metrics(self) -> List[WorkflowMetrics]:
        """Get all workflow metrics"""
        return list(self.workflow_metrics.values())
    
    def _record_workflow_completion(self, metrics: WorkflowMetrics):
        """Record workflow completion for productivity tracking"""
        try:
            task_data = {
                'user_id': os.environ.get('USER', 'unknown'),
                'task_type': f'workflow_{metrics.workflow_name}',
                'complexity': self._assess_complexity(metrics),
                'success': metrics.status == 'completed',
                'duration_seconds': metrics.total_duration_ms / 1000,
                'files_processed': metrics.files_processed,
                'lines_changed': metrics.lines_changed,
                'steps_executed': metrics.completed_steps,
                'cache_efficiency': metrics.cache_hit_rate
            }
            
            self.productivity_tracker.track_task_completion(task_data)
            
            # Record comprehensive metrics
            self.monitor.track_completion({
                'task_type': 'workflow_execution',
                'workflow_name': metrics.workflow_name,
                'success': metrics.status == 'completed',
                'duration': metrics.total_duration_ms / 1000,
                'productivity_score': metrics.productivity_score
            })
            
        except Exception as e:
            # Don't fail workflow execution due to metrics recording errors
            print(f"Warning: Failed to record workflow completion metrics: {e}")
    
    def _record_workflow_failure(self, metrics: WorkflowMetrics, error: str):
        """Record workflow failure for monitoring"""
        try:
            # Record failure metrics
            record_metric_anomaly("workflow.failures", 1.0, {
                "workflow_name": metrics.workflow_name,
                "error_type": error.split(':')[0] if ':' in error else 'unknown',
                "execution_id": metrics.execution_id
            })
            
        except Exception as e:
            print(f"Warning: Failed to record workflow failure metrics: {e}")
    
    def _record_step_completion(self, execution_id: str, step_id: str, step_type: str, duration_ms: float):
        """Record step completion metrics"""
        try:
            # Record step performance metrics
            record_metric_anomaly(f"workflow.step.duration.{step_type}", duration_ms, {
                "execution_id": execution_id,
                "step_id": step_id
            })
            
        except Exception as e:
            print(f"Warning: Failed to record step completion metrics: {e}")
    
    def _record_step_failure(self, execution_id: str, step_id: str, step_type: str, error: str):
        """Record step failure metrics"""
        try:
            record_metric_anomaly("workflow.step.failures", 1.0, {
                "step_type": step_type,
                "step_id": step_id,
                "error_type": error.split(':')[0] if ':' in error else 'unknown'
            })
            
        except Exception as e:
            print(f"Warning: Failed to record step failure metrics: {e}")
    
    def _assess_complexity(self, metrics: WorkflowMetrics) -> str:
        """Assess workflow complexity based on metrics"""
        if metrics.total_steps > 10 or metrics.total_duration_ms > 600000:  # 10 minutes
            return "high"
        elif metrics.total_steps > 5 or metrics.total_duration_ms > 180000:  # 3 minutes
            return "medium"
        else:
            return "low"
    
    def _is_sensitive_key(self, key: str) -> bool:
        """Check if a key contains sensitive information"""
        sensitive_patterns = [
            'password', 'token', 'key', 'secret', 'api_key',
            'auth', 'credential', 'private', 'secure'
        ]
        key_lower = key.lower()
        return any(pattern in key_lower for pattern in sensitive_patterns)
    
    def generate_workflow_dashboard_data(self, execution_id: str) -> Dict[str, Any]:
        """Generate data for workflow execution dashboard"""
        if execution_id not in self.workflow_metrics:
            return {}
        
        metrics = self.workflow_metrics[execution_id]
        
        return {
            "workflow_info": {
                "name": metrics.workflow_name,
                "version": metrics.workflow_version,
                "execution_id": execution_id,
                "status": metrics.status
            },
            "timing": {
                "started_at": metrics.started_at.isoformat(),
                "completed_at": metrics.completed_at.isoformat() if metrics.completed_at else None,
                "total_duration_ms": metrics.total_duration_ms,
                "step_durations": metrics.step_durations
            },
            "execution": {
                "total_steps": metrics.total_steps,
                "completed_steps": metrics.completed_steps,
                "failed_steps": metrics.failed_steps,
                "cached_steps": metrics.cached_steps,
                "cache_hit_rate": metrics.cache_hit_rate
            },
            "business_metrics": {
                "files_processed": metrics.files_processed,
                "lines_changed": metrics.lines_changed,
                "productivity_score": metrics.productivity_score
            }
        }


# Global telemetry collector instance
_global_telemetry_collector: Optional[WorkflowTelemetryCollector] = None

def get_workflow_telemetry() -> WorkflowTelemetryCollector:
    """Get or create global workflow telemetry collector"""
    global _global_telemetry_collector
    if _global_telemetry_collector is None:
        _global_telemetry_collector = WorkflowTelemetryCollector()
    return _global_telemetry_collector

def initialize_workflow_telemetry(enable_tracing: bool = True, enable_metrics: bool = True):
    """Initialize workflow telemetry with specific configuration"""
    global _global_telemetry_collector
    _global_telemetry_collector = WorkflowTelemetryCollector(enable_tracing, enable_metrics)

# Convenience functions for common operations
def start_workflow_telemetry(
    workflow_name: str,
    workflow_version: str,
    execution_id: str,
    inputs: Dict[str, Any],
    **kwargs
):
    """Start workflow telemetry tracking"""
    collector = get_workflow_telemetry()
    return collector.workflow_execution_span(
        workflow_name, workflow_version, execution_id, inputs, **kwargs
    )

def start_step_telemetry(
    execution_id: str,
    step_id: str,
    step_type: str,
    step_index: int,
    total_steps: int,
    **kwargs
):
    """Start step telemetry tracking"""
    collector = get_workflow_telemetry()
    return collector.step_execution_span(
        execution_id, step_id, step_type, step_index, total_steps, **kwargs
    )

def record_workflow_cache_hit(execution_id: str, step_id: str, cache_key: str):
    """Record workflow step cache hit"""
    collector = get_workflow_telemetry()
    collector.record_step_cache_hit(execution_id, step_id, cache_key)

def record_workflow_business_metrics(execution_id: str, metrics: Dict[str, Union[int, float]]):
    """Record business metrics for workflow"""
    collector = get_workflow_telemetry()
    collector.record_business_metrics(execution_id, metrics)