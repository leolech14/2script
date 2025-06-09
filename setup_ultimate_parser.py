#!/usr/bin/env python3
"""
Setup Script for Ultimate Itaú Parser
=====================================

Installs dependencies, validates environment, and sets up configuration.
"""

import subprocess
import sys
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def install_dependencies():
    """Install required dependencies."""
    logger.info("Installing dependencies...")
    
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        logger.info("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to install dependencies: {e}")
        return False

def validate_environment():
    """Validate that the environment is properly set up."""
    logger.info("Validating environment...")
    
    required_modules = ['pdfplumber', 'yaml', 'dateutil']
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        logger.error(f"❌ Missing modules: {missing_modules}")
        return False
    
    logger.info("✅ Environment validation passed")
    return True

def create_sample_config():
    """Create sample configuration if it doesn't exist."""
    config_file = Path("itau_parser_config.yaml")
    
    if config_file.exists():
        logger.info("Configuration file already exists")
        return True
    
    logger.info("Creating sample configuration...")
    
    # Import here to avoid import errors if dependencies aren't installed yet
    try:
        from itau_parser_ultimate import ConfigManager
        config_manager = ConfigManager()
        logger.info("✅ Sample configuration created")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create configuration: {e}")
        return False

def run_basic_test():
    """Run a basic test to ensure everything works."""
    logger.info("Running basic functionality test...")
    
    try:
        from itau_parser_ultimate import ItauParser
        parser = ItauParser()
        logger.info("✅ Basic test passed")
        return True
    except Exception as e:
        logger.error(f"❌ Basic test failed: {e}")
        return False

def main():
    """Main setup function."""
    logger.info("🚀 Setting up Ultimate Itaú Parser")
    logger.info("="*50)
    
    steps = [
        ("Installing dependencies", install_dependencies),
        ("Validating environment", validate_environment), 
        ("Creating configuration", create_sample_config),
        ("Running basic test", run_basic_test)
    ]
    
    for step_name, step_func in steps:
        logger.info(f"\n📋 {step_name}...")
        if not step_func():
            logger.error(f"❌ Setup failed at: {step_name}")
            return 1
    
    logger.info("\n🎉 Setup completed successfully!")
    logger.info("\nNext steps:")
    logger.info("1. Place your Itaú PDF in the current directory")
    logger.info("2. Run: python itau_parser_ultimate.py your_file.pdf")
    logger.info("3. Validate against golden CSV: python golden_validator.py output.csv golden.csv")
    
    return 0

if __name__ == "__main__":
    exit(main())
