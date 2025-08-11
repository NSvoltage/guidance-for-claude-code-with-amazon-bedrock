#!/usr/bin/env python3
"""
Developer-Friendly Configuration Management for Secure Workflow Engine
Provides easy configuration, validation, and environment-specific settings.
"""
import os
import json
import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, asdict, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class SecurityProfileConfig:
    """Configuration for security profiles"""
    name: str
    description: str
    max_concurrent_workflows: int
    max_workflow_duration: int  # seconds
    max_step_duration: int     # seconds  
    max_memory_mb: int
    max_file_size_mb: int
    allow_shell_execution: bool
    allow_file_operations: bool
    allow_network_access: bool
    allowed_commands: List[str] = field(default_factory=list)
    blocked_patterns: List[str] = field(default_factory=list)
    validation_strictness: str = "standard"  # permissive, standard, strict, paranoid


@dataclass
class WorkflowConfig:
    """Complete workflow engine configuration"""
    
    # Environment settings
    environment: str = "development"  # development, staging, production
    
    # Security settings
    security_profile: str = "standard"
    enable_detailed_logging: bool = False
    enable_audit_trail: bool = True
    
    # Resource limits
    default_timeout: int = 3600
    max_cache_entries: int = 1000
    cache_ttl: int = 3600
    
    # File system settings
    workspace_root: str = "/tmp/workflow-workspace"
    allow_temp_files: bool = True
    cleanup_temp_files: bool = True
    
    # Network settings
    allow_outbound_requests: bool = False
    allowed_domains: List[str] = field(default_factory=list)
    
    # Development features
    enable_debug_mode: bool = False
    save_execution_logs: bool = False
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        self._validate_configuration()
    
    def _validate_configuration(self):
        """Validate configuration values"""
        if self.environment not in ['development', 'staging', 'production']:
            raise ValueError(f"Invalid environment: {self.environment}")
            
        if self.default_timeout < 60:
            logger.warning(f"Very low timeout ({self.default_timeout}s) may cause workflow failures")
            
        if self.environment == 'production' and self.enable_debug_mode:
            logger.warning("Debug mode is enabled in production environment")


