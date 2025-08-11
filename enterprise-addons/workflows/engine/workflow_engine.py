#!/usr/bin/env python3
"""
Workflow Execution Engine for Claude Code Enterprise
Executes parsed workflows with state management, caching, and observability integration.
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
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from parser.workflow_parser import WorkflowDefinition, WorkflowStep, WorkflowParser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Workflow/Step execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CACHED = "cached"


@dataclass
class StepResult:
    """Result of step execution"""
    step_id: str
    status: ExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    cached: bool = False
    cache_key: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    exit_code: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'step_id': self.step_id,
            'status': self.status.value,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'outputs': self.outputs,
            'error': self.error,
            'cached': self.cached,
            'cache_key': self.cache_key,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'exit_code': self.exit_code
        }


@dataclass
class WorkflowExecution:
    """Workflow execution state"""
    execution_id: str
    workflow_name: str
    workflow_version: str
    status: ExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, StepResult] = field(default_factory=dict)
    current_step: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'execution_id': self.execution_id,
            'workflow_name': self.workflow_name,
            'workflow_version': self.workflow_version,
            'status': self.status.value,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'inputs': self.inputs,
            'outputs': self.outputs,
            'step_results': {k: v.to_dict() for k, v in self.step_results.items()},
            'current_step': self.current_step,
            'error': self.error
        }


class StepExecutor:
    """Base class for step executors"""
    
    def __init__(self, engine: 'WorkflowEngine'):
        self.engine = engine
    
    async def execute(self, step: WorkflowStep, context: Dict[str, Any]) -> StepResult:
        """Execute a workflow step"""
        raise NotImplementedError


class ShellStepExecutor(StepExecutor):
    """Executor for shell command steps"""
    
    async def execute(self, step: WorkflowStep, context: Dict[str, Any]) -> StepResult:
        """Execute shell command step"""
        result = StepResult(
            step_id=step.id,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc)
        )
        
        try:
            # Render command template
            command = self.engine.parser.template_engine.render(step.command, context)
            
            # Set up environment
            env = os.environ.copy()
            env.update(step.environment)
            
            # Render environment variable templates
            for key, value in step.environment.items():
                env[key] = self.engine.parser.template_engine.render(value, context)
            
            # Set working directory
            cwd = step.working_directory
            if cwd:
                cwd = self.engine.parser.template_engine.render(cwd, context)
            
            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd
            )
            
            # Wait for completion with timeout
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=step.timeout
                )
                
                result.stdout = stdout_bytes.decode('utf-8') if stdout_bytes else ""
                result.stderr = stderr_bytes.decode('utf-8') if stderr_bytes else ""
                result.exit_code = process.returncode
                
                if process.returncode == 0:
                    result.status = ExecutionStatus.COMPLETED
                    
                    # Extract outputs from stdout if defined
                    for output_name, output_config in step.outputs.items():
                        if output_config.from_source:
                            # Simple extraction - in production, you'd want more sophisticated parsing
                            result.outputs[output_name] = result.stdout.strip()
                        else:
                            result.outputs[output_name] = result.stdout.strip()
                
                else:
                    result.status = ExecutionStatus.FAILED
                    result.error = f"Command failed with exit code {process.returncode}: {result.stderr}"
                
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                result.status = ExecutionStatus.FAILED
                result.error = f"Command timed out after {step.timeout} seconds"
        
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = f"Shell execution error: {e}"
        
        finally:
            result.completed_at = datetime.now(timezone.utc)
            result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
        
        return result


class ClaudeCodeStepExecutor(StepExecutor):
    """Executor for Claude Code steps"""
    
    async def execute(self, step: WorkflowStep, context: Dict[str, Any]) -> StepResult:
        """Execute Claude Code step"""
        result = StepResult(
            step_id=step.id,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc)
        )
        
        try:
            # Render prompt template
            prompt = self.engine.parser.template_engine.render(step.prompt, context)
            
            # For now, simulate Claude Code execution
            # In production, this would integrate with actual Claude Code CLI
            result.outputs['response'] = f"Claude Code response for: {prompt[:100]}..."
            result.outputs['model_used'] = step.model
            result.outputs['tokens_used'] = 150  # Simulated
            
            result.status = ExecutionStatus.COMPLETED
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = f"Claude Code execution error: {e}"
        
        finally:
            result.completed_at = datetime.now(timezone.utc)
            result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
        
        return result


class AssertStepExecutor(StepExecutor):
    """Executor for assertion steps"""
    
    async def execute(self, step: WorkflowStep, context: Dict[str, Any]) -> StepResult:
        """Execute assertion step"""
        result = StepResult(
            step_id=step.id,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc)
        )
        
        try:
            # Render condition template
            condition = self.engine.parser.template_engine.render(step.condition, context)
            
            # Simple boolean evaluation
            # In production, you'd want a proper expression evaluator
            assertion_passed = self._evaluate_condition(condition, context)
            
            if assertion_passed:
                result.status = ExecutionStatus.COMPLETED
                result.outputs['assertion_result'] = True
            else:
                if step.on_failure == 'fail':
                    result.status = ExecutionStatus.FAILED
                    result.error = step.message or f"Assertion failed: {condition}"
                elif step.on_failure == 'warn':
                    result.status = ExecutionStatus.COMPLETED
                    result.outputs['assertion_result'] = False
                    result.outputs['warning'] = step.message or f"Assertion failed: {condition}"
                else:  # continue
                    result.status = ExecutionStatus.SKIPPED
                    result.outputs['assertion_result'] = False
        
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = f"Assertion evaluation error: {e}"
        
        finally:
            result.completed_at = datetime.now(timezone.utc)
            result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
        
        return result
    
    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate assertion condition (simplified)"""
        # This is a very basic implementation
        # In production, use a proper expression evaluator like simpleeval
        try:
            # Very basic boolean evaluation
            if condition.lower() in ['true', '1', 'yes']:
                return True
            elif condition.lower() in ['false', '0', 'no']:
                return False
            else:
                # Try to evaluate as Python expression (DANGEROUS - for demo only)
                # In production, use a safe expression evaluator
                return bool(eval(condition, {"__builtins__": {}}, context))
        except:
            return False


