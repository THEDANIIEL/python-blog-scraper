import os
import requests
from bs4 import BeautifulSoup
import json
import time
import re
from urllib.parse import urljoin, urlparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)

class BlogScraper:
    def __init__(self, base_url, output_folder="posts", delay=1):
        """
        Initialize the blog scraper
        
        Args:
            base_url (str): The URL of the blog homepage or section to scrape
            output_folder (str): The folder to save blog posts to
            delay (int): Delay between requests in seconds to avoid rate limiting
        """
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.output_folder = output_folder
        self.delay = delay
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        os.makedirs(output_folder, exist_ok=True)
        
        self.scraped_urls = set()

    def fetch_page(self, url):
        """Fetch the HTML content of a page."""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching {url}: {e}")
            return None

    def find_blog_links(self, html_content):
        """
        Extract blog post links from the blog homepage or archive pages
        
        This method attempts to identify blog post links using common patterns
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        links = []
        
        selectors = [
            "article a", ".post a", ".blog-post a", ".entry a", 
            ".post-title a", ".blog-entry a", ".post-link", ".blog-title a",
            "a.post-link", "a.read-more", "a.more-link", "h2 a", "h1 a", "h3 a"
        ]
        
        for selector in selectors:
            found_links = soup.select(selector)
            if found_links:
                for link in found_links:
                    href = link.get('href')
                    if href and not href.startswith('#') and not href.startswith('javascript:'):
                        absolute_url = urljoin(self.base_url, href)
                        if urlparse(absolute_url).netloc == self.domain:
                            links.append(absolute_url)
        
        if not links:
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href')
                absolute_url = urljoin(self.base_url, href)
                
                if urlparse(absolute_url).netloc == self.domain:
                    if re.search(r'/(post|blog|article|entry)/[a-zA-Z0-9\-]+/?$', absolute_url) or \
                       re.search(r'/\d{4}/\d{2}/\d{2}/[a-zA-Z0-9\-]+/?$', absolute_url) or \
                       re.search(r'/blog/[a-zA-Z0-9\-]+/?$', absolute_url):
                        links.append(absolute_url)
        
        return list(set(links))

    def find_pagination_links(self, html_content):
        """Find pagination links to scrape multiple pages of blog listings."""
        soup = BeautifulSoup(html_content, 'html.parser')
        pagination_links = []
        
        selectors = [
            ".pagination a", ".nav-links a", ".page-numbers", 
            "a.page-link", ".pager a", ".pages a", 
            "a[rel='next']", "a.next"
        ]
        
        for selector in selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                if href and not href.startswith('#'):
                    absolute_url = urljoin(self.base_url, href)
                    if urlparse(absolute_url).netloc == self.domain:
                        pagination_links.append(absolute_url)
                        
        return list(set(pagination_links))

    def extract_blog_content(self, html_content, url):
        """
        Extract blog post content from a blog post page
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        data = {
            "url": url,
            "title": "",
            "date": "",
            "author": "",
            "content": "",
            "raw_html": "",  
            "categories": []
        }
        
        title_selectors = ["h1", "h1.post-title", "h1.entry-title", ".post-title", ".entry-title", "article h1"]
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                data["title"] = title_elem.get_text().strip()
                break
                
        date_selectors = [
            ".post-date", ".entry-date", ".published", "time", 
            ".date", "meta[property='article:published_time']", 
            "span.date", ".post-meta time"
        ]
        for selector in date_selectors:
            date_elem = soup.select_one(selector)
            if date_elem:
                if selector == "meta[property='article:published_time']":
                    data["date"] = date_elem.get("content", "")
                else:
                    data["date"] = date_elem.get_text().strip()
                break
                
        author_selectors = [
            ".author", ".entry-author", "a.author", ".post-author", 
            "meta[name='author']", ".author-name", ".byline"
        ]
        for selector in author_selectors:
            author_elem = soup.select_one(selector)
            if author_elem:
                if selector == "meta[name='author']":
                    data["author"] = author_elem.get("content", "")
                else:
                    data["author"] = author_elem.get_text().strip()
                break
                
        category_selectors = [
            ".category", ".categories", ".tags", ".post-tags", 
            ".entry-tags", ".post-categories", "a[rel='category']"
        ]
        for selector in category_selectors:
            category_elems = soup.select(selector)
            if category_elems:
                data["categories"] = [cat.get_text().strip() for cat in category_elems]
                break
                
        content_selectors = [
            "article", ".post-content", ".entry-content", 
            ".content", ".post", ".blog-post", ".article-content"
        ]
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                for element in content_elem.select("script, style"):
                    element.decompose()
                    
                data["content"] = content_elem.get_text().strip()
                data["raw_html"] = str(content_elem)
                break
            
        #extract raw html
        # content_selectors = [
        #     "article", ".post-content", ".entry-content", 
        #     ".content", ".post", ".blog-post", ".article-content"
        # ]
        # for selector in content_selectors:
        #     content_elem = soup.select_one(selector)
        #     if content_elem:
        #         # Remove script and style elements
        #         for element in content_elem.select("script, style"):
        #             element.decompose()
                    
        #         data["content"] = content_elem.get_text().strip()
        #         break
                
        return data

    def save_post(self, post_data):
        """Save a blog post to a file."""
        if not post_data["title"]:
            filename = re.sub(r'[^\w\-]', '_', post_data["url"].split("/")[-1]) or "post"
        else:
            filename = re.sub(r'[^\w\-]', '_', post_data["title"])
            
        filename = f"{filename[:50]}.json"  
        filepath = os.path.join(self.output_folder, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(post_data, f, ensure_ascii=False, indent=4)
            
        logging.info(f"Saved: {filepath}")
        return filepath

    def scrape(self, max_posts=50, max_pages=5):
        """
        Main scraping method
        
        Args:
            max_posts (int): Maximum number of posts to scrape
            max_pages (int): Maximum number of listing pages to scrape
        """
        logging.info(f"Starting scrape of {self.base_url}")
        
        html_content = self.fetch_page(self.base_url)
        if not html_content:
            logging.error(f"Failed to fetch the blog homepage: {self.base_url}")
            return
            
        blog_links = self.find_blog_links(html_content)
        pagination_links = self.find_pagination_links(html_content)
        
        pages_scraped = 1
        while pagination_links and pages_scraped < max_pages:
            next_page_url = pagination_links[0]  
            pagination_links = pagination_links[1:]  
            
            logging.info(f"Scraping pagination page: {next_page_url}")
            page_html = self.fetch_page(next_page_url)
            
            if page_html:
                new_links = self.find_blog_links(page_html)
                blog_links.extend(new_links)
                
                new_pagination = self.find_pagination_links(page_html)
                pagination_links.extend([link for link in new_pagination if link not in pagination_links])
                
            pages_scraped += 1
            time.sleep(self.delay)
            
        blog_links = list(set(blog_links))[:max_posts]
        
        logging.info(f"Found {len(blog_links)} blog posts to scrape")
        
        for i, link in enumerate(blog_links, 1):
            if link in self.scraped_urls:
                continue
                
            logging.info(f"[{i}/{len(blog_links)}] Scraping: {link}")
            
            html_content = self.fetch_page(link)
            if html_content:
                post_data = self.extract_blog_content(html_content, link)
                self.save_post(post_data)
                self.scraped_urls.add(link)
                
            time.sleep(self.delay)  
            
        logging.info(f"Scraping completed. Scraped {len(self.scraped_urls)} posts")

if __name__ == "__main__":
    url = "https://www.example.com/blog"
    scraper = BlogScraper(url, output_folder="posts/jajiga", delay=2)
    scraper.scrape(max_posts=100, max_pages=10)