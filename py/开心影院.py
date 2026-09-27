# -*- coding: utf-8 -*-
"""
==========================================================
  开心影院 (www.kxyy1.cc) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎)
  更新: 2026-08-08

  URL规则:
    分类/筛选页: /vodshow/{cid}-{area}-{sort}-{class}--------{page}---{year}.html
      字段(12段, 索引0-11):
        0:cid  1:area  2:sort  3:class
        4-7:空  8:page  9-10:空  11:year
    详情页: /voddetail/{vid}.html
    播放页: /vodplay/{vid}-{sid}-{nid}.html
    搜索:   /index.php/ajax/suggest?mid=1&wd={kw}&limit=20 (JSON)

  播放解密:
    1. 播放页内 player_data JSON 含 url, from, encrypt
    2. encrypt=0: URL直接可用 (unescape解码)
    3. bfzym3u8/modum3u8/lzm3u8/bdm3u8: 直接m3u8 URL
    4. NBY源: NBY-XMYAES加密, 两步解密:
       a. GET /static/player/nby.php?get_signed_url=1&url={NBY_URL} → signed_url
       b. GET /static/player/nby.php{signed_url} → jmurl (实际播放地址)

  配置方式:
  {
    "sites": [{
      "key": "py_kxyy",
      "name": "开心影院",
      "type": 3,
      "api": "py_kxyy",
      "searchable": 1,
      "quickSearch": 0,
      "filterable": 1,
      "ext": "https://your-host/py_kxyy.py"
    }]
  }
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
from urllib.parse import quote, unquote
from html import unescape as html_unescape


class Spider(Spider):

    HOST = "https://www.kxyy1.cc"
    UA = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # ==================== 分类配置 ====================
    CATEGORIES = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "电视剧", "type_id": "2"},
        {"type_name": "综艺", "type_id": "3"},
        {"type_name": "动漫", "type_id": "4"},
        {"type_name": "纪录片", "type_id": "24"},
        {"type_name": "短剧", "type_id": "26"},
    ]

    # 各分类的类型(class)选项 (不含"不限", 第一项默认为空)
    CLASS_MAP = {
        "1": ["科幻", "剧情", "惊悚", "爱情", "古装", "动作", "悬疑", "犯罪",
              "谍战", "历史", "喜剧", "奇幻", "家庭", "青春", "冒险", "纪录",
              "动画", "人物", "文化", "其他"],
        "2": ["爱情", "古装", "悬疑", "都市", "喜剧", "战争", "剧情", "青春",
              "历史", "网剧", "奇幻", "冒险", "励志", "犯罪", "商战", "恐怖",
              "穿越", "农村", "人物", "商业", "生活", "其他"],
        "3": ["真人秀", "脱口秀", "喜剧", "音乐", "爱情", "家庭", "歌舞"],
        "4": ["少年", "热血", "科幻", "冒险", "动画", "爱情", "奇幻", "武侠",
              "悬疑", "惊悚", "剧情", "音乐", "恐怖", "喜剧", "儿童"],
        "24": [],
        "26": ["短剧"],
    }

    # 各分类的地区选项
    AREA_MAP = {
        "1": ["中国大陆", "中国香港", "中国台湾", "美国", "日本", "韩国", "泰国",
              "英国", "法国", "德国", "意大利", "印度", "马来西亚"],
        "2": ["中国大陆", "中国香港", "中国台湾", "美国", "日本", "韩国", "泰国",
              "英国", "法国", "德国", "意大利"],
        "3": ["中国大陆", "港台", "韩国", "欧美", "其他"],
        "4": ["中国大陆", "日本"],
        "24": [],
        "26": ["中国大陆"],
    }

    # 排序选项
    SORT_VALUES = [
        {"n": "更新时间", "v": "time"},
        {"n": "近期热门", "v": "hits_week"},
        {"n": "豆瓣评分", "v": "douban_score"},
    ]

    def getName(self):
        return "开心影院"

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
        year_values = [{"n": "不限", "v": ""}]
        for y in range(2026, 1999, -1):
            year_values.append({"n": str(y), "v": str(y)})
        for y in ["90年代", "80年代", "70年代"]:
            year_values.append({"n": y, "v": y})

        for cat in self.CATEGORIES:
            cat_id = cat["type_id"]
            cat_filters = []

            # 类型
            class_values = [{"n": "不限", "v": ""}]
            for c in self.CLASS_MAP.get(cat_id, []):
                class_values.append({"n": c, "v": c})
            if len(class_values) > 1:
                cat_filters.append({"key": "class", "name": "类型", "value": class_values})

            # 地区
            area_values = [{"n": "不限", "v": ""}]
            for a in self.AREA_MAP.get(cat_id, []):
                area_values.append({"n": a, "v": a})
            if len(area_values) > 1:
                cat_filters.append({"key": "area", "name": "地区", "value": area_values})

            # 年份
            cat_filters.append({"key": "year", "name": "年份", "value": year_values})

            # 排序
            cat_filters.append({"key": "sort", "name": "排序", "value": self.SORT_VALUES})

            filters[cat_id] = cat_filters
        return filters

    # ==================== HTTP ====================
    def _fetch(self, url, timeout=15, referer=None):
        """GET请求, 返回HTML文本"""
        if not url.isascii():
            url = quote(url, safe=":/?&=%-._~")
        try:
            h = dict(self.headers)
            if referer:
                h["Referer"] = referer
            req = urllib.request.Request(url, headers=h)
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=self._ssl_ctx)
            )
            with opener.open(req, timeout=timeout) as r:
                data = r.read()
                return data.decode("utf-8", errors="ignore") if data else ""
        except urllib.error.HTTPError as e:
            try:
                return e.read().decode("utf-8", errors="ignore")
            except:
                return ""
        except Exception:
            return ""

    def _fetch_json(self, url, timeout=15, referer=None):
        """GET请求, 返回JSON"""
        try:
            h = dict(self.headers)
            h["Accept"] = "application/json, text/javascript, */*; q=0.01"
            if referer:
                h["Referer"] = referer
            req = urllib.request.Request(url, headers=h)
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=self._ssl_ctx)
            )
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", errors="ignore"))
        except Exception:
            return {}

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

    def _build_show_url(self, cid, extend, page):
        """构建分类筛选URL
        格式: /vodshow/{cid}-{area}-{sort}-{class}--------{page}---{year}.html
        """
        area = ""
        sort = ""
        cls = ""
        year = ""
        if extend:
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except:
                    extend = {}
            area = extend.get("area", "") or ""
            sort = extend.get("sort", "") or ""
            cls = extend.get("class", "") or ""
            year = extend.get("year", "") or ""

        fields = [
            str(cid),
            quote(area, safe="") if area else "",
            sort if sort else "",
            quote(cls, safe="") if cls else "",
            "", "", "", "",
            str(page), "", "",
            year if year else "",
        ]
        return "/vodshow/" + "-".join(fields) + ".html"

    # ==================== 列表解析 ====================
    def _parse_list(self, html):
        """解析视频列表卡片
        卡片结构:
          <div class="card card-sm card-link">
            <a href="/voddetail/vid.html" class="...cover2">
              <img src="封面URL" ...>
              <span class="badge ...">备注</span>
            </a>
            <div class="card-body">
              <h3 class="card-title">标题</h3>
              <p class="text-muted">日期</p>
            </div>
          </div>
        """
        items = []
        seen = set()
        # 匹配所有含 /voddetail/ 链接的卡片
        pattern = re.compile(
            r'<div class="card card-sm card-link">\s*'
            r'<a[^>]*href="(/voddetail/(\d+)\.html)"[^>]*>(.*?)</a>'
            r'(.*?)</div>',
            re.S
        )
        for m in pattern.finditer(html):
            vid = m.group(2)
            if vid in seen:
                continue
            a_content = m.group(3)
            body_content = m.group(4)

            # 标题
            title = ""
            tm = re.search(r'<h3[^>]*>([^<]+)</h3>', body_content)
            if tm:
                title = tm.group(1).strip()
            if not title:
                tm = re.search(r'title="([^"]+)"', m.group(0))
                if tm:
                    title = tm.group(1).strip()
            if not title:
                continue

            seen.add(vid)

            # 封面
            pic = ""
            pm = re.search(r'<img[^>]*src="([^"]+)"', a_content)
            if pm:
                pic_url = pm.group(1)
                if not pic_url.startswith("data:"):
                    pic = self._fix_pic(pic_url)

            # 备注
            remark = ""
            rm = re.search(r'<span[^>]*class="badge[^"]*"[^>]*>([^<]+)</span>', a_content)
            if rm:
                remark = rm.group(1).strip()
            if not remark:
                rm = re.search(r'<p[^>]*class="text-muted"[^>]*>([^<]+)</p>', body_content)
                if rm:
                    remark = rm.group(1).strip()

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
        classes = []
        for c in self.CATEGORIES:
            classes.append({"type_name": c["type_name"], "type_id": c["type_id"]})
        result["class"] = classes
        result["filters"] = self._build_filters()
        html = self._fetch(self.HOST + "/")
        if html:
            result["list"] = self._parse_list(html)
        return result

    def homeVideoContent(self):
        result = {"list": []}
        html = self._fetch(self.HOST + "/")
        if html:
            result["list"] = self._parse_list(html)[:24]
        return result

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}
        try:
            page = int(pg) if pg else 1
        except:
            page = 1
        if page < 1:
            page = 1
        result["page"] = page

        path = self._build_show_url(tid, extend, page)
        html = self._fetch(self.HOST + path)
        if not html:
            return result

        items = self._parse_list(html)
        result["list"] = items

        # 解析总页数
        # 找 "尾页" 链接: /vodshow/{cid}--------{max_page}---.html
        page_m = re.search(r'/vodshow/\d+--------(\d+)---\.html[^"]*"\s*[^>]*>[^<]*尾页', html)
        if page_m:
            result["pagecount"] = int(page_m.group(1))
            result["limit"] = len(items) if items else 24
            result["total"] = result["pagecount"] * result["limit"]
        else:
            # 如果没有尾页链接, 检查是否有下一页
            if items and len(items) >= 20:
                result["pagecount"] = page + 1
            else:
                result["pagecount"] = page

        return result

    # ==================== 详情 ====================
    def detailContent(self, ids):
        vid = ids[0]
        url = self.HOST + "/voddetail/" + str(vid) + ".html"
        html = self._fetch(url)
        if not html:
            return {}

        vod = {"vod_id": vid}

        # 标题
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if m:
            vod["vod_name"] = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        else:
            m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                name = m.group(1).strip()
                # 去掉 "高清完整版在线观看" 等后缀
                name = re.sub(r'[-—]\s*.*$', '', name)
                vod["vod_name"] = name

        # 封面 - 详情页主图在 cover-lg-max-25 div 内
        m = re.search(r'cover-lg-max-25[^>]*>\s*<img[^>]*src="([^"]+)"', html)
        if not m:
            m = re.search(r'<img[^>]*referrerPolicy="no-referrer"[^>]*src="([^"]+)"', html)
        if not m:
            m = re.search(r'<img[^>]*class="[^"]*object-cover[^"]*"[^>]*src="([^"]+)"', html)
        if m:
            vod["vod_pic"] = self._fix_pic(m.group(1))

        # 元数据 - 从 <p><strong>字段：</strong>值</p> 结构提取
        def _extract_field(field_name):
            """提取 <strong>字段：</strong>后到 </p> 之间的内容"""
            pattern = r'<strong>\s*' + re.escape(field_name) + r'\s*[：:]\s*</strong>(.*?)</p>'
            m = re.search(pattern, html, re.S)
            if m:
                text = re.sub(r'<[^>]+>', ' ', m.group(1)).strip()
                text = re.sub(r'\s+', ' ', text)
                return text
            return ""

        # 导演
        vod["vod_director"] = _extract_field("导演")

        # 主演
        vod["vod_actor"] = _extract_field("主演")

        # 类型
        vod["type_name"] = _extract_field("类型")

        # 地区
        area = _extract_field("制片国家/地区")
        if area:
            vod["vod_area"] = area.strip("[]")

        # 语言
        vod["vod_lang"] = _extract_field("语言")

        # 年份 - 优先从首播/上映日期提取, 其次从标题提取
        m = re.search(r'<strong>\s*(?:首播|上映)\s*[：:]\s*</strong>\s*(\d{4})', html)
        if m:
            vod["vod_year"] = m.group(1)
        else:
            m = re.search(r'\((\d{4})\)', vod.get("vod_name", ""))
            if m:
                vod["vod_year"] = m.group(1)

        # 简介 - 从meta description提取剧情部分
        m = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
        if m:
            desc = html_unescape(m.group(1)).strip()
            # 截取 "剧情：" 之后的内容
            dm = re.search(r'剧情[：:](.*)', desc, re.S)
            if dm:
                desc = dm.group(1).strip()
            vod["vod_content"] = desc

        # ==================== 播放源 ====================
        # 源名称: 从 nav-tabs 的 data-bs-toggle="tab" 链接提取
        nav_links = re.findall(
            r'<a[^>]*data-bs-toggle="tab"[^>]*>(.*?)</a>', html, re.S
        )
        source_names = []
        for nt in nav_links:
            name = re.sub(r'<[^>]+>', '', nt).strip()
            name = name.replace('&nbsp;', '').strip()
            name = re.sub(r'\s*\d+$', '', name).strip()  # 去掉集数
            if name:
                source_names.append(name)

        # 所有播放链接: /vodplay/{vid}-{sid}-{nid}.html
        play_links = re.findall(
            r'href="/vodplay/(\d+)-(\d+)-(\d+)\.html"[^>]*>([^<]*)<', html
        )

        # 按 sid 分组
        sources = {}
        for vid_p, sid, nid, ep_name in play_links:
            if sid not in sources:
                sources[sid] = []
            sources[sid].append((nid, ep_name.strip()))

        # 构建播放列表
        play_from_list = []
        play_url_parts = []

        for idx, sid in enumerate(sorted(sources.keys())):
            # 源名称
            if idx < len(source_names):
                sname = source_names[idx]
            else:
                sname = "源" + str(sid)
            play_from_list.append(sname)

            # 集数列表
            eps = sources[sid]
            ep_urls = []
            for nid, ep_name in eps:
                play_path = "/vodplay/{}-{}-{}.html".format(vid, sid, nid)
                ep_urls.append("{}${}".format(ep_name, play_path))
            play_url_parts.append("#".join(ep_urls))

        vod["vod_play_from"] = "$$$".join(play_from_list)
        vod["vod_play_url"] = "$$$".join(play_url_parts)

        return {"list": [vod]}

    # ==================== 播放 ====================
    def _extract_player_data(self, html):
        """从播放页提取 player_data 的关键字段"""
        m = re.search(r'player_data\s*=\s*(\{)', html)
        if not m:
            return None
        start = m.start(1)
        # 手动匹配花括号
        depth = 0
        end = start
        for i in range(start, len(html)):
            if html[i] == '{':
                depth += 1
            elif html[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        raw = html[start:end]

        result = {}
        # encrypt
        m = re.search(r'"encrypt"\s*:\s*(\d+)', raw)
        if m:
            result['encrypt'] = int(m.group(1))
        # from
        m = re.search(r'"from"\s*:\s*"([^"]*)"', raw)
        if m:
            result['from'] = m.group(1)
        # url
        m = re.search(r'"url"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
        if m:
            url_val = m.group(1)
            url_val = url_val.replace('\\"', '"').replace('\\/', '/').replace('\\\\', '\\')
            result['url'] = url_val
        return result

    def _decrypt_nby(self, nby_url):
        """NBY源两步解密"""
        try:
            nby_php = self.HOST + "/static/player/nby.php"
            referer = nby_php + "?url=" + quote(nby_url, safe="")

            # Step 1: 获取 signed_url
            step1_url = nby_php + "?get_signed_url=1&url=" + quote(nby_url, safe="")
            data1 = self._fetch_json(step1_url, referer=referer)
            signed_url = data1.get("signed_url", "")
            if not signed_url:
                return ""

            # 补全URL
            if signed_url.startswith("?"):
                signed_url = nby_php + signed_url
            elif signed_url.startswith("/"):
                signed_url = self.HOST + signed_url
            elif not signed_url.startswith("http"):
                signed_url = nby_php + "?" + signed_url

            # Step 2: 获取实际播放地址
            data2 = self._fetch_json(signed_url, referer=nby_php)
            jmurl = data2.get("jmurl", "")
            return jmurl
        except Exception:
            return ""

    def playerContent(self, flag, id, vipFlags):
        """获取播放地址
        id: 播放路径 /vodplay/{vid}-{sid}-{nid}.html
        """
        result = {"parse": 0, "header": "", "playUrl": "", "url": ""}

        play_path = id
        if not play_path.startswith("http"):
            play_path = self.HOST + play_path

        html = self._fetch(play_path, referer=self.HOST + "/")
        if not html:
            return result

        pd = self._extract_player_data(html)
        if not pd:
            return result

        url = pd.get("url", "")
        from_id = pd.get("from", "")
        encrypt = pd.get("encrypt", 0)

        if not url:
            return result

        # 解密
        if encrypt == 1:
            try:
                url = html_unescape(unquote(base64.b64decode(url).decode("utf-8", errors="ignore")))
            except:
                pass
        elif encrypt == 2:
            try:
                url = html_unescape(base64.b64decode(url).decode("utf-8", errors="ignore"))
            except:
                pass
        else:
            url = html_unescape(url)

        # NBY源特殊处理
        if url.startswith("NBY-") or "XMYAES" in url:
            real_url = self._decrypt_nby(url)
            if real_url:
                result["url"] = real_url
                result["header"] = json.dumps({
                    "User-Agent": self.UA,
                    "Referer": self.HOST + "/",
                })
                return result

        # 直接可播放的URL
        if url.startswith("http"):
            result["url"] = url
            result["header"] = json.dumps({
                "User-Agent": self.UA,
                "Referer": self.HOST + "/",
            })

        return result

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        """搜索 - 使用AJAX suggest接口"""
        result = {"list": []}
        try:
            page = int(pg) if pg else 1
        except:
            page = 1

        url = self.HOST + "/index.php/ajax/suggest?mid=1&wd=" + quote(key) + "&limit=20"
        data = self._fetch_json(url)
        if not data or data.get("code") != 1:
            return result

        items = data.get("list", [])
        for item in items:
            vid = str(item.get("id", ""))
            name = item.get("name", "")
            pic = item.get("pic", "")
            if vid and name:
                result["list"].append({
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": self._fix_pic(pic) if pic else "",
                    "vod_remarks": "",
                })

        result["total"] = len(result["list"])
        result["pagecount"] = 1
        return result
