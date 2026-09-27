# -*- coding: utf-8 -*-
"""
==========================================================
  柠檬视频 (nmsp1.cc) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎)
  框架: 自定义CMS (模板风格类似 maccms-conch 变体)
  更新: 2026-08-12

  多域名支持: nmsp1~9.cc, init时自动测速选最快域名
  搜索优化: 6个分类并行请求, 速度提升6倍
  连接优化: SSL上下文复用, 超时缩短至8秒

  URL规则:
    首页: /
    分类页: /list/{slug}/  (导航: dianying/juji/duanju/zongyi/dongman/jilupian)
    筛选页: /show-{type}-{area}-{by}-{class}------{page}---{year}/
    详情页: /video/{vid}/
    播放页: /play/{vid}-{sid}-{nid}/
    搜索页: /show-{type}-----------?wd={keyword}  (并行遍历分类)

  播放源: RY/BF/HD/FF/LZ/UK(直链m3u8) + TX/YK/QY(平台源parse=1)
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
import socket
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import quote, unquote
from html import unescape as html_unescape
from threading import Thread


class Spider(Spider):

    # 多域名列表 (从站点首页确认: nmsp1~9.cc)
    DOMAINS = [
        "https://nmsp1.cc",
        "https://nmsp2.cc",
        "https://nmsp3.cc",
        "https://nmsp4.cc",
        "https://nmsp5.cc",
        "https://nmsp6.cc",
        "https://nmsp7.cc",
        "https://nmsp8.cc",
        "https://nmsp9.cc",
    ]

    UA = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # 主分类
    CATEGORIES = [
        {"type_name": "电影", "type_id": "dianying"},
        {"type_name": "电视剧", "type_id": "juji"},
        {"type_name": "短剧", "type_id": "duanju"},
        {"type_name": "综艺", "type_id": "zongyi"},
        {"type_name": "动漫", "type_id": "dongman"},
        {"type_name": "纪录片", "type_id": "jilupian"},
    ]

    # 筛选选项
    FILTER_AREA = ["中国大陆", "中国香港", "中国台湾", "美国", "韩国", "日本", "泰国",
                   "新加坡", "马来西亚", "印度", "英国", "法国", "加拿大", "俄罗斯", "澳大利亚"]

    FILTER_CLASS = ["剧情", "喜剧", "动作", "爱情", "科幻", "动画", "悬疑", "惊悚",
                    "恐怖", "犯罪", "同性", "历史", "战争", "奇幻", "冒险", "灾难",
                    "武侠", "古装", "短片", "Netflix"]

    FILTER_YEAR = ["2026", "2025", "2024", "2023", "2022", "2021", "2020",
                   "2019", "2018", "2017", "2016", "2015", "2014", "2013",
                   "2012", "2011", "2010", "2009", "2008", "2007", "2006", "2005"]

    # 平台源 from 字段 (需解析, 非直链)
    PLATFORM_SOURCES = {"qq", "qiyi", "youku", "mgtv", "sohu", "xigua", "bilibili"}

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
        return "柠檬视频"

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
                # 用TCP连接测速 (比HTTP请求更快)
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

        # 选最快的
        best = min(results, key=results.get) if results else self.DOMAINS[0]
        if results.get(best, 999) >= 999:
            # 全部失败, 用默认
            return self.DOMAINS[0]
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
            # 主域名失败时尝试备用域名
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
        """首页推荐内容"""
        html = self._fetch("/show-dianying--time---------/")
        videos = self._parse_cards(html)
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
                          {"n": "最多播放", "v": "hits"},
                          {"n": "实时热门", "v": "hits_day"},
                          {"n": "近期热播", "v": "hits_week"},
                          {"n": "新片上线", "v": "year"}]
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

        def enc(v):
            return quote(v, safe='') if v else ""
        page_str = str(page) if page > 1 else ""
        parts = [tid, enc(area), enc(by), enc(cls), "", "", "", "", page_str, "", "", enc(year)]
        path = "/show-" + "-".join(parts) + "/"

        html = self._fetch(path)
        videos = self._parse_cards(html)

        pagecount = self._parse_pagecount(html)
        if not pagecount:
            pagecount = page + 1 if len(videos) >= 20 else page

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20,
        }

    def _parse_pagecount(self, html):
        """从分页区域解析总页数"""
        pages = re.findall(r'/show-[^"]*--------(\d+)---/', html)
        if pages:
            return max(int(p) for p in pages)
        last = re.search(r'class="page-link page-next"[^>]*href="/show-[^"]*--------(\d+)---"', html)
        if last:
            return int(last.group(1))
        return 0

    def _parse_cards(self, html):
        """解析视频卡片列表"""
        videos = []
        for m in re.finditer(r'<a[^>]*href="/video/(\d+)/"[^>]*class="module-poster-item[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL):
            vid = m.group(1)
            full_tag = m.group(0)
            inner = m.group(2)

            # 标题
            name = ""
            titles = re.findall(r'title="([^"]*)"', full_tag)
            for t in titles:
                if t.strip():
                    name = html_unescape(t.strip())
                    break
            if not name:
                alt_m = re.search(r'alt="([^"]*)"', inner)
                if alt_m:
                    name = html_unescape(alt_m.group(1).strip())
            if not name:
                title_m = re.search(r'module-poster-item-title">(.*?)</div>', inner, re.DOTALL)
                if title_m:
                    name = html_unescape(re.sub(r'<[^>]+>', '', title_m.group(1)).strip())

            # 封面图
            pic_m = re.search(r'data-src="([^"]*)"', inner)
            pic = pic_m.group(1) if pic_m else ""

            # 备注
            note_m = re.search(r'module-item-note">(.*?)<', inner, re.DOTALL)
            remarks = html_unescape(note_m.group(1).strip()) if note_m else ""

            videos.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })
        return videos

    # ===== 详情页 =====

    def detailContent(self, ids):
        vid = ids[0]
        html = self._fetch("/video/" + str(vid) + "/")

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
        title_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        if title_m:
            vod["vod_name"] = html_unescape(title_m.group(1).strip())

        # 封面图
        pic_m = re.search(r'class="module-item-pic"[^>]*>.*?data-src="([^"]*)"', html, re.DOTALL)
        if pic_m:
            vod["vod_pic"] = pic_m.group(1)

        # 标签 (年份/地区/类型)
        tags = re.findall(r'class="module-info-tag-link"[^>]*>.*?title="([^"]*)"', html, re.DOTALL)
        if len(tags) >= 1:
            vod["vod_year"] = tags[0]
        if len(tags) >= 2:
            vod["vod_area"] = tags[1]
        if len(tags) >= 3:
            vod["vod_class"] = tags[2]

        # 元数据项
        info_items = re.findall(
            r'<span class="module-info-item-title">(.*?)</span>\s*<div class="module-info-item-content">(.*?)</div>',
            html, re.DOTALL
        )
        for label_html, value_html in info_items:
            label = html_unescape(re.sub(r'<[^>]+>', '', label_html).strip())
            links = re.findall(r'>([^<]+)<', value_html)
            value = " ".join(html_unescape(l.strip()) for l in links if l.strip())
            if not value:
                value = html_unescape(re.sub(r'<[^>]+>', '', value_html).strip())

            if "导演" in label:
                vod["vod_director"] = value
            elif "编剧" in label:
                vod["vod_writer"] = value
            elif "主演" in label:
                vod["vod_actor"] = value
            elif "集数" in label or "状态" in label:
                vod["vod_remarks"] = value

        # 简介
        desc_m = re.search(r'class="module-info-introduction-content"[^>]*>(.*?)</div>', html, re.DOTALL)
        if desc_m:
            vod["vod_content"] = html_unescape(re.sub(r'<[^>]+>', '', desc_m.group(1)).strip())

        # 播放源
        play_from_list = []
        play_url_list = []

        sources = re.findall(
            r'aria-controls="panel(\d+)"[^>]*>.*?data-dropdown-value="([^"]*)"',
            html, re.DOTALL
        )

        for sid, source_name in sources:
            panel_pattern = r'id="panel' + sid + r'"[^>]*>(.*?)</div>\s*</div>\s*</div>'
            panel_m = re.search(panel_pattern, html, re.DOTALL)
            if not panel_m:
                panel_pattern = r'id="panel' + sid + r'"[^>]*>(.*?)(?=<div[^>]*id="panel|<div[^>]*class="module-player-handle|$)'
                panel_m = re.search(panel_pattern, html, re.DOTALL)

            if panel_m:
                panel_html = panel_m.group(1)
                episodes = re.findall(
                    r'href="(/play/\d+-' + sid + r'-\d+/)"[^>]*>.*?<span>(.*?)</span>',
                    panel_html, re.DOTALL
                )
                if not episodes:
                    episodes = re.findall(
                        r'href="(/play/\d+-' + sid + r'-\d+/)"[^>]*title="([^"]*)"',
                        panel_html, re.DOTALL
                    )

                if episodes:
                    ep_names = []
                    for url, ep_name in episodes:
                        name = html_unescape(ep_name.strip())
                        if not name:
                            nid_m = re.search(r'-(\d+)/', url)
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

        html = self._fetch(play_url.replace(self.host, ""))

        result = {
            "parse": 0,
            "header": self._play_header,
            "url": "",
            "playUrl": "",
        }

        if not html:
            return result

        # 提取 player_aaaa
        m = re.search(r'player_aaaa\s*=\s*(\{.*?\})', html)
        if not m:
            return result

        try:
            player = json.loads(m.group(1))
        except Exception:
            return result

        encrypt = player.get("encrypt", 0)
        raw_url = player.get("url", "")
        from_field = player.get("from", "")

        if encrypt == 1:
            decoded = unquote(raw_url)
        elif encrypt == 2:
            import base64
            try:
                decoded = base64.b64decode(raw_url).decode('utf-8')
            except Exception:
                decoded = raw_url
        else:
            decoded = raw_url

        # 方式1: 提取m3u8/mp4直链
        m3u8_m = re.search(r'(https?://[^\s"&\']+\.m3u8[^\s"&\']*)', decoded)
        mp4_m = re.search(r'(https?://[^\s"&\']+\.mp4[^\s"&\']*)', decoded)
        if m3u8_m:
            result["url"] = m3u8_m.group(1)
            return result
        if mp4_m:
            result["url"] = mp4_m.group(1)
            return result

        # 方式2: 平台源URL, 需解析器播放
        if from_field in self.PLATFORM_SOURCES:
            platform_url = decoded.split("&")[0]
            if platform_url.startswith("http"):
                result["parse"] = 1
                result["url"] = platform_url
                return result

        return result

    # ===== 搜索 (并行优化) =====

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        key = key.strip()
        if not key:
            return {"list": []}

        # 并行搜索所有分类
        results = []
        results_lock = []

        def _search_category(tid):
            path = "/show-" + tid + "-----------"
            params = {"wd": key}
            if page > 1:
                path = "/show-" + tid + "--------" + str(page) + "---"
            html = self._fetch(path, params)
            videos = self._parse_cards(html)
            results_lock.append(videos)

        threads = []
        for cat in self.CATEGORIES:
            t = Thread(target=_search_category, args=(cat["type_id"],))
            t.daemon = True
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=10)

        # 合并结果
        for videos in results_lock:
            for v in videos:
                results.append({
                    "vod_id": v["vod_id"],
                    "vod_name": v["vod_name"],
                    "vod_pic": v["vod_pic"],
                    "vod_remarks": v["vod_remarks"],
                })

        # 去重
        seen = set()
        unique = []
        for r in results:
            if r["vod_id"] not in seen:
                seen.add(r["vod_id"])
                unique.append(r)

        return {"list": unique[:30], "page": page}


if __name__ == "__main__":
    import time as _time

    s = Spider()
    s.init()
    print("选中域名:", s.host)

    print("\n===== 首页分类 =====")
    home = s.homeContent(True)
    print("分类数:", len(home.get("class", [])))

    t0 = _time.time()
    print("\n===== 分类列表 (电影第1页) =====")
    cat = s.categoryContent("dianying", "1", True, {})
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s, 返回: {len(cat.get('list', []))}条")
    for v in cat.get("list", [])[:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    t0 = _time.time()
    print("\n===== 详情页 (281259) =====")
    detail = s.detailContent(["281259"])
    t1 = _time.time()
    if detail.get("list"):
        vod = detail["list"][0]
        print(f"耗时: {t1-t0:.2f}s")
        print(f"  标题: {vod['vod_name']}")
        print(f"  播放源: {vod['vod_play_from']}")
        pu = vod['vod_play_url'].split('$$$')
        if pu:
            for ep in pu[0].split('#')[:3]:
                print(f"    {ep}")

    t0 = _time.time()
    print("\n===== 播放 (281259-1-1) =====")
    play = s.playerContent("UK源", "/play/281259-1-1/", [])
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
    print("\n===== 搜索 (莫得闲) =====")
    search2 = s.searchContent("莫得闲", False)
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s, 结果: {len(search2.get('list', []))}条")
    for v in search2.get("list", []):
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")
