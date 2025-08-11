# Enterprise Governance for Claude Code with Amazon Bedrock

This guide explains how to deploy and manage enterprise governance controls for Claude Code with Amazon Bedrock.

## Overview

The enterprise governance layer adds security, compliance, and cost management capabilities to the base Claude Code with Bedrock solution. It provides:

- **Security Profiles**: Four pre-configured security levels from plan-only to elevated
- **Policy Enforcement**: Automatic enforcement of tool restrictions and access controls
- **Cost Management**: Budgets, alerts, and chargeback reporting
- **Audit & Compliance**: Detailed logging and monitoring for enterprise requirements

## Security Profiles

### Plan-Only Profile
**Use Case**: Compliance-heavy organizations, initial rollouts, high-security environments

**Restrictions**:
- Claude Code operates in plan-mode only (no file writes or shell execution)
- Limited to 4,000 tokens per request
- Only Anthropic Claude 3 models allowed
- No network access

**Environment Variables**:
```bash
CLAUDE_DEFAULT_MODE=plan
CLAUDE_ALLOW_FILE_WRITE=false
CLAUDE_ALLOW_SHELL_EXEC=false
CLAUDE_NETWORK_ACCESS=deny
CLAUDE_MAX_TOKENS=4000
CLAUDE_INTERACTIVE_MODE=false
```

### Restricted Profile
**Use Case**: General development teams, junior developers

**Restrictions**:
- File operations allowed within project directories only
- Shell execution limited to safe development tools
- Limited to 8,000 tokens per request
- Restricted network access
- Explicit allow/deny command lists

**Allowed Commands**: `pytest`, `jest`, `npm`, `pip`, `ruff`, `eslint`, `tsc`, `mypy`, `black`, `git`

**Denied Commands**: `curl`, `wget`, `ssh`, `scp`, `docker`, `kubectl`, `rm`, `sudo`

### Standard Profile  
**Use Case**: Most enterprise development teams

**Restrictions**:
- Full Claude Code functionality with safety guardrails
- Blocks high-risk AWS operations (deleting infrastructure)
- Standard token limits (200,000 tokens)
- Full network access
- Caching enabled

### Elevated Profile
**Use Case**: Platform teams, senior engineers, infrastructure management

**Restrictions**:
- Full Claude Code functionality
- Read-only AWS infrastructure access
- Advanced debugging features
- Still blocks destructive operations for safety

## Quick Start

### 1. Configure Enterprise Policies

```bash
# Interactive configuration
ccwb enterprise configure

# Or specify profile directly
ccwb enterprise configure --security-profile=standard
```

This will prompt you for:
- Security profile selection
- Cost tracking preferences
- Budget amounts and alert emails
- User attribute mapping for chargeback

### 2. Deploy Enhanced Policies

```bash
# Review what will be deployed
ccwb enterprise deploy-policies --dry-run

# Deploy the policies
ccwb enterprise deploy-policies
```

### 3. Verify Deployment

```bash
# Check enterprise status
ccwb enterprise status

# View audit information
ccwb enterprise audit
```

### 4. Use Enterprise Wrapper (Optional)

Instead of calling `claude` directly, use the enterprise wrapper for additional controls:

```bash
# Install the wrapper
cp enterprise-addons/governance/claude-code-wrapper.py /usr/local/bin/claude-enterprise
chmod +x /usr/local/bin/claude-enterprise

# Use with explicit profile
claude-enterprise --security-profile=restricted

# Check policy compliance
claude-enterprise --check-policy
```

## Configuration Files

### Enterprise Configuration (`enterprise-config.json`)

```json
{
  "security_profile": "standard",
  "cost_tracking_enabled": true,
  "user_attribute_mapping_enabled": true,
  "budget_amount": 1000,
  "budget_email": "admin@company.com",
  "existing_identity_pool_id": "us-east-1:12345678-1234-1234-1234-123456789012",
  "existing_bedrock_role_arn": "arn:aws:iam::123456789012:role/BedrockAccessRole",
  "allowed_bedrock_regions": ["us-east-1", "us-west-2"]
}
```

### Profile Environment Variables

Environment variables are automatically set based on the selected security profile:

| Variable | Plan-Only | Restricted | Standard | Elevated |
|----------|-----------|------------|----------|----------|
| `CLAUDE_DEFAULT_MODE` | plan | interactive | interactive | interactive |
| `CLAUDE_ALLOW_FILE_WRITE` | false | true | true | true |
| `CLAUDE_ALLOW_SHELL_EXEC` | false | restricted | true | true |
| `CLAUDE_NETWORK_ACCESS` | deny | restricted | allow | allow |
| `CLAUDE_MAX_TOKENS` | 4000 | 8000 | 200000 | 200000 |
| `CLAUDE_CACHE_ENABLED` | - | - | true | true |
| `CLAUDE_ADVANCED_FEATURES` | - | - | - | true |

## Cost Management

### Budget Configuration

Budgets are automatically configured based on your enterprise settings:

