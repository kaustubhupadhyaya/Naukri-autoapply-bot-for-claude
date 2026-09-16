"""Job search, card scraping, relevance.

Restructured from Naukri_Edge.py (2025-10-12 "IMPROVED VERSION").
Methods are moved verbatim from the original class; behavior is unchanged.
"""
import re
import os
import sys
import json
import time
import random
import sqlite3
import logging
import platform
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
    InvalidSessionIdException,
    ElementNotInteractableException,
)

logger = logging.getLogger(__name__)


class SearchMixin:

    def scrape_job_links(self):
        """Deprecated: scraping is now handled per-page by search_and_apply_page_by_page()."""
        logger.warning("scrape_job_links() is deprecated. Use search_and_apply_page_by_page().")
        return False

    def search_and_apply_page_by_page(self):
        """Scrapes and applies to jobs on a page-by-page basis."""
        logger.info("🔍 Starting page-by-page job search and application...")

        keywords = self.config['job_search']['keywords']
        location = self.config['job_search']['location']
        pages_per_keyword = self.config['job_search']['pages_per_keyword']
        # 0 / null / absent = unlimited
        max_applications = self.config['job_search'].get('max_applications_per_session') or 0

        for keyword in keywords:
            logger.info(f"🔎 Searching for: {keyword}")

            for page in range(1, pages_per_keyword + 1):
                if max_applications and self.applied >= max_applications:
                    logger.info(f"✋ Reached application limit ({max_applications})")
                    return

                try:
                    search_keyword = keyword.lower().replace(' ', '-')
                    search_location = location.lower().replace(' ', '-')
                    url = f"https://www.naukri.com/{search_keyword}-jobs-in-{search_location}-{page}"

                    logger.info(f"📄 Page {page}")
                    self.driver.get(url)

                    WebDriverWait(self.driver, 8).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'body'))
                    )
                    self.smart_delay(1, 2, probability=0.3)
                    self._handle_popups()

                    job_cards = self._get_job_cards_fast()

                    if not job_cards:
                        logger.info("No jobs found on this page, moving to next keyword.")
                        break

                    page_job_links = []
                    for card in job_cards:
                        try:
                            job_url = self._extract_job_url_fast(card)
                            if job_url and job_url not in self.joblinks:
                                job_id = self._extract_job_id(job_url)
                                if not self.is_job_already_applied(job_id) and self._is_job_relevant_fast(card):
                                    page_job_links.append(job_url)
                                    self.joblinks.append(job_url)
                        except Exception as e:
                            logger.debug(f"Error extracting job: {e}")

                    if page_job_links:
                        logger.info(f"✅ Found {len(page_job_links)} new jobs on this page. Applying now...")
                        self.apply_to_jobs(page_job_links)
                    else:
                        logger.info("No new jobs on this page to apply for.")

                except Exception as e:
                    logger.error(f"Error on page {page} for keyword '{keyword}': {e}")
                    continue

    def _get_job_cards_fast(self):
        """Fast job card extraction"""
        selectors = ['.srp-jobtuple-wrapper', '.jobTuple', '[data-job-id]']

        for selector in selectors:
            try:
                cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if cards:
                    return cards
            except:
                continue
        return []

    def _extract_job_url_fast(self, job_card):
        """Fast URL extraction"""
        try:
            link_selectors = ['.title a', '.jobTuple-title a', 'a[href*="job-listings"]']

            for selector in link_selectors:
                try:
                    link = job_card.find_element(By.CSS_SELECTOR, selector)
                    href = link.get_attribute('href')
                    if href and 'job-listings' in href:
                        return href
                except:
                    continue
            return None
        except:
            return None

    def _is_job_relevant_fast(self, job_card):
        """Fast relevance check"""
        try:
            text = job_card.text.lower()

            avoid_companies = [c.lower() for c in self.config['job_search'].get('avoid_companies', [])]
            if any(company in text for company in avoid_companies):
                return False

            # 2026-09-16: this used to fall through to an unconditional `return True`,
            # which made the keyword check dead code -- every Easy-Apply card passed and
            # Naukri's ~26/day server-side quota got spent on clerical/e-commerce roles
            # (12 of 20 slots on 09-15, 2 of 5 on 09-16). The match is now authoritative.
            #
            # It matches `relevance_keywords` (role tokens), NOT `keywords` (search-URL
            # phrases). Measured against 237 real cards: matching the search phrases
            # literally rejected 'ETL Lead', 'ETL Pentaho Developer', 'Airflow developer'
            # and 'Informatica developer' -- target roles that simply do not contain the
            # two-word phrase 'ETL Developer'. Falls back to `keywords` if unset.
            js = self.config['job_search']
            tokens = [k.lower() for k in (js.get('relevance_keywords') or js['keywords'])]

            # Word-ish boundaries, not bare substrings: a bare 'etl'/'dbt' would match
            # inside unrelated words, which is exactly how the 'fir' token once matched
            # 'confirm' and discarded every consent question.
            return any(
                re.search(r'(?<![a-z0-9])' + re.escape(tok) + r'(?![a-z0-9])', text)
                for tok in tokens
            )
        except Exception:
            # A card we cannot read is not evidence of relevance -- but it is also not
            # evidence against it, and dropping it silently loses real jobs. Keep the
            # permissive behaviour only for this genuinely-unknown case.
            return True
