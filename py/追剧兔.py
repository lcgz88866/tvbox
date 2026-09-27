# -*- coding: utf-8 -*-
"""
==========================================================
  追剧兔影视 (zhuijutu.cc) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎)
  框架: macCMS conch 模板
  更新: 2026-08-18

  URL规则:
    首页: /
    分类页: /vodshow/{tid}-{area}-{by}-{class}-{lang}-{letter}------{page}---{year}.html
    详情页: /voddetail/{vid}.html
    播放页: /vodplay/{vid}-{sid}-{nid}.html
    搜索页: /vodsearch/-------------.html?wd={keyword} (全站统一搜索)

  播放源: jsm3u8/dyttm3u8/bfzym3u8/mgtv 等 (直链m3u8)
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

    # 域名列表 (主域名 + 备用发布页)
    DOMAINS = [
        "https://zhuijutu.cc",
        "https://zhuijutu.xyz",
    ]

    UA = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # 主分类 (从站点导航确认)
    CATEGORIES = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "连续剧", "type_id": "2"},
        {"type_name": "综艺", "type_id": "3"},
        {"type_name": "动漫", "type_id": "4"},
        {"type_name": "短剧", "type_id": "23"},
        {"type_name": "记录片", "type_id": "46"},
    ]

    # 筛选选项
    FILTER_AREA = ["内地", "中国香港", "中国台湾", "美国", "韩国", "日本", "泰国",
                   "英国", "法国", "德国", "加拿大", "俄罗斯", "印度", "新加坡",
                   "马来西亚", "澳大利亚", "其他"]

    FILTER_CLASS = ["动作", "喜剧", "爱情", "科幻", "悬疑", "惊悚",
                    "恐怖", "犯罪", "同性", "历史", "战争", "奇幻",
                    "冒险", "灾难", "武侠", "古装", "剧情", "动画",
                    "纪录", "真人秀"]

    FILTER_YEAR = ["2026", "2025", "2024", "2023", "2022", "2021", "2020",
                   "2019", "2018", "2017", "2016", "2015", "2014",
                   "2013", "2012", "2011", "2010", "2009", "2008",
                   "2007", "2006", "2005"]

    # 平台源 from 字段 (需解析, 非直链)
    PLATFORM_SOURCES = {"qq", "qiyi", "youku", "mgtv", "sohu", "xigua", "bilibili", "pptv", "letv", "m1905"}

    # VIP解析器 (麒麟播放器, 从站点playerconfig.js获取)
    VIP_PARSE_URL = "https://svip.qlplayer.cyou/?url="
    VIP_RESOLVE_API = "https://svip.qlplayer.cyou/api/resolve.php?token="

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
        return "追剧兔影视"

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
        html = self._fetch("/vodshow/1--time---------.html")
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
                          {"n": "最多播放", "v": "hits"}]
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
        # vodshow URL格式: /vodshow/{tid}-{area}-{by}-{class}-{lang}-{letter}------{page}---{year}.html
        # 12个字段: [tid, area, by, class, lang, letter, "", "", page, "", "", year]
        parts = [tid, enc(area), enc(by), enc(cls), "", "", "", "", page_str, "", "", enc(year)]
        path = "/vodshow/" + "-".join(parts) + ".html"

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
        pages = re.findall(r'/vodshow/\d+--------(\d+)---', html)
        if pages:
            return max(int(p) for p in pages)
        last = re.search(r'class="hl-num-current"[^>]*>\d+', html)
        if last:
            pass
        return 0

    def _parse_cards(self, html):
        """解析视频卡片列表 (macCMS conch: hl-list-item)"""
        videos = []
        # 匹配 hl-item-thumb 卡片 (分类页/搜索页通用)
        for m in re.finditer(
            r'<a[^>]*class="hl-item-thumb hl-lazy"[^>]*href="/voddetail/(\d+)\.html"[^>]*title="([^"]*)"[^>]*data-original="([^"]*)"[^>]*>(.*?)</a>',
            html, re.DOTALL
        ):
            vid = m.group(1)
            name = html_unescape(m.group(2).strip())
            pic = m.group(3).strip()
            inner = m.group(4)

            # 备注 (集数/状态)
            note_m = re.search(r'class="hl-lc-1 remarks">(.*?)<', inner, re.DOTALL)
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
        html = self._fetch("/voddetail/" + str(vid) + ".html")

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

        # 标题 (hl-dc-title)
        title_m = re.search(r'<h2[^>]*class="hl-dc-title[^"]*"[^>]*>(.*?)</h2>', html, re.DOTALL)
        if title_m:
            vod["vod_name"] = html_unescape(title_m.group(1).strip())

        # 封面图 (hl-dc-pic 内的 data-original)
        pic_m = re.search(r'class="hl-dc-pic"[^>]*>.*?data-original="([^"]*)"', html, re.DOTALL)
        if pic_m:
            vod["vod_pic"] = pic_m.group(1)

        # 元数据项 (<li><em>标签：</em><span/a>值</span></li>)
        info_ul_m = re.search(r'<ul class="clearfix">(.*?)</ul>', html, re.DOTALL)
        if info_ul_m:
            for li in re.finditer(r'<li[^>]*>(.*?)</li>', info_ul_m.group(1), re.DOTALL):
                s = li.group(1)
                lm = re.search(r'<em[^>]*>(.*?)</em>', s, re.DOTALL)
                if not lm:
                    continue
                label = html_unescape(re.sub(r'<[^>]+>', '', lm.group(1)).strip())
                # 去掉em标签后取剩余文本
                rest = re.sub(r'<em[^>]*>.*?</em>', '', s, flags=re.DOTALL)
                value = html_unescape(re.sub(r'<[^>]+>', ' ', rest).strip())
                value = re.sub(r'\s+', ' ', value).strip()

                if "状态" in label or "集数" in label:
                    vod["vod_remarks"] = value
                elif "导演" in label:
                    vod["vod_director"] = value
                elif "主演" in label:
                    vod["vod_actor"] = value
                elif "年份" in label:
                    vod["vod_year"] = value
                elif "地区" in label:
                    vod["vod_area"] = value
                elif "类型" in label:
                    vod["vod_class"] = value
                elif "编剧" in label:
                    vod["vod_writer"] = value
                elif "简介" in label:
                    vod["vod_content"] = value

        # 简介 (备用: hl-content)
        if not vod["vod_content"]:
            desc_m = re.search(r'class="hl-content[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            if desc_m:
                vod["vod_content"] = html_unescape(re.sub(r'<[^>]+>', '', desc_m.group(1)).strip())

        # 播放源
        play_from_list = []
        play_url_list = []

        # 从 hl-from-list 获取源名称和sid
        sources = []
        from_m = re.search(r'<ul class="hl-from-list">(.*?)</ul>', html, re.DOTALL)
        if from_m:
            for li in re.finditer(
                r'<li[^>]*data-href="/vodplay/\d+-(\d+)-\d+\.html"[^>]*>(.*?)</li>',
                from_m.group(1), re.DOTALL
            ):
                sid = li.group(1)
                name = html_unescape(re.sub(r'<[^>]+>', '', li.group(2)).strip())
                sources.append((sid, name))

        # 按源提取剧集列表
        from collections import defaultdict
        by_src = defaultdict(list)
        for m in re.finditer(
            r'href="(/vodplay/\d+-(\d+)-(\d+)\.html)"[^>]*>(.*?)</a>',
            html, re.DOTALL
        ):
            url = m.group(1)
            sid = m.group(2)
            nid = m.group(3)
            inner = m.group(4)
            name = html_unescape(re.sub(r'<[^>]+>', '', inner).strip())
            # 过滤噪声 (立即播放/空文本/超长文本)
            if not name or "立即播放" in name or len(name) > 50:
                continue
            by_src[sid].append((nid, name, url))

        for sid, source_name in sources:
            eps = by_src.get(sid, [])
            if not eps:
                continue
            # 去重 (保持顺序)
            seen = set()
            ep_names = []
            for nid, name, url in eps:
                if url in seen:
                    continue
                seen.add(url)
                ep_names.append(name + "$" + url)
            if ep_names:
                play_from_list.append(source_name)
                play_url_list.append("#".join(ep_names))

        # 备用: 如果没有从hl-from-list获取到源名, 用sid生成
        if not play_from_list and by_src:
            for sid in sorted(by_src, key=int):
                eps = by_src[sid]
                ep_names = []
                seen = set()
                for nid, name, url in eps:
                    if url in seen:
                        continue
                    seen.add(url)
                    ep_names.append(name + "$" + url)
                if ep_names:
                    play_from_list.append("线路" + sid)
                    play_url_list.append("#".join(ep_names))

        vod["vod_play_from"] = "$$$".join(play_from_list)
        vod["vod_play_url"] = "$$$".join(play_url_list)

        return {"list": [vod]}

    # ===== 播放 =====

    def _resolve_vip(self, platform_url):
        """通过麒麟播放器解析VIP平台源, 返回直链m3u8"""
        try:
            # Step 1: 获取解析页HTML, 提取apiToken
            parse_url = self.VIP_PARSE_URL + quote(platform_url, safe='')
            req = urllib.request.Request(parse_url, headers={
                "User-Agent": self.ua,
                "Referer": self.host + "/",
            })
            resp = urllib.request.urlopen(req, timeout=10, context=self._ssl_ctx)
            html = resp.read().decode('utf-8', errors='replace')

            token_m = re.search(r'apiToken:\s*"([^"]*)"', html)
            if not token_m:
                return ""
            token = token_m.group(1)

            # Step 2: 调用resolve API获取直链
            api_url = self.VIP_RESOLVE_API + quote(token, safe='')
            req2 = urllib.request.Request(api_url, headers={
                "User-Agent": self.ua,
                "Referer": "https://svip.qlplayer.cyou/",
            })
            resp2 = urllib.request.urlopen(req2, timeout=10, context=self._ssl_ctx)
            data = json.loads(resp2.read().decode('utf-8', errors='replace'))

            if data.get("code") == 200 and data.get("url"):
                return html_unescape(data["url"])
        except Exception:
            pass
        return ""

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
        m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', html, re.DOTALL)
        if not m:
            m = re.search(r'player_aaaa\s*=\s*(\{.*?\})', html, re.DOTALL)
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

        # 提取m3u8/mp4直链
        m3u8_m = re.search(r'(https?://[^\s"&\']+\.m3u8[^\s"&\']*)', decoded)
        mp4_m = re.search(r'(https?://[^\s"&\']+\.mp4[^\s"&\']*)', decoded)
        if m3u8_m:
            result["url"] = m3u8_m.group(1)
            return result
        if mp4_m:
            result["url"] = mp4_m.group(1)
            return result

        # 平台源URL: 通过麒麟解析器获取直链m3u8
        if from_field in self.PLATFORM_SOURCES:
            platform_url = decoded.split("&")[0] if "&" in decoded else decoded
            if platform_url.startswith("http"):
                # 尝试解析为直链m3u8
                resolved = self._resolve_vip(platform_url)
                if resolved:
                    result["url"] = resolved
                    return result
                # 解析失败, 回退到parse=1交由TVBox解析
                result["parse"] = 1
                result["url"] = platform_url
                return result

        # 如果url本身就是http链接, 直接返回
        if decoded.startswith("http"):
            result["url"] = decoded
            return result

        return result

    # ===== 搜索 =====

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        key = key.strip()
        if not key:
            return {"list": []}

        # 追剧兔统一搜索接口, 无需遍历分类
        path = "/vodsearch/-------------.html"
        params = {"wd": key}
        if page > 1:
            path = "/vodsearch/" + quote(key, safe='') + "----------" + str(page) + "---.html"
            params = None

        html = self._fetch(path, params)
        videos = self._parse_cards(html)

        results = []
        seen = set()
        for v in videos:
            if v["vod_id"] not in seen:
                seen.add(v["vod_id"])
                results.append({
                    "vod_id": v["vod_id"],
                    "vod_name": v["vod_name"],
                    "vod_pic": v["vod_pic"],
                    "vod_remarks": v["vod_remarks"],
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
        print(f"  [{c['type_id']}] {c['type_name']}")

    print("\n===== 首页推荐 =====")
    rec = s.homeVideoContent()
    print("推荐数:", len(rec.get("list", [])))
    for v in rec.get("list", [])[:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    t0 = _time.time()
    print("\n===== 分类列表 (电影第1页) =====")
    cat = s.categoryContent("1", "1", True, {})
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s, 返回: {len(cat.get('list', []))}条, 总页: {cat.get('pagecount')}")
    for v in cat.get("list", [])[:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    t0 = _time.time()
    print("\n===== 分类筛选 (内地+2024) =====")
    cat2 = s.categoryContent("1", "1", True, {"area": "内地", "year": "2024"})
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s, 返回: {len(cat2.get('list', []))}条")
    for v in cat2.get("list", [])[:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    t0 = _time.time()
    print("\n===== 详情页 (歌手2026: 489144) =====")
    detail = s.detailContent(["489144"])
    t1 = _time.time()
    if detail.get("list"):
        vod = detail["list"][0]
        print(f"耗时: {t1-t0:.2f}s")
        print(f"  标题: {vod['vod_name']}")
        print(f"  年份: {vod['vod_year']}  地区: {vod['vod_area']}  类型: {vod['vod_class']}")
        print(f"  导演: {vod['vod_director']}  主演: {vod['vod_actor']}")
        print(f"  播放源: {vod['vod_play_from']}")
        pu = vod['vod_play_url'].split('$$$')
        if pu:
            for ep in pu[0].split('#')[:5]:
                print(f"    {ep}")

    t0 = _time.time()
    print("\n===== 播放 (普通线路一 jsm3u8 直链) =====")
    play = s.playerContent("普通线路一", "/vodplay/489144-2-1.html", [])
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s")
    print(f"  URL: {play.get('url', '')[:80]}")
    print(f"  Parse: {play.get('parse')}")

    t0 = _time.time()
    print("\n===== 播放 (VIP线路二 mgtv 解析) =====")
    play_vip = s.playerContent("vip线路二", "/vodplay/489144-1-1.html", [])
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s")
    print(f"  URL: {play_vip.get('url', '')[:80]}")
    print(f"  Parse: {play_vip.get('parse')}")

    t0 = _time.time()
    print("\n===== 播放 (VIP线路四 qq 解析) =====")
    play_qq = s.playerContent("vip线路四", "/vodplay/688132-1-1.html", [])
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s")
    print(f"  URL: {play_qq.get('url', '')[:80]}")
    print(f"  Parse: {play_qq.get('parse')}")

    t0 = _time.time()
    print("\n===== 播放 (VIP线路五 youku 解析) =====")
    play_yk = s.playerContent("vip线路五", "/vodplay/688132-2-1.html", [])
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s")
    print(f"  URL: {play_yk.get('url', '')[:80]}")
    print(f"  Parse: {play_yk.get('parse')}")

    t0 = _time.time()
    print("\n===== 搜索 (歌手) =====")
    search = s.searchContent("歌手", False)
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s, 结果: {len(search.get('list', []))}条")
    for v in search.get("list", []):
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")