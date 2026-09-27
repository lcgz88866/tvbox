#coding=utf-8
#!/usr/bin/python
# QuickVOD (www.quickvod.fun) - MacCMS V10 + JSUI 主题
#
# 原理:
#   1. MacCMS V10 + JSUI主题(ThinkPHP框架), 标准URL模式
#   2. 分类: /vodshow/{type_id}.html, 筛选: /vodshow/{type}-{area}-{by}-{class}-{lang}-{letter}---{page}---{year}.html
#   3. 详情: /voddetail/{vod_id}.html
#   4. 播放: /vodplay/{vod_id}-{sid}-{nid}.html → player_aaaa → qplay API → 解密
#   5. 搜索: /vodsearch/-------------{wd}--{pg}.html
#   6. 无验证码
#
# 播放解密流程 (纯Python, 无需Node.js):
#   1. 获取播放页 /vodplay/{id}-{sid}-{nid}.html
#   2. 提取 player_aaaa 变量 (含 url=vid, from=线路名)
#   3. POST /qplay/api.php body: vid={vid} → 获取加密URL
#   4. 根据 urlmode 解密:
#      - urlmode=1: Decode1 (Base64+XOR(md5("test"))+Base64+字符替换)
#      - urlmode=2: Decode2 (Base64+自定义字母表每3取1替换)
#   5. 返回解密后的m3u8/mp4直链 (parse=0)
#
# 速度: 快 (纯Python解密, 无外部依赖, 无验证码)