- Monthly budget with configurable amount
- 80% and 100% threshold alerts
- Email notifications to specified addresses
- Integration with AWS Cost Explorer

### Cost Tracking

Enhanced cost tracking provides:

- Per-user cost attribution via session tags
- Team/department chargeback reports  
- Token usage and cost estimation
- Regional cost breakdown

### Chargeback Reports

Monthly chargeback reports include:

- Cost by user/team/department
- Token consumption metrics
- Model usage patterns
- Regional usage distribution

## Monitoring & Compliance

### CloudWatch Dashboards

Enterprise dashboards provide:

- Daily/Monthly Active Users (DAU/MAU)
- Token consumption by profile
- Cost trends and forecasting
- Policy compliance metrics
- Error rates and performance

### Audit Logging

Comprehensive audit trails include:

- All Bedrock API calls via CloudTrail
- User attribution via OIDC token claims
- Policy enforcement actions
- Cost allocation tags
- Session duration tracking

### Compliance Features

- **Data Residency**: Regional controls for Bedrock access
- **Encryption**: All logs and configurations encrypted at rest
- **Retention**: Configurable log retention policies
- **Access Controls**: IAM-based permission boundaries

## Architecture Integration

The enterprise governance layer integrates with existing infrastructure:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   OIDC Provider │    │  Cognito Identity│    │   Amazon        │
│   (Okta/Azure)  │───▶│  Pool (existing) │───▶│   Bedrock       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                        │
                              ▼                        │
┌─────────────────┐    ┌─────────────────┐            │
│  Enhanced IAM   │    │   CloudWatch    │            │
│  Policies       │    │   Dashboards    │◀───────────┘
│  (by Profile)   │    │   (Enterprise)  │
└─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   CloudTrail    │
                       │   Audit Logs    │
                       └─────────────────┘
```

## Troubleshooting

### Common Issues

1. **Policy deployment fails**
   - Check that base infrastructure exists (`ccwb status`)
   - Verify AWS credentials and permissions
   - Ensure CloudFormation limits not exceeded

2. **Users can't access Bedrock**
   - Verify security profile allows the required operations
   - Check regional restrictions in policy
   - Validate Cognito Identity Pool configuration

3. **Cost tracking not working**
   - Ensure `EnableCostTracking` is set to `true`
   - Verify budget creation in AWS Budgets console
   - Check CloudWatch metrics for `ClaudeCode/Enterprise` namespace

### Debug Commands

```bash
# Check enterprise status
ccwb enterprise status

# Verify policy compliance
claude-enterprise --check-policy

# Test AWS credentials
aws sts get-caller-identity

# Check CloudFormation stack
aws cloudformation describe-stacks --stack-name claude-code-enterprise-standard
```

## Migration from Base Deployment

To migrate from a basic Claude Code with Bedrock deployment:

1. **Assess Current Setup**
   ```bash
   ccwb status
   ```

2. **Configure Enterprise Layer**
   ```bash
   ccwb enterprise configure
   ```

3. **Deploy Enhanced Policies**
   ```bash
   ccwb enterprise deploy-policies --dry-run
   ccwb enterprise deploy-policies
   ```

4. **Update End-User Instructions**
   - Distribute new security profile information
   - Update any automation that calls Claude Code
   - Train users on new features and restrictions

The enterprise layer is designed to be non-disruptive - existing deployments continue to work while enhanced controls are gradually applied.

## Security Considerations

- **Principle of Least Privilege**: Each profile provides minimum necessary permissions
- **Defense in Depth**: Multiple layers of controls (IAM, environment variables, wrapper)
- **Auditability**: All actions logged and attributable to specific users
- **Compliance**: Designed for SOC2, ISO27001, and similar frameworks

## Advanced Configuration

### Custom Policy Profiles

Organizations can create custom security profiles by extending the base profiles:

```json
{
  "ProfileName": "custom-devops",
  "Description": "Custom profile for DevOps teams",
  "PolicyDocument": {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "BedrockAccess",
        "Effect": "Allow",
        "Action": ["bedrock:InvokeModel"],
        "Resource": "*",
        "Condition": {
          "StringEquals": {
            "aws:RequestedRegion": ["us-east-1"],
            "aws:PrincipalTag/Team": "DevOps"
          }
        }
      }
    ]
  },
  "EnvironmentVariables": {
    "CLAUDE_CUSTOM_TOOLS": "terraform,kubectl,ansible",
    "CLAUDE_INFRASTRUCTURE_ACCESS": "read-write"
  }
}
```

### Integration with Existing Systems

#### SIEM Integration

Enterprise governance supports integration with Security Information and Event Management (SIEM) systems:

- **Splunk**: Forward CloudTrail logs to Splunk for analysis
- **Sentinel**: Use Azure Sentinel connectors for AWS CloudTrail
- **QRadar**: Configure QRadar DSMs for AWS log ingestion

#### Identity Provider Mapping

Advanced user attribute mapping supports complex organizational structures:

```json
{
  "user_attribute_mapping": {
    "department": "custom:department",
    "cost_center": "custom:cost_center", 
    "security_clearance": "custom:clearance",
    "project_codes": "custom:projects"
  }
}
```

#### CI/CD Pipeline Integration

Integrate Claude Code enterprise controls into existing CI/CD workflows:

```yaml
# GitHub Actions example
- name: Validate with Claude Code Enterprise
  run: |
    export CLAUDE_ENTERPRISE_PROFILE=restricted
    claude-enterprise --check-policy
    claude-enterprise "Review this PR for security issues"
