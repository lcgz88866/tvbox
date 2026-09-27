#coding=utf-8
#!/usr/bin/python
# 电影天堂 - 苹果CMS V10采集站接口
# API: http://caiji.dyttzyapi.com/api.php/provide/vod
# 播放地址直接为m3u8，可直接播放(parse=0)
import sys
sys.path.append('..')
from base.spider import Spider
import json
from urllib.parse import quote

class Spider(Spider):

    def getName(self):
        return "电影天堂"

    def init(self, extend=""):
        self.host = "http://caiji.dyttzyapi.com"
        self.api = self.host + "/api.php/provide/vod"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.header = {
            "User-Agent": self.ua,
        }

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

    def _fetch_json(self, url):
        """获取JSON数据"""
        try:
            rsp = self.fetch(url, headers=self.header)
            return json.loads(rsp.text)
        except Exception as e:
            print("_fetch_json error: {0}".format(e))
            return {}

    # ==================== 分类配置 ====================
    cats = [
        {"type_name": "动作片", "type_id": "6"},
        {"type_name": "喜剧片", "type_id": "7"},
        {"type_name": "爱情片", "type_id": "8"},
        {"type_name": "科幻片", "type_id": "9"},
        {"type_name": "恐怖片", "type_id": "10"},
        {"type_name": "剧情片", "type_id": "11"},
        {"type_name": "战争片", "type_id": "12"},

        {"type_name": "国产剧", "type_id": "13"},
        {"type_name": "香港剧", "type_id": "14"},
        {"type_name": "韩国剧", "type_id": "15"},
        {"type_name": "欧美剧", "type_id": "16"},
        {"type_name": "日本剧", "type_id": "22"},
        {"type_name": "台湾剧", "type_id": "21"},
        {"type_name": "泰国剧", "type_id": "24"},
        {"type_name": "海外剧", "type_id": "23"},
        {"type_name": "大陆综艺", "type_id": "25"},
        {"type_name": "港台综艺", "type_id": "26"},
        {"type_name": "日韩综艺", "type_id": "27"},
        {"type_name": "欧美综艺", "type_id": "28"},
        {"type_name": "国产动漫", "type_id": "29"},
        {"type_name": "日韩动漫", "type_id": "30"},
        {"type_name": "欧美动漫", "type_id": "31"},
        {"type_name": "港台动漫", "type_id": "32"},
        {"type_name": "动画片", "type_id": "37"},
        {"type_name": "记录片", "type_id": "20"},
                {"type_name": "伦理片", "type_id": "34"},
        {"type_name": "短剧", "type_id": "36"},
    ]

    # ==================== 筛选器 ====================
    # extend key -> API参数名 的映射
    _filter_key_map = {
        "class": "class",
        "area": "area",
        "year": "year",
        "by": "by",
    }

    def _build_filters(self):
        """构建筛选器"""
        filters = {}
        # 通用筛选器，所有分类共用
        common_filter = [
            {"key": "class", "name": "类型", "value": [
                {"n": "全部", "v": ""},
                {"n": "剧情", "v": "剧情"},
                {"n": "动作", "v": "动作"},
                {"n": "喜剧", "v": "喜剧"},
                {"n": "爱情", "v": "爱情"},
                {"n": "科幻", "v": "科幻"},
                {"n": "恐怖", "v": "恐怖"},
                {"n": "悬疑", "v": "悬疑"},
                {"n": "惊悚", "v": "惊悚"},
                {"n": "战争", "v": "战争"},
                {"n": "犯罪", "v": "犯罪"},
                {"n": "奇幻", "v": "奇幻"},
                {"n": "冒险", "v": "冒险"},
                {"n": "古装", "v": "古装"},
                {"n": "历史", "v": "历史"},
                {"n": "武侠", "v": "武侠"},
                {"n": "青春", "v": "青春"},
                {"n": "家庭", "v": "家庭"},
                {"n": "动画", "v": "动画"},
                {"n": "国产", "v": "国产"},
                {"n": "日韩", "v": "日韩"},
                {"n": "欧美", "v": "欧美"},
                {"n": "港台", "v": "港台"},
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
                {"n": "德国", "v": "德国"},
                {"n": "泰国", "v": "泰国"},
                {"n": "印度", "v": "印度"},
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
                {"n": "2019", "v": "2019"},
                {"n": "2018", "v": "2018"},
                {"n": "2017", "v": "2017"},
                {"n": "2016", "v": "2016"},
                {"n": "2015", "v": "2015"},
                {"n": "更早", "v": "2014"},
            ]},
            {"key": "by", "name": "排序", "value": [
                {"n": "最新", "v": "time"},
                {"n": "最热", "v": "hits"},
                {"n": "评分", "v": "score"},
            ]},
        ]
        for cat in self.cats:
            filters[cat["type_id"]] = common_filter
        return filters

    # ==================== 首页 ====================
    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        try:
            result["class"] = self.cats
            if filter:
                result["filters"] = self._build_filters()

            # 首页推荐: 获取最新20条
            url = "{0}/?ac=detail&pg=1".format(self.api)
            data = self._fetch_json(url)
            if data.get("list"):
                for item in data["list"]:
                    result["list"].append(self._parse_list_item(item))
        except Exception as e:
            print("homeContent error: {0}".format(e))
        return result

    def homeVideoContent(self):
        pass

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 20, "total": 0}
        try:
            page = int(pg) if int(pg) >= 1 else 1

            # 构建URL参数
            params = ["ac=detail", "t={0}".format(tid), "pg={0}".format(page)]
            if extend:
                for k, v in extend.items():
                    if not v:
                        continue
                    field = self._filter_key_map.get(k, k)
                    # 对中文等特殊字符进行URL编码
                    params.append("{0}={1}".format(field, quote(str(v))))

            url = "{0}/?{1}".format(self.api, "&".join(params))
            data = self._fetch_json(url)
            if data.get("list"):
                for item in data["list"]:
                    result["list"].append(self._parse_list_item(item))
            result["total"] = data.get("total", 0)
            result["pagecount"] = data.get("pagecount", 1)
            result["page"] = page
        except Exception as e:
            print("categoryContent error: {0}".format(e))
        return result

    def _parse_list_item(self, item):
        """解析列表项为TVBox格式"""
        return {
            "vod_id": str(item.get("vod_id", "")),
            "vod_name": item.get("vod_name", ""),
            "vod_pic": item.get("vod_pic", ""),
            "vod_remarks": item.get("vod_remarks", ""),
        }

    # ==================== 详情 ====================
    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            url = "{0}/?ac=detail&ids={1}".format(self.api, vod_id)
            data = self._fetch_json(url)
            if data.get("list"):
                item = data["list"][0]
                detail = self._parse_detail(item)
                if detail:
                    result["list"].append(detail)
        except Exception as e:
            print("detailContent error: {0}".format(e))
        return result

    def _parse_detail(self, item):
        """解析详情数据为TVBox格式"""
        try:
            vod_id = str(item.get("vod_id", ""))
            name = item.get("vod_name", "")
            pic = item.get("vod_pic", "")
            type_name = item.get("type_name", "")
            year = str(item.get("vod_year", ""))
            area = item.get("vod_area", "")
            lang = item.get("vod_lang", "")
            director = item.get("vod_director", "") or ""
            actor = item.get("vod_actor", "") or ""
            remarks = item.get("vod_remarks", "") or ""
            content = item.get("vod_content", "") or ""
            score = item.get("vod_score", "")
            blurb = item.get("vod_blurb", "") or ""

            # 简介: 优先用content，没有则用blurb
            desc = content if content else blurb
            if score and score != "0.0" and score != "0":
                desc = "{0}\n评分: {1}".format(desc, score)

            # 播放源
            play_from = item.get("vod_play_from", "")
            play_url = item.get("vod_play_url", "")

            # vod_play_from格式: dytt$$$dyttm3u8
            # vod_play_url格式: 第01集$url1#第02集$url2$$$第01集$url1#第02集$url2
            play_from_list = []
            play_url_list = []

            if play_from and play_url:
                from_list = play_from.split("$$$")
                url_list = play_url.split("$$$")
                for i, pf in enumerate(from_list):
                    if i < len(url_list):
                        play_from_list.append(pf)
                        play_url_list.append(url_list[i])

            return {
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "type_name": type_name,
                "vod_year": year,
                "vod_area": area,
                "vod_remarks": remarks,
                "vod_actor": actor,
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
            # 必须带ac=detail参数，否则返回验证页面
            url = "{0}/?ac=detail&wd={1}&pg={2}".format(self.api, quote(key), page)
            data = self._fetch_json(url)
            if data.get("list"):
                for item in data["list"]:
                    result["list"].append(self._parse_list_item(item))
        except Exception as e:
            print("searchContent error: {0}".format(e))
        return result

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "playUrl": "", "jx": 0, "url": "", "header": ""}
        try:
            # id就是直接的视频URL(m3u8或分享链接)
            play_url = id

            # 判断是否是m3u8直链
            if ".m3u8" in play_url:
                result["parse"] = 0
            else:
                # 非m3u8链接(分享页)，需要解析
                result["parse"] = 1

            result["url"] = play_url
            result["header"] = json.dumps({
                "User-Agent": self.ua,
            })
            return result
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