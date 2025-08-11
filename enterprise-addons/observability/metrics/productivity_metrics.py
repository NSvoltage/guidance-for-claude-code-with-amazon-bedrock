#!/usr/bin/env python3
"""
Productivity and Compliance Metrics Engine for Claude Code Enterprise
Tracks developer productivity, compliance adherence, and business value metrics
with comprehensive analytics and reporting capabilities.
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
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ProductivityMetric:
    """Individual productivity metric"""
    user_id: str
    team: str
    metric_type: str
    value: float
    timestamp: datetime
    session_id: Optional[str] = None
    project: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ComplianceMetric:
    """Compliance adherence metric"""
    user_id: str
    team: str
    security_profile: str
    compliance_type: str
    score: float  # 0-100
    timestamp: datetime
    violations: int = 0
    total_checks: int = 1
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class BusinessValueMetric:
    """Business value and ROI metric"""
    metric_type: str
    value: float
    timestamp: datetime
    team: Optional[str] = None
    cost_center: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ProductivityTracker:
    """Tracks developer productivity metrics"""
    
    def __init__(self):
        self.session_metrics = defaultdict(dict)
        self.user_activity_history = defaultdict(list)
        
    def track_session_start(self, user_id: str, team: str, session_id: str, project: str = None):
        """Track start of a Claude Code session"""
        self.session_metrics[session_id] = {
            'user_id': user_id,
            'team': team,
            'project': project,
            'start_time': datetime.now(timezone.utc),
            'interactions': 0,
            'tokens_used': 0,
            'files_modified': 0,
            'commands_executed': 0,
            'errors_encountered': 0,
            'success_actions': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    def track_interaction(self, session_id: str, interaction_type: str, success: bool = True, 
                         tokens_used: int = 0, cache_hit: bool = False):
        """Track individual interaction within a session"""
        if session_id not in self.session_metrics:
            return
        
        session = self.session_metrics[session_id]
        session['interactions'] += 1
        session['tokens_used'] += tokens_used
        
        if success:
            session['success_actions'] += 1
        else:
            session['errors_encountered'] += 1
        
        if cache_hit:
            session['cache_hits'] += 1
        else:
            session['cache_misses'] += 1
        
        # Track specific interaction types
        if interaction_type == 'file_operation':
            session['files_modified'] += 1
        elif interaction_type == 'command_execution':
            session['commands_executed'] += 1
    
    def track_session_end(self, session_id: str) -> List[ProductivityMetric]:
        """End session tracking and calculate productivity metrics"""
        if session_id not in self.session_metrics:
            return []
        
        session = self.session_metrics[session_id]
        session['end_time'] = datetime.now(timezone.utc)
        session['duration_minutes'] = (session['end_time'] - session['start_time']).total_seconds() / 60
        
        metrics = self._calculate_session_productivity(session)
        
        # Store in user history
        self.user_activity_history[session['user_id']].append(session)
        
        # Clean up session
        del self.session_metrics[session_id]
        
        return metrics
    
    def _calculate_session_productivity(self, session: Dict[str, Any]) -> List[ProductivityMetric]:
        """Calculate productivity metrics for a session"""
        metrics = []
        timestamp = session['end_time']
        user_id = session['user_id']
        team = session['team']
        session_id = session.get('session_id')
        project = session.get('project')
        
        # Task completion rate
        if session['interactions'] > 0:
            completion_rate = session['success_actions'] / session['interactions'] * 100
            metrics.append(ProductivityMetric(
                user_id=user_id,
                team=team,
                metric_type='task_completion_rate',
                value=completion_rate,
                timestamp=timestamp,
                session_id=session_id,
                project=project,
                metadata={'total_interactions': session['interactions']}
            ))
        
        # Efficiency score (actions per minute)
        if session['duration_minutes'] > 0:
            efficiency = session['success_actions'] / session['duration_minutes']
            metrics.append(ProductivityMetric(
                user_id=user_id,
                team=team,
                metric_type='actions_per_minute',
                value=efficiency,
                timestamp=timestamp,
                session_id=session_id,
                project=project,
                metadata={'duration_minutes': session['duration_minutes']}
            ))
        
        # Error rate
        if session['interactions'] > 0:
            error_rate = session['errors_encountered'] / session['interactions'] * 100
            metrics.append(ProductivityMetric(
                user_id=user_id,
                team=team,
                metric_type='error_rate',
                value=error_rate,
                timestamp=timestamp,
                session_id=session_id,
                project=project,
                metadata={'total_errors': session['errors_encountered']}
            ))
        
        # Cache efficiency
        total_cache_requests = session['cache_hits'] + session['cache_misses']
        if total_cache_requests > 0:
            cache_efficiency = session['cache_hits'] / total_cache_requests * 100
            metrics.append(ProductivityMetric(
                user_id=user_id,
                team=team,
                metric_type='cache_efficiency',
                value=cache_efficiency,
                timestamp=timestamp,
                session_id=session_id,
                project=project,
                metadata={'cache_hits': session['cache_hits'], 'cache_misses': session['cache_misses']}
            ))
        
        # Token efficiency (success actions per token)
        if session['tokens_used'] > 0:
            token_efficiency = session['success_actions'] / session['tokens_used'] * 1000  # per 1k tokens
            metrics.append(ProductivityMetric(
                user_id=user_id,
                team=team,
                metric_type='token_efficiency',
                value=token_efficiency,
                timestamp=timestamp,
                session_id=session_id,
                project=project,
                metadata={'tokens_used': session['tokens_used']}
            ))
        
        return metrics
    
    def get_user_productivity_trends(self, user_id: str, days: int = 7) -> Dict[str, Any]:
        """Get productivity trends for a user"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        user_sessions = [
            session for session in self.user_activity_history[user_id]
            if session.get('end_time', datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
        ]
        
        if not user_sessions:
            return {}
        
        # Calculate trends
        trends = {
            'total_sessions': len(user_sessions),
            'total_duration_hours': sum(s.get('duration_minutes', 0) for s in user_sessions) / 60,
            'average_session_duration': statistics.mean([s.get('duration_minutes', 0) for s in user_sessions]),
            'total_interactions': sum(s.get('interactions', 0) for s in user_sessions),
            'average_completion_rate': 0,
            'average_efficiency': 0,
            'improvement_trend': 'stable'
        }
        
        # Calculate averages
        if user_sessions:
            completion_rates = [
                s.get('success_actions', 0) / s.get('interactions', 1) * 100 
                for s in user_sessions if s.get('interactions', 0) > 0
            ]
            if completion_rates:
                trends['average_completion_rate'] = statistics.mean(completion_rates)
            
            efficiencies = [
                s.get('success_actions', 0) / s.get('duration_minutes', 1)
                for s in user_sessions if s.get('duration_minutes', 0) > 0
            ]
            if efficiencies:
                trends['average_efficiency'] = statistics.mean(efficiencies)
        
        return trends


