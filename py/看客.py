# -*- coding: utf-8 -*-
"""
==========================================================
  看客 (kk123.seesee.sbs) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎 / dr_py)
  站点: 看客  https://kk123.seesee.sbs
  内核: 苹果CMS V10 (maccms) —— 走官方 JSON API, 不依赖 HTML 解析

  更新: 2026-09-19

  ---- 接口 (已实测, 可直接 curl) ----
    列表:   /api.php/provide/vod/?ac=list&pg=1&limit=20&t={type_id}&wd={关键词}
    详情:   /api.php/provide/vod/?ac=detail&ids={vid}        (支持逗号批量: ids=1,2,3)
    搜索:   /api.php/provide/vod/?ac=list&wd={关键词}&pg=1
    翻页:   &pg=N

  ---- 关键约束 (实测结论, 切勿改错) ----
    1) t 为「精确单值」匹配: 有子类的父级(电影20/剧集37)返回 0 条, 影片挂在叶子子类型下。
       分类只列 5 大类: 电影(20)/剧集(37)/动漫(43)/综艺(45)/其他(0);
       动作片/喜剧片... 子类型做成「筛选」, 未选时遍历该大类下全部子类型合并, 选中则用子类型 id 精确查。
       「其他」聚合番剧48/国创49/电影(B站)50/Netflix电影53, 同样遍历合并。
    2) 列表 API 不含 vod_pic (仅 8 字段), 封面需再用「批量详情 API」补:
       ac=detail&ids=id1,id2,... 一次请求拿全部 pic。
    3) 详情 API 的 vod_play_from / vod_play_url 已是标准分隔符:
       源间 '$$$'  集间 '#'  集名与地址 '$'  —— 直接透传 TVBox, 无需再拼。
    4) 播放地址绝大多数是外部平台页 (v.qq.com / iqiyi.com / bilibili.com / dytt share页 ...),
       非直链 m3u8, 需解析。
    5) 按需求「只要 dytt 线路」: detailContent 仅保留 dytt 一路, 其余线路全部删除;
       无 dytt 线路的影片将没有播放源 (dytt 为 share 页, playerContent 返回 parse=1 交解析器)。
==========================================================
"""

import sys
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

import re
import json
import ssl
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import quote
from json.decoder import JSONDecoder


# ==================== 站点常量 ====================
HOST = "https://kk123.seesee.sbs"
API = HOST + "/api.php/provide/vod/"

