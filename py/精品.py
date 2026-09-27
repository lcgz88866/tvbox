# -*- coding: utf-8 -*-
"""
==========================================================
  精品影视 (www.aeete.com) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎)
  站点类型: 自定义影视站 (Auete CMS)
  更新: 2026-08-12

  URL规则:
    首页: /
    分类页: /{cat}/index.html  (如 /Movie/index.html)
    子分类: /{cat}/{sub}/index.html  (如 /Movie/jqp/index.html)
    翻页: /{cat}/index{page}.html  (如 /Movie/index2.html)
    详情页: /{cat}/{sub}/{slug}/
    播放页: /{cat}/{sub}/{slug}/play-{line}-{ep}.html
    搜索: RSS索引 (/xml/rss.xml) 绕过验证码

  卡片结构:
    <li class="trans_3" data-href="/Movie/jqp/slug/">
      <a href="/Movie/jqp/slug/" class="pic">
        <img src="https://..." title="标题" />
        <button class="hdtag">备注</button>
      </a>
    </li>

  详情页元数据 (◎标记):
    ◎影片片名: 重器
    ◎影片导演: 沈严,李江明
    ◎影片主演: 黄景瑜,蒋奇明,...
    ◎影片地区: 中国大陆
    ◎上映年份: 2026-08-10
    ◎影片备注: 至6集/共33集

  播放源:
    H2标签: 『重器』云播X线 / 『重器』云播D线
    line_id=1: 云播X线 (M3u8高清)
    line_id=0: 云播D线 (M3u8超清)

  播放页:
    var now = base64decode("aHR0cHM6...")
    解码后为m3u8直链, parse=0直接播放
==========================================================
"""

import sys
sys.path.append('..')

# 本地调试时模拟 base.spider.Spider 基类
try:
    from base.spider import Spider
except ImportError:
    import types
    base_mod = types.ModuleType('base')
    spider_mod = types.ModuleType('base.spider')
    class Spider:
        pass
    spider_mod.Spider = Spider
    base_mod.spider = spider_mod
    sys.modules['base'] = base_mod
    sys.modules['base.spider'] = spider_mod

import re
import json
import ssl
import base64
import time
import urllib.parse
import urllib.request
from html import unescape as html_unescape


