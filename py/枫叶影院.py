# -*- coding: utf-8 -*-
# 枫叶4k影院 - www.cd-zj.com
# 苹果CMS V10 + e模板，player_aaaa直接返回m3u8
# 分类页有验证码保护，用ddddocr识别验证码绕过
# 搜索用Ajax suggest API，无需验证码
import re
import sys
import json
import ssl
import gzip
import time
import random
import html as html_lib
import urllib.parse
import urllib.request
import urllib.error
import http.cookiejar

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def getName(self):
        return "枫叶影院"

    def init(self, extend=""):
        self.host = "https://www.cd-zj.com"
        self.ua = "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Referer": self.host,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.cats = [
           {"type_name": "腾讯SVIP精选", "type_id": "label_qq"},
            {"type_name": "优酷SVIP精选", "type_id": "label_youku"},
            {"type_name": "B站SVIP精选", "type_id": "label_bli"},
             {"type_name": "电影", "type_id": "1"},
            {"type_name": "电视剧", "type_id": "2"},
            {"type_name": "综艺", "type_id": "3"},
            {"type_name": "动漫", "type_id": "4"},
            {"type_name": "短剧", "type_id": "5"},
            
        ]
        # 子分类映射: 主分类ID -> 子分类选项列表
        # 网站用子分类ID而非文本筛选, 直接替换type_id
        self._subcats = {
            "1": [
                {"n": "全部", "v": "1"},
                {"n": "动作片", "v": "6"},
                {"n": "喜剧片", "v": "7"},
                {"n": "恐怖片", "v": "8"},
                {"n": "科幻片", "v": "9"},
                {"n": "爱情片", "v": "10"},
                {"n": "剧情片", "v": "11"},
                {"n": "战争片", "v": "12"},
                {"n": "纪录片", "v": "20"},
            ],
            "2": [
                {"n": "全部", "v": "2"},
                {"n": "国产剧", "v": "13"},
                {"n": "日韩剧", "v": "15"},
                {"n": "海外剧", "v": "16"},
            ],
            "3": [
                {"n": "全部", "v": "3"},
                {"n": "大陆综艺", "v": "21"},
                {"n": "日韩综艺", "v": "22"},
            ],
            "4": [
                {"n": "全部", "v": "4"},
                {"n": "国产动漫", "v": "25"},
                {"n": "日韩动漫", "v": "26"},
            ],
            "5": [
                {"n": "全部", "v": "5"},
            ],
        }
        self._year_opts = [
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
            {"n": "2014", "v": "2014"},
            {"n": "2013", "v": "2013"},
            {"n": "2012", "v": "2012"},
            {"n": "2011", "v": "2011"},
            {"n": "2010", "v": "2010"},
            {"n": "2009", "v": "2009"},
            {"n": "2008", "v": "2008"},
        ]
        # SSL
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE
        # Cookie管理 (urllib)
        self._cj = http.cookiejar.CookieJar()
        # requests Session (优先使用, cookie管理更好)
        self._session = None
        self._captcha_verified = False
        # ddddocr (验证码识别)
        self._ocr = None
        try:
            import ddddocr
            self._ocr = ddddocr.DdddOcr(show_ad=False)
        except:
            pass

    def getDependence(self):
        return ["ddddocr"]

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def action(self, action):
        pass

    def destroy(self):
        pass

    # ==================== HTTP请求 ====================
    def _get_session(self):
        """获取requests Session (优先), 不可用时返回None"""
        if self._session is not None:
            return self._session
        try:
            import requests as req_mod
            import urllib3
            urllib3.disable_warnings()
            self._session = req_mod.Session()
            self._session.headers.update(self.headers)
            self._session.verify = False
            return self._session
        except ImportError:
            return None

    def _http_req_urllib(self, url, method="GET", data=None, tries=4):
        """urllib HTTP请求 (备用)；带重试、keep-alive 与 gzip 处理，容忍服务端偶发断连(RemoteDisconnected)"""
        for _ in range(tries):
            try:
                headers = dict(self.headers)
                headers["Connection"] = "keep-alive"
                headers["Accept-Encoding"] = "gzip, deflate"
                req = urllib.request.Request(url, headers=headers, method=method, data=data)
                handler = urllib.request.HTTPSHandler(context=self._ssl_ctx)
                opener = urllib.request.build_opener(handler, urllib.request.HTTPCookieProcessor(self._cj))
                with opener.open(req, timeout=15) as resp:
                    raw = resp.read()
                    if "gzip" in resp.headers.get("Content-Encoding", ""):
                        raw = gzip.decompress(raw)
                    return raw, resp.status
            except urllib.error.HTTPError as e:
                try:
                    return e.read(), e.code
                except Exception:
                    return None, e.code
            except Exception:
                time.sleep(0.5)
        return None, 0

    def _is_captcha_page(self, text):
        return "系统安全验证" in text

    # ==================== 验证码绕过 ====================
    def _solve_captcha(self, target_url):
        """用ddddocr识别验证码绕过
        优先用requests Session (cookie管理更好), 备用urllib
        """
        session = self._get_session()

        if session and self._ocr:
            return self._solve_captcha_requests(session, target_url)
        else:
            return self._solve_captcha_urllib(target_url)

    def _solve_captcha_requests(self, session, target_url):
        """requests + ddddocr 方式"""
        import random as _r
        # 触发验证码
        try:
            session.get(target_url, timeout=10)
        except:
            pass

        for attempt in range(20):
            try:
                cap_url = self.host + "/captcha.php?type=code&r=" + str(_r.random())
                img_resp = session.get(cap_url, timeout=5, headers={"Accept": "image/webp,*/*"})
                result = self._ocr.classification(img_resp.content)
                # 清理OCR结果: o/O->0, l/I->1, S/s->5
                result = result.replace("o", "0").replace("O", "0")
                result = result.replace("l", "1").replace("I", "1")
                result = result.replace("S", "5").replace("s", "5")

                if len(result) == 4 and result.isdigit():
                    verify_resp = session.post(
                        self.host + "/captcha.php?type=verify",
                        data={"check": result},
                        timeout=5,
                    )
                    if '"code":1' in verify_resp.text:
                        self._captcha_verified = True
                        return True
            except:
                pass
            time.sleep(0.3)
        return False

    def _solve_captcha_urllib(self, target_url):
        """urllib + ddddocr (无requests时备用)"""
        if not self._ocr:
            return False
        import random as _r
        # 触发验证码
        self._http_req_urllib(target_url)

        for attempt in range(20):
            try:
                cap_url = self.host + "/captcha.php?type=code&r=" + str(_r.random())
                handler = urllib.request.HTTPSHandler(context=self._ssl_ctx)
                opener = urllib.request.build_opener(handler, urllib.request.HTTPCookieProcessor(self._cj))
                req = urllib.request.Request(cap_url, headers=dict(self.headers, Accept="image/webp,*/*"))
                resp = opener.open(req, timeout=5)
                img_data = resp.read()
                result = self._ocr.classification(img_data)
                result = result.replace("o", "0").replace("O", "0")
                result = result.replace("l", "1").replace("I", "1")
                result = result.replace("S", "5").replace("s", "5")

                if len(result) == 4 and result.isdigit():
                    post_data = ("check=" + urllib.parse.quote(result)).encode("utf-8")
                    req2 = urllib.request.Request(
                        self.host + "/captcha.php?type=verify",
                        data=post_data,
                        headers=dict(self.headers, **{"Content-Type": "application/x-www-form-urlencoded"}),
                        method="POST",
                    )
                    resp2 = opener.open(req2, timeout=5)
                    if b'"code":1' in resp2.read():
                        self._captcha_verified = True
                        return True
            except:
                pass
            time.sleep(0.3)
        return False

    # ==================== fetch_html ====================
    def fetch_html(self, url):
        """获取HTML, 自动处理验证码"""
        session = self._get_session()
        if session:
            for _ in range(3):
                try:
                    rsp = session.get(url, timeout=15)
                    text = rsp.text
                    if not self._is_captcha_page(text):
                        return text
                    if not self._ocr:
                        return ""
                    if self._solve_captcha_requests(session, url):
                        rsp = session.get(url, timeout=15)
                        text = rsp.text
                        if not self._is_captcha_page(text):
                            return text
                except Exception:
                    return ""
            return ""
        # 备用: urllib
        for _ in range(3):
            try:
                data, status = self._http_req_urllib(url)
                if not data:
                    return ""
                text = data.decode("utf-8", errors="ignore")
                if not self._is_captcha_page(text):
                    return text
                if not self._ocr:
                    return ""
                if self._solve_captcha_urllib(url):
                    data, status = self._http_req_urllib(url)
                    if data:
                        text = data.decode("utf-8", errors="ignore")
                        if not self._is_captcha_page(text):
                            return text
            except:
                return ""
        return ""

    # ==================== 图片URL处理 ====================
    def _fix_pic(self, pic):
        """处理图片URL: 百度代理、相对路径、HTML实体"""
        if not pic:
            return ""
        pic = pic.replace("&amp;", "&")
        # 百度图床代理: 提取src参数
        if "gimg0.baidu.com" in pic or "gimg.baidu.com" in pic:
            m = re.search(r'[?&]src=([^&]+)', pic)
            if m:
                pic = m.group(1)
                if "gimg0.baidu.com" in pic or "gimg.baidu.com" in pic:
                    m2 = re.search(r'[?&]src=([^&]+)', pic)
                    if m2:
                        pic = m2.group(1)
        if pic.startswith("http"):
            return pic
        if pic.startswith("//"):
            return "https:" + pic
        # 提取的src可能没有协议前缀 (如 images.hzqingshan.com/...)
        if re.match(r'^[a-z0-9][a-z0-9.-]+\.[a-z]{2,}', pic):
            return "https://" + pic
        if not pic.startswith("/"):
            pic = "/" + pic
        return self.host + pic

    # ==================== 列表解析 ====================
    def _parse_list(self, html):
        """解析视频列表 (public-list-exp格式)"""
        items = []
        seen = set()
        for m in re.finditer(
            r'<a[^>]*class="[^"]*public-list-exp[^"]*"[^>]*href="/detail/(\d+)\.html"[^>]*>(.*?)</a>',
            html, re.S
        ):
            vod_id = m.group(1)
            if vod_id in seen:
                continue
            seen.add(vod_id)
            a_tag = m.group(0)
            a_content = m.group(2)

            title_m = re.search(r'title="([^"]+)"', a_tag)
            vod_name = title_m.group(1).strip() if title_m else ""

            pic_m = re.search(r'data-src="([^"]+)"', a_tag) or re.search(r'src="([^"]+)"', a_tag)
            vod_pic = self._fix_pic(pic_m.group(1)) if pic_m else ""

            remarks_m = re.search(r'<span[^>]*class="[^"]*public-list-prb[^"]*"[^>]*>(.*?)</span>', a_content, re.S)
            vod_remarks = re.sub(r'<[^>]+>', '', remarks_m.group(1)).strip() if remarks_m else ""

            if vod_name:
                items.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": vod_remarks,
                })
        return items

    # ==================== URL构造 ====================
    def _build_list_url(self, tid, year="", page="1"):
        """构建分类URL
        cupfox-list格式: /cupfox-list/{tid}-----------{year}.html
        label格式: /label/{name}.html 或 /label/{name}/page/{page}.html
        """
        if tid.startswith("label_"):
            label_name = tid[6:]  # 去掉 "label_" 前缀
            if int(page) > 1:
                return self.host + "/label/" + label_name + "/page/" + str(page) + ".html"
            return self.host + "/label/" + label_name + ".html"

        # cupfox-list格式
        p_year = year if year else ""
        p_page = str(page) if int(page) > 1 else ""
        # 位置: [0]tid [1-7]空 [8]page [9-10]空 [11]year
        parts = [str(tid), "", "", "", "", "", "", "", p_page, "", "", p_year]
        return self.host + "/cupfox-list/" + "-".join(parts) + ".html"

    # ==================== 首页 ====================
    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        try:
            result["class"] = self.cats
            # 构建筛选器
            for cat in self.cats:
                tid = cat["type_id"]
                if tid.startswith("label_"):
                    # label分类无筛选
                    result["filters"][tid] = []
                else:
                    filters_list = [
                        {"key": "class", "name": "类型", "value": self._subcats.get(tid, [{"n": "全部", "v": tid}])},
                        {"key": "year", "name": "年份", "value": self._year_opts},
                    ]
                    result["filters"][tid] = filters_list
            html = self.fetch_html(self.host)
            if html:
                result["list"] = self._parse_list(html)[:30]
        except Exception as e:
            print("homeContent error: {0}".format(e))
        return result

    def homeVideoContent(self):
        pass

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg) if pg else 1, "pagecount": 1, "limit": 24, "total": 0}
        try:
            # label分类: 直接用label URL, 无筛选
            if tid.startswith("label_"):
                page = str(int(pg)) if int(pg) >= 1 else "1"
                url = self._build_list_url(tid, "", page)
                html = self.fetch_html(url)
                if html:
                    result["list"] = self._parse_list(html)
                    result["total"] = len(result["list"])
                    page_m = re.search(r'当前(\d+)/(\d+)页', html)
                    if page_m:
                        result["pagecount"] = int(page_m.group(2))
                    elif result["list"]:
                        result["pagecount"] = int(pg) + 1
                return result

            # 如果选了类型筛选, 用子分类ID替换tid
            actual_tid = tid
            if extend:
                cls = extend.get("class", "")
                if cls:
                    actual_tid = cls
                year = extend.get("year", "")
            else:
                year = ""

            page = str(int(pg)) if int(pg) >= 1 else "1"
            url = self._build_list_url(actual_tid, year, page)
            html = self.fetch_html(url)
            if html:
                result["list"] = self._parse_list(html)
                result["total"] = len(result["list"])
                # 解析总页数
                page_m = re.search(r'当前(\d+)/(\d+)页', html)
                if page_m:
                    result["pagecount"] = int(page_m.group(2))
                elif result["list"]:
                    result["pagecount"] = int(pg) + 1
        except Exception as e:
            print("categoryContent error: {0}".format(e))
        return result

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        """搜索 - 抓取HTML搜索结果页(站点已关闭suggest接口); 结果页带验证码, 由fetch_html自动处理"""
        result = {"list": []}
        try:
            if not key:
                return result
            wd = urllib.parse.quote(str(key))
            page = int(pg) if pg else 1
            # 与站点搜索页分页链接一致: /cupfox-search/{wd}----------{page}---.html
            url = self.host + "/cupfox-search/" + wd + "----------" + str(page) + "---.html"
            html = self.fetch_html(url)
            if html:
                result["list"] = self._parse_list(html)
        except Exception as e:
            print("searchContent error: {0}".format(e))
        return result

    # ==================== 详情 ====================
    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            detail_html = self.fetch_html(self.host + "/detail/" + str(vod_id) + ".html")
            if not detail_html:
                return result

            vod_name = ""
            title_m = re.search(r'<h3 class="slide-info-title hide">([^<]+)</h3>', detail_html)
            if title_m:
                vod_name = title_m.group(1).strip()

            vod_pic = ""
            pic_m = re.search(r'data-src="([^"]+)"', detail_html)
            if pic_m:
                vod_pic = self._fix_pic(pic_m.group(1))

            vod_director = ""
            director_m = re.search(r'<strong class="r6">导演[：:]</strong>([^<]+)</div>', detail_html, re.S)
            if director_m:
                vod_director = director_m.group(1).strip()

            vod_actor = ""
            actor_m = re.search(r'<strong class="r6">主演[：:]</strong>([^<]+)</div>', detail_html, re.S)
            if actor_m:
                vod_actor = actor_m.group(1).strip()

            vod_remarks = ""
            state_m = re.search(r'<strong class="r6">连载\s*[：:]\s*</strong>([^<]+)</div>', detail_html, re.S)
            if state_m:
                vod_remarks = state_m.group(1).strip()

            vod_content = ""
            content_m = re.search(r'<div id="height_limit"[^>]*>(.*?)</div>', detail_html, re.S)
            if content_m:
                vod_content = re.sub(r'<[^>]+>', '', content_m.group(1)).strip()
                vod_content = vod_content.replace('简介:', '').replace('简介：', '').strip()

            # 播放列表
            line_names = []
            tab_match = re.search(r'<div class="anthology-tab[^"]*">(.*?)</div>', detail_html, re.S)
            if tab_match:
                tab_html = tab_match.group(1)
                for a_tag in re.finditer(r'<a[^>]*class="[^"]*swiper-slide[^"]*"[^>]*>(.*?)</a>', tab_html, re.S):
                    name_raw = a_tag.group(1)
                    name_raw = re.sub(r'<span class="badge">.*?</span>', '', name_raw)
                    name = re.sub(r'<[^>]+>', '', name_raw).strip()
                    name = name.replace('&nbsp;', ' ').strip()
                    name = re.sub(r'\s*[（\(]?\d+集[）\)]?\s*$', '', name)
                    name = re.sub(r'\s*第\d+集\s*$', '', name)
                    name = name.strip()
                    if name:
                        line_names.append(name)
            if not line_names:
                line_names = ["线路1"]

            def find_closing_div(html, start_pos):
                count = 1
                pos = start_pos
                while pos < len(html) and count > 0:
                    next_open = html.find('<div', pos)
                    next_close = html.find('</div>', pos)
                    if next_close == -1:
                        break
                    if next_open == -1 or next_close < next_open:
                        count -= 1
                        pos = next_close + 6
                    else:
                        count += 1
                        pos = next_open + 4
                    if pos >= len(html):
                        break
                return pos

            boxes = []
            start = 0
            while True:
                m = re.search(r'<div[^>]*class="[^"]*anthology-list-box[^"]*"[^>]*>', detail_html[start:])
                if not m:
                    break
                box_start = start + m.start()
                box_end = find_closing_div(detail_html, box_start + len(m.group()))
                if box_end <= box_start:
                    break
                boxes.append(detail_html[box_start:box_end])
                start = box_end

            lines = []
            if not boxes:
                eps = re.findall(r'href="/play/(\d+)-(\d+)-(\d+)\.html"[^>]*>(.*?)</a>', detail_html, re.S)
                if eps:
                    eps.sort(key=lambda x: int(x[2]))
                    urls = []
                    for ep_id, ep_sid, ep_nid, ep_name_raw in eps:
                        ep_name = re.sub(r'<[^>]+>', '', ep_name_raw).strip()
                        if not ep_name:
                            ep_name = "第{0}集".format(ep_nid)
                        urls.append("{0}${1}-{2}-{3}".format(ep_name, ep_id, ep_sid, ep_nid))
                    if urls:
                        lines.append((line_names[0], urls))
            else:
                name_counter = {}
                for idx, box_html in enumerate(boxes):
                    eps = re.findall(r'href="/play/(\d+)-(\d+)-(\d+)\.html"[^>]*>(.*?)</a>', box_html, re.S)
                    if eps:
                        eps.sort(key=lambda x: int(x[2]))
                        urls = []
                        for ep_id, ep_sid, ep_nid, ep_name_raw in eps:
                            ep_name = re.sub(r'<[^>]+>', '', ep_name_raw).strip()
                            if not ep_name:
                                ep_name = "第{0}集".format(ep_nid)
                            urls.append("{0}${1}-{2}-{3}".format(ep_name, ep_id, ep_sid, ep_nid))
                        if urls:
                            if idx < len(line_names):
                                base = line_names[idx]
                            else:
                                base = "线路"
                            if base in name_counter:
                                name_counter[base] += 1
                                line_name = "{0}{1}".format(base, name_counter[base])
                            else:
                                name_counter[base] = 1
                                line_name = base
                            lines.append((line_name, urls))

            def sort_key(item):
                name = item[0]
                core = re.sub(r'\d+$', '', name)
                if '至臻' in core:
                    return 0
                elif '自营' in core or '自选' in core:
                    return 1
                elif '蓝光' in core:
                    return 2
                else:
                    return 3
            lines.sort(key=sort_key)

            play_from = [line[0] for line in lines]
            play_url = ["#".join(line[1]) for line in lines]

            result["list"] = [{
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_director": vod_director,
                "vod_actor": vod_actor,
                "vod_content": vod_content,
                "vod_remarks": vod_remarks,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }]
        except Exception as e:
            print("detailContent error: {0}".format(e))
        return result

    # ==================== 播放 ====================
    def playerContent(self, flag, pid, vipFlags):
        result = {}
        try:
            parts = pid.split("-")
            if len(parts) != 3:
                result["parse"] = 1
                result["url"] = self.host + "/play/" + pid + ".html"
                result["header"] = json.dumps({"User-Agent": self.ua, "Referer": self.host})
                return result

            vid, sid, nid = parts
            play_url = self.host + "/play/" + vid + "-" + sid + "-" + nid + ".html"
            html = self.fetch_html(play_url)
            if not html:
                result["parse"] = 1
                result["url"] = play_url
                result["header"] = json.dumps({"User-Agent": self.ua, "Referer": self.host})
                return result

            m = re.search(r'var player_aaaa=(\{.*?\})</script>', html, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                    url = data.get("url", "")
                    if url and url.startswith("http"):
                        result["parse"] = 0
                        result["url"] = url
                        result["header"] = json.dumps({"User-Agent": self.ua, "Referer": self.host})
                        return result
                except:
                    pass

            result["parse"] = 1
            result["url"] = play_url
            result["header"] = json.dumps({"User-Agent": self.ua, "Referer": self.host})
        except Exception as e:
            print("playerContent error: {0}".format(e))
            result["parse"] = 1
            result["url"] = self.host + "/play/" + str(pid) + ".html"
            result["header"] = json.dumps({"User-Agent": self.ua, "Referer": self.host})
        return result

    def localProxy(self, params):
        return [404, "text/plain", b"Not supported"]
