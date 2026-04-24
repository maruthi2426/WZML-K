# Vegamovies Scraper Module

## Overview
This module provides a fresh, fast, and reliable scraper for extracting direct download links from Vegamovies movie and series URLs.

## File Structure
```
bot/scraper/
├── __init__.py          # Package initialization
├── vg.py               # Main Vegamovies scraper (v2.0)
└── README.md           # This file
```

## How It Works

### VegamoviesScraper Class
The `vg.py` module contains the `VegamoviesScraper` class that:

1. **Loads Movie/Series Page** - Uses Selenium WebDriver to load and render JavaScript
2. **Extracts Shortener Links** - Finds all shortener URLs (nexdrive, fast-dl, etc) from the page
3. **Filters by Quality** - Optionally filters to specific quality (e.g., 1080p)
4. **Resolves Shorteners** - Follows shortener links to extract direct download URLs
5. **Returns Results** - Returns structured data with show name, season, episode, quality, size, and direct URL

## Usage

### From Direct Link Generator
When a Vegamovies URL is detected, the bot automatically uses this scraper:

```
/leech https://vegamovies.nf/37740-kalinga-2024-hindi-dual-audio-web-dl-1080p-720p-480p.html -q 1080p
```

The `-q` flag specifies the quality to scrape:
- `480p` - SD Quality
- `720p` - HD Quality  
- `1080p` - Full HD Quality

### Standalone Usage
```python
from bot.scraper.vg import scrape_website

# Scrape without quality filter (gets all)
results = scrape_website("https://vegamovies.nf/...", quality_filter=None)

# Scrape with quality filter
results = scrape_website("https://vegamovies.nf/...", quality_filter="1080p")

# Results format
# [
#   {
#       "show_name": "Kalinga",
#       "season": "01",
#       "episode": "EP01",
#       "quality": "1080P",
#       "size": "1.2 GB",
#       "url": "https://direct-download-link.com/file"
#   },
#   ...
# ]
```

## Features

✅ **Fast Scraping** - Single Chrome instance for minimal overhead
✅ **Quality Filtering** - Extract specific quality only
✅ **Multi-Episode Support** - Handles both movies and series
✅ **Direct Links** - Resolves shortener to actual download URLs
✅ **Detailed Logging** - Shows progress and found links in logs
✅ **Error Handling** - Graceful fallbacks and error messages
✅ **Selenium-based** - JavaScript rendering support

## Dependencies

Required packages (auto-installed on first run):
- `selenium` - WebDriver for JavaScript rendering
- `beautifulsoup4` - HTML parsing
- `webdriver-manager` - Automatic Chrome driver management

These are installed automatically when the module loads if missing.

## Integration with Direct Link Generator

The scraper is integrated into `bot/helper/mirror_leech_utils/download_utils/direct_link_generator.py`:

1. **Auto-detection** - When a vegamovies.nf URL is detected
2. **Quality Passing** - Quality filter from `-q` flag is passed to scraper
3. **Result Handling** - Direct links are returned for download
4. **Logging** - All scraper output appears in bot logs

## Log Output

When scraping, you'll see logs like:

```
[INFO] ========== VEGAMOVIES SCRAPER v2.0 ==========
[INFO] URL: https://vegamovies.nf/...
[INFO] Quality Filter: 1080p
[INFO] Title: Kalinga
[INFO] Season: S01
[INFO] Found 1 shortener link(s)
[INFO] Resolving shortener links...
[INFO] Processing 1080P - EP01
[INFO]      Shortener: https://nexdrive.net/...
[INFO]      ✓ Direct Link: https://video-downloads.googleusercontent.com/...
[INFO] ========== SCRAPER COMPLETED ==========
[INFO] Total direct links found: 1
```

## Troubleshooting

### "WebScrapper module not loaded" Error
**Solution:** Ensure `bot/scraper/vg.py` exists and has the correct code.

### Chrome Driver Issues
**Solution:** `webdriver-manager` handles this automatically. Clear browser cache if issues persist.

### No Links Found
**Check:**
1. URL is correct and page loads normally
2. Quality filter matches available qualities on page
3. Shortener URLs are properly formatted

## Future Enhancements

- [ ] Add more website support (HDhub4u, etc)
- [ ] Implement retry logic for failed resolutions
- [ ] Add concurrent link resolution for speed
- [ ] Support for playlist/multiple episodes batch download

## Version History

**v2.0** - Fresh rewrite with improved error handling, better logging, and fixed dependencies
**v1.0** - Initial version with basic functionality
