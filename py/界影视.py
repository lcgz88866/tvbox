# -*- coding: utf-8 -*-
# 界影视 - m.hkybqufgh.com
# by TRAE
import hashlib
import re
import sys
import time
import json
from urllib.parse import quote

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "界影视"

    def init(self, extend=""):
        self.host = "https://www.hkybqufgh.com"
        self.signKey = "cb808529bae6b6be45ecfab29a4889bc"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
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
                {"type_name": "电影", "type_id": "1"},
                {"type_name": "电视剧", "type_id": "2"},
                {"type_name": "综艺", "type_id": "3"},
                {"type_name": "动漫", "type_id": "4"},
            ]
            # 首页推荐（从移动端HTML解析RSC数据）
            html = self.fetch_html(self.host)
            if html:
                result["list"] = self.parse_rsc_list(html)
        except Exception as e:
            print(f'homeContent error: {e}')
        return result

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": pg, "pagecount": 999, "limit": 90, "total": 999999}
        try:
            data = self.api_list(tid, pg)
            if data:
                result["list"] = data
        except Exception as e:
            print(f'categoryContent error: {e}')
        return result

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            data = self.api_detail(vod_id)
            if data:
                result["list"] = [data]
        except Exception as e:
            print(f'detailContent error: {e}')
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            # 搜索（PC端HTML解析RSC数据）
            url = f"{self.host}/vod/search/{quote(key)}"
            html = self.fetch_html(url)
            if html:
                result["list"] = self.parse_rsc_list(html)
        except Exception as e:
            print(f'searchContent error: {e}')
        return result

    def playerContent(self, flag, pid, vipFlags):
        result = {}
        try:
            url = self.api_play(pid)
            result["parse"] = 0
            result["url"] = url
            result["header"] = {"User-Agent": self.ua}
        except Exception as e:
            print(f'playerContent error: {e}')
            result["parse"] = 0
            result["url"] = ""
        return result

    def localProxy(self, params):
        return self.Mlocal(params)

    # ==================== API方法 ====================

    def api_list(self, tid, page):
        """通过API获取分类列表"""
        t = str(int(time.time() * 1000))
        sign_str = f'page={page}&size=48&type1={tid}&key={self.signKey}&t={t}'
        sign = hashlib.sha1(hashlib.md5(sign_str.encode()).hexdigest().encode()).hexdigest()
        api_headers = {
            "User-Agent": self.ua,
            "Accept": "application/json, text/plain, */*",
            "sign": sign,
            "t": t,
            "referer": self.host + "/",
        }
        url = f"{self.host}/api/mw-movie/anonymous/video/list?type1={tid}&page={page}&size=48"
        res = self.fetch(url, headers=api_headers, timeout=15)
        if not res:
            return []
        try:
            data = res.json()
            if data.get("code") == 200 and data.get("data"):
                vod_list = data["data"].get("list", [])
                items = []
                for v in vod_list:
                    items.append({
                        "vod_id": str(v.get("vodId", "")),
                        "vod_name": v.get("vodName", ""),
                        "vod_pic": v.get("vodPic", ""),
                        "vod_remarks": v.get("vodRemarks", ""),
                    })
                return items
        except Exception as e:
            print(f'api_list json error: {e}')
        return []

    def api_detail(self, vod_id):
        """通过API获取详情"""
        t = str(int(time.time() * 1000))
        sign_str = f'id={vod_id}&key={self.signKey}&t={t}'
        sign = hashlib.sha1(hashlib.md5(sign_str.encode()).hexdigest().encode()).hexdigest()
        api_headers = {
            "User-Agent": self.ua,
            "Accept": "application/json, text/plain, */*",
            "sign": sign,
            "t": t,
            "referer": self.host + "/",
        }
        url = f"{self.host}/api/mw-movie/anonymous/video/detail?id={vod_id}"
        res = self.fetch(url, headers=api_headers, timeout=15)
        if not res:
            return None
        try:
            data = res.json()
            if data.get("code") == 200 and data.get("data"):
                v = data["data"]
                urls = []
                for ep in v.get("episodeList", []):
                    name = ep.get("name", "")
                    nid = ep.get("nid", "")
                    urls.append(f"{name}${vod_id}-{nid}")
                return {
                    "vod_id": str(v.get("vodId", "")),
                    "vod_name": v.get("vodName", ""),
                    "vod_pic": v.get("vodPic", ""),
                    "vod_actor": v.get("vodActor", ""),
                    "vod_director": v.get("vodDirector", ""),
                    "vod_year": str(v.get("vodYear", "")),
                    "vod_area": v.get("vodArea", ""),
                    "vod_remarks": v.get("vodRemarks", ""),
                    "vod_content": v.get("vodContent", ""),
                    "vod_play_from": "默认",
                    "vod_play_url": "#".join(urls),
                }
        except Exception as e:
            print(f'api_detail json error: {e}')
        return None

    def api_play(self, pid):
        """通过API获取播放地址"""
        info = pid.split("-")
        if len(info) < 2:
            return ""
        vod_id = info[0]
        nid = info[1]
        t = str(int(time.time() * 1000))
        sign_str = f'id={vod_id}&nid={nid}&key={self.signKey}&t={t}'
        sign = hashlib.sha1(hashlib.md5(sign_str.encode()).hexdigest().encode()).hexdigest()
        api_headers = {
            "User-Agent": self.ua,
            "Accept": "application/json, text/plain, */*",
            "sign": sign,
            "t": t,
            "referer": self.host + "/",
        }
        url = f"{self.host}/api/mw-movie/anonymous/v2/video/episode/url?id={vod_id}&nid={nid}"
        res = self.fetch(url, headers=api_headers, timeout=15)
        if not res:
            return ""
        try:
            data = res.json()
            if data.get("code") == 200 and data.get("data"):
                play_list = data["data"].get("list", [])
                if play_list:
                    return play_list[0].get("url", "")
        except Exception as e:
            print(f'api_play json error: {e}')
        return ""

    # ==================== HTML解析方法 ====================

    def fetch_html(self, url):
        """获取页面HTML"""
        try:
            res = self.fetch(url, headers=self.headers, timeout=15)
            if res:
                return res.text
        except Exception as e:
            print(f'fetch_html error: {e}')
        return ""

    def parse_rsc_list(self, html):
        """解析Next.js RSC HTML中的视频列表数据"""
        items = []
        try:
            vod_ids = re.findall(r'\\"vodId\\":(.*?),', html)
            vod_names = re.findall(r'\\"vodName\\":\\"(.*?)\\"', html)
            vod_pics = re.findall(r'\\"vodPic\\":\\"(.*?)\\"', html)
            vod_remarks = re.findall(r'\\"vodRemarks\\":\\"(.*?)\\"', html)

            for i in range(len(vod_ids)):
                items.append({
                    "vod_id": str(vod_ids[i]).strip(),
                    "vod_name": vod_names[i] if i < len(vod_names) else "",
                    "vod_pic": vod_pics[i] if i < len(vod_pics) else "",
                    "vod_remarks": vod_remarks[i] if i < len(vod_remarks) else "",
                })
        except Exception as e:
            print(f'parse_rsc_list error: {e}')
        return items
