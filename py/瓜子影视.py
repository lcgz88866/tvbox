# -*- coding: utf-8 -*-
# 瓜子影视 - gz360.tv
# 苹果CMS V10 + 标准API接口 (360zy.com 多域名)
# 优化: 多域名自动测速, SSL上下文复用, 播放URL字段修复, 分类筛选增强

import re
import sys
import json
import ssl
import time
import socket
import urllib.parse
import urllib.request
from threading import Thread

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

    # 多API域名 (360zy系列, 测速选最快)
    API_DOMAINS = [
        "https://360zy.com",
        "https://360zy.tv",
        "https://360zy3.com",
        "https://360zy5.com",
        "https://360zy1.com",
        "https://360zy8.com",
        "https://360zy.net",
        "https://360zy6.com",
        "https://360zy9.com",
        "https://360zy4.com",
        "https://360zy7.com",
    ]

    def getName(self):
        return "瓜子影视"

    def init(self, extend=""):
        self.host = "https://gz360.tv"
        self.ua = "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Referer": self.host,
        }
        # SSL上下文复用 (避免每次请求重新创建)
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

        self._play_header = json.dumps({
            "User-Agent": self.ua,
            "Referer": self.host,
        })

        # 自动选择最快的API域名
        self.api = self._select_fastest_api()

        # 分类 (仅一级分类)
        self.cats = [
            {"type_name": "电影", "type_id": "1"},
            {"type_name": "连续剧", "type_id": "2"},
            {"type_name": "综艺", "type_id": "3"},
            {"type_name": "动漫", "type_id": "4"},
            {"type_name": "体育", "type_id": "17"},
            {"type_name": "爽文短剧", "type_id": "46"},
        ]

        # 二级分类映射
        self.sub_cats = {
            "1": [
                {"n": "全部", "v": ""},
                {"n": "动作片", "v": "6"},
                {"n": "喜剧片", "v": "7"},
                {"n": "爱情片", "v": "8"},
                {"n": "科幻片", "v": "9"},
                {"n": "恐怖片", "v": "10"},
                {"n": "剧情片", "v": "11"},
                {"n": "战争片", "v": "12"},
                {"n": "惊悚片", "v": "20"},
                {"n": "家庭篇", "v": "21"},
                {"n": "古装片", "v": "22"},
                {"n": "历史片", "v": "23"},
                {"n": "悬疑片", "v": "24"},
                {"n": "犯罪片", "v": "25"},
                {"n": "灾难片", "v": "26"},
                {"n": "纪录片", "v": "27"},
                {"n": "短片", "v": "28"},
                {"n": "动画片", "v": "29"},
                {"n": "西部片", "v": "45"},
            ],
            "2": [
                {"n": "全部", "v": ""},
                {"n": "国产剧", "v": "13"},
                {"n": "香港剧", "v": "14"},
                {"n": "韩国剧", "v": "15"},
                {"n": "欧美剧", "v": "16"},
                {"n": "台湾剧", "v": "30"},
                {"n": "日本剧", "v": "31"},
                {"n": "海外剧", "v": "32"},
                {"n": "泰国剧", "v": "33"},
            ],
            "3": [
                {"n": "全部", "v": ""},
                {"n": "大陆综艺", "v": "34"},
                {"n": "港台综艺", "v": "35"},
                {"n": "日韩综艺", "v": "36"},
                {"n": "欧美综艺", "v": "37"},
            ],
            "4": [
                {"n": "全部", "v": ""},
                {"n": "国产动漫", "v": "38"},
                {"n": "欧美动漫", "v": "39"},
                {"n": "日韩动漫", "v": "40"},
            ],
            "17": [
                {"n": "全部", "v": ""},
                {"n": "NBA", "v": "18"},
                {"n": "足球", "v": "41"},
                {"n": "篮球", "v": "42"},
            ],
            "46": [
                {"n": "全部", "v": ""},
                {"n": "现代都市", "v": "47"},
                {"n": "脑洞悬疑", "v": "48"},
                {"n": "年代穿越", "v": "49"},
                {"n": "古装仙侠", "v": "50"},
                {"n": "反转爽剧", "v": "51"},
                {"n": "女频恋爱", "v": "52"},
                {"n": "成长逆袭", "v": "53"},
            ],
        }

        # 通用筛选 (地区/年份/语言/排序)
        self.common_filters = [
            {
                "key": "cateId",
                "name": "类型",
                "value": [],  # 在 homeContent 中按分类填充
            },
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
                    {"n": "80年代", "v": "1980-1989"},
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
                    {"n": "法语", "v": "法语"},
                    {"n": "德语", "v": "德语"},
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
                    {"n": "好评", "v": "up"},
                ],
            },
        ]

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|ts)(\?|#|$)', url, re.I))

    def manualVideoCheck(self):
        pass

    def action(self, action):
        pass

    def destroy(self):
        pass

    def fetch_json(self, url, timeout=8):
        """请求API接口返回JSON数据 (SSL上下文复用 + 故障自动切换)"""
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=timeout) as resp:
                data = resp.read().decode('utf-8', errors='ignore')
                return json.loads(data)
        except Exception:
            # 主域名失败, 尝试备用域名
            path = url.replace(self.api, "")
            for alt in self.API_DOMAINS:
                if alt == self.api:
                    continue
                try:
                    alt_url = alt + path
                    req = urllib.request.Request(alt_url, headers=self.headers)
                    with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=timeout) as resp:
                        data = resp.read().decode('utf-8', errors='ignore')
                        result = json.loads(data)
                        # 切换到可用的备用域名
                        self.api = alt
                        return result
                except Exception:
                    continue
            return None

    def _select_fastest_api(self):
        """并行TCP测速选择最快的API域名"""
        results = {}
        threads = []

        def _test(domain):
            try:
                parsed = urllib.parse.urlparse(domain)
                host = parsed.hostname
                port = parsed.port or 443
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                t0 = time.time()
                sock.connect((host, port))
                t1 = time.time()
                sock.close()
                results[domain] = t1 - t0
            except Exception:
                results[domain] = 999

        for domain in self.API_DOMAINS:
            t = Thread(target=_test, args=(domain,))
            t.daemon = True
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=3)

        best = min(results, key=results.get) if results else self.API_DOMAINS[0]
        if results.get(best, 999) >= 999:
            return self.API_DOMAINS[0]
        return best

    # ==================== 首页 ====================
    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        try:
            result["class"] = self.cats

            # 注册筛选 (每个分类: 类型 + 地区 + 年份 + 语言 + 排序)
            for cat in self.cats:
                tid = cat["type_id"]
                filters = []
                for f in self.common_filters:
                    if f["key"] == "cateId":
                        filters.append({
                            "key": "cateId",
                            "name": "类型",
                            "value": self.sub_cats.get(tid, [{"n": "全部", "v": ""}]),
                        })
                    else:
                        filters.append(f)
                result["filters"][tid] = filters
        except Exception:
            pass
        return result

    def homeVideoContent(self):
        """首页推荐内容 (最新20条)"""
        result = {"list": []}
        try:
            data = self.fetch_json(
                f"{self.api}/api.php/provide/vod/?ac=detail&pg=1"
            )
            if data and data.get("code") == 1:
                for item in data.get("list", [])[:20]:
                    result["list"].append({
                        "vod_id": str(item["vod_id"]),
                        "vod_name": item.get("vod_name", ""),
                        "vod_pic": item.get("vod_pic", "").replace("\\/", "/"),
                        "vod_remarks": item.get("vod_remarks", ""),
                    })
        except Exception:
            pass
        return result

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 20, "total": 0}
        try:
            extend = extend or {}
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except Exception:
                    extend = {}

            cate_id = extend.get("cateId", "")
            area = extend.get("area", "")
            year = extend.get("year", "")
            lang = extend.get("lang", "")
            by = extend.get("by", "")
            page = int(pg) if int(pg) >= 1 else 1

            # 构造API URL
            # 优先使用 ac=detail (更快, 支持area/year/lang/by筛选)
            # 父分类t={tid}在ac=detail下返回空, 需用ajax/data接口
            if cate_id:
                # 二级分类: ac=detail 支持所有筛选参数
                url = f"{self.api}/api.php/provide/vod/?ac=detail&t={cate_id}&pg={page}"
                if area:
                    url += f"&area={urllib.parse.quote(area)}"
                if year:
                    url += f"&year={urllib.parse.quote(year)}"
                if lang:
                    url += f"&lang={urllib.parse.quote(lang)}"
                if by:
                    url += f"&by={by}"
            else:
                # 一级分类: ajax/data 接口 (支持父分类查询)
                url = f"{self.api}/index.php/ajax/data?mid=1&tid={tid}&page={page}&limit=20"
                # ajax/data 也支持area/year/by
                if area:
                    url += f"&area={urllib.parse.quote(area)}"
                if year:
                    url += f"&year={urllib.parse.quote(year)}"
                if by:
                    url += f"&by={by}"

            data = self.fetch_json(url)

            if data and data.get("code") == 1:
                if cate_id:
                    # ac=detail 返回完整分页信息
                    result["page"] = data.get("page", page)
                    result["pagecount"] = data.get("pagecount", 1)
                    result["limit"] = int(data.get("limit", 20))
                    result["total"] = data.get("total", 0)
                else:
                    # ajax/data 需手动计算分页
                    total = data.get("total", 0)
                    limit = 20
                    result["page"] = page
                    result["pagecount"] = (total + limit - 1) // limit if total > 0 else 1
                    result["limit"] = limit
                    result["total"] = total

                for item in data.get("list", []):
                    result["list"].append({
                        "vod_id": str(item["vod_id"]),
                        "vod_name": item.get("vod_name", ""),
                        "vod_pic": item.get("vod_pic", "").replace("\\/", "/"),
                        "vod_remarks": item.get("vod_remarks", ""),
                    })
        except Exception:
            pass
        return result

    # ==================== 详情 ====================
    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            data = self.fetch_json(
                f"{self.api}/api.php/provide/vod/?ac=detail&ids={vod_id}"
            )
            if not data or data.get("code") != 1:
                return result

            items = data.get("list", [])
            if not items:
                return result

            item = items[0]

            vod = {
                "vod_id": str(item["vod_id"]),
                "vod_name": item.get("vod_name", ""),
                "vod_pic": item.get("vod_pic", "").replace("\\/", "/"),
                "vod_actor": item.get("vod_actor", ""),
                "vod_director": item.get("vod_director", ""),
                "vod_year": item.get("vod_year", ""),
                "vod_area": item.get("vod_area", ""),
                "vod_lang": item.get("vod_lang", ""),
                "vod_remarks": item.get("vod_remarks", ""),
                "vod_pubdate": item.get("vod_pubdate", ""),
                "vod_content": self._clean_html(item.get("vod_content", "")),
                "type_name": item.get("type_name", ""),
                "vod_play_from": item.get("vod_play_from", ""),
                "vod_play_url": item.get("vod_play_url", ""),
            }

            result["list"].append(vod)
        except Exception:
            pass
        return result

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            wd = urllib.parse.quote(key)
            page = int(pg) if pg and int(pg) >= 1 else 1
            url = f"{self.api}/api.php/provide/vod/?ac=detail&wd={wd}&pg={page}"
            data = self.fetch_json(url)

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

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        result = {
            "parse": 0,
            "header": "",
            "url": "",
            "playUrl": "",
        }
        try:
            # id 格式: 播放名称$播放地址
            if "$" in id:
                play_url = id.split("$")[-1]
            else:
                play_url = id

            # 替换转义
            play_url = play_url.replace("\\/", "/")

            # 判断URL类型并设置播放头
            if ".m3u8" in play_url or ".mp4" in play_url:
                # 直链m3u8/mp4, 不需要Referer (CDN不验证)
                result["url"] = play_url
                result["parse"] = 0
            elif play_url.startswith("http"):
                # 非m3u8/mp4的HTTP链接, 尝试解析
                result["url"] = play_url
                result["parse"] = 1
            else:
                result["url"] = play_url
                result["parse"] = 0
        except Exception:
            pass
        return result

    # ==================== 工具方法 ====================
    def _clean_html(self, text):
        """清除HTML标签"""
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        return text.strip()


