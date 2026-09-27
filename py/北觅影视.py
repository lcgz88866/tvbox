# -*- coding: utf-8 -*-
"""
==========================================================
  北觅影视 (v.luttt.com) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎)
  框架: 苹果CMS V10 (maccms) - conch模板
  更新: 2026-08-12

  URL规则:
    首页: /
    分类页: /vodtype/{tid}.html
    筛选页: /vodshow/{tid}-{area}-{by}-{class}-{lang}-{letter}------{page}---{year}.html
             (标准maccms 12段格式)
    详情页: /voddetail/{vid}.html
    播放页: /vodplay/{vid}-{sid}-{nid}.html
    搜索页: POST /vodsearch/-------------.html (wd=关键词)

  导航分类 (真实):
    电影=1  连续剧=2  综艺=3  动漫=4  纪录片=20  动画片=35
    电影子类: 动作片=6 喜剧片=7 爱情片=8 科幻片=9 恐怖片=10
             剧情片=11 战争片=12
    剧集子类: 国产剧=13 香港剧=14 韩国剧=15 欧美剧=16
             台湾剧=22 日本剧=23 海外剧=24 泰国剧=25
    综艺子类: 大陆综艺=26 港台综艺=27 日韩综艺=28 欧美综艺=29
    动漫子类: 国产动漫=30 日韩动漫=31 欧美动漫=32 港台动漫=33 海外动漫=34

  卡片结构 (conch模板, 与追剧兔一致):
    <li class="hl-list-item">
      <a class="hl-item-thumb hl-lazy" href="/voddetail/{vid}.html" title="标题" data-original="封面">
        <span class="remarks">备注</span>
      </a>
      <a href="/voddetail/{vid}.html" title="标题">标题</a>
    </li>

  详情页元数据:
    <li><em class="hl-text-muted">片名：</em><span>标题</span></li>
    <li><em class="hl-text-muted">状态：</em><span>全1集</span></li>
    <li><em class="hl-text-muted">主演：</em><a>演员</a></li>
    <li><em class="hl-text-muted">导演：</em><a>导演</a></li>
    <li><em class="hl-text-muted">年份：</em>2026</li>
    <li><em class="hl-text-muted">地区：</em>中国</li>
    <li><em class="hl-text-muted">语言：</em>普通话</li>
    <li><em class="hl-text-muted">简介：</em>简介内容</li>

  播放源结构 (单一线路):
    源标签: <a class="hl-tabs-btn" alt="北觅影视">北觅影视</a>
    集数: <div class="hl-tabs-box"><ul class="hl-plays-list">
             <li><a href="/vodplay/{vid}-{sid}-{nid}.html">第01集</a></li>
           </ul></div>

  播放页:
    player_aaaa = {
      "flag":"play", "encrypt":0,
      "url":"https://vip.dytt-luck.com/xxx/index.m3u8",
      "from":"dyttm3u8", ...
    }
    from=dyttm3u8: 直链m3u8, parse=0直接播放

  header 使用 json.dumps (TVBox标准格式)
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
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import quote, unquote
from html import unescape as html_unescape
from json.decoder import JSONDecoder


class Spider(Spider):

    HOST = "https://v.luttt.com"
    UA = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # 主分类 (从真实导航栏确认)
    CATEGORIES = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "连续剧", "type_id": "2"},
        {"type_name": "综艺", "type_id": "3"},
        {"type_name": "动漫", "type_id": "4"},
        {"type_name": "纪录片", "type_id": "20"},
    ]

    # 各分类的子类型(class)选项
    CLASS_MAP = {
        "1": [
            ("动作片", "6"), ("喜剧片", "7"), ("爱情片", "8"), ("科幻片", "9"),
            ("恐怖片", "10"), ("剧情片", "11"), ("战争片", "12"),
        ],
        "2": [
            ("国产剧", "13"), ("香港剧", "14"), ("韩国剧", "15"), ("欧美剧", "16"),
            ("台湾剧", "22"), ("日本剧", "23"), ("海外剧", "24"), ("泰国剧", "25"),
        ],
        "3": [
            ("大陆综艺", "26"), ("港台综艺", "27"), ("日韩综艺", "28"), ("欧美综艺", "29"),
        ],
        "4": [
            ("国产动漫", "30"), ("日韩动漫", "31"), ("欧美动漫", "32"),
            ("港台动漫", "33"), ("海外动漫", "34"),
        ],
        "20": [],
    }

    # 地区选项 (从分类页筛选确认)
    AREA_VALUES = [
        {"n": "全部", "v": ""},
        {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"},
        {"n": "美国", "v": "美国"}, {"n": "法国", "v": "法国"}, {"n": "英国", "v": "英国"},
        {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"}, {"n": "德国", "v": "德国"},
        {"n": "泰国", "v": "泰国"}, {"n": "印度", "v": "印度"}, {"n": "意大利", "v": "意大利"},
        {"n": "西班牙", "v": "西班牙"}, {"n": "加拿大", "v": "加拿大"}, {"n": "其他", "v": "其他"},
    ]

    # 语言选项 (从分类页筛选确认)
    LANG_VALUES = [
        {"n": "全部", "v": ""},
        {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"},
        {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"},
        {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"},
        {"n": "法语", "v": "法语"}, {"n": "德语", "v": "德语"},
        {"n": "其它", "v": "其它"},
    ]

    # 排序选项 (从分类页筛选确认)
    SORT_VALUES = [
        {"n": "按最新", "v": "time"},
        {"n": "按最热", "v": "hits"},
        {"n": "按评分", "v": "score"},
    ]

    def getName(self):
        return "北觅影视"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": self.UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.HOST + "/",
        }
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def action(self, action):
        pass

    def destroy(self):
        pass

    # ==================== 筛选配置 ====================
    def _build_filters(self):
        filters = {}
        year_values = [{"n": "全部", "v": ""}]
        for y in range(2026, 1999, -1):
            year_values.append({"n": str(y), "v": str(y)})

        for cat in self.CATEGORIES:
            cat_id = cat["type_id"]
            class_values = [{"n": "全部", "v": ""}]
            for name, sub_id in self.CLASS_MAP.get(cat_id, []):
                class_values.append({"n": name, "v": sub_id})

            filters[cat_id] = [
                {"key": "class", "name": "类型", "value": class_values},
                {"key": "area", "name": "地区", "value": self.AREA_VALUES},
                {"key": "year", "name": "年份", "value": year_values},
                {"key": "lang", "name": "语言", "value": self.LANG_VALUES},
                {"key": "sort", "name": "排序", "value": self.SORT_VALUES},
            ]
        return filters

    # ==================== HTTP ====================
    def _fetch(self, url, headers=None, timeout=15, data=None):
        """GET/POST请求, 返回HTML文本"""
        hdr = headers or self.headers

        if data is not None:
            try:
                rsp = self.post(url, data=data, headers=hdr)
                if isinstance(rsp, str):
                    return rsp
                if rsp and hasattr(rsp, 'text'):
                    return rsp.text
                if rsp and hasattr(rsp, 'content'):
                    return rsp.content.decode("utf-8", errors="ignore")
            except:
                pass
            try:
                post_data = data.encode("utf-8") if isinstance(data, str) else urllib.parse.urlencode(data).encode("utf-8")
                req = urllib.request.Request(url, data=post_data, headers=hdr)
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=self._ssl_ctx)
                )
                with opener.open(req, timeout=timeout) as r:
                    d = r.read()
                    return d.decode("utf-8", errors="ignore") if d else ""
            except urllib.error.HTTPError as e:
                try:
                    return e.read().decode("utf-8", errors="ignore")
                except:
                    return ""
            except:
                return ""
        else:
            try:
                rsp = self.fetch(url, headers=hdr)
                if isinstance(rsp, str):
                    return rsp
                if rsp and hasattr(rsp, 'text'):
                    return rsp.text
                if rsp and hasattr(rsp, 'content'):
                    return rsp.content.decode("utf-8", errors="ignore")
            except:
                pass
            req_url = url
            if not req_url.isascii():
                req_url = quote(req_url, safe=":/?&=%-._~")
            try:
                req = urllib.request.Request(req_url, headers=hdr)
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=self._ssl_ctx)
                )
                with opener.open(req, timeout=timeout) as r:
                    d = r.read()
                    return d.decode("utf-8", errors="ignore") if d else ""
            except urllib.error.HTTPError as e:
                try:
                    return e.read().decode("utf-8", errors="ignore")
                except:
                    return ""
            except:
                return ""

    # ==================== 工具 ====================
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
        return self.HOST + pic

    def _is_direct_video(self, url):
        """判断是否为直链视频URL"""
        if not url:
            return False
        lower = url.lower()
        for ext in [".m3u8", ".mp4", ".flv", ".avi", ".mkv", ".mov", ".wmv", ".ts"]:
            if ext in lower:
                return True
        return False

    def _build_show_url(self, tid, pg, extend):
        """构建筛选URL (标准maccms 12段格式)
        格式: /vodshow/{tid}-{area}-{by}-{class}-{lang}-{letter}------{page}---{year}.html
        """
        page = str(int(pg)) if int(pg) >= 1 else "1"

        area = ""
        by = ""
        cls = ""
        lang = ""
        year = ""

        if extend:
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except:
                    extend = {}
            area = extend.get("area", "") or ""
            by = extend.get("sort", "") or ""
            cls = extend.get("class", "") or ""
            lang = extend.get("lang", "") or ""
            year = extend.get("year", "") or ""

        # 如果class是子分类ID, 直接用子分类ID做tid
        actual_tid = tid
        if cls and cls.isdigit():
            actual_tid = cls
            cls = ""

        area = quote(area, safe="") if area else ""
        by = quote(by, safe="") if by else ""
        cls = quote(cls, safe="") if cls else ""
        lang = quote(lang, safe="") if lang else ""
        year = quote(year, safe="") if year else ""

        fields = [str(actual_tid), area, by, cls, lang, "", "", "", page, "", "", year]
        return "/vodshow/" + "-".join(fields) + ".html"

    # ==================== 列表解析 ====================
    def _parse_list(self, html):
        """解析视频列表卡片 (conch模板)
        <li class="hl-list-item">
          <a class="hl-item-thumb hl-lazy" href="/voddetail/{vid}.html" title="标题" data-original="封面">
            <span class="remarks">备注</span>
          </a>
          <a href="/voddetail/{vid}.html" title="标题">标题</a>
        </li>
        """
        items = []
        seen = set()

        pattern = re.compile(
            r'<a[^>]*href="(/voddetail/([^"/\.]+)\.html)"[^>]*>',
            re.S
        )
        for m in pattern.finditer(html):
            vid = m.group(2)
            if vid in seen:
                continue
            full_tag = m.group(0)

            title = ""
            tm = re.search(r'title="([^"]+)"', full_tag)
            if tm:
                title = tm.group(1).strip()
            if not title:
                continue

            if title in ("更多", "换一换", "上一页", "下一页"):
                continue

            seen.add(vid)

            search_start = m.start()
            search_end = min(len(html), search_start + 2000)
            segment = html[search_start:search_end]

            pic = ""
            pm = re.search(r'data-original="([^"]+)"', segment)
            if pm:
                pic = self._fix_pic(pm.group(1))

            remark = ""
            for pat in [
                r'<span class="[^"]*remarks[^"]*"[^>]*>([^<]+)<',
                r'<span class="[^"]*hl-pic-text[^"]*"[^>]*>\s*<span[^>]*>([^<]+)<',
            ]:
                rm = re.search(pat, segment)
                if rm:
                    remark = rm.group(1).strip()
                    break

            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return items

    # ==================== 首页 ====================
    def homeContent(self, filter):
        result = {}
        try:
            classes = []
            for c in self.CATEGORIES:
                classes.append({"type_name": c["type_name"], "type_id": c["type_id"]})
            result["class"] = classes

            if filter:
                result["filters"] = self._build_filters()

            html = self._fetch(self.HOST)
            if html:
                result["list"] = self._parse_list(html)

        except Exception as e:
            print("homeContent error: {0}".format(e))
        return result

    def homeVideoContent(self):
        pass

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg) if pg else 1, "pagecount": 999, "limit": 24, "total": 999999}
        try:
            page = int(pg) if int(pg) >= 1 else 1

            show_path = self._build_show_url(tid, page, extend)
            cat_url = self.HOST + show_path

            html = self._fetch(cat_url)
            if html:
                videos = self._parse_list(html)
                result["list"] = videos

                pm = re.search(r'(\d+)\s*(?:&nbsp;|\s)*[\/／]\s*(?:&nbsp;|\s)*(\d+)\s*页', html)
                if pm:
                    result["page"] = int(pm.group(1))
                    result["pagecount"] = int(pm.group(2))
                else:
                    result["page"] = page

        except Exception as e:
            print("categoryContent error: {0}".format(e))
        return result

    # ==================== 详情 ====================
    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            detail_url = self.HOST + "/voddetail/" + str(vod_id) + ".html"
            html = self._fetch(detail_url)
            if not html:
                return result

            detail = self._extract_detail(html, vod_id)
            if detail:
                result["list"].append(detail)

        except Exception as e:
            print("detailContent error: {0}".format(e))
        return result

    def _extract_detail(self, html, vod_id):
        """从详情页HTML提取视频详情"""
        try:
            title = ""
            m = re.search(r'片名[：:]\s*</em>\s*<span[^>]*>([^<]+)<', html)
            if m:
                title = m.group(1).strip()
            if not title:
                m = re.search(r'class="hl-item-thumb[^"]*"[^>]*title="([^"]+)"', html)
                if m:
                    title = m.group(1).strip()
            if not title:
                m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
                if m:
                    title = m.group(1).strip()

            pic = ""
            m = re.search(r'class="hl-item-thumb[^"]*"[^>]*data-original="([^"]+)"', html)
            if m:
                pic = self._fix_pic(m.group(1))
            if not pic:
                m = re.search(r'data-original="([^"]+)"', html)
                if m:
                    pic = self._fix_pic(m.group(1))

            def extract_field(label):
                pattern = re.escape(label) + r'[：:]\s*</em>\s*(.*?)(?:</li>|<em)'
                m = re.search(pattern, html, re.S)
                if m:
                    content = m.group(1)
                    links = re.findall(r'<a[^>]*>([^<]+)</a>', content)
                    if links:
                        return ",".join([l.strip() for l in links])
                    text = re.sub(r'<[^>]+>', '', content).strip()
                    return text
                return ""

            status = extract_field("状态")
            actor = extract_field("主演")
            director = extract_field("导演")
            vod_year = extract_field("年份")
            vod_area = extract_field("地区")
            vod_lang = extract_field("语言")
            vod_remarks = extract_field("更新")

            vod_class = ""
            m = re.search(r'类型[：:]\s*</em>\s*(.*?)(?:</li>|<em)', html, re.S)
            if m:
                links = re.findall(r'<a[^>]*>([^<]+)</a>', m.group(1))
                if links:
                    vod_class = ",".join([l.strip() for l in links])
                else:
                    vod_class = re.sub(r'<[^>]+>', '', m.group(1)).strip()

            vod_content = ""
            m = re.search(r'简介[：:]\s*</em>\s*(.*?)(?:</li>|</ul>)', html, re.S)
            if m:
                vod_content = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if not vod_content:
                m = re.search(r'class="hl-content-text"[^>]*>(.*?)</span>', html, re.S)
                if m:
                    vod_content = re.sub(r'<[^>]+>', '', m.group(1)).strip()

            vod_douban = ""
            m = re.search(r'class="[^"]*hl-text-conch[^"]*score[^"]*"[^>]*>([^<]+)<', html)
            if m:
                vod_douban = m.group(1).strip()

            play_from, play_url = self._extract_play_info(html, vod_id)

            return {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "type_name": vod_class,
                "vod_year": vod_year,
                "vod_area": vod_area,
                "vod_remarks": status or vod_remarks,
                "vod_actor": actor,
                "vod_director": director,
                "vod_content": vod_content,
                "vod_play_from": play_from,
                "vod_play_url": play_url,
                "vod_douban_score": vod_douban,
            }

        except Exception as e:
            print("_extract_detail error: {0}".format(e))
            return None

    def _extract_play_info(self, html, vod_id):
        """从详情页HTML提取播放源和集数
        源标签: <a class="hl-tabs-btn" alt="北觅影视">北觅影视</a>
        集数: <div class="hl-tabs-box"><ul class="hl-plays-list">
                 <li><a href="/vodplay/{vid}-{sid}-{nid}.html">第01集</a></li>
               </ul></div>
        """
        try:
            play_from_list = []
            play_url_list = []

            source_names = re.findall(
                r'<a[^>]*class="[^"]*hl-tabs-btn[^"]*"[^>]*alt="([^"]+)"',
                html
            )

            if not source_names:
                source_names = re.findall(
                    r'<span class="hl-text-site">([^<]+)</span>',
                    html
                )

            if not source_names:
                return "", ""

            box_pattern = re.compile(
                r'<div class="hl-tabs-box[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
                re.S
            )
            boxes = box_pattern.findall(html)

            if not boxes:
                boxes = re.findall(
                    r'<ul class="hl-plays-list[^"]*"[^>]*>(.*?)</ul>',
                    html, re.S
                )
                boxes = [b for b in boxes]

            for i, source_name in enumerate(source_names):
                if i >= len(boxes):
                    break

                box_html = boxes[i]
                ep_links = re.findall(
                    r'<a[^>]*href="(/vodplay/([^"]+)\.html)"[^>]*>(.*?)</a>',
                    box_html, re.S
                )

                if not ep_links:
                    continue

                episodes = []
                for href, ep_id, ep_text in ep_links:
                    ep_name = re.sub(r'<[^>]+>', '', ep_text).strip()
                    if not ep_name:
                        ep_name = "第" + str(len(episodes) + 1) + "集"
                    episodes.append(ep_name + "$" + href)

                if episodes:
                    play_from_list.append(source_name)
                    play_url_list.append("#".join(episodes))

            return ("$$$".join(play_from_list), "$$$".join(play_url_list))

        except Exception as e:
            print("_extract_play_info error: {0}".format(e))
            return "", ""

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            page = int(pg) if int(pg) >= 1 else 1

            search_url = self.HOST + "/vodsearch/-------------.html"
            if page > 1:
                search_url = self.HOST + "/vodsearch/" + quote(key, safe="") + "----------" + str(page) + "---.html"

            post_data = {"wd": key}
            html = self._fetch(search_url, data=post_data)

            if not html:
                search_url2 = self.HOST + "/vodsearch/" + quote(key, safe="") + "------------.html"
                html = self._fetch(search_url2)

            if not html:
                return result

            videos = self._parse_list(html)
            result["list"] = videos

        except Exception as e:
            print("searchContent error: {0}".format(e))
        return result

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        """播放: 从播放页提取player_aaaa, 返回直链m3u8
        站点仅有一线路 "北觅影视" (from=dyttm3u8), URL为直链m3u8
        encrypt=0: url为明文直链
        encrypt=1: url经过URL编码
        encrypt=2: url经过base64编码
        """
        result = {"parse": 0, "playUrl": "", "url": "", "header": "", "jx": 0}
        try:
            play_path = id
            if "$" in play_path:
                play_path = play_path.split("$")[-1]
            play_path = play_path.strip()
            if not play_path.startswith("http"):
                if not play_path.startswith("/"):
                    play_path = "/" + play_path
                play_page_url = self.HOST + play_path
            else:
                play_page_url = play_path

            play_header = json.dumps({
                "User-Agent": self.UA,
                "Referer": self.HOST + "/",
            })

            html = self._fetch(play_page_url)
            if not html:
                result["parse"] = 1
                result["url"] = play_page_url
                result["header"] = play_header
                return result

            # 提取 player_aaaa
            player_data = None
            m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', html, re.S)
            if not m:
                m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*;', html, re.S)
            if not m:
                m = re.search(r'player_aaaa\s*=\s*(\{.*\})', html, re.S)

            if m:
                raw_json = m.group(1)
                try:
                    player_data = json.loads(raw_json)
                except:
                    try:
                        decoder = JSONDecoder()
                        player_data, _ = decoder.raw_decode(raw_json)
                    except:
                        pass

            if not player_data:
                result["parse"] = 1
                result["url"] = play_page_url
                result["header"] = play_header
                return result

            play_url = player_data.get("url", "")
            encrypt = player_data.get("encrypt", 0)

            if not play_url:
                result["parse"] = 1
                result["url"] = play_page_url
                result["header"] = play_header
                return result

            # 解密URL
            if encrypt == 1:
                try:
                    for _ in range(3):
                        decoded = unquote(play_url)
                        if decoded == play_url:
                            break
                        play_url = decoded
                except:
                    pass
            elif encrypt == 2:
                try:
                    play_url = base64.b64decode(play_url).decode("utf-8", errors="ignore")
                    try:
                        play_url = unquote(play_url)
                    except:
                        pass
                except:
                    pass

            try:
                play_url = html_unescape(play_url)
            except:
                pass
            play_url = play_url.strip()

            # 站点URL为直链m3u8, 直接播放
            if self._is_direct_video(play_url):
                result["parse"] = 0
                result["jx"] = 0
                result["url"] = play_url
                result["header"] = play_header
            else:
                # 非直链 -> 嗅探播放页
                result["parse"] = 1
                result["jx"] = 0
                result["url"] = play_page_url
                result["header"] = play_header

        except Exception as e:
            print("playerContent error: {0}".format(e))
            try:
                play_path = id
                if "$" in play_path:
                    play_path = play_path.split("$")[-1]
                play_path = play_path.strip()
                if not play_path.startswith("http"):
                    if not play_path.startswith("/"):
                        play_path = "/" + play_path
                    play_page_url = self.HOST + play_path
                else:
                    play_page_url = play_path
                result["parse"] = 1
                result["url"] = play_page_url
                result["header"] = json.dumps({
                    "User-Agent": self.UA,
                    "Referer": self.HOST + "/",
                })
            except:
                pass

        return result
