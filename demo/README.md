# Claude Code Enterprise Demo & Showcase

This directory contains everything needed to demonstrate the enterprise features of Claude Code with Amazon Bedrock.

## Demo Overview

This showcase demonstrates:
1. **Base Infrastructure**: Standard Claude Code with Bedrock deployment
2. **Enterprise Enhancements**: Four security profiles with real restrictions
3. **Cost Management**: Live budgets, alerts, and monitoring
4. **Compliance Features**: Audit trails and governance controls
5. **End-to-End Workflows**: From IT admin setup to developer usage

## Demo Structure

```
demo/
├── environments/           # Test environment configurations
│   ├── development.env    # Dev environment settings
│   └── production.env     # Production-like settings
├── scenarios/             # Demo scenarios for each profile
│   ├── 01-base-deployment.md
│   ├── 02-plan-only-demo.md
│   ├── 03-restricted-demo.md
│   ├── 04-standard-demo.md
│   └── 05-elevated-demo.md
├── scripts/               # Automation scripts
│   ├── setup-demo.sh     # Complete demo setup
│   ├── cleanup-demo.sh   # Clean up resources
│   └── validate-demo.sh  # Validate all features work
├── sample-projects/       # Test projects for each scenario
│   ├── simple-python/    # Basic Python project
│   ├── react-webapp/     # React application
│   └── infrastructure/   # Infrastructure code
└── presentation/          # Presentation materials
    ├── demo-script.md    # Speaker notes and timing
    ├── screenshots/      # Screenshots for documentation
    └── slides/          # Presentation slides
```

## Quick Start

### Prerequisites

- AWS Account with appropriate permissions
- AWS CLI configured
- Python 3.10+ and Poetry
- Node.js (for Claude Code)

### 1-Command Demo Setup

```bash
# Complete setup and validation
./demo/scripts/setup-demo.sh --profile=demo
```

### Manual Setup

```bash
# 1. Deploy base infrastructure
cd source
poetry run ccwb init --profile=demo
poetry run ccwb deploy --profile=demo

# 2. Configure enterprise features
poetry run ccwb enterprise configure --profile=demo

# 3. Deploy enterprise policies
poetry run ccwb enterprise deploy-policies --profile=demo

# 4. Install enterprise wrapper
cd ../enterprise-addons/governance
sudo ./install-wrapper.sh

# 5. Run validation tests
cd ../../demo
./scripts/validate-demo.sh
```

## Demo Scenarios

### Scenario 1: Plan-Only Profile (High Security)
- **Audience**: Security-conscious organizations, compliance teams
- **Demo**: Show Claude operating in plan-mode only, no file operations
- **Key Points**: Maximum security, audit trail, compliance-ready

### Scenario 2: Restricted Profile (Development Teams)  
- **Audience**: Engineering managers, team leads
- **Demo**: Safe development workflow with tool restrictions
- **Key Points**: Productivity + security, allowlisted commands

### Scenario 3: Standard Profile (Enterprise Default)
- **Audience**: IT administrators, enterprise architects  
- **Demo**: Full functionality with safety guardrails
- **Key Points**: Balanced approach, cost tracking, monitoring

### Scenario 4: Elevated Profile (Platform Teams)
- **Audience**: Senior engineers, platform teams
- **Demo**: Advanced permissions with infrastructure access
- **Key Points**: Power user features, still safe boundaries

## Key Talking Points

### For Security Teams
- **Zero Trust**: No long-lived credentials, all access logged
- **Granular Control**: Per-user permissions based on OIDC claims  
- **Audit Ready**: Complete CloudTrail integration
- **Compliance**: Supports SOC2, ISO27001 requirements

### For Finance/Operations
- **Cost Control**: Per-user/team budgets and alerts
- **Chargeback**: Automated cost attribution
- **Monitoring**: Real-time usage dashboards
- **Optimization**: Token usage optimization recommendations

### For Development Teams
- **Seamless SSO**: Use existing corporate credentials
- **Profile Flexibility**: Right permissions for each user type
- **No Credential Management**: Automatic token refresh
- **Performance**: Prompt caching reduces costs and latency

### For Leadership
- **Enterprise Ready**: Scales from pilot to organization-wide
- **Risk Management**: Progressive rollout with safety controls
- **ROI Tracking**: Usage analytics and productivity metrics
- **Competitive Advantage**: AI-powered development at scale

## Success Metrics

The demo should showcase:
- ✅ **Security**: All access properly restricted by profile
- ✅ **Usability**: Seamless developer experience
- ✅ **Visibility**: Real-time monitoring and alerts  
- ✅ **Cost Control**: Budgets and optimization working
- ✅ **Compliance**: Audit trails and governance

## Demo Timeline

**Total Duration**: 45-60 minutes including Q&A

1. **Introduction** (5 min): Problem statement and solution overview
2. **Base Infrastructure** (10 min): Standard deployment walkthrough
3. **Enterprise Features** (20 min): Security profiles demonstration
4. **Monitoring & Compliance** (10 min): Dashboards and audit capabilities
5. **Q&A and Discussion** (10-15 min): Technical deep dive

## Troubleshooting

Common demo issues and solutions are documented in each scenario guide.

## Customization

To adapt this demo for your organization:
1. Update `environments/` with your specific AWS regions/accounts
2. Modify `scenarios/` to match your use cases
3. Replace sample projects with your actual codebases
4. Customize presentation materials with your branding