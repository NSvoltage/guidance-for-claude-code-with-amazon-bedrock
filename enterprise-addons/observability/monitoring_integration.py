#!/usr/bin/env python3
"""
Comprehensive Monitoring Integration for Claude Code Enterprise
Unifies telemetry collection, anomaly detection, productivity tracking,
and compliance monitoring into a single cohesive system.
"""

import os
import sys
import json
import time
import boto3
import logging
import threading
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
from pathlib import Path

# Import our custom modules
try:
    from spans.claude_code_tracer import (
        ClaudeCodeTracer, UserContext, ModelContext, CostContext,
        get_tracer, ClaudeCodeAttributes
    )
    from alerting.anomaly_detection_engine import (
        AnomalyDetectionEngine, get_anomaly_engine,
        record_metric_anomaly, record_security_event_anomaly
    )
    from metrics.productivity_metrics import (
        ProductivityTracker, ComplianceTracker, BusinessValueCalculator,
        MetricsReporter, get_productivity_tracker, get_compliance_tracker,
        get_business_calculator, get_metrics_reporter
    )
    MODULES_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Some monitoring modules not available: {e}")
    MODULES_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MonitoringConfig:
    """Configuration for monitoring integration"""
    enable_telemetry: bool = True
    enable_anomaly_detection: bool = True
    enable_productivity_tracking: bool = True
    enable_compliance_monitoring: bool = True
    enable_business_metrics: bool = True
    
    # Reporting configuration
    daily_report_enabled: bool = True
    weekly_report_enabled: bool = True
    monthly_report_enabled: bool = True
    
    # Alert configuration
    anomaly_alert_enabled: bool = True
    compliance_alert_enabled: bool = True
    cost_alert_enabled: bool = True
    
    # Data retention (days)
    telemetry_retention_days: int = 90
    metrics_retention_days: int = 365
    
    # Performance settings
    batch_size: int = 100
    flush_interval_seconds: int = 30


