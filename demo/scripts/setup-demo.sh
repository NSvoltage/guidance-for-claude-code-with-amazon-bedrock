#!/bin/bash
# Automated demo setup for Claude Code Enterprise features
set -euo pipefail

# Configuration
DEMO_PROFILE="demo"
DEMO_REGION="us-east-1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Logging functions
log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }
log_step() { echo -e "\n${CYAN}🔧 $1${NC}"; }

# Progress tracking
TOTAL_STEPS=10
CURRENT_STEP=0

progress() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo -e "${CYAN}[${CURRENT_STEP}/${TOTAL_STEPS}] $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    progress "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run 'aws configure'"
        exit 1
    fi
    
    # Check Python and Poetry
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found"
        exit 1
    fi
    
    if ! command -v poetry &> /dev/null; then
        log_warning "Poetry not found, installing..."
        curl -sSL https://install.python-poetry.org | python3 -
    fi
    
    # Check Node.js (for Claude Code)
    if ! command -v npm &> /dev/null; then
        log_warning "Node.js/npm not found - Claude Code installation may fail"
    fi
    
    # Verify we're in the right directory
    if [[ ! -f "$PROJECT_ROOT/source/pyproject.toml" ]]; then
        log_error "Not in the correct project directory"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Install dependencies
install_dependencies() {
    progress "Installing project dependencies..."
    
    cd "$PROJECT_ROOT/source"
    poetry install
    
    log_success "Dependencies installed"
}

# Setup demo configuration
setup_demo_config() {
    progress "Setting up demo configuration..."
    
    # Create demo environment file
    cat > "$PROJECT_ROOT/demo/environments/demo.env" << EOF
# Demo Environment Configuration
AWS_PROFILE=default
AWS_REGION=${DEMO_REGION}
DEMO_PROFILE=${DEMO_PROFILE}
CLAUDE_ENTERPRISE_PROFILE=standard

# Demo-specific settings
CLAUDE_DEFAULT_MODE=interactive
CLAUDE_CACHE_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Cost tracking (demo values)
DEMO_BUDGET_AMOUNT=100
DEMO_BUDGET_EMAIL=demo@example.com
EOF

    log_success "Demo configuration created"
}

# Deploy base infrastructure
deploy_base_infrastructure() {
    progress "Deploying base Claude Code infrastructure..."
    
    cd "$PROJECT_ROOT/source"
    
    # Check if already initialized
    if [[ -f "$HOME/.claude-code-with-bedrock/profiles/${DEMO_PROFILE}/config.yaml" ]]; then
        log_info "Demo profile already exists, skipping init"
    else
        log_info "Initializing demo profile..."
        # For demo, we'll create a minimal config
        poetry run python -c "
from claude_code_with_bedrock.config import Config, Profile
from pathlib import Path
import yaml

# Create demo profile directory
profile_dir = Path.home() / '.claude-code-with-bedrock' / 'profiles' / '${DEMO_PROFILE}'
profile_dir.mkdir(parents=True, exist_ok=True)

# Create minimal config for demo
demo_config = {
    'profile_name': '${DEMO_PROFILE}',
    'aws_region': '${DEMO_REGION}',
    'oidc_provider_type': 'demo',
    'oidc_provider_domain': 'demo.example.com',
    'client_id': 'demo-client-id',
    'monitoring_enabled': True,
    'cost_tracking_enabled': True
}

with open(profile_dir / 'config.yaml', 'w') as f:
    yaml.dump(demo_config, f)

print('Demo profile configuration created')
"
    fi
    
    # For demo purposes, we'll simulate the deployment
    log_warning "Demo mode: Simulating base infrastructure deployment"
    log_info "In a real environment, this would run: poetry run ccwb deploy --profile=${DEMO_PROFILE}"
    
    sleep 2  # Simulate deployment time
    log_success "Base infrastructure ready (simulated)"
}

# Configure enterprise features
configure_enterprise() {
    progress "Configuring enterprise features..."
    
    cd "$PROJECT_ROOT"
    
    # Create enterprise config for demo
    cat > enterprise-config.json << EOF
{
  "security_profile": "standard",
  "cost_tracking_enabled": true,
  "user_attribute_mapping_enabled": true,
  "budget_amount": 100,
  "budget_email": "demo@example.com",
  "existing_identity_pool_id": "us-east-1:demo-pool-id",
  "existing_bedrock_role_arn": "arn:aws:iam::123456789012:role/DemoBedrockRole",
  "allowed_bedrock_regions": ["${DEMO_REGION}"],
  "monitoring_enabled": true,
  "otel_endpoint": "http://localhost:4317"
}
EOF
    
    log_success "Enterprise configuration created"
}

