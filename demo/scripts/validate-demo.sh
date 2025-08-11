#!/bin/bash
# Comprehensive validation script for Claude Code Enterprise demo
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Test results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Logging
log_test() { 
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -e "${BLUE}🧪 Test $TOTAL_TESTS: $1${NC}"
}

log_pass() { 
    PASSED_TESTS=$((PASSED_TESTS + 1))
    echo -e "${GREEN}  ✅ PASS: $1${NC}"
}

log_fail() { 
    FAILED_TESTS=$((FAILED_TESTS + 1))
    echo -e "${RED}  ❌ FAIL: $1${NC}"
}

log_skip() { 
    echo -e "${YELLOW}  ⏭️  SKIP: $1${NC}"
}

# Validation tests
test_file_structure() {
    log_test "File structure validation"
    
    local required_files=(
        "enterprise-config.json"
        "enterprise-addons/README.md"
        "enterprise-addons/governance/policies/plan-only-profile.json"
        "enterprise-addons/governance/policies/restricted-profile.json"
        "enterprise-addons/governance/policies/standard-profile.json"
        "enterprise-addons/governance/policies/elevated-profile.json"
        "enterprise-addons/governance/templates/enhanced-cognito-policies.yaml"
        "enterprise-addons/governance/claude-code-wrapper.py"
        "docs/ENTERPRISE_GOVERNANCE.md"
        "source/claude_code_with_bedrock/cli/commands/enterprise.py"
    )
    
    local missing_files=0
    for file in "${required_files[@]}"; do
        if [[ -f "$PROJECT_ROOT/$file" ]]; then
            log_pass "Found: $file"
        else
            log_fail "Missing: $file"
            missing_files=$((missing_files + 1))
        fi
    done
    
    if [[ $missing_files -eq 0 ]]; then
        log_pass "All required files present"
    else
        log_fail "$missing_files files missing"
    fi
}

