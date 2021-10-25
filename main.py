import time
from pathlib import Path
from bs4 import BeautifulSoup
import requests
from typing import List, Any
from smtplib import SMTP_SSL
from email.mime.text import MIMEText
import yaml
import argparse
from urllib.parse import urljoin


class Article:
    def __init__(self) -> None:
        self.title = ''
        self.content = ''
        self.url = ''
        self.time: int = 0


class Config:
    def __init__(self, config_path) -> None:
        if(not config_path.exists()):
            raise FileNotFoundError("not found config path")

        with open(config_path, 'r', encoding="utf-8") as config_f:
            config = yaml.load(config_f, Loader=yaml.FullLoader)
            self.url = config['url']
            self.keys = config['keys']
            self.email_from = config['email_from']
            self.email_to = config['email_to']
            self.email_smtp = config['email_smtp']
            self.email_smtp_port = config['email_smtp_port']
            self.email_user = config['email_user']
            self.email_password = config['email_password']


def fetch_sz_csse_news(url: str) -> List[Article]:
    resp = requests.get(url)
    resp.encoding = 'utf-8'
    soup = BeautifulSoup(resp.text, 'html.parser')
    articles_html = soup.find(class_="articles")

    articles: List[Article] = []
    for link in articles_html.find_all('li'):
        a_html = link.find('a')
        span_html = link.find('span')

        article = Article()
        article.title = a_html.text
        article.url = urljoin(url, a_html.get('href'))
        article.time = int(time.mktime(time.strptime(
            span_html.text.split('|', 1)[1].strip(), '%Y-%m-%d')))
        articles.append(article)

    return articles


def get_last_update_time() -> int:
    time_file = Path('./.time.txt')
    if(not time_file.exists()):
        return 0

    with open(time_file, 'r') as time_f:
        return int(time_f.readline().strip())


def set_last_update_time(last_update_time: int) -> None:
    time_file = Path('./.time.txt')

    with open(time_file, 'w') as time_f:
        time_f.write(str(last_update_time))


def filter_articles(articles: List[Article],  keys: List[str]) -> List[Article]:
    last_update_time = get_last_update_time()

    article_max_update_time = last_update_time
    filter_articles: List[Article] = []
    for article in articles:
        if(article.time <= last_update_time):
            continue

        if(article_max_update_time < article.time):
            article_max_update_time = article.time

        for key in keys:
            if(key in article.title):
                filter_articles.append(article)

    set_last_update_time(article_max_update_time)
    return filter_articles


def fetch_article_content(articles: List[Article]) -> List[Article]:
    for article in articles:
        print('fetching article for [%s]' % (article.title))
        resp = requests.get(article.url)
        resp.encoding = 'utf-8'
        article.content = replace_url_for_article(resp.text, article.url)

    return articles


def replace_url_for_article(content: str, content_url: str) -> str:
    soup = BeautifulSoup(content, 'html.parser')
    header_html = soup.find(id='header')
    nav_html = soup.find(id='nav')
    imgs_html = soup.find_all('img')
    as_html = soup.find_all('a')
    links_html = soup.find_all('link')
    scripts_html = soup.find_all('script')

    for img_html in imgs_html:
        img_html['src'] = urljoin(content_url, img_html.get('src'))
    for a_html in as_html:
        a_html['href'] = urljoin(content_url, a_html.get('href'))
    for link_html in links_html:
        link_html['href'] = urljoin(content_url, link_html.get('href'))
    for script_html in scripts_html:
        script_html['href'] = urljoin(content_url, script_html.get('href'))

    header_html.decompose()
    nav_html.decompose()

    return str(soup.prettify())


def notify_email(articles: List[Article], config: Any):
    for article in articles:
        msg = MIMEText(article.content, 'html', _charset="utf-8")
        msg["Subject"] = article.title
        msg["from"] = config.email_from
        msg["to"] = config.email_to
        with SMTP_SSL(host=config.email_smtp, port=config.email_smtp_port) as smtp:
            smtp.login(user=config.email_user, password=config.email_password)
            smtp.sendmail(from_addr=config.email_user, to_addrs=[
                          config.email_to], msg=msg.as_string())

        print("send email successed! email title: %s" % (article.title))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', required=True,
                        dest='config', help="Yaml config file")
    args = parser.parse_args()

    config = Config(Path(args.config))

    articles = fetch_sz_csse_news(config.url)
    articles = filter_articles(articles, config.keys)
    articles = fetch_article_content(articles)

    notify_email(articles, config)
