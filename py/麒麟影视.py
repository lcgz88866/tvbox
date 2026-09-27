# -*- coding: utf-8 -*-
# 麒麟影视 (www.qlys.cc) TVBox Python Spider
# 苹果CMS V10 + 标准API接口
# 24个分类, 多播放源(xiguam3u8/dyttm3u8), 筛选支持

import re
import sys
import json
import ssl
import urllib.parse
import urllib.request

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


class Spider(Spider):

    HOST = "https://www.qlys.cc"
    UA = "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # 主分类
    CATEGORIES = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "电视剧", "type_id": "2"},
        {"type_name": "短剧", "type_id": "3"},
        {"type_name": "动漫", "type_id": "4"},
        {"type_name": "综艺", "type_id": "5"},

    ]

    # 二级分类
    SUB_CATS = {
        "1": [
            {"n": "全部", "v": ""},
            {"n": "动作片", "v": "10"},
            {"n": "喜剧片", "v": "15"},
            {"n": "爱情片", "v": "14"},
            {"n": "科幻片", "v": "12"},
            {"n": "恐怖片", "v": "11"},
            {"n": "剧情片", "v": "16"},
            {"n": "战争片", "v": "13"},
            {"n": "记录片", "v": "17"},
        ],
        "2": [
            {"n": "全部", "v": ""},
            {"n": "内地剧", "v": "6"},
            {"n": "港台剧", "v": "7"},
            {"n": "日韩剧", "v": "8"},
            {"n": "欧美剧", "v": "9"},
            {"n": "泰剧", "v": "22"},
        ],
        "4": [
            {"n": "全部", "v": ""},
            {"n": "内地番", "v": "18"},
            {"n": "日韩番", "v": "19"},
            {"n": "港台番", "v": "20"},
            {"n": "欧美番", "v": "21"},
        ],
    }

    # 通用筛选
    COMMON_FILTERS = [
        {
            "key": "area",
            "name": "地区",
            "value": [
                {"n": "全部", "v": ""},
                {"n": "中国大陆", "v": "中国大陆"},
                {"n": "中国香港", "v": "中国香港"},
                {"n": "中国台湾", "v": "中国台湾"},
                {"n": "美国", "v": "美国"},
                {"n": "韩国", "v": "韩国"},
                {"n": "日本", "v": "日本"},
                {"n": "法国", "v": "法国"},
                {"n": "英国", "v": "英国"},
                {"n": "德国", "v": "德国"},
                {"n": "泰国", "v": "泰国"},
                {"n": "印度", "v": "印度"},
                {"n": "其他", "v": "其他"},
            ],
        },
        {
            "key": "year",
            "name": "年份",
            "value": [
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
                {"n": "2016-2010", "v": "2010-2016"},
                {"n": "2009-2000", "v": "2000-2009"},
                {"n": "90年代", "v": "1990-1999"},
            ],
        },
        {
            "key": "lang",
            "name": "语言",
            "value": [
                {"n": "全部", "v": ""},
                {"n": "国语", "v": "国语"},
                {"n": "英语", "v": "英语"},
                {"n": "粤语", "v": "粤语"},
                {"n": "韩语", "v": "韩语"},
                {"n": "日语", "v": "日语"},
                {"n": "其他", "v": "其他"},
            ],
        },
        {
            "key": "by",
            "name": "排序",
            "value": [
                {"n": "最新", "v": "time"},
                {"n": "最热", "v": "hits"},
                {"n": "评分", "v": "score"},
            ],
        },
    ]

    def getName(self):
        return "麒麟影视"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": self.UA,
            "Referer": self.HOST,
        }
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|ts)(\?|#|$)', url, re.I))

    def manualVideoVCandidate(self, items):
        return []

    # ===== HTTP =====

    def _fetch(self, url, timeout=10):
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=timeout) as resp:
                return json.loads(resp.read().decode('utf-8', errors='ignore'))
        except Exception:
            return None

    # ===== 首页 =====

    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        result["class"] = self.CATEGORIES

        for cat in self.CATEGORIES:
            tid = cat["type_id"]
            filters = []
            # 类型筛选 (仅有一级分类的才加)
            if tid in self.SUB_CATS:
                filters.append({
                    "key": "cateId",
                    "name": "类型",
                    "value": self.SUB_CATS[tid],
                })
            filters.extend(self.COMMON_FILTERS)
            result["filters"][tid] = filters

        return result

    def homeVideoContent(self):
        result = {"list": []}
        data = self._fetch(f"{self.HOST}/api.php/provide/vod/?ac=detail&pg=1")
        if data and data.get("code") == 1:
            for item in data.get("list", [])[:20]:
                result["list"].append(self._item_to_vod(item))
        return result

    # ===== 分类 =====

    # 一级分类ID (父分类, ac=detail返回空, 需用ajax/data)
    PARENT_CATS = {"1", "2", "3", "4", "5"}

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        try:
            extend = extend or {}
            if isinstance(extend, str):
                extend = json.loads(extend)

            cate_id = extend.get("cateId", "") or tid
            area = extend.get("area", "")
            year = extend.get("year", "")
            lang = extend.get("lang", "")
            by = extend.get("by", "")
            page = int(pg) if pg and int(pg) >= 1 else 1

            # 父分类用ajax/data (ac=detail对父分类返回空)
            # 子分类用ac=detail (支持area/year/lang/by筛选)
            if cate_id in self.PARENT_CATS and not area and not year and not lang and not by:
                url = f"{self.HOST}/index.php/ajax/data?mid=1&tid={cate_id}&page={page}&limit=20"
            else:
                url = f"{self.HOST}/api.php/provide/vod/?ac=detail&t={cate_id}&pg={page}"
                if area:
                    url += f"&area={urllib.parse.quote(area)}"
                if year:
                    url += f"&year={urllib.parse.quote(year)}"
                if lang:
                    url += f"&lang={urllib.parse.quote(lang)}"
                if by:
                    url += f"&by={by}"

            data = self._fetch(url)
            if data and data.get("code") == 1:
                result["page"] = int(data.get("page", page))
                result["pagecount"] = int(data.get("pagecount", 1))
                result["limit"] = int(data.get("limit", 20))
                result["total"] = int(data.get("total", 0))
                for item in data.get("list", []):
                    result["list"].append(self._item_to_vod(item))
        except Exception:
            pass
        return result

    # ===== 详情 =====

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            data = self._fetch(f"{self.HOST}/api.php/provide/vod/?ac=detail&ids={vod_id}")
            if not data or data.get("code") != 1:
                return result

            items = data.get("list", [])
            if not items:
                return result

            item = items[0]
            vod = {
                "vod_id": str(item.get("vod_id", "")),
                "vod_name": item.get("vod_name", ""),
                "vod_pic": item.get("vod_pic", "").replace("\\/", "/"),
                "vod_actor": item.get("vod_actor", ""),
                "vod_director": item.get("vod_director", ""),
                "vod_year": item.get("vod_year", ""),
                "vod_area": item.get("vod_area", ""),
                "vod_lang": item.get("vod_lang", ""),
                "vod_remarks": item.get("vod_remarks", ""),
                "vod_content": self._clean_html(item.get("vod_content", "")),
                "type_name": item.get("type_name", ""),
                "vod_play_from": item.get("vod_play_from", ""),
                "vod_play_url": item.get("vod_play_url", ""),
            }
            result["list"].append(vod)
        except Exception:
            pass
        return result

    # ===== 搜索 =====

    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            wd = urllib.parse.quote(key)
            page = int(pg) if pg and int(pg) >= 1 else 1
            url = f"{self.HOST}/api.php/provide/vod/?ac=detail&wd={wd}&pg={page}"
            data = self._fetch(url)
            if data and data.get("code") == 1:
                for item in data.get("list", []):
                    result["list"].append({
                        "vod_id": str(item["vod_id"]),
                        "vod_name": item.get("vod_name", ""),
                        "vod_pic": item.get("vod_pic", "").replace("\\/", "/"),
                        "vod_remarks": item.get("vod_remarks", ""),
                        "type_name": item.get("type_name", ""),
                    })
        except Exception:
            pass
        return result

    # ===== 播放 =====

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "header": "", "url": "", "playUrl": ""}
        try:
            if "$" in id:
                play_url = id.split("$")[-1]
            else:
                play_url = id
            play_url = play_url.replace("\\/", "/")

            if ".m3u8" in play_url or ".mp4" in play_url:
                result["url"] = play_url
                result["parse"] = 0
            elif play_url.startswith("http"):
                result["url"] = play_url
                result["parse"] = 1
            else:
                result["url"] = play_url
                result["parse"] = 0
        except Exception:
            pass
        return result

    # ===== 工具 =====

    def _item_to_vod(self, item):
        return {
            "vod_id": str(item.get("vod_id", "")),
            "vod_name": item.get("vod_name", ""),
            "vod_pic": item.get("vod_pic", "").replace("\\/", "/"),
            "vod_remarks": item.get("vod_remarks", ""),
        }

    def _clean_html(self, text):
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        return text.strip()


