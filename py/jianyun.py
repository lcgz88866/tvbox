#coding=utf-8
#!/usr/bin/python
# 简云影视 (jianyunys.com) - MacCMS站点 (encrypt=0, 无加密)
#
# 原理:
#   1. 标准MacCMS站点, player_aaaa变量中encrypt=0, URL明文可直接使用
#   2. 播放源含多种: youku/qiyi等视频页面URL (需parse=1嗅探) + jsm3u8直链 (parse=0)
#   3. m3u8直链可直接播放, 无需Referer (测试200可通过)
#
# 路由(重要):
#   分类/列表: /vodtype/{type}.html            (第1页)
#              /vodtype/{type}-{page}.html     (第N页, type可为 dianying 或子类型如 dongzuopian)
#   详情:      /voddetail/{vod_id}.html
#   播放:      /vodplay/{vod_id}-{sid}-{nid}.html
#   说明: 站点已关闭 /vodshow/ 筛选页("筛选页功能关闭中"), 该路由一律返回空,
#         因此本爬虫统一走 /vodtype/ 列表, 并改用"子类型即独立分类页"的方式提供分类切换,
#         不再依赖 /vodshow/ 的地区/年份/语言筛选(站点已禁用)。
#
# 播放策略:
#   1. 优先返回m3u8直链 (parse=0, 速度最快)
#   2. 非m3u8源返回视频页面URL (parse=1, TVBox嗅探)
#   3. 当前线路无m3u8时, 自动搜索其他线路的m3u8源
#
# 速度: 极快 (仅需1次HTTP请求获取播放页, 无需API调用/解密)