class ConfigurationManager:
    """Manages workflow configuration from multiple sources"""
    
    def __init__(self):
        self.config_paths = [
            Path.home() / '.claude-code' / 'workflow-config.yaml',
            Path('/etc/claude-code/workflow-config.yaml'),
            Path.cwd() / 'workflow-config.yaml',
            Path.cwd() / '.claude-code.yaml'
        ]
        
        # Default security profiles
        self.default_profiles = {
            'plan_only': SecurityProfileConfig(
                name='plan_only',
                description='Maximum security - plan mode only, no execution',
                max_concurrent_workflows=5,
                max_workflow_duration=1800,  # 30 minutes
                max_step_duration=300,       # 5 minutes
                max_memory_mb=512,
                max_file_size_mb=10,
                allow_shell_execution=False,
                allow_file_operations=False,
                allow_network_access=False,
                validation_strictness='paranoid'
            ),
            'restricted': SecurityProfileConfig(
                name='restricted',
                description='Restricted access for development teams',
                max_concurrent_workflows=10,
                max_workflow_duration=3600,  # 1 hour
                max_step_duration=900,       # 15 minutes
                max_memory_mb=1024,
                max_file_size_mb=50,
                allow_shell_execution=True,
                allow_file_operations=True,
                allow_network_access=False,
                allowed_commands=['npm', 'git', 'python', 'python3', 'pip', 'pytest'],
                validation_strictness='strict'
            ),
            'standard': SecurityProfileConfig(
                name='standard',
                description='Balanced security and functionality for most teams',
                max_concurrent_workflows=25,
                max_workflow_duration=7200,  # 2 hours
                max_step_duration=1800,      # 30 minutes
                max_memory_mb=2048,
                max_file_size_mb=100,
                allow_shell_execution=True,
                allow_file_operations=True,
                allow_network_access=True,
                allowed_commands=['npm', 'git', 'python', 'python3', 'pip', 'pytest', 'docker', 'kubectl'],
                allowed_domains=['github.com', 'pypi.org', 'npmjs.com'],
                validation_strictness='standard'
            ),
            'elevated': SecurityProfileConfig(
                name='elevated',
                description='Advanced permissions for platform teams',
                max_concurrent_workflows=50,
                max_workflow_duration=14400, # 4 hours
                max_step_duration=3600,      # 1 hour
                max_memory_mb=4096,
                max_file_size_mb=500,
                allow_shell_execution=True,
                allow_file_operations=True,
                allow_network_access=True,
                validation_strictness='permissive'
            )
        }
        
        self._config_cache: Optional[WorkflowConfig] = None
    
    def load_config(self, config_file: Optional[str] = None) -> WorkflowConfig:
        """Load configuration from file or environment variables"""
        
        if self._config_cache is not None:
            return self._config_cache
        
        # Start with default configuration
        config_data = {}
        
        # Load from configuration file
        if config_file:
            config_data = self._load_config_file(config_file)
        else:
            # Try to find configuration file
            for config_path in self.config_paths:
                if config_path.exists():
                    config_data = self._load_config_file(str(config_path))
                    logger.info(f"Loaded configuration from {config_path}")
                    break
        
        # Override with environment variables
        env_overrides = self._load_from_environment()
        config_data.update(env_overrides)
        
        # Create configuration object
        config = WorkflowConfig(**config_data)
        
        # Cache the configuration
        self._config_cache = config
        
        return config
    
    def _load_config_file(self, config_file: str) -> Dict[str, Any]:
        """Load configuration from YAML or JSON file"""
        config_path = Path(config_file)
        
        if not config_path.exists():
            logger.warning(f"Configuration file not found: {config_file}")
            return {}
        
        try:
            with open(config_path, 'r') as f:
                if config_path.suffix.lower() in ['.yaml', '.yml']:
                    return yaml.safe_load(f) or {}
                elif config_path.suffix.lower() == '.json':
                    return json.load(f)
                else:
                    logger.warning(f"Unknown configuration file format: {config_file}")
                    return {}
        except Exception as e:
            logger.error(f"Failed to load configuration from {config_file}: {e}")
            return {}
    
    def _load_from_environment(self) -> Dict[str, Any]:
        """Load configuration from environment variables"""
        env_mapping = {
            'CLAUDE_WORKFLOW_ENVIRONMENT': 'environment',
            'CLAUDE_SECURITY_PROFILE': 'security_profile',
            'CLAUDE_ENABLE_DETAILED_LOGGING': ('enable_detailed_logging', bool),
            'CLAUDE_DEFAULT_TIMEOUT': ('default_timeout', int),
            'CLAUDE_MAX_CACHE_ENTRIES': ('max_cache_entries', int),
            'CLAUDE_WORKSPACE_ROOT': 'workspace_root',
            'CLAUDE_ENABLE_DEBUG': ('enable_debug_mode', bool),
            'CLAUDE_ALLOW_NETWORK': ('allow_outbound_requests', bool),
        }
        
        config_data = {}
        
        for env_var, config_key in env_mapping.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                if isinstance(config_key, tuple):
                    key, value_type = config_key
                    try:
                        if value_type == bool:
                            config_data[key] = env_value.lower() in ['true', '1', 'yes', 'on']
                        elif value_type == int:
                            config_data[key] = int(env_value)
                        else:
                            config_data[key] = env_value
                    except (ValueError, TypeError) as e:
                        logger.error(f"Invalid value for {env_var}: {env_value} ({e})")
                else:
                    config_data[config_key] = env_value
        
        return config_data
    
    def get_security_profile(self, profile_name: str) -> SecurityProfileConfig:
        """Get security profile configuration"""
        if profile_name in self.default_profiles:
            return self.default_profiles[profile_name]
        
        # Try to load custom profile
        custom_profile = self._load_custom_profile(profile_name)
        if custom_profile:
            return custom_profile
        
        logger.warning(f"Unknown security profile '{profile_name}', using 'standard'")
        return self.default_profiles['standard']
    
    def _load_custom_profile(self, profile_name: str) -> Optional[SecurityProfileConfig]:
        """Load custom security profile from configuration"""
        # This would load from a custom profiles directory
        # Implementation depends on specific deployment requirements
        return None
    
    def save_config_template(self, output_path: str):
        """Save a configuration template with all options documented"""
        template = {
            'environment': 'development',  # development, staging, production
            'security_profile': 'standard',  # plan_only, restricted, standard, elevated
            'enable_detailed_logging': False,
            'enable_audit_trail': True,
            'default_timeout': 3600,
            'max_cache_entries': 1000,
            'cache_ttl': 3600,
            'workspace_root': '/tmp/workflow-workspace',
            'allow_temp_files': True,
            'cleanup_temp_files': True,
            'allow_outbound_requests': False,
            'allowed_domains': ['github.com', 'pypi.org'],
            'enable_debug_mode': False,
            'save_execution_logs': False,
            
            # You can also define custom security profiles
            'custom_security_profiles': {
                'my_custom_profile': {
                    'name': 'my_custom_profile',
                    'description': 'Custom security profile for my team',
                    'max_concurrent_workflows': 15,
                    'max_workflow_duration': 5400,  # 1.5 hours
                    'max_step_duration': 1200,      # 20 minutes
                    'max_memory_mb': 1536,
                    'max_file_size_mb': 75,
                    'allow_shell_execution': True,
                    'allow_file_operations': True,
                    'allow_network_access': True,
                    'allowed_commands': ['npm', 'git', 'python3', 'pytest'],
                    'allowed_domains': ['github.com', 'internal-registry.company.com'],
                    'validation_strictness': 'standard'
                }
            }
        }
        
        with open(output_path, 'w') as f:
            yaml.dump(template, f, default_flow_style=False, indent=2)
        
        logger.info(f"Configuration template saved to {output_path}")
    
    def validate_configuration(self, config: WorkflowConfig) -> List[str]:
        """Validate configuration and return list of warnings/errors"""
        issues = []
        
        # Check resource limits
        if config.default_timeout < 300:  # 5 minutes
            issues.append("WARNING: Very low default timeout may cause workflow failures")
        
        if config.max_cache_entries < 10:
            issues.append("WARNING: Very low cache limit may hurt performance")
        
        # Check security settings
        if config.environment == 'production':
            if config.enable_debug_mode:
                issues.append("WARNING: Debug mode enabled in production")
            if config.enable_detailed_logging:
                issues.append("INFO: Detailed logging enabled in production (may affect performance)")
        
        # Check workspace settings
        workspace_path = Path(config.workspace_root)
        if not workspace_path.parent.exists():
            issues.append(f"ERROR: Workspace parent directory does not exist: {workspace_path.parent}")
        
        return issues
    
    def get_environment_specific_config(self, environment: str) -> Dict[str, Any]:
        """Get recommended configuration for specific environment"""
        environments = {
            'development': {
                'security_profile': 'elevated',
                'enable_detailed_logging': True,
                'enable_debug_mode': True,
                'default_timeout': 1800,  # 30 minutes
                'save_execution_logs': True,
            },
            'staging': {
                'security_profile': 'standard',
                'enable_detailed_logging': False,
                'enable_debug_mode': False,
                'default_timeout': 3600,  # 1 hour
                'save_execution_logs': True,
            },
            'production': {
                'security_profile': 'standard',
                'enable_detailed_logging': False,
                'enable_debug_mode': False,
                'default_timeout': 7200,  # 2 hours
                'save_execution_logs': False,
            }
        }
        
        return environments.get(environment, environments['production'])