```

### Performance Optimization

#### Prompt Caching Strategies

Maximize cost savings and performance with strategic prompt caching:

1. **Repository Context Caching**: Maintain stable context prefixes for each repository
2. **Team Template Caching**: Cache common patterns and templates used by teams
3. **Workflow State Caching**: Cache intermediate workflow states for replay scenarios

#### Regional Deployment

Deploy enterprise controls across multiple AWS regions:

- Primary region for authentication and governance
- Secondary regions for Bedrock access and caching
- Cross-region replication for audit logs
- Regional cost attribution and budgeting

### Compliance Frameworks

#### SOC 2 Compliance

The enterprise governance layer supports SOC 2 Type 2 compliance:

- **Security**: All access logged and attributed
- **Availability**: Multi-region deployment options  
- **Processing Integrity**: Policy enforcement prevents unauthorized actions
- **Confidentiality**: Encryption at rest and in transit
- **Privacy**: Optional prompt sanitization and retention controls

#### ISO 27001 Support

Key controls for ISO 27001 compliance:

- Access control (A.9): Role-based access via OIDC integration
- Cryptography (A.10): KMS encryption for all sensitive data
- Operations security (A.12): Monitoring and incident response
- Communications security (A.13): Network controls and PrivateLink
- System acquisition (A.14): Secure development lifecycle integration

### Monitoring and Alerting

#### CloudWatch Alarms

Automated alerting for security and operational events:

```yaml
# Cost anomaly detection
CostAnomalyAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmDescription: "Unusual cost patterns detected"
    MetricName: EstimatedCharges
    Threshold: 150
    ComparisonOperator: GreaterThanThreshold
    EvaluationPeriods: 1
```

#### Security Event Monitoring

Real-time monitoring for security events:

- Failed authentication attempts
- Policy violation attempts  
- Unusual usage patterns
- Cross-region access anomalies

### Disaster Recovery

#### Backup and Restore Procedures

Essential backup procedures for enterprise deployments:

1. **Configuration Backup**: Regular snapshots of all policy configurations
2. **Audit Log Archival**: Long-term storage of CloudTrail logs
3. **User State Backup**: Backup of user preferences and team assignments
4. **Infrastructure as Code**: Version-controlled CloudFormation templates

#### Business Continuity Planning

Ensure continuous operation during outages:

- Multi-region deployment strategies
- Offline policy enforcement capabilities  
- Emergency access procedures
- Incident response playbooks

### Troubleshooting Guide

#### Common Issues and Resolutions

**Issue**: Users can't authenticate with OIDC provider
**Resolution**: 
1. Verify OIDC provider configuration
2. Check redirect URIs are correctly configured
3. Validate token claims mapping
4. Review CloudTrail logs for authentication errors

**Issue**: Bedrock access denied errors
**Resolution**:
1. Verify user is in correct OIDC groups
2. Check IAM role trust relationships
3. Validate regional access policies
4. Review session tag propagation

**Issue**: Cost tracking not working
**Resolution**:
1. Verify user attribute mapping is enabled
2. Check CloudTrail is delivering logs
3. Validate cost allocation tags
4. Review AWS Budgets configuration

#### Debug Mode

Enable enhanced logging for troubleshooting:

```bash
export CLAUDE_DEBUG=true
export CLAUDE_LOG_LEVEL=debug
claude-enterprise --check-policy
```

#### Log Analysis

Key log sources for troubleshooting:

- CloudTrail: API calls and authentication events
- CloudWatch Logs: Application logs and errors  
- VPC Flow Logs: Network traffic analysis
- Config: Resource configuration changes

## Support

### Enterprise Support Channels

For enterprise support:
- **Operational Issues**: Review CloudWatch dashboards for real-time metrics
- **Security Incidents**: Check CloudTrail logs for detailed audit information  
- **Compliance Reporting**: Use `ccwb enterprise audit` for automated compliance reports
- **Cost Management**: Monitor AWS Budgets and Cost Explorer for usage optimization
- **Technical Support**: Enterprise customers have access to dedicated support channels

### Community Resources

- **Documentation**: Comprehensive guides and API references
- **Best Practices**: Industry-specific implementation guides
- **Training Materials**: Video tutorials and hands-on workshops
- **User Forums**: Community-driven support and knowledge sharing

### Professional Services

Available professional services for enterprise customers:

- **Implementation Consulting**: Expert guidance for initial deployment
- **Security Assessment**: Comprehensive security review and recommendations
- **Custom Development**: Tailored solutions for unique organizational requirements
- **Training and Certification**: Team training on enterprise features and best practices