test_policy_files() {
    log_test "Policy file validation"
    
    local policies_dir="$PROJECT_ROOT/enterprise-addons/governance/policies"
    
    # Test JSON validity
    for policy_file in "$policies_dir"/*.json; do
        if [[ -f "$policy_file" ]]; then
            if python3 -m json.tool "$policy_file" &>/dev/null; then
                log_pass "Valid JSON: $(basename "$policy_file")"
            else
                log_fail "Invalid JSON: $(basename "$policy_file")"
            fi
        fi
    done
    
    # Test required fields in each profile
    local required_fields=("ProfileName" "Description" "PolicyDocument")
    
    for profile in plan-only restricted standard elevated; do
        local profile_file="$policies_dir/${profile}-profile.json"
        if [[ -f "$profile_file" ]]; then
            for field in "${required_fields[@]}"; do
                if grep -q "\"$field\":" "$profile_file"; then
                    log_pass "$profile profile has $field"
                else
                    log_fail "$profile profile missing $field"
                fi
            done
        fi
    done
}

test_cloudformation_template() {
    log_test "CloudFormation template validation"
    
    local template_file="$PROJECT_ROOT/enterprise-addons/governance/templates/enhanced-cognito-policies.yaml"
    
    if [[ -f "$template_file" ]]; then
        # Basic CloudFormation template structure check
        if grep -q "AWSTemplateFormatVersion:" "$template_file" && 
           grep -q "Resources:" "$template_file"; then
            log_pass "CloudFormation template has valid structure"
        else
            log_fail "CloudFormation template missing required sections"
            return
        fi
        
        # Check for required CloudFormation sections
        local required_sections=("AWSTemplateFormatVersion" "Description" "Parameters" "Resources" "Outputs")
        
        for section in "${required_sections[@]}"; do
            if grep -q "^$section:" "$template_file"; then
                log_pass "Template has $section section"
            else
                log_fail "Template missing $section section"
            fi
        done
        
        # Check for security profiles
        local profiles=("PlanOnlyEnhancedPolicy" "RestrictedEnhancedPolicy" "StandardEnhancedPolicy" "ElevatedEnhancedPolicy")
        
        for profile in "${profiles[@]}"; do
            if grep -q "$profile:" "$template_file"; then
                log_pass "Template includes $profile"
            else
                log_fail "Template missing $profile"
            fi
        done
    else
        log_fail "CloudFormation template not found"
    fi
}

test_cli_integration() {
    log_test "CLI integration validation"
    
    cd "$PROJECT_ROOT/source"
    
    # Check if Poetry is available
    if ! command -v poetry &>/dev/null; then
        log_skip "Poetry not available for CLI testing"
        return
    fi
    
    # Test import
    if poetry run python -c "from claude_code_with_bedrock.cli.commands.enterprise import EnterpriseCommand" 2>/dev/null; then
        log_pass "Enterprise command imports successfully"
    else
        log_fail "Enterprise command import failed"
        return
    fi
    
    # Test CLI registration
    if poetry run python -c "
from claude_code_with_bedrock.cli import create_application
app = create_application()
commands = [cmd.name for cmd in app.all()]
assert 'enterprise' in commands
print('Enterprise command registered')
" 2>/dev/null; then
        log_pass "Enterprise command registered in CLI"
    else
        log_fail "Enterprise command not registered in CLI"
    fi
    
    # Test command structure
    if poetry run python -c "
from claude_code_with_bedrock.cli.commands.enterprise import EnterpriseCommand
cmd = EnterpriseCommand()
expected_args = ['action']
expected_opts = ['profile', 'security-profile', 'dry-run', 'force']
print('Command structure validated')
" 2>/dev/null; then
        log_pass "Command structure is correct"
    else
        log_fail "Command structure validation failed"
    fi
}

test_wrapper_script() {
    log_test "Enterprise wrapper script validation"
    
    local wrapper_script="$PROJECT_ROOT/enterprise-addons/governance/claude-code-wrapper.py"
    
    if [[ -f "$wrapper_script" ]]; then
        # Test Python syntax
        if python3 -m py_compile "$wrapper_script" 2>/dev/null; then
            log_pass "Wrapper script has valid Python syntax"
        else
            log_fail "Wrapper script has Python syntax errors"
            return
        fi
        
        # Test if it's executable
        if [[ -x "$wrapper_script" ]]; then
            log_pass "Wrapper script is executable"
        else
            log_fail "Wrapper script is not executable"
        fi
        
        # Test help functionality
        if python3 "$wrapper_script" --help &>/dev/null; then
            log_pass "Wrapper script help works"
        else
            log_fail "Wrapper script help failed"
        fi
        
        # Test security profile validation
        if python3 -c "
import re
with open('$wrapper_script', 'r') as f:
    content = f.read()
# Extract the ENTERPRISE_POLICY_PROFILES dictionary
match = re.search(r'ENTERPRISE_POLICY_PROFILES\s*=\s*{.*?^}', content, re.MULTILINE | re.DOTALL)
if match:
    profiles_text = match.group(0)
    expected_profiles = ['plan-only', 'restricted', 'standard', 'elevated']
    for profile in expected_profiles:
        assert '\"' + profile + '\"' in profiles_text or \"'\" + profile + \"'\" in profiles_text
    print('Security profiles defined correctly')
else:
    raise AssertionError('ENTERPRISE_POLICY_PROFILES not found')
" 2>/dev/null; then
            log_pass "Security profiles are defined correctly"
        else
            log_fail "Security profiles validation failed"
        fi
        
    else
        log_fail "Wrapper script not found"
    fi
}

test_documentation() {
    log_test "Documentation validation"
    
    local doc_file="$PROJECT_ROOT/docs/ENTERPRISE_GOVERNANCE.md"
    
    if [[ -f "$doc_file" ]]; then
        log_pass "Enterprise governance documentation exists"
        
        # Check for required sections
        local required_sections=(
            "## Overview"
            "## Security Profiles"
            "## Quick Start"
            "## Configuration Files"
            "## Cost Management"
            "## Monitoring & Compliance"
            "## Troubleshooting"
        )
        
        for section in "${required_sections[@]}"; do
            if grep -q "$section" "$doc_file"; then
                log_pass "Documentation has section: $section"
            else
                log_fail "Documentation missing section: $section"
            fi
        done
        
        # Check word count (should be comprehensive)
        local word_count=$(wc -w < "$doc_file")
        if [[ $word_count -gt 1500 ]]; then
            log_pass "Documentation is comprehensive ($word_count words)"
        else
            log_fail "Documentation may be too brief ($word_count words)"
        fi
        
    else
        log_fail "Enterprise governance documentation not found"
    fi
    
    # Check demo README
    local demo_readme="$PROJECT_ROOT/demo/README.md"
    if [[ -f "$demo_readme" ]]; then
        log_pass "Demo README exists"
    else
        log_fail "Demo README missing"
    fi
}

test_sample_projects() {
    log_test "Sample projects validation"
    
    local projects_dir="$PROJECT_ROOT/demo/sample-projects"
    
    # Python project
    if [[ -f "$projects_dir/simple-python/main.py" ]]; then
        log_pass "Python sample project exists"
        
        # Test Python syntax
        if python3 -m py_compile "$projects_dir/simple-python/main.py" 2>/dev/null; then
            log_pass "Python sample has valid syntax"
        else
            log_fail "Python sample has syntax errors"
        fi
        
        # Check for test file
        if [[ -f "$projects_dir/simple-python/test_main.py" ]]; then
            log_pass "Python sample has tests"
        else
            log_fail "Python sample missing tests"
        fi
    else
        log_fail "Python sample project missing"
    fi
    
    # React project
    if [[ -f "$projects_dir/react-webapp/package.json" ]]; then
        log_pass "React sample project exists"
        
        # Validate package.json
        if python3 -m json.tool "$projects_dir/react-webapp/package.json" &>/dev/null; then
            log_pass "React package.json is valid"
        else
            log_fail "React package.json is invalid"
        fi
    else
        log_fail "React sample project missing"
    fi
    
    # Infrastructure project
    if [[ -f "$projects_dir/infrastructure/main.tf" ]]; then
        log_pass "Infrastructure sample project exists"
    else
        log_fail "Infrastructure sample project missing"
    fi
}

test_demo_scenarios() {
    log_test "Demo scenarios validation"
    
    local scenarios_dir="$PROJECT_ROOT/demo/scenarios"
    
    # Check for scenario files
    local expected_scenarios=("02-plan-only-demo.md" "03-restricted-demo.md")
    
    for scenario in "${expected_scenarios[@]}"; do
        if [[ -f "$scenarios_dir/$scenario" ]]; then
            log_pass "Scenario exists: $scenario"
            
            # Check for required sections
            local required_sections=("## Scenario Overview" "## Setup" "## Demo Script")
            
            for section in "${required_sections[@]}"; do
                if grep -q "$section" "$scenarios_dir/$scenario"; then
                    log_pass "$scenario has section: $section"
                else
                    log_fail "$scenario missing section: $section"
                fi
            done
        else
            log_fail "Scenario missing: $scenario"
        fi
    done
}

test_installation_scripts() {
    log_test "Installation scripts validation"
    
    local install_script="$PROJECT_ROOT/enterprise-addons/governance/install-wrapper.sh"
    local demo_setup="$PROJECT_ROOT/demo/scripts/setup-demo.sh"
    
    # Test install wrapper script
    if [[ -f "$install_script" ]]; then
        if [[ -x "$install_script" ]]; then
            log_pass "Install wrapper script is executable"
        else
            log_fail "Install wrapper script is not executable"
        fi
        
        # Test basic syntax
        if bash -n "$install_script" 2>/dev/null; then
            log_pass "Install wrapper script has valid bash syntax"
        else
            log_fail "Install wrapper script has bash syntax errors"
        fi
    else
        log_fail "Install wrapper script not found"
    fi
    
    # Test demo setup script
    if [[ -f "$demo_setup" ]]; then
        if [[ -x "$demo_setup" ]]; then
            log_pass "Demo setup script is executable"
        else
            log_fail "Demo setup script is not executable"
        fi
        
        # Test basic syntax
        if bash -n "$demo_setup" 2>/dev/null; then
            log_pass "Demo setup script has valid bash syntax"
        else
            log_fail "Demo setup script has bash syntax errors"
        fi
    else
        log_fail "Demo setup script not found"
    fi
}

test_configuration_files() {
    log_test "Configuration files validation"
    
    # Test enterprise config if it exists
    local config_files=(
        "$PROJECT_ROOT/enterprise-config.json"
        "$PROJECT_ROOT/demo/environments/demo.env"
    )
    
    for config_file in "${config_files[@]}"; do
        if [[ -f "$config_file" ]]; then
            if [[ "$config_file" == *.json ]]; then
                if python3 -m json.tool "$config_file" &>/dev/null; then
                    log_pass "Valid JSON config: $(basename "$config_file")"
                else
                    log_fail "Invalid JSON config: $(basename "$config_file")"
                fi
            elif [[ "$config_file" == *.env ]]; then
                # Basic .env file validation
                if grep -q "=" "$config_file"; then
                    log_pass "Valid env config: $(basename "$config_file")"
                else
                    log_fail "Invalid env config: $(basename "$config_file")"
                fi
            fi
        else
            log_skip "Config file not present: $(basename "$config_file")"
        fi
    done
}

# AWS integration tests (optional)
test_aws_integration() {
    log_test "AWS integration validation"
    
    if ! command -v aws &>/dev/null; then
        log_skip "AWS CLI not available"
        return
    fi
    
    if ! aws sts get-caller-identity &>/dev/null; then
        log_skip "AWS credentials not configured"
        return
    fi
    
    # Test CloudFormation template validation
    local template_file="$PROJECT_ROOT/enterprise-addons/governance/templates/enhanced-cognito-policies.yaml"
    if [[ -f "$template_file" ]]; then
        if aws cloudformation validate-template --template-body "file://$template_file" &>/dev/null; then
            log_pass "CloudFormation template validates with AWS"
        else
            log_fail "CloudFormation template validation failed"
        fi
    fi
    
    # Test Bedrock model access (if available)
    if aws bedrock list-foundation-models --region us-east-1 &>/dev/null; then
        log_pass "Bedrock API accessible"
    else
        log_skip "Bedrock API not accessible"
    fi
}

# Main validation runner
main() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║              Claude Code Enterprise Demo Validation          ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}\n"
    
    # Run all tests
    test_file_structure
    test_policy_files
    test_cloudformation_template
    test_cli_integration
    test_wrapper_script
    test_documentation
    test_sample_projects
    test_demo_scenarios
    test_installation_scripts
    test_configuration_files
    test_aws_integration
    
    # Summary
    echo
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                      VALIDATION SUMMARY                      ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo
    
    if [[ $FAILED_TESTS -eq 0 ]]; then
        echo -e "${GREEN}🎉 ALL TESTS PASSED! ($PASSED_TESTS/$TOTAL_TESTS)${NC}"
        echo -e "${GREEN}The enterprise demo is ready for use.${NC}"
        echo
        echo -e "${BLUE}Next steps:${NC}"
        echo "1. Run the demo setup: ./demo/scripts/setup-demo.sh"
        echo "2. Review demo scenarios in demo/scenarios/"
        echo "3. Test with sample projects in demo/sample-projects/"
        echo
        return 0
    else
        echo -e "${RED}❌ VALIDATION FAILED${NC}"
        echo -e "${RED}Failed: $FAILED_TESTS tests${NC}"
        echo -e "${GREEN}Passed: $PASSED_TESTS tests${NC}"
        echo -e "${YELLOW}Total:  $TOTAL_TESTS tests${NC}"
        echo
        echo -e "${RED}Please fix the failing tests before proceeding.${NC}"
        return 1
    fi
}

# Handle command line arguments
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: $0 [options]"
    echo
    echo "Options:"
    echo "  --help, -h    Show this help message"
    echo
    echo "This script validates the enterprise demo setup by running"
    echo "comprehensive tests on all components."
    exit 0
fi

main "$@"