import sys
import re
import json
import base64
import hashlib
import urllib.parse

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def getName(self):
        return "QuickVOD"

    def init(self, extend=""):
        self.host = "https://www.quickvod.fun"
        self.ua = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        self._play_header = json.dumps({
            "User-Agent": self.ua,
            "Referer": self.host + "/",
        })

        # 分类 (MacCMS标准分类ID)
        self.cats = [
            {"type_name": "电影", "type_id": "1"},
            {"type_name": "剧集", "type_id": "2"},
            {"type_name": "综艺", "type_id": "3"},
            {"type_name": "动漫", "type_id": "4"},
        ]

        # 预编译正则
        self._re_player_aaaa = re.compile(r'player_aaaa\s*=\s*(\{.*?\})\s*</?script', re.DOTALL)
        self._re_player_aaaa_alt = re.compile(r'player_aaaa\s*=\s*(\{.*?\});', re.DOTALL)

        # 解密参数
        self._xor_key = hashlib.md5(b"test").hexdigest()  # "098f6bcd4621d373cade4e832627b4f6"
        self._decode2_alphabet = "PXhw7UT1B0a9kQDKZsjIASmOezxYG4CHo5Jyfg2b8FLpEvRr3WtVnlqMidu6cN"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|ts)(\?|#|$)', url, re.I))

    def manualVideoVCandidate(self, items):
        return []

    # ===== 解密函数 (纯Python实现, 已验证) =====

    def _b64_decode(self, s):
        """标准Base64解码 (兼容JS的atob)"""
        s = s.strip()
        # 去除非Base64字符
        s = re.sub(r'[^A-Za-z0-9+/=]', '', s)
        # 补齐padding
        missing = len(s) % 4
        if missing:
            s += "=" * (4 - missing)
        try:
            raw = base64.b64decode(s)
            try:
                return raw.decode('utf-8')
            except UnicodeDecodeError:
                return raw.decode('latin-1')
        except:
            return ""

    def _custom_str_decode(self, encoded):
        """Decode1.customStrDecode: Base64解码 → XOR(md5("test")) → Base64解码"""
        # Step 1: Base64解码
        step1 = self._b64_decode(encoded)
        if not step1:
            return ""

        # Step 2: XOR with md5("test") key
        key = self._xor_key
        xored = []
        for i, ch in enumerate(step1):
            k = key[i % len(key)]
            xored.append(chr(ord(ch) ^ ord(k)))
        xored_str = "".join(xored)

        # Step 3: Base64解码XOR结果
        result = self._b64_decode(xored_str)
        return result

    def _de_string(self, map1, map2, input_str):
        """Decode1.deString: 字母替换映射"""
        result = []
        for ch in input_str:
            if re.match(r'^[a-zA-Z]$', ch):
                if ch in map2:
                    try:
                        idx = map1.index(ch)
                        result.append(map2[idx])
                    except (ValueError, IndexError):
                        result.append(ch)
                else:
                    result.append(ch)
            else:
                result.append(ch)
        return "".join(result)

    def _decode1(self, encoded_url):
        """Decode1.get (urlmode=1): customStrDecode → 分割 → Base64解码 → deString替换"""
        try:
            # Step 1: customStrDecode
            decrypted = self._custom_str_decode(encoded_url)
            if not decrypted:
                return ""

            # Step 2: 分割 by '/'
            parts = decrypted.split('/')
            if len(parts) < 3:
                return ""

            # Step 3: URL部分 = parts[2:] joined with '/'
            url_encoded = '/'.join(parts[2:])

            # Step 4: Base64解码URL
            decoded_url = self._b64_decode(url_encoded)
            if not decoded_url:
                return ""

            # Step 5: 解析映射表
            try:
                map1 = json.loads(self._b64_decode(parts[1]))
            except:
                map1 = []
            try:
                map2 = json.loads(self._b64_decode(parts[0]))
            except:
                map2 = []

            # Step 6: deString替换
            if map1 and map2:
                final_url = self._de_string(map1, map2, decoded_url)
            else:
                final_url = decoded_url

            return final_url
        except:
            return ""

    def _decode2(self, encoded_url):
        """Decode2.get (urlmode=2): atob → 自定义字母表每3取1替换"""
        try:
            # Step 1: Base64解码
            decoded = base64.b64decode(encoded_url).decode('latin-1')
            if not decoded:
                return ""

            # Step 2: 从索引1开始, 每3个字符取1个, 替换
            alphabet = self._decode2_alphabet
            result = []
            i = 1
            while i < len(decoded):
                ch = decoded[i]
                idx = alphabet.find(ch)
                if idx == -1:
                    result.append(ch)
                else:
                    result.append(alphabet[(idx + 59) % 62])
                i += 3

            return "".join(result)
        except:
            return ""

    def _decode_url(self, encoded_url, urlmode):
        """根据urlmode选择解密方式"""
        if urlmode == 1:
            return self._decode1(encoded_url)
        elif urlmode == 2:
            return self._decode2(encoded_url)
        return encoded_url

    # ===== HTTP辅助 =====

    def _fetch_text(self, url, headers=None):
        """安全获取页面文本"""
        try:
            resp = self.fetch(url, headers=headers or self.headers)
            if not resp:
                return ""
            text = resp.text if hasattr(resp, 'text') else str(resp)
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="replace")
            return text
        except:
            return ""

    def _make_headers(self, extra=None):
        h = dict(self.headers)
        if extra:
            h.update(extra)
        return h

    # ===== 首页 =====

    def homeContent(self, filter):
        result = {}
        classes = []
        for c in self.cats:
            classes.append({"type_name": c["type_name"], "type_id": c["type_id"]})
        result["class"] = classes
        result["filters"] = self._get_filters()
        return result

    def _get_filters(self):
        """筛选器配置 (JSUI主题标准)"""
        filters = {}

        common_area = [
            {"n": "全部", "v": ""},
            {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
            {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"},
            {"n": "韩国", "v": "韩国"}, {"n": "日本", "v": "日本"},
            {"n": "英国", "v": "英国"}, {"n": "法国", "v": "法国"},
            {"n": "泰国", "v": "泰国"}, {"n": "印度", "v": "印度"},
            {"n": "其他", "v": "其他"},
        ]

        common_year = self._year_options()

        common_by = [
            {"n": "按时间", "v": "time"},
            {"n": "按人气", "v": "hits"},
            {"n": "按评分", "v": "score"},
        ]

        for c in self.cats:
            tid = c["type_id"]
            filters[tid] = [
                {"key": "area", "name": "地区", "value": common_area},
                {"key": "year", "name": "年份", "value": common_year},
                {"key": "by", "name": "排序", "value": common_by},
            ]

        return filters

    def _year_options(self):
        years = [{"n": "全部", "v": ""}]
        for y in range(2026, 2009, -1):
            years.append({"n": str(y), "v": str(y)})
        return years

    def homeVideoContent(self):
        """首页推荐"""
        url = self.host + "/vodshow/1.html"
        html = self._fetch_text(url)
        videos = self._parse_list(html)
        return {"list": videos}

    # ===== 分类列表 =====

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        extend = extend or {}

        url = self._build_category_url(tid, page, extend)
        html = self._fetch_text(url)
        videos = self._parse_list(html)

        pagecount = self._parse_pagecount(html, page)

        result = {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": len(videos) if videos else 20,
            "total": pagecount * 20,
        }
        return result

    def _build_category_url(self, tid, page, extend):
        """构建分类筛选URL (JSUI主题格式)
        /vodshow/{type}-{area}-{by}-{class}-{lang}-{letter}---{page}---{year}.html
        """
        area = extend.get("area", "")
        by = extend.get("by", "")
        cls = extend.get("class", "")
        lang = extend.get("lang", "")
        letter = extend.get("letter", "")
        year = extend.get("year", "")

        def q(s):
            return urllib.parse.quote(str(s), safe='') if s else ""

        segments = [tid, q(area), q(by), q(cls), q(lang), q(letter),
                    "", "", str(page), "", "", q(year)]
        return self.host + "/vodshow/" + "-".join(segments) + ".html"

    # ===== 搜索 =====

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = self.host + f"/vodsearch/-------------{keyword}--{page}.html"
        html = self._fetch_text(url)
        videos = self._parse_list(html)
        return {"list": videos}

    # ===== 详情 =====

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        detail_url = self.host + f"/voddetail/{vod_id}.html"
        html = self._fetch_text(detail_url)

        if not html:
            return {"list": []}

        # 提取元数据
        vod_name = self._extract_meta(html, ["片名", "名称", "名字", "title"])
        if not vod_name:
            title_m = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h1>', html)
            if title_m:
                vod_name = title_m.group(1).strip()
            else:
                title_m = re.search(r'<title>([^<\-]+)', html)
                if title_m:
                    vod_name = title_m.group(1).strip()
        if not vod_name:
            vod_name = vod_id

        vod_pic = self._extract_pic(html)
        vod_remarks = self._extract_meta(html, ["状态", "备注", "更新"])
        vod_year = self._extract_meta(html, ["年份", "年代"])
        vod_area = self._extract_meta(html, ["地区", "区域"])
        vod_actor = self._extract_meta(html, ["主演", "演员", "配音"])
        vod_director = self._extract_meta(html, ["导演"])
        vod_content = self._extract_meta(html, ["简介", "剧情", "介绍", "内容"])
        type_name = self._extract_meta(html, ["类型", "分类"])

        vod = {
            "vod_id": vod_id,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "vod_remarks": vod_remarks,
            "vod_year": vod_year,
            "vod_area": vod_area,
            "vod_actor": vod_actor,
            "vod_director": vod_director,
            "vod_content": vod_content,
            "type_name": type_name,
        }

        # 提取选集列表
        flags, episodes = self._extract_episodes(html, vod_id)

        if flags and episodes:
            vod["vod_play_from"] = "$$$".join(flags)
            vod["vod_play_url"] = "$$$".join(["#".join(ep) for ep in episodes])
        else:
            vod["vod_play_from"] = "QuickVOD"
            vod["vod_play_url"] = "无播放源$$"

        return {"list": [vod]}

    # ===== 播放 =====

    def playerContent(self, flag, id, vipFlags):
        """播放: 获取播放页 → 提取player_aaaa → 调用qplay API → 解密URL → 返回直链"""
        play_id = id.strip().rstrip('/').replace('.html', '')

        # 构建播放页URL
        play_url = self.host + f"/vodplay/{play_id}.html"
        html = self._fetch_text(play_url)

        if not html:
            return {"parse": 1, "url": play_url, "header": self._play_header}

        # 提取 player_aaaa
        player_aaaa = self._extract_player_aaaa(html)
        if not player_aaaa:
            return {"parse": 1, "url": play_url, "header": self._play_header}

        # 获取 vid (player_aaaa.url 即为qplay API的vid参数)
        vid = player_aaaa.get("url", "")
        if not vid:
            return {"parse": 1, "url": play_url, "header": self._play_header}

        # encrypt处理 (MacCMS标准: 0=明文, 1=URL编码, 2=Base64)
        encrypt = player_aaaa.get("encrypt", 0)
        if encrypt == 1:
            vid = urllib.parse.unquote(vid)
        elif encrypt == 2:
            try:
                vid = urllib.parse.unquote(base64.b64decode(vid).decode("utf-8"))
            except:
                pass

        # 调用 qplay API
        api_resp = self.post(
            self.host + "/qplay/api.php",
            data="vid=" + urllib.parse.quote(vid, safe=''),
            headers=self._make_headers({
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, */*; q=0.01",
                "Referer": self.host + "/qplay/index.php",
            })
        )

        text = api_resp.text if hasattr(api_resp, 'text') else str(api_resp)
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")

        # 清理PHP警告信息
        json_start = text.find('{')
        if json_start > 0:
            text = text[json_start:]

        try:
            api_data = json.loads(text)
        except:
            return {"parse": 1, "url": play_url, "header": self._play_header}

        # 检查API响应
        if api_data.get("code") != 200:
            # 即使code非200, data.url仍可能包含加密URL (回退URL)
            pass

        data = api_data.get("data", {})
        encoded_url = data.get("url", "")
        urlmode = data.get("urlmode", 0)

        if not encoded_url:
            return {"parse": 1, "url": play_url, "header": self._play_header}

        # 解密URL
        decoded_url = self._decode_url(encoded_url, urlmode)

        if decoded_url and self.isVideoFormat(decoded_url):
            return {"parse": 0, "url": decoded_url, "header": self._play_header}

        # 解密结果不是视频格式, 尝试直接检查encoded_url
        if self.isVideoFormat(encoded_url):
            return {"parse": 0, "url": encoded_url, "header": self._play_header}

        # 回退: 让TVBox内置解析处理
        return {"parse": 1, "url": play_url, "header": self._play_header}

    # ===== HTML解析辅助 =====

    def _extract_player_aaaa(self, html):
        """从HTML中提取player_aaaa变量"""
        match = self._re_player_aaaa.search(html)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        match = self._re_player_aaaa_alt.search(html)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        # 尝试更宽松的匹配
        match = re.search(r'player_aaaa\s*=\s*(\{[^}]+\})', html)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        return None

    def _parse_list(self, html):
        """解析视频列表页 (支持多种JSUI/MacCMS模板)"""
        videos = []

        # 模式1: module-items (JSUI标准)
        blocks = re.findall(r'<a[^>]*class="[^"]*module-item[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL)
        if not blocks:
            # 模式2: module-poster-item
            blocks = re.findall(r'<a[^>]*class="[^"]*module-poster-item[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL)
        if not blocks:
            # 模式3: stui-vodlist__item
            blocks = re.findall(r'<li[^>]*class="[^"]*stui-vodlist__item[^"]*"[^>]*>(.*?)</li>', html, re.DOTALL)
        if not blocks:
            # 模式4: 通用 - 从href提取
            blocks = re.findall(r'<a[^>]*href="/voddetail/(\d+)"[^>]*>(.*?)</a>', html, re.DOTALL)
            for vod_id, block in blocks:
                title = self._extract_title_from_block(block)
                if not title:
                    continue
                pic = self._extract_pic_from_block(block)
                remarks = self._extract_remarks_from_block(block)
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remarks,
                })
            if videos:
                return videos

        for block in blocks:
            # 提取链接
            href_match = re.search(r'href="/voddetail/(\d+)"', block)
            if not href_match:
                href_match = re.search(r'href="(/voddetail/[^"]+)"', block)
                if href_match:
                    vod_id = href_match.group(1).rstrip('/').split('/')[-1].replace('.html', '')
                else:
                    continue
            else:
                vod_id = href_match.group(1)

            title = self._extract_title_from_block(block)
            if not title:
                continue

            pic = self._extract_pic_from_block(block)
            remarks = self._extract_remarks_from_block(block)

            videos.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })

        return videos

    def _extract_title_from_block(self, block):
        """从卡片HTML中提取标题"""
        # title属性
        m = re.search(r'title="([^"]+)"', block)
        if m:
            return m.group(1).strip()
        # 文本内容
        m = re.search(r'class="[^"]*title[^"]*"[^>]*>([^<]+)</', block)
        if m:
            return m.group(1).strip()
        m = re.search(r'class="[^"]*name[^"]*"[^>]*>([^<]+)</', block)
        if m:
            return m.group(1).strip()
        m = re.search(r'alt="([^"]+)"', block)
        if m:
            return m.group(1).strip()
        return ""

    def _extract_pic_from_block(self, block):
        """从卡片HTML中提取图片"""
        m = re.search(r'data-src="([^"]+)"', block)
        if m:
            return m.group(1)
        m = re.search(r'data-original="([^"]+)"', block)
        if m:
            return m.group(1)
        m = re.search(r'src="([^"]+\.(?:jpg|png|webp)[^"]*)"', block, re.I)
        if m:
            return m.group(1)
        return ""

    def _extract_remarks_from_block(self, block):
        """从卡片HTML中提取备注"""
        m = re.search(r'class="[^"]*(?:note|remarks|tag|prb|text)[^"]*"[^>]*>([^<]+)</', block)
        if m:
            return m.group(1).strip()
        return ""

    def _parse_pagecount(self, html, current_page):
        """解析总页数"""
        # 末页/尾页链接
        match = re.search(r'href="([^"]*)"[^>]*>[末尾]页', html)
        if match:
            pm = re.search(r'---(\d+)---', match.group(1))
            if pm:
                return int(pm.group(1))
            pm = re.search(r'-(\d+)\.html', match.group(1))
            if pm:
                return int(pm.group(1))
        # 从分页链接提取最大页码
        pages = re.findall(r'---(\d+)---', html)
        if pages:
            return max(int(p) for p in pages)
        pages = re.findall(r'-(\d+)\.html', html)
        if pages:
            return max(int(p) for p in pages)
        return 9999

    def _extract_meta(self, html, labels):
        """从详情页提取元数据 (支持多个标签名)"""
        for label in labels:
            # 模式1: <em class="cor4">标签：</em>值</li>
            pattern = f'<em[^>]*>{label}[：:]?</em>(.*?)</li>'
            match = re.search(pattern, html, re.DOTALL)
            if match:
                content = match.group(1)
                # 提取链接文本
                links = re.findall(r'>([^<]+)</a>', content)
                if links:
                    texts = [l.strip() for l in links if l.strip() and l.strip() != '&nbsp;']
                    if texts:
                        return " ".join(texts)
                # 提取span文本
                span = re.search(r'<span>([^<]*)</span>', content)
                if span:
                    return span.group(1).strip()
                # 纯文本
                text = re.sub(r'<[^>]+>', '', content).strip()
                text = text.replace('&nbsp;', ' ').strip()
                if text:
                    return text

            # 模式2: <span class="...">标签：</span><span>值</span>
            pattern2 = f'{label}[：:]?</span>.*?<span[^>]*>([^<]+)</span>'
            match2 = re.search(pattern2, html, re.DOTALL)
            if match2:
                return match2.group(1).strip()

            # 模式3: <div class="...">标签：值</div>
            pattern3 = f'{label}[：:]?([^<]+)</'
            match3 = re.search(pattern3, html)
            if match3:
                val = match3.group(1).strip()
                if val:
                    return val

        return ""

    def _extract_pic(self, html):
        """从详情页提取海报图片"""
        # 多种模式匹配
        patterns = [
            r'alt="[^"]*海报[^"]*"[^>]*data-src="([^"]+)"',
            r'data-src="([^"]+)"[^>]*alt="[^"]*海报[^"]*"',
            r'class="[^"]*module-item-pic[^"]*"[^>]*>.*?data-src="([^"]+)"',
            r'class="[^"]*module-info-poster[^"]*"[^>]*>.*?data-src="([^"]+)"',
            r'class="[^"]*stui-vodlist__thumb[^"]*"[^>]*data-original="([^"]+)"',
            r'<img[^>]*class="[^"]*lazyload[^"]*"[^>]*data-src="([^"]+)"',
            r'<img[^>]*data-src="([^"]+\.(?:jpg|png|webp))"',
        ]
        for p in patterns:
            m = re.search(p, html, re.DOTALL | re.I)
            if m:
                return m.group(1)
        return ""

    def _extract_episodes(self, html, vod_id):
        """从详情页提取选集列表和线路 (支持多种JSUI/MacCMS模板)"""
        flags = []
        episodes = []

        # 模式1: JSUI module-play-list
        # 线路名
        source_matches = re.findall(
            r'class="[^"]*module-tab-item[^"]*"[^>]*>.*?<span>([^<]+)</span>',
            html, re.DOTALL
        )
        if not source_matches:
            source_matches = re.findall(
                r'class="[^"]*tab-item[^"]*"[^>]*>([^<]+)</',
                html, re.DOTALL
            )
        if not source_matches:
            source_matches = re.findall(
                r'class="[^"]*stui-pannel__head[^"]*"[^>]*>.*?<span[^>]*>([^<]+)</span>',
                html, re.DOTALL
            )

        source_names = [s.strip() for s in source_matches if s.strip()]

        # 选集列表
        box_pattern = r'class="[^"]*module-play-list-content[^"]*"[^>]*>(.*?)</div>'
        boxes = re.findall(box_pattern, html, re.DOTALL)
        if not boxes:
            box_pattern = r'class="[^"]*stui-content__playlist[^"]*"[^>]*>(.*?)</ul>'
            boxes = re.findall(box_pattern, html, re.DOTALL)
        if not boxes:
            box_pattern = r'class="[^"]*anthology-list-box[^"]*"[^>]*>(.*?)</ul>'
            boxes = re.findall(box_pattern, html, re.DOTALL)
        if not boxes:
            # 通用模式: 查找所有包含vodplay链接的区域
            boxes = re.findall(r'<ul[^>]*>(.*?/vodplay/.*?)</ul>', html, re.DOTALL)

        for i, box in enumerate(boxes):
            ep_pattern = r'href="/vodplay/([^"]+)"[^>]*>([^<]*)</a>'
            ep_matches = re.findall(ep_pattern, box)
            if not ep_matches:
                ep_pattern = r'href="(/vodplay/([^"]+))"[^>]*>([^<]*)</a>'
                ep_matches = re.findall(ep_pattern, box)
                if ep_matches:
                    ep_matches = [(m[1], m[2]) for m in ep_matches]

            if ep_matches:
                source_name = source_names[i] if i < len(source_names) else f"线路{i+1}"
                flags.append(source_name)

                ep_list = []
                for play_path, ep_name in ep_matches:
                    play_path = play_path.rstrip('/').replace('.html', '')
                    if not ep_name.strip():
                        ep_name = f"第{len(ep_list)+1}集"
                    ep_list.append(f"{ep_name.strip()}${play_path}")

                if ep_list:
                    episodes.append(ep_list)

        # 模式2: 通用 - 如果上面没找到, 直接搜索所有vodplay链接
        if not flags:
            all_links = re.findall(r'href="/vodplay/([^"]+)"[^>]*>([^<]*)</a>', html)
            if all_links:
                flags.append("QuickVOD")
                ep_list = []
                for play_path, ep_name in all_links:
                    play_path = play_path.rstrip('/').replace('.html', '')
                    if not ep_name.strip():
                        ep_name = f"第{len(ep_list)+1}集"
                    ep_list.append(f"{ep_name.strip()}${play_path}")
                episodes.append(ep_list)

        if not flags:
            flags.append("QuickVOD")
            episodes.append([f"正片${vod_id}-1-1"])

        return flags, episodes