# Test CLI commands
test_cli_commands() {
    progress "Testing enterprise CLI commands..."
    
    cd "$PROJECT_ROOT/source"
    
    # Test enterprise command import
    log_info "Testing CLI imports..."
    poetry run python -c "
import sys
sys.path.insert(0, '.')
try:
    from claude_code_with_bedrock.cli.commands.enterprise import EnterpriseCommand
    print('✅ Enterprise command imports successfully')
except ImportError as e:
    print(f'❌ Import failed: {e}')
    sys.exit(1)
"
    
    # Test help command
    log_info "Testing help command..."
    if poetry run ccwb enterprise --help &> /dev/null; then
        log_success "Enterprise help command works"
    else
        log_warning "Enterprise help command failed (expected in demo mode)"
    fi
}

# Install enterprise wrapper
install_enterprise_wrapper() {
    progress "Installing enterprise wrapper..."
    
    cd "$PROJECT_ROOT/enterprise-addons/governance"
    
    # Install in user directory for demo (avoid sudo)
    log_info "Installing wrapper to user directory..."
    mkdir -p "$HOME/.local/bin"
    cp claude-code-wrapper.py "$HOME/.local/bin/claude-enterprise"
    chmod +x "$HOME/.local/bin/claude-enterprise"
    
    # Create config directory
    mkdir -p "$HOME/.claude-code"
    cp "$PROJECT_ROOT/enterprise-config.json" "$HOME/.claude-code/"
    
    log_success "Enterprise wrapper installed to $HOME/.local/bin/claude-enterprise"
    
    # Check if ~/.local/bin is in PATH
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        log_warning "Add $HOME/.local/bin to your PATH for easy access:"
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
}

# Create sample projects
create_sample_projects() {
    progress "Creating sample projects..."
    
    # Simple Python project
    mkdir -p "$PROJECT_ROOT/demo/sample-projects/simple-python"
    cat > "$PROJECT_ROOT/demo/sample-projects/simple-python/main.py" << 'EOF'
#!/usr/bin/env python3
"""
Simple Python project for Claude Code enterprise demo.
This demonstrates typical development tasks that Claude Code can help with.
"""

import requests
import json
from typing import Dict, List, Optional

def fetch_user_data(user_id: int) -> Optional[Dict]:
    """Fetch user data from JSONPlaceholder API."""
    try:
        response = requests.get(f"https://jsonplaceholder.typicode.com/users/{user_id}")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching user data: {e}")
        return None

def calculate_statistics(numbers: List[float]) -> Dict[str, float]:
    """Calculate basic statistics for a list of numbers."""
    if not numbers:
        return {}
    
    return {
        "mean": sum(numbers) / len(numbers),
        "min": min(numbers),
        "max": max(numbers),
        "count": len(numbers)
    }

def main():
    """Main function demonstrating various operations."""
    print("Claude Code Enterprise Demo - Simple Python Project")
    
    # Demo API call (allowed in standard/elevated profiles)
    user = fetch_user_data(1)
    if user:
        print(f"User: {user['name']} ({user['email']})")
    
    # Demo calculation
    sample_data = [1.5, 2.3, 3.7, 4.1, 5.9, 2.8, 3.4]
    stats = calculate_statistics(sample_data)
    print(f"Statistics: {json.dumps(stats, indent=2)}")

if __name__ == "__main__":
    main()
EOF

    # Create requirements.txt
    cat > "$PROJECT_ROOT/demo/sample-projects/simple-python/requirements.txt" << EOF
requests>=2.31.0
EOF

    # Create test file
    cat > "$PROJECT_ROOT/demo/sample-projects/simple-python/test_main.py" << 'EOF'
import pytest
from main import calculate_statistics

def test_calculate_statistics():
    """Test basic statistics calculation."""
    numbers = [1, 2, 3, 4, 5]
    result = calculate_statistics(numbers)
    
    assert result["mean"] == 3.0
    assert result["min"] == 1
    assert result["max"] == 5
    assert result["count"] == 5

def test_calculate_statistics_empty():
    """Test statistics with empty list."""
    result = calculate_statistics([])
    assert result == {}
EOF

    # React webapp project structure
    mkdir -p "$PROJECT_ROOT/demo/sample-projects/react-webapp"
    cat > "$PROJECT_ROOT/demo/sample-projects/react-webapp/package.json" << 'EOF'
{
  "name": "claude-code-demo-webapp",
  "version": "0.1.0",
  "description": "Demo React webapp for Claude Code enterprise showcase",
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "test": "react-scripts test",
    "eject": "react-scripts eject",
    "lint": "eslint src/",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "eslint": "^8.0.0",
    "typescript": "^5.0.0"
  }
}
EOF

    # Infrastructure project
    mkdir -p "$PROJECT_ROOT/demo/sample-projects/infrastructure"
    cat > "$PROJECT_ROOT/demo/sample-projects/infrastructure/main.tf" << 'EOF'
