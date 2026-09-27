# -*- coding: utf-8 -*-
"""
==========================================================
  牛马剧场 (gohh4md.niuama.top) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎)
  框架: 前后端分离 REST API (非maccms)
  更新: 2026-08-12

  API接口 (window.API_BASE='/api/v1', API_DIRECT=0):
    列表: /api/v1/vods?page={page}&pageSize=42&sort=time_desc&localType={type}&area={area}&year={year}
    搜索: /api/v1/vods?page={page}&pageSize=40&sort=time_desc&q={keyword}
    详情: /api/v1/vods/{id}
    播放: /api/v1/vods/{id}/plays?parse=1

  分类 (localType, 站点分类页使用localType而非typeId):
    电影=movie  电视剧=tv  综艺=variety  动漫=anime

  筛选:
    地区: 中国大陆/香港/台湾/美国/日本/韩国/英国/法国/德国/泰国/印度/
          意大利/西班牙/加拿大
    年份: 2016-2026

  列表API返回:
    { items: [{vod_id, vod_name, type_id, type_name, local_type,
               vod_pic, vod_area, vod_year, vod_time, vod_remarks}],
      pagination: {page, pageSize, total} }

  详情API返回:
    { vod_id, vod_name, type_id, type_name, vod_pic, vod_content,
      vod_area, vod_lang, vod_year, vod_time, vod_remarks }

  播放API返回:
    { vod_id, plays: [{vod_play_from, vod_state, vod_play_url,
        episodes: [{name, url}]}] }

  播放源 (均为直链m3u8, parse=0直接播放):
    mtm3u8 / xlm3u8 / dyttm3u8 / dbm3u8 / dzm3u8 / lzm3u8

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
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import quote, unquote
from html import unescape as html_unescape


class Spider(Spider):

    HOST = "https://gohh4md.niuama.top"
    API_BASE = "/api/v1"
    UA = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # 主分类 (站点分类页使用localType参数, 非typeId)
    CATEGORIES = [
        {"type_name": "电影", "type_id": "movie"},
        {"type_name": "电视剧", "type_id": "tv"},
        {"type_name": "综艺", "type_id": "variety"},
        {"type_name": "动漫", "type_id": "anime"},
    ]

    # 地区选项 (所有分类通用)
    AREA_VALUES = [
        {"n": "全部", "v": ""},
        {"n": "中国大陆", "v": "中国大陆"},
        {"n": "香港", "v": "香港"},
        {"n": "台湾", "v": "台湾"},
        {"n": "美国", "v": "美国"},
        {"n": "日本", "v": "日本"},
        {"n": "韩国", "v": "韩国"},
        {"n": "英国", "v": "英国"},
        {"n": "法国", "v": "法国"},
        {"n": "德国", "v": "德国"},
        {"n": "泰国", "v": "泰国"},
        {"n": "印度", "v": "印度"},
        {"n": "意大利", "v": "意大利"},
        {"n": "西班牙", "v": "西班牙"},
        {"n": "加拿大", "v": "加拿大"},
    ]

    def getName(self):
        return "牛马剧场"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": self.UA,
            "Accept": "application/json, text/plain, */*",
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
        for y in range(2026, 2015, -1):
            year_values.append({"n": str(y), "v": str(y)})

        for cat in self.CATEGORIES:
            cat_id = cat["type_id"]
            filters[cat_id] = [
                {"key": "area", "name": "地区", "value": self.AREA_VALUES},
                {"key": "year", "name": "年份", "value": year_values},
            ]
        return filters

    # ==================== HTTP ====================
    def _fetch(self, url, headers=None, timeout=15):
        """GET请求, 返回文本 (优先TVBox基类, 回退urllib)"""
        hdr = headers or self.headers
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

    def _fetch_json(self, url):
        """GET请求, 返回JSON对象"""
        text = self._fetch(url)
        if not text:
            return None
        try:
            return json.loads(text)
        except:
            return None

    def _api_url(self, path, params=None):
        """构建API完整URL"""
        url = self.HOST + self.API_BASE + path
        if params:
            qs = urllib.parse.urlencode(params)
            url = url + "?" + qs
        return url

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

    # ==================== 首页 ====================
    def homeContent(self, filter):
        result = {}
        classes = []
        for c in self.CATEGORIES:
            classes.append({"type_name": c["type_name"], "type_id": c["type_id"]})
        result["class"] = classes
        if filter:
            result["filters"] = self._build_filters()
        return result

    def homeVideoContent(self):
        """首页最新视频"""
        result = {}
        try:
            url = self._api_url("/vods", {
                "page": "1",
                "pageSize": "20",
                "sort": "time_desc",
            })
            data = self._fetch_json(url)
            if data and isinstance(data, dict):
                items = data.get("items", [])
                videos = []
                for item in items:
                    videos.append({
                        "vod_id": str(item.get("vod_id", "")),
                        "vod_name": item.get("vod_name", ""),
                        "vod_pic": self._fix_pic(item.get("vod_pic", "")),
                        "vod_remarks": item.get("vod_remarks", ""),
                    })
                result["list"] = videos
        except Exception as e:
            print("homeVideoContent error: {0}".format(e))
        return result

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, nc, extend):
        """分类列表
        API: /vods?localType={tid}&page={pg}&pageSize=42&sort=time_desc&area={area}&year={year}
        站点分类页使用 localType (movie/tv/variety/anime) 而非 typeId
        """
        result = {}
        page = int(pg) if pg else 1
        if page < 1:
            page = 1

        area = ""
        year = ""
        if extend:
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except:
                    extend = {}
            area = extend.get("area", "") or ""
            year = extend.get("year", "") or ""

        params = {
            "page": str(page),
            "pageSize": "42",
            "sort": "time_desc",
            "localType": str(tid),
        }
        if area:
            params["area"] = area
        if year:
            params["year"] = year

        url = self._api_url("/vods", params)
        data = self._fetch_json(url)

        videos = []
        pagecount = 1
        total = 0
        if data and isinstance(data, dict):
            items = data.get("items", [])
            for item in items:
                videos.append({
                    "vod_id": str(item.get("vod_id", "")),
                    "vod_name": item.get("vod_name", ""),
                    "vod_pic": self._fix_pic(item.get("vod_pic", "")),
                    "vod_remarks": item.get("vod_remarks", ""),
                })
            pagination = data.get("pagination", {})
            total = int(pagination.get("total", 0))
            page_size = int(pagination.get("pageSize", 42))
            if total and page_size:
                pagecount = (total + page_size - 1) // page_size
            elif total:
                pagecount = (total + 41) // 42

        result["list"] = videos
        result["page"] = page
        result["pagecount"] = max(pagecount, 1)
        result["limit"] = 42
        result["total"] = total
        return result

    # ==================== 搜索 ====================
    def searchContent(self, key, quick):
        """搜索
        API: /vods?page=1&pageSize=40&sort=time_desc&q={keyword}
        """
        result = {}
        try:
            params = {
                "page": "1",
                "pageSize": "40",
                "sort": "time_desc",
                "q": key,
            }
            url = self._api_url("/vods", params)
            data = self._fetch_json(url)
            if data and isinstance(data, dict):
                items = data.get("items", [])
                videos = []
                for item in items:
                    videos.append({
                        "vod_id": str(item.get("vod_id", "")),
                        "vod_name": item.get("vod_name", ""),
                        "vod_pic": self._fix_pic(item.get("vod_pic", "")),
                        "vod_remarks": item.get("vod_remarks", ""),
                    })
                result["list"] = videos
        except Exception as e:
            print("searchContent error: {0}".format(e))
        return result

    # ==================== 详情 ====================
    def detailContent(self, ids):
        """详情页
        API: /vods/{id} + /vods/{id}/plays?parse=1
        """
        try:
            vod_id = ids[0] if isinstance(ids, list) else str(ids)

            # 获取详情
            detail_url = self._api_url("/vods/{0}".format(vod_id))
            detail = self._fetch_json(detail_url)
            if not detail:
                return {}

            # 获取播放源
            plays_url = self._api_url("/vods/{0}/plays".format(vod_id), {"parse": "1"})
            plays_data = self._fetch_json(plays_url)

            # 构建播放源
            vod_play_from = ""
            vod_play_url = ""
            if plays_data and isinstance(plays_data, dict):
                plays = plays_data.get("plays", [])
                from_list = []
                url_groups = []
                for p in plays:
                    play_from = p.get("vod_play_from", "")
                    if not play_from:
                        continue
                    episodes = p.get("episodes", [])
                    if not episodes:
                        # 从 vod_play_url 解析 (格式: title$url#title$url)
                        raw = p.get("vod_play_url", "")
                        if raw:
                            ep_list = []
                            for seg in raw.split("#"):
                                if not seg:
                                    continue
                                idx = seg.find("$")
                                if idx > -1:
                                    ep_title = seg[:idx]
                                    ep_url = seg[idx + 1:]
                                    if ep_url:
                                        ep_list.append((ep_title, ep_url))
                            episodes = [{"name": t, "url": u} for t, u in ep_list]

                    if not episodes:
                        continue

                    ep_parts = []
                    for ep in episodes:
                        ep_name = ep.get("name", "") or ep.get("title", "")
                        ep_url = ep.get("url", "")
                        if ep_url:
                            ep_parts.append("{0}${1}".format(ep_name, ep_url))
                    if ep_parts:
                        from_list.append(play_from)
                        url_groups.append("#".join(ep_parts))

                vod_play_from = "$$$".join(from_list)
                vod_play_url = "$$$".join(url_groups)

            # 构建vod信息
            vod = {
                "vod_id": vod_id,
                "vod_name": detail.get("vod_name", ""),
                "vod_pic": self._fix_pic(detail.get("vod_pic", "")),
                "type_name": detail.get("type_name", ""),
                "vod_year": detail.get("vod_year", ""),
                "vod_area": detail.get("vod_area", ""),
                "vod_lang": detail.get("vod_lang", ""),
                "vod_remarks": detail.get("vod_remarks", ""),
                "vod_content": detail.get("vod_content", ""),
                "vod_play_from": vod_play_from,
                "vod_play_url": vod_play_url,
            }

            return {"list": [vod]}
        except Exception as e:
            print("detailContent error: {0}".format(e))
            return {}

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        """播放: 所有源均为直链m3u8, 直接播放
        id 即为 m3u8 URL (从 detailContent 的 vod_play_url 传入)
        """
        result = {"parse": 0, "playUrl": "", "url": "", "header": "", "jx": 0}
        try:
            play_url = id.strip()

            # 如果id包含$, 取后半部分
            if "$" in play_url:
                play_url = play_url.split("$")[-1].strip()

            # HTML实体解码
            try:
                play_url = html_unescape(play_url)
            except:
                pass

            # 构建header
            play_header = json.dumps({
                "User-Agent": self.UA,
                "Referer": self.HOST + "/",
            })

            result["parse"] = 0
            result["jx"] = 0
            result["url"] = play_url
            result["header"] = play_header

        except Exception as e:
            print("playerContent error: {0}".format(e))
            result["parse"] = 1
            result["url"] = id

        return result