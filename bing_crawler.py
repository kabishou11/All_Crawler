import os
import time
import signal
import requests
import csv
import re
import html
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# 全局控制变量
cancel_crawl = False
BING_URL = "https://www.bing.com/search"
QUERY = "" #搜索内容
visited_urls_file = 'visited_urls_bing.txt'
csv_file_path = 'bing_results.csv'
MAX_PAGES = 1000  # 最大翻页数
GEOLOCATIONS = {
    'tw': 'TW',  # 台湾
    'cn': 'CN',  # 中国
    'us': 'US',  # 美国
    'jp': 'JP'   # 日本
}

def signal_handler(sig, frame):
    global cancel_crawl
    cancel_crawl = True
    print("\n爬取已中断，正在保存当前进度...")

signal.signal(signal.SIGINT, signal_handler)

# Chrome浏览器配置
options = Options()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--window-size=1920,1080')
options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

# 初始化浏览器驱动
try:
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
except Exception as e:
    print(f"浏览器驱动初始化失败: {str(e)}")
    exit(1)

def load_visited_urls():
    if os.path.exists(visited_urls_file):
        with open(visited_urls_file, 'r', encoding='utf-8') as f:
            return set(f.read().splitlines())
    return set()

def save_visited_urls(urls):
    with open(visited_urls_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(urls))

def search_bing(query, region='US'):
    search_results = set()
    
    for page in range(0, MAX_PAGES):
        if cancel_crawl:
            break
            
        # 构造Bing搜索参数
        params = {
            'q': query,
            'first': page*10 + 1,  # Bing分页参数
            'cc': region
        }
        
        try:
            driver.get(f"{BING_URL}?{requests.compat.urlencode(params)}")
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'ol#b_results'))
            )
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            results = soup.select('li.b_algo h2 a')
            
            for link in results:
                url = link.get('href')
                if url and url.startswith('http'):
                    search_results.add(url)
            
            print(f"地区 {region} 第 {page+1} 页找到 {len(results)} 个结果")
            
            # 检查是否有下一页
            next_page = soup.select_one('a.sb_pagN')
            if not next_page:
                break
                
        except Exception as e:
            print(f"搜索失败: {str(e)}")
            break
            
    return list(search_results)

def clean_content(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
        tag.decompose()
    text = soup.get_text(separator=' ', strip=True)
    text = re.sub(r'\s+', ' ', text)
    return text[:10000]  # 限制内容长度

def crawl_page(url, visited, depth=1, max_depth=2):
    if cancel_crawl or url in visited or depth > max_depth:
        return
        
    print(f"正在爬取 [{depth}级]: {url}")
    visited.add(url)
    
    try:
        driver.get(url)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, 'body')))
        
        title = driver.title
        content = clean_content(driver.page_source)
        
        with open(csv_file_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([title, url, content])
            
        # 提取子链接
        if depth < max_depth:
            links = driver.find_elements(By.TAG_NAME, 'a')
            for link in links:
                href = link.get_attribute('href')
                if href and href.startswith('http'):
                    absolute_url = urljoin(url, href)
                    if absolute_url not in visited:
                        crawl_page(absolute_url, visited, depth+1, max_depth)
                        
    except Exception as e:
        print(f"爬取失败: {str(e)}")

def main():
    # 初始化文件
    if not os.path.exists(csv_file_path):
        with open(csv_file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['标题', 'URL', '内容'])
            
    visited = load_visited_urls()
    
    # 多地区搜索
    total_results = 0
    for region_code in GEOLOCATIONS.values():
        print(f"\n正在搜索地区: {region_code}")
        urls = search_bing(QUERY, region_code)
        total_results += len(urls)
        
        for url in urls:
            if cancel_crawl:
                break
            crawl_page(url, visited)
            
    driver.quit()
    save_visited_urls(visited)
    print(f"\n完成! 共爬取 {total_results} 个结果")

if __name__ == '__main__':
    main()
