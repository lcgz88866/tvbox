#coding=utf-8
#!/usr/bin/python
# 白嫖者联盟 (ai.baipiaozhe.com) - JSON API驱动站点
#
# 原理:
#   1. React SPA + RESTful JSON API, 无需解析HTML, 无需验证码
#   2. API: /v1/browse/catalog (列表/搜索), /v1/catalog/{id} (详情含剧集)
#   3. 播放: urls.yjm3u8 = https://zy.baipiaozhe.com/v1/playback/yjm3u8/{token}.m3u8
#      该URL返回302跳转到真实m3u8/MP4, TVBox播放器自动跟随重定向
#   4. 分类: movie/series/short_drama/anime/variety/documentary/sports
#   5. 筛选: genre(类型)/area(地区)/year(年份)/language(语言)
#
# 请求签名 (2026-08-12 站点新增):
#   所有 /v1/ 路径的请求必须携带三个签名头:
#     x-ai-movie-timestamp: 毫秒时间戳
#     x-ai-movie-nonce: 32位随机hex
#     x-ai-movie-signature: HMAC-SHA256签名
#   签名消息格式 (4行, \n分隔):
#     {METHOD}\n{pathname}{search}\n{timestamp}\n{nonce}
#   密钥: f39d73aa7a6426203cdee1ef17b31d3b7ea8c23f4c59c62a3a8aa0f39ee5e79d
#
# 播放策略:
#   1. 直接返回m3u8地址 (parse=0, 播放器自动跟随302)
#   2. 需要Referer头播放
#
# 速度: 快 (JSON API, 无HTML解析, 无验证码)

import sys
import re
import json
import ssl
import time
import hmac
import hashlib
import secrets
import urllib.parse
import urllib.request
import urllib.error

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


