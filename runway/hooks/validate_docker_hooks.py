#!/usr/bin/env python3
"""
Validation script for Docker Compose integration hooks.

This script validates that the Docker Compose hooks are properly configured
and can be imported and executed.
"""

import os
import sys
import yaml
from pathlib import Path

def validate_hook_imports():
    """Validate that hook functions can be imported."""
    print("🔍 Validating hook imports...")
    
    try:
        # Add hooks directory to path
        hooks_dir = Path(__file__).parent
        sys.path.insert(0, str(hooks_dir))
        
        # Import hook functions
        from docker_compose_integration import start_containers_hook, stop_containers_hook
        
        print("✅ Hook functions imported successfully")
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import hook functions: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error importing hooks: {e}")
        return False

def validate_stacks_configuration():
    """Validate that stacks.yml is properly configured with hooks."""
    print("🔍 Validating stacks.yml configuration...")
    
    stacks_file = Path("0_infrastructure/stacks.yml")
    
    if not stacks_file.exists():
        print(f"❌ Stacks file not found: {stacks_file}")
        return False
    
    try:
        with open(stacks_file, 'r') as f:
            stacks_config = yaml.safe_load(f)
        
        # Check for pre_deploy hooks
        pre_deploy = stacks_config.get('pre_deploy', [])
        start_hook_found = False
        
        for hook in pre_deploy:
            if 'docker_compose_integration.start_containers_hook' in hook.get('path', ''):
                start_hook_found = True
                print("✅ Found start_containers_hook in pre_deploy")
                
                # Validate hook arguments
                args = hook.get('args', {})
                required_args = ['compose_file', 'services', 'working_directory']
                
                for arg in required_args:
                    if arg in args:
                        print(f"✅ Found required argument: {arg}")
                    else:
                        print(f"⚠️  Missing argument: {arg}")
                
                break
        
        if not start_hook_found:
            print("❌ start_containers_hook not found in pre_deploy")
            return False
        
        # Check for post_destroy hooks
        post_destroy = stacks_config.get('post_destroy', [])
        stop_hook_found = False
        
        for hook in post_destroy:
            if 'docker_compose_integration.stop_containers_hook' in hook.get('path', ''):
                stop_hook_found = True
                print("✅ Found stop_containers_hook in post_destroy")
                
                # Validate hook arguments
                args = hook.get('args', {})
                expected_args = ['compose_file', 'cleanup', 'working_directory']
                
                for arg in expected_args:
                    if arg in args:
                        print(f"✅ Found expected argument: {arg}")
                    else:
                        print(f"⚠️  Missing argument: {arg}")
                
                break
        
        if not stop_hook_found:
            print("❌ stop_containers_hook not found in post_destroy")
            return False
        
        print("✅ Stacks configuration is valid")
        return True
        
    except yaml.YAMLError as e:
        print(f"❌ Failed to parse stacks.yml: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error validating stacks.yml: {e}")
        return False

def validate_environment_files():
    """Validate that environment files have docker_compose_enabled variable."""
    print("🔍 Validating environment files...")
    
    env_files = [
        ("0_infrastructure/local.env", True),   # Should be enabled
        ("0_infrastructure/dev.env", False),   # Should be disabled
        ("0_infrastructure/prod.env", False),  # Should be disabled
    ]
    
    all_valid = True
    
    for env_file, expected_enabled in env_files:
        env_path = Path(env_file)
        
        if not env_path.exists():
            print(f"❌ Environment file not found: {env_file}")
            all_valid = False
            continue
        
        try:
            with open(env_path, 'r') as f:
                content = f.read()
            
            # Check for docker_compose_enabled variable
            if 'docker_compose_enabled:' in content:
                # Extract the value
                for line in content.split('\n'):
                    if line.strip().startswith('docker_compose_enabled:'):
                        value = line.split(':', 1)[1].strip().lower()
                        expected_value = 'true' if expected_enabled else 'false'
                        
                        if value == expected_value:
                            print(f"✅ {env_file}: docker_compose_enabled = {value} (correct)")
                        else:
                            print(f"⚠️  {env_file}: docker_compose_enabled = {value} (expected {expected_value})")
                        break
            else:
                print(f"❌ {env_file}: docker_compose_enabled variable not found")
                all_valid = False
                
        except Exception as e:
            print(f"❌ Error reading {env_file}: {e}")
            all_valid = False
    
    return all_valid

def validate_docker_compose_file():
    """Validate that docker-compose.yml exists and has expected services."""
    print("🔍 Validating docker-compose.yml...")
    
    compose_file = Path("docker-compose.yml")
    
    if not compose_file.exists():
        print(f"❌ Docker Compose file not found: {compose_file}")
        return False
    
    try:
        with open(compose_file, 'r') as f:
            compose_config = yaml.safe_load(f)
        
        services = compose_config.get('services', {})
        expected_services = [
            'api-public', 'api-internal', 'registration-site', 
            'internal-site', 'sales-dashboard', 'scanner-service', 
            'worker-service', 'report-service'
        ]
        
        found_services = []
        missing_services = []
        
        for service in expected_services:
            if service in services:
                found_services.append(service)
                print(f"✅ Found service: {service}")
            else:
                missing_services.append(service)
                print(f"⚠️  Missing service: {service}")
        
        if missing_services:
            print(f"⚠️  Some expected services are missing: {missing_services}")
        else:
            print("✅ All expected services found in docker-compose.yml")
        
        return len(found_services) > 0
        
    except yaml.YAMLError as e:
        print(f"❌ Failed to parse docker-compose.yml: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error validating docker-compose.yml: {e}")
        return False

def main():
    """Run all validations."""
    print("🚀 Validating Docker Compose integration hooks...\n")
    
    validations = [
        ("Hook Imports", validate_hook_imports),
        ("Stacks Configuration", validate_stacks_configuration),
        ("Environment Files", validate_environment_files),
        ("Docker Compose File", validate_docker_compose_file),
    ]
    
    results = []
    
    for name, validation_func in validations:
        print(f"\n{'='*50}")
        print(f"Validating: {name}")
        print('='*50)
        
        try:
            result = validation_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Validation failed with error: {e}")
            results.append((name, False))
    
    # Summary
    print(f"\n{'='*50}")
    print("VALIDATION SUMMARY")
    print('='*50)
    
    all_passed = True
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name}: {status}")
        if not result:
            all_passed = False
    
    print(f"\n{'='*50}")
    if all_passed:
        print("🎉 All validations passed! Docker Compose hooks are properly configured.")
        return 0
    else:
        print("⚠️  Some validations failed. Please review the issues above.")
        return 1

if __name__ == '__main__':
    exit(main())