class ComprehensiveMonitor:
    """Main monitoring integration class that orchestrates all monitoring components"""
    
    def __init__(self, config: MonitoringConfig = None):
        self.config = config or MonitoringConfig()
        
        # Initialize components based on configuration
        self.tracer = None
        self.anomaly_engine = None
        self.productivity_tracker = None
        self.compliance_tracker = None
        self.business_calculator = None
        self.metrics_reporter = None
        
        # AWS clients
        self.cloudwatch = boto3.client('cloudwatch')
        self.sns = boto3.client('sns')
        
        # Internal state
        self.session_cache = {}
        self.metric_buffer = []
        self.running = True
        
        # Initialize components
        self._initialize_components()
        
        # Start background processing
        self._start_background_processing()
    
    def _initialize_components(self):
        """Initialize monitoring components based on configuration"""
        if not MODULES_AVAILABLE:
            logger.error("Monitoring modules not available")
            return
        
        try:
            if self.config.enable_telemetry:
                self.tracer = get_tracer()
                logger.info("Telemetry tracing initialized")
            
            if self.config.enable_anomaly_detection:
                self.anomaly_engine = get_anomaly_engine()
                logger.info("Anomaly detection engine initialized")
            
            if self.config.enable_productivity_tracking:
                self.productivity_tracker = get_productivity_tracker()
                logger.info("Productivity tracking initialized")
            
            if self.config.enable_compliance_monitoring:
                self.compliance_tracker = get_compliance_tracker()
                logger.info("Compliance monitoring initialized")
            
            if self.config.enable_business_metrics:
                self.business_calculator = get_business_calculator()
                logger.info("Business metrics calculator initialized")
            
            # Always initialize reporter if any tracking is enabled
            if any([
                self.config.enable_productivity_tracking,
                self.config.enable_compliance_monitoring, 
                self.config.enable_business_metrics
            ]):
                self.metrics_reporter = get_metrics_reporter()
                logger.info("Metrics reporter initialized")
                
        except Exception as e:
            logger.error(f"Error initializing monitoring components: {e}")
    
    def _start_background_processing(self):
        """Start background threads for data processing"""
        # Metrics flushing thread
        self.flush_thread = threading.Thread(target=self._metrics_flush_loop, daemon=True)
        self.flush_thread.start()
        
        # Periodic reporting thread
        self.report_thread = threading.Thread(target=self._periodic_report_loop, daemon=True)
        self.report_thread.start()
        
        logger.info("Background processing started")
    
    def track_claude_session(self, user_context: Dict[str, Any], session_metadata: Dict[str, Any]) -> str:
        """Start tracking a Claude Code session with comprehensive monitoring"""
        session_id = f"session_{int(time.time())}_{user_context.get('user_id', 'unknown')}"
        
        # Create user context object
        user_ctx = UserContext(
            user_id=user_context.get('user_id'),
            email=user_context.get('email'),
            name=user_context.get('name'),
            team=user_context.get('team', 'unknown'),
            department=user_context.get('department'),
            role=user_context.get('role'),
            organization=user_context.get('organization'),
            security_profile=user_context.get('security_profile', 'standard')
        )
        
        # Initialize session in cache
        self.session_cache[session_id] = {
            'user_context': user_ctx,
            'start_time': datetime.now(timezone.utc),
            'metadata': session_metadata,
            'interactions': [],
            'metrics': {},
            'total_cost': 0.0,
            'total_tokens': 0
        }
        
        # Update tracer user context
        if self.tracer and self.config.enable_telemetry:
            self.tracer.update_user_context(user_ctx)
        
        # Start productivity tracking
        if self.productivity_tracker and self.config.enable_productivity_tracking:
            self.productivity_tracker.track_session_start(
                user_id=user_ctx.user_id or 'unknown',
                team=user_ctx.team,
                session_id=session_id,
                project=session_metadata.get('project')
            )
        
        # Create session start span
        if self.tracer and self.config.enable_telemetry:
            with self.tracer.span("session_start", "session", 
                                 project_ctx=session_metadata) as span:
                span.set_attribute("claude.session.id", session_id)
                span.set_attribute("claude.user.team", user_ctx.team)
                span.set_attribute("claude.security.profile", user_ctx.security_profile or 'unknown')
        
        logger.info(f"Started tracking session {session_id} for user {user_ctx.user_id}")
        return session_id
    
    def track_model_interaction(self, session_id: str, interaction_data: Dict[str, Any]) -> str:
        """Track a model interaction with comprehensive metrics"""
        if session_id not in self.session_cache:
            logger.warning(f"Session {session_id} not found in cache")
            return None
        
        session = self.session_cache[session_id]
        interaction_id = f"interaction_{len(session['interactions'])}"
        
        # Extract interaction details
        model_ctx = ModelContext(
            model_id=interaction_data.get('model_id'),
            provider=interaction_data.get('provider', 'anthropic'),
            tokens_input=interaction_data.get('tokens_input', 0),
            tokens_output=interaction_data.get('tokens_output', 0),
            cache_hit=interaction_data.get('cache_hit', False),
            cache_key=interaction_data.get('cache_key')
        )
        
        # Update session totals
        session['total_tokens'] += model_ctx.tokens_total
        session['total_cost'] += self._estimate_cost(model_ctx)
        
        # Store interaction
        interaction_record = {
            'id': interaction_id,
            'timestamp': datetime.now(timezone.utc),
            'model_context': model_ctx,
            'success': interaction_data.get('success', True),
            'error_type': interaction_data.get('error_type'),
            'latency_ms': interaction_data.get('latency_ms', 0),
            'operation_type': interaction_data.get('operation_type', 'inference')
        }
        
        session['interactions'].append(interaction_record)
        
        # Create telemetry span
        if self.tracer and self.config.enable_telemetry:
            with self.tracer.span("model_interaction", "claude_inference", 
                                 model_ctx=model_ctx) as span:
                span.set_attribute("claude.interaction.id", interaction_id)
                span.set_attribute("claude.session.id", session_id)
                span.set_attribute("claude.operation.type", interaction_record['operation_type'])
                
                if not interaction_record['success']:
                    span.set_attribute("claude.error.type", interaction_record.get('error_type', 'unknown'))
        
        # Track productivity metrics
        if self.productivity_tracker and self.config.enable_productivity_tracking:
            self.productivity_tracker.track_interaction(
                session_id=session_id,
                interaction_type=interaction_record['operation_type'],
                success=interaction_record['success'],
                tokens_used=model_ctx.tokens_total,
                cache_hit=model_ctx.cache_hit
            )
        
        # Feed anomaly detection
        if self.anomaly_engine and self.config.enable_anomaly_detection:
            self.anomaly_engine.add_metric_data(
                'total_tokens', 
                model_ctx.tokens_total,
                metadata={
                    'user_id': session['user_context'].user_id,
                    'team': session['user_context'].team,
                    'session_id': session_id
                }
            )
            
            self.anomaly_engine.add_metric_data(
                'request_latency_p95',
                interaction_record['latency_ms'],
                metadata={'model_id': model_ctx.model_id}
            )
        
        # Add to metrics buffer
        self._buffer_metric({
            'metric_type': 'model_interaction',
            'session_id': session_id,
            'user_context': asdict(session['user_context']),
            'model_context': asdict(model_ctx),
            'interaction_data': interaction_record,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        return interaction_id
    
    def track_policy_check(self, session_id: str, policy_data: Dict[str, Any]):
        """Track policy compliance check"""
        if session_id not in self.session_cache:
            return
        
        session = self.session_cache[session_id]
        user_ctx = session['user_context']
        
        # Track compliance
        if self.compliance_tracker and self.config.enable_compliance_monitoring:
            self.compliance_tracker.track_policy_check(
                user_id=user_ctx.user_id or 'unknown',
                team=user_ctx.team,
                security_profile=user_ctx.security_profile or 'unknown',
                policy_type=policy_data.get('policy_type', 'general'),
                passed=policy_data.get('passed', True),
                details=policy_data.get('details', {})
            )
        
        # Create security event for anomaly detection
        if self.anomaly_engine and self.config.enable_anomaly_detection:
            if not policy_data.get('passed', True):
                self.anomaly_engine.add_security_event(
                    event_type='policy_violation',
                    user_id=user_ctx.user_id or 'unknown',
                    details=policy_data
                )
        
        # Create telemetry span for policy check
        if self.tracer and self.config.enable_telemetry:
            with self.tracer.span("policy_check", "governance") as span:
                span.set_attribute("claude.policy.type", policy_data.get('policy_type', 'general'))
                span.set_attribute("claude.policy.passed", policy_data.get('passed', True))
                span.set_attribute("claude.security.profile", user_ctx.security_profile or 'unknown')
                
                if not policy_data.get('passed', True):
                    self.tracer.record_security_event(span, "policy_violation", policy_data)
    
    def track_cost_event(self, cost_data: Dict[str, Any]):
        """Track cost-related events"""
        if self.business_calculator and self.config.enable_business_metrics:
            self.business_calculator.track_cost(
                cost_type=cost_data.get('cost_type', 'usage'),
                amount=cost_data.get('amount', 0.0),
                team=cost_data.get('team'),
                cost_center=cost_data.get('cost_center'),
                metadata=cost_data.get('metadata', {})
            )
        
        # Feed anomaly detection
        if self.anomaly_engine and self.config.enable_anomaly_detection:
            self.anomaly_engine.add_metric_data(
                'total_cost_usd',
                cost_data.get('amount', 0.0),
                metadata=cost_data
            )
    
    def end_session(self, session_id: str) -> Dict[str, Any]:
        """End session tracking and generate final metrics"""
        if session_id not in self.session_cache:
            logger.warning(f"Session {session_id} not found for ending")
            return {}
        
        session = self.session_cache[session_id]
        session['end_time'] = datetime.now(timezone.utc)
        session['duration_minutes'] = (session['end_time'] - session['start_time']).total_seconds() / 60
        
        # Generate productivity metrics
        productivity_metrics = []
        if self.productivity_tracker and self.config.enable_productivity_tracking:
            productivity_metrics = self.productivity_tracker.track_session_end(session_id)
        
        # Generate compliance score
        compliance_score = None
        if self.compliance_tracker and self.config.enable_compliance_monitoring:
            user_ctx = session['user_context']
            compliance_score = self.compliance_tracker.calculate_compliance_score(
                user_id=user_ctx.user_id or 'unknown',
                team=user_ctx.team,
                security_profile=user_ctx.security_profile or 'unknown'
            )
        
        # Create session end telemetry
        if self.tracer and self.config.enable_telemetry:
            with self.tracer.span("session_end", "session") as span:
                span.set_attribute("claude.session.id", session_id)
                span.set_attribute("claude.session.duration_minutes", session['duration_minutes'])
                span.set_attribute("claude.session.total_interactions", len(session['interactions']))
                span.set_attribute("claude.session.total_tokens", session['total_tokens'])
                span.set_attribute("claude.session.total_cost", session['total_cost'])
        
        # Prepare session summary
        summary = {
            'session_id': session_id,
            'user_context': asdict(session['user_context']),
            'duration_minutes': session['duration_minutes'],
            'total_interactions': len(session['interactions']),
            'total_tokens': session['total_tokens'],
            'total_cost': session['total_cost'],
            'productivity_metrics': [asdict(m) for m in productivity_metrics] if productivity_metrics else [],
            'compliance_score': asdict(compliance_score) if compliance_score else None,
            'success_rate': self._calculate_session_success_rate(session)
        }
        
        # Buffer final session metrics
        self._buffer_metric({
            'metric_type': 'session_summary',
            'session_summary': summary,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        # Clean up session cache
        del self.session_cache[session_id]
        
        logger.info(f"Session {session_id} ended - Duration: {session['duration_minutes']:.1f}min, "
                   f"Interactions: {len(session['interactions'])}, Cost: ${session['total_cost']:.4f}")
        
        return summary
    
    def _estimate_cost(self, model_ctx: ModelContext) -> float:
        """Estimate cost for model interaction"""
        # Default Claude 3 pricing
        input_cost = model_ctx.tokens_input * 0.000008  # $0.008 per 1K tokens
        output_cost = model_ctx.tokens_output * 0.000024  # $0.024 per 1K tokens
        total_cost = input_cost + output_cost
        
        # Apply cache savings
        if model_ctx.cache_hit:
            total_cost *= 0.1  # 90% savings on cache hits
        
        return total_cost
    
    def _calculate_session_success_rate(self, session: Dict[str, Any]) -> float:
        """Calculate success rate for a session"""
        if not session['interactions']:
            return 100.0
        
        successful_interactions = sum(
            1 for interaction in session['interactions'] 
            if interaction['success']
        )
        
        return (successful_interactions / len(session['interactions'])) * 100
    
    def _buffer_metric(self, metric_data: Dict[str, Any]):
        """Buffer metric data for batch processing"""
        self.metric_buffer.append(metric_data)
        
        # Flush if buffer is full
        if len(self.metric_buffer) >= self.config.batch_size:
            self._flush_metrics()
    
    def _flush_metrics(self):
        """Flush buffered metrics to CloudWatch"""
        if not self.metric_buffer:
            return
        
        try:
            # Prepare CloudWatch metrics
            metric_data = []
            
            for metric in self.metric_buffer:
                if metric['metric_type'] == 'model_interaction':
                    # Create metrics for model interactions
                    user_ctx = metric['user_context']
                    model_ctx = metric['model_context']
                    
                    metric_data.extend([
                        {
                            'MetricName': 'model_interactions',
                            'Dimensions': [
                                {'Name': 'Team', 'Value': user_ctx['team']},
                                {'Name': 'SecurityProfile', 'Value': user_ctx.get('security_profile', 'unknown')},
                                {'Name': 'ModelId', 'Value': model_ctx['model_id'] or 'unknown'}
                            ],
                            'Value': 1,
                            'Unit': 'Count',
                            'Timestamp': datetime.fromisoformat(metric['timestamp'].replace('Z', '+00:00'))
                        },
                        {
                            'MetricName': 'total_tokens',
                            'Dimensions': [
                                {'Name': 'Team', 'Value': user_ctx['team']},
                                {'Name': 'ModelId', 'Value': model_ctx['model_id'] or 'unknown'}
                            ],
                            'Value': model_ctx['tokens_input'] + model_ctx['tokens_output'],
                            'Unit': 'Count',
                            'Timestamp': datetime.fromisoformat(metric['timestamp'].replace('Z', '+00:00'))
                        },
                        {
                            'MetricName': 'cache_hit_rate',
                            'Dimensions': [
                                {'Name': 'Team', 'Value': user_ctx['team']}
                            ],
                            'Value': 100.0 if model_ctx['cache_hit'] else 0.0,
                            'Unit': 'Percent',
                            'Timestamp': datetime.fromisoformat(metric['timestamp'].replace('Z', '+00:00'))
                        }
                    ])
                
                elif metric['metric_type'] == 'session_summary':
                    # Create metrics for session summaries
                    summary = metric['session_summary']
                    user_ctx = summary['user_context']
                    
                    metric_data.extend([
                        {
                            'MetricName': 'session_duration',
                            'Dimensions': [
                                {'Name': 'Team', 'Value': user_ctx['team']}
                            ],
                            'Value': summary['duration_minutes'],
                            'Unit': 'None',
                            'Timestamp': datetime.fromisoformat(metric['timestamp'].replace('Z', '+00:00'))
                        },
                        {
                            'MetricName': 'session_success_rate',
                            'Dimensions': [
                                {'Name': 'Team', 'Value': user_ctx['team']},
                                {'Name': 'SecurityProfile', 'Value': user_ctx.get('security_profile', 'unknown')}
                            ],
                            'Value': summary['success_rate'],
                            'Unit': 'Percent',
                            'Timestamp': datetime.fromisoformat(metric['timestamp'].replace('Z', '+00:00'))
                        },
                        {
                            'MetricName': 'total_cost_usd',
                            'Dimensions': [
                                {'Name': 'Team', 'Value': user_ctx['team']}
                            ],
                            'Value': summary['total_cost'],
                            'Unit': 'None',
                            'Timestamp': datetime.fromisoformat(metric['timestamp'].replace('Z', '+00:00'))
                        }
                    ])
            
            # Send to CloudWatch in batches of 20
            for i in range(0, len(metric_data), 20):
                batch = metric_data[i:i+20]
                self.cloudwatch.put_metric_data(
                    Namespace='ClaudeCode/Enterprise',
                    MetricData=batch
                )
            
            logger.info(f"Flushed {len(self.metric_buffer)} metrics to CloudWatch")
            
        except Exception as e:
            logger.error(f"Error flushing metrics: {e}")
        finally:
            self.metric_buffer.clear()
    
    def _metrics_flush_loop(self):
        """Background loop for periodic metrics flushing"""
        while self.running:
            try:
                time.sleep(self.config.flush_interval_seconds)
                self._flush_metrics()
            except Exception as e:
                logger.error(f"Error in metrics flush loop: {e}")
    
    def _periodic_report_loop(self):
        """Background loop for periodic reporting"""
        last_daily_report = datetime.now(timezone.utc).date()
        last_weekly_report = datetime.now(timezone.utc).date()
        last_monthly_report = datetime.now(timezone.utc).date()
        
        while self.running:
            try:
                current_date = datetime.now(timezone.utc).date()
                
                # Daily reports
                if (self.config.daily_report_enabled and 
                    self.metrics_reporter and 
                    current_date > last_daily_report):
                    
                    self._generate_daily_report()
                    last_daily_report = current_date
                
                # Weekly reports (Sunday)
                if (self.config.weekly_report_enabled and 
                    self.metrics_reporter and
                    current_date.weekday() == 6 and  # Sunday
                    current_date > last_weekly_report):
                    
                    self._generate_weekly_report()
                    last_weekly_report = current_date
                
                # Monthly reports (1st of month)
                if (self.config.monthly_report_enabled and
                    self.metrics_reporter and
                    current_date.day == 1 and
                    current_date > last_monthly_report):
                    
                    self._generate_monthly_report()
                    last_monthly_report = current_date
                
                time.sleep(3600)  # Check hourly
                
            except Exception as e:
                logger.error(f"Error in periodic report loop: {e}")
    
    def _generate_daily_report(self):
        """Generate daily monitoring report"""
        try:
            report = self.metrics_reporter.generate_daily_report()
            logger.info(f"Generated daily report: {len(report.get('recommendations', []))} recommendations")
            
            # Could send via SNS or store in S3
            # For now, just log key metrics
            metrics = report.get('business_metrics', {})
            logger.info(f"Daily metrics - Cost: ${metrics.get('daily_cost', 0):.2f}, "
                       f"ROI: {metrics.get('roi_percentage', 0):.1f}%")
                       
        except Exception as e:
            logger.error(f"Error generating daily report: {e}")
    
    def _generate_weekly_report(self):
        """Generate weekly monitoring report"""
        logger.info("Weekly report generation would be implemented here")
    
    def _generate_monthly_report(self):
        """Generate monthly monitoring report"""
        logger.info("Monthly report generation would be implemented here")
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring system status"""
        return {
            'components': {
                'telemetry': self.tracer is not None,
                'anomaly_detection': self.anomaly_engine is not None,
                'productivity_tracking': self.productivity_tracker is not None,
                'compliance_monitoring': self.compliance_tracker is not None,
                'business_metrics': self.business_calculator is not None,
                'metrics_reporter': self.metrics_reporter is not None
            },
            'active_sessions': len(self.session_cache),
            'metric_buffer_size': len(self.metric_buffer),
            'configuration': asdict(self.config),
            'status': 'running' if self.running else 'stopped'
        }
    
    def shutdown(self):
        """Shutdown monitoring system"""
        self.running = False
        
        # Flush any remaining metrics
        self._flush_metrics()
        
        # Shutdown components
        if self.anomaly_engine:
            self.anomaly_engine.shutdown()
        
        logger.info("Comprehensive monitoring system shutdown complete")


# Global monitoring instance
_global_monitor: Optional[ComprehensiveMonitor] = None

def get_monitor(config: MonitoringConfig = None) -> ComprehensiveMonitor:
    """Get or create global monitoring instance"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = ComprehensiveMonitor(config)
    return _global_monitor


# Convenience functions for easy integration
def start_claude_session(user_context: Dict[str, Any], session_metadata: Dict[str, Any] = None) -> str:
    """Start tracking a Claude Code session"""
    monitor = get_monitor()
    return monitor.track_claude_session(user_context, session_metadata or {})


def track_model_call(session_id: str, model_id: str, tokens_input: int, tokens_output: int, 
                    success: bool = True, cache_hit: bool = False, latency_ms: int = 0) -> str:
    """Track a model interaction"""
    monitor = get_monitor()
    return monitor.track_model_interaction(session_id, {
        'model_id': model_id,
        'tokens_input': tokens_input,
        'tokens_output': tokens_output,
        'success': success,
        'cache_hit': cache_hit,
        'latency_ms': latency_ms,
        'operation_type': 'inference'
    })


def track_policy_violation(session_id: str, policy_type: str, details: Dict[str, Any] = None):
    """Track a policy compliance violation"""
    monitor = get_monitor()
    monitor.track_policy_check(session_id, {
        'policy_type': policy_type,
        'passed': False,
        'details': details or {}
    })


def end_claude_session(session_id: str) -> Dict[str, Any]:
    """End Claude Code session tracking"""
    monitor = get_monitor()
    return monitor.end_session(session_id)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude Code Comprehensive Monitoring")
    parser.add_argument("--test", action="store_true", help="Run test scenario")
    parser.add_argument("--status", action="store_true", help="Show monitoring status")
    
    args = parser.parse_args()
    
    if args.test:
        print("Testing comprehensive monitoring...")
        
        # Start a test session
        session_id = start_claude_session({
            'user_id': 'test_user_123',
            'email': 'test@company.com',
            'team': 'engineering',
            'security_profile': 'standard'
        }, {
            'project': 'test_project'
        })
        
        print(f"Started session: {session_id}")
        
        # Track some interactions
        for i in range(5):
            track_model_call(
                session_id=session_id,
                model_id='anthropic.claude-3-sonnet',
                tokens_input=500 + i * 100,
                tokens_output=200 + i * 50,
                success=i < 4,  # One failure
                cache_hit=i > 2,  # Some cache hits
                latency_ms=1000 + i * 200
            )
            time.sleep(0.1)
        
        # Track a policy violation
        track_policy_violation(session_id, 'file_access', {'attempted_path': '/etc/passwd'})
        
        # End session
        summary = end_claude_session(session_id)
        print(f"Session summary: {json.dumps(summary, indent=2, default=str)}")
        
        # Wait a bit for processing
        time.sleep(2)
        
    if args.status:
        monitor = get_monitor()
        status = monitor.get_monitoring_status()
        print(f"Monitoring status: {json.dumps(status, indent=2)}")