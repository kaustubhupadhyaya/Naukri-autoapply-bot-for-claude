"""
Performance Diagnostic Tool - Find bottlenecks in job processing
"""

import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

def load_config():
    """Load configuration"""
    try:
        with open("enhanced_config.json", 'r') as f:
            return json.load(f)
    except:
        with open("config.json", 'r') as f:
            return json.load(f)

def setup_fast_driver():
    """Setup driver with performance monitoring"""
    options = webdriver.EdgeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    try:
        driver = webdriver.Edge(options=options)
        # Set FAST timeouts for testing
        driver.implicitly_wait(2)  # Very short
        driver.set_page_load_timeout(15)
        return driver
    except Exception as e:
        print(f"❌ Driver setup failed: {e}")
        return None

def diagnose_job_extraction_speed():
    """Diagnose exactly what's causing slow job extraction"""
    print("🔍 PERFORMANCE DIAGNOSTIC - Job Extraction Speed Test")
    print("=" * 60)
    
    config = load_config()
    driver = setup_fast_driver()
    
    if not driver:
        return
    
    try:
        # Step 1: Login (reuse from working login)
        print("\n1️⃣ Testing Login Speed...")
        login_start = time.time()
        
        driver.get('https://www.naukri.com/nlogin/login')
        time.sleep(3)
        
        # Fast login
        email_field = driver.find_element(By.ID, 'usernameField')
        email_field.send_keys(config['credentials']['email'])
        
        password_field = driver.find_element(By.ID, 'passwordField')  
        password_field.send_keys(config['credentials']['password'])
        
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_button.click()
        time.sleep(5)
        
        login_time = time.time() - login_start
        print(f"   ✅ Login completed in {login_time:.1f} seconds")
        
        # Step 2: Navigate to job search
        print("\n2️⃣ Testing Job Search Navigation...")
        nav_start = time.time()
        
        search_url = "https://www.naukri.com/data-engineer-jobs-in-bengaluru-1"
        driver.get(search_url)
        
        nav_time = time.time() - nav_start
        print(f"   ✅ Navigation completed in {nav_time:.1f} seconds")
        
        # Step 3: Find job cards
        print("\n3️⃣ Testing Job Card Detection...")
        card_detection_start = time.time()
        
        # Try different selectors and time each one
        selectors_to_test = [
            '.srp-jobtuple-wrapper',
            '.jobTuple',
            '[data-job-id]',
            '.job-tuple'
        ]
        
        best_selector = None
        best_time = float('inf')
        best_count = 0
        
        for selector in selectors_to_test:
            try:
                selector_start = time.time()
                job_cards = driver.find_elements(By.CSS_SELECTOR, selector)
                selector_time = time.time() - selector_start
                
                print(f"   • {selector}: {len(job_cards)} cards in {selector_time:.2f}s")
                
                if len(job_cards) > 0 and selector_time < best_time:
                    best_selector = selector
                    best_time = selector_time
                    best_count = len(job_cards)
                    
            except Exception as e:
                print(f"   • {selector}: FAILED - {e}")
        
        card_detection_time = time.time() - card_detection_start
        print(f"   ✅ Card detection completed in {card_detection_time:.1f} seconds")
        print(f"   🏆 Best selector: {best_selector} ({best_count} cards in {best_time:.2f}s)")
        
        if not best_selector:
            print("   ❌ No working selectors found!")
            return
        
        # Step 4: Test job data extraction speed
        print("\n4️⃣ Testing Job Data Extraction Speed...")
        
        job_cards = driver.find_elements(By.CSS_SELECTOR, best_selector)
        test_cards = job_cards[:3]  # Test first 3 cards
        
        extraction_times = []
        successful_extractions = 0
        
        for i, job_card in enumerate(test_cards):
            print(f"   📋 Testing card {i+1}/3...")
            
            extraction_start = time.time()
            
            # Test different extraction approaches
            extraction_success = False
            
            # Approach 1: Direct selectors
            try:
                title_selectors = ['.title', '.jobTuple-title', 'h3']
                company_selectors = ['.subTitle', '.companyName']
                
                title = ""
                company = ""
                
                for selector in title_selectors:
                    try:
                        element = job_card.find_element(By.CSS_SELECTOR, selector)
                        title = element.text.strip()
                        if title:
                            break
                    except:
                        continue
                
                for selector in company_selectors:
                    try:
                        element = job_card.find_element(By.CSS_SELECTOR, selector)
                        company = element.text.strip()  
                        if company:
                            break
                    except:
                        continue
                
                if title and company:
                    extraction_success = True
                    print(f"     ✅ Direct: '{title}' at '{company}'")
                    
            except Exception as e:
                print(f"     ❌ Direct approach failed: {e}")
            
            # Approach 2: Full text parsing (if direct failed)
            if not extraction_success:
                try:
                    full_text = job_card.text
                    lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                    
                    if lines:
                        title = lines[0]
                        company = lines[1] if len(lines) > 1 else "Unknown Company"
                        extraction_success = True
                        print(f"     ✅ Text parsing: '{title}' at '{company}'")
                        
                except Exception as e:
                    print(f"     ❌ Text parsing failed: {e}")
            
            extraction_time = time.time() - extraction_start
            extraction_times.append(extraction_time)
            
            if extraction_success:
                successful_extractions += 1
                
            print(f"     ⏱️  Extraction time: {extraction_time:.2f} seconds")
            
            # Stop if extraction is taking too long
            if extraction_time > 10:
                print(f"     ⚠️  SLOW EXTRACTION DETECTED!")
                break
        
        # Step 5: Performance Summary
        print(f"\n📊 PERFORMANCE SUMMARY")
        print("=" * 40)
        print(f"Login Time: {login_time:.1f}s")
        print(f"Navigation Time: {nav_time:.1f}s") 
        print(f"Card Detection: {card_detection_time:.1f}s")
        print(f"Best Selector: {best_selector}")
        print(f"Cards Found: {best_count}")
        
        if extraction_times:
            avg_extraction = sum(extraction_times) / len(extraction_times)
            max_extraction = max(extraction_times)
            min_extraction = min(extraction_times)
            
            print(f"\nExtraction Performance:")
            print(f"  • Successful: {successful_extractions}/{len(test_cards)}")
            print(f"  • Average: {avg_extraction:.2f}s per job")
            print(f"  • Fastest: {min_extraction:.2f}s")
            print(f"  • Slowest: {max_extraction:.2f}s")
            
            # Performance recommendations
            print(f"\n🎯 RECOMMENDATIONS:")
            if avg_extraction < 5:
                print("✅ GOOD: Extraction is reasonably fast")
            elif avg_extraction < 15:
                print("⚠️  MODERATE: Could be optimized")
            else:
                print("🚨 SLOW: Major optimization needed")
            
            if max_extraction > 30:
                print("🔧 Add timeout limits to prevent hanging")
                
            if successful_extractions < len(test_cards):
                print("🔧 Update selectors for current Naukri structure")
                
        # Bottleneck identification
        print(f"\n🔍 BOTTLENECK ANALYSIS:")
        total_time = login_time + nav_time + card_detection_time
        
        if login_time > 15:
            print("🐌 BOTTLENECK: Login is slow")
        if nav_time > 10:
            print("🐌 BOTTLENECK: Page navigation is slow")
        if card_detection_time > 5:
            print("🐌 BOTTLENECK: Job card detection is slow")
        if extraction_times and avg_extraction > 10:
            print("🐌 BOTTLENECK: Job data extraction is slow")
            
        print(f"\n⚡ TO OPTIMIZE:")
        print("1. Use fastest selector:", best_selector)
        print("2. Set extraction timeout to 5 seconds")
        print("3. Use fallback text parsing")
        print("4. Reduce implicit waits to 2-3 seconds")
        
    except Exception as e:
        print(f"❌ Diagnostic failed: {e}")
        
    finally:
        input("\nPress Enter to close browser...")
        driver.quit()

