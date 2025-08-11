# Troubleshooting Guide - Secure Workflow Orchestration

This guide helps developers diagnose and resolve common issues with the secure workflow orchestration system.

## 📋 Quick Diagnosis

### 🔍 Check System Status

```bash
# 1. Verify Python environment
python --version  # Should be 3.8+

# 2. Check dependencies
python -c "import yaml, simpleeval, jinja2; print('✅ Dependencies OK')"

# 3. Test basic functionality
python -c "from engine.secure_workflow_engine import create_secure_workflow_engine; print('✅ Engine OK')"

# 4. Validate configuration
python config/workflow_config.py --validate

# 5. Check security profile
python config/workflow_config.py --show-profile standard
```

### 🚨 Common Error Patterns

| Error Message | Likely Cause | Quick Fix |
|---------------|--------------|-----------|
| `ModuleNotFoundError: No module named 'yaml'` | Missing dependencies | `pip install PyYAML` |
| `SecurityError: Potentially dangerous content` | Security validation failed | Use less restrictive profile or modify input |
| `ResourceExhaustionError: Maximum concurrent workflows` | Too many running workflows | Wait or increase limits |
| `WorkflowTimeoutError: exceeded time limit` | Workflow took too long | Increase timeout or optimize workflow |
| `ValidationError: Workflow validation error` | Invalid workflow YAML | Check YAML syntax and schema |

## 🔧 Installation Issues

### Missing Dependencies

**Problem**: Import errors for required packages

```bash
# Diagnosis
python -c "import yaml"
# ModuleNotFoundError: No module named 'yaml'
```

**Solutions**:

```bash
# Install all required dependencies
pip install PyYAML simpleeval jinja2 jsonschema

# For development
pip install PyYAML simpleeval jinja2 jsonschema pytest pytest-asyncio

# Verify installation
python -c "import yaml, simpleeval, jinja2; print('All dependencies installed')"
```

### Python Version Issues

**Problem**: Compatibility issues with older Python versions

```bash
# Check version
python --version
```

**Solution**: Ensure Python 3.8 or higher:

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.9

# macOS with Homebrew
brew install python@3.9

# Update pip and reinstall packages
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Permission Issues

**Problem**: Cannot write to workspace or configuration directories

**Solution**:

```bash
# Create user-specific config directory
mkdir -p ~/.claude-code

# Set appropriate permissions
chmod 755 ~/.claude-code

# Use user-specific workspace
export CLAUDE_WORKSPACE_ROOT="$HOME/claude-workflows"
mkdir -p "$CLAUDE_WORKSPACE_ROOT"
```

## ⚙️ Configuration Issues

### Configuration Not Loading

**Problem**: System using default configuration instead of your custom config

**Diagnosis**:

```bash
# Check config file locations
ls -la ~/.claude-code/workflow-config.yaml
ls -la /etc/claude-code/workflow-config.yaml
ls -la ./workflow-config.yaml

# Test configuration loading
python -c "
from config.workflow_config import load_workflow_config
config = load_workflow_config()
print(f'Profile: {config.security_profile}')
print(f'Environment: {config.environment}')
"
```

**Solutions**:

```bash
# Create config in correct location
python config/workflow_config.py --create-template ~/.claude-code/workflow-config.yaml

# Validate config syntax
python config/workflow_config.py --validate ~/.claude-code/workflow-config.yaml

# Use environment variables as override
export CLAUDE_SECURITY_PROFILE=standard
export CLAUDE_ENABLE_DEBUG=true
```

### Invalid Configuration Values

**Problem**: Configuration validation errors

```yaml
# Common mistakes in workflow-config.yaml
environment: prod  # Should be 'production'
security_profile: custom  # Should be plan_only, restricted, standard, or elevated
default_timeout: 10  # Too low, should be at least 60
```

**Solution**:

```yaml
# Correct configuration
environment: production  # development, staging, production
security_profile: standard  # plan_only, restricted, standard, elevated
default_timeout: 3600  # At least 60 seconds
max_memory_mb: 1024  # At least 256 MB
```

## 🔒 Security Issues

### Security Validation Failures

**Problem**: Workflows blocked by security validation

```bash
SecurityError: Potentially dangerous content detected in shell command
```

**Diagnosis**:

```python
from engine.secure_workflow_engine import SecureInputValidator

validator = SecureInputValidator.create_for_profile('standard')
try:
    validator.validate_shell_command('rm -rf /')
except SecurityError as e:
    print(f"Blocked: {e}")
```

**Solutions**:

