#!/usr/bin/env python3
"""
Enhanced enterprise wrapper for Claude Code with comprehensive telemetry.
Extends the basic governance wrapper with detailed OpenTelemetry instrumentation.
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
import argparse

# Import the enhanced tracer
try:
    from claude_code_tracer import (
        ClaudeCodeTracer, 
        UserContext, 
        ModelContext,
        CostContext,
        get_tracer,
        trace_claude_operation
    )
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False

# Import existing governance wrapper functionality
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "governance"))
try:
    from claude_code_wrapper import (
        ENTERPRISE_POLICY_PROFILES,
        load_enterprise_config,
        get_security_profile,
        apply_security_profile,
        check_policy_compliance,
        setup_monitoring,
        find_claude_code_executable
    )
    GOVERNANCE_AVAILABLE = True
except ImportError:
    GOVERNANCE_AVAILABLE = False
    print("Warning: Governance wrapper not available", file=sys.stderr)


class EnhancedClaudeWrapper:
    """Enhanced wrapper with comprehensive telemetry and governance"""
    
    def __init__(self):
        self.tracer = get_tracer() if TRACING_AVAILABLE else None
        self.user_context = None
        self.project_context = {}
        self.session_id = None
        
    def initialize_telemetry(self):
        """Initialize telemetry with user context"""
        if not TRACING_AVAILABLE:
            return
            
        # Extract user context from enterprise config and environment
        self.user_context = self._extract_user_context()
        if self.user_context:
            self.tracer.update_user_context(self.user_context)
            
        # Extract project context
        self.project_context = self._extract_project_context()
        
        # Set up cost context based on enterprise configuration
        cost_context = self._get_cost_context()
        if cost_context:
            self.tracer.update_cost_context(cost_context)
    
    def _extract_user_context(self) -> Optional[UserContext]:
        """Extract user context from available sources"""
        try:
            # Try to get user info from OTEL helper token
            user_info = self._get_user_from_token()
            
            if user_info:
                return UserContext(
                    user_id=user_info.get("sub"),
                    email=user_info.get("email"),
                    name=user_info.get("name", user_info.get("preferred_username")),
                    team=user_info.get("team", user_info.get("department")),
                    department=user_info.get("department"),
                    role=user_info.get("role", user_info.get("job_title")),
                    organization=user_info.get("org", user_info.get("organization")),
                    security_profile=get_security_profile() if GOVERNANCE_AVAILABLE else None
                )
        except Exception as e:
            print(f"Warning: Could not extract user context: {e}", file=sys.stderr)
            
        return None
    
    def _get_user_from_token(self) -> Optional[Dict[str, Any]]:
        """Extract user info from authentication token"""
        try:
            # Try to run the OTEL helper to get user information
            helper_path = Path(__file__).parent.parent.parent.parent / "source" / "otel_helper" / "__main__.py"
            if helper_path.exists():
                result = subprocess.run([
                    sys.executable, str(helper_path), "--test"
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    # Parse the output to extract user info
                    for line in result.stdout.split('\n'):
                        if 'User attributes extracted:' in line:
                            # Extract JSON from the line
                            json_start = line.find('{')
                            if json_start != -1:
                                return json.loads(line[json_start:])
        except Exception as e:
            print(f"Could not extract user from token: {e}", file=sys.stderr)
            
        return None
    
    def _extract_project_context(self) -> Dict[str, str]:
        """Extract project context from git and filesystem"""
        context = {}
        
        try:
            # Get current directory info
            cwd = Path.cwd()
            context["path"] = str(cwd)
            context["name"] = cwd.name
            
            # Try to get git info
            try:
                # Get repository URL
                result = subprocess.run(
                    ["git", "config", "--get", "remote.origin.url"],
                    capture_output=True, text=True, cwd=cwd, timeout=5
                )
                if result.returncode == 0:
                    context["repository_url"] = result.stdout.strip()
                    
                # Get current branch
                result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True, text=True, cwd=cwd, timeout=5
                )
                if result.returncode == 0:
                    context["branch"] = result.stdout.strip()
                    
            except Exception:
                pass  # Git info is optional
                
        except Exception as e:
            print(f"Warning: Could not extract project context: {e}", file=sys.stderr)
            
        return context
    
    def _get_cost_context(self) -> Optional[CostContext]:
        """Get cost calculation context from enterprise config"""
        try:
            config = load_enterprise_config() if GOVERNANCE_AVAILABLE else {}
            if not config:
                return CostContext()  # Default pricing
                
            # Extract custom pricing if configured
            pricing_config = config.get("pricing", {})
            
            return CostContext(
                input_cost_per_token=pricing_config.get("input_cost_per_token", 0.000008),
                output_cost_per_token=pricing_config.get("output_cost_per_token", 0.000024),
                cache_savings_multiplier=pricing_config.get("cache_savings_multiplier", 0.9)
            )
            
        except Exception:
            return CostContext()  # Fallback to defaults

    def execute_claude_with_telemetry(self, args: List[str]) -> int:
        """Execute Claude Code with comprehensive telemetry"""
        
        if not TRACING_AVAILABLE:
            return self._execute_claude_basic(args)
        
        session_start = time.time()
        
        with self.tracer.span("claude_session", "session", 
                             project_ctx=self.project_context,
                             session_args=' '.join(args[:3])  # First few args for context
                             ) as session_span:
            
            try:
                # Record session initialization
                self.tracer.record_event(session_span, "session_start", {
                    "args_count": len(args),
                    "working_directory": str(Path.cwd()),
                    "security_profile": get_security_profile() if GOVERNANCE_AVAILABLE else "unknown"
                })
                
                # Apply governance policies with telemetry
                if GOVERNANCE_AVAILABLE:
                    with self.tracer.span("policy_check", "governance") as policy_span:
                        if not check_policy_compliance():
                            self.tracer.record_security_event(policy_span, "policy_violation", {
                                "profile": get_security_profile(),
                                "action": "execution_blocked"
                            })
                            return 1
                        
                        self.tracer.record_security_event(policy_span, "policy_compliance", {
                            "profile": get_security_profile(),
                            "action": "execution_allowed"
                        })
                
                # Execute Claude Code with monitoring
                return self._execute_with_monitoring(args, session_span)
                
            except Exception as e:
                self.tracer.record_event(session_span, "session_error", {
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                })
                raise
            finally:
                # Record session metrics
                session_duration = int((time.time() - session_start) * 1000)
                session_span.set_attribute("claude.session.duration_ms", session_duration)
                
                self.tracer.record_event(session_span, "session_end", {
                    "duration_ms": session_duration
                })
    
    def _execute_with_monitoring(self, args: List[str], parent_span) -> int:
        """Execute Claude with detailed monitoring"""
        
        # Find Claude executable
        claude_executable = find_claude_code_executable() if GOVERNANCE_AVAILABLE else "claude"
        if not claude_executable:
            raise RuntimeError("Claude Code executable not found")
        
        # Set up environment with telemetry
        env = os.environ.copy()
        
        # Add telemetry configuration
        if TRACING_AVAILABLE:
            env["OTEL_SERVICE_NAME"] = "claude-code-enterprise"
            env["OTEL_RESOURCE_ATTRIBUTES"] = f"service.name=claude-code,user.team={self.user_context.team if self.user_context else 'unknown'}"
        
        with self.tracer.span("claude_execution", "execution",
                             executable=claude_executable) as exec_span:
            
            try:
                # Start Claude Code process
                process_start = time.time()
                
                result = subprocess.run(
                    [claude_executable] + args,
                    env=env
                )
                
                # Record execution metrics
                execution_time = int((time.time() - process_start) * 1000)
                exec_span.set_attribute("claude.execution.duration_ms", execution_time)
                exec_span.set_attribute("claude.execution.exit_code", result.returncode)
                
                # Record success/failure
                if result.returncode == 0:
                    self.tracer.record_event(exec_span, "execution_success", {
                        "duration_ms": execution_time
                    })
                else:
                    self.tracer.record_event(exec_span, "execution_failure", {
                        "exit_code": result.returncode,
                        "duration_ms": execution_time
                    })
                
                return result.returncode
                
            except Exception as e:
                # Record execution errors
                self.tracer.record_event(exec_span, "execution_error", {
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                })
                raise
    
    def _execute_claude_basic(self, args: List[str]) -> int:
        """Fallback execution without telemetry"""
        try:
            if GOVERNANCE_AVAILABLE:
                # Apply governance if available
                if not check_policy_compliance():
                    return 1
                    
                claude_executable = find_claude_code_executable()
                if not claude_executable:
                    return 1
                    
                result = subprocess.run([claude_executable] + args)
                return result.returncode
            else:
                # Direct execution
                result = subprocess.run(["claude"] + args)
                return result.returncode
                
        except Exception as e:
            print(f"Execution error: {e}", file=sys.stderr)
            return 1


def main():
    """Enhanced main entry point with comprehensive telemetry"""
    parser = argparse.ArgumentParser(
        description="Enhanced Enterprise wrapper for Claude Code with telemetry",
        add_help=False  # Pass through to underlying claude command
    )
    
    # Enterprise governance options
    if GOVERNANCE_AVAILABLE:
        parser.add_argument("--security-profile", 
                           choices=list(ENTERPRISE_POLICY_PROFILES.keys()),
                           help="Override security profile")
        parser.add_argument("--check-policy", 
                           action="store_true",
                           help="Check policy compliance and exit")
    
    # Telemetry options
    parser.add_argument("--disable-telemetry",
                       action="store_true",
                       help="Disable telemetry collection")
    parser.add_argument("--telemetry-debug",
                       action="store_true", 
                       help="Enable telemetry debugging")
    
    # Parse known args, pass the rest through
    known_args, remaining_args = parser.parse_known_args()
    
    # Handle governance check-policy option
    if GOVERNANCE_AVAILABLE and known_args.check_policy:
        profile_name = get_security_profile()
        print(f"Active security profile: {profile_name}")
        if check_policy_compliance():
            print("✅ Policy compliance check passed")
            return 0
        else:
            print("❌ Policy compliance check failed")
            return 1
    
    # Initialize enhanced wrapper
    wrapper = EnhancedClaudeWrapper()
    
    # Set up telemetry unless disabled
    if not known_args.disable_telemetry and TRACING_AVAILABLE:
        wrapper.initialize_telemetry()
        
        if known_args.telemetry_debug:
            os.environ["DEBUG_MODE"] = "true"
    
    # Apply security profile if governance is available
    if GOVERNANCE_AVAILABLE:
        profile_name = known_args.security_profile or get_security_profile()
        apply_security_profile(profile_name)
        setup_monitoring()
    
    # Filter out our custom args from the command line
    filtered_args = []
    skip_next = False
    
    for arg in sys.argv[1:]:
        if skip_next:
            skip_next = False
            continue
            
        if arg in ["--check-policy", "--disable-telemetry", "--telemetry-debug"]:
            continue
        elif arg.startswith("--security-profile"):
            if "=" not in arg:
                skip_next = True  # Skip the value too
            continue
        else:
            filtered_args.append(arg)
    
    # Execute Claude Code with enhanced monitoring
    try:
        return wrapper.execute_claude_with_telemetry(filtered_args)
    except KeyboardInterrupt:
        print("\n\nClaude Code execution interrupted", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Error executing Claude Code: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())