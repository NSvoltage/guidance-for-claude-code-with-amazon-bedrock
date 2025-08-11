# Demo Scenario: Plan-Only Security Profile

**Target Audience**: Security teams, compliance officers, risk-averse organizations  
**Duration**: 8-10 minutes  
**Demo Environment**: Simple Python project

## Scenario Overview

Demonstrate the most restrictive security profile where Claude Code operates in plan-mode only, providing maximum security for high-risk environments.

## Setup Commands

```bash
# Navigate to demo project
cd demo/sample-projects/simple-python

# Set plan-only profile
export CLAUDE_ENTERPRISE_PROFILE=plan-only

# Verify profile settings
claude-enterprise --check-policy
```

## Demo Script

### 1. Introduction (2 minutes)

**Script**: "For organizations with strict security requirements - banks, government, healthcare - we have the plan-only profile. This provides maximum security by ensuring Claude never directly modifies code or executes commands."

**Show**:
```bash
echo "Active security profile: $CLAUDE_ENTERPRISE_PROFILE"
claude-enterprise --check-policy
```

**Key Points**:
- ✅ Complete audit trail maintained
- ✅ No file writes allowed  
- ✅ No shell execution
- ✅ Limited to 4,000 tokens per request
- ✅ Only plan-mode responses

### 2. Code Review Demonstration (4 minutes)

**Script**: "Let's see how Claude analyzes code and provides implementation plans without making any changes."

**Demo Commands**:
```bash
# Start Claude in plan-only mode
claude-enterprise
```

**Demo Prompts** (use these sequentially):

1. **"Review this main.py file and suggest improvements"**
   - Shows Claude analyzing code
   - Provides detailed improvement suggestions
   - NO files are modified

2. **"Create comprehensive unit tests for the calculate_statistics function"**  
   - Claude provides complete test plan
   - Shows exact test code to implement
   - User must copy/paste manually

3. **"Add error handling and input validation"**
   - Detailed implementation plan provided
   - Step-by-step instructions
   - Security-conscious approach

### 3. Security Enforcement (2 minutes)

**Script**: "The profile actively prevents any unauthorized operations."

**Demonstration**:
- Try to ask Claude to write files directly → Blocked
- Request shell command execution → Blocked  
- Show environment variable enforcement

**Expected Behavior**:
- Clear error messages when restrictions apply
- All interactions logged for audit
- User maintains complete control

### 4. Compliance Value Proposition (2 minutes)

**Script**: "This profile is designed for regulatory compliance and high-security environments."

**Show**:
- CloudTrail integration (simulated)
- User attribution via OIDC tokens  
- Cost tracking by user/team
- Zero risk of unintended changes

## Audience Q&A Preparation

**Q**: "How do developers actually get work done in plan-only mode?"  
**A**: "Plan-only is ideal for code review, architecture guidance, and learning. Developers get detailed implementation plans they execute manually, ensuring human oversight of every change."

**Q**: "What about productivity impact?"  
**A**: "Plan-only trades some efficiency for maximum security. It's perfect for sensitive codebases where every change must be reviewed and approved."

**Q**: "Can this be bypassed?"  
**A**: "No. The restrictions are enforced at multiple layers - IAM policies, environment variables, and client-side controls. Complete audit trails make any attempted bypass visible."

## Success Criteria

- ✅ Profile restrictions clearly demonstrated
- ✅ Security benefits articulated
- ✅ Compliance value evident
- ✅ Audience understands appropriate use cases
- ✅ No files modified during demo

## Technical Notes

- Have backup examples ready in case of connectivity issues
- Emphasize the "human-in-the-loop" security model
- Show actual CloudWatch/CloudTrail logs if available
- Prepare cost comparison with other profiles