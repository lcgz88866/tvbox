# -*- coding: utf-8 -*-
"""
==========================================================
  宅男影视 (m.kptv.us) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎)
  框架: Vue.js + Vite SPA (多源聚合, REST API)
  更新: 2026-09-08

  实现变更说明(2026-09-08 修复"加载没数据"):
  原版本依赖 m.kptv.us 的 /api/{hot,detail,search,json} 代理接口,
  但当前该后端对所有 /api/hot 请求一律返回 400 "缺少 API URL", 导致
  整个爬虫拿不到任何数据(/api/search、/api/detail、/api/json 同样失灵)。

  现改为: 仅用 /api/web 拿站点配置(API URL 与分类映射), 业务请求全部
  直接对接底层 macCMS 资源站(standard macCMS v10 API):
    - 列表:   {api}?ac=videolist&t={tid}&pg={page}&area=&class=&year=
    - 详情:   {api}?ac=detail&ids={id}
    - 搜索:   {api}?ac=search&wd={keyword}&pg={page}
    - 播放:   详情里的 vod_play_url 就是直链 m3u8, parse=0 直出
  默认主站:  bfzyapi.com / cj.lziapi.com (来自 hot_db / search_api)
  短剧站:    bf.xoxowin86cisyap.com (来自 short 字段)

  路由(原 /api/* 已废弃):
    配置:    GET  /api/web     {hot_db, search_api, short, ...}
    列表:    {源API}?ac=videolist&t=21&pg=1
    详情:    {源API}?ac=detail&ids=161459
    搜索:    {源API}?ac=search&wd=起义&pg=1

  播放源:
    来自详情 vod_play_url 的 m3u8 直链(无需 /api/json 解析)
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
import urllib.request
import urllib.parse
from urllib.parse import quote, urlencode


class Spider(Spider):

    HOST = "https://m.kptv.us"
    UA = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # 主分类 (从 /api/web 的 hot_db 字段动态获取)
    CATEGORIES = [
        {"type_name": "电影", "type_id": "21"},
        {"type_name": "电视剧", "type_id": "31"},
        {"type_name": "综艺", "type_id": "47"},
        {"type_name": "动漫", "type_id": "41"},
    ]

    # 短剧分类 (从 /api/web 的 short 字段动态获取)
    SHORT_CATEGORIES = [
        {"type_name": "反转爽文", "type_id": "68"},
        {"type_name": "都市脑洞", "type_id": "71"},
        {"type_name": "古装仙侠", "type_id": "72"},
        {"type_name": "现代言情", "type_id": "67"},
        {"type_name": "穿越年代", "type_id": "66"},
    ]

    PER_PAGE = 20

    # 硬编码备用API源 (当/api/web不可用时作为兜底)
    FALLBACK_HOT_API = "https://cj.10010888.xyz"
    FALLBACK_SHORT_API = "https://cj.lziapi.com"
    FALLBACK_SEARCH_SOURCES = [
        {"name": "cj.10010888.xyz", "api": "https://cj.10010888.xyz"},
        {"name": "bfzyapi.com", "api": "https://bfzyapi.com"},
        {"name": "cj.lziapi.com", "api": "https://cj.lziapi.com"},
    ]

    def init(self, extend=""):
        self.ua = self.UA
        self.host = self.HOST
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
        }
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

        self._play_header = json.dumps({
            "User-Agent": self.ua,
        })

        # 配置缓存
        self._web_config = None
        self._hot_api = None
        self._search_sources = None
        self._short_api = None
        self._category_map = None  # {分类名: type_id}
        self._short_map = None     # {短剧分类名: type_id}

    def getName(self):
        return "宅男影视"

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

    # ===== HTTP辅助 =====

    def _request(self, url, method='GET', data=None, timeout=15, headers=None, retries=2):
        """通用请求方法，带重试和详细错误日志"""
        last_err = ""
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=headers or self.headers, method=method)
                if data:
                    req.data = json.dumps(data).encode('utf-8')
                    req.headers['Content-Type'] = 'application/json'
                resp = urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx)
                raw = resp.read().decode('utf-8', errors='replace')
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    print(f"[JSONDecodeError] URL: {url}, raw: {raw[:200]}")
                    return {}
            except urllib.error.HTTPError as e:
                last_err = f"HTTPError {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"
                print(f"[HTTPError] URL: {url}, Code: {e.code}, Err: {last_err}")
                if e.code >= 500:
                    import time
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return {}
            except urllib.error.URLError as e:
                last_err = f"URLError: {e.reason}"
                print(f"[URLError] URL: {url}, Err: {last_err}")
                import time
                time.sleep(1.5 * (attempt + 1))
                continue
            except Exception as e:
                last_err = str(e)
                print(f"[Exception] URL: {url}, Err: {last_err}")
                import time
                time.sleep(1.5 * (attempt + 1))
                continue
        print(f"[RetryFailed] 所有{retries}次重试均失败, URL: {url}")
        return {}

    def _get_json(self, path, timeout=10):
        """GET请求获取JSON"""
        url = self.host + path
        return self._request(url, method='GET', timeout=timeout)

    def _post_json(self, path, data, timeout=15):
        """POST JSON请求"""
        url = self.host + path
        return self._request(url, method='POST', data=data, timeout=timeout)

    def _fetch_maccms(self, api_url, params):
        """直接调用maccms CMS API - 同时支持GET和POST"""
        # 尝试1: GET请求
        try:
            url = api_url + "/api.php" + "?" + urlencode(params)
            headers = {"User-Agent": self.ua, "Accept": "application/json"}
            result = self._request(url, method='GET', headers=headers, timeout=15, retries=1)
            if result and result != {}:
                return result
        except Exception as e:
            print(f"[_fetch_maccms GET] 失败: {e}")

        # 尝试2: 直接路径格式 (部分站点使用 /api.php/ac=list 格式)
        try:
            # 去掉尾部斜杠，添加api.php
            base = api_url.rstrip('/')
            url = base + "/api.php/provide/vod/" + urlencode(params)
            headers = {"User-Agent": self.ua, "Accept": "application/json"}
            result = self._request(url, method='GET', headers=headers, timeout=15, retries=1)
            if result and result != {}:
                return result
        except Exception as e:
            print(f"[_fetch_maccms GET2] 失败: {e}")

        # 尝试3: POST请求
        try:
            url = api_url + "/api.php"
            headers = {"User-Agent": self.ua, "Accept": "application/json", "Content-Type": "application/json"}
            result = self._request(url, method='POST', data=params, timeout=15, headers=headers, retries=1)
            if result and result != {}:
                return result
        except Exception as e:
            print(f"[_fetch_maccms POST] 失败: {e}")

        return {}

    # ===== 配置获取 =====

    def _get_config(self):
        """获取网站配置 (带缓存 + 详细日志 + 兜底)
        新版 /api/web 的 hot_db / short 字段为多行:
          - 第1行:  资源API根URL(已含 /api.php/provide/vod/)
          - 第2行:  分类映射  name,tid|name,tid|...
        search_api: 多行 csv, 其中含 '__app_only__' 的行仅 APP 可用, 这里过滤掉。"""
        if self._web_config is not None:
            return self._web_config

        print("[_get_config] 开始获取网站配置...")

        # 尝试1: 从 /api/web 获取
        web = self._get_json("/api/web")
        if web:
            print(f"[_get_config] /api/web 返回: {json.dumps(web, ensure_ascii=False)[:500]}")
            d = web.get("data", {})
            if d:
                # 解析 hot_db / short(都是 "api_url\n分类1,tid|分类2,tid|...")
                def _parse_two_line_db(text):
                    """返回 (api_url, {分类名: tid})"""
                    if not text or not isinstance(text, str):
                        return "", {}
                    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
                    if not lines:
                        return "", {}
                    api_url = lines[0].rstrip("/")  # 标准化
                    cat_map = {}
                    if len(lines) >= 2:
                        for pair in lines[1].split("|"):
                            pair = pair.strip()
                            if not pair:
                                continue
                            last_comma = pair.rfind(",")
                            if last_comma > 0:
                                name = pair[:last_comma].strip()
                                tid = pair[last_comma + 1:].strip()
                                if name and tid:
                                    cat_map[name] = tid
                    return api_url, cat_map

                hot_db = d.get("hot_db", "")
                hot_api, hot_map = _parse_two_line_db(hot_db)
                if not hot_api:
                    print("[_get_config] hot_db 解析失败, 使用硬编码备用API")
                    self._hot_api = self.FALLBACK_HOT_API
                    self._category_map = {"电影": "21", "电视剧": "31", "综艺": "47", "动漫": "41"}
                else:
                    self._hot_api = hot_api
                    self._category_map = hot_map
                    print(f"[_get_config] hot_db 解析成功: api={self._hot_api}, 分类映射={self._category_map}")

                # 解析 search_api: 多行 csv, 过滤 __app_only__ 行
                search_api = d.get("search_api", "")
                self._search_sources = []
                if search_api and isinstance(search_api, str):
                    for line in search_api.split("\n"):
                        line = line.strip()
                        if not line:
                            continue
                        fields = [f.strip() for f in line.split(",")]
                        name = fields[0] if fields else ""
                        api = fields[1] if len(fields) > 1 else ""
                        # 过滤: APP专享 / app_only 标记
                        if any("app_only" in f.lower() for f in fields[2:]):
                            continue
                        if api and "://" in api:
                            self._search_sources.append({"name": name, "api": api.rstrip("/")})
                # 兜底: 若 search_api 解析不到任何可用源, 用硬编码(过滤 app_only 后: bfzyapi/lziapi)
                if not self._search_sources:
                    self._search_sources = [
                        {"name": "在线资源1", "api": "https://bfzyapi.com/api.php/provide/vod"},
                        {"name": "在线资源2", "api": "https://cj.lziapi.com/api.php/provide/vod"},
                    ]

                # 解析 short: "api_url\n分类1,id1|分类2,id2|..."
                short = d.get("short", "")
                short_api, short_map = _parse_two_line_db(short)
                if short_api:
                    self._short_api = short_api
                else:
                    self._short_api = self.FALLBACK_SHORT_API
                # short 分类映射(短剧 tid)不强制, 保留 default 类目也可
                self._short_map = short_map

                self._web_config = d
                print(f"[_get_config] 配置获取成功: hot_api={self._hot_api}, "
                      f"search_sources={len(self._search_sources)}, short_api={self._short_api}")
                return d

        # 兜底: 使用硬编码的备用API
        print("[_get_config] /api/web 返回为空或解析失败, 使用硬编码备用API")
        self._hot_api = "https://bfzyapi.com/api.php/provide/vod"
        self._search_sources = [
            {"name": "在线资源1", "api": "https://bfzyapi.com/api.php/provide/vod"},
            {"name": "在线资源2", "api": "https://cj.lziapi.com/api.php/provide/vod"},
        ]
        self._short_api = "https://bf.xoxowin86cisyap.com/api.php/provide/vod"
        self._category_map = {"电影": "21", "电视剧": "31", "综艺": "47", "动漫": "41"}
        self._short_map = {"反转爽文": "68", "都市脑洞": "71", "古装仙侠": "72",
                           "现代言情": "67", "穿越年代": "66"}
        self._web_config = {"fallback": True}
        print(f"[_get_config] 兜底配置: hot_api={self._hot_api}, search_sources={len(self._search_sources)}, short_api={self._short_api}")
        return self._web_config

    # ===== 首页 =====

    def homeContent(self, filter):
        result = {}
        config = self._get_config()

        # 主分类
        classes = []
        for c in self.CATEGORIES:
            classes.append({"type_name": c["type_name"], "type_id": c["type_id"]})
        # 短剧分类 (合并为一个入口)
        for c in self.SHORT_CATEGORIES:
            classes.append({"type_name": c["type_name"], "type_id": c["type_id"]})

        result["class"] = classes
        result["filters"] = self._get_filters()
        return result

    def homeVideoContent(self):
        """首页推荐 - 电影分类第1页 (直接调底层 macCMS 资源站, 绕过已失灵的 /api/hot)"""
        config = self._get_config()
        api_url = self._hot_api
        if not api_url:
            print("[homeVideoContent] api_url 为空, 返回空列表")
            return {"list": []}

        # 使用 hot_db 解析出的电影 type_id (第一个分类), 没有就回退 21
        first_type = "21"
        if isinstance(self._category_map, dict) and self._category_map:
            first_type = next(iter(self._category_map.values()), "21")
        print(f"[homeVideoContent] 请求首页推荐, api_url={api_url}, type={first_type}")
        data = self._fetch_maccms(api_url, {"ac": "videolist", "t": first_type, "pg": "1"})
        items = data.get("list", []) if isinstance(data, dict) else []
        videos = []
        for item in items:
            vod_id = item.get("vod_id", "")
            if not vod_id:
                continue
            videos.append({
                "vod_id": f"{api_url}|{vod_id}",
                "vod_name": item.get("vod_name", ""),
                "vod_pic": item.get("vod_pic", ""),
                "vod_remarks": item.get("vod_remarks", ""),
            })
        print(f"[homeVideoContent] 返回 {len(videos)} 条推荐")
        return {"list": videos[:30]}

    def _get_filters(self):
        """获取分类筛选器"""
        filters = {}

        # 主分类筛选 (通过maccms API获取)
        config = self._get_config()
        api_url = self._hot_api

        if api_url:
            # 获取maccms分类信息
            maccms_data = self._fetch_maccms(api_url, {"ac": "list"})
            classes = maccms_data.get("class", [])

            for c in self.CATEGORIES:
                # 使用 hot_db 解析出的 type_id
                tid = self._category_map.get(c["type_name"], c["type_id"])
                filter_list = []

                # 地区
                filter_list.append({
                    "key": "area",
                    "name": "地区",
                    "value": [{"n": "全部", "v": ""}] +
                             [{"n": a, "v": a} for a in
                              ["中国大陆", "中国香港", "中国台湾", "美国", "韩国", "日本",
                               "泰国", "英国", "法国", "印度", "加拿大", "俄罗斯"]]
                })

                # 年份
                filter_list.append({
                    "key": "year",
                    "name": "年份",
                    "value": [{"n": "全部", "v": ""}] +
                             [{"n": str(y), "v": str(y)} for y in
                              [2026, 2025, 2024, 2023, 2022, 2021,
                               2020, 2019, 2018, 2017, 2016, 2015]]
                })

                # 类型
                type_classes = ["剧情", "喜剧", "动作", "爱情", "科幻", "动画",
                                "悬疑", "惊悚", "恐怖", "犯罪", "战争", "奇幻",
                                "冒险", "古装", "武侠", "灾难"]
                if tid == "2":
                    type_classes = ["古装", "都市", "青春", "偶像", "家庭", "警匪",
                                    "悬疑", "科幻", "历史", "武侠", "军事", "谍战"]
                elif tid == "3":
                    type_classes = ["选秀", "综艺", "情感", "访谈", "播报", "旅游",
                                    "音乐", "美食", "纪实", "曲艺", "生活", "游戏"]
                elif tid == "4":
                    type_classes = ["热血", "科幻", "推理", "搞笑", "冒险", "校园",
                                    "动作", "机战", "运动", "治愈", "魔法", "乙女"]

                filter_list.append({
                    "key": "class",
                    "name": "类型",
                    "value": [{"n": "全部", "v": ""}] +
                             [{"n": t, "v": t} for t in type_classes]
                })

                # 排序
                filter_list.append({
                    "key": "by",
                    "name": "排序",
                    "value": [
                        {"n": "时间", "v": "time"},
                        {"n": "人气", "v": "hits"},
                        {"n": "评分", "v": "score"},
                    ]
                })

                filters[tid] = filter_list

        # 短剧分类 (无筛选)
        for c in self.SHORT_CATEGORIES:
            filters[c["type_id"]] = []

        return filters

    # ===== 分类列表 =====

    def _is_short_category(self, tid):
        """判断是否是短剧分类"""
        short_ids = {c["type_id"] for c in self.SHORT_CATEGORIES}
        return tid in short_ids

    def categoryContent(self, tid, pg, filter, extend):
        """分类列表(直接调底层 macCMS 资源站, 不再走已失灵的 /api/hot)"""
        page = max(int(pg or 1), 1)
        extend = extend or {}
        config = self._get_config()

        # 解析 tid: TVBox 传入的 tid 可能是 name(电影/剧集 等) 或 type_id(21/31 等)
        if self._is_short_category(tid):
            # 短剧分类 - 短剧站 api
            api_url = self._short_api or self.FALLBACK_SHORT_API
            actual_tid = tid  # 短剧 tid(如 68)直接可作为 macCMS 的 t
            kind = "short"
        else:
            api_url = self._hot_api
            # 兼容: TVBox 端传 type_name (如"电影")时映射到数字 tid
            if isinstance(self._category_map, dict) and tid in self._category_map:
                actual_tid = self._category_map[tid]
            else:
                actual_tid = tid
            kind = "main"

        if not api_url:
            print(f"[categoryContent] api_url 为空 (tid={tid})")
            return {"list": [], "page": page, "pagecount": 1, "limit": self.PER_PAGE, "total": 0}

        # 构建 macCMS 列表参数(支持筛选)
        params = {"ac": "videolist", "t": str(actual_tid), "pg": str(page)}
        if extend.get("area"):
            params["area"] = str(extend["area"])
        if extend.get("year"):
            params["year"] = str(extend["year"])
        if extend.get("class"):
            params["class"] = str(extend["class"])
        # 注: macCMS v10 标准 API 无 by 排序参数, 这里忽略

        print(f"[categoryContent] {kind} 列表, api_url={api_url}, t={actual_tid}, pg={page}, params={params}")
        data = self._fetch_maccms(api_url, params)
        items = data.get("list", []) if isinstance(data, dict) else []

        videos = []
        for item in items:
            vod_id = item.get("vod_id", "")
            if not vod_id:
                continue
            videos.append({
                "vod_id": f"{api_url}|{vod_id}",
                "vod_name": item.get("vod_name", ""),
                "vod_pic": item.get("vod_pic", ""),
                "vod_remarks": item.get("vod_remarks", ""),
            })

        try:
            pagecount = int(data.get("pagecount", 1))
        except (TypeError, ValueError):
            pagecount = 1
        try:
            total = int(data.get("total", 0))
        except (TypeError, ValueError):
            total = 0
        if not videos and page > 1:
            # 翻页越界, 视为最后页
            pagecount = page
        elif pagecount < page:
            pagecount = page

        print(f"[categoryContent] 返回 {len(videos)} 条, page={page}/{pagecount}, total={total}")
        return {
            "list": videos,
            "page": page,
            "pagecount": max(pagecount, 1),
            "limit": self.PER_PAGE,
            "total": total,
        }

    # ===== 详情页 =====

    def detailContent(self, ids):
        result = {"list": []}
        try:
            pid = ids[0]
            # 解析 PID: 优先拆 "api_url|vod_id", 没有则用默认主站 API
            if "|" in pid:
                parts = pid.split("|", 1)
                api_url = parts[0]
                vid = parts[1]
            else:
                self._get_config()
                api_url = self._hot_api
                vid = pid

            if not vid:
                print(f"[detailContent] vid 为空, pid={pid}")
                return result

            print(f"[detailContent] 请求详情, api_url={api_url}, vid={vid}")
            data = self._fetch_maccms(api_url, {"ac": "detail", "ids": str(vid)})
            v = (data.get("list") or [{}])[0] if isinstance(data, dict) else {}

            # 兜底: 在其他 search_sources 查同一 id
            if (not v) and self._search_sources:
                for src in self._search_sources:
                    if src["api"] == api_url:
                        continue
                    alt = self._fetch_maccms(src["api"], {"ac": "detail", "ids": str(vid)})
                    alt_v = (alt.get("list") or [{}])[0] if isinstance(alt, dict) else {}
                    if alt_v:
                        v = alt_v
                        api_url = src["api"]
                        break

            if not v:
                print("[detailContent] 无法获取详情数据")
                return result

            print(f"[detailContent] 详情获取成功: {v.get('vod_name', '')}")

            # 解析播放源 (macCMS 标准: vod_play_from / vod_play_url 都用 "$$$" 分线路,
            # 集内用 "#", 集名/URL 用 "$")
            raw_from = v.get("vod_play_from", "")
            raw_url = v.get("vod_play_url", "")
            from_list = raw_from.split("$$$") if raw_from else []
            url_list = raw_url.split("$$$") if raw_url else []

            play_from = []
            play_url = []

            for i, from_key in enumerate(from_list):
                from_key = from_key.strip()
                if not from_key:
                    continue
                url_str = url_list[i] if i < len(url_list) else ""
                if not url_str:
                    continue
                episodes = url_str.split("#")
                urls = []
                for idx, ep in enumerate(episodes, start=1):
                    seg = ep.split("$", 1)
                    if len(seg) == 2:
                        title, ep_url = seg[0].strip(), seg[1].strip()
                    else:
                        title, ep_url = str(idx), seg[0].strip()
                    if not title:
                        title = str(idx)
                    # 剧集 URL 已是 m3u8 直链, PID 直接记 url, 播放时 parse=0
                    urls.append(f"{title}${ep_url}")
                if urls:
                    play_from.append(from_key)
                    play_url.append("#".join(urls))

            # 兜底: 主源无播放, 在其他源再试
            if not play_url and self._search_sources:
                for src in self._search_sources:
                    if src["api"] == api_url:
                        continue
                    alt = self._fetch_maccms(src["api"], {"ac": "detail", "ids": str(vid)})
                    alt_v = (alt.get("list") or [{}])[0] if isinstance(alt, dict) else {}
                    if not alt_v:
                        continue
                    raw_from2 = alt_v.get("vod_play_from", "")
                    raw_url2 = alt_v.get("vod_play_url", "")
                    from_list2 = raw_from2.split("$$$") if raw_from2 else []
                    url_list2 = raw_url2.split("$$$") if raw_url2 else []
                    for j, fk in enumerate(from_list2):
                        fk = fk.strip()
                        if not fk:
                            continue
                        url_str2 = url_list2[j] if j < len(url_list2) else ""
                        if not url_str2:
                            continue
                        episodes2 = url_str2.split("#")
                        urls2 = []
                        for idx, ep in enumerate(episodes2, start=1):
                            seg = ep.split("$", 1)
                            if len(seg) == 2:
                                title, ep_url = seg[0].strip(), seg[1].strip()
                            else:
                                title, ep_url = str(idx), seg[0].strip()
                            if not title:
                                title = str(idx)
                            urls2.append(f"{title}${ep_url}")
                        if urls2:
                            play_from.append(fk)
                            play_url.append("#".join(urls2))
                    if play_url:
                        break

            content = v.get("vod_content", "")
            vod_content = re.sub(r'<[^>]+>', '', content).strip()

            result["list"] = [{
                "vod_id": str(v.get("vod_id", vid)),
                "vod_name": v.get("vod_name", ""),
                "vod_pic": v.get("vod_pic", ""),
                "vod_director": v.get("vod_director", ""),
                "vod_actor": v.get("vod_actor", ""),
                "vod_year": str(v.get("vod_year", "")),
                "vod_area": v.get("vod_area", ""),
                "vod_content": vod_content,
                "vod_remarks": v.get("vod_remarks", ""),
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }]
        except Exception as e:
            print(f'detailContent error: {e}')
        return result


    # ===== 播放 =====

    def playerContent(self, flag, id, vipFlags):
        """返回剧集直链 (macCMS 详情里 vod_play_url 已经是 m3u8 直链, parse=0 直出)。"""
        result = {}
        try:
            # 兼容: 旧的 api_url|ep_url 形式 (虽然 detailContent 改造后通常已不带前缀)
            if "|" in id:
                parts = id.split("|", 1)
                movie_url = parts[1]
            else:
                movie_url = id

            # m3u8/mp4/flv/ts 直链, parse=0 直接播放
            if re.search(r'\.(m3u8|mp4|flv|ts)(\?|#|$)', movie_url, re.I):
                result["parse"] = 0
                result["url"] = movie_url
                result["header"] = self._play_header
                return result

            # 非直链(理论上 macCMS vod_play_url 都是直链, 兜底让 TVBox 嗅探)
            result["parse"] = 1
            result["url"] = movie_url
            result["header"] = self._play_header
        except Exception as e:
            print(f'playerContent error: {e}')
            result["parse"] = 0
            result["url"] = id
        return result


    # ===== 搜索 =====

    def searchContent(self, key, quick, pg="1"):
        """多源搜索: 直接调各 macCMS 资源站的 ac=search 接口(原 /api/search 代理已失灵)"""
        key = (key or "").strip()
        if not key:
            return {"list": []}

        page = max(int(pg or 1), 1)
        self._get_config()
        sources_to_try = self._search_sources or [
            {"name": "在线资源1", "api": "https://bfzyapi.com/api.php/provide/vod"},
            {"name": "在线资源2", "api": "https://cj.lziapi.com/api.php/provide/vod"},
        ]
        print(f"[searchContent] 搜索 '{key}', 使用 {len(sources_to_try)} 个源")

        videos = []
        seen_ids = set()
        for src in sources_to_try:
            try:
                data = self._fetch_maccms(src["api"], {"ac": "search", "wd": key, "pg": str(page)})
                items = data.get("list", []) if isinstance(data, dict) else []
                for item in items:
                    vid = str(item.get("vod_id", ""))
                    if not vid or vid in seen_ids:
                        continue
                    seen_ids.add(vid)
                    videos.append({
                        # 同样用 "api_url|vid" 形式, 方便 detailContent 直接定位源
                        "vod_id": f"{src['api']}|{vid}",
                        "vod_name": item.get("vod_name", ""),
                        "vod_pic": item.get("vod_pic", ""),
                        "vod_remarks": item.get("vod_remarks", ""),
                    })
            except Exception as e:
                print(f"[searchContent] 源 {src.get('name', '')} 搜索失败: {e}")
                continue

        print(f"[searchContent] 搜索 '{key}' 返回 {len(videos)} 条")
        return {"list": videos}



if __name__ == "__main__":
    import time

    s = Spider()
    s.init()

    # 1. 首页分类
    print("\n===== 首页分类 =====")
    home = s.homeContent(True)
    print(f"分类数: {len(home.get('class', []))}")
    for c in home["class"]:
        print(f"  [{c['type_id']}] {c['type_name']}")

    # 2. 筛选器
    print("\n===== 筛选器 =====")
    filters = home.get("filters", {})
    for tid, fl in filters.items():
        if fl:
            names = [f["name"] for f in fl]
            print(f"  {tid}: {names}")

    # 3. 首页推荐
    print("\n===== 首页推荐 =====")
    rec = s.homeVideoContent()
    print(f"推荐数: {len(rec.get('list', []))}")
    for v in rec["list"][:5]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    # 4. 分类列表
    print("\n===== 分类列表 (电影第1页) =====")
    t0 = time.time()
    cat = s.categoryContent("1", "1", True, {})
    print(f"耗时: {time.time()-t0:.2f}s, 返回: {len(cat.get('list', []))}条")
    for v in cat["list"][:5]:
        print(f"  [{v['vod_id'][:60]}] {v['vod_name']} - {v['vod_remarks']}")

    # 5. 分类+筛选
    print("\n===== 分类+筛选 (电影+2026年) =====")
    cat2 = s.categoryContent("1", "1", True, {"year": "2026"})
    print(f"返回: {len(cat2.get('list', []))}条, total={cat2.get('total', 'N/A')}")
    for v in cat2["list"][:3]:
        print(f"  {v['vod_name']}")

    # 6. 分类分页
    print("\n===== 分类分页 (电影第2页) =====")
    cat3 = s.categoryContent("1", "2", True, {})
    print(f"返回: {len(cat3.get('list', []))}条")
    for v in cat3["list"][:3]:
        print(f"  {v['vod_name']}")

    # 7. 短剧分类
    print("\n===== 短剧分类 (反转爽文) =====")
    cat4 = s.categoryContent("68", "1", True, {})
    print(f"返回: {len(cat4.get('list', []))}条")
    for v in cat4["list"][:3]:
        print(f"  {v['vod_name']} - {v['vod_remarks']}")

    # 8. 详情页
    print("\n===== 详情页 =====")
    if cat["list"]:
        test_pid = cat["list"][0]["vod_id"]
        detail = s.detailContent([test_pid])
        if detail["list"]:
            vod = detail["list"][0]
            print(f"  标题: {vod['vod_name']}")
            print(f"  年份: {vod['vod_year']}")
            print(f"  地区: {vod['vod_area']}")
            print(f"  导演: {vod['vod_director']}")
            print(f"  演员: {str(vod['vod_actor'])[:80]}")
            print(f"  简介: {str(vod['vod_content'])[:80]}")
            play_from = vod["vod_play_from"].split("$$$")
            play_url = vod["vod_play_url"].split("$$$")
            print(f"  播放源: {' / '.join(play_from)}")
            for i, (name, urls) in enumerate(zip(play_from, play_url)):
                eps = urls.split("#")
                print(f"    [{name}] {len(eps)}集, 第1集: {eps[0][:80]}")

    # 9. 播放
    print("\n===== 播放测试 =====")
    if detail["list"]:
        first_source = detail["list"][0]["vod_play_url"].split("$$$")[0]
        first_ep = first_source.split("#")[0]
        ep_title, pid_value = first_ep.split("$", 1)
        play = s.playerContent("", pid_value, [])
        print(f"  URL: {play.get('url', '')[:80]}")
        print(f"  Parse: {play.get('parse', '')}")

    # 10. 搜索
    print("\n===== 搜索 (九门) =====")
    t0 = time.time()
    search = s.searchContent("九门", False)
    print(f"耗时: {time.time()-t0:.2f}s, 结果: {len(search.get('list', []))}条")
    for v in search["list"][:10]:
        print(f"  [{v['vod_id'][:60]}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 全部测试完成 =====")
