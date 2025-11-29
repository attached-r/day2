# main.py
from flask import Flask, render_template, request, flash
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "123456"

DB_NAME = "database.db"

# 初始化数据库
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            pub_date TEXT,
            source TEXT,
            content TEXT,
            url TEXT,
            collect_time TEXT
        )
    ''')
    conn.commit()
    conn.close()

# 从数据库读取所有记录
def get_all_articles():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, title, pub_date, collect_time, url FROM articles ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

# 插入新记录
def save_article(title, pub_date, source, content, url):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO articles (title, pub_date, source, content, url, collect_time)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (title, pub_date or "未知", source or "未知", content, url, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

# 简单爬取函数
def crawl_page(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, 'lxml')

        # 标题（常见选择器）
        title = soup.find("h1") or soup.find("title") or soup.find("meta", property="og:title")
        title = title.get_text().strip() if title else "无标题"

        # 发布日期（常见关键词）
        date_text = ""
        for text in soup.stripped_strings:
            if any(k in text for k in ["发布日期", "发布时间", "日期", "时间"]):
                date_text = text
                break
        if not date_text:
            date_tag = soup.find(attrs={"class": lambda x: x and "date" in x.lower()})
            date_text = date_tag.get_text() if date_tag else ""

        # 正文（常见class/id）
        content_selectors = [
            "#content", ".article-content", ".content", ".TRS_Editor",
            "article", ".text", ".post-content"
        ]
        content = ""
        for sel in content_selectors:
            elem = soup.select_one(sel)
            if elem and len(elem.get_text()) > 100:
                content = elem.get_text(separator="\n").strip()
                break
        if not content:
            content = soup.get_text(separator="\n")[:3000]

        source = soup.find("meta", property="og:site_name")
        source = source["content"] if source else "未知来源"

        return {
            "title": title,
            "pub_date": date_text.replace("发布日期：", "").replace("发布时间：", "").strip(),
            "source": source,
            "content": content,
            "url": url
        }
    except Exception as e:
        return None

@app.route("/", methods=["GET", "POST"])
def index():
    init_db()
    result = None
    if request.method == "POST":
        url = request.form.get("url", "").strip()
        if not url.startswith("http"):
            flash("请输入完整的网址（带 http 或 https）", "error")
        else:
            flash("正在采集，请稍等...", "info")
            data = crawl_page(url)
            if data:
                save_article(data["title"], data["pub_date"], data["source"], data["content"], url)
                result = data
                flash("采集成功！", "success")
            else:
                flash("采集失败，请检查网址是否正确或网络是否正常", "error")

    articles = get_all_articles()
    return render_template("index.html", result=result, articles=articles)

if __name__ == "__main__":
    # 确保文件夹存在
    os.makedirs("templates", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=True)