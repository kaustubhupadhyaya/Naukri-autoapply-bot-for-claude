#!/usr/bin/env python3
"""
Login Debug Script - Specifically Debug Login Issues
Author: Debug helper for Kaustubh Upadhyaya
Date: July 2025
"""

import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException

def load_config():
    """Load configuration"""
    try:
        with open("config.json", 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        with open("enhanced_config.json", 'r') as f:
            return json.load(f)

def setup_debug_driver():
    """Setup driver with debug options"""
    options = webdriver.EdgeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Keep browser open for manual inspection
    options.add_experimental_option("detach", True)
    
    try:
        driver = webdriver.Edge(options=options)
        return driver
    except Exception as e:
        print(f"❌ Driver setup failed: {e}")
        return None

def debug_login_step_by_step():
    """Debug login process step by step"""
    config = load_config()
    driver = setup_debug_driver()
    
    if not driver:
        return False
    
    try:
        print("🔍 Starting Login Debug Session...")
        print("=" * 50)
        
        # Step 1: Navigate to login page
        print("\n📡 Step 1: Navigating to Naukri login page...")
        driver.get('https://www.naukri.com/nlogin/login')
        time.sleep(5)
        
        print(f"   Current URL: {driver.current_url}")
        print(f"   Page Title: {driver.title}")
        
        # Step 2: Check page elements
        print("\n🔍 Step 2: Analyzing page elements...")
        
        # Look for email field
        email_selectors = [
            '#usernameField',
            'input[placeholder*="email" i]',
            'input[type="email"]',
            'input[name="email"]'
        ]
        
        email_field = None
        for selector in email_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    email_field = elements[0]
                    print(f"   ✅ Email field found: {selector}")
                    print(f"      Visible: {email_field.is_displayed()}")
                    print(f"      Enabled: {email_field.is_enabled()}")
                    break
            except:
                continue
        
        if not email_field:
            print("   ❌ Email field not found!")
            # Show all input fields for debugging
            all_inputs = driver.find_elements(By.TAG_NAME, 'input')
            print(f"   📋 Found {len(all_inputs)} input fields:")
            for i, inp in enumerate(all_inputs):
                print(f"      {i+1}. Type: {inp.get_attribute('type')}, "
                      f"ID: {inp.get_attribute('id')}, "
                      f"Name: {inp.get_attribute('name')}, "
                      f"Placeholder: {inp.get_attribute('placeholder')}")
            return False
        
        # Look for password field
        password_selectors = [
            '#passwordField',
            'input[type="password"]',
            'input[name="password"]'
        ]
        
        password_field = None
        for selector in password_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    password_field = elements[0]
                    print(f"   ✅ Password field found: {selector}")
                    print(f"      Visible: {password_field.is_displayed()}")
                    print(f"      Enabled: {password_field.is_enabled()}")
                    break
            except:
                continue
        
        if not password_field:
            print("   ❌ Password field not found!")
            return False
        
        # Step 3: Fill credentials
        print("\n✏️ Step 3: Filling credentials...")
        
        try:
            email_field.clear()
            email_field.send_keys(config['credentials']['email'])
            print(f"   ✅ Email entered: {config['credentials']['email']}")
            time.sleep(2)
            
            password_field.clear()
            password_field.send_keys(config['credentials']['password'])
            print(f"   ✅ Password entered: {'*' * len(config['credentials']['password'])}")
            time.sleep(2)
            
        except Exception as e:
            print(f"   ❌ Error filling credentials: {e}")
            return False
        
        # Step 4: Find login button
        print("\n🔘 Step 4: Looking for login button...")
        
        login_selectors = [
            "//button[@type='submit']",
            "//button[contains(text(), 'Login')]",
            "//input[@type='submit']",
            ".loginButton"
        ]
        
        login_button = None
        for selector in login_selectors:
            try:
                if selector.startswith('//'):
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                if elements:
                    login_button = elements[0]
                    print(f"   ✅ Login button found: {selector}")
                    print(f"      Text: {login_button.text}")
                    print(f"      Visible: {login_button.is_displayed()}")
                    print(f"      Enabled: {login_button.is_enabled()}")
                    break
            except:
                continue
        
        if not login_button:
            print("   ❌ Login button not found!")
            # Show all buttons for debugging
            all_buttons = driver.find_elements(By.TAG_NAME, 'button')
            print(f"   📋 Found {len(all_buttons)} buttons:")
            for i, btn in enumerate(all_buttons):
                print(f"      {i+1}. Text: '{btn.text}', Type: {btn.get_attribute('type')}")
            return False
        
        # Step 5: Attempt login
        print("\n🚀 Step 5: Attempting login...")
        input("Press Enter to click login button (you can inspect the page manually first)...")
        
        try:
            login_button.click()
            print("   ✅ Login button clicked")
        except Exception as e:
            print(f"   ⚠️ Regular click failed, trying JavaScript click: {e}")
            try:
                driver.execute_script("arguments[0].click();", login_button)
                print("   ✅ JavaScript click successful")
            except Exception as e2:
                print(f"   ❌ JavaScript click also failed: {e2}")
                return False
        
        # Step 6: Wait and check result
        print("\n⏱️ Step 6: Waiting for login to complete...")
        time.sleep(8)
        
        print(f"   Current URL: {driver.current_url}")
        print(f"   Page Title: {driver.title}")
        
        # Check for success indicators
        success_indicators = [
            '.nI-gNb-drawer__icon',
            '.view-profile-wrapper',
            '.user-name'
        ]
        
        login_successful = False
        for indicator in success_indicators:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, indicator)
                if elements and any(el.is_displayed() for el in elements):
                    print(f"   ✅ Login success indicator found: {indicator}")
                    login_successful = True
                    break
            except:
                continue
        
        # Check URL
        if 'nlogin' not in driver.current_url.lower() and 'login' not in driver.current_url.lower():
            print("   ✅ URL indicates successful login")
            login_successful = True
        
        if login_successful:
            print("\n🎉 LOGIN SUCCESSFUL!")
            print("The bot should work with these settings.")
        else:
            print("\n❌ LOGIN FAILED")
            print("Possible issues:")
            print("   - Invalid credentials")
            print("   - CAPTCHA required")  
            print("   - IP blocked by Naukri")
            print("   - Page structure changed")
            
        print(f"\n🔍 Final Page Analysis:")
        print(f"   URL: {driver.current_url}")
        print(f"   Title: {driver.title}")
        
        # Keep browser open for manual inspection
        input("\nPress Enter to close browser (inspect page manually if needed)...")
        
        return login_successful
        
    except Exception as e:
        print(f"❌ Debug session error: {e}")
        return False
    finally:
        if driver:
            driver.quit()

