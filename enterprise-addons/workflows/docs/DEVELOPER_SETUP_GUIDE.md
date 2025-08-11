# Developer Setup Guide - Secure Workflow Orchestration

This guide helps developers set up, configure, and use the secure workflow orchestration system for enterprise environments.

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Security Profiles](#security-profiles)
5. [Writing Workflows](#writing-workflows)
6. [Development Tips](#development-tips)
7. [Troubleshooting](#troubleshooting)

## 🚀 Quick Start

### 5-Minute Setup

```bash
# 1. Install dependencies
pip install PyYAML simpleeval jinja2

# 2. Create configuration
cd enterprise-addons/workflows
python config/workflow_config.py --create-template ./my-config.yaml

# 3. Test the system
python -c "from engine.secure_workflow_engine import create_secure_workflow_engine; print('✅ Setup successful!')"

# 4. Create your first workflow
cat > my-first-workflow.yaml << EOF
name: hello-world
version: 1.0
description: My first secure workflow
inputs:
  name:
    type: string
    required: true
    default: "World"
steps:
  - id: greet
    type: shell
    command: "echo 'Hello {{ inputs.name }}!'"
    outputs:
      greeting:
        type: string
        from: stdout
outputs:
  message:
    type: string
    from: greet.outputs.greeting
EOF

# 5. Run the workflow (simulation)
python testing/workflow_simulator.py my-first-workflow.yaml --inputs '{"name": "Developer"}'
```

## 🔧 Installation

### Prerequisites

- Python 3.8 or higher
- Required Python packages:
  - `PyYAML` - YAML parsing
  - `simpleeval` - Safe expression evaluation  
  - `Jinja2` - Template rendering
  - `jsonschema` - Workflow validation (optional)

### Standard Installation

```bash
# Install required packages
pip install PyYAML simpleeval jinja2 jsonschema

# Verify installation
python -c "import yaml, simpleeval, jinja2; print('✅ All dependencies installed')"
```

### Development Installation

```bash
# Install with development dependencies
pip install PyYAML simpleeval jinja2 jsonschema pytest pytest-asyncio

# Install pre-commit hooks (optional)
pip install pre-commit
pre-commit install
```

### Docker Installation

```dockerfile
# Use in your Dockerfile
FROM python:3.9-slim

RUN pip install PyYAML simpleeval jinja2 jsonschema

COPY enterprise-addons/workflows /app/workflows
WORKDIR /app/workflows

# Set environment variables
ENV CLAUDE_SECURITY_PROFILE=standard
ENV CLAUDE_WORKSPACE_ROOT=/tmp/workflow-workspace

ENTRYPOINT ["python", "-m", "engine.secure_workflow_engine"]
```

## ⚙️ Configuration

### Configuration File

Create a `workflow-config.yaml` file:

```yaml
# Environment Configuration
environment: development  # development, staging, production
security_profile: standard  # plan_only, restricted, standard, elevated

# Logging and Debugging
enable_detailed_logging: true
enable_debug_mode: true
save_execution_logs: true

# Resource Limits
default_timeout: 3600  # 1 hour
max_cache_entries: 1000
cache_ttl: 3600

# File System
workspace_root: "/tmp/workflow-workspace"
allow_temp_files: true
cleanup_temp_files: true

# Network Access
allow_outbound_requests: false
allowed_domains:
  - "github.com"
  - "pypi.org"
  - "npmjs.com"
```

### Environment Variables

Override configuration with environment variables:

```bash
# Security settings
export CLAUDE_SECURITY_PROFILE=restricted
export CLAUDE_ENABLE_DETAILED_LOGGING=true

# Resource limits  
export CLAUDE_DEFAULT_TIMEOUT=1800  # 30 minutes
export CLAUDE_MAX_MEMORY_MB=2048    # 2GB

# Development features
export CLAUDE_ENABLE_DEBUG=true
export CLAUDE_WORKSPACE_ROOT="/home/developer/workflows"
```

### Configuration Locations

The system looks for configuration files in this order:

1. `~/.claude-code/workflow-config.yaml` (user-specific)
2. `/etc/claude-code/workflow-config.yaml` (system-wide)
3. `./workflow-config.yaml` (project-specific)
4. `./.claude-code.yaml` (project root)

## 🔒 Security Profiles

Choose the right security profile for your use case:

### Plan-Only Profile

**Best for**: Compliance-heavy organizations, security reviews

```python
from engine.secure_workflow_engine import create_secure_workflow_engine

# Maximum security - no execution allowed
engine = create_secure_workflow_engine('plan_only')
```

**Characteristics**:
- ✅ Workflow parsing and validation
- ✅ Plan generation and preview
- ❌ No shell command execution
- ❌ No file operations
- ❌ No network access

### Restricted Profile  

**Best for**: Development teams, safe CI/CD

```python
# Restricted access with safe tools only
engine = create_secure_workflow_engine('restricted')
```

**Characteristics**:
- ✅ Limited shell commands (npm, git, python, pip)
- ✅ File operations in workspace only
- ❌ No network access
- ❌ No dangerous system operations

### Standard Profile

**Best for**: Most enterprise teams

```python
# Balanced security and functionality  
engine = create_secure_workflow_engine('standard')
```

**Characteristics**:
- ✅ Common development tools
- ✅ File operations with validation
- ✅ Limited network access
- ❌ Dangerous operations blocked

### Elevated Profile

**Best for**: Platform teams, DevOps engineers

```python
# Advanced permissions for experienced teams
engine = create_secure_workflow_engine('elevated')
```

**Characteristics**:
- ✅ Most development tools
- ✅ Infrastructure commands (docker, kubectl)
- ✅ Full network access
- ❌ Still blocks destructive operations

## 📝 Writing Workflows

### Basic Workflow Structure

```yaml
name: my-workflow
version: 1.0
description: Description of what this workflow does
author: developer@company.com
tags:
  - development
  - automation

# Define inputs
inputs:
  target_environment:
    type: string
    description: Target deployment environment
    required: true
    default: "staging"
    validation:
      pattern: "^(development|staging|production)$"

# Define workflow steps
steps:
  - id: validate-environment
    type: assert
    description: Ensure target environment is valid
    condition: "inputs.target_environment in ['development', 'staging', 'production']"
    message: "Invalid target environment"
    
  - id: run-tests
    type: shell
    description: Run test suite
    command: "npm test"
    timeout: 900  # 15 minutes
    retry:
      attempts: 2
      delay: 30
    outputs:
      test_results:
        type: string
        from: stdout
        
  - id: build-application
    type: shell  
    description: Build the application
    depends_on: [validate-environment, run-tests]
    command: "npm run build:{{ inputs.target_environment }}"
    working_directory: "./src"
    environment:
      NODE_ENV: "{{ inputs.target_environment }}"
    outputs:
      build_output:
        type: string
        from: stdout

# Define workflow outputs
outputs:
  deployment_ready:
    type: boolean
    description: Whether deployment is ready
    from: build-application.exit_code == 0
  build_summary:
    type: string
    from: build-application.outputs.build_output
```

### Step Types

#### Shell Steps

```yaml
- id: shell-example
  type: shell
  command: "echo 'Hello {{ inputs.name }}'"
  working_directory: "/path/to/workspace"
  environment:
    MY_VAR: "value"
  timeout: 300
  outputs:
    result:
      type: string
      from: stdout
```

#### Assertion Steps

```yaml
- id: assert-example
  type: assert
  condition: "inputs.version != null"
  message: "Version is required"
  on_failure: fail  # fail, warn, continue
```

#### Template Steps

```yaml
- id: template-example
  type: template
  template: |
    # Configuration for {{ inputs.environment }}
    
    server:
      port: {{ inputs.port | default(8080) }}
      host: {{ inputs.host }}
    
    database:
      url: {{ inputs.db_url }}
  output: "config/{{ inputs.environment }}.yaml"
  engine: jinja2
```

#### Conditional Steps

```yaml
- id: conditional-example
  type: conditional
  condition: "inputs.environment == 'production'"
  then_steps:
    - id: production-deploy
      type: shell
      command: "kubectl apply -f production.yaml"
  else_steps:
    - id: staging-deploy
      type: shell
      command: "kubectl apply -f staging.yaml"
```

### Template Variables

Use Jinja2-style templates in your workflows:

```yaml
# Simple variable substitution
command: "echo '{{ inputs.message }}'"

# Default values
command: "npm run {{ inputs.script | default('start') }}"

# Conditional logic
command: "{% if inputs.verbose %}npm run build --verbose{% else %}npm run build{% endif %}"

# Accessing step outputs
command: "echo 'Previous step result: {{ steps.previous-step.outputs.result }}'"

# Built-in variables
command: "echo 'Workflow: {{ workflow.name }} v{{ workflow.version }}'"
command: "echo 'Execution ID: {{ execution_id }}'"
```

### Caching

Enable caching to improve performance:

```yaml
- id: expensive-build
  type: shell
  command: "npm run build"
  cache:
    enabled: true
    ttl: 3600  # 1 hour
    key: "build-{{ inputs.version }}-{{ hash(inputs.dependencies) }}"
```

### Error Handling and Retries

```yaml
- id: flaky-operation
  type: shell
  command: "curl https://api.example.com/data"
  retry:
    attempts: 3
    delay: 10  # seconds
    exponential_backoff: true
  timeout: 60
```

## 🛠️ Development Tips

### 1. Use Development Profile for Testing

```bash
export CLAUDE_SECURITY_PROFILE=elevated
export CLAUDE_ENABLE_DEBUG=true
export CLAUDE_ENABLE_DETAILED_LOGGING=true
```

### 2. Validate Workflows Before Running

```python
from parser.workflow_parser import WorkflowParser

parser = WorkflowParser()
workflow = parser.parse_workflow('my-workflow.yaml')
issues = parser.validate_workflow(workflow)

if issues:
    print("Validation issues:")
    for issue in issues:
        print(f"  - {issue}")
```

### 3. Use Dry-Run Mode

```python
result = await engine.execute_workflow_securely(
    workflow, 
    inputs, 
    security_context,
    dry_run=True  # Only validate, don't execute
)
```

### 4. Debug with Detailed Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now you'll see detailed logs during execution
```

### 5. Test Workflows in Isolation

```python
# Test individual steps
from engine.secure_workflow_engine import SecureWorkflowEngine

engine = SecureWorkflowEngine(security_profile='elevated')

# Create minimal workflow for testing single steps
test_workflow = WorkflowDefinition(
    name="test",
    version="1.0",
    steps=[your_step_to_test]
)
```

### 6. Use Configuration Templates

```bash
# Generate configuration template
python config/workflow_config.py --create-template ./my-config.yaml

# Validate configuration
python config/workflow_config.py --validate ./my-config.yaml

# Show profile details
python config/workflow_config.py --show-profile standard
```

## 🔍 Development Workflow

### 1. Create and Validate

```bash
# Create workflow
vim my-workflow.yaml

# Validate syntax
python parser/workflow_parser.py my-workflow.yaml --validate

# Check security
python security_validation.py --workflow my-workflow.yaml
```

### 2. Test Locally

```bash
# Test with development profile
export CLAUDE_SECURITY_PROFILE=elevated
export CLAUDE_ENABLE_DEBUG=true

python testing/workflow_simulator.py my-workflow.yaml \
  --inputs '{"env": "development"}' \
  --dry-run
```

### 3. Integration Testing

```bash
# Run security tests
python testing/security_tests.py

# Run workflow-specific tests
python -m pytest testing/test_my_workflow.py -v
```

### 4. Deploy to Different Environments

```bash
# Staging deployment
export CLAUDE_SECURITY_PROFILE=standard
export CLAUDE_WORKSPACE_ROOT="/opt/workflows/staging"

# Production deployment  
export CLAUDE_SECURITY_PROFILE=standard
export CLAUDE_ENABLE_DEBUG=false
export CLAUDE_WORKSPACE_ROOT="/opt/workflows/production"
```

## 📚 Best Practices

### 1. Workflow Design

- **Keep steps focused**: Each step should do one thing well
- **Use descriptive IDs**: `validate-input` not `step1`
- **Add descriptions**: Help other developers understand the workflow
- **Handle errors gracefully**: Use appropriate retry and timeout settings

### 2. Security

- **Use least privilege**: Choose the most restrictive profile that works
- **Validate inputs**: Use input validation and assertions
- **Avoid secrets in workflows**: Use secure environment variable injection
- **Review templates**: Template injection is a common vulnerability

### 3. Performance

- **Use caching**: Cache expensive operations appropriately
- **Set reasonable timeouts**: Don't make them too short or too long
- **Limit resource usage**: Be mindful of memory and CPU limits
- **Clean up artifacts**: Remove temporary files when done

### 4. Maintainability

- **Version your workflows**: Use semantic versioning
- **Document dependencies**: List required tools and versions
- **Use consistent patterns**: Establish team conventions
- **Test thoroughly**: Include unit tests for complex workflows

## 📖 Next Steps

- Read the [Troubleshooting Guide](TROUBLESHOOTING.md) for common issues
- Explore [Security Best Practices](SECURITY_BEST_PRACTICES.md)
- Check out [Example Workflows](../examples/) for inspiration
- Review the [API Reference](API_REFERENCE.md) for advanced usage

## 🤝 Getting Help

1. **Check the logs**: Enable detailed logging first
2. **Review configuration**: Validate your config files
3. **Test security profile**: Try a less restrictive profile
4. **Consult documentation**: Check all relevant docs
5. **Ask for help**: Create an issue with logs and configuration

Remember: The system is designed to be secure by default. If something is blocked, it's usually for a good security reason. Consider whether you need elevated permissions or if there's a safer way to accomplish your goal.