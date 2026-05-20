
"""lxml回退模块 - 当lxml不可用时提供基本功能"""

import html
import re
from html.parser import HTMLParser

class etree:
    @staticmethod
    def HTML(html_content):
        return html.unescape(html_content)
    
    @staticmethod
    def tostring(element, encoding='utf-8', pretty_print=False):
        if isinstance(element, str):
            return element.encode(encoding) if encoding else element
        return str(element).encode(encoding) if encoding else str(element)

class html_fromstring:
    @staticmethod
    def __call__(html_content):
        return etree.HTML(html_content)

def parse_html(html_content):
    return etree.HTML(html_content)

class SimpleHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.text = []
    
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr, value in attrs:
                if attr == 'href':
                    self.links.append(value)
    
    def handle_data(self, data):
        self.text.append(data.strip())
    
    def extract_links(self, html_content):
        self.links = []
        self.feed(html_content)
        return self.links
    
    def extract_text(self, html_content):
        self.text = []
        self.feed(html_content)
        return ' '.join(self.text)

__version__ = "0.0.0-fallback"
