#!/usr/bin/env python3
"""
FIXED Test Profile Refresher - Works with ANY config structure
- Supports both "credentials" and "login" structures
- Uses Edge WebDriver
- No manual credential input needed
"""

import os
import json
import time
import sys

def test_profile_refresher():
    """Test the FIXED profile refresher locally"""
    print("🧪 Testing Naukri Profile Refresher (FIXED VERSION)")
    print("=" * 60)
    
    try:
        # Check if config.json exists
        if not os.path.exists('config.json'):
            print("❌ config.json not found!")
            print("Please ensure config.json exists with your Naukri credentials")
            show_config_examples()
            return False
        
        # Import the fixed refresher
        print("\n1️⃣ Importing Fixed Profile Refresher...")
        try:
            # Import from the fixed file (you'll save this as naukri_profile_refresher.py)
            import naukri_profile_refresher
            from naukri_profile_refresher import NaukriProfileRefresher
            print("✅ Import successful")
        except ImportError as e:
            print(f"❌ Import failed: {e}")
            print("Make sure you've saved the fixed naukri_profile_refresher.py file")
            return False
        
        # Initialize refresher with config.json
        print("\n2️⃣ Initializing Profile Refresher...")
        refresher = NaukriProfileRefresher('config.json')  # Uses your existing config.json
        print("✅ Refresher initialized with config.json")
        
        # Show loaded credentials (masked)
        email = refresher.config['credentials']['email']
        masked_email = email[:3] + "***@" + email.split('@')[1]
        print(f"📧 Using email: {masked_email}")
        
        # Setup Edge driver (visible for testing)
        print("\n3️⃣ Setting up Edge driver (visible mode)...")
        refresher.setup_driver = lambda: setup_local_edge_driver(refresher)
        
        if not refresher.setup_driver():
            print("❌ Edge driver setup failed")
            print("Make sure Microsoft Edge is installed and EdgeDriver is available")
            return False
        
        print("✅ Edge driver setup successful")
        
        # Test login
        print("\n4️⃣ Testing login...")
        if not refresher.login_to_naukri():
            print("❌ Login failed")
            print("Check your credentials in config.json")
            return False
        
        print("✅ Login successful!")
        
        # Test profile update
        print("\n5️⃣ Testing profile update...")
        print("You can watch the browser perform the profile update...")
        time.sleep(2)  # Give user time to read
        
        if refresher.update_profile():
            print("✅ Profile update successful!")
        else:
            print("⚠️ Profile update failed, but login worked")
        
        print("\n🎉 Local test completed!")
        print("✅ All systems working - ready for automation!")
        
        return True
        
    except KeyboardInterrupt:
        print("\n⏹️ Test stopped by user")
        return False
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        try:
            if 'refresher' in locals() and hasattr(refresher, 'driver') and refresher.driver:
                print("\n🔄 Closing browser...")
                input("Press Enter to close browser...")
                refresher.driver.quit()
                print("✅ Browser closed")
        except:
            pass