# Demo Terraform configuration for Claude Code enterprise showcase
# This demonstrates infrastructure code that Claude Code can help with

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region for demo resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "demo"
}

# S3 bucket for demo purposes
resource "aws_s3_bucket" "demo_bucket" {
  bucket = "claude-code-demo-${var.environment}-${random_string.suffix.result}"
  
  tags = {
    Name        = "Claude Code Demo"
    Environment = var.environment
    Purpose     = "Enterprise Demo"
  }
}

resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}

output "bucket_name" {
  description = "Name of the demo S3 bucket"
  value       = aws_s3_bucket.demo_bucket.id
}
EOF

    log_success "Sample projects created"
}

# Create demo scenarios
create_demo_scenarios() {
    progress "Creating demo scenarios..."
    
    # Plan-only demo scenario
    cat > "$PROJECT_ROOT/demo/scenarios/02-plan-only-demo.md" << 'EOF'
# Demo Scenario: Plan-Only Security Profile

**Target Audience**: Security teams, compliance officers, risk-averse organizations

**Duration**: 8-10 minutes

## Scenario Overview

Demonstrate the most restrictive security profile where Claude Code operates in plan-mode only, providing maximum security for high-risk environments.

## Setup

```bash
# Set plan-only profile
export CLAUDE_ENTERPRISE_PROFILE=plan-only
claude-enterprise --check-policy
```

## Demo Script

### 1. Show Profile Configuration (2 min)

**Say**: "For organizations with strict security requirements, we have the plan-only profile."

```bash
# Show active profile
echo "Active profile: $CLAUDE_ENTERPRISE_PROFILE"

# Show policy restrictions
claude-enterprise --check-policy
```

**Key Points**:
- No file writes allowed
- No shell execution
- Maximum 4,000 tokens per request
- Complete audit trail maintained

### 2. Demonstrate Plan-Mode Operation (4 min)

**Say**: "Claude will analyze your code and create implementation plans without making any changes."

Navigate to sample Python project:
```bash
cd demo/sample-projects/simple-python
claude-enterprise
```

**Demo Prompts**:
1. "Review this code and suggest improvements"
2. "Create unit tests for the calculate_statistics function"
3. "Add error handling to the API calls"

**Expected Behavior**:
- Claude provides detailed plans
- No files are modified
- All suggestions are in plan format
- User must manually implement changes

### 3. Show Security Enforcement (2 min)

**Say**: "The profile prevents any unauthorized operations."

Try operations that should be blocked:
- File write attempts (blocked by environment)
- Shell command execution (blocked by policy)
- Network requests (if attempted, limited)

### 4. Compliance Benefits (2 min)

**Say**: "This profile provides complete audit trails and compliance readiness."

Show:
- All interactions logged to CloudTrail
- User attribution via OIDC tokens
- Cost tracking by user/team
- No risk of unintended changes

## Audience Questions to Expect

**Q**: "How do developers actually get work done in plan-only mode?"
**A**: "Plan-only is for high-security review processes. Developers get detailed implementation plans they can follow manually, ensuring human oversight of all changes."

**Q**: "What about productivity impact?"
**A**: "Plan-only trades some efficiency for maximum security. It's ideal for regulated industries or sensitive codebases where every change must be manually reviewed."

## Success Criteria

- ✅ Profile restrictions are clearly demonstrated
- ✅ Security benefits are articulated
- ✅ Compliance value is evident
- ✅ Audience understands the use case
EOF

    # More scenarios...
    cat > "$PROJECT_ROOT/demo/scenarios/03-restricted-demo.md" << 'EOF'
# Demo Scenario: Restricted Security Profile

**Target Audience**: Development team leads, engineering managers

**Duration**: 10-12 minutes

## Scenario Overview

Demonstrate balanced security for development teams - allows common development tasks while blocking risky operations.

## Setup

```bash
export CLAUDE_ENTERPRISE_PROFILE=restricted
claude-enterprise --check-policy
```

## Demo Script

### 1. Profile Overview (2 min)

**Say**: "The restricted profile balances developer productivity with security controls."

Show allowed vs denied commands:
- ✅ Allowed: `pytest`, `npm`, `git`, `eslint`, `tsc`
- ❌ Denied: `curl`, `wget`, `ssh`, `docker`, `sudo`

### 2. Development Workflow Demo (6 min)

Navigate to React project:
```bash
cd demo/sample-projects/react-webapp
claude-enterprise
```

**Demo Flow**:
1. "Help me add TypeScript support to this React app"
2. "Create a component for user profile display"
3. "Add unit tests using Jest"
4. "Run the linter and fix any issues"

**Expected Behavior**:
- File operations work within project directory
- Safe development commands execute
- Risky network/system operations blocked
- Clear error messages when restrictions hit

### 3. Security Boundaries (3 min)

**Say**: "Let's see how the security boundaries work in practice."

Try blocked operations:
```bash
# These should be blocked/restricted
claude-enterprise
# "Download a file from the internet using curl"
# "Install a system package with sudo"
# "Connect to a remote server via SSH"
```

Show error messages and explain the reasoning.

### 4. Monitoring Integration (1 min)

Show how activities are tracked:
- CloudWatch metrics by profile
- User attribution in logs
- Cost tracking per team

## Key Messages

- **Productivity**: Developers can work normally with common tools
- **Security**: Dangerous operations are prevented
- **Visibility**: All actions are logged and monitored
- **Flexibility**: Profile can be customized per team needs
EOF

    log_success "Demo scenarios created"
}

