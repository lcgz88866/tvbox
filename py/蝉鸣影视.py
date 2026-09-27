# -*- coding: utf-8 -*-
# chanmea影视 (chanmea.cc) TVBox Python Spider
# 苹果CMS V10魔改版 (无标准API, 纯HTML解析)
# 5个分类, 子分类筛选(cateId), 多播放源, HTML页面解析获取m3u8

import re
import sys
import json
import ssl
import urllib.parse
import urllib.request

sys.path.append('..')

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


class Spider(Spider):

    HOST = "https://chanmea.cc"
    UA = "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # 主分类
    CATEGORIES = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "连续剧", "type_id": "15"},
        {"type_name": "综艺", "type_id": "24"},
        {"type_name": "动漫", "type_id": "30"},
        {"type_name": "短剧", "type_id": "47"},
    ]

    # 子分类 (cateId前缀L表示lists页面, 无前缀用cates)
    # 空=全部(用cates), L2=lists-2, L3=lists-3 ...
    SUB_CATS = {
        "1": [
            {"n": "全部", "v": ""},
            {"n": "动作片", "v": "L2"},
            {"n": "喜剧片", "v": "L3"},
            {"n": "爱情片", "v": "L4"},
            {"n": "科幻片", "v": "L5"},
            {"n": "恐怖片", "v": "L6"},
            {"n": "剧情片", "v": "L7"},
            {"n": "战争片", "v": "L8"},
            {"n": "纪录片", "v": "L9"},
            {"n": "悬疑片", "v": "L10"},
            {"n": "动画片", "v": "L11"},
            {"n": "犯罪片", "v": "L12"},
            {"n": "邵氏电影", "v": "L14"},
        ],
        "15": [
            {"n": "全部", "v": ""},
            {"n": "国产剧", "v": "L16"},
            {"n": "香港剧", "v": "L17"},
            {"n": "台湾剧", "v": "L18"},
            {"n": "美国剧", "v": "L19"},
            {"n": "韩国剧", "v": "L20"},
            {"n": "日本剧", "v": "L21"},
            {"n": "海外剧", "v": "L22"},
            {"n": "泰剧", "v": "L23"},
        ],
        "24": [
            {"n": "全部", "v": ""},
            {"n": "大陆综艺", "v": "L25"},
            {"n": "日韩综艺", "v": "L26"},
            {"n": "港台综艺", "v": "L27"},
            {"n": "欧美综艺", "v": "L28"},
            {"n": "演唱会", "v": "L29"},
        ],
        "30": [
            {"n": "全部", "v": ""},
            {"n": "国产动漫", "v": "L31"},
            {"n": "日韩动漫", "v": "L32"},
            {"n": "欧美动漫", "v": "L33"},
            {"n": "港台动漫", "v": "L34"},
            {"n": "海外动漫", "v": "L35"},
        ],
        "47": [
            {"n": "全部", "v": ""},
            {"n": "有声动漫", "v": "L48"},
            {"n": "女频恋爱", "v": "L49"},
            {"n": "反转爽剧", "v": "L50"},
            {"n": "脑洞悬疑", "v": "L51"},
            {"n": "年代穿越", "v": "L52"},
            {"n": "古装仙侠", "v": "L53"},
            {"n": "现代都市", "v": "L54"},
        ],
    }

    # 排序筛选
    SORT_FILTER = {
        "key": "by",
        "name": "排序",
        "value": [
            {"n": "最新", "v": "time"},
            {"n": "最热", "v": "hits"},
        ],
    }

    # 各分类总页数 (预估值)
    CAT_PAGES = {"1": 1327, "15": 438, "24": 94, "30": 183, "47": 908}
    # 子分类总页数上限 (lists页面上限2000)
    LISTS_MAX_PAGES = 2000

    def getName(self):
        return "chanmea影视"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": self.UA,
            "Referer": self.HOST,
        }
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|ts)(\?|#|$)', url, re.I))

    def manualVideoVCandidate(self, items):
        return []

    # ===== HTTP =====

    def _fetch_html(self, url, timeout=10):
        """获取HTML页面"""
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=timeout) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception:
            return ""

    # ===== 首页 =====

    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        result["class"] = self.CATEGORIES
        # 为每个分类添加子分类筛选 + 排序筛选
        for cat in self.CATEGORIES:
            tid = cat["type_id"]
            filters = []
            if tid in self.SUB_CATS:
                filters.append({
                    "key": "cateId",
                    "name": "类型",
                    "value": self.SUB_CATS[tid],
                })
            filters.append(self.SORT_FILTER)
            result["filters"][tid] = filters
        return result

    def homeVideoContent(self):
        result = {"list": []}
        html = self._fetch_html(f"{self.HOST}/?cates-1.html")
        if html:
            items = self._parse_category_items(html)
            result["list"] = items[:20]
        return result

    # ===== 分类 =====

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 40, "total": 0}
        try:
            extend = extend or {}
            if isinstance(extend, str):
                extend = json.loads(extend)

            cate_id = extend.get("cateId", "")
            by = extend.get("by", "")
            page = int(pg) if pg and int(pg) >= 1 else 1

            # 构造URL:
            # 1. 子分类选中 → ?lists-LID-PAGE.html (子分类不支持排序+分页)
            # 2. 全部 + 排序 → ?cates-TID-by-SORT-PAGE.html (排序不支持分页, 只返回第1页)
            # 3. 全部 + 无排序 → ?cates-TID-PAGE.html (标准分页)
            if cate_id and cate_id.startswith("L"):
                # 子分类模式
                lid = cate_id[1:]
                if by and page == 1:
                    url = f"{self.HOST}/?lists-{lid}-by-{by}-1.html"
                else:
                    url = f"{self.HOST}/?lists-{lid}-{page}.html"
                max_page = self.LISTS_MAX_PAGES
            elif by:
                # 排序模式 (排序不支持分页, page>1时降级为普通分页)
                if page == 1:
                    url = f"{self.HOST}/?cates-{tid}-by-{by}-1.html"
                else:
                    url = f"{self.HOST}/?cates-{tid}-{page}.html"
                max_page = self.CAT_PAGES.get(tid, 1)
            else:
                # 标准模式
                url = f"{self.HOST}/?cates-{tid}-{page}.html"
                max_page = self.CAT_PAGES.get(tid, 1)

            html = self._fetch_html(url)
            if not html:
                return result

            items = self._parse_category_items(html)
            result["page"] = page
            result["pagecount"] = max_page
            result["limit"] = 40
            result["total"] = max_page * 40
            result["list"] = items
        except Exception:
            pass
        return result

    def _parse_category_items(self, html):
        """解析分类页视频列表"""
        items = []
        try:
            boxes = re.findall(r'<div class="myui-vodlist__box">([\s\S]*?)</div>\s*</div>', html)
            for box in boxes:
                vid = re.search(r'vodss-(\d+)', box)
                title = re.search(r'title="([^"]+)"', box)
                pic = re.search(r'data-original="([^"]+)"', box)
                remarks = re.search(r'pic-tag[^>]*>([^<]+)<', box)
                if vid and title:
                    items.append({
                        "vod_id": vid.group(1),
                        "vod_name": title.group(1),
                        "vod_pic": pic.group(1) if pic else "",
                        "vod_remarks": remarks.group(1).strip() if remarks else "",
                    })
        except Exception:
            pass
        return items

    # ===== 详情 =====

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            html = self._fetch_html(f"{self.HOST}/?vodss-{vod_id}.html")
            if not html:
                return result

            # 标题
            title = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            # 封面
            pic = re.search(r'myui-content__thumb[\s\S]*?data-original="([^"]+)"', html)
            # 分类 (在<a>标签中)
            cat_name = re.search(r'分类：</span>\s*<a[^>]*>([^<]+)</a>', html)
            # 地区 (在<a>标签中)
            area = re.search(r'地区：</span>\s*<a[^>]*>([^<]+)</a>', html)
            # 年份 (在<a>标签中)
            year = re.search(r'年份：</span>\s*<a[^>]*>(\d+)</a>', html)
            # 主演 (纯文本)
            actor = re.search(r'主演：</span>\s*([^<]+)', html)
            # 导演 (在<a>标签中)
            director = re.search(r'导演：</span>\s*<a[^>]*>([^<]+)</a>', html)
            if not director:
                director = re.search(r'导演：</span>\s*([^<]+)', html)
            # 简介
            content = re.search(r'简介：</span>\s*([\s\S]*?)(?:<a|</p>)', html)
            # 备注 (封面图上的标签)
            remarks = re.search(r'myui-content__thumb[\s\S]*?pic-tag[^>]*>([^<]+)<', html)

            # 播放源和剧集
            play_from, play_url = self._parse_play_sources(html, vod_id)

            vod = {
                "vod_id": vod_id,
                "vod_name": title.group(1).strip() if title else "",
                "vod_pic": pic.group(1) if pic else "",
                "vod_actor": self._clean_text(actor.group(1)) if actor else "",
                "vod_director": self._clean_text(director.group(1)) if director else "",
                "vod_year": year.group(1) if year else "",
                "vod_area": self._clean_text(area.group(1)) if area else "",
                "vod_remarks": remarks.group(1).strip() if remarks else "",
                "vod_content": self._clean_text(content.group(1)) if content else "",
                "type_name": cat_name.group(1).strip() if cat_name else "",
                "vod_play_from": play_from,
                "vod_play_url": play_url,
            }
            result["list"].append(vod)
        except Exception:
            pass
        return result

    def _parse_play_sources(self, html, vod_id):
        """解析播放源和剧集列表"""
        try:
            tabs = re.findall(r'<a[^>]*href="#(playlist\d+)"[^>]*>([^<]+)</a>', html)
            if not tabs:
                tabs = [("playlist1", "播放器1")]

            play_from_list = []
            play_url_list = []

            for playlist_id, tab_name in tabs:
                pattern = rf'id="{re.escape(playlist_id)}"[^>]*>([\s\S]*?)</div>'
                section = re.search(pattern, html)
                if not section:
                    continue

                section_html = section.group(1)
                episodes = re.findall(
                    rf'href="\?plays-{vod_id}-(\d+)-(\d+)\.html"[^>]*>([^<]+)',
                    section_html
                )

                if not episodes:
                    continue

                play_from_list.append(tab_name.strip())
                ep_list = []
                for src, ep, name in episodes:
                    ep_id = f"{vod_id}-{src}-{ep}"
                    ep_list.append(f"{name.strip()}${ep_id}")
                play_url_list.append("#".join(ep_list))

            return "$$$".join(play_from_list), "$$$".join(play_url_list)
        except Exception:
            return "", ""

    # ===== 搜索 =====

    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            wd = urllib.parse.quote(key)
            url = f"{self.HOST}/?search.html&keyword={wd}"
            html = self._fetch_html(url)
            if not html:
                return result

            search_list = re.search(r'id="searchList">([\s\S]*?)</ul>', html)
            if not search_list:
                return result

            items = re.findall(r'<li class="clearfix">\s*<div class="thumb">([\s\S]*?)</div>\s*<div class="detail">([\s\S]*?)</div>\s*</li>', search_list.group(1))
            for thumb, detail in items:
                vid = re.search(r'vodss-(\d+)', thumb)
                if not vid:
                    vid = re.search(r'vodss-(\d+)', detail)
                title = re.search(r'title="([^"]+)"', thumb)
                if not title:
                    title = re.search(r'class="searchkey"[^>]*>([^<]+)', detail)
                pic = re.search(r'data-original="([^"]+)"', thumb)
                remarks = re.search(r'pic-tag[^>]*>([^<]+)<', thumb)

                if vid:
                    result["list"].append({
                        "vod_id": vid.group(1),
                        "vod_name": title.group(1).strip() if title else "",
                        "vod_pic": pic.group(1) if pic else "",
                        "vod_remarks": remarks.group(1).strip() if remarks else "",
                    })
        except Exception:
            pass
        return result

    # ===== 播放 =====

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "header": "", "url": "", "playUrl": ""}
        try:
            if "$" in id:
                play_id = id.split("$")[-1]
            else:
                play_id = id

            parts = play_id.split("-")
            if len(parts) >= 3:
                vod_id, src, ep = parts[0], parts[1], parts[2]
            elif len(parts) >= 2:
                vod_id, src, ep = parts[0], "1", parts[1]
            else:
                return result

            play_url = f"{self.HOST}/?plays-{vod_id}-{src}-{ep}.html"
            html = self._fetch_html(play_url)
            if html:
                m3u8_match = re.search(r'wsyzy\.top/m3u8/\?url=(https?://[^"\'&]+)', html)
                if m3u8_match:
                    actual_url = urllib.parse.unquote(m3u8_match.group(1))
                    result["url"] = actual_url
                    result["parse"] = 0
                else:
                    direct = re.search(r'(https?://[^"\'<\s]+\.(?:m3u8|mp4)[^"\'<\s]*)', html)
                    if direct:
                        result["url"] = direct.group(1)
                        result["parse"] = 0
        except Exception:
            pass
        return result

    # ===== 工具 =====

    def _clean_text(self, text):
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        text = text.strip()
        if len(text) > 200:
            text = text[:200] + "..."
        return text


