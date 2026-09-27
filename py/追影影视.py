# -*- coding: utf-8 -*-
"""
==========================================================
  追影视频 (zhuiying3.cc) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎)
  框架: maccms10 变体 (自定义模板 v6)
  更新: 2026-08-15

  多域名支持: zhuiying1~9.cc, init时自动测速选最快域名
  列表优化: 使用AJAX JSON接口, 无需解析HTML分页
  搜索优化: AJAX JSON接口, 单次请求获取全部分类结果
  播放优化: 加密解析接口 (MD5 token + base64反转解密)

  URL规则:
    首页: /
    分类页(HTML): /vodshow/{slug}-----------.html (仅首页, 后续走AJAX)
    分类AJAX: /index.php/ajax/vod_list?id={tid}&class=&area=&year=&by=&page=&limit=27
    详情页: /video/{vid}.html
    播放页: /play/{vid}-{sid}-{nid}.html
    搜索AJAX: /index.php/ajax/search_list?wd={keyword}&page=&limit=10

  播放解析: 播放页提取 MAC_PLAY_CONFIG (baseKey+requestUrl)
            → MD5(baseKey+timestamp+UA) 生成token
            → POST /player_api.php → 反转+base64解码 → {jmurl, urltype}

  分类ID: 电影=1, 电视剧=2, 综艺=3, 动漫=4, 短剧=26
  播放源: BD/MD/BF/LZ/NB等 (均为直链m3u8, parse=0)
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
import time
import base64
import hashlib
import socket
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import quote, unquote
from html import unescape as html_unescape
from threading import Thread


class Spider(Spider):

    # 多域名列表 (从站点确认: zhuiying1~9.cc)
    DOMAINS = [
        "https://zhuiying1.cc",
        "https://zhuiying2.cc",
        "https://zhuiying3.cc",
        "https://zhuiying4.cc",
        "https://zhuiying5.cc",
        "https://zhuiying6.cc",
        "https://zhuiying7.cc",
        "https://zhuiying8.cc",
        "https://zhuiying9.cc",
    ]

    UA = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # 主分类 (type_id为maccms数字分类ID)
    CATEGORIES = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "电视剧", "type_id": "2"},
        {"type_name": "综艺", "type_id": "3"},
        {"type_name": "动漫", "type_id": "4"},
        {"type_name": "短剧", "type_id": "26"},
    ]

    # 筛选选项 (从站点vodshow页面提取)
    FILTER_AREA = ["中国大陆", "中国香港", "中国台湾", "美国", "日本", "韩国",
                   "泰国", "英国", "法国", "德国", "意大利", "印度", "马来西亚"]

    FILTER_CLASS = ["剧情", "喜剧", "动作", "爱情", "科幻", "动画", "悬疑", "惊悚",
                    "恐怖", "犯罪", "谍战", "历史", "战争", "奇幻", "冒险", "灾难",
                    "武侠", "古装", "家庭", "青春", "短片", "纪录", "人物", "文化", "其他"]

    FILTER_YEAR = ["2026", "2025", "2024", "2023", "2022", "2021", "2020",
                   "2019", "2018", "2017", "2016", "2015", "2014", "2013",
                   "2012", "2011", "2010", "2009", "2008", "2007", "2006",
                   "2005", "2004", "2003", "2002", "2001", "2000",
                   "90年代", "80年代", "70年代", "其他"]

    def init(self, extend=""):
        self.ua = self.UA
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        # SSL上下文复用 (避免每次请求重新握手)
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

        # 自动选择最快域名
        self.host = self._select_fastest_domain()
        self.headers["Referer"] = self.host + "/"
        self._play_header = json.dumps({
            "User-Agent": self.ua,
            "Referer": self.host + "/",
        })

    def getName(self):
        return "追影视频"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|ts)(\?|#|$)', url, re.I))

    def manualVideoVCandidate(self, items):
        return []

    # ===== 域名选择 =====

    def _select_fastest_domain(self):
        """并行测速选择最快域名, 失败则用默认域名"""
        results = {}
        threads = []

        def _test_domain(domain):
            try:
                parsed = urllib.parse.urlparse(domain)
                host = parsed.hostname
                port = parsed.port or 443
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                t0 = time.time()
                sock.connect((host, port))
                t1 = time.time()
                sock.close()
                results[domain] = t1 - t0
            except Exception:
                results[domain] = 999

        for domain in self.DOMAINS:
            t = Thread(target=_test_domain, args=(domain,))
            t.daemon = True
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=3)

        best = min(results, key=results.get) if results else self.DOMAINS[0]
        if results.get(best, 999) >= 999:
            return self.DOMAINS[2]
        return best

    # ===== HTTP辅助 =====

    def _fetch(self, path, params=None, host=None, timeout=8):
        """获取页面HTML"""
        base = host or self.host
        url = base + path
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, headers=self.headers)
            resp = urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx)
            data = resp.read()
            charset = 'utf-8'
            content_type = resp.headers.get('Content-Type', '')
            if 'charset=' in content_type:
                charset = content_type.split('charset=')[-1].strip()
            try:
                return data.decode(charset, errors='replace')
            except Exception:
                return data.decode('utf-8', errors='replace')
        except Exception:
            if host is None and base == self.host:
                for alt in self.DOMAINS:
                    if alt == self.host:
                        continue
                    try:
                        alt_url = alt + path
                        if params:
                            alt_url = alt_url + "?" + urllib.parse.urlencode(params)
                        req = urllib.request.Request(alt_url, headers=self.headers)
                        resp = urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx)
                        data = resp.read()
                        charset = 'utf-8'
                        content_type = resp.headers.get('Content-Type', '')
                        if 'charset=' in content_type:
                            charset = content_type.split('charset=')[-1].strip()
                        try:
                            return data.decode(charset, errors='replace')
                        except Exception:
                            return data.decode('utf-8', errors='replace')
                    except Exception:
                        continue
            return ""

    def _fetch_json(self, path, params=None, referer=None, timeout=8):
        """获取AJAX JSON接口数据"""
        base = self.host
        url = base + path
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        headers = dict(self.headers)
        headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
        headers["X-Requested-With"] = "XMLHttpRequest"
        if referer:
            headers["Referer"] = referer
        else:
            headers["Referer"] = base + "/"
        try:
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx)
            data = resp.read().decode('utf-8', errors='replace')
            return json.loads(data)
        except Exception:
            return {}

    def _post_json(self, path, post_data, referer=None, timeout=10):
        """POST请求获取JSON"""
        base = self.host
        url = base + path
        headers = dict(self.headers)
        headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["X-Requested-With"] = "XMLHttpRequest"
        if referer:
            headers["Referer"] = referer
        else:
            headers["Referer"] = base + "/"
        try:
            body = urllib.parse.urlencode(post_data).encode('utf-8')
            req = urllib.request.Request(url, data=body, headers=headers)
            resp = urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx)
            data = resp.read().decode('utf-8', errors='replace')
            return json.loads(data)
        except Exception:
            return {}

    # ===== 首页 =====

    def homeContent(self, filter):
        result = {}
        classes = []
        for c in self.CATEGORIES:
            classes.append({"type_name": c["type_name"], "type_id": c["type_id"]})
        result["class"] = classes
        result["filters"] = self._get_filters()
        return result

    def homeVideoContent(self):
        """首页推荐内容 - 使用AJAX接口获取最新电影"""
        res = self._fetch_json("/index.php/ajax/vod_list", {
            "id": "1", "by": "time", "page": 1, "limit": 30
        })
        videos = self._parse_ajax_list(res)
        return {"list": videos[:30]}

    def _get_filters(self):
        """生成筛选器配置"""
        filters = {}
        common = [
            {
                "key": "area",
                "name": "地区",
                "value": [{"n": "全部", "v": ""}] +
                         [{"n": a, "v": a} for a in self.FILTER_AREA]
            },
            {
                "key": "class",
                "name": "类型",
                "value": [{"n": "全部", "v": ""}] +
                         [{"n": c, "v": c} for c in self.FILTER_CLASS]
            },
            {
                "key": "year",
                "name": "年份",
                "value": [{"n": "全部", "v": ""}] +
                         [{"n": y, "v": y} for y in self.FILTER_YEAR]
            },
            {
                "key": "by",
                "name": "排序",
                "value": [{"n": "更新时间", "v": "time"},
                          {"n": "近期热播", "v": "hits_week"},
                          {"n": "最新上线", "v": "id"},
                          {"n": "豆瓣评分", "v": "douban_score"}]
            },
        ]
        for c in self.CATEGORIES:
            filters[c["type_id"]] = common
        return filters

    # ===== 分类列表 =====

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        extend = extend or {}

        area = extend.get("area", "")
        by = extend.get("by", "")
        cls = extend.get("class", "")
        year = extend.get("year", "")

        res = self._fetch_json("/index.php/ajax/vod_list", {
            "id": tid,
            "class": cls,
            "area": area,
            "year": year,
            "by": by,
            "page": page,
            "limit": 27,
        })

        videos = self._parse_ajax_list(res)

        pagecount = res.get("pagecount", 0) or 0
        if not pagecount:
            pagecount = page + 1 if len(videos) >= 20 else page

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 27,
            "total": pagecount * 27,
        }

    def _parse_ajax_list(self, res):
        """解析AJAX列表JSON为视频卡片"""
        videos = []
        for item in res.get("list", []):
            vod_url = item.get("vod_url", "")
            # 从 /video/{slug}.html 提取slug作为vod_id
            slug_m = re.search(r'/video/([^.]+)\.html', vod_url)
            vid = slug_m.group(1) if slug_m else str(item.get("vod_id", ""))

            videos.append({
                "vod_id": vid,
                "vod_name": item.get("vod_name", ""),
                "vod_pic": item.get("vod_pic", ""),
                "vod_remarks": item.get("vod_remarks", ""),
            })
        return videos

    # ===== 详情页 =====

    def detailContent(self, ids):
        vid = ids[0]
        html = self._fetch("/video/" + str(vid) + ".html")

        if not html:
            return {}

        vod = {
            "vod_id": vid,
            "vod_name": "",
            "vod_pic": "",
            "vod_year": "",
            "vod_area": "",
            "vod_class": "",
            "vod_director": "",
            "vod_actor": "",
            "vod_writer": "",
            "vod_content": "",
            "vod_remarks": "",
            "vod_play_from": "",
            "vod_play_url": "",
        }

        # 标题
        title_m = re.search(r'<h1[^>]*class="detail-title"[^>]*>(.*?)</h1>', html, re.DOTALL)
        if title_m:
            vod["vod_name"] = html_unescape(title_m.group(1).strip())

        # 年份
        year_m = re.search(r'class="detail-year"[^>]*>\(([^)]*)\)', html)
        if year_m:
            vod["vod_year"] = html_unescape(year_m.group(1).strip())

        # 封面图
        pic_m = re.search(r'<img[^>]*class="detail-poster"[^>]*src="([^"]*)"', html)
        if pic_m:
            vod["vod_pic"] = pic_m.group(1)

        # 备注 (poster-badge)
        badge_m = re.search(r'class="poster-badge"[^>]*>(.*?)<', html, re.DOTALL)
        if badge_m:
            vod["vod_remarks"] = html_unescape(badge_m.group(1).strip())

        # 元数据矩阵 (类型/制片国家/片长等)
        # 提取hero-meta-matrix区块, 再按m-val/m-lbl配对
        matrix_m = re.search(r'class="hero-meta-matrix"[^>]*>(.*?)(?=<div class="cast-info")', html, re.DOTALL)
        if matrix_m:
            matrix_html = matrix_m.group(1)
            vals = re.findall(r'<span class="m-val[^"]*"[^>]*>(.*?)</span>', matrix_html, re.DOTALL)
            lbls = re.findall(r'<span class="m-lbl"[^>]*>(.*?)</span>', matrix_html, re.DOTALL)
            for i in range(min(len(vals), len(lbls))):
                val = html_unescape(re.sub(r'<[^>]+>', '', vals[i]).strip())
                lbl = html_unescape(re.sub(r'<[^>]+>', '', lbls[i]).strip())
                if "类型" in lbl:
                    vod["vod_class"] = val
                elif "制片" in lbl or "地区" in lbl:
                    vod["vod_area"] = val
                elif "片长" in lbl:
                    if not vod["vod_remarks"]:
                        vod["vod_remarks"] = val

        # 导演
        dir_m = re.search(
            r'<span class="label">导演:</span>\s*<span class="val[^"]*"[^>]*>(.*?)</span>',
            html, re.DOTALL
        )
        if dir_m:
            vod["vod_director"] = html_unescape(re.sub(r'<[^>]+>', '', dir_m.group(1)).strip())

        # 主演
        actor_m = re.search(
            r'<span class="label">主演:</span>\s*<div class="val[^"]*"[^>]*>(.*?)</div>',
            html, re.DOTALL
        )
        if actor_m:
            vod["vod_actor"] = html_unescape(re.sub(r'<[^>]+>', '', actor_m.group(1)).strip())

        # 简介
        desc_m = re.search(r'class="synopsis-text"[^>]*>(.*?)</div>', html, re.DOTALL)
        if desc_m:
            vod["vod_content"] = html_unescape(re.sub(r'<[^>]+>', '', desc_m.group(1)).strip())

        # 播放源
        play_from_list = []
        play_url_list = []

        # 提取播放源标签 (source-tab → data-target="ep-list-{sid}" → tab-name)
        sources = re.findall(
            r'class="source-tab"[^>]*data-target="ep-list-(\d+)"[^>]*>\s*<span class="tab-name">(.*?)</span>',
            html, re.DOTALL
        )

        for sid, source_name in sources:
            source_name = html_unescape(source_name.strip())

            # 提取对应集数列表
            ep_pattern = r'id="ep-list-' + sid + r'"[^>]*>(.*?)</div>'
            ep_m = re.search(ep_pattern, html, re.DOTALL)
            if not ep_m:
                continue

            ep_html = ep_m.group(1)
            episodes = re.findall(
                r'href="(/play/[^"]+\.html)"[^>]*class="ep-item-square"[^>]*data-name="([^"]*)"',
                ep_html, re.DOTALL
            )
            if not episodes:
                episodes = re.findall(
                    r'href="(/play/[^"]+\.html)"[^>]*class="ep-item-square"[^>]*>(.*?)</a>',
                    ep_html, re.DOTALL
                )

            if episodes:
                ep_names = []
                for url, ep_name in episodes:
                    name = html_unescape(ep_name.strip())
                    if not name:
                        nid_m = re.search(r'-(\d+)\.html', url)
                        name = "第" + nid_m.group(1) + "集" if nid_m else ""
                    ep_names.append(name + "$" + url)

                play_from_list.append(source_name)
                play_url_list.append("#".join(ep_names))

        vod["vod_play_from"] = "$$$".join(play_from_list)
        vod["vod_play_url"] = "$$$".join(play_url_list)

        return {"list": [vod]}

    # ===== 播放 =====

    def playerContent(self, flag, id, vipFlags):
        url = id
        if url.startswith("http"):
            play_url = url
        else:
            play_url = self.host + url

        # 获取播放页HTML
        path = play_url.replace(self.host, "")
        html = self._fetch(path)

        result = {
            "parse": 0,
            "header": self._play_header,
            "url": "",
            "playUrl": "",
        }

        if not html:
            return result

        # 提取 MAC_PLAY_CONFIG
        config_m = re.search(
            r'MAC_PLAY_CONFIG\s*=\s*\{(.*?)\};',
            html, re.DOTALL
        )
        if not config_m:
            return result

        config_str = config_m.group(1)
        base_key = ""
        request_url = ""

        bk_m = re.search(r'baseKey:\s*"([^"]*)"', config_str)
        if bk_m:
            base_key = bk_m.group(1)
        ru_m = re.search(r'requestUrl:\s*"([^"]*)"', config_str)
        if ru_m:
            request_url = ru_m.group(1)

        if not base_key or not request_url:
            return result

        # 计算token: md5(baseKey + timestamp + userAgent)
        timestamp = str(int(time.time()))
        token = hashlib.md5((base_key + timestamp + self.ua).encode('utf-8')).hexdigest()

        # POST请求解析接口
        referer = play_url
        res = self._post_json("/player_api.php", {
            "url": request_url,
            "timestamp": timestamp,
            "token": token,
        }, referer=referer)

        if not res or "data" not in res:
            return result

        try:
            # 解密: 反转字符串 → base64解码 → UTF-8 → JSON解析
            encoded = res["data"]
            reversed_data = encoded[::-1]
            decoded_bytes = base64.b64decode(reversed_data)
            decoded_str = decoded_bytes.decode('utf-8', errors='replace')
            parsed = json.loads(decoded_str)
        except Exception:
            return result

        jmurl = parsed.get("jmurl", "")
        urltype = parsed.get("urltype", "")

        if jmurl:
            result["url"] = jmurl
            # 判断是否为直链m3u8/mp4
            if jmurl.endswith(".m3u8") or ".m3u8" in jmurl or urltype in ("hls", "m3u8"):
                result["parse"] = 0
            elif jmurl.endswith(".mp4") or ".mp4" in jmurl:
                result["parse"] = 0
            else:
                # 非直链, 可能需要解析器
                result["parse"] = 1

        return result

    # ===== 搜索 =====

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        key = key.strip()
        if not key:
            return {"list": []}

        # 使用AJAX搜索接口
        search_referer = self.host + "/vod/search/wd/" + quote(key, safe='') + ".html"
        res = self._fetch_json("/index.php/ajax/search_list", {
            "wd": key,
            "page": page,
            "limit": 20,
        }, referer=search_referer)

        results = []
        for item in res.get("list", []):
            vod_url = item.get("vod_url", "")
            slug_m = re.search(r'/video/([^.]+)\.html', vod_url)
            vid = slug_m.group(1) if slug_m else str(item.get("vod_id", ""))

            results.append({
                "vod_id": vid,
                "vod_name": item.get("vod_name", ""),
                "vod_pic": item.get("vod_pic", ""),
                "vod_remarks": item.get("vod_remarks", ""),
            })

        return {"list": results[:30], "page": page}


if __name__ == "__main__":
    import time as _time

    s = Spider()
    s.init()
    print("选中域名:", s.host)

    print("\n===== 首页分类 =====")
    home = s.homeContent(True)
    print("分类数:", len(home.get("class", [])))
    for c in home.get("class", []):
        print(f"  {c['type_id']}: {c['type_name']}")

    t0 = _time.time()
    print("\n===== 首页推荐 =====")
    home_video = s.homeVideoContent()
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s, 返回: {len(home_video.get('list', []))}条")
    for v in home_video.get("list", [])[:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    t0 = _time.time()
    print("\n===== 分类列表 (电影第1页) =====")
    cat = s.categoryContent("1", "1", True, {})
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s, 返回: {len(cat.get('list', []))}条, 总页: {cat.get('pagecount')}")
    for v in cat.get("list", [])[:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    t0 = _time.time()
    print("\n===== 分类列表 (电视剧-筛选: 美国) =====")
    cat2 = s.categoryContent("2", "1", True, {"area": "美国"})
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s, 返回: {len(cat2.get('list', []))}条")
    for v in cat2.get("list", [])[:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    t0 = _time.time()
    print("\n===== 详情页 (RDdsp1StVc - 小黄人与大怪兽) =====")
    detail = s.detailContent(["RDdsp1StVc"])
    t1 = _time.time()
    if detail.get("list"):
        vod = detail["list"][0]
        print(f"耗时: {t1-t0:.2f}s")
        print(f"  标题: {vod['vod_name']}")
        print(f"  年份: {vod['vod_year']}")
        print(f"  地区: {vod['vod_area']}")
        print(f"  类型: {vod['vod_class']}")
        print(f"  导演: {vod['vod_director']}")
        print(f"  主演: {vod['vod_actor'][:50]}...")
        print(f"  简介: {vod['vod_content'][:50]}...")
        print(f"  播放源: {vod['vod_play_from']}")
        pu = vod['vod_play_url'].split('$$$')
        if pu:
            for ep in pu[0].split('#')[:5]:
                print(f"    {ep}")

    t0 = _time.time()
    print("\n===== 详情页 (B4FSXJ8xXv - 九门 多集) =====")
    detail2 = s.detailContent(["B4FSXJ8xXv"])
    t1 = _time.time()
    if detail2.get("list"):
        vod = detail2["list"][0]
        print(f"耗时: {t1-t0:.2f}s")
        print(f"  标题: {vod['vod_name']}")
        print(f"  播放源: {vod['vod_play_from']}")
        pu = vod['vod_play_url'].split('$$$')
        for i, src in enumerate(vod['vod_play_from'].split('$$$')):
            eps = pu[i].split('#') if i < len(pu) else []
            print(f"  {src}: {len(eps)}集, 前3集: {', '.join(eps[:3])}")

    t0 = _time.time()
    print("\n===== 播放 (RDdsp1StVc-1-1) =====")
    play = s.playerContent("MD源", "/play/RDdsp1StVc-1-1.html", [])
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s")
    print(f"  URL: {play.get('url', '')[:80]}")
    print(f"  Parse: {play.get('parse')}")

    t0 = _time.time()
    print("\n===== 搜索 (绝密任务) =====")
    search = s.searchContent("绝密任务", False)
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s, 结果: {len(search.get('list', []))}条")
    for v in search.get("list", []):
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    t0 = _time.time()
    print("\n===== 搜索 (九门) =====")
    search2 = s.searchContent("九门", False)
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s, 结果: {len(search2.get('list', []))}条")
    for v in search2.get("list", [])[:5]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")