def quick_selector_test():
    """Quick test of current Naukri selectors"""
    print("🧪 Quick Selector Test...")
    
    driver = setup_debug_driver()
    if not driver:
        return
    
    try:
        driver.get('https://www.naukri.com/nlogin/login')
        time.sleep(3)
        
        print("\n📋 Current Page Elements:")
        
        # Check all form fields
        inputs = driver.find_elements(By.TAG_NAME, 'input')
        print(f"Input fields found: {len(inputs)}")
        for i, inp in enumerate(inputs):
            print(f"  {i+1}. ID: {inp.get_attribute('id')}, "
                  f"Type: {inp.get_attribute('type')}, "
                  f"Name: {inp.get_attribute('name')}")
        
        # Check all buttons
        buttons = driver.find_elements(By.TAG_NAME, 'button')
        print(f"\nButtons found: {len(buttons)}")
        for i, btn in enumerate(buttons):
            print(f"  {i+1}. Text: '{btn.text}', Type: {btn.get_attribute('type')}")
            
        input("\nPress Enter to close...")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    print("🔧 Naukri Login Debug Tool")
    print("=" * 40)
    print("1. Full debug session")
    print("2. Quick selector test")
    
    choice = input("\nSelect option (1 or 2): ").strip()
    
    if choice == "1":
        debug_login_step_by_step()
    elif choice == "2":
        quick_selector_test()
    else:
        print("Invalid choice")