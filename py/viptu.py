#coding=utf-8
#!/usr/bin/python
# VIP兔 (viptu.com) - 聚合多CMS源影视站
# 原理: viptu.com 是Vue SPA, /api/web 返回加密配置(含CMS采集源列表)
#       解密后拿到多个苹果CMS API地址, 用标准CMS接口获取数据
#
# 核心策略:
#   - 分类浏览: 用无广2源(支持t参数过滤, 内容量大)
#   - 搜索: 同时搜索无广2和m3u8直链源(西瓜/非凡)
#   - 详情: 先获取片名, 再去m3u8直链源搜索同名内容获取播放URL
#   - 播放: m3u8直链 parse=0, 网页链接走解析接口 parse=1
#
# vod_id编码: s{源索引}_{原始id}  (URL安全格式)
import sys
import re
import json
import base64
import urllib.parse

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def getName(self):
        return "VIP兔影视"

    def init(self, extend=""):
        self.host = "https://viptu.com"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        self.cms_headers = {
            "User-Agent": self.ua,
            "Accept": "application/json, text/plain, */*",
        }
        # 只保留4个主分类
        self.cats = [
            {"type_name": "电影", "type_id": "1"},
            {"type_name": "剧集", "type_id": "2"},
            {"type_name": "综艺", "type_id": "3"},
            {"type_name": "动漫", "type_id": "4"},
        ]
        self._sources = []
        self._m3u8_sources = []  # m3u8直链源索引列表
        self._cat_source_idx = -1  # 分类浏览源索引 (-1=未设置)
        self._load_sources()

    def _load_sources(self):
        """从 viptu.com /api/web 获取加密配置, 解析CMS源列表
        同时解析 hot_db(首页分类源+分类) 和 short(短剧源+分类)"""
        try:
            html = self.fetch(self.host + "/api/web", headers=self.headers)
            text = html.text if hasattr(html, 'text') else str(html)
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="replace")
            text = text.strip().strip('"')
            decrypted = self._decrypt(text)
            config = json.loads(decrypted)
            data = config.get("data", {})
            search_api = data.get("search_api", "")
            self._sources = self._parse_sources(search_api)
            # 解析首页分类源 (hot_db: 第一行是API, 用于设置分类浏览源)
            self._parse_hot_db(data.get("hot_db", ""))
        except Exception:
            pass
        if not self._sources:
            self._sources = [
                {"name": "无广", "api": "https://tianwei.qzz.io/api.php/provide/vod/", "parse": []},
                {"name": "西瓜", "api": "https://caiji.xgzyapi.com/api.php/provide/vod/from/xiguam3u8/", "parse": []},
                {"name": "非凡", "api": "https://api.ffzyapi.com/api.php/provide/vod/from/ffm3u8/", "parse": []},
                {"name": "天堂", "api": "http://caiji.dyttzyapi.com/api.php/provide/vod/from/dyttm3u8/", "parse": []},
                {"name": "如意", "api": "https://cj.rycjapi.com/api.php/provide/vod/", "parse": []},
            ]
        # 识别m3u8直链源 (api中包含m3u8关键字 或 搜索结果URL含.m3u8)
        self._identify_sources()
        # 选择分类源: 优先用网站配置的hot_db源
        self._cat_source_idx = self._pick_cat_source()

    def _parse_hot_db(self, hot_db_str):
        """解析 hot_db: 只取第一行API设置分类浏览源, 分类列表固定为4个不覆盖"""
        if not hot_db_str:
            return
        lines = hot_db_str.strip().split("\n")
        api = lines[0].strip()
        # 找到对应的源索引
        for i, src in enumerate(self._sources):
            if src["api"].rstrip("/").lower() == api.rstrip("/").lower():
                self._cat_source_idx = i
                break

    def _identify_sources(self):
        """识别m3u8直链源: api URL中含m3u8标记的源"""
        self._m3u8_sources = []
        for i, src in enumerate(self._sources):
            api = src["api"].lower()
            # API中包含 m3u8 的通常是m3u8直链源
            if "m3u8" in api:
                self._m3u8_sources.append(i)
        # 如果没有识别到m3u8源, 把没有parse配置的源都当作m3u8源
        if not self._m3u8_sources:
            for i, src in enumerate(self._sources):
                if not src.get("parse"):
                    self._m3u8_sources.append(i)

    def _pick_cat_source(self):
        """选择分类浏览源: 优先用网站hot_db配置的源(qzz.io)"""
        # 如果 _parse_hot_db 已设置, 直接用
        if 0 <= self._cat_source_idx < len(self._sources):
            return self._cat_source_idx
        # 优先: qzz.io (网站首页源, 分类数据最全)
        preferred = ["qzz.io", "txnp.cn", "lzmhhh"]
        for domain in preferred:
            for i, src in enumerate(self._sources):
                if domain in src["api"]:
                    return i
        # 次选: 第一个m3u8源
        if self._m3u8_sources:
            return self._m3u8_sources[0]
        return 0

    def _decrypt(self, s):
        """解密 viptu.com 的 enc_ 格式"""
        try:
            parts = s.split("_")
            if len(parts) == 3 and parts[0] == "enc":
                b64 = parts[1]
                decoded = base64.b64decode(b64).decode("latin-1")
                result = ""
                for i in range(len(decoded)):
                    c = ord(decoded[i])
                    result += chr(c - i % 5)
                return urllib.parse.unquote(result)
            return urllib.parse.unquote(base64.b64decode(s).decode("utf-8"))
        except Exception:
            return ""

    def _parse_sources(self, search_api_str):
        """解析 search_api 字符串为源列表"""
        sources = []
        for line in search_api_str.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) < 2:
                continue
            name = parts[0].strip()
            api = parts[1].strip()
            if not api or not api.startswith("http"):
                continue
            parse_list = []
            if len(parts) > 6:
                parse_str = ",".join(parts[6:])
                for section in parse_str.split("|||"):
                    section = section.strip()
                    if not section:
                        continue
                    tokens = [t.strip() for t in section.split(",")]
                    i = 0
                    while i < len(tokens):
                        tok = tokens[i]
                        if tok.startswith("http"):
                            parse_list.append({"name": "解析", "url": tok})
                            i += 1
                        elif i + 1 < len(tokens) and tokens[i + 1].startswith("http"):
                            parse_list.append({"name": tok, "url": tokens[i + 1]})
                            i += 2
                        else:
                            i += 1
            sources.append({"name": name, "api": api, "parse": parse_list})
        return sources

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        if re.search(r'\.(m3u8|mp4|flv|ts|avi|mkv|mov|wmv)(\?|#|$)', url, re.I):
            return True
        return False

    def manualVideoCheck(self):
        pass

    def action(self, action):
        pass

    def destroy(self):
        pass

    # ==================== 工具 ====================
    def _cms_get(self, source, params):
        """请求CMS API, 返回JSON dict"""
        api = source["api"]
        url = api + "?" + urllib.parse.urlencode(params)
        try:
            r = self.fetch(url, headers=self.cms_headers)
            text = r.text if hasattr(r, 'text') else str(r)
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="replace")
            return json.loads(text)
        except Exception:
            return {}

    def _encode_id(self, vid, src_idx):
        return "s{}_{}".format(src_idx, vid)

    def _decode_id(self, encoded):
        raw = urllib.parse.unquote(str(encoded))
        m = re.match(r'^s(\d+)_(.+)$', raw)
        if m:
            return m.group(2), int(m.group(1))
        return raw, 0

    def _format_vod(self, v, src_idx):
        return {
            "vod_id": self._encode_id(str(v.get("vod_id", "")), src_idx),
            "vod_name": v.get("vod_name", ""),
            "vod_pic": v.get("vod_pic", ""),
            "vod_remarks": v.get("vod_remarks", "") or v.get("vod_class", ""),
        }

    def _get_source_by_name(self, name):
        for src in self._sources:
            if src["name"] == name:
                return src
        return None

    def _extract_play_section(self, vod_data):
        """从 vod_data 中提取播放段, 处理 $$$ 分隔的多线路格式
        返回 (play_from, play_url) 或 None
        优先返回含 m3u8 的线路, 其次返回第一个非空线路"""
        play_from = vod_data.get("vod_play_from", "") or "播放"
        play_url = vod_data.get("vod_play_url", "")
        if not play_url:
            return None
        # 按 $$$ 分隔多线路
        from_list = play_from.split("$$$")
        url_list = play_url.split("$$$")
        # 对齐长度
        while len(from_list) < len(url_list):
            from_list.append(from_list[-1] if from_list else "播放")
        # 找到第一个包含 m3u8 的线路
        for i, url_section in enumerate(url_list):
            if url_section and ".m3u8" in url_section.lower():
                return from_list[i], url_section
        # 没有 m3u8, 返回第一个非空段
        for i, url_section in enumerate(url_list):
            if url_section:
                return from_list[i], url_section
        return None

    def _find_m3u8_play(self, vod_name):
        """用片名在m3u8直链源搜索, 返回 (source, play_from, play_url) 或 None
        遍历所有m3u8源, 返回第一个含m3u8直链的结果"""
        if not vod_name or not self._m3u8_sources:
            return None
        for idx in self._m3u8_sources:
            src = self._sources[idx]
            try:
                data = self._cms_get(src, {"ac": "detail", "wd": vod_name})
            except Exception:
                continue
            for v in data.get("list", []):
                name = v.get("vod_name", "")
                # 精确匹配或包含匹配
                if name == vod_name or vod_name in name or name in vod_name:
                    section = self._extract_play_section(v)
                    if section and ".m3u8" in section[1].lower():
                        return src, section[0], section[1]
        return None

    # ==================== 分类 ====================
    def homeContent(self, filter):
        result = {}
        classes = []
        # 只保留4个主分类: 电影/剧集/综艺/动漫
        for c in self.cats:
            classes.append({"type_name": c["type_name"], "type_id": c["type_id"]})
        result["class"] = classes
        return result

    def homeVideoContent(self):
        """首页推荐 - 用分类源获取最新电影+剧集"""
        result = {"list": []}
        if not self._sources:
            return result
        src_idx = self._cat_source_idx
        src = self._sources[src_idx]
        for tid in ["1", "2"]:
            data = self._cms_get(src, {"ac": "detail", "t": tid, "pg": "1"})
            for v in data.get("list", [])[:10]:
                result["list"].append(self._format_vod(v, src_idx))
        return result

    def categoryContent(self, tid, pg, filter, extend):
        """分类页: 用分类源 CMS API ?ac=detail&t=type_id&pg=page"""
        result = {"list": [], "page": int(pg) if pg else 1, "pagecount": 1, "limit": 20, "total": 0}
        if not self._sources:
            return result
        src_idx = self._cat_source_idx
        src = self._sources[src_idx]
        data = self._cms_get(src, {"ac": "detail", "t": tid, "pg": str(pg)})
        for v in data.get("list", []):
            result["list"].append(self._format_vod(v, src_idx))
        result["pagecount"] = data.get("pagecount", 1) or 1
        result["total"] = data.get("total", 0) or 0
        return result

    # ==================== 详情 ====================
    def detailContent(self, ids):
        """详情: 获取视频信息, 然后去m3u8直链源搜索同名内容获取播放URL
        策略:
        1. 从原始源获取片名和信息
        2. 去m3u8直链源搜索同名内容
        3. 如果找到m3u8源, 用其播放URL (parse=0直链播放)
        4. 如果没找到, 用原始源的播放URL (可能需要解析)"""
        result = {"list": []}
        if not ids or not self._sources:
            return result
        vid, src_idx = self._decode_id(ids[0])
        if src_idx >= len(self._sources):
            src_idx = 0
        src = self._sources[src_idx]
        # 从原始源获取详情
        data = self._cms_get(src, {"ac": "detail", "ids": vid})
        lst = data.get("list", [])
        if not lst:
            data = self._cms_get(src, {"ac": "detail", "wd": vid, "pg": "1"})
            lst = data.get("list", [])
        if not lst:
            return result
        v = lst[0]
        vod_name = v.get("vod_name", "")
        vod = {
            "vod_id": ids[0],
            "vod_name": vod_name,
            "vod_pic": v.get("vod_pic", ""),
            "vod_year": v.get("vod_year", ""),
            "vod_area": v.get("vod_area", ""),
            "vod_actor": v.get("vod_actor", ""),
            "vod_director": v.get("vod_director", ""),
            "vod_remarks": v.get("vod_remarks", ""),
            "vod_content": re.sub(r'<[^>]+>', '', v.get("vod_content", "")).strip(),
        }
        # 先检查原始源是否已有m3u8直链 (搜索结果直接来自m3u8源的情况)
        section = self._extract_play_section(v)
        if section and ".m3u8" in section[1].lower():
            vod["vod_play_from"] = section[0]
            vod["vod_play_url"] = section[1]
            result["list"] = [vod]
            return result
        # 原始源无m3u8, 去其他m3u8直链源搜索同名内容
        m3u8_result = self._find_m3u8_play(vod_name)
        if m3u8_result:
            m3u8_src, play_from, play_url = m3u8_result
            vod["vod_play_from"] = play_from
            vod["vod_play_url"] = play_url
            result["list"] = [vod]
            return result
        # 没找到m3u8源, 尝试从原始源提取播放段 (可能含 $$$ 多线路)
        if section:
            vod["vod_play_from"] = section[0]
            vod["vod_play_url"] = section[1]
        result["list"] = [vod]
        return result

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        """搜索: 优先搜索m3u8直链源, 也搜索分类源"""
        result = {"list": [], "page": int(pg) if pg else 1, "pagecount": 1}
        if not key or not self._sources:
            return result
        seen = set()
        # 先搜索m3u8直链源 (播放更可靠)
        search_indices = list(self._m3u8_sources[:3])
        # 再加入分类源
        if self._cat_source_idx not in search_indices:
            search_indices.append(self._cat_source_idx)
        for i in search_indices:
            if i >= len(self._sources):
                continue
            src = self._sources[i]
            data = self._cms_get(src, {"ac": "detail", "wd": key, "pg": str(pg)})
            for v in data.get("list", []):
                name = v.get("vod_name", "")
                if not name or name in seen:
                    continue
                seen.add(name)
                result["list"].append({
                    "vod_id": self._encode_id(str(v.get("vod_id", "")), i),
                    "vod_name": name,
                    "vod_pic": v.get("vod_pic", ""),
                    "vod_remarks": v.get("vod_remarks", ""),
                })
        return result

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        """播放: m3u8/mp4直链 parse=0 + Referer, 网页链接走解析接口 parse=1"""
        play_url = urllib.parse.unquote(str(id))
        result = {
            "parse": 0,
            "url": play_url,
            "header": {
                "User-Agent": self.ua,
            },
        }
        is_direct = bool(re.search(r'\.(m3u8|mp4|flv|ts)(\?|#|$)', play_url, re.I))
        if is_direct:
            # m3u8/mp4直链, parse=0, 设置Referer为视频域名根
            parsed = urllib.parse.urlparse(play_url)
            result["header"]["Referer"] = "{}://{}/".format(parsed.scheme, parsed.netloc)
            result["parse"] = 0
            result["url"] = play_url
        else:
            # 网页链接(腾讯/爱奇艺/优酷等), 需要解析
            src = self._get_source_by_name(flag)
            if src and src.get("parse"):
                # 用源配置的解析接口
                result["url"] = src["parse"][0]["url"] + play_url
                result["parse"] = 1
            else:
                # 无解析接口, 交给TVBox嗅探
                result["parse"] = 1
                result["url"] = play_url
        return result