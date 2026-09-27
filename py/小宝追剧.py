# -*- coding: utf-8 -*-
# 豆花影视 (dhvideo.cc) - 自定义CMS + Tailwind CSS
# URL规则:
#   分类页: /{cat}.html?sort_field={sort}&page={pg}
#   详情页: /movie/{hash}-{id}.html 或 /tv/{hash}-{id}.html
#   播放页: /movie/{hash}/{id}.html?origin={origin}&p={page}
# 播放提取: 播放页内 xg_video_player_doc = { aa: JSON.parse('{"origin":"...","url":"...m3u8","title":"..."}') }

import sys
sys.path.append('..')
from base.spider import Spider
import re
import json
import ssl
import http.cookiejar
import urllib.request
import urllib.error
from urllib.parse import quote, unquote
from html import unescape as html_unescape


class Spider(Spider):

    def getName(self):
        return "豆花影视"

    def init(self, extend=""):
        self.host = "https://dhvideo.cc"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.cats = [
            {"type_name": "电影", "type_id": "dianying"},
            {"type_name": "电视剧", "type_id": "dianshiju"},
            {"type_name": "综艺", "type_id": "zongyi"},
            {"type_name": "动漫", "type_id": "dongman"},
            {"type_name": "短剧", "type_id": "duanju"},
        ]
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._cj = http.cookiejar.CookieJar()
        self._opener_inst = None

    def getDependence(self):
        return []

    # ==================== 筛选配置 ====================
    def _build_filters(self):
        """构建各分类的筛选配置 (从网站实际抓取)"""
        filters = {}

        # 通用地区 (所有分类共用)
        area_values = [
            {"n": "全部", "v": ""},
            {"n": "中国大陆", "v": "中国大陆"}, {"n": "美国", "v": "美国"},
            {"n": "日本", "v": "日本"}, {"n": "英国", "v": "英国"},
            {"n": "中国香港", "v": "中国香港"}, {"n": "法国", "v": "法国"},
            {"n": "韩国", "v": "韩国"}, {"n": "加拿大", "v": "加拿大"},
            {"n": "印度", "v": "印度"}, {"n": "德国", "v": "德国"},
            {"n": "意大利", "v": "意大利"}, {"n": "中国台湾", "v": "中国台湾"},
            {"n": "西班牙", "v": "西班牙"}, {"n": "泰国", "v": "泰国"},
            {"n": "俄罗斯", "v": "俄罗斯"}, {"n": "澳大利亚", "v": "澳大利亚"},
            {"n": "比利时", "v": "比利时"}, {"n": "菲律宾", "v": "菲律宾"},
            {"n": "墨西哥", "v": "墨西哥"}, {"n": "丹麦", "v": "丹麦"},
            {"n": "波兰", "v": "波兰"}, {"n": "印度尼西亚", "v": "印度尼西亚"},
            {"n": "土耳其", "v": "土耳其"}, {"n": "巴西", "v": "巴西"},
        ]

        # 通用年份
        year_values = [{"n": "全部", "v": ""}]
        for y in range(2026, 1999, -1):
            year_values.append({"n": str(y), "v": str(y)})

        # 排序
        sort_values = [
            {"n": "热度", "v": "play_hot"},
            {"n": "豆瓣评分", "v": "group_douban"},
        ]

        # 各分类的类型选项
        class_map = {
            "dianying": [
                "剧情", "喜剧", "动作", "爱情", "惊悚", "犯罪", "恐怖", "悬疑",
                "冒险", "奇幻", "科幻", "院线", "家庭", "历史", "战争", "纪录片",
                "古装", "音乐", "动画", "传记", "武侠", "运动", "西部", "短片",
            ],
            "dianshiju": [
                "剧情", "喜剧", "爱情", "犯罪", "悬疑", "家庭", "古装", "惊悚",
                "动作", "奇幻", "科幻", "都市", "历史", "战争", "冒险", "武侠",
                "恐怖", "青春", "传记", "谍战", "情感", "纪录", "军旅", "时装",
                "纪录片",
            ],
            "zongyi": [
                "真人秀", "脱口秀", "国产综艺", "喜剧", "晚会", "综艺", "音乐",
                "纪录", "游戏", "生活", "港台综艺", "日韩综艺", "剧情", "文化",
                "相声", "情感", "悬疑", "欧美综艺", "美食", "竞技", "爱情",
                "犯罪", "家庭", "历史", "纪录片",
            ],
            "dongman": [
                "动画", "冒险", "喜剧", "奇幻", "剧情", "科幻", "动作", "儿童",
                "悬疑", "都市", "家庭", "国漫", "日常", "爱情", "玄幻", "日漫",
                "音乐", "治愈", "短片", "古风", "犯罪", "武侠", "运动", "校园",
                "纪录片",
            ],
            "duanju": [
                "AI漫剧", "短剧", "剧情", "爱情", "爽文", "古装", "短片", "悬疑",
                "喜剧", "奇幻", "都市", "玄幻", "犯罪", "家庭", "穿越", "惊悚",
                "武侠", "科幻", "动作", "冒险", "恐怖", "青春", "历史", "动画",
                "战争", "纪录片",
            ],
        }

        for cat_id in ["dianying", "dianshiju", "zongyi", "dongman", "duanju"]:
            class_values = [{"n": "全部", "v": ""}]
            for c in class_map.get(cat_id, []):
                class_values.append({"n": c, "v": c})
            filters[cat_id] = [
                {"key": "class", "name": "类型", "value": class_values},
                {"key": "area", "name": "地区", "value": area_values},
                {"key": "year", "name": "年份", "value": year_values},
                {"key": "sort", "name": "排序", "value": sort_values},
            ]
        return filters

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def action(self, action):
        pass

    def destroy(self):
        pass

    # ==================== HTTP ====================
    def _opener(self):
        if self._opener_inst is None:
            self._opener_inst = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=self._ssl_ctx),
                urllib.request.HTTPCookieProcessor(self._cj),
            )
        return self._opener_inst

    def _http(self, path, referer=None, timeout=15, no_cookie=False):
        """请求, path 可带 query, 返回 html 字符串
        no_cookie=True 时不带cookie (搜索需要, 否则触发反爬验证页)
        """
        if path.startswith("http"):
            url = path
        else:
            url = self.host + path
        h = dict(self.headers)
        if referer:
            h["Referer"] = referer
        try:
            req = urllib.request.Request(url, headers=h)
            if no_cookie:
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=self._ssl_ctx),
                )
            else:
                opener = self._opener()
            with opener.open(req, timeout=timeout) as r:
                data = r.read()
                return data.decode("utf-8", errors="ignore") if data else ""
        except urllib.error.HTTPError as e:
            try:
                return e.read().decode("utf-8", errors="ignore")
            except:
                return ""
        except Exception:
            return ""

    # ==================== 图片URL ====================
    def _fix_pic(self, pic):
        if not pic:
            return ""
        pic = html_unescape(pic)
        if pic.startswith("http"):
            return pic
        if pic.startswith("//"):
            return "https:" + pic
        if not pic.startswith("/"):
            pic = "/" + pic
        return self.host + pic

    # ==================== 列表解析 ====================
    def _parse_list(self, html):
        """解析视频列表卡片
        结构: <div class="flex flex-col gap-2 group cursor-pointer h-full">
                <a href="/movie/{hash}-{id}.html" ...>
                  <img data-src="/img/id/{hash}.jpg" alt="title">
                  <span>1080p</span> (备注)
                  <span>7.8</span> (评分)
                </a>
                <h3><a href="...">title</a></h3>
              </div>
        """
        items = []
        seen = set()
        # 匹配卡片块
        for m in re.finditer(
            r'<div class="flex flex-col gap-2 group cursor-pointer h-full">(.*?)(?=<div class="flex flex-col gap-2 group cursor-pointer h-full">|<nav|$)',
            html, re.S
        ):
            block = m.group(1)
            # 详情链接
            lm = re.search(r'href="(/(?:movie|tv)/([a-f0-9]+)-(\d+)\.html)"', block)
            if not lm:
                continue
            full_url, vid_hash, vid_id = lm.group(1), lm.group(2), lm.group(3)
            vid = vid_hash + "-" + vid_id
            if vid in seen:
                continue
            seen.add(vid)
            # 标题: <h3><a>title</a></h3> 或 img alt
            tm = re.search(r'<h3[^>]*>\s*<a[^>]*>(.*?)</a>', block, re.S)
            if tm:
                title = re.sub(r'<[^>]+>', '', tm.group(1)).strip()
            else:
                am = re.search(r'<img[^>]+alt="([^"]+)"', block)
                title = am.group(1).strip() if am else ""
            if not title:
                continue
            # 封面
            pm = re.search(r'data-src="([^"]+)"', block)
            if not pm:
                pm = re.search(r'<img[^>]+src="([^"]+)"', block)
            pic = self._fix_pic(pm.group(1)) if pm else ""
            # 备注: 第一个 span (清晰度)
            remarks = ""
            spans = re.findall(r'<span[^>]*class="[^"]*bg-black[^"]*"[^>]*>\s*([^<]+)\s*</span>', block)
            if spans:
                remarks = spans[0].strip()
            # 评分: 第二个 span
            if len(spans) > 1:
                score = spans[1].strip()
                if re.match(r'^\d+\.\d+$', score):
                    remarks = (remarks + " " if remarks else "") + "★" + score
            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })
        return items

    # ==================== 首页 ====================
    def homeContent(self, filter):
        result = {}
        classes = []
        for c in self.cats:
            classes.append({"type_name": c["type_name"], "type_id": c["type_id"]})
        result["class"] = classes
        result["filters"] = self._build_filters()
        # 首页推荐
        html = self._http("/")
        if html:
            result["list"] = self._parse_list(html)
        return result

    def homeVideoContent(self):
        result = {"list": []}
        html = self._http("/")
        if html:
            result["list"] = self._parse_list(html)[:24]
        return result

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg) if pg else 1, "pagecount": 1, "limit": 48, "total": 0}
        page = int(pg) if pg else 1
        if page < 1:
            page = 1
        # URL: /{cat}.html?sort_field={sort}&class={class}&area={area}&year={year}&page={pg}
        params = []
        sort = "play_hot"
        if extend and extend.get("sort"):
            sort = extend["sort"]
        params.append("sort_field=" + sort)
        # 筛选: class(类型), area(地区), year(年份) - 网站无lang/actor参数
        if extend:
            for key in ["class", "area", "year"]:
                val = extend.get(key, "")
                if val:
                    params.append(key + "=" + quote(str(val)))
        if page > 1:
            params.append("page=" + str(page))
        path = "/" + tid + ".html?" + "&".join(params)
        html = self._http(path, referer=self.host + "/")
        if not html:
            return result
        items = self._parse_list(html)
        result["list"] = items
        result["total"] = len(items)
        # 分页: 找页码链接
        page_nums = re.findall(r'[?&]page=(\d+)', html)
        if page_nums:
            max_page = max(int(p) for p in page_nums)
            result["pagecount"] = max_page
        else:
            result["pagecount"] = 300  # 默认多页
        return result

    # ==================== 详情 ====================
    def detailContent(self, ids):
        result = {"list": []}
        if not ids:
            return result
        vid = ids[0]
        # vid 格式: {hash}-{id}
        parts = vid.split("-")
        if len(parts) < 2:
            return result
        # 判断 movie/tv
        # 先试 movie, 失败试 tv
        for cat in ["movie", "tv"]:
            url = "/" + cat + "/" + vid + ".html"
            html = self._http(url, referer=self.host + "/")
            if html and len(html) > 5000:
                break
        else:
            return result
        # 标题
        title = ""
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        # 年份: 标题后 <span>(2026)</span>
        year = ""
        m = re.search(r'</h1>\s*<span[^>]*>\((\d{4})\)</span>', html)
        if m:
            year = m.group(1)
        # 封面
        pic = ""
        m = re.search(r'data-src="(/img/(?:id|cover)/[^"]+)"', html)
        if m:
            pic = self._fix_pic(m.group(1))
        # 简介
        desc = ""
        m = re.search(r'剧情介绍[：:]\s*([^"<]+)', html)
        if m:
            desc = m.group(1).strip()
        if not desc:
            # 简介: <h3>简介</h3> 后的 div
            m = re.search(r'简介</h3>\s*<div[^>]*>(.*?)</div>', html, re.S)
            if m:
                desc = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        # 主演
        actor = ""
        m = re.search(r'<span[^>]*>\s*主演\s*</span>(.*?)</div>', html, re.S)
        if m:
            raw = re.sub(r'<[^>]+>', ' ', m.group(1))
            actor = re.sub(r'\s*,\s*', ', ', raw).strip()
            actor = re.sub(r'\s+', ' ', actor)
        # 评分 (列表页卡片里有, 详情页 h1 附近)
        remarks = ""
        m = re.search(r'(\d+\.\d)\s*</span>', html)
        if m:
            remarks = "豆瓣 " + m.group(1)
        # 播放源和分集
        play_from_list = []
        play_url_list = []
        # 找所有播放源列表 (按 origin 分组)
        # 结构: <div id="list-{origin}" class="episode-list ..."> ... <a href="/{cat}/{hash}/{id}.html?origin={origin}&p={page}" data-origin="..." data-title="...">
        # 先找所有 episode-list 块
        list_blocks = re.findall(
            r'id="list-([^"]+)"[^>]*class="episode-list[^"]*"[^>]*>(.*?)(?=id="list-|<div class="magnet|<footer|$)',
            html, re.S
        )
        if not list_blocks:
            # 备用: 找所有 episode-button
            list_blocks = [("", html)]
        for origin, block in list_blocks:
            # 找分集
            eps = re.findall(
                r'href="(/(?:movie|tv)/[a-f0-9]+/\d+\.html\?origin=([^&]+)&amp;p=(\d+))"[^>]*data-title="([^"]*)"',
                block
            )
            if not eps:
                # 不限定 data-title
                eps = re.findall(
                    r'href="(/(?:movie|tv)/[a-f0-9]+/\d+\.html\?origin=([^&]+)&amp;p=(\d+))"',
                    block
                )
                eps = [(e[0], e[1], e[2], "") for e in eps]
            if not eps:
                continue
            # 源名称
            src_name = origin if origin else "豆花影视"
            # 映射 origin 到友好名称
            origin_map = {
                "modum3u8": "魔都m3u8",
                "jsm3u8": "极速m3u8",
                "mtm3u8": "美图m3u8",
                "lzm3u8": "量子m3u8",
                "bfzym3u8": "暴风m3u8",
                "ffm3u8": "飞飞m3u8",
                "dyttm3u8": "电影天堂m3u8",
                "1080zyk": "1080资源",
                "vip": "VIP专线",
                "wztv": "微众TV",
            }
            src_name = origin_map.get(origin, origin) if origin else "豆花影视"
            play_from_list.append(src_name)
            ep_list = []
            for ep_url, ep_origin, ep_page, ep_title in eps:
                if not ep_title:
                    ep_title = "第" + str(int(ep_page) + 1) + "集"
                # 播放ID: {cat}|{hash}|{id}|{origin}|{page}
                play_id = ep_url + "|" + ep_origin + "|" + ep_page
                ep_list.append(ep_title + "$" + play_id)
            play_url_list.append("#".join(ep_list))
        # 如果没找到分集, 尝试单集 (电影)
        if not play_from_list:
            # 找默认 origin
            origins = re.findall(r'origin=([a-z0-9]+)', html)
            if origins:
                origin = origins[0]
                # 构造单集播放
                play_url = "/" + cat + "/" + parts[0] + "/" + parts[1] + ".html?origin=" + origin + "&p=0"
                origin_map = {
                    "modum3u8": "魔都m3u8", "jsm3u8": "极速m3u8", "mtm3u8": "美图m3u8",
                    "lzm3u8": "量子m3u8", "bfzym3u8": "暴风m3u8", "ffm3u8": "飞飞m3u8",
                    "dyttm3u8": "电影天堂m3u8", "1080zyk": "1080资源", "vip": "VIP专线",
                    "wztv": "微众TV",
                }
                src_name = origin_map.get(origin, origin)
                play_from_list.append(src_name)
                play_url_list.append("播放$" + play_url + "|" + origin + "|0")
        # 播放源排序: 直链m3u8源(快)优先, CDN中转源(慢)靠后
        if len(play_from_list) > 1:
            # 优先级: 数字越小越靠前; 直链m3u8=0, 1080资源=1, VIP/CDN=2, 未知=9
            priority_map = {
                "jsm3u8": 0, "modum3u8": 0, "mtm3u8": 0,
                "lzm3u8": 0, "bfzym3u8": 0, "ffm3u8": 0,
                "dyttm3u8": 0, "1080zyk": 1,
                "vip": 2, "wztv": 2,
            }
            # 源名称到origin的反向映射 (用于查优先级)
            name_to_origin = {v: k for k, v in {
                "modum3u8": "魔都m3u8", "jsm3u8": "极速m3u8", "mtm3u8": "美图m3u8",
                "lzm3u8": "量子m3u8", "bfzym3u8": "暴风m3u8", "ffm3u8": "飞飞m3u8",
                "dyttm3u8": "电影天堂m3u8", "1080zyk": "1080资源", "vip": "VIP专线",
                "wztv": "微众TV",
            }.items()}
            # 从 play_url_list 提取 origin 排序键
            def sort_key(i):
                name = play_from_list[i]
                origin = name_to_origin.get(name, "")
                return priority_map.get(origin, 9)
            order = sorted(range(len(play_from_list)), key=sort_key)
            play_from_list = [play_from_list[i] for i in order]
            play_url_list = [play_url_list[i] for i in order]
        vod = {
            "vod_id": vid,
            "vod_name": title or "未知",
            "vod_pic": pic,
            "vod_year": year,
            "vod_remarks": remarks,
            "vod_actor": actor,
            "vod_content": desc,
        }
        if play_from_list:
            vod["vod_play_from"] = "$$$".join(play_from_list)
            vod["vod_play_url"] = "$$$".join(play_url_list)
        result["list"] = [vod]
        return result

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        if not key:
            return result
        # 搜索: /s?name={key}&page={pg}  (注意: 参数是name不是keyword)
        # 搜索必须用no_cookie, 否则sion_id cookie触发反爬验证页
        page = int(pg) if pg else 1
        path = "/s?name=" + quote(key)
        if page > 1:
            path += "&page=" + str(page)
        html = self._http(path, referer=self.host + "/", no_cookie=True)
        if not html:
            return result
        result["list"] = self._parse_list(html)
        return result

    # ==================== 播放 ====================
    def _get_redirect(self, url, referer=None, timeout=6):
        """请求URL获取302重定向的Location (不跟随重定向, 短超时)"""
        h = dict(self.headers)
        if referer:
            h["Referer"] = referer
        try:
            req = urllib.request.Request(url, headers=h)
            # 不跟随重定向
            class _NoRedir(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None
            opener = urllib.request.build_opener(
                _NoRedir,
                urllib.request.HTTPSHandler(context=self._ssl_ctx),
            )
            with opener.open(req, timeout=timeout) as r:
                return ""  # 没有重定向
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                return e.headers.get("Location", "")
            return ""
        except:
            return ""

    def _build_cdn_url(self, api_url):
        """从 /api/m3u8?origin=XXX&url=YYY 直接构造CDN URL
        规律: https://box.dyrs.com.de/api/super?g=douhua&id=YYY&origin=XXX
        """
        try:
            m = re.search(r'/api/m3u8\?origin=([^&]+)&url=(.+)', api_url)
            if m:
                origin_val = m.group(1)
                url_val = m.group(2)
                return "https://box.dyrs.com.de/api/super?g=douhua&id=" + url_val + "&origin=" + origin_val
        except:
            pass
        return ""

    def playerContent(self, flag, id, vipFlags):
        """播放流程:
        1. 播放页提取 xg_video_player_doc.aa.url = /api/m3u8?origin=XXX&url=YYY
        2. 请求 /api/m3u8 获取302重定向Location (CDN URL)
        3. 失败则直接构造CDN URL: box.dyrs.com.de/api/super?g=douhua&id=YYY&origin=XXX
        4. 返回CDN URL (parse=0, CDN返回m3u8主清单)
        """
        result = {"parse": 0, "url": "", "header": ""}
        play_header = json.dumps({"User-Agent": self.ua, "Referer": self.host + "/"})
        try:
            # id 格式: 集名$播放路径|origin|page
            play_id = id.split("$")[-1] if "$" in id else id
            parts = play_id.split("|")
            play_url = parts[0]
            play_url = html_unescape(play_url)  # &amp; -> &
            if not play_url.startswith("http"):
                play_url = self.host + play_url
            # 请求播放页
            html = self._http(play_url, referer=self.host + "/")
            if not html:
                result["parse"] = 1
                result["url"] = play_url
                result["header"] = play_header
                return result
            # 提取 xg_video_player_doc = { aa: JSON.parse('{"origin":"...","url":"...","title":"..."}') }
            api_url = ""
            m = re.search(
                r"xg_video_player_doc\s*=\s*\{[^}]*JSON\.parse\(\s*['\"]([^'\"]+)['\"]\s*\)",
                html, re.S
            )
            if m:
                raw = m.group(1)
                raw = raw.replace("\\u0022", '"').replace("\\/", "/").replace("\\\\", "\\")
                try:
                    data = json.loads(raw)
                    api_url = data.get("url", "")
                except:
                    pass
            # 处理 api_url
            if api_url:
                # 补全为完整URL
                if api_url.startswith("/"):
                    full_api = self.host + api_url
                else:
                    full_api = api_url
                # 如果是 /api/m3u8 类型
                if "/api/m3u8" in api_url:
                    # 方案1: 请求获取302 Location (快速, 6秒超时)
                    location = self._get_redirect(full_api, referer=play_url)
                    if location and location.startswith("http"):
                        result["parse"] = 0
                        result["url"] = location
                        result["header"] = play_header
                        return result
                    # 方案2: 直接构造CDN URL
                    cdn_url = self._build_cdn_url(api_url)
                    if cdn_url:
                        result["parse"] = 0
                        result["url"] = cdn_url
                        result["header"] = play_header
                        return result
                # 如果是直接m3u8 URL
                if ".m3u8" in api_url:
                    result["parse"] = 0
                    result["url"] = full_api
                    result["header"] = play_header
                    return result
                # 其他: 返回完整API URL
                result["parse"] = 0
                result["url"] = full_api
                result["header"] = play_header
                return result
            # 备用: 直接找 m3u8 url
            m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
            if m:
                result["parse"] = 0
                result["url"] = m.group(1)
                result["header"] = play_header
                return result
            # 兜底: 嗅探
            result["parse"] = 1
            result["url"] = play_url
            result["header"] = play_header
        except:
            result["parse"] = 1
            result["url"] = ""
            result["header"] = play_header
        return result