class Spider(Spider):

    # 请求签名密钥 (从 movie-card-runtime-BcoVWsBn.js 提取)
    SIGN_SECRET = "f39d73aa7a6426203cdee1ef17b31d3b7ea8c23f4c59c62a3a8aa0f39ee5e79d"

    def getName(self):
        return "白嫖者联盟"

    def init(self, extend=""):
        self.host = "https://ai.baipiaozhe.com"
        self.zy_host = "https://zy.baipiaozhe.com"
        self.ua = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        self._play_header = json.dumps({
            "User-Agent": self.ua,
            "Referer": self.host + "/",
        })
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

        self.cats = [
            {"type_name": "电影", "type_id": "movie"},
            {"type_name": "剧集", "type_id": "series"},
            {"type_name": "短剧", "type_id": "short_drama"},
            {"type_name": "动漫", "type_id": "anime"},
            {"type_name": "综艺", "type_id": "variety"},
            {"type_name": "纪录片", "type_id": "documentary"},
            {"type_name": "体育", "type_id": "sports"},
        ]

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|ts)(\?|#|$)', url, re.I))

    def manualVideoVCandidate(self, items):
        return []

    def getDependence(self):
        return []

    def action(self, action):
        pass

    def destroy(self):
        pass

    # ===== 签名 =====

    def _sign_headers(self, method, path, query_string):
        """生成API请求签名头
        签名消息格式 (4行, \\n分隔):
            {METHOD}\\n{pathname}{search}\\n{timestamp}\\n{nonce}
        """
        timestamp = str(int(time.time() * 1000))
        nonce = secrets.token_hex(16)

        search = query_string
        if search and not search.startswith("?"):
            search = "?" + search

        message = "{0}\n{1}{2}\n{3}\n{4}".format(
            method.upper(), path, search, timestamp, nonce
        )

        signature = hmac.new(
            self.SIGN_SECRET.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        return {
            "x-ai-movie-timestamp": timestamp,
            "x-ai-movie-nonce": nonce,
            "x-ai-movie-signature": signature,
        }

    # ===== HTTP辅助 =====

    def _api_get(self, path, params=None):
        """调用JSON API并返回解析后的dict (带签名)"""
        url = self.host + path
        qs = ""
        if params:
            qs = urllib.parse.urlencode(params, safe='')
            url = url + "?" + qs

        sign_headers = self._sign_headers("GET", path, qs)

        headers = dict(self.headers)
        headers.update(sign_headers)

        # 优先TVBox基类
        try:
            resp = self.fetch(url, headers=headers)
            text = resp.text if hasattr(resp, 'text') else str(resp)
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="replace")
            return json.loads(text)
        except Exception:
            pass

        # urllib回退
        try:
            req = urllib.request.Request(url, headers=headers)
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=self._ssl_ctx)
            )
            with opener.open(req, timeout=15) as r:
                data = r.read()
                return json.loads(data.decode("utf-8", errors="ignore"))
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode("utf-8", errors="ignore"))
            except:
                return {}
        except Exception:
            return {}

    def _api_post(self, path, body_dict):
        """POST JSON API (带签名)"""
        url = self.host + path
        body = json.dumps(body_dict)

        sign_headers = self._sign_headers("POST", path, "")

        headers = {
            "User-Agent": self.ua,
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Type": "application/json",
            "Referer": self.host + "/",
        }
        headers.update(sign_headers)

        # 优先TVBox基类
        try:
            resp = self.post(url, data=body, headers=headers)
            text = resp.text if hasattr(resp, 'text') else str(resp)
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="replace")
            return json.loads(text)
        except Exception:
            pass

        # urllib回退
        try:
            post_data = body.encode("utf-8")
            req = urllib.request.Request(url, data=post_data, headers=headers, method="POST")
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=self._ssl_ctx)
            )
            with opener.open(req, timeout=15) as r:
                data = r.read()
                return json.loads(data.decode("utf-8", errors="ignore"))
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode("utf-8", errors="ignore"))
            except:
                return {}
        except Exception:
            return {}

    def _card_to_vod(self, card):
        """将API卡片转为TVBox视频对象"""
        pic = card.get("poster_url", "")
        return {
            "vod_id": card.get("id", ""),
            "vod_name": card.get("title", ""),
            "vod_pic": pic,
            "vod_remarks": card.get("remarks", ""),
        }

    # ===== 首页 =====

    def homeContent(self, filter):
        result = {}
        classes = []
        for c in self.cats:
            classes.append({"type_name": c["type_name"], "type_id": c["type_id"]})
        result["class"] = classes
        result["filters"] = self._get_filters()
        return result

    def _get_filters(self):
        """筛选器配置 (对应API的genre/area/year参数)"""
        filters = {}

        # 通用筛选 (所有分类共享同一套)
        common = [
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""},
                {"n": "中国大陆", "v": "中国大陆"},
                {"n": "中国香港", "v": "中国香港"},
                {"n": "中国台湾", "v": "中国台湾"},
                {"n": "美国", "v": "美国"},
                {"n": "韩国", "v": "韩国"},
                {"n": "日本", "v": "日本"},
                {"n": "英国", "v": "英国"},
                {"n": "法国", "v": "法国"},
                {"n": "泰国", "v": "泰国"},
                {"n": "印度", "v": "印度"},
                {"n": "其他", "v": "其他"},
            ]},
            {"key": "year", "name": "年份", "value": self._year_options()},
            {"key": "by", "name": "排序", "value": [
                {"n": "最新", "v": "updated_at"},
                {"n": "最热", "v": "playback_count"},
            ]},
        ]

        for c in self.cats:
            tid = c["type_id"]
            filters_list = list(common)
            # 在地区前面插入类型筛选
            genre_vals = [{"n": "全部", "v": ""}]
            if tid == "movie":
                genre_vals += [
                    {"n": "剧情", "v": "剧情"}, {"n": "喜剧", "v": "喜剧"},
                    {"n": "动作", "v": "动作"}, {"n": "爱情", "v": "爱情"},
                    {"n": "科幻", "v": "科幻"}, {"n": "悬疑", "v": "悬疑"},
                    {"n": "惊悚", "v": "惊悚"}, {"n": "恐怖", "v": "恐怖"},
                    {"n": "犯罪", "v": "犯罪"}, {"n": "动画", "v": "动画"},
                    {"n": "奇幻", "v": "奇幻"}, {"n": "战争", "v": "战争"},
                    {"n": "冒险", "v": "冒险"}, {"n": "警匪", "v": "警匪"},
                ]
            elif tid == "series":
                genre_vals += [
                    {"n": "国产剧", "v": "国产剧"}, {"n": "韩剧", "v": "韩剧"},
                    {"n": "日剧", "v": "日剧"}, {"n": "美剧", "v": "美剧"},
                    {"n": "古装", "v": "古装"}, {"n": "悬疑", "v": "悬疑"},
                    {"n": "喜剧", "v": "喜剧"}, {"n": "犯罪", "v": "犯罪"},
                    {"n": "奇幻", "v": "奇幻"}, {"n": "家庭", "v": "家庭"},
                    {"n": "青春", "v": "青春"}, {"n": "历史", "v": "历史"},
                ]
            elif tid == "anime":
                genre_vals += [
                    {"n": "热血", "v": "热血"}, {"n": "搞笑", "v": "搞笑"},
                    {"n": "冒险", "v": "冒险"}, {"n": "科幻", "v": "科幻"},
                    {"n": "校园", "v": "校园"}, {"n": "动作", "v": "动作"},
                    {"n": "奇幻", "v": "奇幻"}, {"n": "推理", "v": "推理"},
                ]
            elif tid == "variety":
                genre_vals += [
                    {"n": "选秀", "v": "选秀"}, {"n": "情感", "v": "情感"},
                    {"n": "访谈", "v": "访谈"}, {"n": "音乐", "v": "音乐"},
                    {"n": "美食", "v": "美食"}, {"n": "纪实", "v": "纪实"},
                ]
            else:
                genre_vals += [
                    {"n": "剧情", "v": "剧情"}, {"n": "喜剧", "v": "喜剧"},
                    {"n": "悬疑", "v": "悬疑"}, {"n": "科幻", "v": "科幻"},
                ]

            filters_list.insert(0, {"key": "genre", "name": "类型", "value": genre_vals})
            filters[tid] = filters_list

        return filters

    def _year_options(self):
        years = [{"n": "全部", "v": ""}]
        for y in range(2026, 2014, -1):
            years.append({"n": str(y), "v": str(y)})
        years.append({"n": "更早", "v": "2014"})
        return years

    def homeVideoContent(self):
        """首页推荐 - 取各分类最新内容"""
        result = {"list": []}
        for cat in self.cats[:4]:
            data = self._api_get("/v1/browse/catalog", {
                "kind": cat["type_id"],
                "page": "1",
                "limit": "6",
            })
            cards = data.get("cards", [])
            for c in cards:
                result["list"].append(self._card_to_vod(c))
        return result

    # ===== 分类列表 =====

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except:
                extend = {}
        extend = extend or {}

        params = {
            "kind": tid,
            "page": str(page),
            "limit": "20",
        }

        # 应用筛选
        genre = extend.get("genre", "")
        if genre:
            params["genre"] = genre
        area = extend.get("area", "")
        if area:
            params["area"] = area
        year = extend.get("year", "")
        if year:
            params["year"] = year
        by = extend.get("by", "")
        if by:
            params["sort"] = by

        data = self._api_get("/v1/browse/catalog", params)
        cards = data.get("cards", [])

        videos = [self._card_to_vod(c) for c in cards]

        # 分页
        pagination = data.get("pagination", {})
        total = pagination.get("total", 0)
        pagecount = max(1, (total + 19) // 20) if total else 1
        if pagination.get("has_more"):
            pagecount = max(pagecount, page + 1)

        result = {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 20,
            "total": total,
        }
        return result

    # ===== 搜索 =====

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        params = {
            "q": key,
            "page": str(page),
            "limit": "20",
        }
        data = self._api_get("/v1/browse/catalog", params)
        cards = data.get("cards", [])
        videos = [self._card_to_vod(c) for c in cards]
        return {"list": videos}

    # ===== 详情 =====

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0]

        data = self._api_get("/v1/catalog/" + str(vod_id))
        if not data or not data.get("id"):
            return {"list": []}

        # 元数据
        vod = {
            "vod_id": vod_id,
            "vod_name": data.get("title", ""),
            "vod_pic": data.get("poster_url", ""),
            "vod_remarks": data.get("remarks", ""),
            "vod_year": str(data.get("year", "")),
            "vod_area": data.get("area", ""),
            "vod_actor": ", ".join(data.get("actors", [])[:15]),
            "vod_director": ", ".join(data.get("directors", [])[:10]),
            "vod_content": data.get("description", ""),
            "type_name": ", ".join(data.get("genres", [])[:5]),
        }

        # 选集
        episodes = data.get("episodes", [])

        # 如果没有episodes, 尝试多季
        if not episodes:
            seasons = data.get("seasons", [])
            if seasons:
                first_season = seasons[0]
                season_id = first_season.get("id", "")
                if season_id and season_id != vod_id:
                    s_data = self._api_get("/v1/catalog/" + season_id)
                    s_eps = s_data.get("episodes", [])
                    if s_eps:
                        episodes = s_eps

        if episodes:
            # 构建单线路播放列表: ep_name$token
            play_list = []
            for ep in episodes:
                ep_title = ep.get("title", "") or ep.get("display_name", "")
                if not ep_title:
                    ep_title = "第" + str(ep.get("number", 0)) + "集"
                token = ep.get("token", "")
                if token:
                    play_list.append(ep_title + "$" + token)

            if play_list:
                # 获取可用线路列表
                first_token = episodes[0].get("token", "")
                line_names = self._get_line_names(first_token)

                if line_names:
                    # 多线路: 每条线路都是相同的选集, 但flag不同
                    vod["vod_play_from"] = "$$$".join(line_names)
                    # 每条线路的播放列表相同 (token是按集的, 不是按线路的)
                    play_url_str = "#".join(play_list)
                    vod["vod_play_url"] = "$$$".join([play_url_str] * len(line_names))
                else:
                    # 无线路信息, 用直链m3u8
                    vod["vod_play_from"] = "直链m3u8"
                    vod["vod_play_url"] = "#".join(play_list)

        # 兜底
        if "vod_play_from" not in vod:
            vod["vod_play_from"] = "白嫖者"
            vod["vod_play_url"] = "无播放源$$"

        return {"list": [vod]}

    def _get_line_names(self, token):
        """调用resolve端点获取可用线路名称列表 (按优先级排序)
        官方线路优先, 然后是直链m3u8资源
        """
        if not token:
            return []

        data = self._api_get("/v1/playback/resolve/" + token)
        lines = data.get("line_options", [])
        if not lines:
            return []

        # 按preference_weight降序排列
        lines_sorted = sorted(lines, key=lambda x: x.get("preference_weight", 0), reverse=True)

        # 筛选可用线路: 官方线路 + 直链m3u8
        result = []
        for line in lines_sorted:
            label = line.get("label", "") or line.get("display_label", "")
            if not label:
                continue
            # 去重 (同名的线路只保留一个)
            if label in result:
                continue
            result.append(label)

        # 限制线路数量 (太多影响体验), 保留前12条
        if len(result) > 12:
            result = result[:12]

        return result if result else ["直链m3u8"]

    # ===== 播放 =====

    def playerContent(self, flag, id, vipFlags):
        """播放: 根据flag(线路名)和id(token)解析真实播放地址
        1. 调用resolve获取该集的线路列表
        2. 匹配flag对应的线路
        3. 直链m3u8线路直接返回URL
        4. 官方线路需POST resolve-line获取真实URL
        5. 失败时回退到yjm3u8直链
        """
        token = id.strip()
        if not token:
            return {"parse": 0, "url": "", "header": ""}

        # 默认回退: yjm3u8直链
        fallback_url = self.zy_host + "/v1/playback/yjm3u8/" + token + ".m3u8"

        # 直链m3u8模式 (旧版兼容)
        if flag == "直链m3u8":
            return {"parse": 0, "url": fallback_url, "header": self._play_header, "jx": 0}

        # 调用resolve获取线路列表
        data = self._api_get("/v1/playback/resolve/" + token)
        lines = data.get("line_options", [])

        if not lines:
            # resolve失败, 回退到直链
            return {"parse": 0, "url": fallback_url, "header": self._play_header, "jx": 0}

        # 匹配flag对应的线路
        target_line = None
        for line in lines:
            label = line.get("label", "") or line.get("display_label", "")
            if label == flag:
                target_line = line
                break

        # 如果没找到匹配的线路, 取第一个available的
        if not target_line:
            for line in lines:
                label = line.get("label", "") or line.get("display_label", "")
                if label:
                    target_line = line
                    break

        if not target_line:
            return {"parse": 0, "url": fallback_url, "header": self._play_header, "jx": 0}

        # 情况1: 已解析的直链m3u8
        if target_line.get("resolved") and target_line.get("url_kind") == "m3u8":
            url = target_line.get("url", "")
            if url and self.isVideoFormat(url):
                return {"parse": 0, "url": url, "header": self._play_header, "jx": 0}

        # 情况2: 需要resolve的官方线路
        ticket = target_line.get("url", "")
        if ticket and ticket.startswith("resolve://"):
            resolved_url = self._resolve_line(ticket, token)
            if resolved_url:
                return {"parse": 0, "url": resolved_url, "header": self._play_header, "jx": 0}

        # 情况3: 其他已解析线路 (url_kind不是m3u8, 但有URL)
        url = target_line.get("url", "")
        if url and url.startswith("http"):
            return {"parse": 0, "url": url, "header": self._play_header, "jx": 0}

        # 所有解析失败, 回退到yjm3u8直链
        return {"parse": 0, "url": fallback_url, "header": self._play_header, "jx": 0}

    def _resolve_line(self, ticket, token):
        """POST resolve-line 获取官方线路真实播放地址 (带签名)"""
        result = self._api_post("/v1/playback/resolve-line", {
            "ticket": ticket,
            "token": token,
        })
        line = result.get("line", {})
        real_url = line.get("url", "")
        if real_url and real_url.startswith("http"):
            return real_url
        return None
