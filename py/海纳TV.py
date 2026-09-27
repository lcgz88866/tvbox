# -*- coding: utf-8 -*-
# 海纳TV - www.hainatv.net
# by TRAE
# 苹果CMS + conch模板 + rym3u8播放器(iframe解析)
import re
import sys
import json
import base64
import urllib.parse

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def getName(self):
        return "海纳TV"

    def init(self, extend=""):
        self.host = "https://www.hainatv.net"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.headers = {"User-Agent": self.ua}

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

    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        try:
            result["class"] = [
                {"type_name": "视剧", "type_id": "2"},
                {"type_name": "综艺", "type_id": "3"},
                {"type_name": "短剧", "type_id": "5"},
                {"type_name": "纪录片", "type_id": "52"},
            ]
            html = self.fetch_html(self.host + "/")
            if html:
                result["list"] = self.parse_list(html)
        except Exception as e:
            print(f'homeContent error: {e}')
        return result

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": pg, "pagecount": 999, "limit": 90, "total": 999999}
        try:
            url = f"{self.host}/index.php/vod/type/id/{tid}/page/{pg}.html"
            html = self.fetch_html(url)
            if html:
                result["list"] = self.parse_list(html)
        except Exception as e:
            print(f'categoryContent error: {e}')
        return result

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            data = self.parse_detail(vod_id)
            if data:
                result["list"] = [data]
        except Exception as e:
            print(f'detailContent error: {e}')
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            wd = urllib.parse.quote(key)
            url = f"{self.host}/index.php/vod/search/wd/{wd}/page/{pg}.html"
            html = self.fetch_html(url)
            if html:
                result["list"] = self.parse_list(html)
        except Exception as e:
            print(f'searchContent error: {e}')
        return result

    def playerContent(self, flag, pid, vipFlags):
        result = {}
        try:
            # pid格式: /index.php/vod/play/id/{id}/sid/{sid}/nid/{nid}.html
            play_url = self.host + pid
            # rym3u8播放器通过iframe加载解析页，必须用WebView
            result["parse"] = 1
            result["url"] = play_url
            result["header"] = {"User-Agent": self.ua, "Referer": self.host}
        except Exception as e:
            print(f'playerContent error: {e}')
            result["parse"] = 0
            result["url"] = ""
        return result

    def localProxy(self, params):
        return self.Mlocal(params)

    # ==================== 工具方法 ====================

    def fetch_html(self, url):
        try:
            res = self.fetch(url, headers=self.headers, timeout=15)
            if res:
                if isinstance(res, str):
                    return res
                return res.text
        except Exception as e:
            print(f'fetch_html error: {e}')
        return ""

    def parse_list(self, html):
        """解析视频列表"""
        items = []
        try:
            blocks = re.findall(
                r'<a\s+class="hl-item-thumb[^"]*"\s+href="(/index\.php/vod/detail/id/(\d+)\.html)"\s+title="([^"]+)"\s+data-original="([^"]+)"',
                html, re.S
            )
            seen = set()
            for link, vod_id, vod_name, vod_pic in blocks:
                if vod_id in seen:
                    continue
                seen.add(vod_id)
                items.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic if vod_pic.startswith("http") else (self.host + vod_pic if vod_pic else ""),
                    "vod_remarks": "",
                })
        except Exception as e:
            print(f'parse_list error: {e}')
        return items

    def parse_detail(self, vod_id):
        """解析详情页"""
        try:
            detail_html = self.fetch_html(f"{self.host}/index.php/vod/detail/id/{vod_id}.html")
            if not detail_html:
                return None

            # 标题 - 从 ld+json 的 TVSeries 提取
            vod_name = ""
            ld_name = re.search(r'"@type":"TVSeries","name":"([^"]+)"', detail_html)
            if ld_name:
                vod_name = ld_name.group(1)
            if not vod_name:
                crumb = re.search(r'<span class="hl-crumb-item">([^<]+)</span>', detail_html)
                if crumb:
                    vod_name = crumb.group(1).strip()

            # 封面 - ld+json image
            vod_pic = ""
            pic = re.search(r'"image":"([^"]+)"', detail_html)
            if pic:
                vod_pic = pic.group(1)
            if not vod_pic:
                pic2 = re.search(r'data-original="([^"]+)"', detail_html)
                if pic2:
                    vod_pic = pic2.group(1)
            if vod_pic and not vod_pic.startswith("http"):
                vod_pic = self.host + vod_pic

            # 简介
            vod_content = ""
            content = re.search(r'<span class="hl-content-text"[^>]*>(.*?)</span>', detail_html, re.S)
            if content:
                vod_content = re.sub(r'<[^>]+>', '', content.group(1)).strip()
                vod_content = re.sub(r'&nbsp;', '', vod_content).strip()
                vod_content = re.sub(r'\s+', ' ', vod_content).strip()
            if not vod_content:
                meta = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]+)"', detail_html)
                if meta:
                    vod_content = meta.group(1).strip()

            # 演员/导演 - 从 ld+json 正则提取
            vod_actor = ""
            vod_director = ""
            am = re.search(r'"actor":\s*\{[^}]*"name":\s*"([^"]+)"', detail_html)
            if am:
                vod_actor = am.group(1)
            dm = re.search(r'"director":\s*\{[^}]*"name":\s*"([^"]+)"', detail_html)
            if dm:
                vod_director = dm.group(1)

            # 年份/地区 - 从 hl-data-xs 提取
            vod_year = ""
            vod_area = ""
            data_xs = re.search(r'class="hl-data-xs[^"]*">(.*?)</div>', detail_html, re.S)
            if data_xs:
                text = re.sub(r'<[^>]+>', '', data_xs.group(1)).strip()
                parts = re.split(r'[/\s]+', text)
                for p in parts:
                    p = p.strip()
                    if re.match(r'\d{4}$', p):
                        vod_year = p
                    elif not vod_area and len(p) >= 2 and p not in ['国产', '汉语普通话']:
                        vod_area = p

            # 备注
            vod_remarks = ""
            # 从首页列表项的 remarks 或详情页提取
            remarks = re.search(r'<span class="hl-lc-1 remarks">([^<]*)</span>', detail_html)
            if remarks:
                vod_remarks = remarks.group(1).strip()

            # 播放列表
            play_from = []
            play_url = []

            # 线路名称
            line_names = re.findall(r'class="hl-tabs-btn[^"]*"[^>]*alt="([^"]+)"', detail_html)

            # 选集链接 - 按sid分组
            all_eps = re.findall(
                r'<a href="(/index\.php/vod/play/id/\d+/sid/(\d+)/nid/\d+\.html)">([^<]+)</a>',
                detail_html
            )
            sid_eps = {}
            for ep_url, sid, ep_name in all_eps:
                sid_eps.setdefault(sid, []).append((ep_url, ep_name))

            for sid, eps in sid_eps.items():
                idx = int(sid) - 1
                line_name = line_names[idx].strip() if idx < len(line_names) else f"线路{sid}"
                urls = [f"{n}${u}" for u, n in eps]
                if urls:
                    play_from.append(line_name)
                    play_url.append("#".join(urls))

            return {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_director": vod_director,
                "vod_actor": vod_actor,
                "vod_year": vod_year,
                "vod_area": vod_area,
                "vod_content": vod_content,
                "vod_remarks": vod_remarks,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }
        except Exception as e:
            print(f'parse_detail error: {e}')
        return None