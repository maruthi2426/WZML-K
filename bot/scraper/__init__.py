"""
Scraper Package for WZML-K Bot
Contains website-specific scrapers for extracting direct download links
"""

from .vg import scrape_website, VegamoviesScraper

__all__ = ['scrape_website', 'VegamoviesScraper']
