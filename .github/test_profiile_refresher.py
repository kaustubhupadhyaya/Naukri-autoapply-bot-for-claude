#!/usr/bin/env python3
"""
Test Profile Refresher Locally - Before Setting Up GitHub Actions
"""

import os
import json
import time
from naukri_profile_refresher import NaukriProfileRefresher

def create_test_config():
    """Create test config file if it doesn't exist"""
    config_files = ['enhanced_config.json', 'config.json']
    
    for config_file in config_files:
        if os.path.exists(config_file):
            print(f"✅ Using existing config: {config_file}")
            return config_file
    
    # Create basic config for testing
    email = input("Enter your Naukri email: ").strip()
    password = input("Enter your Naukri password: ").strip()
    
    test_config = {
        "credentials": {
            "email": email,
            "password": password
        },
        "personal_info": {
            "firstname": "Test",
            "lastname": "User"
        }
    }
    
    with open('test_config.json', 'w') as f:
        json.dump(test_config, f, indent=2)
    
    print("✅ Created test_config.json")
    return 'test_config.json'

def test_profile_refresher():
    """Test the profile refresher locally"""
    print("🧪 Testing Naukri Profile Refresher Locally")
    print("=" * 50)
    
    try:
        # Create/find config
        config_file = create_test_config()
        
        # Initialize refresher
        print("\n1️⃣ Initializing Profile Refresher...")
        refresher = NaukriProfileRefresher(config_file)
        print("✅ Refresher initialized")
        
        # Setup driver (will be visible, not headless)
        print("\n2️⃣ Setting up Chrome driver...")
        # Temporarily modify for local testing (visible browser)
        refresher.setup_driver = lambda: setup_local_driver(refresher)
        
        if not refresher.setup_driver():
            print("❌ Driver setup failed")
            return False
        
        print("✅ Driver setup successful")
        
        # Test login
        print("\n3️⃣ Testing login...")
        if not refresher.login_to_naukri():
            print("❌ Login failed")
            return False
        
        print("✅ Login successful!")
        
        # Test profile update
        print("\n4️⃣ Testing profile update...")
        input("Press Enter to continue with profile update (you can watch the browser)...")
        
        if refresher.update_profile():
            print("✅ Profile update successful!")
        else:
            print("⚠️ Profile update failed, but login worked")
        
        print("\n🎉 Local test completed!")
        print("You can now set up GitHub Actions automation.")
        
        return True
        
    except KeyboardInterrupt:
        print("\n⏹️ Test stopped by user")
        return False
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False
    finally:
        if hasattr(refresher, 'driver') and refresher.driver:
            input("\nPress Enter to close browser...")
            refresher.driver.quit()

def setup_local_driver(refresher):
    """Setup visible driver for local testing"""
    try:
        from selenium import webdriver
        from selenium.webdriver.support.ui import WebDriverWait
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service as ChromeService
        
        options = webdriver.ChromeOptions()
        
        # Local testing - visible browser (no headless)
        # options.add_argument('--headless')  # Commented out for local testing
        
        # Anti-detection measures
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Install and setup Chrome driver
        service = ChromeService(ChromeDriverManager().install())
        refresher.driver = webdriver.Chrome(service=service, options=options)
        
        refresher.driver.set_window_size(1280, 720)
        refresher.driver.implicitly_wait(10)
        refresher.wait = WebDriverWait(refresher.driver, 20)
        
        print("✅ Chrome driver setup successful (visible mode)")
        return True
        
    except Exception as e:
        print(f"❌ Local driver setup failed: {e}")
        return False

def check_prerequisites():
    """Check if all prerequisites are installed"""
    print("🔍 Checking Prerequisites...")
    
    # Check Python packages
    try:
        import selenium
        print(f"✅ Selenium: {selenium.__version__}")
    except ImportError:
        print("❌ Selenium not installed. Run: pip install selenium")
        return False
    
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        print("✅ WebDriver Manager: Available")
    except ImportError:
        print("❌ WebDriver Manager not installed. Run: pip install webdriver-manager")
        return False
    
    # Check Chrome browser
    try:
        import subprocess
        result = subprocess.run(['google-chrome', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"✅ Chrome Browser: {result.stdout.strip()}")
        else:
            print("⚠️ Chrome browser may not be installed")
    except:
        print("⚠️ Could not verify Chrome installation")
    
    print("✅ Prerequisites check completed")
    return True

if __name__ == "__main__":
    print("🔧 Naukri Profile Refresher - Local Test")
    print("=" * 45)
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Prerequisites missing. Install required packages first.")
        exit(1)
    
    # Run test
    print("\n🚀 Starting local test...")
    print("Note: Browser will be VISIBLE so you can see what's happening")
    
    success = test_profile_refresher()
    
    if success:
        print("\n✅ Local test successful! Ready for GitHub Actions setup.")
        print("\nNext steps:")
        print("1. Add files to your GitHub repository")
        print("2. Set up GitHub Secrets")
        print("3. Enable GitHub Actions")
        print("4. Test with manual workflow run")
    else:
        print("\n❌ Local test failed. Check the logs above for issues.")
        print("Fix any issues before setting up GitHub Actions.")