class TemplateStepExecutor(StepExecutor):
    """Executor for template generation steps"""
    
    async def execute(self, step: WorkflowStep, context: Dict[str, Any]) -> StepResult:
        """Execute template step"""
        result = StepResult(
            step_id=step.id,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc)
        )
        
        try:
            # Render template content
            template_content = self.engine.parser.template_engine.render(step.template, context)
            
            # Render output path
            output_path = self.engine.parser.template_engine.render(step.output, context)
            
            # Write template to output file
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w') as f:
                f.write(template_content)
            
            result.status = ExecutionStatus.COMPLETED
            result.outputs['output_file'] = output_path
            result.outputs['template_length'] = len(template_content)
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = f"Template execution error: {e}"
        
        finally:
            result.completed_at = datetime.now(timezone.utc)
            result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
        
        return result


class WorkflowEngine:
    """Main workflow execution engine"""
    
    def __init__(self, parser: Optional[WorkflowParser] = None, cache_enabled: bool = True):
        self.parser = parser or WorkflowParser()
        self.cache_enabled = cache_enabled
        self.step_executors = {
            'shell': ShellStepExecutor(self),
            'claude_code': ClaudeCodeStepExecutor(self),
            'assert': AssertStepExecutor(self),
            'template': TemplateStepExecutor(self)
        }
        
        # State storage (in production, use DynamoDB)
        self.executions: Dict[str, WorkflowExecution] = {}
        
        # Step cache (in production, use S3/Redis)
        self.step_cache: Dict[str, Dict[str, Any]] = {}
    
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        inputs: Dict[str, Any],
        execution_id: Optional[str] = None,
        resume_from_step: Optional[str] = None
    ) -> WorkflowExecution:
        """Execute a complete workflow"""
        
        # Create execution record
        if execution_id is None:
            execution_id = str(uuid.uuid4())
        
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_name=workflow.name,
            workflow_version=workflow.version,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            inputs=inputs
        )
        
        self.executions[execution_id] = execution
        
        try:
            # Validate inputs
            self._validate_workflow_inputs(workflow, inputs)
            
            # Execute steps in order
            context = {
                'inputs': inputs,
                'workflow': asdict(workflow),
                'execution': asdict(execution),
                'env': dict(os.environ),
                'steps': {}  # Will be populated with step results
            }
            
            # Determine starting step
            start_index = 0
            if resume_from_step:
                try:
                    start_index = workflow.execution_order.index(resume_from_step)
                except ValueError:
                    raise ValueError(f"Resume step {resume_from_step} not found in workflow")
            
            # Execute steps
            for i in range(start_index, len(workflow.execution_order)):
                step_id = workflow.execution_order[i]
                step = next(s for s in workflow.steps if s.id == step_id)
                
                execution.current_step = step_id
                
                # Check if step should be skipped due to conditional
                if step.when:
                    condition_result = self._evaluate_when_condition(step.when, context)
                    if not condition_result:
                        # Skip step
                        result = StepResult(
                            step_id=step_id,
                            status=ExecutionStatus.SKIPPED,
                            started_at=datetime.now(timezone.utc),
                            completed_at=datetime.now(timezone.utc)
                        )
                        execution.step_results[step_id] = result
                        context['steps'][step_id] = result.to_dict()
                        continue
                
                # Execute step
                result = await self._execute_step(step, context, execution)
                execution.step_results[step_id] = result
                context['steps'][step_id] = result.to_dict()
                
                # Check if step failed
                if result.status == ExecutionStatus.FAILED:
                    execution.status = ExecutionStatus.FAILED
                    execution.error = f"Step {step_id} failed: {result.error}"
                    break
            
            # Set final status if not already failed
            if execution.status == ExecutionStatus.RUNNING:
                execution.status = ExecutionStatus.COMPLETED
                
                # Extract workflow outputs
                for output_name, output_config in workflow.outputs.items():
                    if output_config.from_step:
                        step_reference = output_config.from_step
                        output_value = self._extract_output_value(step_reference, context)
                        execution.outputs[output_name] = output_value
        
        except Exception as e:
            execution.status = ExecutionStatus.FAILED
            execution.error = f"Workflow execution error: {e}"
        
        finally:
            execution.completed_at = datetime.now(timezone.utc)
            execution.current_step = None
        
        return execution
    
    async def _execute_step(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        execution: WorkflowExecution
    ) -> StepResult:
        """Execute individual workflow step with caching"""
        
        # Check cache first
        if self.cache_enabled and step.cache.get('enabled', True):
            cache_key = self.parser.generate_cache_key(step, context)
            cached_result = self.step_cache.get(cache_key)
            
            if cached_result:
                # Return cached result
                result = StepResult(**cached_result)
                result.cached = True
                result.cache_key = cache_key
                logger.info(f"Using cached result for step {step.id}")
                return result
        
        # Execute step
        executor = self.step_executors.get(step.type)
        if not executor:
            raise ValueError(f"Unknown step type: {step.type}")
        
        logger.info(f"Executing step {step.id} ({step.type})")
        result = await executor.execute(step, context)
        
        # Cache result if successful
        if (self.cache_enabled and 
            step.cache.get('enabled', True) and 
            result.status == ExecutionStatus.COMPLETED):
            
            cache_key = self.parser.generate_cache_key(step, context)
            result.cache_key = cache_key
            
            # Store in cache
            cache_data = result.to_dict()
            cache_data['cached_at'] = datetime.now(timezone.utc).isoformat()
            self.step_cache[cache_key] = cache_data
            
            logger.info(f"Cached result for step {step.id} with key {cache_key[:8]}...")
        
        return result
    
    def _validate_workflow_inputs(self, workflow: WorkflowDefinition, inputs: Dict[str, Any]):
        """Validate workflow inputs against definition"""
        for input_name, input_config in workflow.inputs.items():
            if input_config.required and input_name not in inputs:
                raise ValueError(f"Required input {input_name} not provided")
            
            # Apply defaults
            if input_name not in inputs and input_config.default is not None:
                inputs[input_name] = input_config.default
    
    def _evaluate_when_condition(self, when_condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate when condition for conditional step execution"""
        try:
            # Render template
            condition = self.parser.template_engine.render(when_condition, context)
            
            # Basic boolean evaluation (in production, use proper expression evaluator)
            if condition.lower() in ['true', '1', 'yes']:
                return True
            elif condition.lower() in ['false', '0', 'no', '']:
                return False
            else:
                # Try Python evaluation (DANGEROUS - for demo only)
                return bool(eval(condition, {"__builtins__": {}}, context))
        except:
            return False
    
    def _extract_output_value(self, step_reference: str, context: Dict[str, Any]) -> Any:
        """Extract output value from step reference like 'step1.outputs.result'"""
        try:
            parts = step_reference.split('.')
            value = context
            
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return None
            
            return value
        except:
            return None
    
    def get_execution_status(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get execution status by ID"""
        return self.executions.get(execution_id)
    
    def list_executions(self, workflow_name: Optional[str] = None) -> List[WorkflowExecution]:
        """List workflow executions"""
        executions = list(self.executions.values())
        
        if workflow_name:
            executions = [e for e in executions if e.workflow_name == workflow_name]
        
        return sorted(executions, key=lambda x: x.started_at, reverse=True)
    
    def clear_cache(self, pattern: Optional[str] = None):
        """Clear step cache"""
        if pattern:
            # Clear cache entries matching pattern
            keys_to_remove = [k for k in self.step_cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self.step_cache[key]
        else:
            # Clear all cache
            self.step_cache.clear()
        
        logger.info(f"Cleared cache {f'matching {pattern}' if pattern else ''}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'total_entries': len(self.step_cache),
            'cache_size_mb': sum(len(str(v)) for v in self.step_cache.values()) / (1024 * 1024),
            'oldest_entry': min((v.get('cached_at', '') for v in self.step_cache.values()), default=''),
            'newest_entry': max((v.get('cached_at', '') for v in self.step_cache.values()), default='')
        }


async def main():
    """CLI interface for workflow engine"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude Code Workflow Engine")
    parser.add_argument("workflow_file", help="Path to workflow YAML file")
    parser.add_argument("--inputs", help="JSON string of workflow inputs", default="{}")
    parser.add_argument("--execution-id", help="Execution ID (for resume)")
    parser.add_argument("--resume-from", help="Step ID to resume from")
    parser.add_argument("--no-cache", action="store_true", help="Disable step caching")
    parser.add_argument("--output", help="Output file for execution results")
    
    args = parser.parse_args()
    
    try:
        # Parse inputs
        inputs = json.loads(args.inputs)
        
        # Create workflow engine
        workflow_parser = WorkflowParser()
        workflow_engine = WorkflowEngine(workflow_parser, cache_enabled=not args.no_cache)
        
        # Parse workflow
        workflow = workflow_parser.parse_workflow(args.workflow_file)
        
        print(f"🔄 Executing workflow: {workflow.name} v{workflow.version}")
        print(f"   Inputs: {inputs}")
        
        # Execute workflow
        execution = await workflow_engine.execute_workflow(
            workflow,
            inputs,
            args.execution_id,
            args.resume_from
        )
        
        # Print results
        print(f"\n📊 Execution Results:")
        print(f"   Execution ID: {execution.execution_id}")
        print(f"   Status: {execution.status.value}")
        print(f"   Duration: {(execution.completed_at - execution.started_at).total_seconds():.2f}s")
        
        if execution.status == ExecutionStatus.COMPLETED:
            print(f"   Outputs: {execution.outputs}")
        elif execution.status == ExecutionStatus.FAILED:
            print(f"   Error: {execution.error}")
        
        # Step results
        print(f"\n📋 Step Results:")
        for step_id, result in execution.step_results.items():
            status_icon = "✅" if result.status == ExecutionStatus.COMPLETED else "❌"
            cache_indicator = " (cached)" if result.cached else ""
            print(f"   {status_icon} {step_id}: {result.status.value}{cache_indicator} ({result.duration_seconds:.2f}s)")
            if result.error:
                print(f"      Error: {result.error}")
        
        # Save output if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(execution.to_dict(), f, indent=2, default=str)
            print(f"📄 Saved execution results to: {args.output}")
        
        # Cache stats
        cache_stats = workflow_engine.get_cache_stats()
        print(f"\n📦 Cache Stats:")
        print(f"   Entries: {cache_stats['total_entries']}")
        print(f"   Size: {cache_stats['cache_size_mb']:.2f} MB")
        
        # Exit with appropriate code
        sys.exit(0 if execution.status == ExecutionStatus.COMPLETED else 1)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())