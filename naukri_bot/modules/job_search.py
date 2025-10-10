"""
Job Search Module - Handles job searching and filtering
"""

import re
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from naukri_bot.utils.helpers import smart_delay, extract_job_id

logger = logging.getLogger(__name__)


class JobSearchModule:
    """Handles job searching and link collection"""

    def __init__(self, driver, config, database):
        self.driver = driver
        self.config = config
        self.database = database
        self.joblinks = []

    def search_jobs(self):
        """
        Search for jobs based on keywords
        Returns: list of job URLs
        """
        try:
            logger.info("🔍 Starting job search...")

            keywords = self.config['job_search']['keywords']
            location = self.config['job_search']['location']
            pages_per_keyword = self.config['job_search'].get('pages_per_keyword', 3)

            self.joblinks = []

            for keyword in keywords:
                logger.info(f"\n{'='*60}")
                logger.info(f"Searching: '{keyword}' in {location}")
                logger.info(f"{'='*60}")

                links = self._search_keyword(keyword, location, pages_per_keyword)
                self.joblinks.extend(links)

                smart_delay(2, 3)

            # Remove duplicates
            self.joblinks = list(set(self.joblinks))

            # Filter out already applied
            self.joblinks = [
                link for link in self.joblinks
                if not self.database.is_job_applied(extract_job_id(link))
            ]

            logger.info(f"\n✅ Found {len(self.joblinks)} jobs to apply")

            return self.joblinks

        except Exception as e:
            logger.error(f"Job search error: {e}")
            return []

    def _search_keyword(self, keyword, location, max_pages):
        """Search for a specific keyword"""
        links = []

        try:
            # Build search URL
            search_url = f"https://www.naukri.com/{keyword.replace(' ', '-')}-jobs-in-{location.replace(' ', '-')}"

            logger.info(f"🌐 Navigating to: {search_url}")
            self.driver.get(search_url)
            smart_delay(3, 5)

            # Collect job links from multiple pages
            for page_num in range(1, max_pages + 1):
                logger.info(f"📄 Scraping page {page_num}/{max_pages}...")

                page_links = self._extract_job_links_from_page()
                links.extend(page_links)

                logger.info(f"Found {len(page_links)} jobs on page {page_num}")

                # Go to next page
                if page_num < max_pages:
                    if not self._go_to_next_page():
                        logger.info("No more pages available")
                        break

                    smart_delay(2, 3)

            logger.info(f"✅ Collected {len(links)} jobs for '{keyword}'")

        except Exception as e:
            logger.error(f"Keyword search error for '{keyword}': {e}")

        return links
    
    def _extract_job_links_from_page(self):
        """Extract job links from current page"""
        links = []

        job_card_selectors = [
            "article.jobTuple",
            "div.jobTuple",
            "div[class*='job-tuple']",
            "a.title"
        ]

        for selector in job_card_selectors:
            try:
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, selector)

                if job_cards:
                    for card in job_cards:
                        try:
                            # Find link within card
                            link = card.get_attribute('href')

                            if not link:
                                # Try finding anchor tag
                                anchor = card.find_element(By.CSS_SELECTOR, "a")
                                link = anchor.get_attribute('href')

                            if link and 'naukri.com' in link:
                                # Filter by job criteria
                                if self._matches_criteria(card.text):
                                    links.append(link)

                        except:
                            continue

                    if links:
                        break

            except:
                continue

        return links

    def _matches_criteria(self, job_text):
        """Check if job matches search criteria"""
        try:
            text = job_text.lower()

            # Check avoided companies
            avoid_companies = [c.lower() for c in self.config['job_search'].get('avoid_companies', [])]
            if any(company in text for company in avoid_companies):
                return False

            # Check preferred companies (if specified)
            preferred_companies = [c.lower() for c in self.config['job_search'].get('preferred_companies', [])]
            if preferred_companies and not any(company in text for company in preferred_companies):
                return False

            # Check keywords
            keywords = [k.lower() for k in self.config['job_search']['keywords']]
            if any(keyword in text for keyword in keywords):
                return True

            return True

        except:
            return True

    def _go_to_next_page(self):
        """Navigate to next page of results"""
        try:
            # Find next button
            next_selectors = [
                "a.styles_btn-secondary__2AsIP[href*='page']",
                "a[class*='pagination'] span:contains('Next')",
                "//a[contains(text(), 'Next')]",
                "a.fright"
            ]

            for selector in next_selectors:
                try:
                    if selector.startswith('//'):
                        next_button = self.driver.find_element(By.XPATH, selector)
                    elif ':contains' in selector:
                        # Handle pseudo-selector
                        text = selector.split("'")[1]
                        next_button = self.driver.find_element(
                            By.XPATH,
                            f"//a[contains(text(), '{text}')]"
                        )
                    else:
                        next_button = self.driver.find_element(By.CSS_SELECTOR, selector)     

                    if next_button.is_displayed() and next_button.is_enabled():
                        next_button.click()
                        return True

                except:
                    continue

            return False

        except Exception as e:
            logger.debug(f"Next page navigation failed: {e}")
            return False