import sys
import re
import json
import urllib.parse

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def getName(self):
        return "简云影视"

    def init(self, extend=""):
        self.host = "https://jianyunys.com"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        self._play_header = json.dumps({"User-Agent": self.ua, "Referer": ""})
        self.cats = [
            {"type_name": "电影", "type_id": "dianying"},
            {"type_name": "剧集", "type_id": "lianxuju"},
            {"type_name": "综艺", "type_id": "zongyi"},
            {"type_name": "动漫", "type_id": "dongman"},
        ]
        # 子类型(独立 /vodtype/ 分类页), 用于"类型"切换导航。
        # 站点只有 电影/剧集 有子类型; 综艺/动漫 无子类型。
        self.subcats = {
            "dianying": [  # 电影
                ("动作片", "dongzuopian"), ("喜剧片", "xijupian"), ("爱情片", "aiqingpian"),
                ("科幻片", "kehuanpian"), ("恐怖片", "kongbupian"), ("剧情片", "juqingpian"),
                ("战争片", "zhanzhengpian"), ("动画片", "donghuapian"), ("奇幻片", "qihuanpian"),
                ("悬疑片", "xuanyipian"), ("武侠片", "wuxiapian"), ("伦理片", "lunlipian"),
                ("惊悚片", "jingsongpian"), ("犯罪片", "fanzuipian"), ("其他片", "qitapian"),
            ],
            "lianxuju": [  # 剧集
                ("国产剧", "guochanju"), ("港台剧", "gangtaiju"), ("日韩剧", "rihanju"),
                ("欧美剧", "oumeiju"), ("短剧", "duanju"), ("其他剧", "qitaju"),
            ],
            "zongyi": [],  # 综艺
            "dongman": [],  # 动漫
        }
        # m3u8源标识 (直链源, 优先返回)
        self._m3u8_sources = {"jsm3u8", "m3u8", "mp4", "thunder", "xunlei"}
        # 预编译正则
        self._re_player_aaaa = re.compile(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', re.DOTALL)
        self._re_player_aaaa_alt = re.compile(r'player_aaaa\s*=\s*(\{.*?\});', re.DOTALL)
        self._re_url_from = re.compile(r'"url":"([^"]*)","url_next":"[^"]*","from":"([^"]*)"')

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
        """站点已关闭 /vodshow/ 筛选(地区/年份/语言等一律失效)。
        这里只暴露仍可用的筛选: 电影/剧集的"子类型"(本身就是独立 /vodtype/ 分类页)。"""
        filters = {}
        for c in self.cats:
            tid = c["type_id"]
            subs = self.subcats.get(tid, [])
            groups = []
            if subs:
                value = [{"n": "全部", "v": ""}]
                value += [{"n": n, "v": v} for n, v in subs]
                groups.append({"key": "class", "name": "类型", "value": value})
            filters[tid] = groups
        return filters

    def homeVideoContent(self):
        # 首页聚合各分类推荐, 统一用 /vodtype/ 路由(而非已关闭的 /vodshow/)
        html = self._fetch_text(self.host + "/")
        videos = self._parse_list(html)
        return {"list": videos}

    # ===== 分类列表 =====
    def categoryContent(self, tid, pg, filter, extend):
        page = max(int(pg or 1), 1)
        extend = extend or {}
        url = self._build_category_url(tid, page, extend)
        html = self._fetch_text(url)
        videos = self._parse_list(html)

        # 若当前页无内容但页码>1, 回退到第1页避免出现空白
        if not videos and page > 1:
            url = self._build_category_url(tid, 1, extend)
            html = self._fetch_text(url)
            videos = self._parse_list(html)
            if videos:
                page = 1

        pagecount = self._parse_pagecount(html)
        if pagecount < page:
            pagecount = page
        result = {}
        result["list"] = videos
        result["page"] = page
        result["pagecount"] = pagecount
        result["limit"] = len(videos) if videos else 20
        result["total"] = result["pagecount"] * result["limit"]
        return result

    def _build_category_url(self, tid, page, extend):
        """构建分类URL(统一走 /vodtype/, 站点已关闭 /vodshow/ 筛选页)。
        第1页:  /vodtype/{type}.html
        第N页:  /vodtype/{type}-{page}.html
        当 extend['class'] 为子类型(如 dongzuopian) 时, {type}=子类型 slug, 即跳到该子类型的独立分类页。"""
        cls = (extend.get("class", "") or "").strip() if extend else ""
        # 子类型即独立分类页, 直接用其 slug; 否则用顶层分类 tid
        slug = cls if cls else str(tid)
        if page <= 1:
            return "%s/vodtype/%s.html" % (self.host, slug)
        return "%s/vodtype/%s-%d.html" % (self.host, slug, page)

    # ===== 搜索 =====
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        # 使用query参数格式, 不预编码关键词 (self.fetch会自动编码)
        # 路径格式 /vodsearch/{keyword}----------{page}---.html 会被OkHttp双重编码中文
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
        vod_name = self._extract_meta(detail_html, "片名")
        if not vod_name:
            vod_name = detail_id
        vod_pic = self._extract_pic(detail_html)
        vod_remarks = self._extract_meta(detail_html, "状态")
        year = self._extract_meta(detail_html, "年份")
        area = self._extract_meta(detail_html, "地区")
        actor = self._extract_meta(detail_html, "主演")
        director = self._extract_meta(detail_html, "导演")
        description = self._extract_meta(detail_html, "简介")
        class_name = self._extract_meta_links(detail_html, "类型")

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
        source = player_data.get("from", "")
        if not url:
            return {"parse": 0, "url": "", "header": ""}

        # 策略1: m3u8/mp4直链, parse=0直接播放 (最快)
        if self.isVideoFormat(url):
            return {
                "parse": 0,
                "url": url,
                "header": self._play_header,
            }

        # 策略2: 视频页面URL (youku/iqiyi等), 自动搜索其他线路m3u8源
        m3u8_url = self._find_m3u8_from_other_lines(play_id)
        if m3u8_url:
            return {
                "parse": 0,
                "url": m3u8_url,
                "header": self._play_header,
            }

        # 策略3: 无m3u8源, 返回视频页面URL让TVBox嗅探 (parse=1)
        return {
            "parse": 1,
            "url": url,
            "header": "",
        }

    def _find_m3u8_from_other_lines(self, play_id):
        """当前线路非m3u8时, 尝试其他线路寻找m3u8直链"""
        m = re.match(r'^(\d+)-(\d+)-(\d+)$', play_id)
        if not m:
            return ""
        vod_id = m.group(1)
        episode = m.group(3)

        detail_url = self.host + f"/voddetail/{vod_id}.html"
        detail_html = self._fetch_text(detail_url)
        if not detail_html:
            return ""

        # 找到所有播放链接, 尝试不同线路同一集
        all_play_ids = re.findall(r'href="/vodplay/([^"]+)"', detail_html)
        seen = set()
        for pid in all_play_ids:
            pid = pid.rstrip('/').replace('.html', '')
            if pid in seen or pid == play_id:
                continue
            seen.add(pid)
            pm = re.match(r'^\d+-(\d+)-(\d+)$', pid)
            if pm and pm.group(2) == episode:
                # 检查这个线路是否为m3u8源
                alt_play_url = self.host + f"/vodplay/{pid}.html"
                alt_html = self._fetch_text(alt_play_url)
                if not alt_html:
                    continue
                alt_data = self._extract_player_aaaa(alt_html)
                if not alt_data:
                    continue
                alt_url = alt_data.get("url", "")
                if alt_url and self.isVideoFormat(alt_url):
                    return alt_url
        return ""

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
        """解析视频列表页"""
        videos = []
        # MacCMS conch模板: hl-list-item结构
        blocks = re.findall(r'<li class="hl-list-item[^"]*">(.*?)</li>', html, re.DOTALL)
        for block in blocks:
            href_match = re.search(r'href="/voddetail/([^"]+)"', block)
            if not href_match:
                continue
            vod_id = href_match.group(1).rstrip('/').replace('.html', '')

            title = ""
            title_match = re.search(r'title="([^"]*)"', block)
            if title_match:
                title = title_match.group(1)
            if not title:
                title_match = re.search(r'hl-item-title[^>]*><a[^>]*>([^<]+)</a>', block)
                if title_match:
                    title = title_match.group(1).strip()
            if not title:
                continue

            pic = ""
            pic_match = re.search(r'data-original="([^"]*)"', block)
            if pic_match:
                pic = pic_match.group(1)

            remarks = ""
            rem_match = re.search(r'remarks">([^<]*)</span>', block)
            if rem_match:
                remarks = rem_match.group(1).strip()

            videos.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })
        return videos

    def _parse_pagecount(self, html):
        """解析总页数(vodtype 分页: 移动端显示 "1 / N", 且末尾链接 /vodtype/x-{N}.html)"""
        if not html:
            return 1
        best = 0
        # 1) 移动端页码提示 "1 / 1513"
        m = re.search(r'hl-page-tips[^>]*>([^<]*)<', html)
        if m:
            tips = re.sub(r'[^0-9/]', '', m.group(1))
            parts = tips.split('/')
            if len(parts) >= 2 and parts[-1].strip().isdigit():
                best = max(best, int(parts[-1].strip()))
        # 2) 末尾数字页码链接 /vodtype/{word}-{N}.html 取最大 N
        pages = re.findall(r'/vodtype/[a-z0-9]+-(\d+)\.html', html)
        if pages:
            best = max(best, *(int(p) for p in pages))
        return best if best else 9999


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

        # 提取线路名 (hl-tabs-btn中的alt属性或文本)
        source_pattern = r'hl-tabs-btn[^>]*alt="([^"]*)"'
        source_matches = re.findall(source_pattern, html)
        source_names = [s.strip() for s in source_matches if s.strip()]

        # 提取每个hl-plays-list中的选集
        box_pattern = r'hl-plays-list[^"]*"[^>]*>(.*?)</ul>'
        boxes = re.findall(box_pattern, html, re.DOTALL)

        for i, box in enumerate(boxes):
            ep_pattern = r'href="(/vodplay/([^"]+))"[^>]*>([^<]*)</a>'
            ep_matches = re.findall(ep_pattern, box)

            if ep_matches:
                source_name = source_names[i] if i < len(source_names) else f"线路{i+1}"
                flags.append(source_name)

                ep_list = []
                for m in ep_matches:
                    play_path = m[1].rstrip('/').replace('.html', '')
                    ep_name = m[2].strip()
                    if not ep_name:
                        ep_name = f"第{len(ep_list)+1}集"
                    ep_list.append(f"{ep_name}${play_path}")

                episodes.append(ep_list)

        if not flags:
            flags.append("线路1")
            episodes.append([f"正片${detail_id}-1-1"])

        return flags, episodes

    def _extract_meta(self, html, label):
        """从详情页提取元数据"""
        pattern = f'<em class="hl-text-muted">{label}：</em>(.*?)</li>'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            content = match.group(1)
            links = re.findall(r'>([^<]+)</a>', content)
            if links:
                texts = [l.strip() for l in links if l.strip() and l.strip() != '&nbsp;']
                if texts:
                    return " ".join(texts)
            span = re.search(r'<span[^>]*>([^<]*)</span>', content)
            if span:
                return span.group(1).strip()
            text = re.sub(r'<[^>]+>', '', content).strip()
            text = text.replace('&nbsp;', ' ').strip()
            return text
        return ""

    def _extract_meta_links(self, html, label):
        """从详情页提取链接型元数据"""
        pattern = f'<em class="hl-text-muted">{label}：</em>(.*?)</li>'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            links = re.findall(r'>([^<]+)</a>', match.group(1))
            texts = [l.strip() for l in links if l.strip()]
            if texts:
                return " ".join(texts)
            text = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            return text.replace('&nbsp;', ' ').strip()
        return ""

    def _extract_pic(self, html):
        """从详情页提取海报图片"""
        match = re.search(r'hl-dc-pic.*?data-original="([^"]+)"', html, re.DOTALL)
        if match:
            return match.group(1)
        match = re.search(r'data-original="([^"]+)"', html)
        if match:
            return match.group(1)
        return ""