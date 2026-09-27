# -*- coding: utf-8 -*-
# 飞飞影视 - www.ffys.me
# 苹果CMS V10 通用适配（增强版）
import re
import sys
import json
import ssl
import html as html_lib
import urllib.parse
import urllib.request

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def getName(self):
        return "飞飞影视"

    def init(self, extend=""):
        self.host = "https://www.ffys.me"
        self.ua = "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Referer": self.host,
        }
        # TVBox 网页播放点击代码：打开播放页后点击 iframe 内的 #start 按钮
        self.click_code = 'document.querySelector("#playleft iframe").contentWindow.document.querySelector("#start").click();'
        # 分类（飞飞影视当前站点真实ID）
        self.cats = [
            {"type_name": "电影", "type_id": "20"},
            {"type_name": "剧集", "type_id": "21"},
            {"type_name": "动漫", "type_id": "22"},
            {"type_name": "综艺", "type_id": "23"},
            {"type_name": "爽剧", "type_id": "25"},
        ]
        # 筛选选项（通用）
        self._class_opts = [
            {"n": "全部", "v": ""},
            {"n": "喜剧", "v": "喜剧"},
            {"n": "爱情", "v": "爱情"},
            {"n": "恐怖", "v": "恐怖"},
            {"n": "动作", "v": "动作"},
            {"n": "科幻", "v": "科幻"},
            {"n": "剧情", "v": "剧情"},
            {"n": "战争", "v": "战争"},
            {"n": "警匪", "v": "警匪"},
            {"n": "犯罪", "v": "犯罪"},
            {"n": "动画", "v": "动画"},
            {"n": "奇幻", "v": "奇幻"},
            {"n": "武侠", "v": "武侠"},
            {"n": "冒险", "v": "冒险"},
            {"n": "悬疑", "v": "悬疑"},
            {"n": "惊悚", "v": "惊悚"},
            {"n": "历史", "v": "历史"},
            {"n": "运动", "v": "运动"},
            {"n": "古装", "v": "古装"},
            {"n": "纪录", "v": "纪录"},
            {"n": "儿童", "v": "儿童"},
            {"n": "微电影", "v": "微电影"},
            {"n": "农村", "v": "农村"},
            {"n": "其他", "v": "其他"},
        ]
        self._area_opts = [
            {"n": "全部", "v": ""},
            {"n": "大陆", "v": "大陆"},
            {"n": "香港", "v": "香港"},
            {"n": "台湾", "v": "台湾"},
            {"n": "美国", "v": "美国"},
            {"n": "韩国", "v": "韩国"},
            {"n": "日本", "v": "日本"},
            {"n": "泰国", "v": "泰国"},
            {"n": "新加坡", "v": "新加坡"},
            {"n": "马来西亚", "v": "马来西亚"},
            {"n": "印度", "v": "印度"},
            {"n": "英国", "v": "英国"},
            {"n": "法国", "v": "法国"},
            {"n": "加拿大", "v": "加拿大"},
            {"n": "西班牙", "v": "西班牙"},
            {"n": "俄罗斯", "v": "俄罗斯"},
            {"n": "其它", "v": "其它"},
        ]
        self._year_opts = [
            {"n": "全部", "v": ""},
            {"n": "2026", "v": "2026"},
            {"n": "2025", "v": "2025"},
            {"n": "2024", "v": "2024"},
            {"n": "2023", "v": "2023"},
            {"n": "2022", "v": "2022"},
            {"n": "2021", "v": "2021"},
            {"n": "2020", "v": "2020"},
            {"n": "2019", "v": "2019"},
            {"n": "2018", "v": "2018"},
            {"n": "2017", "v": "2017"},
            {"n": "2016", "v": "2016"},
            {"n": "2015", "v": "2015"},
            {"n": "2014", "v": "2014"},
            {"n": "2013", "v": "2013"},
            {"n": "2012", "v": "2012"},
            {"n": "2011", "v": "2011"},
            {"n": "2010", "v": "2010"},
            {"n": "2009", "v": "2009"},
            {"n": "2008", "v": "2008"},
            {"n": "2007", "v": "2007"},
            {"n": "2006", "v": "2006"},
            {"n": "2005", "v": "2005"},
            {"n": "2004", "v": "2004"},
        ]

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        if not url:
            return False
        return re.search(r'\.(m3u8|mp4|flv|avi|mkv|mov|ts)(?:\?|$)', url, re.I) is not None

    def manualVideoCheck(self):
        return False

    def action(self, action):
        return None

    def destroy(self):
        return None

    def fetch_html(self, url):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            print(f'fetch_html error: {e}')
            return ""

    def _clean_text(self, text):
        if not text:
            return ""
        text = re.sub(r'<script[\s\S]*?</script>', '', text, flags=re.I)
        text = re.sub(r'<style[\s\S]*?</style>', '', text, flags=re.I)
        text = re.sub(r'<[^>]+>', '', text)
        text = html_lib.unescape(text)
        return re.sub(r'\s+', ' ', text).strip()

    def _abs_url(self, url):
        if not url:
            return ""
        url = html_lib.unescape(url.strip())
        if url.startswith("//"):
            return "https:" + url
        return urllib.parse.urljoin(self.host + "/", url)

    # ==================== 列表解析（不依赖特定类名） ====================
    def _parse_list(self, html):
        items = []
        seen = set()
        # 匹配所有指向 /video/数字.html 的 <a> 标签，并提取内部内容
        for m in re.finditer(
            r'<a[^>]*href=["\'](?:https?://[^"\']+)?/(?:video|detail)/(\d+)\.html["\'][^>]*>(.*?)</a>',
            html, re.S
        ):
            vod_id = m.group(1)
            if vod_id in seen:
                continue
            seen.add(vod_id)
            a_tag = m.group(0)          # 完整a标签
            a_content = m.group(2)      # a标签内部内容

            # 提取标题：优先从 title 属性，否则从内部 img 的 alt 属性，再否则取内部文本
            title_m = re.search(r'title=["\']([^"\']+)["\']', a_tag)
            if title_m:
                vod_name = html_lib.unescape(title_m.group(1)).strip()
            else:
                title_m = re.search(r'<img[^>]*alt=["\']([^"\']+)["\']', a_tag)
                if title_m:
                    vod_name = html_lib.unescape(title_m.group(1)).strip()
                else:
                    # 取内部纯文本（去除html标签）
                    vod_name = self._clean_text(a_content)

            # 提取图片：优先 data-src，其次 src
            pic_m = (
                re.search(r'data-original=["\']([^"\']+)["\']', a_tag)
                or re.search(r'data-src=["\']([^"\']+)["\']', a_tag)
                or re.search(r'background\s*:\s*url\(([^)]+)\)', a_tag, re.I)
                or re.search(r'src=["\']([^"\']+)["\']', a_tag)
            )
            vod_pic = self._abs_url(pic_m.group(1)) if pic_m else ""
            if 'img.meituan.net/content/187e1c5aeebcc123b538699e5a09a522107341.gif' in vod_pic:
                vod_pic = ""

            # 提取备注（集数/状态）：找常见的 class 或直接从文本中截取
            remarks_m = re.search(r'<[^>]+class="[^"]*(?:module-item-note|prb|remarks|state|hint|label)[^"]*"[^>]*>(.*?)</[^>]+>', a_content, re.S)
            vod_remarks = self._clean_text(remarks_m.group(1)) if remarks_m else ""
            if not vod_remarks:
                # 尝试匹配 “第X集” 或 “更新至X集” 等
                remark_match = re.search(r'(更新至?\s*第?\s*\d+集|第\d+集)', a_content)
                if remark_match:
                    vod_remarks = remark_match.group(1)

            # 首页轮播、详情按钮、搜索页底部等链接可能没有海报图，TVBox 首页会显示空图，直接跳过
            if not vod_name or not vod_pic:
                continue

            items.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks,
            })
        return items

    # ==================== URL 构造（可自行切换格式） ====================
    def _build_list_url(self, tid, area="", cls="", year="", page="1"):
        # 首页导航使用 /type/20.html；带分页/筛选时使用 /vodshow/... 格式
        if str(page) == "1" and not area and not cls and not year:
            return f"{self.host}/type/{tid}.html"

        path = f"{self.host}/vodshow"
        if area:
            path += f"/area/{urllib.parse.quote(str(area))}"
        if cls:
            path += f"/class/{urllib.parse.quote(str(cls))}"
        path += f"/id/{tid}"
        if year:
            path += f"/year/{urllib.parse.quote(str(year))}"
        if str(page) != "1":
            path += f"/page/{page}"
        path += ".html"
        return path

    # ==================== 首页 ====================
    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        try:
            result["class"] = self.cats
            for cat in self.cats:
                tid = cat["type_id"]
                result["filters"][tid] = [
                    {"key": "class", "name": "类型", "value": self._class_opts},
                    {"key": "area", "name": "地区", "value": self._area_opts},
                    {"key": "year", "name": "年份", "value": self._year_opts},
                ]
            html = self.fetch_html(self.host)
            if html:
                result["list"] = self._parse_list(html)[:30]
        except Exception as e:
            print(f'homeContent error: {e}')
        return result

    def homeVideoContent(self):
        result = {"list": []}
        try:
            html = self.fetch_html(self.host)
            if html:
                result["list"] = self._parse_list(html)[:30]
        except Exception as e:
            print(f'homeVideoContent error: {e}')
        return result

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
        try:
            area = extend.get("area", "") if extend else ""
            cls = extend.get("class", "") if extend else ""
            year = extend.get("year", "") if extend else ""
            page = pg if int(pg) >= 1 else "1"
            url = self._build_list_url(tid, area, cls, year, page)
            html = self.fetch_html(url)
            if html:
                result["list"] = self._parse_list(html)
                # 分页解析（兼容多种样式）
                page_m = re.search(r'<span[^>]*class="[^"]*page[^"]*"[^>]*>.*?(\d+)/(\d+)</span>', html, re.S)
                if not page_m:
                    page_m = re.search(r'当前(\d+)/(\d+)页', html)
                if not page_m:
                    page_m = re.search(r'共(\d+)页', html)
                    if page_m:
                        result["pagecount"] = int(page_m.group(1))
                    else:
                        result["pagecount"] = int(pg) + 1 if result["list"] else 1
                else:
                    result["pagecount"] = int(page_m.group(2))
        except Exception as e:
            print(f'categoryContent error: {e}')
        return result

    # ==================== 详情 ====================
    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            detail_html = self.fetch_html(f"{self.host}/video/{vod_id}.html")
            if not detail_html:
                detail_html = self.fetch_html(f"{self.host}/detail/{vod_id}.html")
            if not detail_html:
                return result

            # ---- 基本信息 ----
            vod_name = ""
            title_m = re.search(r'<h3 class="slide-info-title hide">([^<]+)</h3>', detail_html)
            if not title_m:
                title_m = re.search(r'<h1[^>]*>(.*?)</h1>', detail_html, re.S)
            if not title_m:
                title_m = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h1>', detail_html)
            if title_m:
                vod_name = self._clean_text(title_m.group(1))

            vod_pic = ""
            pic_m = (
                re.search(r'data-original="([^"]+)"', detail_html)
                or re.search(r'data-src="([^"]+)"', detail_html)
                or re.search(r'<img[^>]*src="([^"]+)"', detail_html)
            )
            if pic_m:
                vod_pic = pic_m.group(1).replace("&amp;", "&")

            def clean_people(html_text):
                names = []
                for a in re.finditer(r'<a[^>]*>(.*?)</a>', html_text, re.S):
                    name = self._clean_text(a.group(1))
                    if name:
                        names.append(name)
                if names:
                    return ",".join(names)
                text = self._clean_text(html_text)
                text = re.sub(r'\s*/\s*', ',', text).strip(' ,/')
                return text

            def extract_info_item(label):
                pattern = (
                    r'<div[^>]*class=["\'][^"\']*module-info-item[^"\']*["\'][^>]*>\s*'
                    r'<span[^>]*class=["\'][^"\']*module-info-item-title[^"\']*["\'][^>]*>\s*'
                    + re.escape(label) +
                    r'\s*[：:]\s*</span>\s*'
                    r'<div[^>]*class=["\'][^"\']*module-info-item-content[^"\']*["\'][^>]*>(.*?)</div>'
                )
                m = re.search(pattern, detail_html, re.S)
                return clean_people(m.group(1)) if m else ""

            vod_director = extract_info_item("导演")
            vod_actor = extract_info_item("主演")

            vod_year = ""
            vod_area = ""
            vod_class = ""
            tag_html = ""
            tag_start = detail_html.find('module-info-tag')
            if tag_start != -1:
                tag_end = detail_html.find('module-mobile-play', tag_start)
                tag_html = detail_html[tag_start:tag_end if tag_end != -1 else tag_start + 3000]
                year_m = re.search(r'href=["\'][^"\']*/year/(\d{4})\.html["\'][^>]*>(.*?)</a>', tag_html, re.S)
                if year_m:
                    vod_year = self._clean_text(year_m.group(2)) or year_m.group(1)
                area_m = re.search(r'href=["\'][^"\']*/area/[^"\']+/id/\d+\.html["\'][^>]*>(.*?)</a>', tag_html, re.S)
                if area_m:
                    vod_area = self._clean_text(area_m.group(1))
                class_names = []
                for class_m in re.finditer(r'href=["\'][^"\']*/class/[^"\']+/id/\d+\.html["\'][^>]*>(.*?)</a>', tag_html, re.S):
                    name = self._clean_text(class_m.group(1))
                    if name and name not in class_names:
                        class_names.append(name)
                vod_class = ",".join(class_names)

            vod_remarks = ""
            remarks_m = re.search(r'<div[^>]*class=["\'][^"\']*module-item-note[^"\']*["\'][^>]*>(.*?)</div>', detail_html, re.S)
            if remarks_m:
                vod_remarks = self._clean_text(remarks_m.group(1))
            if not vod_remarks:
                state_m = re.search(r'(更新至?第?\d+集|第\d+集|已完结|全集|HD[^<\s]*|正片|蓝光[^<\s]*)', detail_html)
                if state_m:
                    vod_remarks = state_m.group(1).strip()

            vod_content = ""
            content_m = re.search(r'<div[^>]*class=["\'][^"\']*module-info-introduction-content[^"\']*["\'][^>]*>(.*?)</div>', detail_html, re.S)
            if not content_m:
                content_m = re.search(r'<div id="height_limit"[^>]*>(.*?)</div>', detail_html, re.S)
            if not content_m:
                content_m = re.search(r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>', detail_html, re.S)
            if content_m:
                vod_content = self._clean_text(content_m.group(1))
                vod_content = vod_content.replace('简介:', '').replace('简介：', '').strip()

            # ---- 播放列表 ----
            # 当前站点使用 module-tab-item 表示播放线路，module-list 面板表示对应集数
            line_names = []
            for m in re.finditer(r'<div[^>]*class=["\'][^"\']*\bmodule-tab-item\b[^"\']*["\'][^>]*>', detail_html, re.S):
                tag = m.group(0)
                name_m = re.search(r'data-dropdown-value=["\']([^"\']+)["\']', tag)
                if name_m:
                    name = html_lib.unescape(name_m.group(1)).strip()
                else:
                    end = detail_html.find('</div>', m.end())
                    name = self._clean_text(detail_html[m.end():end]) if end != -1 else ""
                    name = re.sub(r'\d+$', '', name).strip()
                if name:
                    line_names.append(name)

            boxes = re.split(
                r'<div[^>]*class=["\'][^"\']*module-list[^"\']*his-tab-list[^"\']*["\'][^>]*>',
                detail_html,
                flags=re.S
            )[1:]
            if not line_names:
                line_names = [f"线路{i + 1}" for i in range(len(boxes))]

            def parse_eps(box_html):
                eps = re.findall(r'href=["\']/(?:player|play)/(\d+)-(\d+)-(\d+)\.html["\'][^>]*>(.*?)</a>', box_html, re.S)
                urls = []
                seen_ep = set()
                for ep_id, ep_sid, ep_nid, ep_name_raw in eps:
                    ep_key = f"{ep_id}-{ep_sid}-{ep_nid}"
                    if ep_key in seen_ep:
                        continue
                    seen_ep.add(ep_key)
                    ep_name = self._clean_text(ep_name_raw)
                    if not ep_name:
                        ep_name = f"第{ep_nid}集"
                    urls.append(f"{ep_name}${ep_key}")
                return urls

            lines = []
            name_counter = {}
            if boxes:
                for idx, box_html in enumerate(boxes):
                    urls = parse_eps(box_html)
                    if not urls:
                        continue
                    base = line_names[idx] if idx < len(line_names) else f"线路{idx + 1}"
                    if base in name_counter:
                        name_counter[base] += 1
                        line_name = f"{base}{name_counter[base]}"
                    else:
                        name_counter[base] = 1
                        line_name = base
                    lines.append((line_name, urls))

            if not lines:
                urls = parse_eps(detail_html)
                if urls:
                    lines.append((line_names[0] if line_names else "线路1", urls))

            # 线路排序（至臻 > 自营 > 蓝光）
            def sort_key(item):
                name = item[0]
                core = re.sub(r'\d+$', '', name)
                if '至臻' in core:
                    return 0
                elif '自营' in core or '自选' in core:
                    return 1
                elif '蓝光' in core:
                    return 2
                else:
                    return 3
            lines.sort(key=sort_key)

            play_from = [line[0] for line in lines]
            play_url = ["#".join(line[1]) for line in lines]

            # ---- 组装结果 ----
            if not vod_name:
                vod_name = f"视频{vod_id}"

            result["list"] = [{
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": self._abs_url(vod_pic),
                "vod_director": vod_director,
                "vod_actor": vod_actor,
                "vod_year": vod_year,
                "vod_area": vod_area,
                "vod_class": vod_class,
                "vod_content": vod_content,
                "vod_remarks": vod_remarks,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }]
        except Exception as e:
            print(f'detailContent error: {e}')
        return result

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            wd = urllib.parse.quote(key)
            # 当前站点精确搜索地址
            url = f"{self.host}/vodsearch.html?wd={wd}"
            html = self.fetch_html(url)
            if not html:
                url = f"{self.host}/vodsearch/{wd}-------------.html"
                html = self.fetch_html(url)
            if not html:
                url = f"{self.host}/index.php/vod/search/wd/{wd}.html"
                html = self.fetch_html(url)
            if not html:
                url = f"{self.host}/search.php?searchword={wd}"
                html = self.fetch_html(url)
            if not html:
                url = f"{self.host}/vod/search?wd={wd}"
                html = self.fetch_html(url)
            if html:
                result["list"] = self._parse_list(html)
        except Exception as e:
            print(f'searchContent error: {e}')
        return result

    # ==================== 播放 ====================
    # 播放模式：默认使用网页播放（parse=1），由 TVBox WebView + 配置里的 click JS 点击播放。
    # 如果能解析出真实 m3u8/mp4 直链，则使用直链模式（parse=0）。
    def playerContent(self, flag, pid, vipFlags):
        result = {}
        try:
            parts = pid.split("-")
            if len(parts) == 3:
                vid, sid, nid = parts
                play_url = f"{self.host}/player/{vid}-{sid}-{nid}.html"
                referer = f"{self.host}/video/{vid}.html"
            else:
                play_url = f"{self.host}/player/{pid}.html"
                referer = self.host

            html = self.fetch_html(play_url)
            if not html:
                # 降级到旧路径
                play_url = f"{self.host}/play/{pid}.html"
                html = self.fetch_html(play_url)

            # ---- 优先尝试直链解析（m3u8/mp4 等） ----
            if html:
                m = re.search(r'var\s+(?:player_aaaa|player_info|player_data)\s*=\s*(\{[\s\S]*?\})\s*</script>', html, re.I)
                if not m:
                    m = re.search(r'player_aaaa\s*=\s*(\{[\s\S]*?\})\s*;', html, re.I)
                if m:
                    try:
                        data = json.loads(m.group(1))
                        url = html_lib.unescape(data.get("url", "")).strip()
                        url = urllib.parse.unquote(url)
                        if url and self.isVideoFormat(url):
                            result["parse"] = 0
                            result["url"] = self._abs_url(url)
                            result["header"] = {"User-Agent": self.ua, "Referer": referer}
                            result["click"] = self.click_code
                            return result
                    except Exception as e:
                        print(f'player parse error: {e}')

            # ---- 网页播放模式（配合 TVBox 配置里的 click 代码点击播放） ----
            result["parse"] = 1
            result["url"] = play_url
            result["header"] = {"User-Agent": self.ua, "Referer": referer}
            result["click"] = self.click_code
        except Exception as e:
            print(f'playerContent error: {e}')
            result["parse"] = 1
            result["url"] = f"{self.host}/player/{pid}.html"
            result["header"] = {"User-Agent": self.ua, "Referer": self.host}
            result["click"] = self.click_code
        return result

    def localProxy(self, params):
        return [404, "text/plain", b"Not supported"]