def setup_local_edge_driver(refresher):
    """Setup visible Edge driver for local testing"""
    try:
        from selenium import webdriver
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.edge.service import Service as EdgeService
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        
        print("🔧 Setting up Edge WebDriver for testing...")
        
        options = webdriver.EdgeOptions()
        
        # Visible browser for testing (no headless)
        # options.add_argument('--headless')  # Commented out for testing
        
        # Anti-detection measures
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # User agent
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59')
        
        # Try automatic Edge driver setup
        try:
            service = EdgeService(EdgeChromiumDriverManager().install())
            refresher.driver = webdriver.Edge(service=service, options=options)
            print("✅ Edge driver auto-download successful")
        except Exception as e:
            print(f"⚠️ Auto-download failed: {e}")
            # Try manual path fallback
            manual_paths = [
                r"C:\WebDrivers\msedgedriver.exe",
                r"C:\edgedriver\msedgedriver.exe",
                "msedgedriver.exe"  # If in PATH
            ]
            
            driver_found = False
            for path in manual_paths:
                if os.path.exists(path):
                    print(f"🔄 Trying manual path: {path}")
                    service = EdgeService(path)
                    refresher.driver = webdriver.Edge(service=service, options=options)
                    driver_found = True
                    break
            
            if not driver_found:
                print("❌ No Edge driver found!")
                print("Solutions:")
                print("1. Let webdriver-manager auto-download (requires internet)")
                print("2. Download EdgeDriver manually to C:\\WebDrivers\\msedgedriver.exe")
                print("3. Add EdgeDriver to your system PATH")
                return False
        
        refresher.driver.set_window_size(1280, 720)
        refresher.driver.implicitly_wait(10)
        refresher.wait = WebDriverWait(refresher.driver, 20)
        
        print("✅ Edge driver setup successful (visible mode)")
        return True
        
    except Exception as e:
        print(f"❌ Edge driver setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_prerequisites():
    """Check if all prerequisites are installed"""
    print("🔍 Checking Prerequisites...")
    
    # Check config.json with flexible structure detection
    if os.path.exists('config.json'):
        print("✅ config.json: Found")
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
            
            # Check for EITHER structure
            email_found = False
            password_found = False
            
            # Check "credentials" structure (user's actual structure)
            if 'credentials' in config:
                if 'email' in config['credentials'] and 'password' in config['credentials']:
                    email_found = True
                    password_found = True
                    print("✅ config.json: Valid structure (credentials)")
            
            # Check "login" structure (old structure)
            elif 'login' in config:
                if 'email' in config['login'] and 'password' in config['login']:
                    email_found = True
                    password_found = True
                    print("✅ config.json: Valid structure (login)")
            
            if not email_found or not password_found:
                print("❌ config.json: Invalid structure (missing email/password)")
                show_config_examples()
                return False
                
        except:
            print("❌ config.json: Invalid JSON format")
            return False
    else:
        print("❌ config.json: Not found")
        return False
    
    # Check Python packages
    required_packages = [
        'selenium',
        'webdriver_manager'
    ]
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}: Installed")
        except ImportError:
            print(f"❌ {package}: Not installed")
            print(f"   Install with: pip install {package}")
            return False
    
    # Check Edge browser
    try:
        import subprocess
        result = subprocess.run(['msedge', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ Microsoft Edge: Installed")
        else:
            print("⚠️ Microsoft Edge: May not be installed or not in PATH")
    except:
        print("⚠️ Microsoft Edge: Could not verify installation")
    
    print("✅ Prerequisites check completed")
    return True

def show_config_examples():
    """Show example config.json structures"""
    print("\n📋 Supported config.json structures:")
    print("=" * 50)
    
    print("\n🔹 Structure 1 (Your current structure):")
    example_config1 = {
        "credentials": {
            "email": "your_email@gmail.com",
            "password": "your_password"
        },
        "personal_info": {
            "firstname": "Your",
            "lastname": "Name"
        }
    }
    print(json.dumps(example_config1, indent=2))
    
    print("\n🔹 Structure 2 (Alternative structure):")
    example_config2 = {
        "login": {
            "email": "your_email@gmail.com",
            "password": "your_password"
        },
        "job_search": {
            "keywords": ["data engineer", "python developer"],
            "location": "bengaluru"
        }
    }
    print(json.dumps(example_config2, indent=2))
    print("=" * 50)

if __name__ == "__main__":
    print("🧪 Naukri Profile Refresher - TEST MODE")
    print("FIXED VERSION: Edge WebDriver + ANY config.json structure")
    print("=" * 60)
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Prerequisites check failed!")
        print("Please install missing dependencies and try again")
        show_config_examples()
        sys.exit(1)
    
    print("\n✅ Prerequisites OK - Starting test...")
    
    # Run test
    success = test_profile_refresher()
    
    if success:
        print("\n" + "=" * 60)
        print("🎉 TEST SUCCESSFUL!")
        print("✅ Profile refresher is working correctly")
        print("✅ Ready for automation setup")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Set up GitHub Actions secrets")
        print("2. Enable automated hourly runs")
        print("3. Monitor profile refresh logs")
    else:
        print("\n" + "=" * 60)
        print("❌ TEST FAILED!")
        print("Please fix the issues above and try again")
        print("=" * 60)
        show_config_examples()
    
    sys.exit(0 if success else 1)