class Spider(Spider):

    HOST = "https://www.aeete.com"
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

    # 主分类
    CATEGORIES = [
        {"type_name": "电影", "type_id": "Movie",
         "subs": {"xjp": "喜剧片", "dzp": "动作片", "aqp": "爱情片", "khp": "科幻片",
                  "kbp": "恐怖片", "jsp": "惊悚片", "zzp": "战争片", "jqp": "剧情片"}},
        {"type_name": "电视剧", "type_id": "Tv",
         "subs": {"neidi": "国产剧", "hanju": "韩剧", "oumei": "美剧", "riju": "日剧",
                  "taiju": "台剧", "tvbgj": "港剧", "waiju": "外剧", "wangju": "网剧",
                  "yataiju": "泰剧", "yingju": "英剧", "duanju": "短剧"}},
        {"type_name": "动漫", "type_id": "Dm",
         "subs": {"guoman": "国漫", "riman": "日漫", "meiman": "美漫", "donghua": "动画"}},
        {"type_name": "综艺", "type_id": "Zy",
         "subs": {"guozong": "大陆综艺", "qitazy": "其他综艺"}},
        {"type_name": "其他", "type_id": "qita",
         "subs": {"Jlp": "纪录片", "wlp": "网络短片"}},
    ]

    def init(self, extend=""):
        self.host = self.HOST
        self.ua = self.UA
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        self._play_header = json.dumps({
            "User-Agent": self.ua,
            "Referer": self.host + "/",
        })
        self._rss_cache = None
        self._rss_cache_time = 0

    def getName(self):
        return "精品影视"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|ts)(\?|#|$)', url, re.I))

    def manualVideoVCandidate(self, items):
        return []

    # ===== HTTP辅助 =====

    def _fetch(self, path, params=None):
        """获取页面HTML"""
        url = path if path.startswith("http") else (self.host + path)
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, headers=self.headers)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            resp = urllib.request.urlopen(req, timeout=15, context=ctx)
            data = resp.read()
            charset = "utf-8"
            content_type = resp.headers.get("Content-Type", "")
            if "charset=" in content_type:
                charset = content_type.split("charset=")[-1].strip().split(";")[0]
            try:
                return data.decode(charset, errors="replace")
            except Exception:
                return data.decode("utf-8", errors="replace")
        except Exception:
            return ""

    # ===== 首页 =====

    def homeContent(self, filter):
        result = {}
        classes = []
        filters = {}
        for cat in self.CATEGORIES:
            classes.append({"type_name": cat["type_name"], "type_id": cat["type_id"]})
            if cat.get("subs"):
                sub_options = [{"n": "全部", "v": ""}]
                for sub_key, sub_name in cat["subs"].items():
                    sub_options.append({"n": sub_name, "v": sub_key})
                filters[cat["type_id"]] = [{
                    "key": "sub",
                    "name": "类型",
                    "value": sub_options,
                }]
        result["class"] = classes
        result["filters"] = filters
        return result

    def homeVideoContent(self):
        """首页推荐"""
        html = self._fetch("/")
        return {"list": self._parse_list(html)}

    # ===== 分类列表 =====

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        extend = extend or {}
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}

        sub = extend.get("sub", "") or ""
        base_path = "/{0}/{1}/".format(tid, sub) if sub else "/{0}/".format(tid)

        # 翻页URL: /Movie/index2.html
        if page <= 1:
            path = base_path + "index.html"
        else:
            path = base_path + "index{0}.html".format(page)

        html = self._fetch(path)
        videos = self._parse_list(html)

        # 判断是否有下一页
        has_next = False
        if videos:
            # 检查分页区域中是否有下一页链接
            next_page_num = page + 1
            if sub:
                next_pattern = 'href="/{0}/{1}/index{2}.html"'.format(tid, sub, next_page_num)
            else:
                next_pattern = 'href="/{0}/index{1}.html"'.format(tid, next_page_num)
            has_next = next_pattern in html

        result = {
            "list": videos,
            "page": page,
            "pagecount": 9999 if has_next else page,
            "limit": len(videos),
            "total": 9999,
        }
        return result

    # ===== HTML解析 =====

    def _parse_list(self, html):
        """解析视频卡片列表"""
        results = []
        seen = set()

        # 卡片: <li data-href="/Movie/jqp/slug/" data-tid="...">
        pattern = re.compile(
            r'<li[^>]*data-href="([^"]+)"[^>]*>(.*?)</li>',
            re.DOTALL
        )
        for match in pattern.finditer(html):
            path = match.group(1)
            content = match.group(2)

            if path in seen:
                continue
            seen.add(path)

            # 标题
            title = ""
            title_m = re.search(r'<img[^>]*title="([^"]+)"', content)
            if title_m:
                title = title_m.group(1).strip()
            if not title:
                title_m2 = re.search(r'<h2[^>]*>.*?<a[^>]*>(.*?)</a>', content, re.DOTALL)
                if title_m2:
                    title = re.sub(r'<[^>]+>', '', title_m2.group(1)).strip()
            if not title:
                continue

            # 封面图
            pic_m = re.search(r'<img[^>]*src="([^"]+)"', content)
            pic = pic_m.group(1) if pic_m else ""

            # 备注
            remark = ""
            remark_m = re.search(r'<span[^>]*class="hdtag"[^>]*>([^<]+)</span>', content)
            if remark_m:
                remark = remark_m.group(1).strip()

            results.append({
                "vod_name": title,
                "vod_id": path,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return results

    # ===== 详情页 =====

    def detailContent(self, ids):
        vid = ids[0] if ids else ""
        html = self._fetch(vid)

        if not html:
            return {}

        vod = {
            "vod_id": vid,
            "vod_name": "",
            "vod_pic": "",
            "vod_year": "",
            "vod_area": "",
            "vod_class": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_writer": "",
            "vod_content": "",
            "vod_remarks": "",
            "vod_play_from": "",
            "vod_play_url": "",
        }

        # 封面
        og_img = re.search(r'og:image"\s+content="([^"]+)"', html)
        if og_img:
            vod["vod_pic"] = og_img.group(1)

        # 影片信息 (◎标记)
        info_map = {
            "影片片名": "vod_name",
            "影片导演": "vod_director",
            "影片编剧": "vod_writer",
            "影片主演": "vod_actor",
            "影片分类": "vod_class",
            "影片地区": "vod_area",
            "上映年份": "vod_year",
            "影片备注": "vod_remarks",
        }
        for line in re.finditer(r'◎(.+?)[：:]\s*', html):
            key = line.group(1).strip()
            # 值在 </span><b> 标签中，需要跳过 </span> 等标签
            val_start = line.end()
            # 查找下一个 <b> 标签
            b_match = re.search(r'<b[^>]*>(.*?)</b>', html[val_start:])
            if b_match:
                val = html_unescape(b_match.group(1).strip())
            else:
                val = ""
            if key == "上映年份":
                year_m = re.match(r'(\d{4})', val)
                if year_m:
                    val = year_m.group(1)
            field = info_map.get(key)
            if field and val:
                vod[field] = val

        # 简介
        desc_m = re.search(r'◎影片简介:\s*</?\w*[^>]*>\s*([^<\n]+)', html)
        if desc_m:
            vod["vod_content"] = html_unescape(desc_m.group(1).strip())
        if not vod["vod_content"]:
            desc_m2 = re.search(r'og:description"\s+content="([^"]+)"', html)
            if desc_m2:
                vod["vod_content"] = html_unescape(desc_m2.group(1).strip())

        # 片名兜底
        if not vod["vod_name"]:
            # 尝试 og:title
            og_title = re.search(r'og:title"\s+content="([^"]+)"', html)
            if og_title:
                vod["vod_name"] = og_title.group(1).strip()
        if not vod["vod_name"]:
            # 尝试 <title> 标签
            title_m = re.search(r'<title>(.*?)__', html)
            if title_m:
                vod["vod_name"] = title_m.group(1).strip()
        if not vod["vod_name"]:
            title_m2 = re.search(r'<title>《([^》]+)》', html)
            if title_m2:
                vod["vod_name"] = title_m2.group(1)

        # 播放列表 - 从 episode-list ul 元素中按线路分组解析
        # 每个 episode-list ul 对应一个线路
        episode_lists = re.findall(r'<ul class="episode-list">(.*?)</ul>', html, re.DOTALL)

        line_names = {}
        line_names[0] = "线路一"
        line_names[1] = "线路二"

        play_from_list = []
        play_url_parts = []
        for lid, ep_list_html in enumerate(episode_lists):
            eps = []
            # 解析每个 li > a 标签
            for ep_match in re.finditer(r'<li[^>]*><a[^>]*title="([^"]*)"[^>]*href="([^"]+)"[^>]*>(.*?)</a></li>', ep_list_html, re.DOTALL):
                ep_name = ep_match.group(1).strip()
                play_path = ep_match.group(2).strip()
                if not ep_name:
                    ep_name = ep_match.group(3).strip()
                if not ep_name:
                    ep_name = "第{0:02d}集".format(len(eps) + 1)
                # 从 href 中提取集数索引: play-{line_id}-{ep_index}.html
                ep_idx_match = re.search(r'play-\d+-(\d+)\.html', play_path)
                ep_index = int(ep_idx_match.group(1)) if ep_idx_match else len(eps)
                eps.append((ep_index, ep_name, play_path))

            if not eps:
                continue
            eps.sort(key=lambda x: x[0])
            name = line_names.get(lid, "线路{0}".format(lid))
            play_from_list.append(name)
            play_url_parts.append("#".join("{0}${1}".format(n, p) for _, n, p in eps))

        vod["vod_play_from"] = "$$$".join(play_from_list)
        vod["vod_play_url"] = "$$$".join(play_url_parts)

        return {"list": [vod]}

    # ===== 播放 =====

    def playerContent(self, flag, id, vipFlags):
        url = id if id.startswith("http") else (self.host + id)
        html = self._fetch(url.replace(self.host, ""))

        result = {
            "parse": 0,
            "header": self._play_header,
            "url": "",
            "playUrl": "",
        }

        if not html:
            return result

        # 方式1: var now = base64decode("...")
        m = re.search(r'var\s+now\s*=\s*base64decode\(\s*"([A-Za-z0-9+/=]+)"\s*\)', html)
        if m:
            try:
                decoded = base64.b64decode(m.group(1)).decode("utf-8")
                if decoded.startswith("http") and (".m3u8" in decoded or ".mp4" in decoded):
                    result["url"] = decoded
                    return result
            except Exception:
                pass

        # 方式2: player_aaaa = {"url":"...", "encrypt":1}
        m2 = re.search(r'player_aaaa\s*=\s*(\{.*?\})', html, re.DOTALL)
        if m2:
            try:
                player = json.loads(m2.group(1))
                play_url = player.get("url", "")
                encrypt = player.get("encrypt", 0)
                if encrypt == 1:
                    play_url = urllib.parse.unquote(play_url)
                elif encrypt == 2:
                    play_url = base64.b64decode(play_url).decode("utf-8")
                if play_url and (".m3u8" in play_url or ".mp4" in play_url):
                    result["url"] = play_url
                    return result
            except Exception:
                pass

        # 方式3: 直接搜m3u8
        m3 = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
        if m3:
            result["url"] = m3.group(1)
            return result

        # 方式4: 直接搜mp4
        m4 = re.search(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html)
        if m4:
            result["url"] = m4.group(1)

        return result

    # ===== 搜索 =====

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        if page > 1:
            return {"list": []}

        key = key.strip().lower()
        if not key:
            return {"list": []}

        items = self._load_rss_index()
        results = []

        for item in items:
            title = item["title"]
            if key in title.lower() or key in item.get("desc", "").lower():
                results.append({
                    "vod_name": title,
                    "vod_id": item["path"],
                    "vod_pic": "",
                    "vod_remarks": "",
                })
            if len(results) >= 30:
                break

        return {"list": results}

    def _load_rss_index(self):
        """加载RSS订阅作为搜索索引 (缓存5分钟)"""
        now = time.time()
        if self._rss_cache is not None and (now - self._rss_cache_time) < 300:
            return self._rss_cache

        xml = self._fetch("/xml/rss.xml")
        if not xml:
            return []

        items = []
        for m in re.finditer(r'<item>(.*?)</item>', xml, re.DOTALL):
            item = m.group(1)
            title_m = re.search(r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', item, re.DOTALL)
            link_m = re.search(r'<link>(.*?)</link>', item, re.DOTALL)
            desc_m = re.search(r'<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>', item, re.DOTALL)

            if title_m and link_m:
                title = html_unescape(title_m.group(1).strip())
                link = link_m.group(1).strip()
                path = link
                # 去除可能的域名前缀 (支持多个域名)
                for host in [self.host, "https://www.au1080.top", "http://www.au1080.top"]:
                    path = path.replace(host, "")
                if not path.startswith("/"):
                    path = "/" + path
                desc = ""
                if desc_m:
                    desc = html_unescape(desc_m.group(1).strip())

                items.append({
                    "title": title,
                    "path": path,
                    "desc": desc,
                })

        self._rss_cache = items
        self._rss_cache_time = now
        return items


if __name__ == "__main__":
    # 本地测试
    s = Spider()
    s.init()

    print("===== 首页分类 =====")
    home = s.homeContent(True)
    print("分类数:", len(home.get("class", [])))
    for c in home.get("class", []):
        print("  {0} -> {1}".format(c["type_name"], c["type_id"]))

    print("\n===== 首页推荐 =====")
    rec = s.homeVideoContent()
    print("推荐视频数:", len(rec.get("list", [])))
    for v in rec.get("list", [])[:3]:
        print("  [{0}] {1} - {2}".format(v["vod_id"], v["vod_name"], v["vod_remarks"]))

    print("\n===== 分类列表 (电影第1页) =====")
    cat = s.categoryContent("Movie", "1", True, {})
    print("返回视频数:", len(cat.get("list", [])))
    for v in cat.get("list", [])[:3]:
        print("  [{0}] {1} - {2}".format(v["vod_id"], v["vod_name"], v["vod_remarks"]))

    print("\n===== 详情页 (重器) =====")
    detail = s.detailContent(["/Tv/neidi/zhongqi/"])
    if detail.get("list"):
        vod = detail["list"][0]
        print("  标题:", vod["vod_name"])
        print("  年份:", vod["vod_year"])
        print("  导演:", vod["vod_director"])
        print("  备注:", vod["vod_remarks"])
        pf = vod["vod_play_from"].split("$$$")
        pu = vod["vod_play_url"].split("$$$")
        for i, name in enumerate(pf):
            eps = pu[i].split("#") if i < len(pu) else []
            print("  {0}: {1}集".format(name, len(eps)))
            for ep in eps[:2]:
                parts = ep.split("$")
                print("    {0} -> {1}".format(parts[0], parts[1]))

    print("\n===== 播放测试 (云播X 第1集) =====")
    play = s.playerContent("云播X线", "/Tv/neidi/zhongqi/play-1-0.html", [])
    print("  URL:", play.get("url", "")[:80], "...")
    print("  Parse:", play.get("parse"))

    print("\n===== 搜索 (恋爱) =====")
    search = s.searchContent("恋爱", False)
    print("搜索结果数:", len(search.get("list", [])))
    for v in search.get("list", [])[:5]:
        print("  [{0}] {1}".format(v["vod_id"], v["vod_name"]))