#coding=utf-8
#!/usr/bin/python
# 毒舌影视 (m.xnhrsb.com) - MacCMS + dsshiyi模板
#
# 原理:
#   1. MacCMS站, dsshiyi模板, 标准HTML抓取, 无验证码
#   2. 分类列表: /dsshiyitp/{tid}-{page}.html (支持area/year/by/class/lang筛选)
#   3. 筛选列表: /dsshiyisw/{tid}-{area}-{by}-{class}-{lang}-{letter}------{page}---{year}.html
#   4. 详情页: /dsshiyidt/{vod_id}.html (元数据在li标签, 剧集在ypxingq_t线路块)
#   5. 播放页: /dsshiyipy/{vod_id}-{line}-{ep}.html → player_aaaa JSON含m3u8直链 (encrypt=0, 无加密!)
#   6. 搜索: POST /search.php?searchword={kw}
#   7. 分页总数: 尾页链接 /dsshiyisw/{tid}--------{max}---.html
#
# 播放策略:
#   1. 直接返回m3u8直链 (parse=0, 速度最快)
#   2. 无需Referer, m3u8可直接访问
#
# 速度: 极快 (仅需1次HTTP请求获取播放页, 无需解密)

import sys
import re
import json
import urllib.parse

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def getName(self):
        return "毒舌影视"

    def init(self, extend=""):
        self.host = "https://m.xnhrsb.com"
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
            {"type_name": "短剧", "type_id": "5"},
        ]

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

    def _post_text(self, url, data, headers=None):
        try:
            resp = self.post(url, data=data, headers=headers or self.headers)
            if not resp:
                return ""
            text = resp.text if hasattr(resp, 'text') else str(resp)
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="replace")
            return text
        except:
            return ""

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
            {"n": "德国", "v": "德国"}, {"n": "印度", "v": "印度"},
            {"n": "泰国", "v": "泰国"}, {"n": "意大利", "v": "意大利"},
            {"n": "西班牙", "v": "西班牙"}, {"n": "加拿大", "v": "加拿大"},
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
            {"n": "按评分", "v": "score"},
        ]}

        common_class = {"key": "class", "name": "类型", "value": [
            {"n": "全部", "v": ""},
            {"n": "喜剧", "v": "喜剧"}, {"n": "爱情", "v": "爱情"},
            {"n": "恐怖", "v": "恐怖"}, {"n": "动作", "v": "动作"},
            {"n": "科幻", "v": "科幻"}, {"n": "剧情", "v": "剧情"},
            {"n": "战争", "v": "战争"}, {"n": "警匪", "v": "警匪"},
            {"n": "犯罪", "v": "犯罪"}, {"n": "动画", "v": "动画"},
            {"n": "奇幻", "v": "奇幻"}, {"n": "武侠", "v": "武侠"},
            {"n": "冒险", "v": "冒险"}, {"n": "枪战", "v": "枪战"},
            {"n": "悬疑", "v": "悬疑"}, {"n": "惊悚", "v": "惊悚"},
            {"n": "经典", "v": "经典"}, {"n": "青春", "v": "青春"},
            {"n": "文艺", "v": "文艺"}, {"n": "古装", "v": "古装"},
            {"n": "历史", "v": "历史"}, {"n": "运动", "v": "运动"},
            {"n": "农村", "v": "农村"}, {"n": "儿童", "v": "儿童"},
            {"n": "网络电影", "v": "网络电影"},
        ]}

        common_lang = {"key": "lang", "name": "语言", "value": [
            {"n": "全部", "v": ""},
            {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"},
            {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"},
            {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"},
            {"n": "法语", "v": "法语"}, {"n": "德语", "v": "德语"},
            {"n": "其它", "v": "其它"},
        ]}

        for c in self.cats:
            filters[c["type_id"]] = [common_area, common_year, common_by, common_class, common_lang]

        return filters

    def homeVideoContent(self):
        url = self.host + "/dsshiyitp/1.html"
        html = self._fetch_text(url)
        videos = self._parse_list(html)
        return {"list": videos}

    # ===== 分类列表 =====

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        extend = extend or {}

        area = extend.get("area", "")
        year = extend.get("year", "")
        by = extend.get("by", "")
        cls = extend.get("class", "")
        lang = extend.get("lang", "")

        # 如果没有任何筛选, 使用简单URL: /dsshiyitp/{tid}-{page}.html
        if not area and not year and not by and not cls and not lang:
            if page == 1:
                url = self.host + f"/dsshiyitp/{tid}.html"
            else:
                url = self.host + f"/dsshiyitp/{tid}-{page}.html"
        else:
            # 使用筛选URL: /dsshiyisw/{tid}-{area}-{by}-{class}-{lang}------{page}---{year}.html
            # 格式: 12个字段, 11个连字符
            # [0]=tid [1]=area [2]=by [3]=class [4]=lang [5]=letter [6]= [7]= [8]=page [9]= [10]= [11]=year
            # 注意: 中文需URL编码 (如 大陆 -> %E5%A4%A7%E9%99%86)
            q = lambda s: urllib.parse.quote(s, safe='') if s else ""
            parts = [tid, q(area), q(by), q(cls), q(lang), "", "", "", str(page), "", "", year]
            url = self.host + "/dsshiyisw/" + "-".join(parts) + ".html"

        html = self._fetch_text(url)
        videos = self._parse_list(html)

        pagecount = self._parse_pagecount(html, tid)

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

        # 搜索URL格式: /dsshiyisc/{keyword}----------{page}---.html
        # 14个字段(13个连字符): keyword在第0位, page在第10位
        # 搜索表单action="/dsshiyisc/-------------.html", JS函数qrsearch()将keyword填入路径
        url = self.host + f"/dsshiyisc/{keyword}----------{page}---.html"
        html = self._fetch_text(url)

        # 检测: 无搜索结果时网站返回空列表 (mac_total=0)
        if html and "mac_total').html('0')" in html:
            return {"list": []}

        videos = self._parse_list(html)
        return {"list": videos}

    # ===== 详情 =====

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        detail_url = self.host + f"/dsshiyidt/{vod_id}.html"
        html = self._fetch_text(detail_url)

        if not html:
            return {"list": []}

        # 提取标题
        vod_name = ""
        title_m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if title_m:
            vod_name = title_m.group(1).strip()
        if not vod_name:
            title_m = re.search(r'<h2[^>]*>([^<]+)</h2>', html)
            if title_m:
                vod_name = title_m.group(1).strip()
        if not vod_name:
            title_m = re.search(r'<title>([^<\-]+)', html)
            if title_m:
                vod_name = title_m.group(1).strip()
        if not vod_name:
            vod_name = vod_id

        # 提取元数据
        vod_pic = self._extract_detail_pic(html)
        vod_remarks = self._extract_meta_text(html, "状态")
        if not vod_remarks:
            # 从列表卡片备注提取
            rem_m = re.search(r'<span class="qb">([^<]+)</span>', html)
            if rem_m:
                vod_remarks = rem_m.group(1).strip()
        vod_year = self._extract_meta_links(html, "年份")
        vod_area = self._extract_meta_links(html, "地区")
        vod_actor = self._extract_meta_links(html, "主演")
        vod_director = self._extract_meta_links(html, "导演")
        vod_content = self._extract_plot(html)
        type_name = self._extract_meta_links(html, "类型")
        vod_lang = self._extract_meta_links(html, "语言")
        if not vod_lang:
            vod_lang = self._extract_meta_text(html, "语言")

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
            "vod_lang": vod_lang,
        }

        # 提取选集列表和线路
        flags, episodes = self._extract_episodes(html, vod_id)

        if flags and episodes:
            vod["vod_play_from"] = "$$$".join(flags)
            vod["vod_play_url"] = "$$$".join(["#".join(ep) for ep in episodes])
        else:
            vod["vod_play_from"] = "毒舌影视"
            vod["vod_play_url"] = "无播放源$$"

        return {"list": [vod]}

    # ===== 播放 =====

    def playerContent(self, flag, id, vipFlags):
        """播放: 获取播放页 → 提取player_aaaa JSON → 返回m3u8直链
        encrypt=0, 明文m3u8, 无需解密!"""
        play_id = id.strip().rstrip('/').replace('.html', '')

        # 如果id是完整URL, 直接使用
        if play_id.startswith("http"):
            play_url = play_id if play_id.endswith(".html") else play_id + ".html"
        else:
            play_url = self.host + f"/dsshiyipy/{play_id}.html"

        # 设置播放页请求头
        play_headers = dict(self.headers)
        play_headers["Referer"] = self.host + "/"

        html = self._fetch_text(play_url, play_headers)

        if not html:
            return {"parse": 1, "url": play_url, "header": self._play_header}

        # 提取player_aaaa JSON
        m3u8_url = self._extract_m3u8(html)

        if m3u8_url:
            return {"parse": 0, "url": m3u8_url, "header": self._play_header}

        # 回退1: 尝试从iframe提取播放器URL
        iframe_match = re.search(r'<iframe[^>]*src=["\']([^"\']+)["\']', html)
        if iframe_match:
            iframe_url = iframe_match.group(1)
            if not iframe_url.startswith("http"):
                iframe_url = self.host + iframe_url
            return {"parse": 1, "url": iframe_url, "header": self._play_header}

        # 回退2: 搜索任意m3u8 URL
        m3u8_matches = re.findall(r'https?://[^\s"\'<>\)]+\.m3u8[^\s"\'<>\)]*', html)
        if m3u8_matches:
            return {"parse": 0, "url": m3u8_matches[0], "header": self._play_header}

        # 最终回退: 让TVBox解析播放页
        return {"parse": 1, "url": play_url, "header": self._play_header}

    def _extract_m3u8(self, html):
        """从播放页提取m3u8直链
        策略1: player_aaaa JSON的url字段 (主要)
        策略2: var now="url"
        策略3: 搜索任意m3u8 URL
        """
        # 策略1: player_aaaa JSON
        match = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                url = data.get("url", "")
                if url and url.startswith("http"):
                    return url
            except:
                pass

        # 策略2: var now
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

        # 策略3: 搜索任意m3u8 URL
        m3u8_matches = re.findall(r'https?://[^\s"\'<>\)]+\.m3u8[^\s"\'<>\)]*', html)
        for url in m3u8_matches:
            return url

        return ""

    # ===== HTML解析: 列表 =====

    def _parse_list(self, html):
        """解析视频列表页 (dsshiyi模板)
        卡片结构:
          <a href="/dsshiyidt/{id}.html">
            <img class="thumb lazy" data-original="{pic}" alt="{title}">
          </a>
          <div class="hdinfo"><span class="qb">{remarks}</span></div>
          <h3 class="dytit"><a href="/dsshiyidt/{id}.html">{title}</a></h3>
        """
        videos = []

        # 用finditer遍历所有图片链接卡片
        for m in re.finditer(
            r'<a[^>]*href="/dsshiyidt/(\d+)\.html"[^>]*>\s*<img[^>]*class="thumb[^"]*"[^>]*>',
            html, re.DOTALL
        ):
            vod_id = m.group(1)
            full_tag = m.group(0)

            # 标题: 从alt属性提取
            title = ""
            alt_m = re.search(r'alt="([^"]+)"', full_tag)
            if alt_m:
                title = alt_m.group(1).strip()

            if not title:
                # 从h3标签提取
                h3_m = re.search(
                    r'<h3[^>]*>\s*<a[^>]*href="/dsshiyidt/' + vod_id + r'\.html"[^>]*>([^<]+)</a>',
                    html
                )
                if h3_m:
                    title = h3_m.group(1).strip()

            if not title:
                continue

            # 图片: data-original优先, 再src (排除blank.gif占位图)
            pic = ""
            pic_m = re.search(r'data-original="([^"]+)"', full_tag)
            if pic_m:
                pic = pic_m.group(1)
            if not pic:
                pic_m = re.search(r'src="([^"]+)"', full_tag)
                if pic_m and "blank.gif" not in pic_m.group(1):
                    pic = pic_m.group(1)

            # 补全图片URL
            if pic and not pic.startswith("http"):
                pic = self.host + pic

            # 备注: 从hdinfo/span.qb提取
            remarks = ""
            # 在当前卡片附近查找备注
            after_tag = html[m.end():m.end()+500]
            rem_m = re.search(r'<span class="qb">([^<]+)</span>', after_tag)
            if rem_m:
                remarks = rem_m.group(1).strip()

            videos.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })

        return videos

    def _parse_pagecount(self, html, tid):
        """解析总页数
        分页结构:
          <a href="/dsshiyisw/{tid}--------1---.html" class="current">1</a>
          <a href="/dsshiyisw/{tid}--------828---.html" class="extend" title="跳转到最后一页"> »</a>
        筛选页URL含编码中文 (如 1-%E5%A4%A7%E9%99%86-------306---.html), 需通用匹配
        """
        # 策略1: 从"跳转到最后一页"链接提取 (最可靠, 不依赖tid位置)
        # 匹配任意URL格式: href="...{page}---.html"...title="跳转到最后一页"
        match = re.search(
            r'href="[^"]*?-(\d+)---\.html"[^>]*title="跳转到最后一页"',
            html
        )
        if match:
            return int(match.group(1))

        # 反向匹配: title在前
        match = re.search(
            r'title="跳转到最后一页"[^>]*href="[^"]*?-(\d+)---\.html"',
            html
        )
        if match:
            return int(match.group(1))

        # 策略2: 从所有分页链接中取最大值
        # 格式: ...{page}---.html (page后跟3个dash和.html)
        pages = re.findall(r'-(\d+)---\.html', html)
        if pages:
            # 过滤掉太大的值 (可能是ID而非页码)
            valid = [int(p) for p in pages if int(p) < 10000]
            if valid:
                return max(valid)

        # 策略3: 从dsshiyitp分页链接提取最大值
        pages = re.findall(r'dsshiyitp/' + tid + r'-(\d+)\.html', html)
        if pages:
            return max(int(p) for p in pages)

        # 无分页链接 → 单页结果
        return 1

    # ===== HTML解析: 详情页 =====

    def _extract_meta_links(self, html, label):
        """提取链接型元数据
        结构: <li>标签：<a href="...">值</a>&nbsp;</li>
        """
        pattern = f'{label}[：:]\s*</li>'
        # 先找li标签内容
        pattern = f'<li>{label}[：:]\s*(.*?)</li>'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            content = match.group(1)
            links = re.findall(r'>([^<]+)</a>', content)
            texts = [l.strip() for l in links if l.strip() and l.strip() != "&nbsp;"]
            if texts:
                return " ".join(texts)
            # 无链接时提取纯文本
            text = re.sub(r'<[^>]+>', '', content).strip()
            text = text.replace('&nbsp;', ' ').strip()
            if text:
                return text
        return ""

    def _extract_meta_text(self, html, label):
        """提取文本型元数据
        结构: <li>标签：<span>值</span></li> 或 <li>标签：值</li>
        """
        pattern = f'<li>{label}[：:]\s*(?:<span>)?([^<\n]+?)(?:</span>)?\s*</li>'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            val = match.group(1).strip()
            if val and val != "&nbsp;":
                return val
        return ""

    def _extract_plot(self, html):
        """提取剧情简介: <div class="yp_context">text</div>"""
        match = re.search(r'class="yp_context"[^>]*>(.*?)</div>', html, re.DOTALL)
        if match:
            text = re.sub(r'<[^>]+>', '', match.group(1))
            text = text.replace('\u3000', ' ')
            text = re.sub(r'[\n\r\t]+', ' ', text)
            text = re.sub(r'\s{2,}', ' ', text).strip()
            return text
        return ""

    def _extract_detail_pic(self, html):
        """从详情页提取海报图片"""
        patterns = [
            r'<img[^>]*class="[^"]*thumb[^"]*"[^>]*data-original="([^"]+)"',
            r'<img[^>]*class="[^"]*lazy[^"]*"[^>]*data-original="([^"]+)"',
            r'<img[^>]*data-original="([^"]+\.(?:jpg|png|webp|jpeg))"',
        ]
        for p in patterns:
            m = re.search(p, html, re.I)
            if m:
                url = m.group(1)
                if "blank.gif" not in url:
                    if not url.startswith("http"):
                        url = self.host + url
                    return url
        return ""

    def _extract_episodes(self, html, vod_id):
        """从详情页提取选集列表和线路
        结构:
          <div class="ypxingq_t">秒播-<span>在线播放</span></div>
          <div class="paly_list_btn">
            <a href="/dsshiyipy/{id}-{line}-{ep}.html">第01集</a>
          </div>
        """
        flags = []
        episodes = []

        # 提取所有线路块: ypxingq_t (线路名) + paly_list_btn (剧集链接)
        sections = re.findall(
            r'class="ypxingq_t">([^<-]+)-<span>在线播放.*?class="paly_list_btn">(.*?)(?=class="ypxingq_t"|$)',
            html, re.DOTALL
        )

        for name, content in sections:
            name = name.strip()
            if not name:
                continue

            ep_list = self._extract_episode_links(content)

            if ep_list:
                flags.append(name)
                episodes.append(ep_list)

        return flags, episodes

    def _extract_episode_links(self, content):
        """从HTML内容中提取剧集链接
        格式: <a href="/dsshiyipy/{id}-{line}-{ep}.html">第01集</a>
        排除APP秒播等非剧集链接
        只提取 {id}-{line}-{ep} 部分, 不含路径前缀和.html后缀
        """
        ep_list = []

        # 提取所有/dsshiyipy/链接, 只捕获ID部分 (不含/dsshiyipy/前缀和.html后缀)
        # group1=play_id (如 263620-2-1), group2=ep_name (如 第01集)
        ep_matches = re.findall(
            r'href="/dsshiyipy/([^"]+?)(?:\.html)?"[^>]*>([^<]*)</a>',
            content
        )

        for play_id, ep_name in ep_matches:
            # 跳过APP播放链接
            if "app2." in play_id or "zstv" in play_id:
                continue

            ep_name = ep_name.strip()
            if not ep_name or "APP" in ep_name:
                continue

            ep_list.append(f"{ep_name}${play_id}")

        return ep_list