if __name__ == "__main__":
    import time

    s = Spider()
    s.init()

    print("===== 首页分类 =====")
    t0 = time.time()
    home = s.homeContent(True)
    t1 = time.time()
    print(f"耗时: {t1-t0:.2f}s")
    print("分类数:", len(home.get("class", [])))
    for c in home.get("class", []):
        print(f"  {c['type_name']} -> {c['type_id']}")

    print("\n===== 首页推荐 =====")
    t0 = time.time()
    rec = s.homeVideoContent()
    t1 = time.time()
    print(f"耗时: {t1-t0:.2f}s, 返回: {len(rec.get('list', []))}条")
    for v in rec.get("list", [])[:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 分类列表 (电影第1页) =====")
    t0 = time.time()
    cat = s.categoryContent("1", "1", True, {})
    t1 = time.time()
    print(f"耗时: {t1-t0:.2f}s, 返回: {len(cat.get('list', []))}条, 总页数: {cat.get('pagecount')}")
    for v in cat.get("list", [])[:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 分类列表 (电影-动作片) =====")
    t0 = time.time()
    cat2 = s.categoryContent("1", "1", True, {"cateId": "6"})
    t1 = time.time()
    print(f"耗时: {t1-t0:.2f}s, 返回: {len(cat2.get('list', []))}条, 总页数: {cat2.get('pagecount')}")
    for v in cat2.get("list", [])[:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 分类列表 (电影-动作片-2026年) =====")
    t0 = time.time()
    cat3 = s.categoryContent("1", "1", True, {"cateId": "6", "year": "2026"})
    t1 = time.time()
    print(f"耗时: {t1-t0:.2f}s, 返回: {len(cat3.get('list', []))}条, 总页数: {cat3.get('pagecount')}")

    print("\n===== 详情页 =====")
    if cat.get("list"):
        vid = cat["list"][0]["vod_id"]
        t0 = time.time()
        detail = s.detailContent([vid])
        t1 = time.time()
        print(f"耗时: {t1-t0:.2f}s")
        if detail.get("list"):
            vod = detail["list"][0]
            print(f"  标题: {vod['vod_name']}")
            print(f"  年份: {vod['vod_year']}")
            print(f"  地区: {vod['vod_area']}")
            print(f"  播放源: {vod['vod_play_from']}")
            play_url = vod['vod_play_url']
            if play_url:
                first_ep = play_url.split("#")[0]
                print(f"  第一集: {first_ep[:100]}")

                print("\n===== 播放测试 =====")
                t0 = time.time()
                play = s.playerContent("360zy", first_ep, [])
                t1 = time.time()
                print(f"耗时: {t1-t0:.2f}s")
                print(f"  URL: {play.get('url', '')[:80]}")
                print(f"  Parse: {play.get('parse')}")
                print(f"  Header: {play.get('header', '')[:60]}")

    print("\n===== 搜索 (绝密任务) =====")
    t0 = time.time()
    search = s.searchContent("绝密任务", False)
    t1 = time.time()
    print(f"耗时: {t1-t0:.2f}s, 结果: {len(search.get('list', []))}条")
    for v in search.get("list", [])[:5]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")