1. **Use safer alternatives**:
```yaml
# Instead of dangerous commands
- command: "rm -rf /tmp/*"  # ❌ Blocked

# Use safer approaches
- command: "find /tmp -name 'temp-*' -delete"  # ✅ Allowed
```

2. **Adjust security profile**:
```bash
# For development only
export CLAUDE_SECURITY_PROFILE=elevated
```

3. **Validate inputs**:
```yaml
steps:
  - id: validate-input
    type: assert
    condition: "inputs.filename matches '^[a-zA-Z0-9_-]+$'"
    message: "Invalid filename"
```

### Template Injection Prevention

**Problem**: Templates blocked for security

```yaml
# This will be blocked
template: "{{ config.__class__.__mro__ }}"  # ❌ Dangerous
```

**Solution**:
```yaml
# Use safe templates
template: "{{ inputs.app_name }}"  # ✅ Safe
template: "{{ workflow.version }}"  # ✅ Safe
```

### Path Traversal Issues

**Problem**: File paths blocked by validation

```yaml
# This will be blocked
output: "../../../etc/passwd"  # ❌ Path traversal
```

**Solution**:
```yaml
# Use workspace-relative paths
output: "config/app.yaml"  # ✅ Safe
working_directory: "./src"  # ✅ Safe
```

## 🚀 Performance Issues

### Workflow Timeouts

**Problem**: Workflows timing out before completion

**Diagnosis**:
```bash
# Check timeout settings
python -c "
from config.workflow_config import load_workflow_config
config = load_workflow_config()
print(f'Default timeout: {config.default_timeout}s')
"
```

**Solutions**:

1. **Increase timeouts**:
```yaml
# In workflow file
steps:
  - id: long-running-task
    timeout: 7200  # 2 hours
```

2. **Optimize workflows**:
```yaml
# Use caching for expensive operations
- id: build-cache
  type: shell
  command: "npm install"
  cache:
    enabled: true
    ttl: 3600
    key: "npm-{{ hash(package.json) }}"
```

3. **Break down large steps**:
```yaml
# Instead of one large step
- id: monolithic-build
  command: "npm install && npm test && npm build"  # ❌ Long-running

# Use multiple steps
- id: install
  command: "npm install"
- id: test
  command: "npm test"
  depends_on: [install]
- id: build
  command: "npm build"
  depends_on: [test]
```

### Memory Issues

**Problem**: Workflows failing due to memory limits

**Diagnosis**:
```bash
# Check memory settings
python -c "
from engine.secure_workflow_engine import SECURITY_CONFIG
print(f'Memory limit: {SECURITY_CONFIG.MAX_MEMORY_MB}MB')
"
```

**Solutions**:

1. **Increase memory limits**:
```bash
export CLAUDE_MAX_MEMORY_MB=2048  # 2GB
```

2. **Optimize memory usage**:
```yaml
# Process files in chunks
- id: process-large-file
  command: "split -l 1000 large-file.txt && for chunk in x*; do process $chunk; done"
```

### Cache Issues

**Problem**: Caching not working or cache corruption

**Solutions**:

1. **Clear cache**:
```python
from engine.secure_workflow_engine import SecureWorkflowEngine
engine = SecureWorkflowEngine()
engine.step_cache.clear()
```

2. **Verify cache configuration**:
```yaml
steps:
  - id: cached-step
    cache:
      enabled: true
      ttl: 3600
      key: "unique-key-{{ inputs.version }}"  # Must be unique
```

## 🔄 Workflow Issues

### YAML Syntax Errors

**Problem**: Invalid YAML in workflow files

```bash
yaml.scanner.ScannerError: mapping values are not allowed here
```

**Solutions**:

1. **Validate YAML syntax**:
```bash
# Use yamllint
pip install yamllint
yamllint my-workflow.yaml

# Or use Python
python -c "import yaml; yaml.safe_load(open('my-workflow.yaml'))"
```

2. **Common YAML mistakes**:
```yaml
# ❌ Incorrect indentation
steps:
- id: step1
type: shell  # Should be indented

# ✅ Correct indentation
steps:
  - id: step1
    type: shell

# ❌ Missing quotes
command: echo Hello World  # Should be quoted if contains spaces

# ✅ Quoted strings
command: "echo 'Hello World'"
```

### Step Dependencies

**Problem**: Dependency resolution errors

```bash
WorkflowValidationError: Step step2 depends on unknown step: step1
```

**Solutions**:

1. **Check step IDs**:
```yaml
steps:
  - id: validate-input  # Referenced by this ID
    type: assert
    
  - id: process-data
    depends_on: [validate-input]  # Must match exactly
```

