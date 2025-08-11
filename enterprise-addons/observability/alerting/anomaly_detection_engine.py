#!/usr/bin/env python3
"""
Real-time Anomaly Detection Engine for Claude Code Enterprise
Provides comprehensive anomaly detection for usage patterns, security events,
and performance metrics with automated incident response.
"""

import os
import sys
import json
import time
import boto3
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import statistics
import threading
from queue import Queue, Empty

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AnomalyThreshold:
    """Configuration for anomaly detection thresholds"""
    metric_name: str
    baseline_period_minutes: int = 60
    detection_period_minutes: int = 5
    sensitivity: float = 2.0  # Standard deviations
    min_data_points: int = 10
    alert_cooldown_minutes: int = 15


@dataclass
class SecurityAnomalyConfig:
    """Configuration for security-specific anomaly detection"""
    policy_violations_per_minute: int = 3
    failed_auth_attempts_per_minute: int = 5
    unusual_access_patterns_threshold: float = 3.0
    high_privilege_usage_threshold: float = 2.0


@dataclass
class AnomalyAlert:
    """Anomaly alert information"""
    anomaly_id: str
    metric_name: str
    anomaly_type: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    description: str
    current_value: float
    baseline_value: float
    deviation: float
    timestamp: datetime
    user_context: Optional[Dict[str, str]] = None
    additional_data: Optional[Dict[str, Any]] = None


class MetricBuffer:
    """Thread-safe circular buffer for metric data"""
    
    def __init__(self, max_size: int = 1000):
        self.buffer = deque(maxlen=max_size)
        self.lock = threading.Lock()
    
    def add(self, timestamp: datetime, value: float, metadata: Dict[str, Any] = None):
        """Add a metric data point"""
        with self.lock:
            self.buffer.append({
                'timestamp': timestamp,
                'value': value,
                'metadata': metadata or {}
            })
    
    def get_recent(self, minutes: int) -> List[Dict[str, Any]]:
        """Get data points from the last N minutes"""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        
        with self.lock:
            return [point for point in self.buffer if point['timestamp'] >= cutoff]
    
    def get_baseline(self, minutes: int, exclude_recent_minutes: int = 5) -> List[float]:
        """Get baseline values excluding recent data"""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=exclude_recent_minutes)
        baseline_start = cutoff - timedelta(minutes=minutes)
        
        with self.lock:
            return [
                point['value'] for point in self.buffer 
                if baseline_start <= point['timestamp'] <= cutoff
            ]