class ComplianceTracker:
    """Tracks compliance adherence metrics"""
    
    def __init__(self):
        self.compliance_events = defaultdict(list)
        self.policy_violations = defaultdict(list)
        
    def track_policy_check(self, user_id: str, team: str, security_profile: str,
                          policy_type: str, passed: bool, details: Dict[str, Any] = None):
        """Track a policy compliance check"""
        timestamp = datetime.now(timezone.utc)
        
        event = {
            'user_id': user_id,
            'team': team,
            'security_profile': security_profile,
            'policy_type': policy_type,
            'passed': passed,
            'timestamp': timestamp,
            'details': details or {}
        }
        
        self.compliance_events[user_id].append(event)
        
        if not passed:
            self.policy_violations[user_id].append(event)
    
    def calculate_compliance_score(self, user_id: str, team: str, security_profile: str,
                                 hours: int = 24) -> ComplianceMetric:
        """Calculate compliance score for a user"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        recent_events = [
            event for event in self.compliance_events[user_id]
            if event['timestamp'] >= cutoff
        ]
        
        if not recent_events:
            # No recent activity - assume compliant
            return ComplianceMetric(
                user_id=user_id,
                team=team,
                security_profile=security_profile,
                compliance_type='overall',
                score=100.0,
                timestamp=datetime.now(timezone.utc),
                total_checks=0
            )
        
        total_checks = len(recent_events)
        violations = len([e for e in recent_events if not e['passed']])
        passed_checks = total_checks - violations
        
        score = (passed_checks / total_checks) * 100 if total_checks > 0 else 100.0
        
        return ComplianceMetric(
            user_id=user_id,
            team=team,
            security_profile=security_profile,
            compliance_type='overall',
            score=score,
            timestamp=datetime.now(timezone.utc),
            violations=violations,
            total_checks=total_checks,
            metadata={
                'recent_violations': [
                    {
                        'policy_type': e['policy_type'],
                        'timestamp': e['timestamp'].isoformat(),
                        'details': e['details']
                    }
                    for e in recent_events if not e['passed']
                ][-5:]  # Last 5 violations
            }
        )
    
    def get_team_compliance_summary(self, team: str, hours: int = 24) -> Dict[str, Any]:
        """Get compliance summary for a team"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        team_events = []
        for user_id, events in self.compliance_events.items():
            team_events.extend([
                e for e in events 
                if e['team'] == team and e['timestamp'] >= cutoff
            ])
        
        if not team_events:
            return {'team': team, 'compliance_score': 100.0, 'total_checks': 0, 'violations': 0}
        
        total_checks = len(team_events)
        violations = len([e for e in team_events if not e['passed']])
        
        return {
            'team': team,
            'compliance_score': ((total_checks - violations) / total_checks) * 100,
            'total_checks': total_checks,
            'violations': violations,
            'violation_types': defaultdict(int, {
                e['policy_type']: sum(1 for event in team_events 
                                    if event['policy_type'] == e['policy_type'] and not event['passed'])
                for e in team_events if not e['passed']
            })
        }