2. **Verify dependency order**:
```yaml
# Dependencies must be defined before they're used
steps:
  - id: first-step  # Define first
    type: shell
    
  - id: second-step
    depends_on: [first-step]  # Reference after definition
```

### Template Rendering Issues

**Problem**: Template variables not resolving

**Diagnosis**:
```yaml
# Enable debug mode to see template context
steps:
  - id: debug-template
    type: shell
    command: "echo 'Available variables:'; env | grep CLAUDE"
```

**Solutions**:

1. **Check variable names**:
```yaml
# ❌ Wrong variable reference
command: "echo {{ input.name }}"  # Should be inputs.name

# ✅ Correct variable reference
command: "echo {{ inputs.name }}"
```

2. **Use default values**:
```yaml
# Handle missing variables gracefully
command: "echo {{ inputs.name | default('Unknown') }}"
```

3. **Debug template context**:
```python
from engine.secure_workflow_engine import SecureWorkflowEngine
engine = SecureWorkflowEngine()

# Enable detailed logging to see template variables
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🌐 Environment Issues

### Development vs Production

**Problem**: Different behavior between environments

**Solutions**:

1. **Use environment-specific configurations**:
```bash
# Development
export CLAUDE_SECURITY_PROFILE=elevated
export CLAUDE_ENABLE_DEBUG=true

# Production
export CLAUDE_SECURITY_PROFILE=standard
export CLAUDE_ENABLE_DEBUG=false
```

2. **Create environment-specific configs**:
```yaml
# development-config.yaml
environment: development
security_profile: elevated
enable_debug_mode: true

# production-config.yaml
environment: production
security_profile: standard
enable_debug_mode: false
```

### Container Issues

**Problem**: Workflows failing in Docker containers

**Solutions**:

1. **Set proper environment variables**:
```dockerfile
ENV CLAUDE_WORKSPACE_ROOT=/app/workspace
ENV CLAUDE_SECURITY_PROFILE=standard
RUN mkdir -p /app/workspace
```

2. **Handle user permissions**:
```dockerfile
RUN useradd -m workflow-user
USER workflow-user
```

3. **Mount configuration**:
```bash
docker run -v ./workflow-config.yaml:/app/workflow-config.yaml my-workflow-image
```

## 🔍 Debugging Tools

### Enable Debug Mode

```bash
# Environment variable
export CLAUDE_ENABLE_DEBUG=true
export CLAUDE_ENABLE_DETAILED_LOGGING=true

# Configuration file
echo "enable_debug_mode: true" >> workflow-config.yaml
```

### Verbose Logging

```python
import logging

# Enable all debug logs
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Filter specific components
logging.getLogger('engine.secure_workflow_engine').setLevel(logging.DEBUG)
```

### Dry-Run Mode

```python
# Test workflow without execution
result = await engine.execute_workflow_securely(
    workflow,
    inputs,
    security_context,
    dry_run=True
)
```

### Configuration Validation

```bash
# Validate current configuration
python config/workflow_config.py --validate

# Show effective configuration
python -c "
from config.workflow_config import load_workflow_config
import json
config = load_workflow_config()
print(json.dumps(config.__dict__, indent=2, default=str))
"
```

## 📞 Getting Additional Help

### Self-Service Diagnostics

1. **Run system health check**:
```bash
python testing/system_health_check.py
```

2. **Generate diagnostic report**:
```bash
python debugging/generate_diagnostic_report.py > diagnostic-report.txt
```

3. **Test with minimal example**:
```bash
python testing/minimal_workflow_test.py
```

### When to Escalate

Escalate to your platform team when:

- ✅ You've tried the solutions in this guide
- ✅ You have logs and error messages
- ✅ You can reproduce the issue consistently
- ✅ You've tested with a minimal example

### What to Include in Bug Reports

1. **System information**:
   - Python version
   - Operating system
   - Security profile being used

2. **Configuration files** (sanitized of secrets):
   - workflow-config.yaml
   - Environment variables

3. **Error logs**:
   - Full error messages
   - Stack traces
   - Debug logs if available

4. **Minimal reproduction case**:
   - Simplified workflow that shows the issue
   - Exact steps to reproduce

5. **Expected vs actual behavior**:
   - What you expected to happen
   - What actually happened

## 📚 Additional Resources

- [Developer Setup Guide](DEVELOPER_SETUP_GUIDE.md) - Complete setup instructions
- [Security Best Practices](SECURITY_BEST_PRACTICES.md) - Security guidelines
- [API Reference](API_REFERENCE.md) - Technical documentation
- [Example Workflows](../examples/) - Working examples for reference

Remember: Most issues are configuration-related. Start with the basics (dependencies, configuration, permissions) before diving into complex debugging.