# 浏览器 UA (模拟移动端, 规避部分限制)
UA = ("Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

# 顶层分类 = 主类 (t 精确匹配, 有子类的父级需遍历子类)
# 按需求: 只列 电影/剧集/动漫/综艺/其他 五大类, 子类型(动作片...)做成「筛选」
# 「其他」聚合本站其余类型(番剧/国创/电影B站/Netflix电影)
MAIN_CATS = [
    {"type_name": "电影", "type_id": "20"},
    {"type_name": "剧集", "type_id": "37"},
    {"type_name": "动漫", "type_id": "43"},
    {"type_name": "综艺", "type_id": "45"},
    {"type_name": "其他", "type_id": "99"},   # 99 仅作占位, 真实按 CAT_SUBS 遍历子类型
]

# 主类 -> 子类型 (做成筛选). 子类型格式: (显示名, type_id)
CAT_SUBS = {
    "20": [("动作片", "21"), ("喜剧片", "22"), ("爱情片", "23"), ("科幻片", "24"),
           ("恐怖片", "25"), ("剧情片", "26"), ("战争片", "27"), ("惊悚片", "28"),
           ("犯罪片", "29"), ("冒险片", "30"), ("动画片", "31"), ("悬疑片", "32"),
           ("武侠片", "33"), ("奇幻片", "34"), ("纪录片", "35"), ("其他片", "36")],
    "37": [("国产剧", "38"), ("港台剧", "39"), ("欧美剧", "40"), ("日韩剧", "41"),
           ("其他剧", "42"), ("Netflix自制剧", "54")],
    "43": [("动漫", "44")],
    "45": [("综艺", "46")],
    "99": [("番剧(B站)", "48"), ("国创(B站)", "49"), ("电影(B站)", "50"), ("Netflix电影", "53")],
}

# 仅保留的播放线路 (其余全部删除, 不用)
KEEP_PLAY_FROM = "dytt"

PAGE_LIMIT = 24


class Spider(Spider):

    def getName(self):
        return "看客"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": UA,
            "Accept": "application/json,text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": HOST + "/",
        }
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

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

    # ==================== HTTP / JSON ====================
    def _fetch(self, url, headers=None, timeout=15):
        """GET 请求, 返回文本 (优先用框架 fetch, 失败回退 urllib)"""
        hdr = headers or self.headers
        try:
            rsp = self.fetch(url, headers=hdr)
            if isinstance(rsp, str):
                return rsp
            if rsp and hasattr(rsp, 'text'):
                return rsp.text
            if rsp and hasattr(rsp, 'content'):
                return rsp.content.decode("utf-8", errors="ignore")
        except Exception:
            pass
        req_url = url
        if not req_url.isascii():
            req_url = quote(req_url, safe=":/?&=%-._~")
        try:
            req = urllib.request.Request(req_url, headers=hdr)
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=self._ssl_ctx)
            )
            with opener.open(req, timeout=timeout) as r:
                d = r.read()
                return d.decode("utf-8", errors="ignore") if d else ""
        except urllib.error.HTTPError as e:
            try:
                return e.read().decode("utf-8", errors="ignore")
            except Exception:
                return ""
        except Exception:
            return ""

    def _get_json(self, url):
        """请求并解析 JSON, 返回 dict (失败返回空 dict)"""
        try:
            txt = self._fetch(url)
            if not txt:
                return {}
            return json.loads(txt)
        except Exception as e:
            print("_get_json error: {0}".format(e))
            return {}

    # ==================== 工具 ====================
    def _is_direct_video(self, url):
        if not url:
            return False
        lower = url.lower()
        for ext in [".m3u8", ".mp4", ".flv", ".avi", ".mkv", ".mov", ".wmv", ".ts"]:
            if ext in lower:
                return True
        return False

    def _norm_pic(self, pic):
        if not pic:
            return ""
        pic = pic.strip()
        if pic.startswith("//"):
            return "https:" + pic
        return pic

    def _enrich_pic(self, items):
        """列表 API 不含 vod_pic, 用批量详情 API 补封面 (一次请求)"""
        ids = [str(it.get("vod_id")) for it in items if it.get("vod_id")]
        if not ids:
            return
        det = self._get_json(API + "?ac=detail&ids=" + ",".join(ids))
        dmap = {}
        for d in det.get("list", []):
            vid = d.get("vod_id")
            if vid is not None:
                dmap[str(vid)] = d
        for it in items:
            d = dmap.get(str(it.get("vod_id")))
            if d and d.get("vod_pic"):
                it["vod_pic"] = self._norm_pic(d.get("vod_pic"))

    def _keep_dytt(self, play_from, play_url):
        """只保留 dytt 一路线路, 其余删除; 无 dytt 则返回空。
        maccms 返回的 play_from / play_url 都是 '$$$' 分隔的字符串。
        注: 本站 dytt 为 share 页(需解析), playerContent 对之返回 parse=1。
        """
        froms = play_from.split("$$$") if isinstance(play_from, str) else []
        urls = play_url.split("$$$") if isinstance(play_url, str) else []
        idx = None
        for i, f in enumerate(froms):
            if f.strip() == KEEP_PLAY_FROM:
                idx = i
                break
        if idx is None:
            return "", ""
        pf = froms[idx]
        pu = urls[idx] if idx < len(urls) else ""
        return pf, pu

    # ==================== 首页 ====================
    def _parse_selected(self, extend, subs):
        """从框架回传的 extend 中解析出选中的子类型 id (兼容 dict/list/str/嵌套形态)"""
        if not extend:
            return None
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                return None
        if isinstance(extend, list):
            for item in extend:
                if isinstance(item, dict):
                    v = item.get("value", item.get("v"))
                    sid = self._extract_sid(v, subs)
                    if sid:
                        return sid
            # 列表里也可能是纯字符串
            for item in extend:
                sid = self._extract_sid(item, subs)
                if sid:
                    return sid
            return None
        if not isinstance(extend, dict):
            return None
        for k, v in extend.items():
            sid = self._extract_sid(v, subs)
            if sid:
                return sid
        return None

    def _extract_sid(self, v, subs):
        """从单个 extend 值中提取匹配的子类型 id"""
        if v is None:
            return None
        if isinstance(v, list):
            for x in v:
                sid = self._extract_sid(x, subs)
                if sid:
                    return sid
            return None
        if isinstance(v, dict):
            val = v.get("v", v.get("value"))
            return self._extract_sid(val, subs)
        s = str(v).strip()
        if any(sid == s for _, sid in subs):
            return s
        return None

    def homeContent(self, filter=False):
        result = {}
        try:
            classes = [{"type_name": c["type_name"], "type_id": c["type_id"]} for c in MAIN_CATS]
            result["class"] = classes

            # 始终构建筛选并下发: 去掉 if filter 守卫 —— 部分 TVBox 分支 homeContent 不带 True 参数,
            # 否则子分类(动作片等)整块被跳过, 只剩主分类显示 (正是「子分类不显示」的常见成因)
            filters = {}
            for c in MAIN_CATS:
                tid = c["type_id"]
                subs = CAT_SUBS.get(tid, [])
                if subs:
                    # 列表格式: 与 kxyy.py / dr_py 官方一致, 每个分类一个 "类型" 筛选组
                    filters[tid] = [
                        {
                            "key": "类型",
                            "name": "类型",
                            "value": [{"n": "全部", "v": ""}] +
                                     [{"n": name, "v": sid} for name, sid in subs],
                        }
                    ]
            result["filters"] = filters

            # 首页: 最新列表
            j = self._get_json(API + "?ac=list&pg=1&limit=%d" % PAGE_LIMIT)
            items = []
            for it in j.get("list", []):
                items.append({
                    "vod_id": it.get("vod_id"),
                    "vod_name": it.get("vod_name", ""),
                    "vod_pic": "",
                    "vod_remarks": it.get("vod_remarks", "") or "",
                })
            self._enrich_pic(items)
            result["list"] = items

        except Exception as e:
            print("homeContent error: {0}".format(e))
        return result

    def homeVideoContent(self):
        pass

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg) if pg else 1, "pagecount": 999, "limit": PAGE_LIMIT, "total": 999999}
        try:
            page = int(pg) if int(pg) >= 1 else 1
            tid = str(tid)
            subs = CAT_SUBS.get(tid, [])

            # 解析筛选选中的子类型。框架回传的 extend 形态不统一, 兼容多种:
            #   dict  : {"类型": "21"} / {"类型": {"n":"动作片","v":"21"}}
            #   list  : [{"key":"类型","value":"21"}] / [{"key":"类型","value":["21"]}]
            #   str   : JSON 字符串
            selected = self._parse_selected(extend, subs)

            items = []
            if selected:
                # 选中子类型: 单 t 精确查询, 分页准确
                url = API + "?ac=list&t=%s&pg=%d&limit=%d" % (selected, page, PAGE_LIMIT)
                j = self._get_json(url)
                for it in j.get("list", []):
                    items.append(self._mk_list_item(it))
                self._enrich_pic(items)
                result["list"] = items
                result["page"] = page
                if j.get("pagecount"):
                    try:
                        result["pagecount"] = int(j.get("pagecount"))
                    except Exception:
                        pass
                if j.get("total"):
                    try:
                        result["total"] = int(j.get("total"))
                    except Exception:
                        pass
            elif subs:
                # 未选筛选: 遍历该主类下所有子类型, 各取第 page 页合并
                totals = []
                for _, sid in subs:
                    url = API + "?ac=list&t=%s&pg=%d&limit=%d" % (sid, page, PAGE_LIMIT)
                    j = self._get_json(url)
                    try:
                        totals.append(int(j.get("total", 0)))
                    except Exception:
                        totals.append(0)
                    for it in j.get("list", []):
                        items.append(self._mk_list_item(it))
                self._enrich_pic(items)
                result["list"] = items
                result["page"] = page
                if totals:
                    mx = max(totals)
                    result["total"] = sum(totals)
                    result["pagecount"] = max(mx // PAGE_LIMIT + 1, 1)
            else:
                # 叶子主类(无子类): 直接用主类 id 查
                url = API + "?ac=list&t=%s&pg=%d&limit=%d" % (tid, page, PAGE_LIMIT)
                j = self._get_json(url)
                for it in j.get("list", []):
                    items.append(self._mk_list_item(it))
                self._enrich_pic(items)
                result["list"] = items
                result["page"] = page
                if j.get("pagecount"):
                    try:
                        result["pagecount"] = int(j.get("pagecount"))
                    except Exception:
                        pass
                if j.get("total"):
                    try:
                        result["total"] = int(j.get("total"))
                    except Exception:
                        pass

        except Exception as e:
            print("categoryContent error: {0}".format(e))
        return result

    def _mk_list_item(self, it):
        return {
            "vod_id": it.get("vod_id"),
            "vod_name": it.get("vod_name", ""),
            "vod_pic": "",
            "vod_remarks": it.get("vod_remarks", "") or "",
        }

    # ==================== 详情 ====================
    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0] if isinstance(ids, list) else ids
            j = self._get_json(API + "?ac=detail&ids=%s" % vod_id)
            lst = j.get("list") or []
            if not lst:
                return result
            it = lst[0]

            # 只保留 dytt 一路线路, 其余线路全部删除
            pf, pu = self._keep_dytt(it.get("vod_play_from", ""), it.get("vod_play_url", ""))

            detail = {
                "vod_id": it.get("vod_id"),
                "vod_name": it.get("vod_name", ""),
                "vod_pic": self._norm_pic(it.get("vod_pic", "")),
                "type_name": it.get("type_name", ""),
                "vod_year": it.get("vod_year", "") or "",
                "vod_area": it.get("vod_area", "") or "",
                "vod_lang": it.get("vod_lang", "") or "",
                "vod_actor": it.get("vod_actor", "") or "",
                "vod_director": it.get("vod_director", "") or "",
                "vod_writer": it.get("vod_writer", "") or "",
                "vod_content": it.get("vod_content", "") or "",
                "vod_score": it.get("vod_score", "") or "",
                "vod_remarks": it.get("vod_remarks", "") or "",
                "vod_play_from": pf,
                "vod_play_url": pu,
            }
            result["list"].append(detail)

        except Exception as e:
            print("detailContent error: {0}".format(e))
        return result

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            page = int(pg) if int(pg) >= 1 else 1
            url = API + "?ac=list&wd=" + quote(key, safe="") + "&pg=%d&limit=%d" % (page, PAGE_LIMIT)
            j = self._get_json(url)
            items = []
            for it in j.get("list", []):
                items.append({
                    "vod_id": it.get("vod_id"),
                    "vod_name": it.get("vod_name", ""),
                    "vod_pic": "",
                    "vod_remarks": it.get("vod_remarks", "") or "",
                })
            self._enrich_pic(items)
            result["list"] = items

        except Exception as e:
            print("searchContent error: {0}".format(e))
        return result

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        """播放: id 即 vod_play_url 中的集地址。
        本站仅保留 dytt 一路线路, 其地址为 dytt share 页(需解析), 故 parse=1;
        若地址恰为直链 m3u8/mp4, 则 parse=0 直接播(兜底)。
        """
        result = {"parse": 1, "playUrl": "", "url": "", "header": "", "jx": 0}
        try:
            play_url = id.split("$")[-1].strip() if "$" in id else id.strip()
            if not play_url:
                return result

            header = json.dumps({
                "User-Agent": UA,
                "Referer": HOST + "/",
            })
            result["header"] = header

            if self._is_direct_video(play_url):
                result["parse"] = 0
                result["url"] = play_url
            else:
                # dytt share 页 -> 交 TVBox 解析器 (parse=1)
                result["parse"] = 1
                result["url"] = play_url

        except Exception as e:
            print("playerContent error: {0}".format(e))
        return result