class BusinessValueCalculator:
    """Calculates business value and ROI metrics"""
    
    def __init__(self):
        self.cost_data = defaultdict(list)
        self.value_metrics = defaultdict(list)
        
    def track_cost(self, cost_type: str, amount: float, team: str = None, 
                  cost_center: str = None, metadata: Dict[str, Any] = None):
        """Track cost data"""
        self.cost_data[cost_type].append({
            'amount': amount,
            'team': team,
            'cost_center': cost_center,
            'timestamp': datetime.now(timezone.utc),
            'metadata': metadata or {}
        })
    
    def track_value_metric(self, metric_type: str, value: float, team: str = None,
                          cost_center: str = None, metadata: Dict[str, Any] = None):
        """Track value generation metrics"""
        self.value_metrics[metric_type].append({
            'value': value,
            'team': team,
            'cost_center': cost_center,
            'timestamp': datetime.now(timezone.utc),
            'metadata': metadata or {}
        })
    
    def calculate_roi_metrics(self, period_days: int = 30) -> List[BusinessValueMetric]:
        """Calculate ROI and business value metrics"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)
        metrics = []
        
        # Calculate total costs
        total_cost = 0
        for cost_type, costs in self.cost_data.items():
            period_costs = [c for c in costs if c['timestamp'] >= cutoff]
            period_total = sum(c['amount'] for c in period_costs)
            total_cost += period_total
            
            if period_total > 0:
                metrics.append(BusinessValueMetric(
                    metric_type=f'cost_{cost_type}',
                    value=period_total,
                    timestamp=datetime.now(timezone.utc),
                    metadata={'period_days': period_days}
                ))
        
        # Calculate cost per user
        if total_cost > 0:
            # Estimate active users from productivity tracker
            estimated_users = max(10, total_cost / 50)  # Rough estimate
            cost_per_user = total_cost / estimated_users
            
            metrics.append(BusinessValueMetric(
                metric_type='cost_per_user',
                value=cost_per_user,
                timestamp=datetime.now(timezone.utc),
                metadata={'period_days': period_days, 'estimated_users': estimated_users}
            ))
        
        # Calculate productivity ROI
        # This would integrate with actual business metrics
        # For now, use estimated values based on usage patterns
        productivity_multiplier = 1.5  # Assume 50% productivity increase
        estimated_value = total_cost * productivity_multiplier
        
        if total_cost > 0:
            roi_percentage = ((estimated_value - total_cost) / total_cost) * 100
            metrics.append(BusinessValueMetric(
                metric_type='roi_percentage',
                value=roi_percentage,
                timestamp=datetime.now(timezone.utc),
                metadata={
                    'period_days': period_days,
                    'total_cost': total_cost,
                    'estimated_value': estimated_value
                }
            ))
        
        return metrics


class MetricsReporter:
    """Generates comprehensive metrics reports"""
    
    def __init__(self, productivity_tracker: ProductivityTracker,
                 compliance_tracker: ComplianceTracker,
                 business_calculator: BusinessValueCalculator):
        self.productivity = productivity_tracker
        self.compliance = compliance_tracker
        self.business = business_calculator
        self.cloudwatch = boto3.client('cloudwatch')
    
    def generate_daily_report(self, team: str = None) -> Dict[str, Any]:
        """Generate comprehensive daily metrics report"""
        report = {
            'date': datetime.now(timezone.utc).date().isoformat(),
            'team': team,
            'productivity_metrics': {},
            'compliance_metrics': {},
            'business_metrics': {},
            'recommendations': []
        }
        
        # Productivity metrics
        # This would integrate with actual user data
        report['productivity_metrics'] = {
            'active_users': 0,
            'total_sessions': 0,
            'average_completion_rate': 0,
            'average_efficiency': 0,
            'top_performers': [],
            'improvement_opportunities': []
        }
        
        # Compliance metrics
        if team:
            compliance_summary = self.compliance.get_team_compliance_summary(team)
            report['compliance_metrics'] = compliance_summary
        
        # Business metrics
        roi_metrics = self.business.calculate_roi_metrics(1)  # Daily
        report['business_metrics'] = {
            'daily_cost': sum(m.value for m in roi_metrics if m.metric_type.startswith('cost_')),
            'roi_percentage': next((m.value for m in roi_metrics if m.metric_type == 'roi_percentage'), 0),
            'cost_per_user': next((m.value for m in roi_metrics if m.metric_type == 'cost_per_user'), 0)
        }
        
        # Generate recommendations
        report['recommendations'] = self._generate_recommendations(report)
        
        return report
    
    def _generate_recommendations(self, report: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on metrics"""
        recommendations = []
        
        # Compliance recommendations
        compliance_score = report['compliance_metrics'].get('compliance_score', 100)
        if compliance_score < 95:
            recommendations.append(
                f"Compliance score is {compliance_score:.1f}%. Consider additional training or policy review."
            )
        
        # Cost recommendations
        daily_cost = report['business_metrics'].get('daily_cost', 0)
        if daily_cost > 100:  # Arbitrary threshold
            recommendations.append(
                f"Daily cost of ${daily_cost:.2f} is high. Review usage patterns and cache efficiency."
            )
        
        # ROI recommendations
        roi = report['business_metrics'].get('roi_percentage', 0)
        if roi < 20:
            recommendations.append(
                f"ROI of {roi:.1f}% is below target. Focus on productivity improvements and cost optimization."
            )
        
        return recommendations
    
    def send_metrics_to_cloudwatch(self, metrics: List[Any]):
        """Send metrics to CloudWatch"""
        try:
            metric_data = []
            
            for metric in metrics:
                if isinstance(metric, ProductivityMetric):
                    metric_data.append({
                        'MetricName': metric.metric_type,
                        'Dimensions': [
                            {'Name': 'Team', 'Value': metric.team},
                            {'Name': 'MetricType', 'Value': 'productivity'}
                        ],
                        'Value': metric.value,
                        'Unit': 'None',
                        'Timestamp': metric.timestamp
                    })
                elif isinstance(metric, ComplianceMetric):
                    metric_data.append({
                        'MetricName': 'compliance_score',
                        'Dimensions': [
                            {'Name': 'Team', 'Value': metric.team},
                            {'Name': 'SecurityProfile', 'Value': metric.security_profile},
                            {'Name': 'MetricType', 'Value': 'compliance'}
                        ],
                        'Value': metric.score,
                        'Unit': 'Percent',
                        'Timestamp': metric.timestamp
                    })
                elif isinstance(metric, BusinessValueMetric):
                    metric_data.append({
                        'MetricName': metric.metric_type,
                        'Dimensions': [
                            {'Name': 'Team', 'Value': metric.team or 'unknown'},
                            {'Name': 'MetricType', 'Value': 'business_value'}
                        ],
                        'Value': metric.value,
                        'Unit': 'None' if 'percentage' in metric.metric_type else 'None',
                        'Timestamp': metric.timestamp
                    })
            
            # Send in batches of 20 (CloudWatch limit)
            for i in range(0, len(metric_data), 20):
                batch = metric_data[i:i+20]
                self.cloudwatch.put_metric_data(
                    Namespace='ClaudeCode/Enterprise',
                    MetricData=batch
                )
                
        except Exception as e:
            logger.error(f"Failed to send metrics to CloudWatch: {e}")