# Validate demo setup
validate_demo() {
    progress "Validating demo setup..."
    
    local validation_errors=0
    
    # Check file structure
    if [[ ! -f "$PROJECT_ROOT/enterprise-config.json" ]]; then
        log_error "Enterprise config not found"
        validation_errors=$((validation_errors + 1))
    fi
    
    # Check sample projects
    if [[ ! -f "$PROJECT_ROOT/demo/sample-projects/simple-python/main.py" ]]; then
        log_error "Sample Python project not created"
        validation_errors=$((validation_errors + 1))
    fi
    
    # Check wrapper installation
    if [[ ! -x "$HOME/.local/bin/claude-enterprise" ]]; then
        log_warning "Enterprise wrapper not executable"
    else
        # Test wrapper
        if "$HOME/.local/bin/claude-enterprise" --check-policy &> /dev/null; then
            log_success "Enterprise wrapper test passed"
        else
            log_warning "Enterprise wrapper test failed (expected without Claude Code)"
        fi
    fi
    
    # Check CLI integration
    cd "$PROJECT_ROOT/source"
    if poetry run python -c "from claude_code_with_bedrock.cli.commands.enterprise import EnterpriseCommand" 2>/dev/null; then
        log_success "CLI integration validated"
    else
        log_error "CLI integration failed"
        validation_errors=$((validation_errors + 1))
    fi
    
    if [[ $validation_errors -eq 0 ]]; then
        log_success "Demo validation passed"
        return 0
    else
        log_error "$validation_errors validation errors found"
        return 1
    fi
}

# Show next steps
show_next_steps() {
    progress "Demo setup complete!"
    
    echo
    log_success "Enterprise Demo Environment Ready"
    echo
    log_info "Demo Resources:"
    echo "  📁 Configuration: $PROJECT_ROOT/enterprise-config.json"
    echo "  📁 Sample Projects: $PROJECT_ROOT/demo/sample-projects/"
    echo "  📁 Demo Scenarios: $PROJECT_ROOT/demo/scenarios/"
    echo "  🔧 Enterprise Wrapper: $HOME/.local/bin/claude-enterprise"
    echo
    log_info "Quick Demo Commands:"
    echo "  # Check policy compliance"
    echo "  claude-enterprise --check-policy"
    echo
    echo "  # Test different profiles"
    echo "  claude-enterprise --security-profile=plan-only"
    echo "  claude-enterprise --security-profile=restricted"
    echo
    echo "  # Enterprise CLI"
    echo "  cd $PROJECT_ROOT/source"
    echo "  poetry run ccwb enterprise status"
    echo
    log_info "Next Steps:"
    echo "  1. Review demo scenarios in: demo/scenarios/"
    echo "  2. Test with sample projects in: demo/sample-projects/"
    echo "  3. Run full validation: demo/scripts/validate-demo.sh"
    echo
}

# Main execution
main() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                Claude Code Enterprise Demo Setup             ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --profile=*)
                DEMO_PROFILE="${1#*=}"
                shift
                ;;
            --region=*)
                DEMO_REGION="${1#*=}"
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [--profile=PROFILE] [--region=REGION]"
                echo "  --profile=PROFILE    Demo profile name (default: demo)"
                echo "  --region=REGION      AWS region (default: us-east-1)"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Execute setup steps
    check_prerequisites
    install_dependencies
    setup_demo_config
    deploy_base_infrastructure
    configure_enterprise
    test_cli_commands
    install_enterprise_wrapper
    create_sample_projects
    create_demo_scenarios
    
    if validate_demo; then
        show_next_steps
    else
        log_error "Demo setup completed with validation errors"
        exit 1
    fi
}

# Error handling
trap 'log_error "Demo setup failed at step $CURRENT_STEP"; exit 1' ERR

# Run main function
main "$@"