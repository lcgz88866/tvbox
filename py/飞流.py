# -*- coding: utf-8 -*-
"""
==========================================================
  FlixFlop (www.flixflop.com) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎)
  框架: Next.js (pages router) + React Query (SSR)
  更新: 2026-09-20  (修复全站无数据: 原 /api/v1/* 端点已下线返回502)

  ★ 站点改动说明 (2026-09 实测):
    旧的 /api/v1/* REST 端点 (categories/explore/videos/search)
    已全部 502 下线; 站点改为 Next.js SSR + React Query,
    页面数据通过 Next.js 数据端点下发, 数据结构与旧 API 兼容:

    数据端点: GET /_next/data/{buildId}/{页面路由}.json?参数
      分类列表: /_next/data/{buildId}/explore/{categoryId}.json
                ?page={N}&area={id}&genre={id}&year={Y}&language={id}
                (每页固定48条, meta.count 为总条数)
      详情/播放源: /_next/data/{buildId}/streams/{videoId}/detail.json
                (一次返回 metadata + sources 两个 query)
      搜索:     /_next/data/{buildId}/results.json?q={keyword}  (参数名是 q !)
      首页推荐: 首页 HTML 内嵌 <script id="__NEXT_DATA__"> 中的
                dehydratedState.queries (daily/weekly recommendations)

    buildId 会随站点部署变化, 本文件自动从首页提取并缓存,
    失效时自动刷新重试; 另有抓取 HTML 页面解析 __NEXT_DATA__ 的兜底路径。

  queryKey 布局 (React Query dehydratedState.queries):
    ["categories"]
    ["explore", categoryId, "filters"]                          -> 筛选器
    ["explore", categoryId, {area,genre,year,language,sort,
                              startPage}]                       -> 列表 {pages:[{meta:{count,page}, data:[...]}]}
    ["videos", videoId, "metadata"]                             -> 详情元数据
    ["videos", videoId, "sources"]                              -> 播放源 [{name, url:"第01集$http...#第02集$..."}]
    ["explore", "search", {q: keyword}]                         -> 搜索结果 {pages:[{data:[...]}]}
    ["landing", "recommendations", "daily"]                     -> 每日推荐

  条目字段: video_id / cover_image / title / published_year /
            remarks / actors[] / directors[] / description / area / genre
  播放: m3u8直链, parse=0, 无需解密
==========================================================
"""

import sys
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

import re
import json
import ssl
import time
import threading
import urllib.request
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urlencode
from html import unescape as html_unescape


