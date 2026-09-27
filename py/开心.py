# -*- coding: utf-8 -*-
"""
==========================================================
  开心影院 (kxyy1.cc) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎 / dr_py)
  站点: 开心影院  https://www.kxyy1.cc  (kxyy = 开心影院)
  模板: 自研 Bootstrap 影视站 (非 maccms/conch)

  更新: 2026-09-17 (修复筛选 + 剧情简介)

  ---- 路由规则 (已实测) ----
    首页:        /
    分类(无筛选): /vodshow/{type_id}-----------.html      例: /vodshow/2-----------.html
    分类(筛选):   /vodshow/{12段}.html
                 段位(0起): [0]=type_id [1]=地区 [2]=排序 [3]=类型 [8]=页码 [11]=年份
                 其余段位恒空。例:
                   /vodshow/2-%E7%BE%8E%E5%9B%BD----------.html           (美国 电视剧)
                   /vodshow/2-%E7%BE%8E%E5%9B%BD-%E5%89%A7%E6%83%85----.html (美国+剧情)
                   /vodshow/2-----------2---.html                        (第2页)
    详情页:      /voddetail/{vid}.html          例: /voddetail/1923.html
    播放页:      /vodplay/{vid}-{sid}-{nid}.html 例: /vodplay/1923-1-1.html
    搜索页:      /vodsearch/-------------.html?wd={key}   (注意: 前置人机验证, 大概率空)

  ---- 分类 type_id (导航实测, 数字) ----
    电影=1  电视剧=2  综艺=3  动漫=4  短剧=26  (纪录片=24)

  ---- 列表卡片结构 ----
    <a title="片名" href="/voddetail/{vid}.html" class="d-block cover">
      <img class="..." data-src="封面" alt="片名">
    </a>
    <div class="card-body">
      <h3 class="card-title">片名</h3>
      <p class="text-muted">2026-09-15</p>     <!-- 备注/更新 -->
    </div>
    <div class="ribbon ribbon-top p-0">8.7</div>  <!-- 评分(可选) -->

  ---- 详情页结构 ----
    元信息: <p ...><strong>导演：</strong>... <strong>制片国家/地区：</strong>[日本]
            <strong>类型：</strong><a>剧情片</a> <strong>语言：</strong>日语
            <strong>上映日期：</strong>2025-... <strong>编剧：</strong>... <strong>主演：</strong>...</p>
    剧情简介: 折叠区 <div id="synopsis"> ... <div class="card-body">正文</div> ... </div>
              (注意: <strong>摘要：</strong> 仅放 "1080P" 画质徽标, 不是剧情!)
    线路标签: <a href="#tabs-home-1">IK源</a>  (1=IK源 2=TT源 3=YX源 ...)
    选集:     <div class="tab-pane" id="tabs-home-1"><a href="/vodplay/{vid}-1-1.html">正片</a></div>

  ---- 播放页 ----
    var player_data = {"flag":"play","encrypt":0,"url":"https://.../index.m3u8","from":"ikm3u8",...}
    encrypt=0 -> url 为明文直链(m3u8/mp4), parse=0 直连播放
    encrypt=1 -> url 经 URL 编码; encrypt=2 -> url 经 base64 编码
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
import base64
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import quote, unquote
from html import unescape as html_unescape
from json.decoder import JSONDecoder


# ==================== 站点常量 ====================
HOST = "https://www.kxyy1.cc"
UA = ("Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

# 主分类 (导航栏实测, type_id 为数字, 对应 /vodshow/{tid} 路由)
CATEGORIES = [
    {"type_name": "电影",   "type_id": "1"},
    {"type_name": "电视剧", "type_id": "2"},
    {"type_name": "综艺",   "type_id": "3"},
    {"type_name": "动漫",   "type_id": "4"},
    {"type_name": "短剧",   "type_id": "26"},
]

# vodshow 12 段 URL 中, 各筛选项所在的段位(0起)
SEG_TYPE = 0
SEG_AREA = 1
SEG_ORDER = 2
SEG_CLASS = 3
SEG_PAGE = 8
SEG_YEAR = 11
SEG_COUNT = 12

# 全局筛选模板 (站点筛选项为全局共享: 地区/类型/排序/年份)
# value 的 v 为 URL 路径段原值: 中文已 URL 编码(可直接拼路径), 英文/数字原样
FILTER_TEMPLATE = [
    {
        "key": "area", "name": "地区",
        "values": [
            {"n": "不限", "v": ""},
            {"n": "中国大陆", "v": "%E4%B8%AD%E5%9B%BD%E5%A4%A7%E9%99%86"},
            {"n": "中国香港", "v": "%E4%B8%AD%E5%9B%BD%E9%A6%99%E6%B8%AF"},
            {"n": "中国台湾", "v": "%E4%B8%AD%E5%9B%BD%E5%8F%B0%E6%B9%BE"},
            {"n": "美国", "v": "%E7%BE%8E%E5%9B%BD"},
            {"n": "日本", "v": "%E6%97%A5%E6%9C%AC"},
            {"n": "韩国", "v": "%E9%9F%A9%E5%9B%BD"},
            {"n": "泰国", "v": "%E6%B3%B0%E5%9B%BD"},
            {"n": "英国", "v": "%E8%8B%B1%E5%9B%BD"},
            {"n": "法国", "v": "%E6%B3%95%E5%9B%BD"},
            {"n": "德国", "v": "%E5%BE%B7%E5%9B%BD"},
            {"n": "意大利", "v": "%E6%84%8F%E5%A4%A7%E5%88%A9"},
        ],
    },
    {
        "key": "class", "name": "类型",
        "values": [
            {"n": "不限", "v": ""},
            {"n": "爱情", "v": "%E7%88%B1%E6%83%85"},
            {"n": "古装", "v": "%E5%8F%A4%E8%A3%85"},
            {"n": "悬疑", "v": "%E6%82%AC%E7%96%91"},
            {"n": "都市", "v": "%E9%83%BD%E5%B8%82"},
            {"n": "喜剧", "v": "%E5%96%9C%E5%89%A7"},
            {"n": "战争", "v": "%E6%88%98%E4%BA%89"},
            {"n": "剧情", "v": "%E5%89%A7%E6%83%85"},
            {"n": "青春", "v": "%E9%9D%92%E6%98%A5"},
            {"n": "历史", "v": "%E5%8E%86%E5%8F%B2"},
            {"n": "网剧", "v": "%E7%BD%91%E5%89%A7"},
            {"n": "奇幻", "v": "%E5%A5%87%E5%B9%BB"},
            {"n": "冒险", "v": "%E5%86%92%E9%99%A9"},
            {"n": "励志", "v": "%E5%8A%B1%E5%BF%97"},
            {"n": "犯罪", "v": "%E7%8A%AF%E7%BD%AA"},
            {"n": "商战", "v": "%E5%95%86%E6%88%98"},
            {"n": "恐怖", "v": "%E6%81%90%E6%80%96"},
            {"n": "穿越", "v": "%E7%A9%BF%E8%B6%8A"},
            {"n": "农村", "v": "%E5%86%9C%E6%9D%91"},
            {"n": "人物", "v": "%E4%BA%BA%E7%89%A9"},
            {"n": "商业", "v": "%E5%95%86%E4%B8%9A"},
            {"n": "生活", "v": "%E7%94%9F%E6%B4%BB"},
            {"n": "其他", "v": "%E5%85%B6%E4%BB%96"},
        ],
    },
    {
        "key": "order", "name": "排序",
        "values": [
            {"n": "不限", "v": ""},
            {"n": "更新时间", "v": "time"},
            {"n": "近期热门", "v": "hits_week"},
            {"n": "豆瓣评分", "v": "douban_score"},
        ],
    },
    {
        "key": "year", "name": "年份",
        "values": [
            {"n": "不限", "v": ""},
            {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"},
            {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"},
            {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"},
            {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"},
            {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"},
            {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"},
            {"n": "2014", "v": "2014"}, {"n": "2013", "v": "2013"},
            {"n": "2012", "v": "2012"}, {"n": "2011", "v": "2011"},
            {"n": "2010", "v": "2010"}, {"n": "2009", "v": "2009"},
            {"n": "2008", "v": "2008"}, {"n": "2007", "v": "2007"},
            {"n": "2006", "v": "2006"}, {"n": "2005", "v": "2005"},
            {"n": "2004", "v": "2004"}, {"n": "2003", "v": "2003"},
            {"n": "2002", "v": "2002"}, {"n": "2001", "v": "2001"},
            {"n": "2000", "v": "2000"},
            {"n": "90年代", "v": "90%E5%B9%B4%E4%BB%A3"},
            {"n": "80年代", "v": "80%E5%B9%B4%E4%BB%A3"},
            {"n": "70年代", "v": "70%E5%B9%B4%E4%BB%A3"},
            {"n": "其他", "v": "%E5%85%B6%E4%BB%96"},
        ],
    },
]


class Spider(Spider):

    def getName(self):
        return "开心影院"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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

    # ==================== HTTP ====================
    def _fetch(self, url, headers=None, timeout=15, data=None):
        """GET/POST 请求, 返回 HTML 文本 (优先用框架 fetch, 失败回退 urllib)"""
        hdr = headers or self.headers

        if data is not None:
            try:
                rsp = self.post(url, data=data, headers=hdr)
                if isinstance(rsp, str):
                    return rsp
                if rsp and hasattr(rsp, 'text'):
                    return rsp.text
                if rsp and hasattr(rsp, 'content'):
                    return rsp.content.decode("utf-8", errors="ignore")
            except Exception:
                pass
            try:
                post_data = data.encode("utf-8") if isinstance(data, str) else urllib.parse.urlencode(data).encode("utf-8")
                req = urllib.request.Request(url, data=post_data, headers=hdr)
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
        else:
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

    # ==================== 工具 ====================
    def _fix_pic(self, pic):
        if not pic:
            return ""
        pic = html_unescape(pic)
        if pic.startswith("http"):
            return pic
        if pic.startswith("//"):
            return "https:" + pic
        if not pic.startswith("/"):
            pic = "/" + pic
        return HOST + pic

    def _enc(self, v):
        """筛选值处理: 已 URL 编码(含 %) 原样返回, 否则编码(兼容 TVBox 回传 label 的情况)"""
        v = str(v).strip()
        if not v:
            return ""
        if "%" in v:
            return v
        return quote(v, safe="")

    def _is_direct_video(self, url):
        if not url:
            return False
        lower = url.lower()
        for ext in [".m3u8", ".mp4", ".flv", ".avi", ".mkv", ".mov", ".wmv", ".ts"]:
            if ext in lower:
                return True
        return False

    # ==================== 列表解析 ====================
    def _parse_list(self, html):
        """解析视频列表卡片 (以 <a> 卡片为边界, 不跨卡片串台)
        首页/分类: <a title="片名" href="/voddetail/{id}.html" class="d-block cover">
                      <img data-src="封面" alt="片名">
                   </a>
                   <div class="card-body"><h3 class="card-title">片名</h3><p class="text-muted">日期</p></div>
                   <div class="ribbon ...">8.7</div>
        vodshow : <a href="/voddetail/{id}.html" class="...cover2"><img src="封面">
                      <span class="badge">更新至第xx集</span></a>
                   <div class="card-body"><h3 class="card-title">片名</h3><p class="text-muted">日期</p></div>

        关键: 标题/图片只在单个 <a>…</a> 卡片内取, 杜绝相邻卡片标题串台与图片错配。
        返回 [{'vod_id','vod_name','vod_pic','vod_remarks'}, ...]
        """
        items = []
        seen = set()
        link_pat = re.compile(r'<a\b([^>]*?)href="(/voddetail/(\d+)\.html)"([^>]*)>', re.S)
        for m in link_pat.finditer(html):
            vid = m.group(3)
            if vid in seen:
                continue
            a_open = m.group(0)          # 整个 <a ...> 开标签 (可能含 title=)
            a_start = m.start()
            end = html.find('</a>', a_start)
            if end == -1:
                end = a_start + 800
            a_block = html[a_start:end]  # <a ...>...</a> 内联内容

            # ---- 标题: 优先 <a> 自身 title=, 否则其后紧跟的 <h3 class="card-title"> ----
            title = ""
            ta = re.search(r'title="([^"]+)"', a_open)
            if ta:
                title = ta.group(1).strip()
            if not title:
                after = html[end:end + 600]
                hm = re.search(r'card-title[^>]*>([^<]+)</h3>', after)
                if hm:
                    title = hm.group(1).strip()
            if not title:
                continue
            if title in ("更多", "换一换", "上一页", "下一页", "首页"):
                continue

            seen.add(vid)

            # ---- 封面: 仅在 <a>…</a> 内取 <img> 的 data-src / src ----
            pic = ""
            im = re.search(r'<img\b[^>]*\b(?:data-src|src)="([^"]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^"]*)?)"', a_block, re.I)
            if not im:
                im = re.search(r'<img\b[^>]*\bsrc="([^"]+)"', a_block, re.I)
            if im:
                pic = self._fix_pic(im.group(1))

            # ---- 备注: <a> 内 badge(更新至..)> 否则 </a> 后 text-muted 日期 > 评分 ----
            remark = ""
            bm = re.search(r'<span class="badge[^"]*">([^<]+)</span>', a_block)
            if bm:
                bt = bm.group(1).strip()
                if bt:
                    remark = bt
            if not remark:
                after = html[end:end + 600]
                rm = re.search(r'<p class="text-muted">([^<]+)</p>', after)
                if rm:
                    remark = rm.group(1).strip()
            sm = re.search(r'class="ribbon[^"]*">([^<]+)</div>', html[a_start:a_start + 1200])
            if sm:
                score = sm.group(1).strip()
                if score and score != remark:
                    remark = (remark + " " + score).strip() if remark else score

            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return items

    # ==================== 首页 ====================
    def homeContent(self, filter):
        result = {}
        try:
            classes = []
            filters = {}
            for c in CATEGORIES:
                classes.append({"type_name": c["type_name"], "type_id": c["type_id"]})
                # 每个分类挂同一套全局筛选
                filters[c["type_id"]] = [
                    {
                        "key": g["key"],
                        "name": g["name"],
                        "value": [dict(x) for x in g["values"]],
                    }
                    for g in FILTER_TEMPLATE
                ]
            result["class"] = classes

            if filter:
                result["filters"] = filters

            html = self._fetch(HOST + "/")
            if html:
                result["list"] = self._parse_list(html)

        except Exception as e:
            print("homeContent error: {0}".format(e))
        return result

    def homeVideoContent(self):
        pass

    # ==================== 分类 ====================
    def _build_vodshow_url(self, tid, extend, pg):
        """构造 /vodshow/{12段}.html
        extend: {'area','order','class','year'} -> 对应段位
        pg: 页码 -> 段位 8
        """
        segs = [""] * SEG_COUNT
        segs[SEG_TYPE] = str(tid)
        if extend:
            if extend.get("area"):
                segs[SEG_AREA] = self._enc(extend["area"])
            if extend.get("order"):
                segs[SEG_ORDER] = self._enc(extend["order"])
            if extend.get("class"):
                segs[SEG_CLASS] = self._enc(extend["class"])
            if extend.get("year"):
                segs[SEG_YEAR] = self._enc(extend["year"])
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1
        if page > 1:
            segs[SEG_PAGE] = str(page)
        return HOST + "/vodshow/" + "-".join(segs) + ".html"

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg) if pg else 1, "pagecount": 999, "limit": 24, "total": 999999}
        try:
            page = int(pg) if int(pg) >= 1 else 1
            url = self._build_vodshow_url(tid, extend or {}, page)
            html = self._fetch(url)
            if html:
                result["list"] = self._parse_list(html)
                result["page"] = page

        except Exception as e:
            print("categoryContent error: {0}".format(e))
        return result

    # ==================== 详情 ====================
    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0] if isinstance(ids, list) else ids
            detail_url = HOST + "/voddetail/" + str(vod_id) + ".html"
            html = self._fetch(detail_url)
            if not html:
                return result

            detail = self._extract_detail(html, vod_id)
            if detail:
                result["list"].append(detail)

        except Exception as e:
            print("detailContent error: {0}".format(e))
        return result

    @staticmethod
    def _label_val(html, label):
        """提取 <strong>标签：</strong>内容(到 </p>/</div>/<br )"""
        pattern = re.escape(label) + r'[：:]\s*</strong>\s*(.*?)(?:</p>|</div>|<br\s*/?>|</strong>|</dd>|</li>)'
        m = re.search(pattern, html, re.S)
        if not m:
            return ""
        content = m.group(1)
        links = re.findall(r'<a[^>]*>([^<]+)</a>', content)
        if links:
            return ",".join([l.strip() for l in links if l.strip()])
        return re.sub(r'<[^>]+>', '', content).strip()

    def _extract_synopsis(self, html):
        """真实剧情简介在折叠区 #synopsis 的 <div class="card-body"> 内
        (站点 <strong>摘要：</strong> 仅放 "1080P" 画质徽标, 不是剧情)
        """
        m = re.search(r'id="synopsis".*?card-body">(.*?)</div>', html, re.S)
        if m:
            txt = re.sub(r'<[^>]+>', '', m.group(1))
            txt = txt.strip(' \u3000\t\n\r')
            if txt:
                return txt
        # 兜底: 部分页面可能直接放 摘要/剧情 字段
        return self._label_val(html, "摘要") or self._label_val(html, "剧情")

    def _extract_detail(self, html, vod_id):
        """从详情页提取影片信息 + 播放线路/选集"""
        try:
            # 标题
            title = ""
            m = re.search(r'<a[^>]*class="d-block cover"[^>]*title="([^"]+)"', html)
            if m:
                title = m.group(1).strip()
            if not title:
                m = re.search(r'<title>《?([^》<]+)', html)
                if m:
                    title = m.group(1).strip()
            if not title:
                m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
                if m:
                    title = m.group(1).strip()
            if not title:
                return None

            # 封面
            pic = ""
            m = re.search(r'og:image[^>]*content="([^"]+)"', html)
            if m:
                pic = self._fix_pic(m.group(1))
            if not pic:
                m = re.search(r'class="d-block cover"[^>]*data-src="([^"]+)"', html)
                if m:
                    pic = self._fix_pic(m.group(1))
            if not pic:
                m = re.search(r'data-src="([^"]+)"', html)
                if m:
                    pic = self._fix_pic(m.group(1))
            if not pic:
                m = re.search(r'<img[^>]*alt="' + re.escape(title) + r'"[^>]*src="([^"]+)"', html)
                if m:
                    pic = self._fix_pic(m.group(1))

            # 元信息
            vod_area = self._label_val(html, "制片国家/地区").strip("[]").strip()
            vod_year = self._label_val(html, "上映日期")
            vod_year = re.search(r'(\d{4})', vod_year).group(1) if re.search(r'\d{4}', vod_year) else vod_year
            vod_class = self._label_val(html, "类型")
            vod_lang = self._label_val(html, "语言")
            vod_actor = self._label_val(html, "主演")
            vod_director = self._label_val(html, "导演")
            vod_writer = self._label_val(html, "编剧")
            vod_douban = self._label_val(html, "豆瓣评分") or self._label_val(html, "评分")
            vod_content = self._extract_synopsis(html)

            play_from, play_url = self._extract_play_info(html, vod_id)

            return {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_class": vod_class,
                "vod_year": vod_year,
                "vod_area": vod_area,
                "vod_lang": vod_lang,
                "vod_actor": vod_actor,
                "vod_director": vod_director,
                "vod_writer": vod_writer,
                "vod_content": vod_content,
                "vod_douban_score": vod_douban,
                "vod_play_from": play_from,
                "vod_play_url": play_url,
            }

        except Exception as e:
            print("_extract_detail error: {0}".format(e))
            return None

    def _extract_play_info(self, html, vod_id):
        """提取线路名 + 选集
        线路名: <a href="#tabs-home-1">IK源</a>
        选集:   <div class="tab-pane" id="tabs-home-1"><a href="/vodplay/{vid}-1-1.html">正片</a></div>
        """
        try:
            name_map = {}
            for m in re.finditer(r'href="#tabs-home-(\d+)"[^>]*>(.*?)</a>', html, re.S):
                nid = m.group(1)
                name = re.sub(r'<[^>]+>', '', m.group(2)).replace('&nbsp;', ' ').strip()
                name_map[nid] = name or ("线路" + nid)

            starts = [(m.start(), m.group(1)) for m in re.finditer(r'id="tabs-home-(\d+)"', html)]
            if not starts:
                return "", ""

            play_from_list = []
            play_url_list = []
            for idx, (pos, nid) in enumerate(starts):
                end = starts[idx + 1][0] if idx + 1 < len(starts) else len(html)
                pane = html[pos:end]

                eps = []
                for em in re.finditer(r'href="(/vodplay/[^"]+\.html)"[^>]*>(.*?)</a>', pane, re.S):
                    ep_url = HOST + em.group(1)
                    ep_name = re.sub(r'<[^>]+>', '', em.group(2)).strip()
                    if not ep_name:
                        ep_name = "第" + str(len(eps) + 1) + "集"
                    eps.append(ep_name + "$" + ep_url)

                if eps:
                    play_from_list.append(name_map.get(nid, "线路" + nid))
                    play_url_list.append("#".join(eps))

            return ("$$$".join(play_from_list), "$$$".join(play_url_list))

        except Exception as e:
            print("_extract_play_info error: {0}".format(e))
            return "", ""

    # ==================== 搜索 ====================
    # 注意: 该站搜索前置「人机验证」网关 (先访问 /index.php/verify 获取验证码,
    #       再 POST /index.php/ajax/verify_check?type=search&verify=CODE 通过后才出结果)。
    #       TVBox 的 self.fetch 不执行 JS、也无法解验证码, 故自动化搜索大概率返回空。
    #       此处仍按站点自身 JS 的跳转地址尽力请求, 若服务端放宽验证则可正常返回。
    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            page = int(pg) if int(pg) >= 1 else 1
            search_url = HOST + "/vodsearch/-------------.html?wd=" + quote(key, safe="")
            if page > 1:
                search_url += "&page=" + str(page)

            html = self._fetch(search_url)
            if not html:
                return result

            result["list"] = self._parse_list(html)

        except Exception as e:
            print("searchContent error: {0}".format(e))
        return result

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        """播放: 从播放页提取 var player_data, 取直链 m3u8/mp4
        encrypt=0: url 为明文直链
        encrypt=1: url 经 URL 编码
        encrypt=2: url 经 base64 编码
        """
        result = {"parse": 0, "playUrl": "", "url": "", "header": "", "jx": 0}
        try:
            play_path = id.split("$")[-1].strip() if "$" in id else id.strip()
            if play_path.startswith("http"):
                play_page_url = play_path
            else:
                if not play_path.startswith("/"):
                    play_path = "/" + play_path
                play_page_url = HOST + play_path

            play_header = json.dumps({
                "User-Agent": UA,
                "Referer": HOST + "/",
            })

            html = self._fetch(play_page_url)
            if not html:
                result["parse"] = 1
                result["url"] = play_page_url
                result["header"] = play_header
                return result

            player_data = None
            i = html.find('var player_data')
            if i >= 0:
                seg = html[i:]
                start = seg.find('{')
                if start >= 0:
                    try:
                        player_data, _ = JSONDecoder().raw_decode(seg[start:])
                    except Exception:
                        player_data = None

            if not player_data:
                result["parse"] = 1
                result["url"] = play_page_url
                result["header"] = play_header
                return result

            play_url = player_data.get("url", "")
            encrypt = int(player_data.get("encrypt", 0) or 0)

            if not play_url:
                result["parse"] = 1
                result["url"] = play_page_url
                result["header"] = play_header
                return result

            if encrypt == 1:
                try:
                    for _ in range(3):
                        decoded = unquote(play_url)
                        if decoded == play_url:
                            break
                        play_url = decoded
                except Exception:
                    pass
            elif encrypt == 2:
                try:
                    play_url = base64.b64decode(play_url).decode("utf-8", errors="ignore")
                    play_url = unquote(play_url)
                except Exception:
                    pass

            play_url = html_unescape(play_url).strip()

            if self._is_direct_video(play_url):
                result["parse"] = 0
                result["jx"] = 0
                result["url"] = play_url
                result["header"] = play_header
            else:
                result["parse"] = 1
                result["jx"] = 0
                result["url"] = play_page_url
                result["header"] = play_header

        except Exception as e:
            print("playerContent error: {0}".format(e))
            try:
                play_path = id.split("$")[-1].strip() if "$" in id else id.strip()
                if not play_path.startswith("http"):
                    if not play_path.startswith("/"):
                        play_path = "/" + play_path
                    play_page_url = HOST + play_path
                else:
                    play_page_url = play_path
                result["parse"] = 1
                result["url"] = play_page_url
                result["header"] = json.dumps({
                    "User-Agent": UA,
                    "Referer": HOST + "/",
                })
            except Exception:
                pass

        return result
