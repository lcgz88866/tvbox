# -*- coding: utf-8 -*-
"""
==========================================================
  剧踪视频 (juzong.me) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎)
  框架: STUI模板 (maccms变体)
  更新: 2026-08-15

  URL规则:
    首页: /
    分类页: /vodshow/{type_id}-----------/
    筛选页: /vodshow/{type_id}-{area}-{by}-{class}------{page}---{year}/
    详情页: /voddetail/{vod_id}/
    播放页: /vodplay/{vod_id}-{sid}-{nid}/
    搜索页: /?m=search&wd={keyword}

  播放源: juzongx/juzong/dujiarbx等 (通过jz8.ok1333.cn API解析)
  播放流程:
    1. 获取播放页player_data (含加密URL)
    2. 获取jz8.ok1333.cn的parse_token
    3. 调用try_json_api获取真实视频地址
    4. 返回parse=0直链给ExoPlayer
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

    HOST = "https://www.juzong01.me/"

    # 外部播放器API
    PLAYER_API_BASE = "https://jz8.ok1333.cn"

    UA = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # 主分类 (4个主分类)
    CATEGORIES = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "剧集", "type_id": "2"},
        {"type_name": "综艺", "type_id": "3"},
        {"type_name": "动漫", "type_id": "4"},
    ]

    # 子分类 (作为筛选条件, tid为子分类ID)
    SUB_CATEGORIES = {
        "1": [
            {"n": "全部", "v": ""},
            {"n": "动作片", "v": "6"},
            {"n": "喜剧片", "v": "7"},
            {"n": "爱情片", "v": "8"},
            {"n": "科幻片", "v": "9"},
            {"n": "恐怖片", "v": "10"},
            {"n": "剧情片", "v": "11"},
            {"n": "战争片", "v": "12"},
            {"n": "犯罪片", "v": "22"},
            {"n": "动画片", "v": "23"},
        ],
        "2": [
            {"n": "全部", "v": ""},
            {"n": "国产剧", "v": "13"},
            {"n": "港台剧", "v": "14"},
            {"n": "日韩剧", "v": "15"},
            {"n": "欧美剧", "v": "16"},
            {"n": "海外剧", "v": "20"},
        ],
    }

    # 各分类的地区筛选 (不同分类有不同地区选项)
    FILTER_AREA_MAP = {
        "1": ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
              "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
        "2": ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国", "新加坡", "其他"],
        "3": ["内地", "港台", "日韩", "欧美"],
        "4": ["国产", "日本", "欧美", "其他"],
    }

    FILTER_YEAR = ["2026", "2025", "2024", "2023", "2022", "2021", "2020",
                   "2019", "2018", "2017", "2016", "2015", "2014", "2013",
                   "2012", "2011", "2010", "2009", "2008", "2007", "2006",
                   "2005", "2004", "2003", "2002", "2001", "2000", "1999", "1998"]

    def init(self, extend=""):
        self.ua = self.UA
        self.host = self.HOST
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        # SSL上下文复用
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

        # 播放header: 不带Referer (抖音CDN douyinvod.com/picovr.com 会403)
        self._play_header = json.dumps({
            "User-Agent": self.ua,
        })

        # parse_token 缓存
        self._parse_token = None
        self._token_time = 0

    def getName(self):
        return "剧踪视频"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|ts)(\?|#|$)', url, re.I))

    def manualVideoVCandidate(self, items):
        return []

    def getDependence(self):
        return []

    # ===== HTTP辅助 =====

    def _fetch(self, path, params=None, host=None, timeout=8, headers=None):
        """获取页面HTML"""
        base = host or self.host
        url = base + path
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        try:
            hdrs = dict(self.headers)
            if headers:
                hdrs.update(headers)
            req = urllib.request.Request(url, headers=hdrs)
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
            return ""

    def _fetch_json(self, url, headers=None, timeout=10):
        """获取JSON响应"""
        try:
            hdrs = {"User-Agent": self.ua}
            if headers:
                hdrs.update(headers)
            req = urllib.request.Request(url, headers=hdrs)
            resp = urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx)
            data = resp.read()
            return json.loads(data.decode('utf-8', errors='replace'))
        except Exception:
            return None

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
        html = self._fetch("/vodshow/1--time---------/")
        videos = self._parse_cards(html)
        return {"list": videos[:30]}

    def _get_filters(self):
        """生成筛选器配置: 包含子分类/地区/年份/排序"""
        filters = {}
        # 子分类到父分类的映射 (继承父分类的地区选项)
        PARENT_MAP = {
            "6": "1", "7": "1", "8": "1", "9": "1", "10": "1",
            "11": "1", "12": "1", "22": "1", "23": "1",
            "13": "2", "14": "2", "15": "2", "16": "2", "20": "2",
        }
        for c in self.CATEGORIES:
            tid = c["type_id"]
            area_list = self.FILTER_AREA_MAP.get(tid, [])
            filter_list = []

            # 子分类筛选 (仅电影和剧集有)
            if tid in self.SUB_CATEGORIES:
                filter_list.append({
                    "key": "class",
                    "name": "类型",
                    "value": self.SUB_CATEGORIES[tid]
                })

            # 地区
            filter_list.append({
                "key": "area",
                "name": "地区",
                "value": [{"n": "全部", "v": ""}] +
                         [{"n": a, "v": a} for a in area_list]
            })

            # 年份
            filter_list.append({
                "key": "year",
                "name": "年份",
                "value": [{"n": "全部", "v": ""}] +
                         [{"n": y, "v": y} for y in self.FILTER_YEAR]
            })

            # 排序
            filter_list.append({
                "key": "by",
                "name": "排序",
                "value": [{"n": "最新更新", "v": "time"},
                          {"n": "最近热播", "v": "hits"}]
            })

            filters[tid] = filter_list
        return filters

    # ===== 分类列表 =====

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        extend = extend or {}

        area = extend.get("area", "")
        by = extend.get("by", "")
        year = extend.get("year", "")
        # 子分类: 如果设置了class筛选, 用子分类ID替换tid
        cat_id = extend.get("class", "") or tid

        def enc(v):
            return quote(v, safe='') if v else ""
        page_str = str(page) if page > 1 else ""
        # 格式: /vodshow/{tid}-{area}-{by}------{page}---{year}/
        parts = [cat_id, enc(area), enc(by), "", "", "", "", "", page_str, "", "", enc(year)]
        path = "/vodshow/" + "-".join(parts) + "/"

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
        pages = re.findall(r'/vodshow/[^"]*--------(\d+)---', html)
        if pages:
            return max(int(p) for p in pages)
        # 尝试其他分页模式
        last = re.search(r'class="page-link page-next"[^>]*href="/vodshow/[^"]*--------(\d+)---"', html)
        if last:
            return int(last.group(1))
        return 0

    def _parse_cards(self, html):
        """解析STUI模板视频卡片列表"""
        videos = []
        # STUI卡片: <a class="...stui-vodlist__thumb..." href="/voddetail/{vid}/" title="{title}" data-original="{pic}">
        # 注意: class中stui-vodlist__thumb可能不是第一个类名 (如搜索页是 "v-thumb stui-vodlist__thumb lazyload")
        for m in re.finditer(r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*href="/voddetail/(\d+)/"[^>]*>(.*?)</a>', html, re.DOTALL):
            vid = m.group(1)
            full_tag = m.group(0)
            inner = m.group(2)

            # 标题
            name = ""
            title_m = re.search(r'title="([^"]*)"', full_tag)
            if title_m:
                name = html_unescape(title_m.group(1).strip())

            # 封面图
            pic_m = re.search(r'data-original="([^"]*)"', full_tag)
            if not pic_m:
                pic_m = re.search(r'src="([^"]*)"', full_tag)
            pic = pic_m.group(1) if pic_m else ""

            # 备注 (pic-text)
            note_m = re.search(r'class="pic-text[^"]*"[^>]*>(.*?)<', inner, re.DOTALL)
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
        html = self._fetch("/voddetail/" + str(vid) + "/")

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
        title_m = re.search(r'<h1 class="title">(.*?)</h1>', html, re.DOTALL)
        if title_m:
            vod["vod_name"] = html_unescape(title_m.group(1).strip())

        # 封面图
        pic_m = re.search(r'class="stui-vodlist__thumb[^"]*"[^>]*data-original="([^"]*)"', html, re.DOTALL)
        if not pic_m:
            pic_m = re.search(r'data-original="([^"]*\.jpg[^"]*)"', html)
        if not pic_m:
            pic_m = re.search(r'data-original="([^"]*\.png[^"]*)"', html)
        if pic_m:
            vod["vod_pic"] = pic_m.group(1)

        # 元数据段落: <p class="data">类型：xx 地区：xx 年份：xx</p>
        data_m = re.search(r'<p class="data">(.*?)</p>', html, re.DOTALL)
        if data_m:
            data_html = data_m.group(1)
            # 提取类型、地区、年份
            type_m = re.search(r'类型[：:]\s*</span>(.*?)(?:<span|<span class="split-line")', data_html, re.DOTALL)
            if type_m:
                vod["vod_class"] = html_unescape(re.sub(r'<[^>]+>', '', type_m.group(1)).strip())
            area_m = re.search(r'地区[：:]\s*</span>(.*?)(?:<span|<span class="split-line")', data_html, re.DOTALL)
            if area_m:
                vod["vod_area"] = html_unescape(re.sub(r'<[^>]+>', '', area_m.group(1)).strip())
            year_m = re.search(r'年份[：:]\s*</span>(.*?)(?:<span|<span class="split-line"|$)', data_html, re.DOTALL)
            if year_m:
                vod["vod_year"] = html_unescape(re.sub(r'<[^>]+>', '', year_m.group(1)).strip())

        # 导演
        director_m = re.search(r'<p class="data">\s*<span class="text-muted[^"]*">导演[：:]?</span>(.*?)</p>', html, re.DOTALL)
        if director_m:
            vod["vod_director"] = html_unescape(re.sub(r'<[^>]+>', '', director_m.group(1)).strip())

        # 主演
        actor_m = re.search(r'<p class="data">\s*<span class="text-muted[^"]*">主演[：:]?</span>(.*?)</p>', html, re.DOTALL)
        if actor_m:
            vod["vod_actor"] = html_unescape(re.sub(r'<[^>]+>', '', actor_m.group(1)).strip())

        # 更新/状态
        update_m = re.search(r'<p class="data hidden-sm">\s*<span class="text-muted[^"]*">更新[：:]?</span>(.*?)</p>', html, re.DOTALL)
        if update_m:
            vod["vod_remarks"] = html_unescape(re.sub(r'<[^>]+>', '', update_m.group(1)).strip())

        # 简介: 优先从detail-content提取剧情简介, 其次用detail-sketch
        desc_text = ""
        dc_m = re.search(r'class="detail-content"[^>]*>(.*?)</span>', html, re.DOTALL)
        if dc_m:
            desc_text = html_unescape(re.sub(r'<[^>]+>', '', dc_m.group(1)).strip())
            # 从"剧情简介:"后提取实际内容
            plot_m = re.search(r'剧情简介[：:](.*)', desc_text, re.DOTALL)
            if plot_m:
                desc_text = plot_m.group(1).strip()
            else:
                # 清理推广文案
                desc_text = re.sub(r'欢迎在线观看.*$', '', desc_text).strip()
                desc_text = re.sub(r'剧踪影院.*$', '', desc_text).strip()
        if not desc_text:
            ds_m = re.search(r'class="detail-sketch"[^>]*>(.*?)</span>', html, re.DOTALL)
            if ds_m:
                desc_text = html_unescape(re.sub(r'<[^>]+>', '', ds_m.group(1)).strip())
        if desc_text:
            vod["vod_content"] = desc_text

        # 播放源
        play_from_list = []
        play_url_list = []

        # STUI播放源: <h3 class="title">源名称</h3> 后跟 <ul class="stui-content__playlist"><li><a href="/vodplay/...">集名</a></li></ul>
        # 找到所有播放面板
        panels = re.findall(
            r'<h3 class="title"[^>]*>(.*?)</h3>.*?<ul class="stui-content__playlist[^"]*"[^>]*>(.*?)</ul>',
            html, re.DOTALL
        )

        for source_name_html, panel_html in panels:
            source_name = html_unescape(re.sub(r'<[^>]+>', '', source_name_html).strip())
            if not source_name:
                continue

            # 解析剧集
            episodes = re.findall(
                r'href="(/vodplay/\d+-\d+-\d+/)"[^>]*>(.*?)</a>',
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

    def _encode_video_url(self, url):
        """对URL中的非ASCII字符进行编码 (如中文路径), 保持URL结构不变"""
        if not url:
            return url
        try:
            # 只编码路径和查询参数中的非ASCII字符
            parsed = urllib.parse.urlparse(url)
            # 编码path (保留 / )
            path = quote(unquote(parsed.path), safe='/:@!$&\'()*+,;=-._~')
            # 编码query (保留 = & )
            query = quote(unquote(parsed.query), safe='/:@!$&\'()*+,;=-._~?=')
            # 重建URL
            encoded = urllib.parse.urlunparse((
                parsed.scheme,
                parsed.netloc,
                path,
                parsed.params,
                query,
                parsed.fragment
            ))
            return encoded
        except Exception:
            return url

    def _get_parse_token(self, force_refresh=False):
        """获取jz8.ok1333.cn的parse_token"""
        now = time.time()
        # token 2分钟内有效, 缓存复用
        if not force_refresh and self._parse_token and (now - self._token_time) < 120:
            return self._parse_token

        try:
            html = self._fetch("/?url=test", host=self.PLAYER_API_BASE, timeout=10,
                             headers={"Referer": self.host + "/"})
            if html:
                token_m = re.search(r'WGART_PARSE_TOKEN\s*=\s*"([^"]*)"', html)
                if token_m:
                    self._parse_token = token_m.group(1)
                    self._token_time = now
                    return self._parse_token
        except Exception:
            pass
        return ""

    def playerContent(self, flag, id, vipFlags):
        url = id
        if url.startswith("http"):
            play_url = url
        else:
            play_url = self.host + url

        result = {
            "parse": 0,
            "header": self._play_header,
            "url": "",
            "playUrl": "",
        }

        # 获取播放页HTML
        html = self._fetch(play_url.replace(self.host, ""))
        if not html:
            return result

        # 提取 player_data (格式: var player_data={...}</script> 或 player_data={...};)
        m = re.search(r'player_data\s*=\s*(\{.*?\})\s*(?:</script>|;|$)', html, re.DOTALL)
        if not m:
            # 尝试不要求结尾
            m = re.search(r'player_data\s*=\s*(\{[^<]*?\})', html, re.DOTALL)
        if not m:
            return result

        try:
            player = json.loads(m.group(1))
        except Exception:
            return result

        encrypt = player.get("encrypt", 0)
        raw_url = player.get("url", "")
        from_field = player.get("from", "")

        # encrypt=0: URL可能直接是加密的 juzongx-xxx 格式
        # encrypt=1: URL编码
        # encrypt=2: base64编码
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

        # 如果已经是m3u8/mp4直链, URL编码后直接返回
        if re.search(r'https?://[^\s"\'<>]+\.(m3u8|mp4)[^\s"\'<>]*', decoded, re.I):
            result["url"] = self._encode_video_url(decoded)
            return result

        # 通过jz8.ok1333.cn API解析 (带Token刷新重试)
        video_url = self._resolve_via_api(decoded)
        if video_url:
            result["url"] = self._encode_video_url(video_url)
            return result

        return result

    def _resolve_via_api(self, encoded_url):
        """通过jz8.ok1333.cn API解析加密URL, Token失败时自动刷新重试"""
        if not encoded_url:
            return ""

        # 最多尝试2次: 第1次用缓存token, 失败后刷新token重试
        for attempt in range(2):
            token = self._get_parse_token(force_refresh=(attempt > 0))
            if not token:
                continue

            try:
                api_url = (self.PLAYER_API_BASE +
                          "/wgart/api.php?action=try_json_api&video_url=" +
                          quote(encoded_url) +
                          "&parse_token=" + quote(token))
                data = self._fetch_json(api_url, headers={"Referer": self.PLAYER_API_BASE + "/"})
                if data and data.get("success") and data.get("data") and data["data"].get("url"):
                    return data["data"]["url"]
                # 如果第1次失败且不是明确的"所有接口均解析失败"错误, 刷新token重试
                if attempt == 0 and data and not data.get("success"):
                    msg = data.get("message", "")
                    # token过期相关的错误才重试
                    if "token" in msg.lower() or "expire" in msg.lower() or "forbidden" in msg.lower() or not msg:
                        continue
                    # 其他错误(如所有接口解析失败)不需要重试
                    break
            except Exception:
                if attempt == 0:
                    continue

        return ""

    # ===== 搜索 =====

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        key = key.strip()
        if not key:
            return {"list": []}

        # 搜索URL: /vodsearch/{keyword}----------{page}---/
        path = f"/vodsearch/{quote(key)}----------{page}---/"
        html = self._fetch(path)
        videos = self._parse_cards(html)

        # 去重
        seen = set()
        unique = []
        for v in videos:
            if v["vod_id"] not in seen:
                seen.add(v["vod_id"])
                unique.append({
                    "vod_id": v["vod_id"],
                    "vod_name": v["vod_name"],
                    "vod_pic": v["vod_pic"],
                    "vod_remarks": v["vod_remarks"],
                })

        return {"list": unique[:30], "page": page}


if __name__ == "__main__":
    import time as _time

    s = Spider()
    s.init()

    print("\n===== 首页分类 =====")
    home = s.homeContent(True)
    print("分类数:", len(home.get("class", [])))

    t0 = _time.time()
    print("\n===== 分类列表 (电影第1页) =====")
    cat = s.categoryContent("1", "1", True, {})
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s, 返回: {len(cat.get('list', []))}条")
    for v in cat.get("list", [])[:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    t0 = _time.time()
    print("\n===== 详情页 (60543) =====")
    detail = s.detailContent(["60543"])
    t1 = _time.time()
    if detail.get("list"):
        vod = detail["list"][0]
        print(f"耗时: {t1-t0:.2f}s")
        print(f"  标题: {vod['vod_name']}")
        print(f"  年份: {vod['vod_year']}")
        print(f"  地区: {vod['vod_area']}")
        print(f"  导演: {vod['vod_director']}")
        print(f"  演员: {vod['vod_actor'][:50]}")
        print(f"  简介: {vod['vod_content'][:100]}")
        print(f"  播放源: {vod['vod_play_from']}")
        pu = vod['vod_play_url'].split('$$$')
        if pu:
            for ep in pu[0].split('#')[:3]:
                print(f"    {ep}")

    t0 = _time.time()
    print("\n===== 播放 (60543-1-1) =====")
    play = s.playerContent("剧踪独家[爽看]", "/vodplay/60543-1-1/", [])
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s")
    print(f"  URL: {play.get('url', '')[:100]}")
    print(f"  Parse: {play.get('parse')}")

    t0 = _time.time()
    print("\n===== 搜索 (蜘蛛侠) =====")
    search = s.searchContent("蜘蛛侠", False)
    t1 = _time.time()
    print(f"耗时: {t1-t0:.2f}s, 结果: {len(search.get('list', []))}条")
    for v in search.get("list", [])[:5]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")