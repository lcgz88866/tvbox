#coding=utf-8
#!/usr/bin/python
# safilm69.com - Nuxt.js SSR + 加密API
# 列表/搜索通过SSR HTML中的__NUXT_DATA__提取数据
# 详情和播放通过加密API直接获取m3u8_url，parse=0直接播放
import sys
sys.path.append('..')
from base.spider import Spider
import json
import re
import gzip
import time
import uuid
import hmac
import hashlib
from urllib.parse import quote
from base64 import b64encode, b64decode

class Spider(Spider):

    def getName(self):
        return "SA视频"

    def init(self, extend=""):
        self.host = "https://safilm69.com"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.header = {
            "User-Agent": self.ua,
            "Referer": self.host + "/",
        }
        self.api_key = "x3t8rvtaescfe38s"

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

    # ==================== 加密API ====================
    def _gen_request_id(self):
        return str(uuid.uuid4())

    def _gen_key(self, request_id, key):
        hex_request_id = request_id.replace("-", "")
        hex_bytes = bytes.fromhex(hex_request_id)
        key_bytes = key.encode('utf-8')
        return hmac.new(key_bytes, hex_bytes, hashlib.sha256).digest()

    def _encrypt_data(self, data, request_id, key):
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import pad
            from Crypto.Random import get_random_bytes
            json_str = json.dumps(data, separators=(',', ':'))
            plaintext = gzip.compress(json_str.encode('utf-8'))
            aes_key = self._gen_key(request_id, key)
            iv = get_random_bytes(16)
            cipher = AES.new(aes_key, AES.MODE_CBC, iv)
            ciphertext = cipher.encrypt(pad(plaintext, AES.block_size))
            return b64encode(iv + ciphertext).decode('utf-8')
        except Exception as e:
            print("_encrypt_data error: {0}".format(e))
            return ""

    def _decrypt_data(self, encrypted, request_id, key):
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
            raw = b64decode(encrypted)
            iv = raw[:16]
            ciphertext = raw[16:]
            aes_key = self._gen_key(request_id, key)
            cipher = AES.new(aes_key, AES.MODE_CBC, iv)
            plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
            plaintext = gzip.decompress(plaintext)
            return json.loads(plaintext.decode('utf-8'))
        except Exception as e:
            print("_decrypt_data error: {0}".format(e))
            return None

    def _api_call(self, path, data=None):
        try:
            request_id = self._gen_request_id()
            timestamp = str(int(time.time() * 1000))[:11]
            body = {"data": data or {}, "token": "", "deviceId": "web_" + request_id[:8]}
            encrypted_body = self._encrypt_data(body, request_id, self.api_key)
            if not encrypted_body:
                return None
            headers = {
                "Content-Type": "application/json",
                "time": timestamp,
                "version": "1.0.0",
                "deviceType": "web",
                "requestId": request_id,
                "language": "zh-cn",
                "User-Agent": self.ua,
                "Referer": self.host + "/",
            }
            url = self.host + "/api" + path
            rsp = self.fetch(url, headers=headers, data=encrypted_body, method="POST")
            if rsp and rsp.text:
                return self._decrypt_data(rsp.text, request_id, self.api_key)
        except Exception as e:
            print("_api_call error: {0}".format(e))
        return None

    # ==================== NUXT Payload 解析 ====================
    def _extract_nuxt_payload(self, html):
        try:
            m = re.search(r'<script[^>]*id=["\']__NUXT_DATA__["\'][^>]*>(.*?)</script>', html, re.S)
            if not m:
                return None
            return json.loads(m.group(1))
        except Exception as e:
            print("_extract_nuxt_payload error: {0}".format(e))
            return None

    def _resolve_refs(self, payload, max_depth=25):
        if not isinstance(payload, list) or len(payload) == 0:
            return None

        def resolve(obj, visited=None, depth=0):
            if visited is None:
                visited = set()
            if depth > max_depth:
                return obj
            if isinstance(obj, int):
                if 0 <= obj < len(payload) and obj not in visited:
                    visited = visited | {obj}
                    return resolve(payload[obj], visited, depth + 1)
                return obj
            if isinstance(obj, list):
                if len(obj) >= 2 and isinstance(obj[0], str) and obj[0] in (
                    "ShallowReactive", "ShallowReadonly", "ShallowRef",
                    "Ref", "ComputedRef", "Reactive"
                ):
                    if len(obj) == 2 and isinstance(obj[1], int):
                        ref_idx = obj[1]
                        if 0 <= ref_idx < len(payload) and ref_idx not in visited:
                            visited = visited | {ref_idx}
                            return resolve(payload[ref_idx], visited, depth + 1)
                        return obj
                    return [resolve(x, visited, depth + 1) for x in obj]
                return [resolve(x, visited, depth + 1) for x in obj]
            if isinstance(obj, dict):
                return {k: resolve(v, visited, depth + 1) for k, v in obj.items()}
            return obj

        for root_idx in [1, 2, 3]:
            if root_idx < len(payload):
                resolved = resolve(payload[root_idx])
                if isinstance(resolved, dict) and "data" in resolved:
                    return resolved
        return None

    def _fetch_html(self, url):
        try:
            rsp = self.fetch(url, headers=self.header)
            return rsp.text
        except Exception as e:
            print("_fetch_html error: {0}".format(e))
            return ""

    def _strip_html(self, text):
        if not text:
            return ""
        return re.sub(r'<[^>]+>', '', text).strip()

    # ==================== 分类配置 ====================
    cats = [
        {"type_name": "电影", "type_id": "13"},
        {"type_name": "连续剧", "type_id": "12"},
        {"type_name": "综艺", "type_id": "11"},
        {"type_name": "动漫", "type_id": "14"},
        {"type_name": "短剧", "type_id": "16"},
        {"type_name": "纪录片", "type_id": "15"},
    ]

    # ==================== 首页 ====================
    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        try:
            result["class"] = self.cats

            if filter:
                result["filters"] = self._build_filters()

            html = self._fetch_html(self.host + "/")
            if html:
                payload = self._extract_nuxt_payload(html)
                if payload:
                    resolved = self._resolve_refs(payload)
                    if resolved:
                        data = resolved.get("data", {})
                        for k, v in data.items():
                            if "/movie/home" in k and isinstance(v, dict):
                                videos = []
                                home_recommends = v.get("home_recommends", [])
                                for section in home_recommends:
                                    items = section.get("items", [])
                                    for item in items:
                                        videos.append(self._parse_list_item(item))
                                seen = set()
                                unique = []
                                for v in videos:
                                    vid = v.get("vod_id", "")
                                    if vid and vid not in seen:
                                        seen.add(vid)
                                        unique.append(v)
                                result["list"] = unique[:30]
                                break
        except Exception as e:
            print("homeContent error: {0}".format(e))
        return result

    def homeVideoContent(self):
        pass

    # ==================== 筛选器 ====================
    _filter_key_map = {
        "tag": "tag_id",
        "area": "area",
        "lang": "language",
        "year": "year",
        "status": "update_status",
        "sort": "order",
    }

    def _build_filters(self):
        filters = {}
        try:
            html = self._fetch_html(self.host + "/movie/list/1?cat_id=13")
            if not html:
                return self._default_filters()

            payload = self._extract_nuxt_payload(html)
            if not payload:
                return self._default_filters()

            resolved = self._resolve_refs(payload)
            if not resolved:
                return self._default_filters()

            data = resolved.get("data", {})
            filter_data = None
            for k, v in data.items():
                if "/movie/filter" in k and isinstance(v, dict):
                    filter_data = v
                    break

            if not filter_data or not isinstance(filter_data, dict):
                return self._default_filters()

            category = filter_data.get("category", {})
            cat_items = category.get("items", [])

            area = filter_data.get("area", {})
            area_items = area.get("items", [])

            language = filter_data.get("language", {})
            lang_items = language.get("items", [])

            year = filter_data.get("year", {})
            year_items = year.get("items", [])

            series_status = filter_data.get("series_status", {})
            status_items = series_status.get("items", [])

            sort = filter_data.get("sort", {})
            sort_items = sort.get("items", [])

            for cat in self.cats:
                tid = cat["type_id"]
                filter_list = []

                tag_opts = [{"n": "全部标签", "v": ""}]
                for ci in cat_items:
                    if ci.get("value") == tid:
                        sub_filters = ci.get("filters", {})
                        sub_items = sub_filters.get("items", [])
                        for si in sub_items:
                            name = si.get("name", "")
                            val = si.get("value", "")
                            if name and val and "全部" not in name:
                                tag_opts.append({"n": name, "v": val})
                        break
                if len(tag_opts) > 1:
                    filter_list.append({"key": "tag", "name": "标签", "value": tag_opts})

                area_opts = [{"n": "全部地区", "v": ""}]
                for ai in area_items:
                    name = ai.get("name", "")
                    val = ai.get("value", "")
                    if name and val:
                        area_opts.append({"n": name, "v": val})
                if len(area_opts) > 1:
                    filter_list.append({"key": "area", "name": "地区", "value": area_opts})

                lang_opts = [{"n": "全部语言", "v": ""}]
                for li in lang_items:
                    name = li.get("name", "")
                    val = li.get("value", "")
                    if name and val:
                        lang_opts.append({"n": name, "v": val})
                if len(lang_opts) > 1:
                    filter_list.append({"key": "lang", "name": "语言", "value": lang_opts})

                year_opts = [{"n": "全部年份", "v": ""}]
                for yi in year_items:
                    name = yi.get("name", "")
                    val = yi.get("value", "")
                    if name and val:
                        year_opts.append({"n": name, "v": val})
                if len(year_opts) > 1:
                    filter_list.append({"key": "year", "name": "年份", "value": year_opts})

                status_opts = [{"n": "全部状态", "v": ""}]
                for si in status_items:
                    name = si.get("name", "")
                    val = si.get("value", "")
                    if name and val:
                        status_opts.append({"n": name, "v": val})
                if len(status_opts) > 1:
                    filter_list.append({"key": "status", "name": "状态", "value": status_opts})

                sort_opts = [{"n": "全部", "v": ""}]
                for si in sort_items:
                    name = si.get("name", "")
                    val = si.get("value", "")
                    if name and val and "全部" not in name:
                        sort_opts.append({"n": name, "v": val})
                if len(sort_opts) > 1:
                    filter_list.append({"key": "sort", "name": "排序", "value": sort_opts})

                filters[tid] = filter_list

        except Exception as e:
            print("_build_filters error: {0}".format(e))
            filters = self._default_filters()
        return filters

    def _default_filters(self):
        filters = {}
        for cat in self.cats:
            tid = cat["type_id"]
            filters[tid] = [
                {"key": "year", "name": "年份", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "今年", "v": "current"},
                    {"n": "去年", "v": "last"},
                    {"n": "更早", "v": "before"},
                ]},
                {"key": "sort", "name": "排序", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "上映时间", "v": "issue_date"},
                    {"n": "人气高低", "v": "hot"},
                    {"n": "评分高低", "v": "score"},
                ]},
            ]
        return filters

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
        try:
            page = int(pg) if int(pg) >= 1 else 1

            params = ["cat_id={0}".format(tid)]
            if extend:
                for k, v in extend.items():
                    if not v:
                        continue
                    field = self._filter_key_map.get(k, k)
                    params.append("{0}={1}".format(field, quote(v)))

            url = "{0}/movie/list/{1}?{2}".format(self.host, page, "&".join(params))
            html = self._fetch_html(url)
            if not html:
                return result

            payload = self._extract_nuxt_payload(html)
            if not payload:
                return result

            resolved = self._resolve_refs(payload)
            if not resolved:
                return result

            data = resolved.get("data", {})
            for k, v in data.items():
                if "/search/movie" in k and isinstance(v, dict):
                    total = v.get("total", 0)
                    last_page = v.get("last_page", 1)
                    items = v.get("data", [])
                    if isinstance(items, list):
                        for item in items:
                            result["list"].append(self._parse_list_item(item))
                    result["total"] = total
                    result["pagecount"] = last_page if last_page else 1
                    result["page"] = page
                    break

        except Exception as e:
            print("categoryContent error: {0}".format(e))
        return result

    def _parse_list_item(self, item):
        try:
            vod_id = str(item.get("id", ""))
            name = self._strip_html(str(item.get("name", "")))
            pic = item.get("img", "")
            remarks = item.get("duration", "") or item.get("show_at", "") or ""
            return {
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remarks,
            }
        except Exception as e:
            print("_parse_list_item error: {0}".format(e))
            return {}

    # ==================== 详情 ====================
    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]

            # 优先使用加密API获取详情（含m3u8_url）
            detail_data = self._api_call("/movie/detail", {"id": vod_id})
            if detail_data and detail_data.get("status") == "y":
                data = detail_data.get("data", {}).get("data", {})
                if data:
                    detail = self._parse_detail(data, vod_id)
                    if detail:
                        result["list"].append(detail)
                        return result

            # API失败时回退到SSR HTML
            detail_url = "{0}/movie/detail/{1}".format(self.host, vod_id)
            html = self._fetch_html(detail_url)
            if not html:
                return result

            payload = self._extract_nuxt_payload(html)
            if not payload:
                return result

            resolved = self._resolve_refs(payload)
            if not resolved:
                return result

            data = resolved.get("data", {})
            detail_data = None
            for k, v in data.items():
                if "/movie/detail" in k and isinstance(v, dict):
                    detail_data = v.get("data", {})
                    break

            if not detail_data:
                return result

            detail = self._parse_detail(detail_data, vod_id)
            if detail:
                result["list"].append(detail)

        except Exception as e:
            print("detailContent error: {0}".format(e))
        return result

    def _parse_detail(self, dd, vod_id):
        try:
            name = self._strip_html(str(dd.get("name", "")))
            pic = dd.get("img", "")
            score = str(dd.get("score", ""))
            desc = self._strip_html(str(dd.get("description", "")))

            if score and score != "0":
                desc = "{0}\n评分: {1}".format(desc, score)

            year = str(dd.get("issue_year", ""))
            director = dd.get("director", "") or ""
            actors = dd.get("actors", "") or ""
            update_status = dd.get("update_status_text", "") or ""

            category = dd.get("category", {})
            type_name = ""
            if isinstance(category, dict):
                type_name = category.get("name", "")

            play_links = dd.get("play_links", [])
            links = dd.get("links", [])

            # 构建播放源 - 所有线路共享同一组集数
            play_from_list = []
            play_url_list = []

            if play_links and links:
                pl = play_links[0]
                line_name = "SA视频"
                line_code = pl.get("code", "line1")
                movie_id = pl.get("id", vod_id)

                ep_items = []
                for link_group in links:
                    items = link_group.get("items", [])
                    for ep in items:
                        ep_name = ep.get("name", "")
                        ep_lid = ep.get("id", "")
                        if ep_name and ep_lid:
                            play_id = "{0}@@@{1}@@@{2}".format(movie_id, ep_lid, line_code)
                            ep_items.append("{0}${1}".format(ep_name, play_id))

                if ep_items:
                    play_from_list.append(line_name)
                    play_url_list.append("#".join(ep_items))

            return {
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "type_name": type_name,
                "vod_year": year,
                "vod_remarks": update_status,
                "vod_actor": actors,
                "vod_director": director,
                "vod_content": desc,
                "vod_play_from": "$$$".join(play_from_list),
                "vod_play_url": "$$$".join(play_url_list),
            }
        except Exception as e:
            print("_parse_detail error: {0}".format(e))
            return None

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            page = int(pg) if int(pg) >= 1 else 1
            url = "{0}/search?keywords={1}&page={2}".format(self.host, quote(key), page)
            html = self._fetch_html(url)
            if not html:
                return result

            payload = self._extract_nuxt_payload(html)
            if not payload:
                return result

            resolved = self._resolve_refs(payload)
            if not resolved:
                return result

            data = resolved.get("data", {})
            for k, v in data.items():
                if "/search/movie" in k and isinstance(v, dict):
                    items = v.get("data", [])
                    if isinstance(items, list):
                        for item in items:
                            result["list"].append(self._parse_list_item(item))
                    break
        except Exception as e:
            print("searchContent error: {0}".format(e))
        return result

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "playUrl": "", "jx": 0, "url": "", "header": ""}
        try:
            # 解析play_id格式: movie_id@@@ep_lid@@@line_code
            parts = id.split("@@@")
            if len(parts) < 3:
                return result

            movie_id = parts[0]
            ep_lid = parts[1]
            line_code = parts[2]

            # 通过加密API获取指定集数的m3u8_url
            detail_data = self._api_call("/movie/detail", {"id": movie_id, "lid": ep_lid})
            m3u8_url = ""

            if detail_data and detail_data.get("status") == "y":
                data = detail_data.get("data", {}).get("data", {})
                play_links = data.get("play_links", [])
                # 找到对应线路的m3u8_url
                for pl in play_links:
                    if pl.get("code") == line_code:
                        m3u8_url = pl.get("m3u8_url", "")
                        break
                # 如果没找到对应线路，取第一条
                if not m3u8_url and play_links:
                    m3u8_url = play_links[0].get("m3u8_url", "")

            if m3u8_url:
                # m3u8_url是相对路径，拼接完整URL
                if m3u8_url.startswith("/"):
                    play_url = self.host + m3u8_url
                else:
                    play_url = m3u8_url

                result["parse"] = 0
                result["url"] = play_url
                result["header"] = json.dumps({
                    "User-Agent": self.ua,
                    "Referer": self.host + "/",
                })
                return result

            # API失败时回退到WebView模式
            play_url = "{0}/movie/detail/{1}?lid={2}".format(self.host, movie_id, ep_lid)
            result["parse"] = 1
            result["jx"] = 0
            result["url"] = play_url
            result["header"] = json.dumps({
                "User-Agent": self.ua,
                "Referer": self.host + "/",
            })

        except Exception as e:
            print("playerContent error: {0}".format(e))
        return result

    # ==================== 配置 ====================
    config = {
        "player": {},
        "filter": {}
    }
    header = {}

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]
