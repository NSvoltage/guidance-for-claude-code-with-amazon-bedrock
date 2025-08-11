#!/usr/bin/env python3
"""
Workflow Parser for Claude Code Enterprise
Parses and validates workflow YAML definitions against the schema.
"""
import os
import sys
import yaml
import json
import re
import hashlib
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
import jsonschema

# Template engine for variable substitution
try:
    from jinja2 import Template, Environment, StrictUndefined
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False


@dataclass
class WorkflowInput:
    """Workflow input parameter definition"""
    name: str
    type: str
    description: Optional[str] = None
    required: bool = False
    default: Any = None
    validation: Optional[Dict[str, Any]] = None


@dataclass
class WorkflowOutput:
    """Workflow output definition"""
    name: str
    type: str
    description: Optional[str] = None
    from_step: Optional[str] = None


@dataclass
class StepOutput:
    """Step output definition"""
    name: str
    type: str
    description: Optional[str] = None
    from_source: Optional[str] = None


@dataclass
class WorkflowStep:
    """Workflow step definition"""
    id: str
    type: str
    name: Optional[str] = None
    description: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    when: Optional[str] = None
    timeout: int = 300
    retry: Dict[str, Any] = field(default_factory=dict)
    cache: Dict[str, Any] = field(default_factory=dict)
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, StepOutput] = field(default_factory=dict)
    
    # Step type specific properties
    command: Optional[str] = None  # shell
    working_directory: Optional[str] = None  # shell
    environment: Dict[str, str] = field(default_factory=dict)  # shell
    
    prompt: Optional[str] = None  # claude_code
    model: str = "claude-3-sonnet-20240229"  # claude_code
    security_profile: str = "restricted"  # claude_code
    use_cache: bool = True  # claude_code
    max_tokens: Optional[int] = None  # claude_code
    temperature: float = 0.0  # claude_code
    
    condition: Optional[str] = None  # assert, conditional
    message: Optional[str] = None  # assert
    on_failure: str = "fail"  # assert
    
    template: Optional[str] = None  # template
    output: Optional[str] = None  # template
    engine: str = "jinja2"  # template
    
    url: Optional[str] = None  # webhook
    method: str = "POST"  # webhook
    headers: Dict[str, str] = field(default_factory=dict)  # webhook
    body: Optional[str] = None  # webhook
    
    then_steps: List['WorkflowStep'] = field(default_factory=list)  # conditional
    else_steps: List['WorkflowStep'] = field(default_factory=list)  # conditional


@dataclass
class WorkflowDefinition:
    """Complete workflow definition"""
    name: str
    version: str
    description: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    inputs: Dict[str, WorkflowInput] = field(default_factory=dict)
    outputs: Dict[str, WorkflowOutput] = field(default_factory=dict)
    environment: Dict[str, str] = field(default_factory=dict)
    timeout: int = 3600
    retry: Dict[str, Any] = field(default_factory=dict)
    cache: Dict[str, Any] = field(default_factory=dict)
    steps: List[WorkflowStep] = field(default_factory=list)
    
    # Computed properties
    step_dependency_graph: Dict[str, Set[str]] = field(default_factory=dict, init=False)
    execution_order: List[str] = field(default_factory=list, init=False)


class WorkflowParseError(Exception):
    """Workflow parsing error"""
    pass


class WorkflowValidationError(Exception):
    """Workflow validation error"""
    pass


class TemplateEngine:
    """Template engine for variable substitution"""
    
    def __init__(self):
        if JINJA2_AVAILABLE:
            self.env = Environment(undefined=StrictUndefined)
        
    def render(self, template_str: str, context: Dict[str, Any]) -> str:
        """Render template with given context"""
        if not JINJA2_AVAILABLE:
            # Simple {{ variable }} substitution fallback
            return self._simple_render(template_str, context)
        
        try:
            template = self.env.from_string(template_str)
            return template.render(**context)
        except Exception as e:
            raise WorkflowParseError(f"Template rendering error: {e}")
    
    def _simple_render(self, template_str: str, context: Dict[str, Any]) -> str:
        """Simple template substitution without Jinja2"""
        result = template_str
        
        # Find all {{ variable }} patterns
        pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9._]*)\s*\}\}'
        matches = re.findall(pattern, result)
        
        for match in matches:
            # Support nested attribute access like inputs.target_file
            value = self._get_nested_value(context, match)
            if value is not None:
                result = result.replace(f"{{{{ {match} }}}}", str(value))
        
        return result
    
    def _get_nested_value(self, context: Dict[str, Any], key: str) -> Any:
        """Get value from nested dictionary using dot notation"""
        keys = key.split('.')
        value = context
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return None


