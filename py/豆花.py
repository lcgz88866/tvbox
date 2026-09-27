# -*- coding: utf-8 -*-
"""
==========================================================
  豆花影视 (dhvideo.cc) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎)
  框架: 豆花电影网 (自定义 Tailwind + 原生渲染, 非 maccms)
  更新: 2026-09-20  (修复分类/搜索/播放页被 WAF 拦截导致无数据)

   URL规则:
    首页:        /
    分类页:      /{cat}.html?area=&class=&year=&sort_field={sort}&page={N}
                (cat: dianying/dianshiju/zongyi/dongman/duanju)
    筛选(query): area(地区)/class(类型)/year(年份)/sort_field(play_hot最热|update最新)
    搜索:        /s?name={关键词}  (兜底 /search?wd= / /search.html?wd=)
    详情页:      /{type}/{hash}-{id}.html             (type: movie/tv/zongyi/dongman/duanju)
    选集链接:    /{type}/{hash}/{id}.html?origin={线路}&p={集号}
    图片:        /img/id/{hash}.jpg

  ★ 站点 WAF 反爬机制 (2026-09 实测, 必须处理否则分类/搜索全部无数据):
    1) 无参数 URL (首页/详情页) 直接 200 返回, 并种下会话 cookie: sion_id
    2) 带参数 URL (分类筛选/翻页/搜索/播放页) 若无 attack_key cookie,
       返回 HTTP 429 + PoW 挑战页 (标题"开心每一天", 含 passChallenge JS)
    3) 挑战页 JS 要求暴力求解: 找 i 使 sha1(hash + i) == target
       (i 取值很小, 通常 < 数千, 毫秒级可解)
    4) 将 attack_key={i} 拼到原 URL 重新请求, 且必须携带 sion_id cookie,
       通过后服务端种下 attack_key cookie (约 1 小时有效)
    5) 之后约 1 小时内所有请求免挑战; 过期后重复上述流程即可
    本文件 _fetch 已内置: Cookie 会话保持 + PoW 挑战自动应答, 全自动通过。
    注意: sion_id 是 cookie, 不是 URL 参数, 不要往 URL 上拼!

  卡片结构(网格):
    <a href="/movie/{hash}-{id}.html" class="... aspect-[2/3] ...">
      <img loading="lazy" class="lazy-image ..." alt="片名"
           data-src="/img/id/{hash}.jpg" decoding="async">
      <div ...>备注/更新</div>
      <div ...>片名</div>
    </a>

  详情页结构:
    标题:    <h1>片名</h1>  (或 <title>片名 - 豆花电影网</title>)
    元数据:  <span ...>导演</span><span ...><a>董润年</a></span>
            <span ...>主演</span><span ...><a>...</a></span>
            <h3>简介</h3><div ...>简介正文</div>
    播放源:  每个线路一个容器 <div id="list-{origin}">, 内含选集 <a>:
      <a href="/movie/{hash}/{id}.html?origin=lzm3u8&p=0"
         class="... episode-button" data-origin="lzm3u8" data-title="第1集" ...>...</a>
    线路标签来自 data-origin / ?origin= 参数 (如 lzm3u8 / bfzym3u8 / vip / 1080zyk ...)

  播放页结构:
    <script> window.xg_video_player_doc = {
        aa: JSON.parse('{"origin":"lzm3u8","url":"https://xxx/index.m3u8","title":"HD中字"}'),
        nexturl: JSON.parse('[]'), poster:'/img/id/{hash}.jpg', ... }
    直链即 aa.url (m3u8), parse=0 直接播放。

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
import time
import hashlib
import threading
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar
from urllib.parse import quote, unquote, urlencode
from html import unescape as html_unescape


class Spider(Spider):

    HOST = "https://dhvideo.cc"
    UA = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # 主分类 (来自站点导航栏)
    CATEGORIES = [
        {"type_name": "电影", "type_id": "dianying"},
        {"type_name": "电视剧", "type_id": "dianshiju"},
        {"type_name": "综艺", "type_id": "zongyi"},
        {"type_name": "动漫", "type_id": "dongman"},
        {"type_name": "短剧", "type_id": "duanju"},
    ]

    # 支持的类型前缀(详情/选集链接)
    TYPES = ("movie", "tv", "zongyi", "dongman", "duanju")

    def getName(self):
        return "豆花影视"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": self.UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.HOST + "/",
        }
        # WAF 挑战应答依赖 Cookie 会话: 全局共享一个带 CookieJar 的 opener
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._cookiejar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookiejar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._challenge_lock = threading.Lock()

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

    # ==================== HTTP (含 WAF 挑战自动应答) ====================
    def _urllib_get(self, url, headers=None, timeout=15):
        """单次 GET (走共享 opener, 自动维护 Cookie)。
        无论状态码如何都返回响应体文本 (429 挑战页原样返回, 由上层识别)。
        """
        try:
            req = urllib.request.Request(url, headers=headers or self.headers)
            with self._opener.open(req, timeout=timeout) as r:
                d = r.read()
                return d.decode("utf-8", errors="ignore") if d else ""
        except urllib.error.HTTPError as e:
            try:
                return e.read().decode("utf-8", errors="ignore")
            except:
                return ""
        except Exception:
            return ""

    def _is_challenge(self, html):
        """识别 WAF PoW 挑战页 (标题'开心每一天', 内含 passChallenge/attack_key JS)"""
        if not html:
            return False
        return "passChallenge" in html or ("attack_key" in html and "sha1" in html)

    def _solve_pow(self, html):
        """解 PoW 挑战: 求 i 使 sha1(hash + i) == target (i 值很小, 毫秒级)"""
        try:
            m = re.search(r"var\s+hash\s*=\s*'([0-9a-f]{40})'", html)
            t = re.search(r"var\s+target\s*=\s*'([0-9a-f]{40})'", html)
            if not (m and t):
                return None
            h = m.group(1).encode()
            target = t.group(1)
            sha1 = hashlib.sha1
            for i in range(10 * 1000 * 1000):
                if sha1(h + str(i).encode()).hexdigest() == target:
                    return i
        except Exception as e:
            print("_solve_pow error: {0}".format(e))
        return None

    def _ensure_session(self):
        """确保已持有站点会话 cookie(sion_id): 挑战验证依赖它。
        首次访问任意无参 URL 即可种下, 这里直接访问首页。
        """
        try:
            for c in self._cookiejar:
                if c.name == "sion_id":
                    return
        except Exception:
            pass
        url = self.HOST + "/"
        html = self._urllib_get(url)
        if html and self._is_challenge(html):
            self._pass_challenge(url, html)

    def _pass_challenge(self, url, html, max_retry=3):
        """自动通过 WAF 挑战: 解 PoW -> 带 attack_key 重试原 URL (须携带 sion_id cookie)"""
        ref = url
        for _ in range(max_retry):
            key = self._solve_pow(html)
            if key is None:
                break
            sep = "&" if "?" in url else "?"
            retry_url = url + sep + "attack_key=" + str(key)
            html = self._urllib_get(retry_url, headers={"Referer": ref})
            if not self._is_challenge(html):
                return html
        return html

    def _fetch(self, url, headers=None, timeout=15, retries=2):
        """GET请求, 返回HTML文本。
        流程: 共享opener请求(Cookie自动维护) -> 若遇 WAF 挑战页自动解 PoW 应答
        -> 失败重试 -> 最后兜底基类 self.fetch。
        """
        hdr = dict(headers or self.headers)
        req_url = url
        if not req_url.isascii():
            req_url = quote(req_url, safe=":/?&=%-._~")

        last_html = ""
        for attempt in range(retries + 1):
            html = self._urllib_get(req_url, hdr, timeout)
            if html and self._is_challenge(html):
                # 挑战应答加锁: 避免并发线程重复过挑战
                try:
                    self._challenge_lock.acquire()
                    self._ensure_session()
                    html = self._pass_challenge(req_url, html)
                except Exception as e:
                    print("_pass_challenge error: {0}".format(e))
                finally:
                    try:
                        self._challenge_lock.release()
                    except:
                        pass
            if html and not self._is_challenge(html):
                return html
            last_html = html or last_html
            if attempt < retries:
                time.sleep(2 + attempt * 2)

        # 兜底: 基类 fetch (兼容 TVBox 环境; 无 Cookie 会话, 仅作最后手段)
        try:
            rsp = self.fetch(url, headers=hdr)
            if isinstance(rsp, str) and rsp:
                return rsp
            if rsp and hasattr(rsp, 'text'):
                return rsp.text
            if rsp and hasattr(rsp, 'content'):
                return rsp.content.decode("utf-8", errors="ignore")
        except:
            pass
        return last_html

    # ==================== 工具 ====================
    def _fix_pic(self, pic):
        if not pic:
            return ""
        pic = html_unescape(pic).strip()
        if pic.startswith("http"):
            return pic
        if pic.startswith("//"):
            return "https:" + pic
        if not pic.startswith("/"):
            pic = "/" + pic
        return self.HOST + pic

    def _is_direct_video(self, url):
        """判断是否为直链视频(用于决定 parse 方式)"""
        if not url:
            return False
        lower = url.lower()
        for ext in [".m3u8", ".mp4", ".flv", ".avi", ".mkv", ".mov", ".wmv", ".ts"]:
            if ext in lower:
                return True
        return False

    def _js_unescape(self, s):
        """还原 JS 字符串字面量中转义:
           \\\\ -> \\ (JS 中双反斜杠表示单反斜杠, 如 \\u0026 实为 &)
           \\uXXXX -> 对应字符
           \\/ -> /
        """
        s = s.replace("\\\\", "\\")
        s = re.sub(r'\\u([0-9a-fA-F]{4})', lambda x: chr(int(x.group(1), 16)), s)
        s = s.replace("\\/", "/")
        return s

    def _extract_m3u8_url(self, html):
        """从播放页 window.xg_video_player_doc.aa.url 提取播放地址。
        aa.url 可能是:
          - 直链 m3u8 (如 https://xxx/index.m3u8)
          - /api/m3u8?... 主播放列表(master), 由播放器逐级解析
        注意: JS 字符串里属性名用 \\u0022、& 用 \\\\u0026(双反斜杠) 转义,
              需先按 JS 规则还原再 JSON 解析。
        """
        try:
            m = re.search(r'window\.xg_video_player_doc\s*=\s*\{', html)
            if not m:
                return ""
            seg = html[m.start(): m.start() + 8000]
            am = re.search(r'aa:\s*JSON\.parse\(\'([^\']+)\'\)', seg)
            if am:
                dec = self._js_unescape(am.group(1))
                try:
                    return json.loads(dec).get("url", "")
                except Exception:
                    pass
            # 兜底: 直接抓转义后的 url 字段值(兼容 url 值内含单引号导致上法失效)
            um = re.search(r'\\u0022url\\u0022:\\u0022(.*?)\\u0022', seg, re.S)
            if um:
                return self._js_unescape(um.group(1))
            return ""
        except Exception as e:
            print("_extract_m3u8_url error: {0}".format(e))
            return ""

    # ==================== 列表解析 ====================
    def _parse_list(self, html):
        """解析网格卡片: /{type}/{hash}-{id}.html , 图片 data-src , 标题 alt/内部文本
        按 key(type/hash-id) 去重, 标题与图片均取自同一张卡片, 不会错位。
        """
        items = {}
        order = []
        pat = re.compile(
            r'<a\b[^>]*href="/(movie|tv|zongyi|dongman|duanju)/([0-9a-f]+)-(\d+)\.html"[^>]*>(.*?)</a>',
            re.S
        )
        for m in pat.finditer(html):
            typ, h, vid, anchor = m.group(1), m.group(2), m.group(3), m.group(0)

            # 必须有封面图(排除无图的"立即播放"按钮卡)
            im = re.search(r'<img\b[^>]*\bdata-src="([^"]+)"', anchor)
            if not im:
                im = re.search(r'<img\b[^>]*\bsrc="([^"]+)"', anchor)
            if not im:
                continue
            pic = self._fix_pic(im.group(1))

            # 标题: img 的 alt 优先, 其次卡片内标题文本
            tm = re.search(r'\balt="([^"]+)"', anchor)
            title = tm.group(1).strip() if tm else ""
            if not title:
                tm2 = re.search(r'class="[^"]*title[^"]*"[^>]*>([^<]+)<', anchor)
                title = tm2.group(1).strip() if tm2 else ""
            if not title or title in ("立即播放",):
                continue

            key = typ + "/" + h + "-" + vid
            if key in items:
                continue
            # 备注(更新状态等)取卡片内最近的可读文本
            remark = ""
            rm = re.search(r'class="[^"]*absolute[^"]*"[^>]*>([^<]{1,20})<', anchor)
            if rm:
                remark = rm.group(1).strip()
            items[key] = {
                "vod_id": key,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            }
            order.append(key)
        return [items[k] for k in order]

    # ==================== 筛选配置 ====================
    # 站点筛选为 query 参数 (注意: 带参请求会触发 WAF 挑战, _fetch 已自动应答):
    #   area 地区 / class 类型 / year 年份 / sort_field 排序(play_hot最热|update最新)
    # 仅在用户实际选择筛选时才拼参数; 未选任何筛选时不带参数(无参URL零挑战直达)。
    def _build_filters(self):
        # 地区(全站统一, 取自电影分类页 SSR 筛选链接真实值)
        area_values = [
            {"n": "全部", "v": ""},
            {"n": "中国大陆", "v": "中国大陆"}, {"n": "美国", "v": "美国"}, {"n": "日本", "v": "日本"},
            {"n": "英国", "v": "英国"}, {"n": "中国香港", "v": "中国香港"}, {"n": "法国", "v": "法国"},
            {"n": "韩国", "v": "韩国"}, {"n": "加拿大", "v": "加拿大"}, {"n": "印度", "v": "印度"},
            {"n": "德国", "v": "德国"}, {"n": "意大利", "v": "意大利"}, {"n": "中国台湾", "v": "中国台湾"},
            {"n": "西班牙", "v": "西班牙"}, {"n": "泰国", "v": "泰国"}, {"n": "俄罗斯", "v": "俄罗斯"},
            {"n": "澳大利亚", "v": "澳大利亚"}, {"n": "比利时", "v": "比利时"}, {"n": "菲律宾", "v": "菲律宾"},
            {"n": "墨西哥", "v": "墨西哥"}, {"n": "丹麦", "v": "丹麦"}, {"n": "波兰", "v": "波兰"},
            {"n": "印度尼西亚", "v": "印度尼西亚"}, {"n": "土耳其", "v": "土耳其"}, {"n": "巴西", "v": "巴西"},
        ]
        year_values = [
            {"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"},
            {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"},
            {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"},
            {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"},
            {"n": "2015", "v": "2015"}, {"n": "2014", "v": "2014"}, {"n": "2013", "v": "2013"},
            {"n": "2012", "v": "2012"}, {"n": "2011", "v": "2011"}, {"n": "2010", "v": "2010"},
        ]
        sort_values = [
            {"n": "最热", "v": "play_hot"}, {"n": "最新", "v": "update"},
        ]
        # 各主分类的类型候选 (借鉴通用影视类型词表)
        class_map = {
            # 电影类型(取自电影分类页 SSR 筛选链接真实值)
            "dianying": ["剧情", "喜剧", "动作", "爱情", "惊悚", "犯罪", "恐怖", "悬疑", "冒险", "奇幻",
                         "科幻", "院线", "家庭", "历史", "战争", "纪录片", "古装", "音乐", "动画", "传记", "武侠", "运动", "西部", "短片"],
            "dianshiju": ["陆剧", "港剧", "日韩剧", "台泰剧", "短剧", "剧情", "古装", "喜剧",
                          "爱情", "悬疑", "惊悚", "武侠", "科幻", "都市", "青春", "家庭", "历史", "年代", "穿越", "谍战"],
            "zongyi": ["真人秀", "选秀", "音乐", "搞笑", "情感", "竞技", "竞演", "美食",
                       "旅游", "纪实", "脱口秀", "游戏互动", "生活"],
            "dongman": ["热血", "冒险", "格斗", "科幻", "推理", "校园", "恋爱", "少女",
                        "机战", "武侠", "魔幻", "爆笑", "竞技", "动作"],
            "duanju": ["古装", "现代", "爱情", "甜宠", "虐恋", "逆袭", "豪门", "搞笑", "悬疑", "都市"],
        }

        filters = {}
        for cat in self.CATEGORIES:
            tid = cat["type_id"]
            class_values = [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in class_map.get(tid, [])]
            filters[tid] = [
                {"key": "area", "name": "地区", "value": area_values},
                {"key": "class", "name": "类型", "value": class_values},
                {"key": "year", "name": "年份", "value": year_values},
                {"key": "sort_field", "name": "排序", "value": sort_values},
            ]
        return filters

    # ==================== 首页 ====================
    def homeContent(self, filter):
        result = {}
        try:
            classes = [{"type_name": c["type_name"], "type_id": c["type_id"]} for c in self.CATEGORIES]
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
    def _has_next_page(self, html):
        """自适应判断是否还有下一页(兼容 ?page=N 链接式分页)"""
        if re.search(r'(下一页|尾页)', html):
            return True
        # 页面内出现大于当前页的 page= 链接
        for pg in re.findall(r'[?&]page=(\d+)', html):
            if int(pg) > 1:
                return True
        return False

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if int(pg) >= 1 else 1
        ext = {}
        if extend:
            try:
                ext = json.loads(extend) if isinstance(extend, str) else dict(extend)
            except:
                ext = {}

        # 拼筛选 query 参数: area / class / year / sort_field
        # 注意: 只在用户实际选择时才拼; 未筛选不带参数(避免无谓触发 WAF 挑战)。
        # sion_id 是 cookie(由 _fetch/opener 自动维护), 不要拼到 URL 上!
        params = {}
        if ext.get("area"):
            params["area"] = ext["area"]
        if ext.get("class"):
            params["class"] = ext["class"]
        if ext.get("year"):
            params["year"] = ext["year"]
        if ext.get("sort_field"):
            params["sort_field"] = ext["sort_field"]
        if page > 1:
            params["page"] = page

        base = self.HOST + "/" + tid + ".html"
        url = base + ("?" + urlencode(params) if params else "")
        result = {"list": [], "page": page, "pagecount": 1, "limit": 90, "total": 9999}
        try:
            html = self._fetch(url)
            if html:
                result["list"] = self._parse_list(html)
                # 检测到分页则允许继续翻页, 否则到此为止(避免重复首页)
                result["pagecount"] = 999 if self._has_next_page(html) else page
        except Exception as e:
            print("categoryContent error: {0}".format(e))
        return result

    # ==================== 详情 ====================
    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            detail_url = self.HOST + "/" + vod_id
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
        """提取 导演/主演 等 <span>标签:文字</span><span>值(<a>名</a>)</span>"""
        pat = re.escape(label) + r'</span>\s*<span[^>]*>(.*?)</span>'
        m = re.search(pat, html, re.S)
        if not m:
            return ""
        content = m.group(1)
        links = re.findall(r'<a[^>]*>([^<]+)</a>', content)
        if links:
            return "/".join([l.strip() for l in links if l.strip()])
        return re.sub(r'<[^>]+>', '', content).strip()

    def _extract_detail(self, html, vod_id):
        try:
            # 标题
            title = ""
            m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            if m:
                title = m.group(1).strip()
            if not title:
                m = re.search(r'<title>([^<]+)</title>', html)
                if m:
                    title = m.group(1).split(" - ")[0].split("_")[0].strip()
            if not title:
                return None

            # 封面: 直接用 /img/id/{hash}.jpg (hash 来自 vod_id; vod_id 形如 type/hash-id)
            hm = re.search(r'(?:^|/)(movie|tv|zongyi|dongman|duanju)/([0-9a-f]+)-', vod_id)
            pic = ""
            if hm:
                pic = self.HOST + "/img/id/" + hm.group(2) + ".jpg"
            if not pic:
                m = re.search(r'data-src="(/img/id/[^"]+)"', html)
                if m:
                    pic = self._fix_pic(m.group(1))

            # 元数据
            director = self._field(html, "导演")
            actor = self._field(html, "主演")
            area = self._field(html, "地区") or self._field(html, "国家")
            vod_year = self._field(html, "年份")
            vod_class = self._field(html, "类型")
            vod_remarks = self._field(html, "状态") or self._field(html, "更新")

            # 简介
            vod_content = ""
            m = re.search(r'简介</h3>\s*<div[^>]*>(.*?)</div>', html, re.S)
            if m:
                vod_content = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if not vod_content:
                m = re.search(r'class="[^"]*reset-style[^"]*"[^>]*>(.*?)</div>', html, re.S)
                if m:
                    vod_content = re.sub(r'<[^>]+>', '', m.group(1)).strip()

            play_from, play_url = self._extract_play(html)

            return {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "type_name": vod_class,
                "vod_year": vod_year,
                "vod_area": area,
                "vod_remarks": vod_remarks,
                "vod_actor": actor,
                "vod_director": director,
                "vod_content": vod_content,
                "vod_play_from": play_from,
                "vod_play_url": play_url,
            }
        except Exception as e:
            print("_extract_detail error: {0}".format(e))
            return None

    def _extract_play(self, html):
        """从详情页提取多线路 + 各线路选集
        选集: <a ... href="/{type}/{hash}/{id}.html?origin=X&p=N" data-origin="X" data-title="第N集">
        按 origin 分组, 线路顺序按出现顺序去重。
        """
        try:
            ep_pat = re.compile(
                r'<a\b([^>]*)href="/(movie|tv|zongyi|dongman|duanju)/([0-9a-f]+)/(\d+)\.html'
                r'\?origin=([^&"\s]+)&amp;p=(\d+)"([^>]*)>',
                re.S
            )
            sources_order = []
            episodes_by_source = {}
            for m in ep_pat.finditer(html):
                attrs = m.group(1) + m.group(7)
                typ, h, gid, origin_q, p = m.group(2), m.group(3), m.group(4), m.group(5), m.group(6)
                do = re.search(r'data-origin="([^"]+)"', attrs)
                dt = re.search(r'data-title="([^"]*)"', attrs)
                origin = do.group(1).strip() if do else origin_q
                ep_name = dt.group(1).strip() if dt else ("第" + str(int(p) + 1) + "集")
                if not origin:
                    continue
                play_path = "/{0}/{1}/{2}.html?origin={3}&p={4}".format(typ, h, gid, origin, p)
                if origin not in episodes_by_source:
                    episodes_by_source[origin] = []
                    sources_order.append(origin)
                episodes_by_source[origin].append(ep_name + "$" + play_path)

            if not sources_order:
                return "", ""

            play_from = "$$$".join(sources_order)
            play_url = "$$$".join(
                "#".join(episodes_by_source[o]) for o in sources_order
            )
            return play_from, play_url
        except Exception as e:
            print("_extract_play error: {0}".format(e))
            return "", ""

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            page = int(pg) if int(pg) >= 1 else 1
            # 站点搜索表单 action="/s" name="name"
            url = self.HOST + "/s?name=" + quote(key, safe="")
            if page > 1:
                url += "&page=" + str(page)
            html = self._fetch(url)
            items = self._parse_list(html) if html else []
            if not items:
                # 兜底格式
                for alt in ("/search?wd=" + quote(key, safe=""),
                            "/search.html?wd=" + quote(key, safe="")):
                    html = self._fetch(self.HOST + alt)
                    items = self._parse_list(html) if html else []
                    if items:
                        break
            result["list"] = items
        except Exception as e:
            print("searchContent error: {0}".format(e))
        return result

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        """播放: 从播放页 window.xg_video_player_doc.aa.url 取播放地址
        id 形如 /{type}/{hash}/{gid}.html?origin=X&p=N
        aa.url 可能是直链 m3u8 或 /api/m3u8?... 主播放列表(master),
        统一 parse=0 交给播放器解析(HLS 会逐级拉取变体)。
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
                "Referer": play_page_url,
            })

            html = self._fetch(play_page_url)
            if not html:
                result["parse"] = 1
                result["url"] = play_page_url
                result["header"] = play_header
                return result

            play_url = self._extract_m3u8_url(html)
            if not play_url:
                result["parse"] = 1
                result["url"] = play_page_url
                result["header"] = play_header
                return result

            if not play_url.startswith("http"):
                if not play_url.startswith("/"):
                    play_url = "/" + play_url
                play_url = self.HOST + play_url

            # 直链视频 或 /api/m3u8 主列表: 均由播放器直接解析
            if self._is_direct_video(play_url) or "/api/m3u8" in play_url or play_url.endswith(".m3u8"):
                result["parse"] = 0
                result["jx"] = 0
                result["url"] = play_url
                result["header"] = play_header
            else:
                # 其它未知形态: 退回嗅探播放页
                result["parse"] = 1
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
                    "Referer": play_page_url,
                })
            except:
                pass
        return result
