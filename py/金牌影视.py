# -*- coding: utf-8 -*-
# 金牌影视 - www.tjrongze.com
# by TRAE
import re
import json
import time
import sys
import hashlib
from base64 import b64encode, b64decode
from urllib.parse import quote, urlencode, urlparse

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def init(self, extend=""):
        self.host = "https://www.tjrongze.com"
        self.signKey = "cb808529bae6b6be45ecfab29a4889bc"
        self.deviceId = hashlib.md5(str(int(time.time())).encode()).hexdigest()
        self.ua = "okhttp/3.14.9"

    def getName(self):
        return "金牌影视"

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
            # 分类
            result["class"] = [
                {"type_name": "电影", "type_id": "1"},
                {"type_name": "电视剧", "type_id": "2"},
                {"type_name": "综艺", "type_id": "3"},
                {"type_name": "动漫", "type_id": "4"},
                {"type_name": "短剧", "type_id": "88"},
            ]
            result["filters"] = {
                "1": [
                    {"key": "type", "name": "类型", "value": [
                        {"n": "全部", "v": "0"}, {"n": "动作", "v": "动作"}, {"n": "喜剧", "v": "喜剧"},
                        {"n": "爱情", "v": "爱情"}, {"n": "科幻", "v": "科幻"}, {"n": "恐怖", "v": "恐怖"},
                        {"n": "剧情", "v": "剧情"}, {"n": "战争", "v": "战争"}, {"n": "犯罪", "v": "犯罪"},
                        {"n": "悬疑", "v": "悬疑"}, {"n": "奇幻", "v": "奇幻"},
                    ]},
                    {"key": "year", "name": "年份", "value": [
                        {"n": "全部", "v": "0"}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"},
                        {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"},
                    ]},
                    {"key": "area", "name": "地区", "value": [
                        {"n": "全部", "v": "0"}, {"n": "中国大陆", "v": "中国大陆"}, {"n": "中国香港", "v": "中国香港"},
                        {"n": "美国", "v": "美国"}, {"n": "韩国", "v": "韩国"}, {"n": "日本", "v": "日本"},
                    ]},
                    {"key": "sort", "name": "排序", "value": [
                        {"n": "最新", "v": "1"}, {"n": "最热", "v": "2"},
                    ]},
                ],
                "2": [
                    {"key": "type", "name": "类型", "value": [
                        {"n": "全部", "v": "0"}, {"n": "古装", "v": "古装"}, {"n": "爱情", "v": "爱情"},
                        {"n": "悬疑", "v": "悬疑"}, {"n": "剧情", "v": "剧情"}, {"n": "都市", "v": "都市"},
                        {"n": "喜剧", "v": "喜剧"},
                    ]},
                    {"key": "year", "name": "年份", "value": [
                        {"n": "全部", "v": "0"}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"},
                        {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"},
                    ]},
                    {"key": "area", "name": "地区", "value": [
                        {"n": "全部", "v": "0"}, {"n": "中国大陆", "v": "中国大陆"}, {"n": "中国香港", "v": "中国香港"},
                        {"n": "韩国", "v": "韩国"}, {"n": "美国", "v": "美国"}, {"n": "日本", "v": "日本"},
                    ]},
                    {"key": "sort", "name": "排序", "value": [
                        {"n": "最新", "v": "1"}, {"n": "最热", "v": "2"},
                    ]},
                ],
                "3": [
                    {"key": "sort", "name": "排序", "value": [
                        {"n": "最新", "v": "1"}, {"n": "最热", "v": "2"},
                    ]},
                ],
                "4": [
                    {"key": "type", "name": "类型", "value": [
                        {"n": "全部", "v": "0"}, {"n": "国产动漫", "v": "国产动漫"},
                        {"n": "日本动漫", "v": "日本动漫"}, {"n": "欧美动漫", "v": "欧美动漫"},
                    ]},
                    {"key": "sort", "name": "排序", "value": [
                        {"n": "最新", "v": "1"}, {"n": "最热", "v": "2"},
                    ]},
                ],
                "88": [
                    {"key": "sort", "name": "排序", "value": [
                        {"n": "最新", "v": "1"}, {"n": "最热", "v": "2"},
                    ]},
                ],
            }
            # 通过分类页HTML获取首页推荐（API返回空数据）
            html = self.fetch_html(f"{self.host}/vod/show/id/1")
            if html:
                data = self.parse_video_list_html(html)
                if data:
                    result["list"] = self.format_vod_list(data.get("list", []))
        except Exception as e:
            print(f'首页解析错误: {e}')
        return result

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": pg, "pagecount": 999, "limit": 90, "total": 999999}
        try:
            # 构建分类页URL路径
            path = f"/vod/show/id/{tid}"
            v_type = extend.get("type", "0")
            if v_type and v_type != "0":
                path += f"/class/{quote(v_type, safe='')}"
            v_year = extend.get("year", "0")
            if v_year and v_year != "0":
                path += f"/year/{quote(v_year, safe='')}"
            v_area = extend.get("area", "0")
            if v_area and v_area != "0":
                path += f"/area/{quote(v_area, safe='')}"
            v_sort = extend.get("sort", "1")
            if v_sort and v_sort != "1":
                path += f"/sort/{v_sort}"
            if int(pg) > 1:
                path += f"/page/{pg}"

            html = self.fetch_html(self.host + path)
            if html:
                data = self.parse_video_list_html(html)
                if data:
                    items = data.get("list", [])
                    result["list"] = self.format_vod_list(items)
                    result["pagecount"] = data.get("totalPage", 999)
                    result["total"] = data.get("totalCount", 999999)
        except Exception as e:
            print(f'分类解析错误: {e}')
        return result

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            # 优先通过API获取详情
            vod_data = None
            resp = self.api_get("/mw-movie/anonymous/video/detail", {"id": vod_id})
            if resp and resp.get("code") == 200:
                vod_data = resp["data"]

            if not vod_data:
                # 备用：从详情页HTML解析RSC数据
                try:
                    html = self.fetch_html(f"{self.host}/detail/{vod_id}")
                    vod_data = self.parse_detail_rsc(html)
                except Exception:
                    pass

            if vod_data:
                vod = {
                    "vod_id": str(vod_data.get("vodId", "")),
                    "vod_name": vod_data.get("vodName", ""),
                    "vod_pic": vod_data.get("vodPic", ""),
                    "vod_class": vod_data.get("vodClass", ""),
                    "vod_year": vod_data.get("vodYear", ""),
                    "vod_area": vod_data.get("vodArea", ""),
                    "vod_lang": vod_data.get("vodLang", ""),
                    "vod_remarks": vod_data.get("vodRemarks", ""),
                    "vod_actor": vod_data.get("vodActor", ""),
                    "vod_director": vod_data.get("vodDirector", ""),
                    "vod_content": self.clean_html(vod_data.get("vodContent", "")),
                    "vod_score": vod_data.get("vodScore", ""),
                }

                # 解析剧集列表
                episode_list = vod_data.get("episodeList", [])
                if episode_list:
                    play_names = []
                    play_urls = []
                    # 默认线路
                    names = ["默认"]
                    a = []
                    vod_id_str = str(vod_data.get("vodId", ""))
                    for ep in episode_list:
                        nid = ep.get("nid")
                        name = ep.get("name", "")
                        # 将vodId和nid一起编码，方便播放时使用
                        play_info = {"vodId": vod_id_str, "nid": str(nid)}
                        a.append(f"{name}${self.e64(json.dumps(play_info))}")
                    play_urls.append("#".join(a))
                    play_names.extend(names)

                    vod["vod_play_from"] = "$$$".join(play_names)
                    vod["vod_play_url"] = "$$$".join(play_urls)

                result["list"] = [vod]
        except Exception as e:
            print(f'详情解析错误: {e}')
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {"list": [], "page": pg}
        try:
            params = {
                "keyword": key,
                "pageNum": pg,
                "pageSize": 20,
            }
            data = self.api_get("/mw-movie/anonymous/video/searchByWord", params)
            if data and data.get("code") == 200:
                # 搜索结果在 data.result.list
                search_data = data.get("data", {})
                items = search_data.get("result", {}).get("list", [])
                if not items:
                    items = search_data.get("list", [])
                result["list"] = self.format_vod_list(items)
        except Exception as e:
            print(f'搜索错误: {e}')
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {}
        try:
            # id 是 base64 编码的 {"vodId": "xxx", "nid": "xxx"}
            play_info = json.loads(self.d64(id))
            vod_id = play_info["vodId"]
            nid = play_info["nid"]

            # 通过签名API获取播放地址
            data = self.api_get("/mw-movie/anonymous/v2/video/episode/url", {
                "clientType": 1,
                "id": vod_id,
                "nid": nid,
            })
            if data and data.get("code") == 200:
                # 播放地址在 data.list 数组中，包含多个清晰度
                url_list = data.get("data", {}).get("list", [])
                if url_list:
                    # 默认取第一个（最高清晰度）
                    play_url = url_list[0].get("url", "")
                    if play_url:
                        result["parse"] = 0
                        result["url"] = play_url
                        result["header"] = {
                            "User-Agent": "Mozilla/5.0 (Linux; Android 11; M2012K10C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                        }
                        return result

            # 备用方案：使用播放页直接解析
            url = f"{self.host}/vod/play/{vod_id}/sid/{nid}"
            result["parse"] = 1
            result["url"] = url
            result["header"] = {"User-Agent": self.ua}
        except Exception as e:
            print(f'播放解析错误: {e}')
            result["parse"] = 1
            result["url"] = ""
        return result

    def localProxy(self, param):
        return self.Mlocal(param)

    # ==================== 工具方法 ====================

    def fetch_html(self, url):
        """获取页面HTML内容"""
        try:
            resp = self.fetch(url, headers={
                "User-Agent": "Mozilla/5.0 (Linux; Android 11; M2012K10C Build/RP1A.200720.011) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            }, timeout=15)
            if resp:
                return resp.text
        except Exception as e:
            print(f'获取HTML失败: {e}')
        return ""

    def api_get(self, path, params=None):
        """调用需要签名的API
        签名算法: sha1(md5(param_str + key + t))
        时间戳: 毫秒
        """
        try:
            t = str(int(time.time() * 1000))
            sign_str = f"key={self.signKey}&t={t}"

            if params:
                sorted_params = sorted(params.items(), key=lambda x: x[0])
                param_part = "&".join(f"{k}={v}" for k, v in sorted_params if v)
                if param_part:
                    sign_str = f"{param_part}&{sign_str}"

            # sha1(md5(sign_str))
            md5_hex = hashlib.md5(sign_str.encode("utf-8")).hexdigest()
            sign = hashlib.sha1(md5_hex.encode("utf-8")).hexdigest()

            headers = {
                "User-Agent": self.ua,
                "sign": sign,
                "t": t,
                "deviceId": self.deviceId,
                "client-type": "3",
                "Referer": self.host,
            }

            full_url = f"{self.host}/api{path}"
            if params:
                full_url += "?" + urlencode(params)

            resp = self.fetch(full_url, headers=headers, timeout=10)
            if resp:
                return json.loads(resp.text)
        except Exception as e:
            print(f'API请求失败: {e}')
        return None

    def parse_video_list_html(self, html):
        """从分类/首页HTML解析videoList数据"""
        try:
            idx = html.find('videoList')
            if idx == -1:
                return None
            colon_idx = html.find(':', idx)
            start = html.find('{', colon_idx)
            if start == -1:
                return None

            depth = 0
            end = start
            in_str = False
            esc = False
            for i in range(start, len(html)):
                c = html[i]
                if esc:
                    esc = False
                    continue
                if c == '\\':
                    esc = True
                    continue
                if c == '"' and not esc:
                    in_str = not in_str
                    continue
                if not in_str:
                    if c == '{':
                        depth += 1
                    elif c == '}':
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break

            json_str = html[start:end]
            json_str = json_str.replace('\\"', '"').replace('\\\\', '\\')
            return json.loads(json_str)
        except Exception as e:
            print(f'videoList解析错误: {e}')
        return None

    def parse_detail_rsc(self, html):
        """从详情页HTML解析RSC数据"""
        try:
            idx = html.find("playListData")
            if idx == -1:
                idx = html.find('"vodId"')
            if idx == -1:
                return None

            start = html.rfind('{', 0, idx)
            depth = 0
            end = start
            for i in range(start, min(start + 20000, len(html))):
                if html[i] == '{':
                    depth += 1
                elif html[i] == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break

            json_str = html[start:end]
            json_str = json_str.replace('\\"', '"').replace('\\\\', '\\')
            prefix_idx = json_str.find('{')
            if prefix_idx > 0:
                json_str = json_str[prefix_idx:]

            data = json.loads(json_str)
            if data.get("data"):
                return data["data"]
        except Exception as e:
            print(f'RSC解析错误: {e}')
        return None

    def format_vod_list(self, items):
        """格式化视频列表为标准格式"""
        result = []
        for item in items:
            vod_id = item.get("vodId", "")
            vod_name = item.get("vodName", "")
            vod_pic = item.get("vodPic", "")
            vod_remarks = item.get("vodRemarks", "")
            # 如果 remarks 为空但有 total 和 serial，生成如 (5/24)
            if not vod_remarks:
                total = item.get("vodTotal", 0)
                serial = item.get("vodSerial", 0)
                if total and serial:
                    vod_remarks = f"({serial}/{total})"
                elif total:
                    vod_remarks = f"({total}集)"
            result.append({
                "vod_id": str(vod_id),
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_class": item.get("vodClass", ""),
                "vod_year": item.get("vodYear", ""),
                "vod_area": item.get("vodArea", ""),
                "vod_lang": item.get("vodLang", ""),
                "vod_remarks": vod_remarks,
                "vod_score": str(item.get("vodScore", "")),
            })
        return result

    def clean_html(self, text):
        """清理HTML标签"""
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&nbsp;', ' ').replace('\r\n', ' ').replace('\n', ' ')
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def Mlocal(self, param, header=None):
        url = self.d64(param["url"])
        ydata = self.fetch(url, headers=header, allow_redirects=False)
        data = ydata.content.decode('utf-8')
        if ydata.headers.get('Location'):
            url = ydata.headers['Location']
            data = self.fetch(url, headers=header).content.decode('utf-8')
        parsed_url = urlparse(url)
        durl = parsed_url.scheme + "://" + parsed_url.netloc
        lines = data.strip().split('\n')
        for index, string in enumerate(lines):
            if '#EXT' not in string and 'http' not in string:
                last_slash_index = string.rfind('/')
                lpath = string[:last_slash_index + 1]
                lines[index] = durl + ('' if lpath.startswith('/') else '/') + lpath
        data = '\n'.join(lines)
        return [200, "application/vnd.apple.mpegur", data]

    def e64(self, text):
        try:
            return b64encode(text.encode('utf-8')).decode('utf-8')
        except Exception:
            return ""

    def d64(self, encoded_text):
        try:
            return b64decode(encoded_text.encode('utf-8')).decode('utf-8')
        except Exception:
            return ""