# Global metrics instances
_global_productivity_tracker: Optional[ProductivityTracker] = None
_global_compliance_tracker: Optional[ComplianceTracker] = None
_global_business_calculator: Optional[BusinessValueCalculator] = None
_global_reporter: Optional[MetricsReporter] = None


def get_productivity_tracker() -> ProductivityTracker:
    """Get global productivity tracker"""
    global _global_productivity_tracker
    if _global_productivity_tracker is None:
        _global_productivity_tracker = ProductivityTracker()
    return _global_productivity_tracker


def get_compliance_tracker() -> ComplianceTracker:
    """Get global compliance tracker"""
    global _global_compliance_tracker
    if _global_compliance_tracker is None:
        _global_compliance_tracker = ComplianceTracker()
    return _global_compliance_tracker


def get_business_calculator() -> BusinessValueCalculator:
    """Get global business value calculator"""
    global _global_business_calculator
    if _global_business_calculator is None:
        _global_business_calculator = BusinessValueCalculator()
    return _global_business_calculator


def get_metrics_reporter() -> MetricsReporter:
    """Get global metrics reporter"""
    global _global_reporter
    if _global_reporter is None:
        _global_reporter = MetricsReporter(
            get_productivity_tracker(),
            get_compliance_tracker(),
            get_business_calculator()
        )
    return _global_reporter


