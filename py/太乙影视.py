#coding=utf-8
#!/usr/bin/python
# 极我TV (gimy5.sbs) - 苹果CMS V10
# API: /api.php/provide/vod/
# 播放: 各大视频平台外链，需parse=1嗅探解析
# 解析: 虾米解析(jx.xmflv.com) - 网站播放页通过jx.jiexila.com套壳调用虾米解析
import sys
sys.path.append('..')
from base.spider import Spider
import json
import re
import time
from urllib.parse import quote


class Spider(Spider):

    def getName(self):
        return "极我TV"

    def init(self, extend=""):
        # 多域名（防屏蔽备用）
        self.hosts = [
            "https://tv.gimy5.sbs",
        ]
        # 支持用户通过extend传入自定义域名
        if extend:
            ext = extend.strip()
            if ext.startswith("http"):
                self.hosts.insert(0, ext.rstrip("/"))

        self.host = ""
        self.api_path = "/api.php/provide/vod/"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.header = {
            "User-Agent": self.ua,
        }

        # 选择可用域名
        self._select_host()

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

    # ==================== 域名选择 ====================
    def _select_host(self):
        """从域名列表中选择一个可用的域名"""
        if self.host:
            if self._try_api(self.host):
                return
            self.host = ""

        for h in self.hosts:
            h = h.rstrip("/")
            if self._try_api(h):
                self.host = h
                return

        if not self.host:
            self.host = self.hosts[0].rstrip("/")

    def _try_api(self, host):
        """测试域名是否可用"""
        try:
            url = "{0}{1}?ac=detail&pg=1".format(host, self.api_path)
            rsp = self.fetch(url, headers=self.header)
            if rsp.status_code == 200:
                d = rsp.json()
                if d.get("code") == 1:
                    return True
        except:
            pass
        return False

    def _api_get(self, params):
        """带域名容错的API请求"""
        url = "{0}{1}?{2}".format(self.host, self.api_path, params)
        try:
            rsp = self.fetch(url, headers=self.header)
            if rsp.status_code == 200:
                d = rsp.json()
                if d.get("code") == 1:
                    return d
        except:
            pass

        # 当前域名失败，尝试其他域名
        for h in self.hosts:
            h = h.rstrip("/")
            if h == self.host:
                continue
            url = "{0}{1}?{2}".format(h, self.api_path, params)
            try:
                rsp = self.fetch(url, headers=self.header)
                if rsp.status_code == 200:
                    d = rsp.json()
                    if d.get("code") == 1:
                        self.host = h
                        return d
            except:
                pass
        return None

    # ==================== 分类配置 ====================
    cats = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "剧集", "type_id": "2"},
        {"type_name": "综艺", "type_id": "3"},
        {"type_name": "动漫", "type_id": "4"},
    ]

    # 播放源名称映射（与网站playerconfig.js一致）
    _source_map = {
        "qq": "TX",
        "qiyi": "IQ",
        "youku": "YK",
        "mgtv": "MG",
        "bilibili": "BL",
    }

    def _build_filters(self):
        """构建筛选器"""
        filters = {}
        common = [
            {"key": "class", "name": "类型", "value": [
                {"n": "全部", "v": ""},
                {"n": "动作", "v": "动作"},
                {"n": "喜剧", "v": "喜剧"},
                {"n": "爱情", "v": "爱情"},
                {"n": "科幻", "v": "科幻"},
                {"n": "恐怖", "v": "恐怖"},
                {"n": "剧情", "v": "剧情"},
                {"n": "犯罪", "v": "犯罪"},
                {"n": "悬疑", "v": "悬疑"},
                {"n": "动画", "v": "动画"},
                {"n": "惊悚", "v": "惊悚"},
                {"n": "冒险", "v": "冒险"},
                {"n": "战争", "v": "战争"},
                {"n": "奇幻", "v": "奇幻"},
                {"n": "武侠", "v": "武侠"},
                {"n": "古装", "v": "古装"},
                {"n": "都市", "v": "都市"},
                {"n": "家庭", "v": "家庭"},
                {"n": "军旅", "v": "军旅"},
                {"n": "热血", "v": "热血"},
                {"n": "玄幻", "v": "玄幻"},
                {"n": "院线", "v": "院线"},
                {"n": "综艺", "v": "综艺"},
                {"n": "音乐", "v": "音乐"},
                {"n": "游戏", "v": "游戏"},
                {"n": "脱口秀", "v": "脱口秀"},
                {"n": "真人秀", "v": "真人秀"},
            ]},
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""},
                {"n": "中国大陆", "v": "中国大陆"},
                {"n": "中国香港", "v": "中国香港"},
                {"n": "中国台湾", "v": "中国台湾"},
                {"n": "美国", "v": "美国"},
                {"n": "日本", "v": "日本"},
                {"n": "韩国", "v": "韩国"},
                {"n": "英国", "v": "英国"},
                {"n": "法国", "v": "法国"},
                {"n": "其他", "v": "其他"},
            ]},
            {"key": "year", "name": "年份", "value": [
                {"n": "全部", "v": ""},
                {"n": "2026", "v": "2026"},
                {"n": "2025", "v": "2025"},
                {"n": "2024", "v": "2024"},
                {"n": "2023", "v": "2023"},
                {"n": "2022", "v": "2022"},
                {"n": "2021", "v": "2021"},
                {"n": "2020", "v": "2020"},
                {"n": "更早", "v": "2019"},
            ]},
            {"key": "by", "name": "排序", "value": [
                {"n": "最新", "v": "time"},
                {"n": "最热", "v": "hits"},
                {"n": "评分", "v": "score"},
            ]},
        ]
        for cat in self.cats:
            filters[cat["type_id"]] = common
        return filters

    # ==================== 首页 ====================
    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        try:
            result["class"] = self.cats
            if filter:
                result["filters"] = self._build_filters()

            d = self._api_get("ac=detail&pg=1")
            if d:
                result["list"] = self._parse_list(d)
        except Exception as e:
            print("homeContent error: {0}".format(e))
        return result

    def homeVideoContent(self):
        pass

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": []}
        try:
            page = int(pg) if pg else 1

            params = "ac=detail&pg={0}".format(page)
            if extend:
                cls = extend.get("class", "")
                if cls:
                    params += "&class={0}".format(quote(cls))
                area = extend.get("area", "")
                if area:
                    params += "&area={0}".format(quote(area))
                year = extend.get("year", "")
                if year:
                    params += "&year={0}".format(quote(year))
                by = extend.get("by", "")
                if by:
                    params += "&by={0}".format(by)

            url_params = "{0}&t={1}".format(params, tid)

            d = self._api_get(url_params)
            if d:
                result["list"] = self._parse_list(d)
                result["page"] = page
                result["pagecount"] = int(d.get("pagecount", 1))
                result["limit"] = int(d.get("limit", 20))
                result["total"] = int(d.get("total", 0))
            else:
                result["page"] = page
                result["pagecount"] = 1
                result["limit"] = 20
                result["total"] = 0
        except Exception as e:
            print("categoryContent error: {0}".format(e))
            result["page"] = int(pg) if pg else 1
            result["pagecount"] = 1
            result["limit"] = 20
            result["total"] = 0
        return result

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg) if pg else 1
            keyword = quote(key)
            params = "ac=detail&wd={0}&pg={1}".format(keyword, page)

            d = self._api_get(params)
            if d:
                return {"list": self._parse_list(d)}
        except Exception as e:
            print("searchContent error: {0}".format(e))
        return {"list": []}

    # ==================== 详情 ====================
    def detailContent(self, ids):
        try:
            vod_id = ids[0]
            params = "ac=detail&ids={0}".format(vod_id)

            d = self._api_get(params)
            if d and d.get("list"):
                vod = self._parse_detail(d["list"][0])
                return {"list": [vod]}
        except Exception as e:
            print("detailContent error: {0}".format(e))
        return {"list": []}

    # ==================== 播放 ====================
    # 网站播放页通过 jx.jiexila.com 套壳调用虾米解析(jx.xmflv.com)
    # 虾米解析通过JS渲染获取m3u8，TVBox需用parse=1嗅探模式
    # 直接用虾米解析URL，跳过jx.jiexila.com中间层（减少一层跳转，更稳定）
    # id中用~分隔: vod_id~sid~nid~video_url

    # 第三方解析接口(嗅探模式,parse=1)
    _parse_api = "https://jx.xmflv.com/?url="

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "playUrl": "", "jx": 0, "url": "", "header": ""}
        try:
            # id格式: vod_id~sid~nid~video_url
            parts = id.split("~")
            if len(parts) < 4:
                # 兜底：id不完整时回退到网站播放页嗅探
                if len(parts) >= 3:
                    play_url = "{0}/index.php/vod/play/id/{1}/sid/{2}/nid/{3}.html".format(
                        self.host, parts[0], parts[1], parts[2])
                    result["parse"] = 1
                    result["url"] = play_url
                    result["header"] = {
                        "User-Agent": self.ua,
                        "Referer": self.host + "/",
                    }
                return result

            video_url = parts[3]

            # 用虾米解析嗅探m3u8(parse=1, TVBox自动嗅探页面中的m3u8)
            parse_url = self._parse_api + quote(video_url)
            result["parse"] = 1
            result["url"] = parse_url
            result["header"] = {
                "User-Agent": self.ua,
                "Referer": "https://jx.xmflv.com/",
            }

        except Exception as e:
            print("playerContent error: {0}".format(e))

        return result

    # ==================== 数据解析 ====================
    def _parse_list(self, data):
        """解析列表数据"""
        videos = []
        try:
            items = data.get("list", [])
            for item in items:
                vod_pic = item.get("vod_pic", "")
                if vod_pic and not vod_pic.startswith("http"):
                    vod_pic = self.host + vod_pic

                videos.append({
                    "vod_id": str(item.get("vod_id", "")),
                    "vod_name": item.get("vod_name", ""),
                    "vod_pic": vod_pic,
                    "vod_remarks": item.get("vod_remarks", ""),
                })
        except Exception as e:
            print("_parse_list error: {0}".format(e))
        return videos

    def _parse_detail(self, item):
        """解析详情数据"""
        try:
            vod_id = str(item.get("vod_id", ""))
            vod_pic = item.get("vod_pic", "")
            if vod_pic and not vod_pic.startswith("http"):
                vod_pic = self.host + vod_pic

            vod_name = item.get("vod_name", "")
            vod_content = item.get("vod_content", "") or item.get("vod_blurb", "")
            if vod_content:
                vod_content = re.sub(r'<[^>]+>', '', vod_content).strip()

            # 播放源解析
            play_from = item.get("vod_play_from", "")
            play_url = item.get("vod_play_url", "")

            play_from_list = play_from.split("$$$") if play_from else []
            play_url_list = play_url.split("$$$") if play_url else []

            final_from = []
            final_url = []

            for i, source_id in enumerate(play_from_list):
                source_id = source_id.strip()
                if not source_id:
                    continue

                sid = i + 1

                # 播放源名称
                source_name = self._source_map.get(source_id, source_id)

                if i < len(play_url_list):
                    url_str = play_url_list[i]
                    if not url_str:
                        continue

                    # 解析每集: 集名$URL#集名$URL
                    episodes = url_str.split("#")
                    ep_urls = []
                    for j, ep in enumerate(episodes):
                        ep = ep.strip()
                        if not ep:
                            continue
                        nid = j + 1
                        if "$" in ep:
                            parts = ep.split("$", 1)
                            ep_name = parts[0].strip()
                            ep_url = parts[1].strip() if len(parts) > 1 else ""
                        else:
                            ep_name = ep
                            ep_url = ep

                        if ep_url:
                            # id格式: vod_id~sid~nid~video_url
                            ep_urls.append("{0}${1}~{2}~{3}~{4}".format(ep_name, vod_id, sid, nid, ep_url))

                    if ep_urls:
                        final_from.append(source_name)
                        final_url.append("#".join(ep_urls))

            vod = {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "type_name": item.get("type_name", ""),
                "vod_year": item.get("vod_year", ""),
                "vod_area": item.get("vod_area", ""),
                "vod_remarks": item.get("vod_remarks", ""),
                "vod_actor": item.get("vod_actor", ""),
                "vod_director": item.get("vod_director", ""),
                "vod_content": vod_content,
                "vod_lang": item.get("vod_lang", ""),
                "vod_score": item.get("vod_score", ""),
                "vod_play_from": "$$$".join(final_from) if final_from else "极我播放",
                "vod_play_url": "$$$".join(final_url) if final_url else "",
            }

            return vod
        except Exception as e:
            print("_parse_detail error: {0}".format(e))
            return {}