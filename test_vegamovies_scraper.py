#!/usr/bin/env python3
"""
Test script for Vegamovies Scraper
Run this to verify the scraper works correctly
"""

import sys
import os

# Add bot directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bot'))

def test_scraper_import():
    """Test if scraper can be imported"""
    print("[TEST] Testing scraper import...")
    try:
        from scraper.vg import scrape_website, VegamoviesScraper
        print("✓ Scraper imported successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to import scraper: {e}")
        return False

def test_scraper_class():
    """Test if scraper class can be instantiated"""
    print("\n[TEST] Testing scraper class instantiation...")
    try:
        from scraper.vg import VegamoviesScraper
        scraper = VegamoviesScraper()
        print("✓ Scraper class instantiated successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to instantiate scraper: {e}")
        return False

def test_dependencies():
    """Test if all dependencies are available"""
    print("\n[TEST] Checking dependencies...")
    dependencies = {
        'selenium': 'Selenium WebDriver',
        'bs4': 'BeautifulSoup4',
        'webdriver_manager': 'WebDriver Manager',
    }
    
    all_ok = True
    for module, name in dependencies.items():
        try:
            __import__(module)
            print(f"✓ {name} is installed")
        except ImportError:
            print(f"✗ {name} is NOT installed")
            all_ok = False
    
    return all_ok

def test_direct_link_generator_integration():
    """Test if scraper is integrated into direct link generator"""
    print("\n[TEST] Testing direct link generator integration...")
    try:
        from helper.mirror_leech_utils.download_utils.direct_link_generator import _load_webscrapper_module
        result = _load_webscrapper_module()
        if result:
            print("✓ Scraper successfully integrated with direct link generator")
            return True
        else:
            print("✗ Scraper failed to load in direct link generator")
            return False
    except Exception as e:
        print(f"✗ Error testing integration: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print("="*70)
    print("VEGAMOVIES SCRAPER - SYSTEM TEST")
    print("="*70)
    
    tests = [
        ("Scraper Import", test_scraper_import),
        ("Scraper Class", test_scraper_class),
        ("Dependencies", test_dependencies),
        ("Direct Link Generator Integration", test_direct_link_generator_integration),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"✗ Unexpected error in {test_name}: {e}")
            results[test_name] = False
    
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Scraper is ready to use.")
        return True
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
