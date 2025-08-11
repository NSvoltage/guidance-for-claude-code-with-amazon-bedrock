# Claude Code Enterprise Demo Script

**Duration**: 45-60 minutes  
**Audience**: Enterprise decision makers, security teams, development leaders  
**Goal**: Demonstrate enterprise-ready AI development with comprehensive governance

## Pre-Demo Setup (5 minutes before start)

### Technical Setup
```bash
# Ensure clean environment
cd /Users/namansharma/guidance-for-claude-code-with-amazon-bedrock

# Validate everything is working
./demo/scripts/validate-demo.sh

# Set up demo profiles
export DEMO_USER="demo-presenter@company.com"
export AWS_PROFILE="demo"

# Open browser tabs:
# - AWS CloudWatch Console (dashboards)
# - AWS CloudTrail Console (event history)  
# - AWS Budgets Console (cost tracking)
```

### Presentation Setup
- [ ] Projector/screen ready
- [ ] Terminal with large font (18pt+)
- [ ] Browser bookmarks configured
- [ ] Sample projects ready
- [ ] Backup screenshots prepared

---

## Demo Flow

### Opening (5 minutes)

**Hook**: "What if your development teams could leverage AI safely, with the same governance and compliance controls you have for your production infrastructure?"

**Problem Statement**:
- Development teams want AI assistance (productivity, code quality)
- Security teams need controls and audit trails
- Finance needs cost management and chargeback
- Leadership needs visibility and risk management

**Solution Preview**: "Today I'll show you how Claude Code with Enterprise Governance solves all four concerns."

---

### Part 1: Foundation - Base Infrastructure (10 minutes)

#### 1.1 Show Existing Solution (3 minutes)

**Script**: "We start with the proven AWS Solutions Library foundation:"

```bash
# Show base configuration
cd source
poetry run ccwb status
```

**Key Points**:
- ✅ Enterprise SSO (Okta, Azure AD, Auth0)
- ✅ No long-lived credentials
- ✅ Regional access controls
- ✅ CloudTrail audit trail

#### 1.2 Demo Base Authentication Flow (4 minutes)

**Script**: "Let me show you the seamless developer experience:"

```bash
# Simulate authentication flow
export AWS_PROFILE=demo
aws sts get-caller-identity
```

**Show in browser**: CloudTrail events for authentication

**Key Points**:
- User identity from corporate OIDC
- Temporary AWS credentials (1-8 hours)
- All access logged and attributed
- Works with any AWS SDK/CLI

#### 1.3 Basic Claude Code Usage (3 minutes)

**Script**: "Without enterprise controls, this is what developers get:"

```bash
cd demo/sample-projects/simple-python
# Simulate: claude
# (Show plan: "Help me improve this code")
```

**Key Points**:
- Full functionality
- No restrictions
- No cost controls
- No usage attribution

---

### Part 2: Enterprise Governance Layer (20 minutes)

#### 2.1 Enterprise Configuration (5 minutes)

**Script**: "Now let's add enterprise governance. IT administrators configure policies once:"

```bash
# Show enterprise configuration
poetry run ccwb enterprise configure --security-profile=standard
```

**Walk through**:
- Four security profiles (plan-only → elevated)
- Cost tracking and budgets
- User/team attribute mapping
- Monitoring and dashboards

**Show config file**:
```bash
cat enterprise-config.json
```

#### 2.2 Policy Deployment (3 minutes)

**Script**: "Deploy enhanced policies to existing infrastructure:"

```bash
poetry run ccwb enterprise deploy-policies --dry-run
```

**Show**:
- Non-disruptive enhancement
- CloudFormation integration
- IAM policy extension
- Monitoring setup

#### 2.3 Security Profile Demo: Plan-Only (4 minutes)

**Script**: "For maximum security environments - banks, government, healthcare:"

```bash
cd demo/sample-projects/simple-python
export CLAUDE_ENTERPRISE_PROFILE=plan-only
claude-enterprise --check-policy
```

**Demo prompt**: "Review this code and add comprehensive error handling"

**Key Points**:
- Plan-mode only responses
- No file modifications
- Complete audit trail
- Human oversight required

#### 2.4 Security Profile Demo: Restricted (4 minutes)

**Script**: "For development teams that need productivity with safety:"

```bash
export CLAUDE_ENTERPRISE_PROFILE=restricted
claude-enterprise --check-policy
cd demo/sample-projects/react-webapp
```

**Demo prompts**:
1. "Add TypeScript support to this React app"
2. "Try to download a file with curl" (should be blocked)

**Key Points**:
- Safe development tools allowed
- Dangerous operations blocked
- Clear error messages
- Productivity maintained

#### 2.5 Cost and Monitoring (4 minutes)

**Script**: "Enterprise needs visibility and cost control:"

**Show in browser**:
- CloudWatch dashboard (if available)
- AWS Budgets configuration
- Cost allocation by user/team

```bash
# Show monitoring setup
poetry run ccwb enterprise status
```

**Key Points**:
- Real-time usage monitoring
- Per-user cost attribution
- Budget alerts and controls
- Chargeback reporting

---

### Part 3: Enterprise Value Proposition (8 minutes)

#### 3.1 For Security Teams (2 minutes)

**Script**: "Security teams get enterprise-grade controls:"

