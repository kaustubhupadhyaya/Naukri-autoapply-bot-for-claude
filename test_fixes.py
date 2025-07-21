
if __name__ == "__main__":
    """Test script to verify fixes work"""
    
    print("🔧 Testing Naukri Bot Fixes...")
    
    # Test 1: Base bot functionality
    print("\n1️⃣ Testing Base Bot (Naukri_Edge.py)")
    try:
        from Naukri_Edge import IntelligentNaukriBot
        base_bot = IntelligentNaukriBot()
        
        if base_bot.setup_driver():
            print("✅ Base bot driver setup: SUCCESS")
        else:
            print("❌ Base bot driver setup: FAILED")
            
        base_bot.driver.quit() if hasattr(base_bot, 'driver') and base_bot.driver else None
        
    except Exception as e:
        print(f"❌ Base bot test failed: {e}")
    
    # Test 2: Enhanced bot initialization  
    print("\n2️⃣ Testing Enhanced Bot Initialization")
    try:
        from enhanced_naukri_bot import EnhancedNaukriBot
        enhanced_bot = EnhancedNaukriBot()
        print("✅ Enhanced bot initialization: SUCCESS")
        
    except Exception as e:
        print(f"❌ Enhanced bot initialization failed: {e}")
    
    # Test 3: AI Processor
    print("\n3️⃣ Testing AI Processor")
    try:
        from intelligent_job_processor import IntelligentJobProcessor
        processor = IntelligentJobProcessor()
        print("✅ AI processor initialization: SUCCESS")
        
    except Exception as e:
        print(f"❌ AI processor failed: {e}")
    
    print("\n🎯 Fix testing completed!")
    print("Next steps:")
    print("1. Apply the fixes above to your code")
    print("2. Run 'python test_fixes.py' to verify")
    print("3. Test with small batch (5-10 jobs) first")
    print("4. Monitor logs for any remaining issues")