class AnomalyDetectionEngine:
    """Main anomaly detection engine"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.metric_buffers = defaultdict(lambda: MetricBuffer())
        self.alert_history = defaultdict(lambda: deque(maxlen=100))
        self.alert_queue = Queue()
        
        # AWS clients
        self.cloudwatch = boto3.client('cloudwatch')
        self.sns = boto3.client('sns')
        
        # Security anomaly detector
        self.security_config = SecurityAnomalyConfig()
        self.security_events_buffer = defaultdict(lambda: deque(maxlen=1000))
        
        # Alert cooldown tracking
        self.alert_cooldowns = {}
        
        # Start background processing
        self.running = True
        self.processor_thread = threading.Thread(target=self._process_alerts, daemon=True)
        self.processor_thread.start()
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, AnomalyThreshold]:
        """Load anomaly detection configuration"""
        default_thresholds = {
            'daily_active_users': AnomalyThreshold(
                metric_name='daily_active_users',
                baseline_period_minutes=1440,  # 24 hours
                detection_period_minutes=60,    # 1 hour
                sensitivity=2.5
            ),
            'total_tokens': AnomalyThreshold(
                metric_name='total_tokens',
                baseline_period_minutes=120,    # 2 hours
                detection_period_minutes=10,    # 10 minutes
                sensitivity=3.0
            ),
            'total_cost_usd': AnomalyThreshold(
                metric_name='total_cost_usd',
                baseline_period_minutes=120,
                detection_period_minutes=15,
                sensitivity=2.5
            ),
            'error_rate': AnomalyThreshold(
                metric_name='error_rate',
                baseline_period_minutes=60,
                detection_period_minutes=5,
                sensitivity=2.0,
                min_data_points=5
            ),
            'request_latency_p95': AnomalyThreshold(
                metric_name='request_latency_p95',
                baseline_period_minutes=60,
                detection_period_minutes=5,
                sensitivity=2.5
            ),
            'cache_hit_rate': AnomalyThreshold(
                metric_name='cache_hit_rate',
                baseline_period_minutes=120,
                detection_period_minutes=15,
                sensitivity=2.0
            )
        }
        
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    custom_config = json.load(f)
                    # Override defaults with custom config
                    for name, config in custom_config.items():
                        default_thresholds[name] = AnomalyThreshold(**config)
            except Exception as e:
                logger.error(f"Failed to load config from {config_path}: {e}")
        
        return default_thresholds
    
    def add_metric_data(self, metric_name: str, value: float, metadata: Dict[str, Any] = None):
        """Add metric data point for anomaly detection"""
        timestamp = datetime.now(timezone.utc)
        self.metric_buffers[metric_name].add(timestamp, value, metadata)
        
        # Check for anomalies if we have enough data
        if metric_name in self.config:
            self._check_metric_anomaly(metric_name)
    
    def add_security_event(self, event_type: str, user_id: str, details: Dict[str, Any]):
        """Add security event for anomaly detection"""
        timestamp = datetime.now(timezone.utc)
        event = {
            'timestamp': timestamp,
            'event_type': event_type,
            'user_id': user_id,
            'details': details
        }
        
        self.security_events_buffer[event_type].append(event)
        self._check_security_anomalies()
    
    def _check_metric_anomaly(self, metric_name: str):
        """Check if a metric shows anomalous behavior"""
        threshold = self.config[metric_name]
        
        # Get recent data and baseline
        recent_data = self.metric_buffers[metric_name].get_recent(threshold.detection_period_minutes)
        baseline_data = self.metric_buffers[metric_name].get_baseline(threshold.baseline_period_minutes)
        
        if len(recent_data) < 2 or len(baseline_data) < threshold.min_data_points:
            return  # Not enough data
        
        # Calculate baseline statistics
        baseline_values = [point['value'] for point in recent_data]
        recent_values = [point['value'] for point in recent_data]
        
        try:
            baseline_mean = statistics.mean(baseline_values)
            baseline_stdev = statistics.stdev(baseline_values) if len(baseline_values) > 1 else 0
            recent_mean = statistics.mean(recent_values)
            
            if baseline_stdev == 0:
                return  # No variation in baseline
            
            # Calculate deviation
            deviation = abs(recent_mean - baseline_mean) / baseline_stdev
            
            if deviation > threshold.sensitivity:
                # Check alert cooldown
                cooldown_key = f"{metric_name}_anomaly"
                if self._is_in_cooldown(cooldown_key, threshold.alert_cooldown_minutes):
                    return
                
                # Create anomaly alert
                alert = AnomalyAlert(
                    anomaly_id=f"{metric_name}_{int(time.time())}",
                    metric_name=metric_name,
                    anomaly_type='statistical_deviation',
                    severity=self._calculate_severity(deviation, threshold.sensitivity),
                    description=f"{metric_name} showing {deviation:.2f}σ deviation from baseline",
                    current_value=recent_mean,
                    baseline_value=baseline_mean,
                    deviation=deviation,
                    timestamp=datetime.now(timezone.utc)
                )
                
                self._queue_alert(alert)
                self._set_cooldown(cooldown_key)
                
        except Exception as e:
            logger.error(f"Error checking anomaly for {metric_name}: {e}")
    
    def _check_security_anomalies(self):
        """Check for security-related anomalies"""
        now = datetime.now(timezone.utc)
        
        # Check policy violations
        recent_violations = [
            event for event in self.security_events_buffer['policy_violation']
            if (now - event['timestamp']).total_seconds() < 60
        ]
        
        if len(recent_violations) > self.security_config.policy_violations_per_minute:
            if not self._is_in_cooldown('policy_violation_spike', 15):
                alert = AnomalyAlert(
                    anomaly_id=f"policy_violation_spike_{int(time.time())}",
                    metric_name='policy_violations',
                    anomaly_type='security_spike',
                    severity='HIGH',
                    description=f"High rate of policy violations: {len(recent_violations)} in last minute",
                    current_value=len(recent_violations),
                    baseline_value=self.security_config.policy_violations_per_minute,
                    deviation=len(recent_violations) - self.security_config.policy_violations_per_minute,
                    timestamp=now
                )
                self._queue_alert(alert)
                self._set_cooldown('policy_violation_spike')
        
        # Check failed authentication attempts
        recent_auth_failures = [
            event for event in self.security_events_buffer['authentication_failure']
            if (now - event['timestamp']).total_seconds() < 60
        ]
        
        if len(recent_auth_failures) > self.security_config.failed_auth_attempts_per_minute:
            if not self._is_in_cooldown('auth_failure_spike', 15):
                alert = AnomalyAlert(
                    anomaly_id=f"auth_failure_spike_{int(time.time())}",
                    metric_name='authentication_failures',
                    anomaly_type='security_spike',
                    severity='HIGH',
                    description=f"High rate of authentication failures: {len(recent_auth_failures)} in last minute",
                    current_value=len(recent_auth_failures),
                    baseline_value=self.security_config.failed_auth_attempts_per_minute,
                    deviation=len(recent_auth_failures) - self.security_config.failed_auth_attempts_per_minute,
                    timestamp=now
                )
                self._queue_alert(alert)
                self._set_cooldown('auth_failure_spike')
        
        # Check for unusual access patterns per user
        self._check_unusual_user_patterns()
    
    def _check_unusual_user_patterns(self):
        """Check for unusual access patterns per user"""
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        
        # Group recent events by user
        user_activities = defaultdict(list)
        
        for event_type, events in self.security_events_buffer.items():
            for event in events:
                if event['timestamp'] >= hour_ago:
                    user_activities[event['user_id']].append(event)
        
        # Analyze each user's pattern
        for user_id, activities in user_activities.items():
            if len(activities) < 5:  # Not enough activity to analyze
                continue
            
            # Check for unusual activity volume
            hourly_average = self._get_user_hourly_average(user_id)
            current_activity = len(activities)
            
            if hourly_average > 0 and current_activity > hourly_average * self.security_config.unusual_access_patterns_threshold:
                if not self._is_in_cooldown(f'unusual_activity_{user_id}', 30):
                    alert = AnomalyAlert(
                        anomaly_id=f"unusual_activity_{user_id}_{int(time.time())}",
                        metric_name='user_activity',
                        anomaly_type='unusual_pattern',
                        severity='MEDIUM',
                        description=f"Unusual activity volume for user {user_id[:8]}...: {current_activity} vs average {hourly_average}",
                        current_value=current_activity,
                        baseline_value=hourly_average,
                        deviation=current_activity / hourly_average,
                        timestamp=now,
                        user_context={'user_id': user_id}
                    )
                    self._queue_alert(alert)
                    self._set_cooldown(f'unusual_activity_{user_id}')
    
    def _get_user_hourly_average(self, user_id: str) -> float:
        """Get user's average hourly activity over the past week"""
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        
        hourly_counts = []
        
        # Group activities by hour over the past week
        for event_type, events in self.security_events_buffer.items():
            user_events = [
                event for event in events
                if event['user_id'] == user_id and event['timestamp'] >= week_ago
            ]
            
            # Group by hour
            hourly_activity = defaultdict(int)
            for event in user_events:
                hour_key = event['timestamp'].replace(minute=0, second=0, microsecond=0)
                hourly_activity[hour_key] += 1
            
            hourly_counts.extend(hourly_activity.values())
        
        return statistics.mean(hourly_counts) if hourly_counts else 0
    
    def _calculate_severity(self, deviation: float, threshold: float) -> str:
        """Calculate alert severity based on deviation"""
        if deviation > threshold * 3:
            return 'CRITICAL'
        elif deviation > threshold * 2:
            return 'HIGH'
        elif deviation > threshold * 1.5:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _is_in_cooldown(self, key: str, cooldown_minutes: int) -> bool:
        """Check if alert is in cooldown period"""
        if key not in self.alert_cooldowns:
            return False
        
        cooldown_expires = self.alert_cooldowns[key] + timedelta(minutes=cooldown_minutes)
        return datetime.now(timezone.utc) < cooldown_expires
    
    def _set_cooldown(self, key: str):
        """Set alert cooldown"""
        self.alert_cooldowns[key] = datetime.now(timezone.utc)
    
    def _queue_alert(self, alert: AnomalyAlert):
        """Queue alert for processing"""
        self.alert_queue.put(alert)
        logger.info(f"Queued anomaly alert: {alert.anomaly_id}")
    
    def _process_alerts(self):
        """Background thread to process alert queue"""
        while self.running:
            try:
                alert = self.alert_queue.get(timeout=5)
                self._handle_alert(alert)
                self.alert_queue.task_done()
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing alert: {e}")
    
    def _handle_alert(self, alert: AnomalyAlert):
        """Handle an anomaly alert"""
        try:
            # Log the alert
            logger.warning(f"Anomaly detected: {alert.description}")
            
            # Store in alert history
            self.alert_history[alert.metric_name].append(alert)
            
            # Send to CloudWatch as custom metric
            self._send_to_cloudwatch(alert)
            
            # Send SNS notification for high/critical alerts
            if alert.severity in ['HIGH', 'CRITICAL']:
                self._send_sns_notification(alert)
            
            # Trigger automated response if needed
            if alert.severity == 'CRITICAL':
                self._trigger_automated_response(alert)
                
        except Exception as e:
            logger.error(f"Error handling alert {alert.anomaly_id}: {e}")
    
    def _send_to_cloudwatch(self, alert: AnomalyAlert):
        """Send alert as CloudWatch metric"""
        try:
            self.cloudwatch.put_metric_data(
                Namespace='ClaudeCode/Enterprise/Anomalies',
                MetricData=[
                    {
                        'MetricName': 'anomaly_detected',
                        'Dimensions': [
                            {'Name': 'MetricName', 'Value': alert.metric_name},
                            {'Name': 'Severity', 'Value': alert.severity},
                            {'Name': 'AnomalyType', 'Value': alert.anomaly_type}
                        ],
                        'Value': 1,
                        'Unit': 'Count',
                        'Timestamp': alert.timestamp
                    },
                    {
                        'MetricName': 'anomaly_deviation',
                        'Dimensions': [
                            {'Name': 'MetricName', 'Value': alert.metric_name}
                        ],
                        'Value': alert.deviation,
                        'Unit': 'None',
                        'Timestamp': alert.timestamp
                    }
                ]
            )
        except Exception as e:
            logger.error(f"Failed to send alert to CloudWatch: {e}")
    
    def _send_sns_notification(self, alert: AnomalyAlert):
        """Send SNS notification for alert"""
        topic_arn = os.getenv('ANOMALY_ALERT_TOPIC_ARN')
        if not topic_arn:
            return
        
        try:
            message = {
                'alert_id': alert.anomaly_id,
                'metric_name': alert.metric_name,
                'severity': alert.severity,
                'description': alert.description,
                'current_value': alert.current_value,
                'baseline_value': alert.baseline_value,
                'deviation': alert.deviation,
                'timestamp': alert.timestamp.isoformat()
            }
            
            if alert.user_context:
                message['user_context'] = alert.user_context
            
            subject = f"[{alert.severity}] Claude Code Anomaly: {alert.metric_name}"
            
            self.sns.publish(
                TopicArn=topic_arn,
                Subject=subject,
                Message=json.dumps(message, indent=2)
            )
            
        except Exception as e:
            logger.error(f"Failed to send SNS notification: {e}")
    
    def _trigger_automated_response(self, alert: AnomalyAlert):
        """Trigger automated response for critical alerts"""
        try:
            # Example automated responses:
            
            if alert.metric_name == 'error_rate' and alert.severity == 'CRITICAL':
                # Could trigger circuit breaker or rate limiting
                logger.warning(f"Would trigger rate limiting due to high error rate")
            
            elif alert.anomaly_type == 'security_spike':
                # Could trigger temporary security lockdown
                logger.warning(f"Would trigger enhanced security monitoring")
            
            elif alert.metric_name == 'total_cost_usd' and alert.deviation > 5.0:
                # Could trigger cost controls
                logger.warning(f"Would trigger cost controls due to spending spike")
            
            # Add custom automated response logic here
            
        except Exception as e:
            logger.error(f"Error in automated response: {e}")
    
    def get_alert_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get summary of recent alerts"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        summary = {
            'total_alerts': 0,
            'by_severity': defaultdict(int),
            'by_metric': defaultdict(int),
            'by_type': defaultdict(int),
            'recent_alerts': []
        }
        
        for metric_name, alerts in self.alert_history.items():
            recent_alerts = [alert for alert in alerts if alert.timestamp >= cutoff]
            
            for alert in recent_alerts:
                summary['total_alerts'] += 1
                summary['by_severity'][alert.severity] += 1
                summary['by_metric'][alert.metric_name] += 1
                summary['by_type'][alert.anomaly_type] += 1
                
                summary['recent_alerts'].append({
                    'id': alert.anomaly_id,
                    'metric': alert.metric_name,
                    'severity': alert.severity,
                    'description': alert.description,
                    'timestamp': alert.timestamp.isoformat()
                })
        
        # Sort recent alerts by timestamp
        summary['recent_alerts'].sort(key=lambda x: x['timestamp'], reverse=True)
        
        return summary
    
    def shutdown(self):
        """Shutdown the anomaly detection engine"""
        self.running = False
        if self.processor_thread.is_alive():
            self.processor_thread.join(timeout=10)