class WorkflowParser:
    """Parser for workflow YAML files"""
    
    def __init__(self, schema_path: Optional[str] = None):
        self.template_engine = TemplateEngine()
        self.schema = self._load_schema(schema_path)
    
    def _load_schema(self, schema_path: Optional[str]) -> Optional[Dict[str, Any]]:
        """Load workflow schema for validation"""
        if schema_path is None:
            # Use default schema path
            script_dir = os.path.dirname(os.path.abspath(__file__))
            schema_path = os.path.join(script_dir, "../schema/workflow_schema.yaml")
        
        if not os.path.exists(schema_path):
            return None
            
        try:
            with open(schema_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Could not load workflow schema: {e}")
            return None
    
    def parse_workflow(self, workflow_path: str) -> WorkflowDefinition:
        """Parse workflow YAML file into WorkflowDefinition"""
        if not os.path.exists(workflow_path):
            raise WorkflowParseError(f"Workflow file not found: {workflow_path}")
        
        try:
            with open(workflow_path, 'r') as f:
                workflow_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise WorkflowParseError(f"Invalid YAML in {workflow_path}: {e}")
        
        return self.parse_workflow_data(workflow_data, workflow_path)
    
    def parse_workflow_data(self, workflow_data: Dict[str, Any], source_path: str = None) -> WorkflowDefinition:
        """Parse workflow data dictionary into WorkflowDefinition"""
        # Validate against schema if available
        if self.schema:
            try:
                jsonschema.validate(workflow_data, self.schema)
            except jsonschema.ValidationError as e:
                raise WorkflowValidationError(f"Workflow validation error: {e.message}")
        
        # Extract basic workflow info
        workflow = WorkflowDefinition(
            name=workflow_data.get('name'),
            version=workflow_data.get('version'),
            description=workflow_data.get('description'),
            author=workflow_data.get('author'),
            tags=workflow_data.get('tags', []),
            environment=workflow_data.get('environment', {}),
            timeout=workflow_data.get('timeout', 3600),
            retry=workflow_data.get('retry', {}),
            cache=workflow_data.get('cache', {})
        )
        
        # Validate required fields
        if not workflow.name:
            raise WorkflowValidationError("Workflow name is required")
        if not workflow.version:
            raise WorkflowValidationError("Workflow version is required")
        
        # Parse inputs
        inputs_data = workflow_data.get('inputs', {})
        for input_name, input_config in inputs_data.items():
            workflow.inputs[input_name] = WorkflowInput(
                name=input_name,
                type=input_config.get('type'),
                description=input_config.get('description'),
                required=input_config.get('required', False),
                default=input_config.get('default'),
                validation=input_config.get('validation')
            )
        
        # Parse outputs
        outputs_data = workflow_data.get('outputs', {})
        for output_name, output_config in outputs_data.items():
            workflow.outputs[output_name] = WorkflowOutput(
                name=output_name,
                type=output_config.get('type'),
                description=output_config.get('description'),
                from_step=output_config.get('from')
            )
        
        # Parse steps
        steps_data = workflow_data.get('steps', [])
        if not steps_data:
            raise WorkflowValidationError("Workflow must have at least one step")
        
        for step_data in steps_data:
            step = self._parse_step(step_data)
            workflow.steps.append(step)
        
        # Build dependency graph and execution order
        self._build_dependency_graph(workflow)
        self._compute_execution_order(workflow)
        
        return workflow
    
    def _parse_step(self, step_data: Dict[str, Any]) -> WorkflowStep:
        """Parse individual step data"""
        step = WorkflowStep(
            id=step_data.get('id'),
            type=step_data.get('type'),
            name=step_data.get('name'),
            description=step_data.get('description'),
            when=step_data.get('when'),
            timeout=step_data.get('timeout', 300),
            retry=step_data.get('retry', {}),
            cache=step_data.get('cache', {}),
            inputs=step_data.get('inputs', {})
        )
        
        # Validate required fields
        if not step.id:
            raise WorkflowValidationError("Step id is required")
        if not step.type:
            raise WorkflowValidationError(f"Step type is required for step {step.id}")
        
        # Parse dependencies
        depends_on = step_data.get('depends_on', [])
        if isinstance(depends_on, str):
            step.depends_on = [depends_on]
        elif isinstance(depends_on, list):
            step.depends_on = depends_on
        
        # Parse step outputs
        outputs_data = step_data.get('outputs', {})
        for output_name, output_config in outputs_data.items():
            if isinstance(output_config, dict):
                step.outputs[output_name] = StepOutput(
                    name=output_name,
                    type=output_config.get('type'),
                    description=output_config.get('description'),
                    from_source=output_config.get('from')
                )
            else:
                # Simple string output
                step.outputs[output_name] = StepOutput(
                    name=output_name,
                    type="string",
                    from_source=str(output_config)
                )
        
        # Parse step type specific properties
        if step.type == 'shell':
            step.command = step_data.get('command')
            step.working_directory = step_data.get('working_directory')
            step.environment = step_data.get('environment', {})
            if not step.command:
                raise WorkflowValidationError(f"Shell step {step.id} requires command")
        
        elif step.type == 'claude_code':
            step.prompt = step_data.get('prompt')
            step.model = step_data.get('model', 'claude-3-sonnet-20240229')
            step.security_profile = step_data.get('security_profile', 'restricted')
            step.use_cache = step_data.get('use_cache', True)
            step.max_tokens = step_data.get('max_tokens')
            step.temperature = step_data.get('temperature', 0.0)
            if not step.prompt:
                raise WorkflowValidationError(f"Claude code step {step.id} requires prompt")
        
        elif step.type == 'assert':
            step.condition = step_data.get('condition')
            step.message = step_data.get('message')
            step.on_failure = step_data.get('on_failure', 'fail')
            if not step.condition:
                raise WorkflowValidationError(f"Assert step {step.id} requires condition")
        
        elif step.type == 'template':
            step.template = step_data.get('template')
            step.output = step_data.get('output')
            step.engine = step_data.get('engine', 'jinja2')
            if not step.template or not step.output:
                raise WorkflowValidationError(f"Template step {step.id} requires template and output")
        
        elif step.type == 'webhook':
            step.url = step_data.get('url')
            step.method = step_data.get('method', 'POST')
            step.headers = step_data.get('headers', {})
            step.body = step_data.get('body')
            if not step.url:
                raise WorkflowValidationError(f"Webhook step {step.id} requires url")
        
        elif step.type == 'conditional':
            step.condition = step_data.get('condition')
            then_steps_data = step_data.get('then_steps', [])
            else_steps_data = step_data.get('else_steps', [])
            
            if not step.condition:
                raise WorkflowValidationError(f"Conditional step {step.id} requires condition")
            
            # Parse nested steps
            for then_step_data in then_steps_data:
                step.then_steps.append(self._parse_step(then_step_data))
            
            for else_step_data in else_steps_data:
                step.else_steps.append(self._parse_step(else_step_data))
        
        return step
    
    def _build_dependency_graph(self, workflow: WorkflowDefinition):
        """Build step dependency graph"""
        workflow.step_dependency_graph = {}
        step_ids = {step.id for step in workflow.steps}
        
        for step in workflow.steps:
            workflow.step_dependency_graph[step.id] = set()
            
            for dependency in step.depends_on:
                if dependency not in step_ids:
                    raise WorkflowValidationError(
                        f"Step {step.id} depends on unknown step: {dependency}"
                    )
                workflow.step_dependency_graph[step.id].add(dependency)
    
    def _compute_execution_order(self, workflow: WorkflowDefinition):
        """Compute topological execution order for steps"""
        # Kahn's algorithm for topological sorting
        in_degree = {step_id: 0 for step_id in workflow.step_dependency_graph}
        
        # Calculate in-degrees
        for step_id, dependencies in workflow.step_dependency_graph.items():
            for dependency in dependencies:
                in_degree[dependency] = in_degree.get(dependency, 0)
            for dependency in dependencies:
                in_degree[step_id] += 1
        
        # Find nodes with no incoming edges
        queue = [step_id for step_id, degree in in_degree.items() if degree == 0]
        execution_order = []
        
        while queue:
            current = queue.pop(0)
            execution_order.append(current)
            
            # Remove edges from current node
            for step_id in workflow.step_dependency_graph:
                if current in workflow.step_dependency_graph[step_id]:
                    in_degree[step_id] -= 1
                    if in_degree[step_id] == 0:
                        queue.append(step_id)
        
        # Check for cycles
        if len(execution_order) != len(workflow.steps):
            raise WorkflowValidationError("Circular dependency detected in workflow steps")
        
        workflow.execution_order = execution_order
    
    def validate_workflow(self, workflow: WorkflowDefinition) -> List[str]:
        """Validate workflow and return list of issues"""
        issues = []
        
        # Check for duplicate step IDs
        step_ids = [step.id for step in workflow.steps]
        if len(step_ids) != len(set(step_ids)):
            issues.append("Duplicate step IDs found")
        
        # Check workflow outputs reference valid steps
        for output_name, output in workflow.outputs.items():
            if output.from_step:
                # Parse step reference like "step1.outputs.result"
                parts = output.from_step.split('.')
                if len(parts) >= 2:
                    step_id = parts[0]
                    if step_id not in step_ids:
                        issues.append(f"Output {output_name} references unknown step: {step_id}")
        
        # Check step input references
        for step in workflow.steps:
            for input_name, input_value in step.inputs.items():
                if isinstance(input_value, str) and '.' in input_value:
                    # Check if it's a step reference
                    if input_value.startswith('{{') and '.outputs.' in input_value:
                        # Extract step reference from template
                        match = re.search(r'([a-z][a-z0-9_]*).outputs', input_value)
                        if match:
                            referenced_step = match.group(1)
                            if referenced_step not in step_ids:
                                issues.append(f"Step {step.id} references unknown step: {referenced_step}")
        
        return issues
    
    def render_step_templates(self, step: WorkflowStep, context: Dict[str, Any]) -> WorkflowStep:
        """Render templates in step configuration with given context"""
        # Create a copy of the step to avoid modifying original
        step_dict = asdict(step)
        rendered_dict = self._render_dict_templates(step_dict, context)
        
        # Convert back to WorkflowStep
        # Note: This is a simplified approach - in production, you'd want more sophisticated handling
        for key, value in rendered_dict.items():
            if hasattr(step, key):
                setattr(step, key, value)
        
        return step
    
    def _render_dict_templates(self, obj: Any, context: Dict[str, Any]) -> Any:
        """Recursively render templates in dictionary/list structures"""
        if isinstance(obj, dict):
            return {k: self._render_dict_templates(v, context) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._render_dict_templates(item, context) for item in obj]
        elif isinstance(obj, str):
            if '{{' in obj and '}}' in obj:
                try:
                    return self.template_engine.render(obj, context)
                except Exception:
                    # If template rendering fails, return original string
                    return obj
            return obj
        else:
            return obj
    
    def generate_cache_key(self, step: WorkflowStep, context: Dict[str, Any]) -> str:
        """Generate cache key for step execution"""
        cache_config = step.cache
        
        if 'key' in cache_config:
            # Use custom cache key template
            cache_key_template = cache_config['key']
            cache_key = self.template_engine.render(cache_key_template, context)
        else:
            # Generate default cache key based on step configuration
            key_components = [
                step.id,
                step.type,
                json.dumps(step.inputs, sort_keys=True),
                json.dumps(asdict(step), sort_keys=True, default=str)
            ]
            cache_key = hashlib.sha256('|'.join(key_components).encode()).hexdigest()
        
        return cache_key
    
    def export_workflow(self, workflow: WorkflowDefinition, output_path: str):
        """Export workflow definition to YAML file"""
        # Convert workflow back to dictionary format
        workflow_dict = {
            'name': workflow.name,
            'version': workflow.version,
            'description': workflow.description,
            'author': workflow.author,
            'tags': workflow.tags,
            'inputs': {name: asdict(input_def) for name, input_def in workflow.inputs.items()},
            'outputs': {name: asdict(output_def) for name, output_def in workflow.outputs.items()},
            'environment': workflow.environment,
            'timeout': workflow.timeout,
            'retry': workflow.retry,
            'cache': workflow.cache,
            'steps': [asdict(step) for step in workflow.steps]
        }
        
        # Remove None values and empty collections
        workflow_dict = self._clean_dict(workflow_dict)
        
        with open(output_path, 'w') as f:
            yaml.dump(workflow_dict, f, default_flow_style=False, indent=2, sort_keys=False)
    
    def _clean_dict(self, obj: Any) -> Any:
        """Remove None values and empty collections from nested dictionary"""
        if isinstance(obj, dict):
            cleaned = {}
            for k, v in obj.items():
                if v is not None:
                    cleaned_v = self._clean_dict(v)
                    if cleaned_v or cleaned_v == 0 or cleaned_v is False:
                        cleaned[k] = cleaned_v
            return cleaned
        elif isinstance(obj, list):
            return [self._clean_dict(item) for item in obj if item is not None]
        else:
            return obj


def main():
    """CLI interface for workflow parser"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude Code Workflow Parser")
    parser.add_argument("workflow_file", help="Path to workflow YAML file")
    parser.add_argument("--validate", action="store_true", help="Validate workflow only")
    parser.add_argument("--export", help="Export parsed workflow to file")
    parser.add_argument("--schema", help="Path to workflow schema file")
    
    args = parser.parse_args()
    
    try:
        workflow_parser = WorkflowParser(args.schema)
        workflow = workflow_parser.parse_workflow(args.workflow_file)
        
        print(f"✅ Successfully parsed workflow: {workflow.name} v{workflow.version}")
        print(f"   Description: {workflow.description}")
        print(f"   Steps: {len(workflow.steps)}")
        print(f"   Execution order: {' → '.join(workflow.execution_order)}")
        
        if args.validate:
            issues = workflow_parser.validate_workflow(workflow)
            if issues:
                print("\n⚠️  Validation issues:")
                for issue in issues:
                    print(f"   - {issue}")
            else:
                print("✅ Workflow validation passed")
        
        if args.export:
            workflow_parser.export_workflow(workflow, args.export)
            print(f"📄 Exported workflow to: {args.export}")
        
    except (WorkflowParseError, WorkflowValidationError) as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()