# -*- coding: utf-8 -*-
"""
==========================================================
  青禾影视 (movie.qhdaohang.cn) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎)
  框架: 苹果CMS V10 (maccms) - mxpro 模板
  更新: 2026-09-19

  URL规则:
    首页: /
    分类页(纯列表): /vodtype/{tid}.html  /  /vodtype/{tid}-{page}.html
    筛选页: /vodshow/{tid}-{area}-{by}-{class}-{lang}-{letter}------{page}---{year}.html
            (标准maccms 12段格式, 仅 area/年份 实际生效)
    详情页: /voddetail/{vid}.html
    播放页: /vodplay/{vid}-{sid}-{nid}.html
    搜索页: GET /vodsearch/{wd}-------------.html

  导航分类 (真实, 来自站点导航栏):
    电影=20  连续剧=37  动漫=43  综艺=45
    B站=47   Netflix=52   短剧=55   下饭剧=56

  卡片结构:
    [海报布局] (首页/分类)
      <a href="/vodplay/{vid}-{sid}-{nid}.html" title="标题" class="module-poster-item module-item">
        <div class="module-item-cover">
          <div class="module-item-note">HD中字</div>
          <div class="module-item-pic"><img data-original="封面" ...></div>
        </div>
        <div class="module-poster-item-info"><div class="module-poster-item-title">标题</div></div>
      </a>

    [卡片布局] (搜索结果)
      <a href="/vodplay/{vid}-1-1.html" ...><img data-original="封面"></a>
      <div class="module-card-item-info">
        <div class="module-card-item-title"><a href="/vodplay/{vid}-1-1.html"><strong>标题</strong></a></div>
      </div>

  详情页元数据 (mxpro):
    <h1>片名</h1>
    <span class="module-info-item-title">导演：</span><div class="module-info-item-content"><a>董润年</a></div>
    <span class="module-info-item-title">主演：</span>...
    <span class="module-info-item-title">更新：</span>2026-09-19
    <span class="module-info-item-title">备注：</span>2026年08月01日上映
    <div class="module-info-introduction-content"><p>简介</p></div>

  播放源结构 (多线路):
    源标签: <div class="module-tab-item tab-item" data-dropdown-value="奇异"><span>奇异</span><small>1</small></div>
    集数:   <div class="module-list sort-list tab-list his-tab-list" id="panel1">
              <div class="module-play-list">
                <div class="module-play-list-content module-play-list-base">
                  <a class="module-play-list-link" href="/vodplay/{vid}-{sid}-{nid}.html" title="..."><span>正片</span></a>
                </div>
              </div>
            </div>

  播放页:
    player_aaaa = {"flag":"play","encrypt":0,"url":"https://play.phimgood.com/share/xxxx","from":"dytt",...}
    该 url 为分享页, 需再请求分享页提取真实直链:
      const url = "/20260918/31382_xxxx/index.m3u8?sign=xxxx";  ->  https://play.phimgood.com + url

  header 使用 json.dumps (TVBox标准格式)
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
from urllib.parse import quote, unquote, urlparse
from html import unescape as html_unescape
from json.decoder import JSONDecoder


class Spider(Spider):

    HOST = "https://movie.qhdaohang.cn"
    UA = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # 主分类 (来自站点导航栏, 真实 tid)
    CATEGORIES = [
        {"type_name": "电影", "type_id": "20"},
        {"type_name": "连续剧", "type_id": "37"},
        {"type_name": "动漫", "type_id": "43"},
        {"type_name": "综艺", "type_id": "45"},
        {"type_name": "B站", "type_id": "47"},
        {"type_name": "Netflix", "type_id": "52"},
        {"type_name": "短剧", "type_id": "55"},
        {"type_name": "下饭剧", "type_id": "56"},
    ]

    # 地区选项 (经 vodshow area 段验证可用)
    AREA_VALUES = [
        {"n": "全部", "v": ""},
        {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"},
        {"n": "美国", "v": "美国"}, {"n": "韩国", "v": "韩国"}, {"n": "日本", "v": "日本"},
        {"n": "泰国", "v": "泰国"}, {"n": "英国", "v": "英国"}, {"n": "法国", "v": "法国"},
        {"n": "德国", "v": "德国"}, {"n": "印度", "v": "印度"}, {"n": "意大利", "v": "意大利"},
        {"n": "西班牙", "v": "西班牙"}, {"n": "加拿大", "v": "加拿大"}, {"n": "其他", "v": "其他"},
    ]

    # 语言选项 (备用, 站点多数线路为原声/国语, 由 area 段兼容)
    LANG_VALUES = [
        {"n": "全部", "v": ""},
        {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"},
        {"n": "粤语", "v": "粤语"}, {"n": "韩语", "v": "韩语"},
        {"n": "日语", "v": "日语"}, {"n": "法语", "v": "法语"},
    ]

    def getName(self):
        return "青禾影视"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": self.UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.HOST + "/",
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

    # ==================== 筛选配置 ====================
    def _build_filters(self):
        filters = {}
        year_values = [{"n": "全部", "v": ""}]
        for y in range(2026, 1999, -1):
            year_values.append({"n": str(y), "v": str(y)})

        for cat in self.CATEGORIES:
            cat_id = cat["type_id"]
            filters[cat_id] = [
                {"key": "area", "name": "地区", "value": self.AREA_VALUES},
                {"key": "year", "name": "年份", "value": year_values},
                {"key": "lang", "name": "语言", "value": self.LANG_VALUES},
            ]
        return filters

    # ==================== HTTP ====================
    def _fetch(self, url, headers=None, timeout=15, data=None):
        """GET/POST请求, 返回HTML文本"""
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
            except:
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
                except:
                    return ""
            except:
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
            except:
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
                except:
                    return ""
            except:
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
        return self.HOST + pic

    def _is_direct_video(self, url):
        """判断是否为直链视频URL"""
        if not url:
            return False
        lower = url.lower()
        for ext in [".m3u8", ".mp4", ".flv", ".avi", ".mkv", ".mov", ".wmv", ".ts"]:
            if ext in lower:
                return True
        return False

    def _build_cat_url(self, tid, pg, extend):
        """构建分类/筛选URL
        纯列表走 vodtype (站点该路由返回更多卡片且不分页);
        带筛选(地区/年份/语言)走标准 vodshow 12段格式 (仅 area/year/lang 实际生效)。
        """
        area = cls = lang = year = by = ""
        if extend:
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except:
                    extend = {}
            area = extend.get("area", "") or ""
            year = extend.get("year", "") or ""
            lang = extend.get("lang", "") or ""
            cls = extend.get("class", "") or ""
            by = extend.get("sort", "") or ""

        if area or year or lang or cls or by:
            # 标准maccms 12段: tid-area-by-class-lang-letter-...-page-...-year
            fields = [str(tid), area, by, cls, lang, "", "", "", str(int(pg) if int(pg) >= 1 else 1), "", "", year]
            return "/vodshow/" + "-".join(fields) + ".html"
        else:
            page = int(pg) if int(pg) >= 1 else 1
            if page > 1:
                return "/vodtype/%s-%s.html" % (tid, page)
            return "/vodtype/%s.html" % tid

    # ==================== 列表解析 ====================
    @staticmethod
    def _anchor_title(anchor):
        """从【锚点内部】提取标题: 优先 title 属性, 其次 <strong>, 再 module-poster-item-title"""
        tm = re.search(r'\btitle="([^"]+)"', anchor)
        if tm and tm.group(1).strip():
            return tm.group(1).strip()
        sm = re.search(r'<strong>([^<]+)</strong>', anchor)
        if sm and sm.group(1).strip():
            return sm.group(1).strip()
        pm = re.search(r'module-poster-item-title[^>]*>([^<]+)<', anchor)
        if pm and pm.group(1).strip():
            return pm.group(1).strip()
        return ""

    @staticmethod
    def _anchor_pic(anchor):
        """从【锚点内部】提取封面(data-original); 只取本卡片, 杜绝相邻卡片串图"""
        m = re.search(r'data-original="([^"]+)"', anchor)
        if m and m.group(1).strip():
            return m.group(1).strip()
        return ""

    @staticmethod
    def _anchor_note(anchor):
        """从【锚点内部】提取备注(如 HD中字 / 更新至13集)"""
        m = re.search(r'module-item-note[^>]*>([^<]+)<', anchor)
        if m and m.group(1).strip():
            return m.group(1).strip()
        return ""

    @staticmethod
    def _backward_pic(html, start, window=400):
        """向前回溯取【最近一张】data-original(搜索卡片布局: 图锚与标题锚为相邻兄弟节点,
        最近者即本卡片图片)。仅取距标题锚点最近的图, 不会跨卡片串图。
        """
        seg = html[max(0, start - window): start]
        matches = re.findall(r'data-original="([^"]+)"', seg)
        for u in reversed(matches):
            if u.strip():
                return u.strip()
        return ""

    def _parse_list(self, html):
        """解析视频列表卡片 (mxpro 海报布局 + 搜索卡片布局)

        修复项 —— 图片与剧名不对称:
          旧逻辑在锚点 ±400 字符区域内搜索 data-original, 而本站点
          (1) 每张海报卡片体积较大(>400字符);
          (2) 首页顶部 banner 轮播与下方海报网格【复用同一批 vodplay 链接】;
          导致相邻卡片的图片被误取, 出现"剧名A配图片B"。
          现改为: 标题/封面/备注优先从【各自锚点内部】提取; 搜索卡片布局中
          图片锚点不带 vodplay 链接、与标题锚点相邻, 则在标题锚点处向前回溯取
          【最近一张】图。无标题/按钮类锚点直接跳过, 杜绝串图与污染。
        """
        items = {}    # vid -> {vod_id, vod_name, vod_pic, vod_remarks}
        order = []    # 保留首次出现(且已含标题)的 vid 顺序

        # 匹配包含 vodplay 链接的 <a> 标签及其内容
        pattern = re.compile(
            r'<a\b[^>]*href="(/vodplay/(\d+)-(\d+)-(\d+)\.html)"[^>]*>(.*?)</a>',
            re.S
        )
        SKIP = ("更多", "换一换", "上一页", "下一页", "立即播放", "播放")
        for m in pattern.finditer(html):
            vid = m.group(2)
            anchor = m.group(0)

            title = self._anchor_title(anchor)
            if not title or title in SKIP:
                continue

            # 封面: 优先锚点内部(海报布局); 否则向前回溯取最近一张图(搜索卡片布局)
            ap = self._anchor_pic(anchor)
            if ap:
                pic = self._fix_pic(ap)
            else:
                bp = self._backward_pic(html, m.start())
                pic = self._fix_pic(bp) if bp else ""

            note = self._anchor_note(anchor)

            rec = items.get(vid)
            if rec is None:
                items[vid] = {
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": note,
                }
                order.append(vid)
            else:
                # 同 vid 再次出现(如首页 banner 与网格复用链接): 仅补全缺失字段
                if not rec["vod_name"]:
                    rec["vod_name"] = title
                    if vid not in order:
                        order.append(vid)
                if not rec["vod_pic"] and pic:
                    rec["vod_pic"] = pic
                if not rec["vod_remarks"] and note:
                    rec["vod_remarks"] = note

        return [items[v] for v in order if items[v]["vod_name"]]

    # ==================== 首页 ====================
    def homeContent(self, filter):
        result = {}
        try:
            classes = []
            for c in self.CATEGORIES:
                classes.append({"type_name": c["type_name"], "type_id": c["type_id"]})
            result["class"] = classes

            if filter:
                result["filters"] = self._build_filters()

            html = self._fetch(self.HOST)
            if html:
                result["list"] = self._parse_list(html)

        except Exception as e:
            print("homeContent error: {0}".format(e))
        return result

    def homeVideoContent(self):
        pass

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        # 站点不支持真实分页(页面参数被忽略, 始终返回首页内容), 固定 pagecount=1 避免重复加载
        result = {"list": [], "page": int(pg) if pg else 1, "pagecount": 1, "limit": 90, "total": 9999}
        try:
            page = int(pg) if int(pg) >= 1 else 1

            cat_url = self.HOST + self._build_cat_url(tid, page, extend)
            html = self._fetch(cat_url)
            if html:
                result["list"] = self._parse_list(html)

        except Exception as e:
            print("categoryContent error: {0}".format(e))
        return result

    # ==================== 详情 ====================
    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            detail_url = self.HOST + "/voddetail/" + str(vod_id) + ".html"
            html = self._fetch(detail_url)
            if not html:
                return result

            detail = self._extract_detail(html, vod_id)
            if detail:
                result["list"].append(detail)

        except Exception as e:
            print("detailContent error: {0}".format(e))
        return result

    def _field(self, html, label):
        """提取 module-info-item (导演/主演/更新/备注) 的值"""
        pat = re.escape(label) + r'[：:]\s*</span>\s*<div class="module-info-item-content">(.*?)</div>'
        m = re.search(pat, html, re.S)
        if not m:
            return ""
        content = m.group(1)
        links = re.findall(r'<a[^>]*>([^<]+)</a>', content)
        if links:
            return "/".join([l.strip() for l in links])
        return re.sub(r'<[^>]+>', '', content).strip()

    def _extract_detail(self, html, vod_id):
        """从详情页HTML提取视频详情 (mxpro 模板)"""
        try:
            # 标题
            title = ""
            m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            if m:
                title = m.group(1).strip()
            if not title:
                m = re.search(r'class="hl-item-thumb[^"]*"[^>]*title="([^"]+)"', html)
                if m:
                    title = m.group(1).strip()
            if not title:
                m = re.search(r'<title>([^<]+)</title>', html)
                if m:
                    title = m.group(1).strip()
            if not title:
                return None

            # 封面 (module-info-poster 区域内的 data-original)
            pic = ""
            m = re.search(r'class="module-info-poster"[^>]*>.*?data-original="([^"]+)"', html, re.S)
            if m:
                pic = self._fix_pic(m.group(1))
            if not pic:
                m = re.search(r'data-original="([^"]+)"', html)
                if m:
                    pic = self._fix_pic(m.group(1))

            # 元数据字段
            director = self._field(html, "导演")
            actor = self._field(html, "主演")
            vod_remarks = self._field(html, "备注") or self._field(html, "更新")
            vod_year = ""
            vod_area = ""
            vod_class = ""
            tags = re.findall(r'class="module-info-tag-link"[^>]*>\s*<a[^>]*>([^<]+)</a>', html)
            if tags:
                for t in tags:
                    if re.match(r'^\d{4}$', t):
                        vod_year = t
                    elif t in ("大陆", "香港", "台湾", "美国", "韩国", "日本", "泰国", "英国", "法国", "德国", "印度"):
                        vod_area = t
                    else:
                        if vod_class:
                            vod_class += "/" + t
                        else:
                            vod_class = t

            # 简介
            vod_content = ""
            m = re.search(r'class="module-info-introduction-content"[^>]*>(.*?)</div>', html, re.S)
            if m:
                vod_content = re.sub(r'<[^>]+>', '', m.group(1)).strip()

            # 豆瓣评分 (如有)
            vod_douban = ""
            m = re.search(r'class="module-info-item-title">豆瓣：</span>.*?font[^>]*>([^<]+)<', html, re.S)
            if m:
                vod_douban = m.group(1).strip()

            play_from, play_url = self._extract_play_info(html, vod_id)

            return {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "type_name": vod_class,
                "vod_year": vod_year,
                "vod_area": vod_area,
                "vod_remarks": vod_remarks,
                "vod_actor": actor,
                "vod_director": director,
                "vod_content": vod_content,
                "vod_play_from": play_from,
                "vod_play_url": play_url,
                "vod_douban_score": vod_douban,
            }

        except Exception as e:
            print("_extract_detail error: {0}".format(e))
            return None

    def _extract_play_info(self, html, vod_id):
        """从详情页提取播放源与集数 (mxpro 多线路)
        源标签: data-dropdown-value="奇异" (按顺序)
        集数容器: <div class="module-list ..."> ... <a class="module-play-list-link" href="/vodplay/{vid}-{sid}-{nid}.html"><span>正片</span></a>
        """
        try:
            # 源名称 (按文档顺序)
            source_names = re.findall(
                r'class="module-tab-item[^"]*"[^>]*?data-dropdown-value="([^"]+)"',
                html
            )
            if not source_names:
                source_names = re.findall(
                    r'<span class="hl-text-site">([^<]+)</span>',
                    html
                )

            # 每个源的集数容器 (module-list 块, 可能带 id 等附加属性)
            block_pattern = re.compile(
                r'<div class="module-list[^"]*"[^>]*>.*?</div>\s*</div>\s*</div>',
                re.S
            )
            blocks = block_pattern.findall(html)

            if not blocks and not source_names:
                return "", ""

            episodes_per_block = []
            for b in blocks:
                eps = re.findall(
                    r'<a class="module-play-list-link" href="(/vodplay/(\d+)-(\d+)-(\d+)\.html)"[^>]*>\s*<span>([^<]*)</span>',
                    b
                )
                if not eps:
                    # 兼容无 <span> 包裹的情况
                    eps = re.findall(
                        r'<a class="module-play-list-link" href="(/vodplay/(\d+)-(\d+)-(\d+)\.html)"[^>]*>([^<]*)</a>',
                        b
                    )
                if eps:
                    episodes_per_block.append(eps)

            if not episodes_per_block:
                return "", ""

            play_from_list = []
            play_url_list = []

            for i, eps in enumerate(episodes_per_block):
                if i < len(source_names):
                    src_name = source_names[i]
                else:
                    src_name = "线路" + str(i + 1)

                episodes = []
                for href, evid, esid, enid, ep_text in eps:
                    ep_name = re.sub(r'<[^>]+>', '', ep_text).strip()
                    if not ep_name:
                        ep_name = "第" + str(len(episodes) + 1) + "集"
                    episodes.append(ep_name + "$" + href)

                if episodes:
                    play_from_list.append(src_name)
                    play_url_list.append("#".join(episodes))

            # 将「备用线路」排到最前 (保持其余顺序)
            paired = list(zip(play_from_list, play_url_list))
            backup = [p for p in paired if "备用" in p[0]]
            others = [p for p in paired if "备用" not in p[0]]
            paired = backup + others
            play_from_list = [p[0] for p in paired]
            play_url_list = [p[1] for p in paired]

            return ("$$$".join(play_from_list), "$$$".join(play_url_list))

        except Exception as e:
            print("_extract_play_info error: {0}".format(e))
            return "", ""

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            page = int(pg) if int(pg) >= 1 else 1

            # GET: /vodsearch/{关键词}-------------.html
            search_path = "/vodsearch/" + quote(key, safe="") + "-------------.html"
            if page > 1:
                search_path = "/vodsearch/" + quote(key, safe="") + "------------" + str(page) + "---.html"

            html = self._fetch(self.HOST + search_path)
            if not html:
                # 兜底: 带 wd 参数的表单式 GET
                search_path2 = "/vodsearch/-------------.html?wd=" + quote(key, safe="")
                html = self._fetch(self.HOST + search_path2)
            if not html:
                return result

            videos = self._parse_list(html)
            result["list"] = videos

        except Exception as e:
            print("searchContent error: {0}".format(e))
        return result

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        """播放: 从播放页提取 player_aaaa, 跟随 share 分享页得到真实 m3u8 直链
        encrypt=0: url 为明文
        encrypt=1: url 经过URL编码
        encrypt=2: url 经过base64编码
        """
        result = {"parse": 0, "playUrl": "", "url": "", "header": "", "jx": 0}
        try:
            play_path = id
            if "$" in play_path:
                play_path = play_path.split("$")[-1]
            play_path = play_path.strip()
            if not play_path.startswith("http"):
                if not play_path.startswith("/"):
                    play_path = "/" + play_path
                play_page_url = self.HOST + play_path
            else:
                play_page_url = play_path

            play_header = json.dumps({
                "User-Agent": self.UA,
                "Referer": self.HOST + "/",
            })

            html = self._fetch(play_page_url)
            if not html:
                result["parse"] = 1
                result["url"] = play_page_url
                result["header"] = play_header
                return result

            # 提取 player_aaaa
            player_data = None
            m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', html, re.S)
            if not m:
                m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*;', html, re.S)
            if not m:
                m = re.search(r'player_aaaa\s*=\s*(\{.*\})', html, re.S)

            if m:
                raw_json = m.group(1)
                try:
                    player_data = json.loads(raw_json)
                except:
                    try:
                        decoder = JSONDecoder()
                        player_data, _ = decoder.raw_decode(raw_json)
                    except:
                        pass

            if not player_data:
                result["parse"] = 1
                result["url"] = play_page_url
                result["header"] = play_header
                return result

            play_url = player_data.get("url", "")
            encrypt = player_data.get("encrypt", 0)

            if not play_url:
                result["parse"] = 1
                result["url"] = play_page_url
                result["header"] = play_header
                return result

            # 解密URL
            if encrypt == 1:
                try:
                    for _ in range(3):
                        decoded = unquote(play_url)
                        if decoded == play_url:
                            break
                        play_url = decoded
                except:
                    pass
            elif encrypt == 2:
                try:
                    play_url = base64.b64decode(play_url).decode("utf-8", errors="ignore")
                    try:
                        play_url = unquote(play_url)
                    except:
                        pass
                except:
                    pass

            try:
                play_url = html_unescape(play_url)
            except:
                pass
            play_url = play_url.strip()

            # 站点 url 为分享页 (play.xxx.com/share/xxx), 需再请求提取真实 m3u8
            if "/share/" in play_url and not self._is_direct_video(play_url):
                share_html = self._fetch(play_url)
                if share_html:
                    sm = re.search(r'const\s+url\s*=\s*"([^"]+)"', share_html)
                    if sm:
                        real_url = sm.group(1).strip()
                        if real_url.startswith("/"):
                            parsed = urlparse(play_url)
                            real_url = parsed.scheme + "://" + parsed.netloc + real_url
                        play_url = real_url

            # 站点URL为直链(m3u8/mp4)时, 直接播放
            if self._is_direct_video(play_url):
                result["parse"] = 0
                result["jx"] = 0
                result["url"] = play_url
                result["header"] = play_header
            else:
                # 非直链 -> 嗅探播放页
                result["parse"] = 1
                result["jx"] = 0
                result["url"] = play_page_url
                result["header"] = play_header

        except Exception as e:
            print("playerContent error: {0}".format(e))
            try:
                play_path = id
                if "$" in play_path:
                    play_path = play_path.split("$")[-1]
                play_path = play_path.strip()
                if not play_path.startswith("http"):
                    if not play_path.startswith("/"):
                        play_path = "/" + play_path
                    play_page_url = self.HOST + play_path
                else:
                    play_page_url = play_path
                result["parse"] = 1
                result["url"] = play_page_url
                result["header"] = json.dumps({
                    "User-Agent": self.UA,
                    "Referer": self.HOST + "/",
                })
            except:
                pass

        return result