if __name__ == "__main__":
    import time

    s = Spider()
    s.init()

    print("===== 首页分类 =====")
    home = s.homeContent(True)
    print(f"分类数: {len(home['class'])}")
    for c in home["class"]:
        print(f"  {c['type_name']} -> {c['type_id']}")
        filters = home["filters"].get(c["type_id"], [])
        for f in filters:
            print(f"    筛选: {f['name']} ({len(f['value'])}项)")
            for v in f["value"][:3]:
                print(f"      {v['n']} -> {v['v']}")
            if len(f["value"]) > 3:
                print(f"      ... 共{len(f['value'])}项")

    print("\n===== 分类列表 (电影第1页, 全部) =====")
    cat = s.categoryContent("1", "1", True, {})
    print(f"返回: {len(cat['list'])}条, 总页数: {cat['pagecount']}")
    for v in cat["list"][:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 分类列表 (电影-动作片, 第1页) =====")
    cat2 = s.categoryContent("1", "1", True, {"cateId": "L2"})
    print(f"返回: {len(cat2['list'])}条, 总页数: {cat2['pagecount']}")
    for v in cat2["list"][:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 分类列表 (电影-动作片, 第2页) =====")
    cat3 = s.categoryContent("1", "2", True, {"cateId": "L2"})
    print(f"返回: {len(cat3['list'])}条")
    for v in cat3["list"][:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 分类列表 (电影-最热, 第1页) =====")
    cat4 = s.categoryContent("1", "1", True, {"by": "hits"})
    print(f"返回: {len(cat4['list'])}条")
    for v in cat4["list"][:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 分类列表 (连续剧-国产剧, 第1页) =====")
    cat5 = s.categoryContent("15", "1", True, {"cateId": "L16"})
    print(f"返回: {len(cat5['list'])}条")
    for v in cat5["list"][:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 分类列表 (短剧-反转爽剧, 第1页) =====")
    cat6 = s.categoryContent("47", "1", True, {"cateId": "L50"})
    print(f"返回: {len(cat6['list'])}条")
    for v in cat6["list"][:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 详情页 + 播放 =====")
    detail = s.detailContent(["53509"])
    if detail["list"]:
        vod = detail["list"][0]
        print(f"  标题: {vod['vod_name']}  年份: {vod['vod_year']}  地区: {vod['vod_area']}")
        print(f"  播放源: {vod['vod_play_from']}")
        first_ep = vod["vod_play_url"].split("#")[0]
        play = s.playerContent("播放器1", first_ep, [])
        print(f"  播放URL: {play.get('url', '')[:80]}")
        print(f"  Parse: {play.get('parse')}")

    print("\n===== 搜索 (庆余年) =====")
    search = s.searchContent("庆余年", False)
    print(f"结果: {len(search['list'])}条")
    for v in search["list"][:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")