# Global anomaly detection engine instance
_global_engine: Optional[AnomalyDetectionEngine] = None

def get_anomaly_engine() -> AnomalyDetectionEngine:
    """Get or create global anomaly detection engine"""
    global _global_engine
    if _global_engine is None:
        config_path = os.getenv('ANOMALY_DETECTION_CONFIG_PATH')
        _global_engine = AnomalyDetectionEngine(config_path)
    return _global_engine


def record_metric_anomaly(metric_name: str, value: float, metadata: Dict[str, Any] = None):
    """Convenience function to record metric for anomaly detection"""
    engine = get_anomaly_engine()
    engine.add_metric_data(metric_name, value, metadata)


def record_security_event_anomaly(event_type: str, user_id: str, details: Dict[str, Any]):
    """Convenience function to record security event for anomaly detection"""
    engine = get_anomaly_engine()
    engine.add_security_event(event_type, user_id, details)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude Code Anomaly Detection Engine")
    parser.add_argument("--test", action="store_true", help="Run test scenarios")
    parser.add_argument("--config", help="Path to configuration file")
    
    args = parser.parse_args()
    
    if args.test:
        # Run test scenarios
        engine = AnomalyDetectionEngine(args.config)
        
        print("Testing anomaly detection...")
        
        # Simulate normal activity
        for i in range(20):
            engine.add_metric_data('total_tokens', 1000 + (i * 50))
            time.sleep(0.1)
        
        # Simulate anomaly
        engine.add_metric_data('total_tokens', 5000)  # Spike
        
        time.sleep(2)  # Let alerts process
        
        summary = engine.get_alert_summary(1)
        print(f"Alert summary: {json.dumps(summary, indent=2)}")
        
        engine.shutdown()
    else:
        print("Anomaly detection engine - import as module for normal usage")