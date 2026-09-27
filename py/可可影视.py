# -*- coding: utf-8 -*-
# 可可影视 - https://www.kkys03.com
# TVBox Python 爬虫适配
import re
import sys
import json
import ssl
import hashlib
import time
import html as html_lib
import urllib.parse
import urllib.request
import urllib.error

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def getName(self):
        return "可可影视"

    def init(self, extend=""):
        self.host = "https://www.kkys03.com"
        self.img_host = "https://vres.cyscyy.com"
        self.ua = "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.cookie = ""
        self.search_token = ""
        self.play_url_cache = {}

        # 只保留四个分类。type_id 用纯数字，真实网站路径在 _build_list_urls 内部映射。
        self.cats = [
            {"type_name": "电影", "type_id": "1"},
            {"type_name": "连续剧", "type_id": "2"},
            {"type_name": "动漫", "type_id": "3"},
            {"type_name": "综艺", "type_id": "4"},
        ]

        self._year_opts = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 2003, -1)]
        self._area_opts = [
            {"n": "全部", "v": ""},
            {"n": "大陆", "v": "大陆"},
            {"n": "香港", "v": "香港"},
            {"n": "台湾", "v": "台湾"},
            {"n": "美国", "v": "美国"},
            {"n": "韩国", "v": "韩国"},
            {"n": "日本", "v": "日本"},
            {"n": "泰国", "v": "泰国"},
            {"n": "英国", "v": "英国"},
            {"n": "法国", "v": "法国"},
            {"n": "其它", "v": "其它"},
        ]
        self._class_opts = [
            {"n": "全部", "v": ""},
            {"n": "动作", "v": "动作"},
            {"n": "喜剧", "v": "喜剧"},
            {"n": "爱情", "v": "爱情"},
            {"n": "科幻", "v": "科幻"},
            {"n": "恐怖", "v": "恐怖"},
            {"n": "剧情", "v": "剧情"},
            {"n": "悬疑", "v": "悬疑"},
            {"n": "犯罪", "v": "犯罪"},
            {"n": "动画", "v": "动画"},
            {"n": "纪录", "v": "纪录"},
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

    def _solve_cdndefend_cookie(self, html):
        """
        可可影视目前会返回 cdndefend 的 850 验证页。
        页面里的逻辑是：sha1(seed + i).digest()[int(seed[0],16)] == 0xb0
        且下一位 == 0x0b，满足后写入 cdndefend_js_cookie。
        """
        try:
            if not html or "cdndefend_js_cookie" not in html:
                return ""
            seed_m = re.search(r'["\']([A-Fa-f0-9]{40})["\']', html)
            if not seed_m:
                seed_m = re.search(r'([A-Fa-f0-9]{40})', html)
            if not seed_m:
                return ""
            seed = seed_m.group(1)
            n1 = int(seed[0], 16)
            for i in range(0, 2000000):
                digest = hashlib.sha1((seed + str(i)).encode("utf-8")).digest()
                if digest[n1] == 0xb0 and digest[n1 + 1] == 0x0b:
                    return seed + str(i)
        except Exception as e:
            print(f"cdndefend solve error: {e}")
        return ""

    def fetch_html(self, url, retry=2):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            headers = dict(self.headers)
            if self.cookie:
                headers["Cookie"] = self.cookie
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
                if "Protected by cdndefend" in text:
                    cookie_val = self._solve_cdndefend_cookie(text)
                    if retry > 0 and cookie_val:
                        self.cookie = "cdndefend_js_cookie=" + cookie_val
                        time.sleep(1)
                        return self.fetch_html(url, retry=retry - 1)
                    return ""
                return text
        except urllib.error.HTTPError as e:
            try:
                text = e.read().decode("utf-8", errors="ignore")
                if text and "Protected by cdndefend" in text:
                    cookie_val = self._solve_cdndefend_cookie(text)
                    if retry > 0 and cookie_val:
                        self.cookie = "cdndefend_js_cookie=" + cookie_val
                        time.sleep(1)
                        return self.fetch_html(url, retry=retry - 1)
                    return ""
                elif text:
                    return text
            except Exception:
                pass
            print(f"fetch_html http error: {e}")
            return ""
        except Exception as e:
            print(f"fetch_html error: {e}")
            return ""

    def _clean_text(self, text):
        if not text:
            return ""
        text = re.sub(r'<script[\s\S]*?</script>', '', text, flags=re.I)
        text = re.sub(r'<style[\s\S]*?</style>', '', text, flags=re.I)
        text = re.sub(r'<[^>]+>', '', text)
        text = html_lib.unescape(text)
        return re.sub(r'\s+', ' ', text).strip()

    def _clean_url(self, url):
        if not url:
            return ""
        return url.strip().strip("'\"").replace("&amp;", "&").replace("\\/", "/")

    def _abs_url(self, url):
        if not url:
            return ""
        url = self._clean_url(url)
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/vod"):
            return self.img_host + url
        return urllib.parse.urljoin(self.host + "/", url)

    def _pick_pic(self, html):
        candidates = []
        for pattern in [
            r'data-original=["\']([^"\']+)["\']',
            r'data-src=["\']([^"\']+)["\']',
            r'<img[^>]+src=["\']([^"\']+)["\']',
            r'background\s*:\s*url\(([^)]+)\)',
        ]:
            for m in re.finditer(pattern, html, re.I | re.S):
                pic = self._abs_url(m.group(1))
                if not pic:
                    continue
                if "logo_placeholder" in pic or "placeholder_vertical" in pic:
                    continue
                if pic not in candidates:
                    candidates.append(pic)
        return candidates[0] if candidates else ""

    def _extract_div_blocks(self, html, class_name):
        blocks = []
        pattern = r'<div[^>]+class=["\'][^"\']*%s[^"\']*["\'][^>]*>' % re.escape(class_name)
        for m in re.finditer(pattern, html, re.I | re.S):
            end = self._find_close_div(html, m.end())
            block = html[m.start():end]
            if block:
                blocks.append(block)
        return blocks

    def _extract_div_blocks_by_class_token(self, html, class_token):
        blocks = []
        for m in re.finditer(r'<div([^>]+class=["\']([^"\']+)["\'][^>]*)>', html, re.I | re.S):
            classes = re.split(r'\s+', m.group(2).strip())
            if class_token not in classes:
                continue
            end = self._find_close_div(html, m.end())
            block = html[m.start():end]
            if block:
                blocks.append(block)
        return blocks

    def _find_close_div(self, html, start_pos):
        count = 1
        pos = start_pos
        while pos < len(html) and count > 0:
            next_open = html.find("<div", pos)
            next_close = html.find("</div>", pos)
            if next_close == -1:
                break
            if next_open == -1 or next_close < next_open:
                count -= 1
                pos = next_close + 6
            else:
                count += 1
                pos = next_open + 4
        return pos

    def _parse_list(self, html):
        items = []
        seen = set()

        blocks = self._extract_div_blocks(html, "module-item")
        if not blocks:
            blocks = []
            for m in re.finditer(r'<a[^>]+href=["\'](?:https?://[^"\']+)?/(?:detail|voddetail|video)/(\d+)\.html["\'][^>]*>', html, re.S):
                a_start = m.start()
                a_end = html.find("</a>", m.end())
                block_start = max(0, a_start - 800)
                block_end = min(len(html), (a_end if a_end != -1 else m.end()) + 1200)
                blocks.append(html[block_start:block_end])

        for block in blocks:
            m = re.search(r'href=["\'](?:https?://[^"\']+)?/(?:detail|voddetail|video)/(\d+)\.html["\']', block, re.S)
            if not m:
                continue
            vod_id = m.group(1)
            if vod_id in seen:
                continue
            seen.add(vod_id)

            names = []
            for name_raw in re.findall(r'<div[^>]+class=["\'][^"\']*v-item-title[^"\']*["\'][^>]*>(.*?)</div>', block, re.S):
                name = self._clean_text(name_raw)
                if name and "可可影视" not in name and name not in names:
                    names.append(name)
            if not names:
                for pattern in [
                    r'title=["\']([^"\']+)["\']',
                    r'<img[^>]+alt=["\']([^"\']+)["\']',
                    r'<h\d[^>]*>\s*([^<]+?)\s*</h\d>',
                    r'<[^>]+class=["\'][^"\']*(?:title|name)[^"\']*["\'][^>]*>(.*?)</[^>]+>',
                ]:
                    for name_raw in re.findall(pattern, block, re.S | re.I):
                        name = self._clean_text(name_raw)
                        if name and "可可影视" not in name and name not in names:
                            names.append(name)
            vod_name = names[0] if names else f"视频{vod_id}"

            vod_pic = self._pick_pic(block)

            remark_m = re.search(r'<div[^>]+class=["\'][^"\']*v-item-bottom[^"\']*["\'][^>]*>\s*<span>\s*([\s\S]*?)\s*</span>', block, re.S)
            if not remark_m:
                remark_m = re.search(r'(更新[^<\s]+|全\d+集|第\d+集|已完结|正片|高清版|TC[^<\s]*|HD中字\|国语|HD中字|HD国语|HD|蓝光[^<\s]*)', block)
            vod_remarks = self._clean_text(remark_m.group(1)) if remark_m else ""

            items.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks,
            })
        return items

    def _build_list_urls(self, tid, page="1"):
        tid = str(tid)
        cate_map = {
            "1": "show/1-----3",
            "2": "show/2-----3",
            "3": "show/3-----1",
            "4": "show/4-----3",
        }
        cate = cate_map.get(tid, tid)
        return [
            f"{self.host}/{cate}-{page}.html",
            f"{self.host}/{cate}-.html",
            f"{self.host}/{cate}.html",
        ]

    def homeContent(self, filter):
        result = {"class": self.cats, "filters": {}, "list": []}
        try:
            for cat in self.cats:
                tid = cat["type_id"]
                result["filters"][tid] = [
                    {"key": "class", "name": "类型", "value": self._class_opts},
                    {"key": "area", "name": "地区", "value": self._area_opts},
                    {"key": "year", "name": "年份", "value": self._year_opts},
                ]
            html = self.fetch_html(self.host + "/")
            if html:
                result["list"] = self._parse_list(html)[:30]
        except Exception as e:
            print(f"homeContent error: {e}")
        return result

    def homeVideoContent(self):
        result = {"list": []}
        try:
            html = self.fetch_html(self.host + "/")
            if html:
                result["list"] = self._parse_list(html)[:30]
        except Exception as e:
            print(f"homeVideoContent error: {e}")
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
        try:
            page = pg if int(pg) >= 1 else "1"
            for url in self._build_list_urls(tid, page):
                html = self.fetch_html(url)
                if not html:
                    continue
                result["list"] = self._parse_list(html)
                if result["list"]:
                    page_m = re.search(r'(\d+)\s*/\s*(\d+)', html)
                    if page_m:
                        result["pagecount"] = int(page_m.group(2))
                    else:
                        result["pagecount"] = int(pg) + 1 if len(result["list"]) >= 20 else int(pg)
                    break
            if not result["list"]:
                html = self.fetch_html(self.host + "/")
                if html:
                    result["list"] = self._parse_list(html)
                    result["pagecount"] = 1
        except Exception as e:
            print(f"categoryContent error: {e}")
        return result

    def _extract_info_by_label(self, html, labels):
        if isinstance(labels, str):
            labels = [labels]
        for label in labels:
            patterns = [
                r'<div[^>]+class=["\'][^"\']*detail-info-row-side[^"\']*["\'][^>]*>\s*%s[：:]?\s*</div>\s*<div[^>]+class=["\'][^"\']*detail-info-row-main[^"\']*["\'][^>]*>([\s\S]*?)</div>' % re.escape(label),
                r'%s[：:]\s*</?[^>]*>\s*([^<]+)<' % re.escape(label),
                r'<[^>]+class=["\'][^"\']*(?:title|label)[^"\']*["\'][^>]*>\s*%s[：:]?\s*</[^>]+>\s*<[^>]+class=["\'][^"\']*(?:content|value|desc)[^"\']*["\'][^>]*>(.*?)</[^>]+>' % re.escape(label),
                r'%s[：:]\s*(.*?)</(?:div|p|span|li)>' % re.escape(label),
            ]
            for p in patterns:
                m = re.search(p, html, re.S)
                if m:
                    text = self._clean_text(m.group(1))
                    text = re.sub(r'\s*/\s*', ',', text).strip(" ,/")
                    if text:
                        return text
        return ""

    def _line_speed_score(self, name, sub=""):
        text = (name + " " + sub).upper()
        if "4K" in text:
            return 999
        if "播放快" in text or "秒播" in text or "FF" in text or "SB" in text:
            return 0
        if "HN" in text or "WJ" in text or "GS" in text or "JY" in text or "IK" in text:
            return 1
        if "超清" in text:
            return 2
        if "蓝光" in text:
            return 3
        return 5

    def _parse_play_lines(self, detail_html):
        lines = []

        labels = []
        label_infos = []
        for block in re.findall(r'<a[^>]+class=["\'][^"\']*source-item[^"\']*["\'][^>]*>([\s\S]*?)</a>', detail_html, re.S):
            label_m = re.search(r'<span[^>]+class=["\'][^"\']*source-item-label[^"\']*["\'][^>]*>(.*?)</span>', block, re.S)
            sub_m = re.search(r'<span[^>]+class=["\'][^"\']*source-item-sublabel[^"\']*["\'][^>]*>(.*?)</span>', block, re.S)
            label = self._clean_text(label_m.group(1)) if label_m else ""
            sub = self._clean_text(sub_m.group(1)) if sub_m else ""
            name = label or sub
            if name and name not in labels:
                labels.append(name)
                label_infos.append((name, sub))

        ep_blocks = self._extract_div_blocks_by_class_token(detail_html, "episode-list")
        for idx, block in enumerate(ep_blocks):
            eps = []
            for ep_id, sid, nid, name_raw in re.findall(r'href=["\']/(?:play|player|vodplay)/(\d+)-(\d+)-(\d+)\.html["\'][^>]*>([\s\S]*?)</a>', block, re.S):
                ep_name = self._clean_text(name_raw)
                if not ep_name or len(ep_name) > 30:
                    ep_name = f"第{nid}集"
                item = f"{ep_name}${ep_id}-{sid}-{nid}"
                if item not in eps:
                    eps.append(item)
            if eps:
                line_name = labels[idx] if idx < len(labels) else f"线路{idx + 1}"
                line_sub = label_infos[idx][1] if idx < len(label_infos) else ""
                if "4K" in line_name.upper():
                    continue
                lines.append((line_name, eps, self._line_speed_score(line_name, line_sub)))

        if lines:
            lines.sort(key=lambda x: x[2])
            return [(name, eps) for name, eps, _ in lines]

        lines_map = {}
        for ep_id, sid, nid, name_raw in re.findall(r'href=["\']/(?:play|player|vodplay)/(\d+)-(\d+)-(\d+)\.html["\'][^>]*>([\s\S]*?)</a>', detail_html, re.S):
            ep_name = self._clean_text(name_raw)
            if not ep_name or len(ep_name) > 30:
                ep_name = f"第{nid}集"
            lines_map.setdefault(sid, [])
            item = f"{ep_name}${ep_id}-{sid}-{nid}"
            if item not in lines_map[sid]:
                lines_map[sid].append(item)
        for sid, eps in lines_map.items():
            line_name = f"线路{sid}"
            if "4K" in line_name.upper():
                continue
            lines.append((line_name, eps, self._line_speed_score(line_name)))

        lines.sort(key=lambda x: x[2])
        return [(name, eps) for name, eps, _ in lines]

    def _extract_search_tokens(self, html):
        tokens = []
        if not html:
            return tokens
        patterns = [
            r'<input[^>]+name=["\']t["\'][^>]+value=["\']([^"\']+)["\']',
            r'<input[^>]+value=["\']([^"\']+)["\'][^>]+name=["\']t["\']',
            r'[?&]t=([^"&\']+)',
        ]
        for pattern in patterns:
            for token in re.findall(pattern, html, re.S):
                token = urllib.parse.unquote(html_lib.unescape(token)).strip()
                if token and token not in tokens:
                    tokens.append(token)
        return tokens

    def _get_search_tokens(self):
        tokens = []
        if self.search_token:
            tokens.append(self.search_token)
        for url in [self.host + "/", self.host + "/show/1-----3-1.html"]:
            html = self.fetch_html(url)
            for token in self._extract_search_tokens(html):
                if token not in tokens:
                    tokens.append(token)
        if tokens:
            self.search_token = tokens[0]
        # 站点搜索参数有时短时间内仍接受页面推荐链接里的旧 token，作为动态提取失败时的兜底。
        fallback = "nksbgH9Lyh38FQ+g8DE7og=="
        if fallback not in tokens:
            tokens.append(fallback)
        return tokens

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            detail_url = f"{self.host}/detail/{vod_id}.html"
            detail_html = ""
            for _ in range(3):
                detail_html = self.fetch_html(detail_url)
                if detail_html:
                    break
                time.sleep(1)
            if not detail_html:
                return result

            detail_title = ""
            detail_title_m = re.search(r'<div[^>]+class=["\'][^"\']*detail-title[^"\']*["\'][^>]*>([\s\S]*?)</div>', detail_html, re.S)
            if detail_title_m:
                for strong_raw in re.findall(r'<strong[^>]*>(.*?)</strong>', detail_title_m.group(1), re.S):
                    name = self._clean_text(strong_raw)
                    if name and "kkys" not in name.lower() and "可可影视" not in name and "𝕜" not in name and "𝕔" not in name and "." not in name:
                        detail_title = name
                        break
            title_m = re.search(r'<h1[^>]*>(.*?)</h1>', detail_html, re.S)
            if not title_m:
                title_m = re.search(r'<title>(.*?)(?:详情介绍|在线观看| - |｜|\|)</title>', detail_html, re.S)
            vod_name = detail_title or (self._clean_text(title_m.group(1)) if title_m else f"视频{vod_id}")

            vod_pic = self._pick_pic(detail_html)

            vod_director = self._extract_info_by_label(detail_html, ["导演"])
            vod_actor = self._extract_info_by_label(detail_html, ["主演", "演员"])
            vod_year = self._extract_info_by_label(detail_html, ["年份", "年代", "首映"])
            vod_area = self._extract_info_by_label(detail_html, ["地区", "制片国家"])
            vod_class = self._extract_info_by_label(detail_html, ["类型", "类别"])

            vod_remarks = self._extract_info_by_label(detail_html, ["备注"])
            if not vod_remarks:
                remarks_m = re.search(r'(更新[^<\s]+|全\d+集|第\d+集|已完结|正片|高清版|TC[^<\s]*|HD中字\|国语|HD中字|HD国语|HD|蓝光[^<\s]*)', detail_html)
                vod_remarks = remarks_m.group(1).strip() if remarks_m else ""

            content_m = (
                re.search(r'<div[^>]+class=["\'][^"\']*detail-desc[^"\']*["\'][^>]*>([\s\S]*?)</div>', detail_html, re.S)
                or
                re.search(r'<div[^>]+class=["\'][^"\']*(?:introduction|summary|plot|desc|content)[^"\']*["\'][^>]*>(.*?)</div>', detail_html, re.S)
                or re.search(r'剧情(?:简介|介绍)[：:]?\s*</?[^>]*>\s*(.*?)</(?:div|p)>', detail_html, re.S)
                or re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', detail_html, re.S)
            )
            vod_content = self._clean_text(content_m.group(1)) if content_m else ""
            vod_content = vod_content.replace("剧情简介", "").replace("简介：", "").replace("简介:", "").strip()

            lines = self._parse_play_lines(detail_html)

            result["list"] = [{
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_director": vod_director,
                "vod_actor": vod_actor,
                "vod_year": vod_year,
                "vod_area": vod_area,
                "vod_class": vod_class,
                "vod_content": vod_content,
                "vod_remarks": vod_remarks,
                "vod_play_from": "$$$".join([x[0] for x in lines]),
                "vod_play_url": "$$$".join(["#".join(x[1]) for x in lines]),
            }]
        except Exception as e:
            print(f"detailContent error: {e}")
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            wd = urllib.parse.quote(key)
            urls = []
            for token in self._get_search_tokens():
                tv = urllib.parse.quote(token, safe="")
                urls.extend([
                    f"{self.host}/search?os=pc&k={wd}&t={tv}",
                    f"{self.host}/search?k={wd}&t={tv}",
                ])
            urls.extend([
                f"{self.host}/search?os=pc&k={wd}",
                f"{self.host}/search?k={wd}",
            ])
            for url in urls:
                html = ""
                for _ in range(2):
                    html = self.fetch_html(url)
                    if html:
                        break
                    time.sleep(1)
                if html:
                    result["list"] = self._parse_list(html)
                    if result["list"]:
                        break
        except Exception as e:
            print(f"searchContent error: {e}")
        return result

    def playerContent(self, flag, pid, vipFlags):
        result = {}
        try:
            if pid in self.play_url_cache:
                return {
                    "parse": 0,
                    "url": self.play_url_cache[pid],
                    "header": {"User-Agent": self.ua}
                }

            parts = pid.split("-")
            if len(parts) == 3:
                vid, sid, nid = parts
                play_url = f"{self.host}/play/{vid}-{sid}-{nid}.html"
                referer = f"{self.host}/detail/{vid}.html"
            else:
                play_url = f"{self.host}/play/{pid}.html"
                referer = self.host + "/"

            html = ""
            for _ in range(3):
                html = self.fetch_html(play_url)
                if html:
                    break
                time.sleep(1)
            if html:
                play_url_m = (
                    re.search(r'playSource\s*=\s*\{[\s\S]*?src\s*:\s*["\']([^"\']+)["\']', html, re.I)
                    or re.search(r'url\s*:\s*playSource\.src[\s\S]*?src\s*:\s*["\']([^"\']+)["\']', html, re.I)
                    or re.search(r'src\s*:\s*["\']([^"\']+\.(?:m3u8|mp4)(?:\?[^"\']*)?)["\']', html, re.I)
                    or re.search(r'["\'](https?://[^"\']+\.(?:m3u8|mp4)(?:\?[^"\']*)?)["\']', html, re.I)
                )
                if play_url_m:
                    url = self._clean_url(play_url_m.group(1))
                    url = urllib.parse.unquote(url)
                    if url:
                        result["parse"] = 0
                        result["url"] = self._abs_url(url)
                        self.play_url_cache[pid] = result["url"]
                        result["header"] = {"User-Agent": self.ua}
                        return result

                m = re.search(r'var\s+(?:player_aaaa|player_info|player_data)\s*=\s*(\{[\s\S]*?\})\s*</script>', html, re.I)
                if not m:
                    m = re.search(r'(?:player_aaaa|player_info|player_data)\s*=\s*(\{[\s\S]*?\})\s*;', html, re.I)
                if m:
                    try:
                        data = json.loads(m.group(1))
                        url = self._clean_url(data.get("url", ""))
                        url = urllib.parse.unquote(url)
                        if url and self.isVideoFormat(url):
                            result["parse"] = 0
                            result["url"] = self._abs_url(url)
                            self.play_url_cache[pid] = result["url"]
                            result["header"] = {"User-Agent": self.ua}
                            return result
                    except Exception as e:
                        print(f"player parse error: {e}")

            result["parse"] = 1
            result["url"] = play_url
            result["header"] = {"User-Agent": self.ua, "Referer": referer}
        except Exception as e:
            print(f"playerContent error: {e}")
            result["parse"] = 1
            result["url"] = f"{self.host}/play/{pid}.html"
            result["header"] = {"User-Agent": self.ua, "Referer": self.host + "/"}
        return result

    def localProxy(self, params):
        return [404, "text/plain", b"Not supported"]