def load_workflow_config(config_file: Optional[str] = None) -> WorkflowConfig:
    """Convenience function to load workflow configuration"""
    manager = ConfigurationManager()
    return manager.load_config(config_file)


def get_security_profile_config(profile_name: str) -> SecurityProfileConfig:
    """Convenience function to get security profile configuration"""
    manager = ConfigurationManager()
    return manager.get_security_profile(profile_name)


def create_config_template(output_path: str = './workflow-config.yaml'):
    """Create a configuration template file"""
    manager = ConfigurationManager()
    manager.save_config_template(output_path)


if __name__ == "__main__":
    # CLI interface for configuration management
    import argparse
    
    parser = argparse.ArgumentParser(description="Workflow Configuration Management")
    parser.add_argument('--create-template', help='Create configuration template file')
    parser.add_argument('--validate', help='Validate configuration file')
    parser.add_argument('--show-profile', help='Show security profile details')
    
    args = parser.parse_args()
    
    if args.create_template:
        create_config_template(args.create_template)
        print(f"Configuration template created: {args.create_template}")
    
    elif args.validate:
        manager = ConfigurationManager()
        config = manager.load_config(args.validate)
        issues = manager.validate_configuration(config)
        
        if issues:
            print("Configuration Issues:")
            for issue in issues:
                print(f"  {issue}")
        else:
            print("Configuration is valid")
    
    elif args.show_profile:
        manager = ConfigurationManager()
        profile = manager.get_security_profile(args.show_profile)
        print(f"Security Profile: {profile.name}")
        print(f"Description: {profile.description}")
        print(f"Configuration:")
        for key, value in asdict(profile).items():
            if key not in ['name', 'description']:
                print(f"  {key}: {value}")
    
    else:
        # Show current configuration
        config = load_workflow_config()
        print("Current Workflow Configuration:")
        print(f"  Environment: {config.environment}")
        print(f"  Security Profile: {config.security_profile}")
        print(f"  Debug Mode: {config.enable_debug_mode}")
        print(f"  Detailed Logging: {config.enable_detailed_logging}")