def quick_speed_test():
    """Quick test of key operations"""
    print("⚡ QUICK SPEED TEST")
    print("=" * 30)
    
    driver = setup_fast_driver()
    if not driver:
        return
    
    try:
        # Test 1: Page load speed
        start = time.time()
        driver.get("https://www.naukri.com")
        load_time = time.time() - start
        print(f"Page Load: {load_time:.1f}s")
        
        # Test 2: Element find speed
        start = time.time()
        try:
            elements = driver.find_elements(By.TAG_NAME, "div")
            find_time = time.time() - start
            print(f"Element Find: {find_time:.2f}s ({len(elements)} divs)")
        except:
            find_time = time.time() - start
            print(f"Element Find: {find_time:.2f}s (failed)")
        
        # Test 3: Text extraction speed
        start = time.time()
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            text_time = time.time() - start
            print(f"Text Extract: {text_time:.2f}s ({len(body_text)} chars)")
        except:
            text_time = time.time() - start
            print(f"Text Extract: {text_time:.2f}s (failed)")
            
        # Overall assessment
        total_time = load_time + find_time + text_time
        print(f"\nTotal: {total_time:.1f}s")
        
        if total_time < 5:
            print("✅ FAST: System performing well")
        elif total_time < 15:
            print("⚠️  MODERATE: Some optimization needed")  
        else:
            print("🚨 SLOW: Significant optimization required")
            
    except Exception as e:
        print(f"❌ Quick test failed: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    print("🔧 Naukri Bot Performance Diagnostic Tool")
    print("=" * 50)
    print("1. Full diagnostic (recommended)")
    print("2. Quick speed test")
    
    choice = input("\nSelect option (1 or 2): ").strip()
    
    if choice == "1":
        diagnose_job_extraction_speed()
    elif choice == "2":
        quick_speed_test()
    else:
        print("Invalid choice")