# Convenience functions
def track_session_productivity(user_id: str, team: str, session_id: str, 
                             interactions: int, success_rate: float, duration_minutes: float):
    """Convenience function to track session productivity"""
    tracker = get_productivity_tracker()
    # Simulate session tracking
    tracker.session_metrics[session_id] = {
        'user_id': user_id,
        'team': team,
        'start_time': datetime.now(timezone.utc) - timedelta(minutes=duration_minutes),
        'end_time': datetime.now(timezone.utc),
        'duration_minutes': duration_minutes,
        'interactions': interactions,
        'success_actions': int(interactions * success_rate / 100),
        'errors_encountered': interactions - int(interactions * success_rate / 100),
        'tokens_used': interactions * 500,  # Estimate
        'files_modified': max(1, interactions // 3),
        'commands_executed': max(1, interactions // 4),
        'cache_hits': int(interactions * 0.7),  # 70% cache hit rate
        'cache_misses': int(interactions * 0.3)
    }
    
    return tracker.track_session_end(session_id)


def track_policy_compliance(user_id: str, team: str, security_profile: str, 
                           policy_checks: int, violations: int):
    """Convenience function to track policy compliance"""
    tracker = get_compliance_tracker()
    
    # Track individual policy checks
    for i in range(policy_checks):
        passed = i >= violations  # First N checks fail, rest pass
        tracker.track_policy_check(
            user_id=user_id,
            team=team,
            security_profile=security_profile,
            policy_type='general',
            passed=passed
        )
    
    return tracker.calculate_compliance_score(user_id, team, security_profile)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude Code Productivity Metrics")
    parser.add_argument("--test", action="store_true", help="Run test scenarios")
    parser.add_argument("--report", action="store_true", help="Generate test report")
    
    args = parser.parse_args()
    
    if args.test:
        print("Testing productivity metrics...")
        
        # Test session tracking
        metrics = track_session_productivity(
            user_id="test_user",
            team="engineering", 
            session_id="test_session_1",
            interactions=20,
            success_rate=85.0,
            duration_minutes=30.0
        )
        
        print(f"Generated {len(metrics)} productivity metrics")
        for metric in metrics:
            print(f"  {metric.metric_type}: {metric.value:.2f}")
        
        # Test compliance tracking
        compliance = track_policy_compliance(
            user_id="test_user",
            team="engineering",
            security_profile="standard",
            policy_checks=50,
            violations=2
        )
        
        print(f"Compliance score: {compliance.score:.1f}%")
        
    if args.report:
        reporter = get_metrics_reporter()
        report = reporter.generate_daily_report("engineering")
        print(f"Daily report: {json.dumps(report, indent=2)}")