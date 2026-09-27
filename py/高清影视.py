# -*- coding: utf-8 -*-
"""
==========================================================
  好看影视 (hkys3.cc) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎)
  框架: 自定义CMS (maccms-conch 变体)
  更新: 2026-08-19

  多域名支持: hkys2~9.cc, init时自动测速选最快域名
  搜索优化: 5个分类并行请求, 速度提升5倍
  连接优化: 仅HTTP(HTTPS返回403), 超时缩短至8秒

  URL规则:
    首页: /
    分类页: /v/{slug}/  (导航: dianying/dianshiju/duanju/zongyi/dongman)
    筛选页: /pianku-{type}-{area}-{by}-{class}-{lang}------{page}---{year}/
    详情页: /show-{vid}/
    播放页: /paly-{vid}-{sid}-{nid}/  (注意: paly 非笔误, 站点原始拼写)
    搜索页: /pianku-{type}-----------?wd={keyword}  (并行遍历分类)

  播放源: FF/RY/HD/BF/LZ/UK(直链m3u8, encrypt=1 URL编码) + 可能的平台源(parse=1)
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

    # 多域名列表 (从站点页脚确认: hkys2~9.cc, 仅HTTP)
    DOMAINS = [
        "http://hkys2.cc",
        "http://hkys3.cc",
        "http://hkys4.cc",
        "http://hkys5.cc",
        "http://hkys6.cc",
        "http://hkys7.cc",
        "http://hkys8.cc",
        "http://hkys9.cc",
    ]

    UA = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # 主分类
    CATEGORIES = [
        {"type_name": "电影", "type_id": "dianying"},
        {"type_name": "电视剧", "type_id": "dianshiju"},
        {"type_name": "短剧", "type_id": "duanju"},
        {"type_name": "综艺", "type_id": "zongyi"},
        {"type_name": "动漫", "type_id": "dongman"},
    ]

    # 筛选选项 (从站点评测确认)
    FILTER_AREA = ["中国大陆", "中国香港", "中国台湾", "美国", "韩国", "日本", "泰国",
                   "新加坡", "马来西亚", "印度", "英国", "法国", "加拿大", "西班牙",
                   "俄罗斯", "澳大利亚", "其它"]

    FILTER_CLASS = ["剧情", "喜剧", "动作", "爱情", "科幻", "动画", "悬疑", "惊悚",
                    "警匪", "恐怖", "犯罪", "同性", "音乐", "歌舞", "传记", "历史",
                    "战争", "西部", "奇幻", "冒险", "灾难", "武侠", "古装", "纪录",
                    "运动", "青春偶像", "都市", "情景", "短片", "Netflix"]

    FILTER_LANG = ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语"]

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
        # SSL上下文 (备用, 站点目前仅HTTP)
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
        return "好看影视"

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
                port = parsed.port or 80
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
            return self.DOMAINS[0]
        return best

    # ===== HTTP辅助 =====

    def _http_get(self, url, timeout=8):
        """发起HTTP请求并返回解码后的文本"""
        req = urllib.request.Request(url, headers=self.headers)
        if url.startswith("https"):
            resp = urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx)
        else:
            resp = urllib.request.urlopen(req, timeout=timeout)
        data = resp.read()
        charset = 'utf-8'
        content_type = resp.headers.get('Content-Type', '')
        if 'charset=' in content_type:
            charset = content_type.split('charset=')[-1].strip()
        try:
            return data.decode(charset, errors='replace')
        except Exception:
            return data.decode('utf-8', errors='replace')

    def _fetch(self, path, params=None, host=None, timeout=8):
        """获取页面HTML, 主域名失败时尝试备用域名"""
        base = host or self.host
        url = base + path
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        try:
            return self._http_get(url, timeout)
        except Exception:
            if host is None and base == self.host:
                for alt in self.DOMAINS:
                    if alt == self.host:
                        continue
                    try:
                        alt_url = alt + path
                        if params:
                            alt_url = alt_url + "?" + urllib.parse.urlencode(params)
                        return self._http_get(alt_url, timeout)
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
        """首页推荐内容 (最新电影)"""
        html = self._fetch("/pianku-dianying--time---------/")
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
                "key": "lang",
                "name": "语言",
                "value": [{"n": "全部", "v": ""}] +
                         [{"n": l, "v": l} for l in self.FILTER_LANG]
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
                          {"n": "评分", "v": "score"}]
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
        lang = extend.get("lang", "")
        year = extend.get("year", "")

        def enc(v):
            return quote(v, safe='') if v else ""

        page_str = str(page) if page > 1 else ""
        # 格式: pianku-{type}-{area}-{by}-{class}-{lang}------{page}---{year}/
        parts = [tid, enc(area), enc(by), enc(cls), enc(lang), "", "", "", page_str, "", "", enc(year)]
        path = "/pianku-" + "-".join(parts) + "/"

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
        pages = re.findall(r'/pianku-[^"]*--------(\d+)---/', html)
        if pages:
            return max(int(p) for p in pages)
        last = re.search(r'class="page-number page-next"[^>]*href="/pianku-[^"]*--------(\d+)---/"', html)
        if last:
            return int(last.group(1))
        return 0

    def _parse_cards(self, html):
        """解析视频卡片列表 (module-item-pic 结构)"""
        videos = []
        for m in re.finditer(r'<a\s[^>]*class="module-item-pic"[^>]*>(.*?)</a>', html, re.DOTALL):
            full_tag = m.group(0)
            inner = m.group(1)

            # 视频ID
            vid_m = re.search(r'href="/show-(\d+)/"', full_tag)
            if not vid_m:
                continue
            vid = vid_m.group(1)

            # 标题
            name = ""
            title_m = re.search(r'title="([^"]*)"', full_tag)
            if title_m and title_m.group(1).strip():
                name = html_unescape(title_m.group(1).strip())
            if not name:
                alt_m = re.search(r'alt="([^"]*)"', inner)
                if alt_m:
                    name = html_unescape(alt_m.group(1).strip())

            # 封面图
            pic_m = re.search(r'data-src="([^"]*)"', inner)
            pic = pic_m.group(1) if pic_m else ""

            # 备注 (module-item-text 在卡片内, 紧随 module-item-pic 之后)
            text_m = re.search(r'class="module-item-text">([^<]*)<', html[m.end():m.end() + 500])
            remarks = html_unescape(text_m.group(1).strip()) if text_m else ""

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
        html = self._fetch("/show-" + str(vid) + "/")

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

        # 封面图 (video-cover 区域内的 module-item-pic)
        pic_m = re.search(r'class="video-cover"[^>]*>.*?data-src="([^"]*)"', html, re.DOTALL)
        if not pic_m:
            pic_m = re.search(r'class="module-item-pic"[^>]*>.*?data-src="([^"]*)"', html, re.DOTALL)
        if pic_m:
            vod["vod_pic"] = pic_m.group(1)

        # 年份 (从 itemprop="datePublished" 提取)
        year_m = re.search(r'itemprop="datePublished"[^>]*>(\d{4})', html)
        if year_m:
            vod["vod_year"] = year_m.group(1)

        # 地区 (从 pianku URL: /pianku-{type}-{area}----------/)
        area_m = re.search(r'href="/pianku-\d+-([^/]+?)----------/"', html)
        if area_m:
            vod["vod_area"] = unquote(area_m.group(1))

        # 类型 (从 pianku URL: /pianku-{type}---{class}--------/, 可能有多个)
        class_matches = re.findall(r'href="/pianku-\d+---([^/]+?)--------/"', html)
        if class_matches:
            vod["vod_class"] = " ".join(unquote(c) for c in class_matches)

        # 元数据项 (导演/编剧/主演/上映/连载/剧情等)
        info_items = re.findall(
            r'<span class="video-info-itemtitle">(.*?)</span>\s*<div class="video-info-item[^"]*"[^>]*>(.*?)</div>',
            html, re.DOTALL
        )
        for label_html, value_html in info_items:
            label = html_unescape(re.sub(r'<[^>]+>', '', label_html).strip())
            # 提取文本, 过滤 "/" 分隔符
            links = re.findall(r'>([^<]+)<', value_html)
            value = " ".join(html_unescape(l.strip()) for l in links
                            if l.strip() and l.strip() != "/")
            if not value:
                value = html_unescape(re.sub(r'<[^>]+>', '', value_html).strip())

            if "导演" in label:
                vod["vod_director"] = value
            elif "编剧" in label:
                vod["vod_writer"] = value
            elif "主演" in label:
                vod["vod_actor"] = value
            elif "集数" in label or "状态" in label or "连载" in label or "更新" in label:
                vod["vod_remarks"] = value

        # 简介 (class="video-info-item video-info-content" 为多class值, 需用通配匹配)
        desc_m = re.search(r'class="[^"]*video-info-content[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
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
            # 匹配面板内容 (到下一个panel或download-list)
            panel_pattern = r'id="panel' + sid + r'"[^>]*>(.*?)</div>\s*</div>\s*</div>'
            panel_m = re.search(panel_pattern, html, re.DOTALL)
            if not panel_m:
                panel_pattern = (r'id="panel' + sid + r'"[^>]*>(.*?)'
                                 r'(?=<div[^>]*class="module-list module-player-list|<div[^>]*id="download-list"|$)')
                panel_m = re.search(panel_pattern, html, re.DOTALL)

            if panel_m:
                panel_html = panel_m.group(1)
                # 提取剧集链接 (URL格式: /paly-{vid}-{sid}-{nid}/)
                episodes = re.findall(
                    r'href="(/paly-\d+-' + sid + r'-\d+/)"[^>]*>.*?<span[^>]*>(.*?)</span>',
                    panel_html, re.DOTALL
                )
                if not episodes:
                    episodes = re.findall(
                        r'href="(/paly-\d+-' + sid + r'-\d+/)"[^>]*title="([^"]*)"',
                        panel_html, re.DOTALL
                    )

                # 去重 (sort-item 和 scroll-content 各有一组)
                seen_urls = set()
                unique_eps = []
                for url, ep_name in episodes:
                    if url not in seen_urls:
                        seen_urls.add(url)
                        unique_eps.append((url, ep_name))
                episodes = unique_eps

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
            if page > 1:
                path = "/pianku-" + tid + "--------" + str(page) + "---"
            else:
                path = "/pianku-" + tid + "-----------"
            params = {"wd": key}
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
    print(f"耗时: {t1-t0:.2f}s, 返回: {len(cat.get('list', []))}条, 总页数: {cat.get('pagecount')}")
    for v in cat.get("list", [])[:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    t0 = _time.time()
    print("\n===== 详情页 (337130) =====")
    detail = s.detailContent(["337130"])
    t1 = _time.time()
    if detail.get("list"):
        vod = detail["list"][0]
        print(f"耗时: {t1-t0:.2f}s")
        print(f"  标题: {vod['vod_name']}")
        print(f"  年份: {vod['vod_year']}  地区: {vod['vod_area']}  类型: {vod['vod_class']}")
        print(f"  导演: {vod['vod_director']}")
        print(f"  主演: {vod['vod_actor'][:50]}")
        print(f"  播放源: {vod['vod_play_from']}")
        pu = vod['vod_play_url'].split('$$$')
        if pu:
            for ep in pu[0].split('#')[:3]:
                print(f"    {ep}")

    t0 = _time.time()
    print("\n===== 播放 (337130-1-1) =====")
    play = s.playerContent("BF节点", "/paly-337130-1-1/", [])
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s")
    print(f"  URL: {play.get('url', '')[:80]}")
    print(f"  Parse: {play.get('parse')}")

    t0 = _time.time()
    print("\n===== 搜索 (海贼) =====")
    search = s.searchContent("海贼", False)
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s, 结果: {len(search.get('list', []))}条")
    for v in search.get("list", []):
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    t0 = _time.time()
    print("\n===== 搜索 (藏锋) =====")
    search2 = s.searchContent("藏锋", False)
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s, 结果: {len(search2.get('list', []))}条")
    for v in search2.get("list", []):
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")