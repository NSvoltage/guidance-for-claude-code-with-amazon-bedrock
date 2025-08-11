#!/usr/bin/env python3
"""
Simple Phase 1 Validation Test
Tests basic functionality of Phase 1 components without AWS dependencies.
"""
import os
import sys
import json
import yaml
import unittest
from unittest.mock import Mock, patch

print("🔍 Starting Phase 1 Component Testing...")

class TestPhase1Components(unittest.TestCase):
    """Simple tests for Phase 1 components."""
    
    def test_configuration_files(self):
        """Test all configuration files are valid."""
        print("\n📋 Testing configuration files...")
        
        # Test OTEL collector config
        with open('collectors/enhanced_otel_config.yaml', 'r') as f:
            otel_config = yaml.safe_load(f)
        
        required_sections = ['receivers', 'processors', 'exporters', 'service']
        for section in required_sections:
            self.assertIn(section, otel_config, f"Missing section: {section}")
        
        # Test pipelines exist
        pipelines = otel_config['service']['pipelines']
        self.assertIn('traces', pipelines)
        self.assertIn('metrics', pipelines)
        print("  ✅ OTEL collector configuration valid")
        
        # Test dashboard JSON
        with open('dashboards/advanced_enterprise_dashboard.json', 'r') as f:
            dashboard = json.load(f)
        
        self.assertIn('widgets', dashboard)
        self.assertGreater(len(dashboard['widgets']), 0)
        
        # Validate widget structure
        for widget in dashboard['widgets']:
            self.assertIn('type', widget)
            self.assertIn('properties', widget)
        print("  ✅ Dashboard configuration valid")
        
    def test_python_syntax(self):
        """Test all Python files have valid syntax."""
        print("\n🐍 Testing Python syntax...")
        
        python_files = [
            'spans/claude_code_tracer.py',
            'spans/enhanced_wrapper.py', 
            'monitoring_integration.py',
            'metrics/productivity_metrics.py',
            'alerting/anomaly_detection_engine.py'
        ]
        
        for file_path in python_files:
            with open(file_path, 'r') as f:
                code = f.read()
            
            # Test syntax by compiling
            try:
                compile(code, file_path, 'exec')
                print(f"  ✅ {file_path} syntax valid")
            except SyntaxError as e:
                self.fail(f"Syntax error in {file_path}: {e}")
    
    def test_component_structure(self):
        """Test component classes can be defined (without executing)."""
        print("\n🏗️  Testing component structure...")
        
        # Test tracer configuration classes exist
        with open('spans/claude_code_tracer.py', 'r') as f:
            content = f.read()
            self.assertIn('class ClaudeCodeTracer', content)
            self.assertIn('class UserContext', content)
            print("  ✅ Tracer classes defined")
        
        # Test anomaly detection classes
        with open('alerting/anomaly_detection_engine.py', 'r') as f:
            content = f.read()
            self.assertIn('class AnomalyDetectionEngine', content)
            self.assertIn('class AnomalyAlert', content)
            print("  ✅ Anomaly detection classes defined")
            
        # Test productivity metrics classes
        with open('metrics/productivity_metrics.py', 'r') as f:
            content = f.read()
            self.assertIn('class ProductivityTracker', content)
            self.assertIn('class ProductivityMetric', content)
            print("  ✅ Productivity metrics classes defined")
            
        # Test monitoring integration
        with open('monitoring_integration.py', 'r') as f:
            content = f.read()
            self.assertIn('class ComprehensiveMonitor', content)
            self.assertIn('class MonitoringConfig', content)
            print("  ✅ Monitoring integration class defined")
    
    def test_documentation_exists(self):
        """Test documentation files exist and have content."""
        print("\n📚 Testing documentation...")
        
        doc_file = 'docs/PHASE_1_OBSERVABILITY_GUIDE.md'
        self.assertTrue(os.path.exists(doc_file), f"Documentation missing: {doc_file}")
        
        with open(doc_file, 'r') as f:
            content = f.read()
            self.assertGreater(len(content), 1000, "Documentation too short")
            self.assertIn('# Phase 1 Advanced Observability Guide', content)
            self.assertIn('## Architecture Overview', content)
            self.assertIn('## Deployment Guide', content)
            print("  ✅ Documentation complete")

def run_simple_tests():
    """Run simple Phase 1 component tests."""
    # Change to the observability directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    print(f"📁 Testing from directory: {os.getcwd()}")
    
    # Run tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPhase1Components)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    
    # Summary
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    
    print(f"\n📊 Phase 1 Test Results:")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {total_tests - failures - errors}")
    print(f"Failed: {failures}")
    print(f"Errors: {errors}")
    
    if failures == 0 and errors == 0:
        print("✅ All Phase 1 component tests passed!")
        return True
    else:
        print("❌ Some Phase 1 tests failed.")
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"  - {test}: {traceback}")
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"  - {test}: {traceback}")
        return False

if __name__ == "__main__":
    success = run_simple_tests()
    sys.exit(0 if success else 1)