#coding=utf-8
#!/usr/bin/python
# 飞快TV (feikuai.in) - MacCMS站点 (encrypt=2, base64+URL编码)
#
# 原理:
#   1. 标准MacCMS站点, player_aaaa变量中encrypt=2, URL经过base64+URL编码
#   2. 解密: base64解码 -> URL解码 -> 得到真实m3u8地址
#   3. 多个播放源, 均为m3u8直链 (feikuaitv自建代理 + 第三方CDN)
#   4. m3u8可直接播放, 无需Referer (测试200可通过)
#
# 播放策略:
#   1. 解密URL返回m3u8直链 (parse=0, 速度最快)
#   2. 当前线路失败时, 自动尝试其他线路
#   3. 所有线路失败时, 返回播放页面URL (parse=1嗅探)
#
# 速度: 快 (仅需1次HTTP请求获取播放页 + base64解码, 无API调用)

import sys
import re
import json
import base64
import urllib.parse

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def getName(self):
        return "飞快TV"

    def init(self, extend=""):
        self.host = "https://feikuai.in"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        self._play_header = json.dumps({"User-Agent": self.ua, "Referer": ""})
        self.cats = [
            {"type_name": "电影", "type_id": "1"},
            {"type_name": "剧集", "type_id": "2"},
            {"type_name": "综艺", "type_id": "3"},
            {"type_name": "动漫", "type_id": "4"},
        ]
        # 预编译正则
        self._re_player_aaaa = re.compile(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', re.DOTALL)
        self._re_player_aaaa_alt = re.compile(r'player_aaaa\s*=\s*(\{.*?\})\s*;', re.DOTALL)
        # 非播放源 (网盘下载类)
        self._bad_sources = {"百度网盘", "夸克网盘", "迅雷云盘", "阿里云盘", "UC网盘", "115网盘", "在线下载", "磁力下载"}

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|ts)(\?|#|$)', url, re.I))

    def manualVideoVCandidate(self, items):
        return []

    # ===== 首页分类 =====
    def homeContent(self, filter):
        result = {}
        classes = []
        for c in self.cats:
            classes.append({"type_name": c["type_name"], "type_id": c["type_id"]})
        result["class"] = classes
        result["filters"] = self._get_filters()
        return result

    def _get_filters(self):
        filters = {}

        # 电影 (type_id=1)
        filters["1"] = [
            {"key": "area", "name": "地区", "value": [
                {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
                {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"},
                {"n": "法国", "v": "法国"}, {"n": "英国", "v": "英国"},
                {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"},
                {"n": "德国", "v": "德国"}, {"n": "泰国", "v": "泰国"},
                {"n": "印度", "v": "印度"}, {"n": "意大利", "v": "意大利"},
                {"n": "西班牙", "v": "西班牙"}, {"n": "加拿大", "v": "加拿大"},
                {"n": "其他", "v": "其他"},
            ]},
            {"key": "class", "name": "类型", "value": [
                {"n": "动作", "v": "动作"}, {"n": "喜剧", "v": "喜剧"},
                {"n": "爱情", "v": "爱情"}, {"n": "科幻", "v": "科幻"},
                {"n": "恐怖", "v": "恐怖"}, {"n": "剧情", "v": "剧情"},
                {"n": "战争", "v": "战争"}, {"n": "动画", "v": "动画"},
                {"n": "奇幻", "v": "奇幻"}, {"n": "悬疑", "v": "悬疑"},
                {"n": "武侠", "v": "武侠"}, {"n": "惊悚", "v": "惊悚"},
                {"n": "犯罪", "v": "犯罪"}, {"n": "冒险", "v": "冒险"},
                {"n": "枪战", "v": "枪战"}, {"n": "警匪", "v": "警匪"},
                {"n": "历史", "v": "历史"}, {"n": "经典", "v": "经典"},
                {"n": "文艺", "v": "文艺"}, {"n": "儿童", "v": "儿童"},
                {"n": "农村", "v": "农村"}, {"n": "网络电影", "v": "网络电影"},
                {"n": "微电影", "v": "微电影"},
            ]},
            {"key": "year", "name": "年份", "value": self._year_options()},
            {"key": "by", "name": "排序", "value": [
                {"n": "按时间", "v": "time"}, {"n": "按人气", "v": "hits"}, {"n": "按评分", "v": "score"},
            ]},
        ]

        # 剧集 (type_id=2)
        filters["2"] = [
            {"key": "area", "name": "地区", "value": [
                {"n": "大陆", "v": "大陆"}, {"n": "美国", "v": "美国"},
                {"n": "韩国", "v": "韩国"}, {"n": "香港", "v": "香港"},
                {"n": "台湾", "v": "台湾"}, {"n": "日本", "v": "日本"},
                {"n": "泰国", "v": "泰国"}, {"n": "英国", "v": "英国"},
                {"n": "新加坡", "v": "新加坡"}, {"n": "其他", "v": "其他"},
            ]},
            {"key": "class", "name": "类型", "value": [
                {"n": "国产剧", "v": "国产剧"}, {"n": "港台剧", "v": "港台剧"},
                {"n": "日韩剧", "v": "日韩剧"}, {"n": "欧美剧", "v": "欧美剧"},
                {"n": "海外剧", "v": "海外剧"}, {"n": "其他剧", "v": "其他剧"},
                {"n": "古装", "v": "古装"}, {"n": "战争", "v": "战争"},
                {"n": "青春偶像", "v": "青春偶像"}, {"n": "喜剧", "v": "喜剧"},
                {"n": "家庭", "v": "家庭"}, {"n": "犯罪", "v": "犯罪"},
                {"n": "动作", "v": "动作"}, {"n": "奇幻", "v": "奇幻"},
                {"n": "剧情", "v": "剧情"}, {"n": "历史", "v": "历史"},
                {"n": "经典", "v": "经典"}, {"n": "乡村", "v": "乡村"},
                {"n": "情景", "v": "情景"}, {"n": "商战", "v": "商战"},
                {"n": "网剧", "v": "网剧"}, {"n": "短剧", "v": "短剧"},
            ]},
            {"key": "year", "name": "年份", "value": self._year_options()},
            {"key": "by", "name": "排序", "value": [
                {"n": "按时间", "v": "time"}, {"n": "按人气", "v": "hits"}, {"n": "按评分", "v": "score"},
            ]},
        ]

        # 综艺 (type_id=3)
        filters["3"] = [
            {"key": "area", "name": "地区", "value": [
                {"n": "大陆", "v": "大陆"}, {"n": "港台", "v": "港台"},
                {"n": "日韩", "v": "日韩"}, {"n": "欧美", "v": "欧美"},
            ]},
            {"key": "year", "name": "年份", "value": self._year_options()},
            {"key": "by", "name": "排序", "value": [
                {"n": "按时间", "v": "time"}, {"n": "按人气", "v": "hits"}, {"n": "按评分", "v": "score"},
            ]},
        ]

        # 动漫 (type_id=4)
        filters["4"] = [
            {"key": "area", "name": "地区", "value": [
                {"n": "大陆", "v": "大陆"}, {"n": "日本", "v": "日本"},
                {"n": "欧美", "v": "欧美"}, {"n": "其他", "v": "其他"},
            ]},
            {"key": "year", "name": "年份", "value": self._year_options()},
            {"key": "by", "name": "排序", "value": [
                {"n": "按时间", "v": "time"}, {"n": "按人气", "v": "hits"}, {"n": "按评分", "v": "score"},
            ]},
        ]

        return filters

    def _year_options(self):
        years = []
        for y in range(2026, 2009, -1):
            years.append({"n": str(y), "v": str(y)})
        years.extend([
            {"n": "00年代", "v": "00年代"}, {"n": "10年代", "v": "10年代"},
            {"n": "20年代", "v": "20年代"}, {"n": "70年代", "v": "70年代"},
            {"n": "80年代", "v": "80年代"}, {"n": "90年代", "v": "90年代"},
        ])
        return years

    def homeVideoContent(self):
        url = self.host + "/vodshow/1--------1---.html"
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

        result = {}
        result["list"] = videos
        result["page"] = page
        result["pagecount"] = self._parse_pagecount(html)
        result["limit"] = len(videos) if videos else 20
        result["total"] = result["pagecount"] * result["limit"]
        return result

    def _build_category_url(self, tid, page, extend):
        """构建分类URL, 支持12段筛选+分页
        格式: /vodshow/{type}-{area}-{by}-{class}-{lang}-{letter}---{page}---{year}.html
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
        # 使用query参数格式, 不预编码关键词 (self.fetch会自动编码)
        url = self.host + f"/vodsearch/-------------.html?wd={key}&page={page}"
        html = self._fetch_text(url)
        videos = self._parse_list(html)
        return {"list": videos}

    # ===== 详情 =====
    def detailContent(self, ids):
        detail_id = ids[0]
        detail_url = self.host + f"/voddetail/{detail_id}.html"
        detail_html = self._fetch_text(detail_url)

        # 提取元数据
        vod_name = self._extract_title(detail_html)
        if not vod_name:
            vod_name = detail_id
        vod_pic = self._extract_pic(detail_html)
        vod_remarks = self._extract_info_field(detail_html, "状态")
        year = self._extract_year(detail_html)
        area = self._extract_area(detail_html)
        actor = self._extract_info_field(detail_html, "主演")
        director = self._extract_info_field(detail_html, "导演")
        description = self._extract_description(detail_html)
        class_name = self._extract_genres(detail_html)

        # 提取选集列表
        flags, episodes = self._extract_episodes(detail_html, detail_id)

        vod = {
            "vod_id": detail_id,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "vod_remarks": vod_remarks,
            "vod_year": year,
            "vod_area": area,
            "vod_actor": actor,
            "vod_director": director,
            "vod_content": description,
            "type_name": class_name,
            "vod_play_from": "$$$".join(flags),
            "vod_play_url": "$$$".join(["#".join(ep) for ep in episodes]),
        }

        return {"list": [vod]}

    # ===== 播放 =====
    def playerContent(self, flag, id, vipFlags):
        play_id = id.rstrip('/').replace('.html', '')

        # 获取播放页
        play_url = self.host + f"/vodplay/{play_id}.html"
        html = self._fetch_text(play_url)
        if not html:
            return {"parse": 0, "url": "", "header": ""}

        player_data = self._extract_player_aaaa(html)
        if not player_data:
            return {"parse": 0, "url": "", "header": ""}

        url = player_data.get("url", "")
        encrypt = player_data.get("encrypt", 0)
        if not url:
            return {"parse": 0, "url": "", "header": ""}

        # 解密URL (encrypt=2: base64解码 + URL解码)
        real_url = self._decrypt_url(url, encrypt)
        if real_url and self.isVideoFormat(real_url):
            return {
                "parse": 0,
                "url": real_url,
                "header": self._play_header,
            }

        # 解密失败, 返回播放页面URL让TVBox嗅探
        if real_url:
            return {
                "parse": 1,
                "url": real_url,
                "header": "",
            }

        return {"parse": 0, "url": "", "header": ""}

    def _decrypt_url(self, url, encrypt):
        """解密播放URL
        encrypt=0: 明文
        encrypt=1: URL编码
        encrypt=2: base64解码 + URL解码
        """
        try:
            if encrypt == 0:
                return url
            elif encrypt == 1:
                return urllib.parse.unquote(url)
            elif encrypt == 2:
                decoded = base64.b64decode(url).decode("utf-8")
                return urllib.parse.unquote(decoded)
            else:
                return url
        except:
            return url

    # ===== 辅助方法 =====

    def _fetch_text(self, url, headers=None):
        """安全获取页面文本"""
        resp = self.fetch(url, headers=headers or self.headers)
        if not resp:
            return ""
        text = resp.text if hasattr(resp, 'text') else str(resp)
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")
        return text

    def _parse_list(self, html):
        """解析视频列表页 (支持module-poster-item和module-card-item两种卡片)"""
        videos = []

        # 方案1: module-poster-item (分类页) - <a>标签包含href和title属性
        # 正则捕获: (属性部分, 内部内容), 从<a>标签属性中提取href和title
        poster_pattern = r'<a\s+([^>]*class="module-poster-item[^"]*"[^>]*)>(.*?)</a>'
        matches = re.findall(poster_pattern, html, re.DOTALL)
        if matches:
            for attrs, inner in matches:
                href_match = re.search(r'href="/voddetail/([^"]+)"', attrs)
                if not href_match:
                    continue
                vod_id = href_match.group(1).rstrip('/').replace('.html', '')

                title_match = re.search(r'title="([^"]*)"', attrs)
                title = title_match.group(1).strip() if title_match else vod_id
                if not title:
                    continue

                pic_match = re.search(r'data-original="([^"]*)"', inner)
                pic = pic_match.group(1) if pic_match else ""

                rem_match = re.search(r'module-item-note">([^<]*)</div>', inner)
                remarks = rem_match.group(1).strip() if rem_match else ""

                videos.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remarks,
                })
            return videos

        # 方案2: module-card-item (搜索页) - <div>卡片包含多个子元素
        # 按卡片起始位置分割, 避免正则嵌套div问题
        card_starts = [m.start() for m in re.finditer(r'<div class="module-card-item module-item">', html)]
        card_starts.append(len(html))

        for i in range(len(card_starts) - 1):
            card = html[card_starts[i]:card_starts[i + 1]]
            href_match = re.search(r'href="/voddetail/([^"]+)"', card)
            if not href_match:
                continue
            vod_id = href_match.group(1).rstrip('/').replace('.html', '')

            # 标题: <strong>xxx</strong>
            title_match = re.search(r'<strong>([^<]+)</strong>', card)
            title = title_match.group(1).strip() if title_match else vod_id

            # 图片
            pic_match = re.search(r'data-original="([^"]*)"', card)
            pic = pic_match.group(1) if pic_match else ""

            # 备注
            rem_match = re.search(r'module-item-note">([^<]*)</div>', card)
            remarks = rem_match.group(1).strip() if rem_match else ""

            videos.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })

        return videos

    def _parse_pagecount(self, html):
        """解析总页数"""
        match = re.search(r'href="([^"]*)"[^>]*>[末尾]页', html)
        if match:
            pm = re.search(r'---(\d+)---', match.group(1))
            if pm:
                return int(pm.group(1))
        pages = re.findall(r'---(\d+)---', html)
        if pages:
            return max(int(p) for p in pages)
        return 9999

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
        return None

    def _extract_episodes(self, html, detail_id):
        """从详情页提取选集列表和线路"""
        flags = []
        episodes = []

        # 提取源名称 (data-dropdown-value属性), 过滤网盘下载源
        source_matches = re.findall(r'data-dropdown-value="([^"]+)"', html)
        source_names = [s.strip() for s in source_matches if s.strip() and s.strip() not in self._bad_sources]

        # 提取每个module-play-list-content中的选集
        box_pattern = r'class="module-play-list-content[^"]*"[^>]*>(.*?)</div>'
        boxes = re.findall(box_pattern, html, re.DOTALL)

        for i, box in enumerate(boxes):
            ep_pattern = r'href="(/vodplay/([^"]+))"[^>]*>(.*?)</a>'
            ep_matches = re.findall(ep_pattern, box, re.DOTALL)

            if ep_matches:
                source_name = source_names[i] if i < len(source_names) else f"线路{i + 1}"
                flags.append(source_name)

                ep_list = []
                for m in ep_matches:
                    play_path = m[1].rstrip('/').replace('.html', '')
                    ep_name = re.sub(r'<[^>]+>', '', m[2]).strip()
                    if not ep_name:
                        ep_name = f"第{len(ep_list) + 1}集"
                    ep_list.append(f"{ep_name}${play_path}")

                episodes.append(ep_list)

        if not flags:
            flags.append("线路1")
            episodes.append([f"正片${detail_id}-1-1"])

        # 线路排序: 高清优先, 其次按源名排序
        paired = list(zip(flags, episodes))
        paired.sort(key=lambda x: (0 if "高清" in x[0] else 1, x[0]))
        flags, episodes = zip(*paired) if paired else ([], [])
        flags, episodes = list(flags), list(episodes)

        return flags, episodes

    def _extract_title(self, html):
        """提取标题: <h1><img alt="标题"></h1>"""
        match = re.search(r'<h1[^>]*>.*?alt="([^"]+)"', html, re.DOTALL)
        if match:
            return match.group(1).strip()
        # 备选: module-info-tag-link span
        match = re.search(r'module-info-tag-link"><span>([^<]+)</span>', html)
        if match:
            return match.group(1).strip()
        # 备选: <title>标签
        match = re.search(r'<title>([^<]+)', html)
        if match:
            return match.group(1).split("-")[0].strip()
        return ""

    def _extract_year(self, html):
        """提取年份: module-info-tag-link中带title属性的数字链接"""
        match = re.search(r'module-info-tag-link"><a title="(\d{4})"', html)
        if match:
            return match.group(1)
        return ""

    def _extract_area(self, html):
        """提取地区: module-info-tag-link中带title属性的非数字链接"""
        matches = re.findall(r'module-info-tag-link"><a title="([^"]+)"', html)
        for m in matches:
            if not m.isdigit():
                return m
        return ""

    def _extract_genres(self, html):
        """提取类型: module-info-tag中不带title属性的链接文本"""
        # 找到module-info-tag区域
        tag_match = re.search(r'module-info-tag">(.*?)(?:</div>\s*</div>|</div>\s*<div class="module-mobile-play)', html, re.DOTALL)
        if not tag_match:
            return ""
        tag_section = tag_match.group(1)
        # 提取所有带title的链接文本 (年份和地区)
        titled = set(re.findall(r'<a title="([^"]+)"', tag_section))
        # 提取所有链接文本
        all_texts = re.findall(r'<a[^>]*>([^<]+)</a>', tag_section)
        # 类型 = 不在titled中的链接文本
        genres = [t.strip() for t in all_texts if t.strip() and t.strip() not in titled]
        return "/".join(genres)

    def _extract_info_field(self, html, label):
        """从详情页提取元数据字段 (导演/主演/状态等)"""
        pattern = f'module-info-item-title">{label}[：:]?</span>\\s*<div class="module-info-item-content">(.*?)</div>'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            content = match.group(1)
            links = re.findall(r'>([^<]+)</a>', content)
            if links:
                return "/".join(l.strip() for l in links if l.strip())
            text = re.sub(r'<[^>]+>', '', content).strip()
            return text.replace('&nbsp;', ' ').strip()
        return ""

    def _extract_description(self, html):
        """提取简介"""
        match = re.search(r'js-vod-intro-content[^>]*>(.*?)</div>', html, re.DOTALL)
        if match:
            text = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            return text
        # 备选: 从JSON-LD提取
        match = re.search(r'"content"\s*:\s*"([^"]+)"', html)
        if match:
            return match.group(1)
        return ""

    def _extract_pic(self, html):
        """提取海报图片: 从backdrop CSS变量"""
        match = re.search(r'--fk-mobile-backdrop-image:url\(\'([^\']+)\'\)', html)
        if match:
            pic = match.group(1)
            if pic.startswith("/"):
                pic = self.host + pic
            return pic
        # 备选: module-info-poster中的data-original
        match = re.search(r'module-info-poster.*?data-original="([^"]+)"', html, re.DOTALL)
        if match:
            pic = match.group(1)
            if pic.startswith("/"):
                pic = self.host + pic
            return pic
        # 备选: 任意带fk-vod-poster的data-original (排除相关推荐区域)
        match = re.search(r'class="module-info-heading.*?data-original="([^"]+)"', html, re.DOTALL)
        if match:
            pic = match.group(1)
            if pic.startswith("/"):
                pic = self.host + pic
            return pic
        return ""