- **Zero Trust**: No long-lived credentials, all access logged
- **Granular Control**: Per-user permissions based on OIDC claims
- **Compliance Ready**: SOC2, ISO27001 support built-in
- **Audit Trail**: Every action traceable to specific users

#### 3.2 For Finance/Operations (2 minutes)

**Script**: "Finance gets cost control and visibility:"

- **Budget Controls**: Automatic alerts at 80%, 100% thresholds
- **Chargeback**: Monthly reports by user/team/department  
- **Optimization**: Token usage analytics and caching recommendations
- **Forecasting**: Usage trends and budget planning

#### 3.3 For Development Teams (2 minutes)

**Script**: "Developers get AI assistance without friction:"

- **Seamless SSO**: Use existing corporate credentials
- **Right-sized Permissions**: Appropriate access for role
- **No Credential Management**: Automatic token refresh
- **Performance**: Prompt caching reduces latency and costs

#### 3.4 For Leadership (2 minutes)

**Script**: "Leadership gets risk management and ROI tracking:"

- **Controlled Rollout**: Start with pilots, scale systematically
- **Risk Mitigation**: Multiple safety layers and controls
- **Usage Analytics**: Who's using AI, how, and with what outcomes
- **Competitive Advantage**: AI-powered development at enterprise scale

---

### Part 4: Implementation Path (7 minutes)

#### 4.1 Deployment Options (3 minutes)

**Script**: "Three deployment approaches:"

1. **Pilot Program** (2-4 weeks):
   - Deploy to single team
   - Plan-only or restricted profile
   - Gather feedback and refine

2. **Department Rollout** (1-2 months):
   - Extend to full department
   - Multiple security profiles
   - Cost tracking and optimization

3. **Organization-wide** (3-6 months):
   - All development teams
   - Full governance and compliance
   - Integration with existing systems

#### 4.2 Success Metrics (2 minutes)

**Track**:
- **Adoption**: Daily/Monthly Active Users
- **Productivity**: Code generation, review speeds
- **Security**: Policy violations, incident reduction
- **Cost**: Usage efficiency, budget adherence

#### 4.3 Getting Started (2 minutes)

**Next steps**:
1. **Technical Validation**: Deploy in sandbox environment
2. **Pilot Team Selection**: Choose early adopters
3. **Policy Configuration**: Define organizational security profiles
4. **Training**: Onboard IT administrators and developers

---

### Q&A Session (10-15 minutes)

#### Expected Questions & Answers

**Q**: "How does this integrate with our existing SIEM/monitoring?"  
**A**: "CloudTrail events can be forwarded to any SIEM. We provide standard integrations for Splunk, Sentinel, and QRadar."

**Q**: "What about data sovereignty and compliance?"  
**A**: "All processing uses your chosen AWS regions. Optional PrivateLink keeps traffic private. Bedrock doesn't store or train on your data."

**Q**: "Can policies be customized per team/department?"  
**A**: "Yes. The four base profiles are starting points. You can create custom profiles with specific tool allowlists and access controls."

**Q**: "What's the cost impact?"  
**A**: "Base AWS costs are minimal (Cognito, CloudTrail, CloudWatch). Bedrock usage is pay-per-token. Prompt caching typically saves 30-50% on repeated operations."

**Q**: "How do we handle model updates and new features?"  
**A**: "Policies control which models are available. New features can be enabled per security profile. Updates are backward-compatible."

**Q**: "What if Claude Code becomes unavailable?"  
**A**: "The governance layer is Bedrock-agnostic. It would work with other AI coding tools that support AWS authentication."

---

### Closing (5 minutes)

#### Summary
- **Enterprise-Ready**: Built on proven AWS patterns
- **Security-First**: Multiple layers of controls and monitoring
- **Developer-Friendly**: Seamless experience with existing tools
- **Business Value**: Productivity, compliance, cost control

#### Call to Action
- **Technical Proof**: 30-day pilot program
- **Business Case**: ROI analysis with actual usage data
- **Strategic Planning**: Integration with development roadmap

#### Resources
- **Documentation**: Complete implementation guides
- **Support**: Professional services and training available
- **Community**: Best practices and user forums

---

## Backup Materials

### Screenshots to Prepare
1. CloudWatch dashboard with metrics
2. AWS Budgets configuration and alerts
3. CloudTrail event showing user attribution
4. Policy configuration in AWS IAM console
5. Enterprise config JSON files

### Demo Videos (if live demo fails)
1. Authentication flow working
2. Plan-only mode restricting operations
3. Restricted profile blocking dangerous commands
4. Cost tracking in action

### Technical Deep-dive Backup
- CloudFormation templates
- IAM policies details  
- OTEL collector configuration
- Integration architecture diagrams

---

## Speaker Notes

### Timing Management
- **Hard stops**: Part 1 (15 min), Part 2 (35 min), Part 3 (43 min)
- **Flex time**: Q&A can extend if audience engaged
- **Backup plan**: Skip Part 4 if running long

### Audience Adaptation
- **Security-focused**: Emphasize compliance, audit trails, policy enforcement
- **Developer-focused**: Show productivity benefits, seamless experience
- **Executive-focused**: ROI, risk management, competitive advantage

### Technical Troubleshooting
- Keep backup screenshots ready
- Have pre-recorded demos for critical flows
- Prepare to show configuration files directly if needed