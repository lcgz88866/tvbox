#coding=utf-8
#!/usr/bin/python
# 袋鼠影视 (dsystv.com) - MacCMS + wapian模板
#
# 原理:
#   1. MacCMS改造站, wapian模板, 标准HTML抓取, 无验证码, 无API
#   2. 分类列表: /search.php?searchtype=5&tid={type_id}&page={n} (支持area/year/order筛选)
#   3. 详情页: /movie/index{vod_id}.html (元数据在data-video-meta属性, 剧集已内嵌)
#   4. 播放页: /play/{vod_id}-{line}-{ep}.html → var now="m3u8直链" (明文, 无加密!)
#   5. 搜索: /search.php?searchword={kw}&page={n}
#   6. 分页总数: <span class="num">{当前}/{总数}</span>
#
# 播放策略:
#   1. 直接返回m3u8直链 (parse=0, 速度最快)
#   2. 需要Referer头播放
#
# 速度: 极快 (仅需1次HTTP请求获取播放页, 无需解密, 无需验证码)

import sys
import re
import json
import urllib.parse

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def getName(self):
        return "袋鼠影视"

    def init(self, extend=""):
        self.host = "https://dsystv.com"
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

        # 分类 (type_id)
        self.cats = [
            {"type_name": "电影", "type_id": "1"},
            {"type_name": "剧集", "type_id": "2"},
            {"type_name": "综艺", "type_id": "3"},
            {"type_name": "动漫", "type_id": "4"},
            {"type_name": "短剧", "type_id": "44"},
        ]

        # 预编译正则
        self._re_vod_id = re.compile(r'/movie/index(\d+)\.html')
        self._re_pagecount = re.compile(r'<span class="num">\d+/(\d+)</span>')

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|ts)(\?|#|$)', url, re.I))

    def manualVideoVCandidate(self, items):
        return []

    # ===== HTTP辅助 =====

    def _fetch_text(self, url, headers=None):
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
        filters = {}

        common_area = {"key": "area", "name": "地区", "value": [
            {"n": "全部", "v": ""},
            {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
            {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"},
            {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"},
            {"n": "英国", "v": "英国"}, {"n": "法国", "v": "法国"},
            {"n": "印度", "v": "印度"}, {"n": "泰国", "v": "泰国"},
            {"n": "西班牙", "v": "西班牙"}, {"n": "新加坡", "v": "新加坡"},
            {"n": "其他", "v": "其他"},
        ]}

        common_year = {"key": "year", "name": "年份", "value": [
            {"n": "全部", "v": ""},
        ]}
        for y in range(2026, 2009, -1):
            common_year["value"].append({"n": str(y), "v": str(y)})

        common_by = {"key": "by", "name": "排序", "value": [
            {"n": "按时间", "v": "time"},
            {"n": "按人气", "v": "hit"},
            {"n": "按推荐", "v": "commend"},
            {"n": "按评分", "v": "douban"},
        ]}

        for c in self.cats:
            filters[c["type_id"]] = [common_area, common_year, common_by]

        return filters

    def homeVideoContent(self):
        url = self.host + "/search.php?searchtype=5&tid=1&page=1"
        html = self._fetch_text(url)
        videos = self._parse_list(html)
        return {"list": videos}

    # ===== 分类列表 =====

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        extend = extend or {}

        # 构建URL: /search.php?searchtype=5&tid={id}&page={n}&area={area}&year={year}&order={by}
        params = {"searchtype": "5", "tid": tid, "page": str(page)}
        if extend.get("area"):
            params["area"] = extend["area"]
        if extend.get("year"):
            params["year"] = extend["year"]
        if extend.get("by"):
            params["order"] = extend["by"]

        url = self.host + "/search.php?" + urllib.parse.urlencode(params)
        html = self._fetch_text(url)
        videos = self._parse_list(html)

        pagecount = self._parse_pagecount(html)

        result = {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": len(videos) if videos else 20,
            "total": pagecount * 20,
        }
        return result

    # ===== 搜索 =====

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = self.host + f"/search.php?searchword={keyword}&page={page}"
        html = self._fetch_text(url)
        videos = self._parse_list(html)
        return {"list": videos}

    # ===== 详情 =====

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        detail_url = self.host + f"/movie/index{vod_id}.html"
        html = self._fetch_text(detail_url)

        if not html:
            return {"list": []}

        # 提取元数据 (data-video-meta属性)
        vod_name = self._extract_meta_attr(html, "片名")
        if not vod_name:
            # 从title标签提取
            title_m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            if title_m:
                vod_name = title_m.group(1).strip()
            else:
                title_m = re.search(r'<title>([^<\-]+)', html)
                if title_m:
                    vod_name = title_m.group(1).strip()
        if not vod_name:
            vod_name = vod_id

        vod_pic = self._extract_detail_pic(html)
        vod_remarks = self._extract_meta_attr(html, "状态")
        if not vod_remarks:
            vod_remarks = self._extract_meta_attr(html, "备注")
        vod_year = self._extract_meta_attr(html, "年份")
        vod_area = self._extract_meta_attr(html, "地区")
        vod_actor = self._extract_meta_attr(html, "主演")
        vod_director = self._extract_meta_attr(html, "导演")
        vod_content = self._extract_plot(html)
        type_name = self._extract_meta_links(html, "类型")

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

        # 提取选集列表 (详情页已内嵌剧集)
        flags, episodes = self._extract_episodes(html, vod_id)

        if flags and episodes:
            vod["vod_play_from"] = "$$$".join(flags)
            vod["vod_play_url"] = "$$$".join(["#".join(ep) for ep in episodes])
        else:
            # 回退: 通过playlist.php AJAX获取 (传入已获取的HTML避免重复请求)
            flags, episodes = self._fetch_playlists(vod_id, html)
            if flags and episodes:
                vod["vod_play_from"] = "$$$".join(flags)
                vod["vod_play_url"] = "$$$".join(["#".join(ep) for ep in episodes])
            else:
                vod["vod_play_from"] = "袋鼠影视"
                vod["vod_play_url"] = "无播放源$$"

        return {"list": [vod]}

    # ===== 播放 =====

    def playerContent(self, flag, id, vipFlags):
        """播放: 获取播放页 → 提取m3u8直链 → 返回直链
        多重提取策略:
        1. var now="m3u8_url" (主要)
        2. 任意m3u8 URL搜索 (回退)
        3. iframe播放器URL (回退, parse=1)
        4. 播放页URL (最终回退, parse=1)
        """
        play_id = id.strip().rstrip('/').replace('.html', '')

        # 如果id已经是完整URL, 直接使用
        if play_id.startswith("http"):
            play_url = play_id if play_id.endswith(".html") else play_id + ".html"
        else:
            play_url = self.host + f"/play/{play_id}.html"

        # 设置播放页请求头 (Referer指向详情页)
        play_headers = dict(self.headers)
        play_headers["Referer"] = self.host + "/"

        html = self._fetch_text(play_url, play_headers)

        if not html:
            return {"parse": 1, "url": play_url, "header": self._play_header}

        # 提取m3u8直链
        m3u8_url = self._extract_m3u8(html)

        if m3u8_url:
            return {"parse": 0, "url": m3u8_url, "header": self._play_header}

        # 回退1: 尝试从iframe提取播放器URL, 让TVBox嗅探
        iframe_match = re.search(r'<iframe[^>]*src=["\']([^"\']+)["\']', html)
        if iframe_match:
            iframe_url = iframe_match.group(1)
            if not iframe_url.startswith("http"):
                iframe_url = self.host + iframe_url
            return {"parse": 1, "url": iframe_url, "header": self._play_header}

        # 最终回退: 让TVBox解析播放页
        return {"parse": 1, "url": play_url, "header": self._play_header}

    def _extract_m3u8(self, html):
        """从播放页HTML中提取m3u8直链
        多重提取策略:
        1. var now="url" (标准格式, 双引号)
        2. var now='url' (单引号)
        3. now="url" (无var前缀)
        4. 搜索任意https m3u8 URL
        """
        # 策略1-3: var now 变量提取
        patterns = [
            r'var\s+now\s*=\s*"([^"]+)"',
            r"var\s+now\s*=\s*'([^']+)'",
            r'\bnow\s*=\s*"([^"]+)"',
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                url = match.group(1).strip()
                if url and url.startswith("http"):
                    return url

        # 策略4: 搜索任意m3u8 URL
        m3u8_matches = re.findall(
            r'https?://[^\s"\'<>\)]+\.m3u8[^\s"\'<>\)]*',
            html
        )
        for url in m3u8_matches:
            # 优先返回包含vip或常见CDN域名的URL
            if any(k in url for k in ["vip.", "dytt", "ffzy", "fengbao", "m3u8"]):
                return url
        # 如果没有匹配到优先域名, 返回第一个m3u8 URL
        if m3u8_matches:
            return m3u8_matches[0]

        return ""

    # ===== HTML解析: 列表 =====

    def _parse_list(self, html):
        """解析视频列表页 (wapian模板)
        卡片结构: <a class="videopic" href="/movie/index{id}.html" title="名称">
                    <img ... data-original="图片URL" ... />
                    <span class="note textbg">备注</span>
                  </a>
        """
        videos = []

        # 用finditer遍历所有匹配, 从完整a标签中提取title属性
        for m in re.finditer(
            r'<a[^>]*class="videopic"[^>]*href="/movie/index(\d+)\.html"[^>]*>(.*?)</a>',
            html, re.DOTALL
        ):
            vod_id = m.group(1)
            full_tag = m.group(0)  # 完整的<a ...>...</a>
            block = m.group(2)    # a标签内容

            # 标题: 优先从a标签title属性提取, 再从alt属性
            title = ""
            title_m = re.search(r'title="([^"]+)"', full_tag)
            if title_m:
                title = title_m.group(1).strip()
            if not title:
                # 从alt属性提取: alt="《名称》高清海报"
                alt_m = re.search(r'alt="《([^》]+)》', block)
                if alt_m:
                    title = alt_m.group(1).strip()
            if not title:
                # 从span.title或h3提取
                title_m2 = re.search(r'<span class="title">([^<]+)</span>', block)
                if title_m2:
                    title = title_m2.group(1).strip()
            if not title:
                title_m3 = re.search(r'<h3[^>]*>([^<]+)</h3>', block)
                if title_m3:
                    title = title_m3.group(1).strip()
            if not title:
                continue

            # 图片: data-original优先, 再src (排除load.gif占位图)
            pic = ""
            pic_m = re.search(r'data-original="([^"]+)"', block)
            if pic_m:
                pic = pic_m.group(1)
            if not pic:
                pic_m = re.search(r'src="([^"]+)"', block)
                if pic_m and "load.gif" not in pic_m.group(1):
                    pic = pic_m.group(1)

            # 备注
            remarks = ""
            rem_m = re.search(r'<span class="note textbg">([^<]*)</span>', block)
            if rem_m:
                remarks = rem_m.group(1).strip()

            videos.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })

        return videos

    def _parse_pagecount(self, html):
        """解析总页数: <span class="num">{当前}/{总数}</span>"""
        match = self._re_pagecount.search(html)
        if match:
            return int(match.group(1))
        # 回退: 从尾页链接提取
        match = re.search(r'href="[^"]*page=(\d+)[^"]*"[^>]*>[尾末]页', html)
        if match:
            return int(match.group(1))
        # 从分页链接提取最大值
        pages = re.findall(r'page=(\d+)', html)
        if pages:
            return max(int(p) for p in pages)
        return 9999

    # ===== HTML解析: 详情页 =====

    def _extract_meta_attr(self, html, label):
        """从详情页提取元数据 (data-video-meta属性)
        结构: <li data-video-meta="值"><span class="text-muted">标签：</span>...</li>
        注意: 用[^<]*防止跨li匹配
        """
        pattern = f'<li[^>]*data-video-meta="([^"]*)"[^>]*>[^<]*<span[^>]*>{label}[：:]?</span>(.*?)</li>'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            val = match.group(1).strip()
            if val:
                return val
        # 回退: 从标签文本提取
        pattern2 = f'<span class="text-muted">{label}[：:]?</span>(.*?)</li>'
        match2 = re.search(pattern2, html, re.DOTALL)
        if match2:
            content = match2.group(1)
            links = re.findall(r'>([^<]+)</a>', content)
            if links:
                texts = [l.strip() for l in links if l.strip() and l.strip() != '&nbsp;']
                if texts:
                    return " ".join(texts)
            text = re.sub(r'<[^>]+>', '', content).strip()
            text = text.replace('&nbsp;', ' ').strip()
            if text:
                return text
        return ""

    def _extract_meta_links(self, html, label):
        """提取链接型元数据 (如类型)"""
        pattern = f'<span class="text-muted">{label}[：:]?</span>(.*?)</li>'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            links = re.findall(r'>([^<]+)</a>', match.group(1))
            texts = [l.strip() for l in links if l.strip()]
            if texts:
                return " ".join(texts)
            text = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            return text.replace('&nbsp;', ' ').strip()
        return ""

    def _extract_plot(self, html):
        """提取剧情简介
        结构: <div class="video-section-body video-plot" data-video-plot>
                <p>剧情文字...</p>      (部分页面有p标签)
                或直接文本              (大部分页面无p标签)
              </div>
        注意: data-video-plot-section 在 <section> 上, 不能误匹配
        """
        # 精确匹配 data-video-plot 但排除 data-video-plot-section/panel (用负向先行)
        match = re.search(r'data-video-plot(?![-\w])[^>]*>(.*?)</div>', html, re.DOTALL)
        if not match:
            # 回退: 通过 class="video-section-body video-plot" 定位
            match = re.search(
                r'class="[^"]*video-section-body[^"]*video-plot[^"]*"[^>]*>(.*?)</div>',
                html, re.DOTALL
            )
        if not match:
            return ""

        content = match.group(1)

        # 策略1: 提取p标签内容
        p_match = re.search(r'<p>(.*?)</p>', content, re.DOTALL)
        if p_match:
            text = re.sub(r'<[^>]+>', '', p_match.group(1))
        else:
            # 策略2: 直接清理整个div内容
            text = re.sub(r'<[^>]+>', '', content)

        # 清理: 去除全角空格(\u3000)、换行、制表符, 压缩多空格
        text = text.replace('\u3000', ' ')
        text = re.sub(r'[\n\r\t]+', ' ', text)
        text = re.sub(r'\s{2,}', ' ', text).strip()

        return text

    def _extract_detail_pic(self, html):
        """从详情页提取海报图片"""
        # 查找详情页主图
        patterns = [
            r'class="[^"]*videopic[^"]*"[^>]*>.*?data-original="([^"]+)"',
            r'class="[^"]*video-pic[^"]*"[^>]*>.*?data-original="([^"]+)"',
            r'class="[^"]*module-item-pic[^"]*"[^>]*>.*?data-original="([^"]+)"',
            r'<img[^>]*class="[^"]*lazy[^"]*"[^>]*data-original="([^"]+)"',
            r'<img[^>]*data-original="([^"]+\.(?:jpg|png|webp|jpeg))"',
            r'<img[^>]*src="([^"]+\.(?:jpg|png|webp|jpeg)[^"]*)"[^>]*alt="[^"]*海报',
        ]
        for p in patterns:
            m = re.search(p, html, re.DOTALL | re.I)
            if m:
                url = m.group(1)
                if "load.gif" not in url:
                    return url
        return ""

    def _extract_episodes(self, html, vod_id):
        """从详情页提取选集列表和线路
        结构:
          <div class="panel" data-playlist-name="蓝光专线1" data-playlist-line="0">
            <ul data-playlist-url="/playlist.php?id=xxx&line=0">
              <li><a title="第01集" href="/play/{id}-{line}-{ep}.html">第01集</a></li>
            </ul>
          </div>
        """
        flags = []
        episodes = []

        # 提取所有线路panel (name + content到</ul>)
        panels = re.findall(
            r'data-playlist-name="([^"]*)"[^>]*>(.*?)</ul>',
            html, re.DOTALL
        )

        for name, content in panels:
            if not name.strip():
                continue

            ep_list = self._extract_episode_links(content)

            if ep_list:
                flags.append(name.strip())
                episodes.append(ep_list)

        return flags, episodes

    def _extract_episode_links(self, content):
        """从HTML内容中提取剧集链接 (复用方法)
        多重提取策略:
        1. title在href前: <a title="第01集" href="/play/xxx.html">
        2. href在title前: <a href="/play/xxx.html" title="第01集">
        3. 只有href: <a href="/play/xxx.html">第01集</a>
        """
        ep_list = []

        # 策略1: title在前, href在后
        ep_matches = re.findall(
            r'title="([^"]*)"[^>]*href="/play/([^"]+)"',
            content
        )

        # 策略2: href在前, title在后
        if not ep_matches:
            href_matches = re.findall(
                r'href="/play/([^"]+)"[^>]*title="([^"]*)"',
                content
            )
            if href_matches:
                ep_matches = [(name, path) for path, name in href_matches]

        # 策略3: 只有href, 用a标签文本作为名称
        if not ep_matches:
            text_matches = re.findall(
                r'href="/play/([^"]+)"[^>]*>([^<]*)</a>',
                content
            )
            if text_matches:
                ep_matches = [(name, path) for path, name in text_matches]

        for ep_name, play_path in ep_matches:
            play_path = play_path.rstrip('/').replace('.html', '')
            ep_name = ep_name.strip()
            if not ep_name:
                ep_name = f"第{len(ep_list)+1}集"
            ep_list.append(f"{ep_name}${play_path}")

        return ep_list

    def _fetch_playlists(self, vod_id, html=None):
        """通过playlist.php AJAX接口获取剧集 (回退方案)
        可传入已获取的详情页HTML, 避免重复请求
        """
        flags = []
        episodes = []

        # 如果没有HTML, 获取详情页
        if not html:
            detail_url = self.host + f"/movie/index{vod_id}.html"
            html = self._fetch_text(detail_url)
        if not html:
            return flags, episodes

        # 提取所有playlist URL和名称
        playlist_urls = re.findall(
            r'data-playlist-url="([^"]+)"',
            html
        )
        playlist_names = re.findall(
            r'data-playlist-name="([^"]+)"',
            html
        )

        for i, pl_url in enumerate(playlist_urls):
            name = playlist_names[i] if i < len(playlist_names) else f"线路{i+1}"
            # 解码HTML实体
            pl_url = pl_url.replace("&amp;", "&")
            if not pl_url.startswith("http"):
                pl_url = self.host + pl_url

            # 设置AJAX请求头
            ajax_headers = dict(self.headers)
            ajax_headers["Referer"] = self.host + f"/movie/index{vod_id}.html"
            ajax_headers["X-Requested-With"] = "XMLHttpRequest"

            pl_html = self._fetch_text(pl_url, ajax_headers)
            if not pl_html:
                continue

            ep_list = self._extract_episode_links(pl_html)

            if ep_list:
                flags.append(name.strip())
                episodes.append(ep_list)

        return flags, episodes