# Demo Scenario: Restricted Security Profile

**Target Audience**: Development team leads, engineering managers  
**Duration**: 10-12 minutes  
**Demo Environment**: React webapp project

## Scenario Overview

Demonstrate balanced security for development teams - allows common development tasks while blocking risky operations. Perfect for general development teams.

## Setup Commands

```bash
# Navigate to React demo project  
cd demo/sample-projects/react-webapp

# Set restricted profile
export CLAUDE_ENTERPRISE_PROFILE=restricted

# Verify settings
claude-enterprise --check-policy
```

## Demo Script

### 1. Profile Overview (2 minutes)

**Script**: "The restricted profile balances developer productivity with security controls. It's designed for most development teams."

**Show Policy Details**:
```bash
echo "Security profile: $CLAUDE_ENTERPRISE_PROFILE"
claude-enterprise --check-policy
```

**Highlight**:
- ✅ **Allowed commands**: `pytest`, `npm`, `git`, `eslint`, `tsc`, `mypy`
- ❌ **Denied commands**: `curl`, `wget`, `ssh`, `docker`, `sudo`, `rm -rf`
- ✅ **File operations**: Allowed within project directory
- ⚠️ **Network access**: Restricted to safe operations

### 2. Development Workflow Demo (6 minutes)

**Script**: "Let's walk through a typical development workflow showing how Claude helps while maintaining security boundaries."

**Start Claude**:
```bash
claude-enterprise
```

**Demo Flow** (sequential prompts):

1. **"Help me add TypeScript support to this React app"**
   - Shows file creation/modification
   - Uses allowed commands (`npm`, `tsc`)
   - Demonstrates tool restrictions working

2. **"Create a reusable Button component with proper TypeScript interfaces"**
   - File operations work normally
   - Shows productive development workflow
   - Component creation and testing

3. **"Add unit tests using Jest for the Button component"**
   - Demonstrates allowed testing tools
   - Shows `npm test` execution
   - File creation for test files

4. **"Run the linter and fix any issues found"**
   - Uses allowed `eslint` command
   - Shows automated code fixing
   - Maintains code quality standards

### 3. Security Boundary Testing (3 minutes)

**Script**: "Now let's see how the security boundaries protect against risky operations."

**Test Blocked Operations**:

Try these commands through Claude (they should be blocked):
- **"Download a dependency using curl"** → Should be blocked
- **"Install a system package with sudo"** → Should be blocked  
- **"Connect to production database"** → Should be blocked
- **"Run docker commands"** → Should be blocked

**Show**:
- Clear error messages explaining restrictions
- Alternative safe approaches suggested
- Audit logging of blocked attempts

### 4. Monitoring Integration (1 minute)

**Script**: "All activities are tracked for visibility and compliance."

**Demonstrate**:
- CloudWatch metrics by security profile
- User attribution in logs
- Cost tracking per developer/team
- Usage patterns and optimization suggestions

## Key Messages for Audience

### For Development Teams
- **Productivity**: "Work normally with common development tools"
- **Safety**: "Dangerous operations are automatically prevented"
- **Learning**: "Suggested alternatives for blocked operations"

### For Management  
- **Risk Reduction**: "Developer mistakes can't cause infrastructure damage"
- **Visibility**: "Complete audit trail of all AI-assisted development"
- **Cost Control**: "Built-in usage monitoring and budgets"

### For Security Teams
- **Defense in Depth**: "Multiple layers of protection"
- **Customizable**: "Allow/deny lists can be tailored per team"
- **Auditable**: "Every action logged with user attribution"

## Advanced Scenarios (if time permits)

### Package Management Safety
```bash
# These should work (safe package operations)
claude-enterprise
# "Add lodash dependency to package.json"
# "Update React to latest stable version"

# These should be restricted
# "Install global packages with npm -g"
# "Modify system package repositories"
```

### Git Operations
```bash
# Safe git operations should work
# "Create a feature branch and commit these changes"
# "Generate a good commit message for these changes"

# Risky operations should be blocked
# "Push to production branch"
# "Force push with --force-with-lease"
```

## Troubleshooting

### Common Issues
1. **Commands not blocked**: Check environment variables
2. **Unexpected errors**: Verify policy profile is loaded
3. **Network timeouts**: Show graceful error handling

### Demo Recovery
- Have pre-recorded examples ready
- Keep simple backup examples
- Prepare to show policy JSON directly if needed

## Success Criteria

- ✅ Productive development workflow demonstrated
- ✅ Security restrictions clearly shown
- ✅ Error messages are helpful, not frustrating
- ✅ Audience sees practical value
- ✅ Balance between security and usability evident

## Follow-up Questions

**Q**: "Can the allow/deny lists be customized per team?"  
**A**: "Yes, the policy profiles can be customized. Different teams can have different tool access based on their needs and risk tolerance."

**Q**: "What happens if a developer needs a blocked command for legitimate work?"  
**A**: "They can request elevated permissions temporarily, or the command can be added to the team's allow list through the governance process."

**Q**: "How does this compare to the standard profile?"  
**A**: "Standard profile allows more operations and network access. Restricted is better for teams that need tighter security controls."