class Spider(Spider):

    HOST = "https://www.flixflop.com"
    UA = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # 主分类 (2026-09 实测与站点 ["categories"] 数据一致)
    CATEGORIES = [
        {"type_name": "电影", "type_id": "151438147786375168"},
        {"type_name": "电视剧", "type_id": "151438147794763777"},
        {"type_name": "动漫", "type_id": "151438147807346690"},
        {"type_name": "综艺", "type_id": "151438147807346691"},
        {"type_name": "体育", "type_id": "151438147807346693"},
        {"type_name": "电影解说", "type_id": "204814944317734918"},
        {"type_name": "短剧", "type_id": "331153971999670710"},
    ]

    # 站点 SSR 每页固定条数
    PER_PAGE = 48

    def init(self, extend=""):
        self.ua = self.UA
        self.host = self.HOST
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
            "x-nextjs-data": "1",
        }
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

        self._play_header = json.dumps({
            "User-Agent": self.ua,
            "Referer": self.host + "/",
        })

        # 筛选器缓存 / buildId 缓存
        self._filters_cache = None
        self._build_id = ""
        self._build_id_time = 0
        self._build_lock = threading.Lock()

    def getName(self):
        return "FlixFlop"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|ts)(\?|#|$)', url, re.I))

    def manualVideoCheck(self):
        return False

    def getDependence(self):
        return []

    def action(self, action):
        pass

    def destroy(self):
        pass

    # ===== HTTP 辅助 =====

    def _http_get(self, url, timeout=10, retries=2):
        """GET 请求, 返回文本; 网络抖动自动重试"""
        last = ""
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx) as resp:
                    return resp.read().decode('utf-8', errors='replace')
            except urllib.error.HTTPError as e:
                try:
                    last = e.read().decode('utf-8', errors='replace')
                except:
                    last = ""
                if e.code < 500:
                    # 4xx 不重试
                    return last
            except Exception:
                last = ""
            if attempt < retries:
                time.sleep(0.5 + attempt)
        return last

    def _get_build_id(self, force=False):
        """获取 Next.js buildId (从首页 __NEXT_DATA__ 提取, 缓存1小时)"""
        with self._build_lock:
            if not force and self._build_id and time.time() - self._build_id_time < 3600:
                return self._build_id
            html = self._http_get(self.host + "/", timeout=12)
            m = re.search(r'"buildId"\s*:\s*"([^"]+)"', html)
            if m:
                self._build_id = m.group(1)
                self._build_id_time = time.time()
            return self._build_id

    def _queries_from_payload(self, payload):
        """从 Next.js 数据(JSON dict)或 HTML 中的 __NEXT_DATA__ 提取 queries 列表"""
        pp = None
        if isinstance(payload, dict):
            pp = payload.get('pageProps') or (payload.get('props') or {}).get('pageProps')
        elif isinstance(payload, str) and payload:
            m = re.search(
                r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>',
                payload, re.S)
            if m:
                try:
                    d = json.loads(m.group(1))
                    pp = d.get('props', {}).get('pageProps') or d.get('pageProps')
                except Exception:
                    pp = None
        if pp and isinstance(pp, dict) and 'dehydratedState' in pp:
            return pp['dehydratedState'].get('queries', []) or []
        return []

    def _fetch_nextdata(self, page_path, params=None):
        """请求 /_next/data/{buildId}/{page_path}.json
        返回 dehydratedState.queries 列表; buildId 失效自动刷新重试。
        """
        qs = ""
        if params:
            qs = "?" + urlencode(params)

        def _url(bid):
            return "{0}/_next/data/{1}{2}.json{3}".format(self.host, bid, page_path, qs)

        bid = self._get_build_id()
        if not bid:
            return []

        body = self._http_get(_url(bid))
        if body:
            queries = self._queries_from_payload(body)
            if queries:
                return queries
            # 请求成功但结构异常: buildId 可能已随部署过期 -> 强刷重试
            bid2 = self._get_build_id(force=True)
            if bid2 and bid2 != bid:
                queries = self._queries_from_payload(self._http_get(_url(bid2)))
                if queries:
                    return queries
        else:
            # 网络失败: 原地重试一次
            queries = self._queries_from_payload(self._http_get(_url(bid)))
            if queries:
                return queries

        # 终极兜底: 直接抓对应 HTML 页面解析 __NEXT_DATA__ (数据同构)
        html = self._http_get("{0}{1}{2}".format(self.host, page_path, qs))
        return self._queries_from_payload(html)

    def _find_query_data(self, queries, match):
        """按条件从 queries 中取 state.data
        match: callable(queryKey) -> bool
        """
        for q in queries:
            try:
                key = q.get('queryKey') or []
                if match(key):
                    st = q.get('state') or {}
                    if st.get('error'):
                        continue
                    return st.get('data')
            except Exception:
                continue
        return None

    @staticmethod
    def _is_list_query(key):
        """列表类 query: key 长度>=3 且第3项为 dict (explore/搜索结果)"""
        return len(key) >= 3 and isinstance(key[2], dict)

    def _pages_items(self, data):
        """从 {pages:[{meta,data}]} 提取条目与总数"""
        items = []
        total = 0
        if isinstance(data, dict):
            pages = data.get('pages') or []
            for pg in pages:
                items.extend(pg.get('data') or [])
                meta = pg.get('meta') or {}
                try:
                    total = max(total, int(meta.get('count') or 0))
                except:
                    pass
        return items, total

    def _to_videos(self, items):
        videos = []
        for item in items or []:
            vid = str(item.get('video_id', '') or '')
            if not vid:
                continue
            videos.append({
                "vod_id": vid,
                "vod_name": item.get('title', '') or '',
                "vod_pic": item.get('cover_image', '') or '',
                "vod_remarks": item.get('remarks', '') or '',
            })
        return videos

    # ===== 首页 =====

    def homeContent(self, filter):
        result = {
            "class": [{"type_name": c["type_name"], "type_id": c["type_id"]}
                      for c in self.CATEGORIES],
        }
        if filter:
            result["filters"] = self._get_filters()
        return result

    def homeVideoContent(self):
        """首页推荐 - 抓首页 HTML, 从内嵌 __NEXT_DATA__ 取每日推荐"""
        videos = []
        try:
            html = self._http_get(self.host + "/", timeout=12)
            queries = self._queries_from_payload(html)
            data = self._find_query_data(
                queries, lambda k: len(k) >= 3 and k[:3] == ["landing", "recommendations", "daily"])
            if not data:
                # 兜底: 取任一 landing 推荐
                data = self._find_query_data(
                    queries, lambda k: len(k) >= 2 and k[0] == "landing")
            items = []
            if isinstance(data, dict):
                items = data.get('data') or []
                if not items:
                    # weekly 结构: {latest: [...]}
                    items = data.get('latest') or []
            elif isinstance(data, list):
                items = data
            videos = self._to_videos(items)
        except Exception as e:
            print('homeVideoContent error: {0}'.format(e))
        return {"list": videos[:30]}

    def _fetch_category_filters(self, tid):
        """拉取单个分类的筛选器 (来自 explore SSR 数据中的 filters query)"""
        filter_list = []
        try:
            queries = self._fetch_nextdata("/explore/" + tid, {"page": "1"})
            fdata = self._find_query_data(
                queries, lambda k: len(k) >= 3 and k[0] == "explore" and k[2] == "filters")
            f = {}
            if isinstance(fdata, dict):
                f = fdata.get('data') or {}
        except Exception as e:
            print('get_filters({0}) error: {1}'.format(tid, e))
            f = {}

        # 地区
        areas = f.get("areas", []) or []
        if areas:
            filter_list.append({
                "key": "area", "name": "地区",
                "value": [{"n": "全部", "v": ""}] +
                         [{"n": a.get("name", ""), "v": a.get("area_id", "")} for a in areas]
            })
        # 类型
        genres = f.get("genres", []) or []
        if genres:
            filter_list.append({
                "key": "genre", "name": "类型",
                "value": [{"n": "全部", "v": ""}] +
                         [{"n": g.get("name", ""), "v": g.get("genre_id", "")} for g in genres]
            })
        # 年份
        years = f.get("published_years", []) or []
        if years:
            filter_list.append({
                "key": "year", "name": "年份",
                "value": [{"n": "全部", "v": ""}] +
                         [{"n": str(y), "v": str(y)} for y in years]
            })
        # 语言
        languages = f.get("languages", []) or []
        if languages:
            filter_list.append({
                "key": "language", "name": "语言",
                "value": [{"n": "全部", "v": ""}] +
                         [{"n": l.get("name", ""), "v": l.get("language_id", "")} for l in languages]
            })
        return tid, filter_list

    def _get_filters(self):
        """动态获取所有分类的筛选器 (并发拉取, 结果缓存)"""
        if self._filters_cache is not None:
            return self._filters_cache

        filters = {}
        try:
            with ThreadPoolExecutor(max_workers=min(7, len(self.CATEGORIES))) as pool:
                for tid, fl in pool.map(self._fetch_category_filters,
                                        [c["type_id"] for c in self.CATEGORIES]):
                    filters[tid] = fl
        except Exception as e:
            print('get_filters error: {0}'.format(e))
            for c in self.CATEGORIES:
                filters.setdefault(c["type_id"], [])

        self._filters_cache = filters
        return filters

    # ===== 分类列表 =====

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        try:
            page = int(pg)
            if page < 1:
                page = 1
        except:
            page = 1
        try:
            extend = json.loads(extend) if isinstance(extend, str) else (extend or {})
        except:
            extend = {}

        params = {"page": str(page)}
        if extend.get("area"):
            params["area"] = extend["area"]
        if extend.get("genre"):
            params["genre"] = extend["genre"]
        if extend.get("year"):
            params["year"] = extend["year"]
        if extend.get("language"):
            params["language"] = extend["language"]

        videos = []
        total = 0
        try:
            queries = self._fetch_nextdata("/explore/" + tid, params)
            data = self._find_query_data(queries, self._is_list_query)
            items, total = self._pages_items(data)
            videos = self._to_videos(items)
        except Exception as e:
            print('categoryContent error: {0}'.format(e))

        # 用服务端总数精确计算页数 (每页48条)
        if videos:
            pagecount = (total + self.PER_PAGE - 1) // self.PER_PAGE if total else page + 1
            if pagecount < page:
                pagecount = page
        else:
            pagecount = page

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": self.PER_PAGE,
            "total": total or (pagecount * self.PER_PAGE),
        }

    # ===== 详情页 =====

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vid = str(ids[0])
            queries = self._fetch_nextdata("/streams/{0}/detail".format(vid))

            meta_data = self._find_query_data(
                queries, lambda k: len(k) >= 3 and k[0] == "videos" and str(k[1]) == vid and k[2] == "metadata")
            src_data = self._find_query_data(
                queries, lambda k: len(k) >= 3 and k[0] == "videos" and str(k[1]) == vid and k[2] == "sources")

            m = {}
            if isinstance(meta_data, dict):
                m = meta_data.get('data') or {}
            sources = []
            if isinstance(src_data, dict):
                sources = src_data.get('data') or []
            elif isinstance(src_data, list):
                sources = src_data

            if not m:
                return result

            play_from = []
            play_url = []

            for src in sources:
                name = src.get("name", "未知") or "未知"
                url_str = src.get("url", "") or ""
                if not url_str:
                    continue

                # url格式: title$url#title$url#...
                episodes = url_str.split("#")
                urls = []
                for idx, ep in enumerate(episodes, start=1):
                    parts = ep.split("$", 1)
                    if len(parts) == 2:
                        title, ep_url = parts[0].strip(), parts[1].strip()
                    else:
                        title, ep_url = str(idx), parts[0].strip()
                    if not title:
                        title = str(idx)
                    if not ep_url:
                        continue
                    urls.append("{0}${1}".format(title, ep_url))

                if urls:
                    play_from.append(name)
                    play_url.append("#".join(urls))

            # 演员和导演
            actors = ", ".join(a.get("name", "") for a in (m.get("actors") or []) if a.get("name"))
            directors = ", ".join(d.get("name", "") for d in (m.get("directors") or []) if d.get("name"))

            # 简介
            content = m.get("description", "") or ""
            vod_content = re.sub(r'<[^>]+>', '', content).strip()

            result["list"] = [{
                "vod_id": str(m.get("video_id", vid) or vid),
                "vod_name": m.get("title", "") or "",
                "vod_pic": m.get("cover_image", "") or "",
                "type_name": m.get("genre", "") or m.get("category", "") or "",
                "vod_director": directors,
                "vod_actor": actors,
                "vod_year": str(m.get("published_year", "") or ""),
                "vod_area": m.get("area", "") or "",
                "vod_content": vod_content,
                "vod_remarks": m.get("remarks", "") or "",
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }]
        except Exception as e:
            print('detailContent error: {0}'.format(e))
        return result

    # ===== 播放 =====

    def playerContent(self, flag, id, vipFlags):
        result = {}
        try:
            # id就是m3u8直链URL
            url = id.strip()
            result["parse"] = 0
            result["url"] = url
            result["header"] = self._play_header
        except Exception as e:
            print('playerContent error: {0}'.format(e))
        return result

    # ===== 搜索 =====

    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            key = (key or "").strip()
            if not key:
                return result

            # 搜索页数据端点: /_next/data/{buildId}/results.json?q={keyword}
            queries = self._fetch_nextdata("/results", {"q": key})
            data = self._find_query_data(
                queries, lambda k: len(k) >= 3 and isinstance(k[2], dict) and k[0] == "explore")
            items, _ = self._pages_items(data)
            result["list"] = self._to_videos(items)
        except Exception as e:
            print('searchContent error: {0}'.format(e))
        return result