if __name__ == "__main__":
    import time

    s = Spider()
    s.init()

    print("===== 首页分类 =====")
    home = s.homeContent(True)
    print(f"分类数: {len(home['class'])}")
    for c in home["class"]:
        print(f"  {c['type_name']} -> {c['type_id']}")

    print("\n===== 首页推荐 =====")
    t0 = time.time()
    rec = s.homeVideoContent()
    t1 = time.time()
    print(f"耗时: {t1-t0:.2f}s, 返回: {len(rec['list'])}条")
    for v in rec["list"][:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 分类列表 (电影第1页) =====")
    t0 = time.time()
    cat = s.categoryContent("1", "1", True, {})
    t1 = time.time()
    print(f"耗时: {t1-t0:.2f}s, 返回: {len(cat['list'])}条, 总页数: {cat['pagecount']}")
    for v in cat["list"][:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 分类列表 (电影-动作片) =====")
    t0 = time.time()
    cat2 = s.categoryContent("1", "1", True, {"cateId": "10"})
    t1 = time.time()
    print(f"耗时: {t1-t0:.2f}s, 返回: {len(cat2['list'])}条, 总页数: {cat2['pagecount']}")

    print("\n===== 详情页 =====")
    if cat["list"]:
        vid = cat["list"][0]["vod_id"]
        t0 = time.time()
        detail = s.detailContent([vid])
        t1 = time.time()
        print(f"耗时: {t1-t0:.2f}s")
        if detail["list"]:
            vod = detail["list"][0]
            print(f"  标题: {vod['vod_name']}")
            print(f"  年份: {vod['vod_year']} 地区: {vod['vod_area']}")
            print(f"  播放源: {vod['vod_play_from']}")
            play_url = vod["vod_play_url"]
            if play_url:
                first_ep = play_url.split("#")[0]
                print(f"  第一集: {first_ep[:100]}")

                print("\n===== 播放测试 =====")
                t0 = time.time()
                play = s.playerContent("xiguam3u8", first_ep, [])
                t1 = time.time()
                print(f"耗时: {t1-t0:.2f}s")
                print(f"  URL: {play.get('url', '')[:80]}")
                print(f"  Parse: {play.get('parse')}")

    print("\n===== 搜索 (绝密任务) =====")
    t0 = time.time()
    search = s.searchContent("绝密任务", False)
    t1 = time.time()
    print(f"耗时: {t1-t0:.2f}s, 结果: {len(search['list'])}条")
    for v in search["list"][:5]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")