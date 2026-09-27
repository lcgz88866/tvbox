#coding=utf-8
#!/usr/bin/python
# 4K影视 (www.4kvms.org) - 自定义框架 (Tailwind + Alpine.js + WASM)
# URL规则:
#   分类页: /filter?classify={tid}&areas={areas}&years={years}&sort_by={sort}&order=desc&page={page}
#   播放页: /play/{vod_id}
#   搜索: /search?q={keyword}
# 播放: Python wasmtime运行WASM签名, 获取MP4直链给ExoPlayer (parse=0)

import sys
import os
import time
import struct
sys.path.append('..')
from base.spider import Spider
import re
import json
from urllib.parse import quote, urlencode, urlparse, urlunparse


class Spider(Spider):

    def getName(self):
        return "4K影视"

    def init(self, extend=""):
        self.host = "https://www.4kvms.org"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.header = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        # 预查找 WASM 二进制文件路径（只查一次）
        self._wasm_file = None
        _script_dir = os.path.dirname(os.path.abspath(__file__))
        wasm_paths = [
            os.path.join(_script_dir, "nbmovie_wasm_bg.d5d51939.wasm"),
            os.path.join(_script_dir, "nbmovie_wasm_bg.wasm"),
            "/data/user/work/nbmovie_wasm_bg.d5d51939.wasm",
        ]
        for p in wasm_paths:
            if os.path.exists(p):
                self._wasm_file = p
                break
        # 自动下载WASM文件（无需手动放置）
        if not self._wasm_file:
            self._wasm_file = self._download_wasm(wasm_paths[0])
        # wasmtime 引擎延迟初始化
        self._wasm_engine = None
        self._wasm_module = None
        self._wasm_linker = None
        self._wasm_ready = False

    def _download_wasm(self, save_path):
        """从网站自动下载WASM文件，无需手动放置"""
        try:
            # 尝试从播放页HTML中查找WASM文件URL
            wasm_url = None
            html = self._req("/")
            if html:
                # 先从首页找一个播放页链接
                m_play = re.search(r'href="/play/([a-z0-9]+)"', html)
                if m_play:
                    play_html = self._req("/play/" + m_play.group(1))
                    if play_html:
                        m = re.search(r'(/static/wasm/nbmovie_wasm_bg\.[a-f0-9]+\.wasm)', play_html)
                        if m:
                            wasm_url = self.host + m.group(1)
            # 回退到已知URL
            if not wasm_url:
                wasm_url = self.host + "/static/wasm/nbmovie_wasm_bg.d5d51939.wasm"
            print("Downloading WASM: {0}".format(wasm_url))
            rsp = self.fetch(wasm_url, headers=self.header)
            content = rsp.content if hasattr(rsp, 'content') else rsp
            if content and len(content) > 1000:
                data = content if isinstance(content, bytes) else content.encode()
                # 尝试多个保存位置
                save_paths = [save_path, "/data/user/work/nbmovie_wasm_bg.d5d51939.wasm"]
                for p in save_paths:
                    try:
                        with open(p, "wb") as f:
                            f.write(data)
                        print("WASM saved to: {0} ({1} bytes)".format(p, len(data)))
                        return p
                    except:
                        continue
            else:
                print("WASM download failed: empty response")
        except Exception as e:
            print("WASM download error: {0}".format(e))
        return None

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

    # ==================== 通用请求 ====================
    def _req(self, path):
        """通用请求"""
        url = self.host + path if not path.startswith("http") else path
        try:
            rsp = self.fetch(url, headers=self.header)
            if isinstance(rsp, str):
                return rsp
            if isinstance(rsp, bytes):
                return rsp.decode('utf-8', errors='replace')
            if rsp and hasattr(rsp, 'text'):
                return rsp.text
            if rsp and hasattr(rsp, 'content'):
                return rsp.content.decode('utf-8', errors='replace')
        except Exception as e:
            print("_req error: {0} | {1}".format(url, e))
        return ""

    # ==================== 图片URL处理 ====================
    def _fix_pic(self, pic):
        """处理图片URL
        - data-src 懒加载: 提取真实URL
        - 百度图床代理: gimg0.baidu.com/gimg/app=2001&...&src=真实URL
        - 相对路径: 补全host
        - 完整URL: 直接返回
        """
        if not pic:
            return ""
        # HTML实体解码 (API返回的是&, HTML中是&amp;)
        pic = pic.replace("&amp;", "&")
        # 百度图床代理: 提取src参数中的真实URL
        if "gimg0.baidu.com" in pic or "gimg.baidu.com" in pic:
            m = re.search(r'[?&]src=([^&]+)', pic)
            if m:
                pic = m.group(1)
                # 可能还嵌套了百度代理
                if "gimg0.baidu.com" in pic or "gimg.baidu.com" in pic:
                    m2 = re.search(r'[?&]src=([^&]+)', pic)
                    if m2:
                        pic = m2.group(1)
        if pic.startswith("http"):
            return pic
        # 提取的src可能没有协议前缀 (如 4kvm.staticimgjs.org/...)
        # 检查是否是域名格式
        if re.match(r'^[a-z0-9][a-z0-9.-]+\.[a-z]{2,}', pic):
            return "https://" + pic
        if not pic.startswith("/"):
            pic = "/" + pic
        return self.host + pic

    # ==================== 分类配置 ====================
    cats = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "电视剧", "type_id": "2"},
        {"type_name": "动漫", "type_id": "3"},
        {"type_name": "综艺", "type_id": "4"},
    ]

    def _build_filters(self):
        filters = {}

        # 地区 (使用数字ID)
        area_values = [
            {"n": "全部", "v": ""},
            {"n": "美国", "v": "5"},
            {"n": "中国", "v": "7"},
            {"n": "中国大陆", "v": "52"},
            {"n": "中国香港", "v": "14"},
            {"n": "中国台湾", "v": "21"},
            {"n": "日本", "v": "11"},
            {"n": "韩国", "v": "12"},
            {"n": "英国", "v": "30"},
            {"n": "法国", "v": "6"},
            {"n": "德国", "v": "18"},
            {"n": "泰国", "v": "33"},
            {"n": "印度", "v": "34"},
            {"n": "加拿大", "v": "32"},
            {"n": "俄罗斯", "v": "16"},
            {"n": "西班牙", "v": "24"},
            {"n": "意大利", "v": "19"},
            {"n": "澳大利亚", "v": "22"},
            {"n": "其他", "v": "78"},
        ]

        # 年份 (使用数字ID)
        year_values = [
            {"n": "全部", "v": ""},
            {"n": "2026", "v": "1"},
            {"n": "2025", "v": "3"},
            {"n": "2024", "v": "4"},
            {"n": "2023", "v": "56"},
            {"n": "2022", "v": "13"},
            {"n": "2021", "v": "2"},
            {"n": "2020", "v": "6"},
            {"n": "2019", "v": "8"},
            {"n": "2018", "v": "9"},
            {"n": "2017", "v": "12"},
            {"n": "2016", "v": "11"},
            {"n": "2015", "v": "14"},
            {"n": "2014", "v": "15"},
            {"n": "2013", "v": "22"},
            {"n": "2012", "v": "10"},
            {"n": "2011", "v": "17"},
            {"n": "2010", "v": "25"},
            {"n": "2009", "v": "20"},
            {"n": "2008", "v": "23"},
        ]

        # 排序
        sort_values = [
            {"n": "最新上映", "v": "update_time"},
            {"n": "最受欢迎", "v": "hits"},
            {"n": "评分最高", "v": "score"},
        ]

        common = [
            {"key": "area", "name": "地区", "value": area_values},
            {"key": "year", "name": "年份", "value": year_values},
            {"key": "sort", "name": "排序", "value": sort_values},
        ]

        for tid in ["1", "2", "3", "4"]:
            filters[tid] = list(common)

        return filters

    # ==================== 通用视频列表解析 ====================
    def _parse_video_list(self, html):
        """解析视频列表 (movie-card格式)
        HTML结构:
        <div class="relative group movie-card cursor-pointe" data-vod-id="ch4alqj33">
          <a href="/play/ch4alqj33" class="block">
            <img data-src="https://..." src="placeholder" alt="金特务：本色回归" class="lazy ...">
            <span class="absolute bottom-0 ...">全10集</span>  (可选)
            <h3 class="text-white text-sm font-medium truncate mt-2 text-center">金特务：本色回归</h3>
          </a>
          ... (hover card with rating, year, etc.)
        </div>
        """
        videos = []
        seen_ids = set()

        # 匹配 movie-card 块
        pattern = re.compile(
            r'<div[^>]*class="[^"]*movie-card[^"]*"[^>]*data-vod-id="([^"]*)"[^>]*>([\s\S]*?)(?=<div[^>]*class="[^"]*movie-card|</div>\s*</div>\s*</div>\s*$)',
            re.MULTILINE
        )

        # 备用: 直接匹配 <a href="/play/{id}" class="block">
        pattern2 = re.compile(
            r'<a[^>]*href="/play/([a-z0-9]+)"[^>]*class="block"[^>]*>([\s\S]*?)</a>',
            re.MULTILINE
        )

        # 优先用 movie-card 块匹配
        for m in pattern.finditer(html):
            vid = m.group(1)
            if vid in seen_ids:
                continue
            seen_ids.add(vid)

            block = m.group(2)

            # 标题: alt 属性 或 <h3> 标签
            title = ""
            m_title = re.search(r'alt="([^"]*)"', block)
            if m_title:
                title = m_title.group(1).strip()
            if not title:
                m_title = re.search(r'<h3[^>]*>([^<]*)</h3>', block)
                if m_title:
                    title = m_title.group(1).strip()

            # 图片: data-src (懒加载)
            pic = ""
            m_pic = re.search(r'data-src="([^"]*)"', block)
            if m_pic:
                pic = m_pic.group(1)

            # 备注: <span class="absolute bottom-0 ...">全10集</span> 或 hover card 中的集数信息
            note = ""
            m_note = re.search(r'absolute bottom-0[^>]*>\s*([^<]*?)\s*</span>', block)
            if m_note:
                note = m_note.group(1).strip()
            if not note:
                # 从 hover card 中查找集数/评分
                m_note = re.search(r'text-yellow-500[^>]*>\s*([^<]*?)\s*</span>', block)
                if m_note:
                    note = m_note.group(1).strip()

            if title:
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": self._fix_pic(pic),
                    "vod_remarks": note,
                })

        # 如果没有匹配到 movie-card, 用备用匹配
        if not videos:
            for m in pattern2.finditer(html):
                vid = m.group(1)
                if vid in seen_ids:
                    continue
                seen_ids.add(vid)

                inner = m.group(2)

                # 标题
                title = ""
                m_title = re.search(r'alt="([^"]*)"', inner)
                if m_title:
                    title = m_title.group(1).strip()
                if not title:
                    m_title = re.search(r'<h3[^>]*>([^<]*)</h3>', inner)
                    if m_title:
                        title = m_title.group(1).strip()

                # 图片
                pic = ""
                m_pic = re.search(r'data-src="([^"]*)"', inner)
                if m_pic:
                    pic = m_pic.group(1)
                if not pic:
                    m_pic = re.search(r'src="([^"]*)"', inner)
                    if m_pic and "placeholder" not in m_pic.group(1):
                        pic = m_pic.group(1)

                # 备注
                note = ""
                m_note = re.search(r'absolute bottom-0[^>]*>\s*([^<]*?)\s*</span>', inner)
                if m_note:
                    note = m_note.group(1).strip()

                if title:
                    videos.append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": self._fix_pic(pic),
                        "vod_remarks": note,
                    })

        return videos

    def _parse_search_list(self, html):
        """解析搜索结果HTML, 返回完整视频对象列表
        搜索页结构: <div class="group relative"> <a href="/play/{id}" class="block"> ...
        图片用 src (非懒加载), 年份在 absolute top-2 left-2
        """
        videos = []
        seen = set()
        # 匹配搜索页的 <a href="/play/xxx" class="block">
        # class可能在href前或后, 用更灵活的匹配
        pattern = re.compile(
            r'<a[^>]*href="/play/([a-z0-9]+)"[^>]*>([\s\S]*?)</a>',
            re.MULTILINE
        )
        for m in pattern.finditer(html):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            full_tag = m.group(0)
            inner = m.group(2)

            # 只处理包含 class="block" 的链接 (排除导航、相关搜索等)
            if 'class="block"' not in full_tag and "class='block'" not in full_tag:
                continue

            # 标题: alt 属性 或 <h3> 标签
            title = ""
            m_t = re.search(r'alt="([^"]*)"', inner)
            if m_t:
                title = m_t.group(1).strip()
            if not title:
                m_t = re.search(r'<h3[^>]*>([^<]*)</h3>', inner)
                if m_t:
                    title = m_t.group(1).strip()

            # 图片: 优先 data-src (懒加载), 回退 src
            pic = ""
            m_pic = re.search(r'data-src="([^"]*)"', inner)
            if not m_pic:
                m_pic = re.search(r'data-original="([^"]*)"', inner)
            if not m_pic:
                m_pic = re.search(r'<img[^>]*src="([^"]*)"', inner)
            if m_pic:
                pic = m_pic.group(1)

            # 备注: 年份标签 <div class="absolute top-2 left-2 ...">2022</div>
            note = ""
            m_note = re.search(r'absolute top-2 left-2[^>]*>\s*([^<]*?)\s*</div>', inner)
            if m_note:
                note = m_note.group(1).strip()
            if not note:
                # 备用: 集数标签 <span class="absolute bottom-0 ...">全10集</span>
                m_note = re.search(r'absolute bottom-0[^>]*>\s*([^<]*?)\s*</span>', inner)
                if m_note:
                    note = m_note.group(1).strip()
            if not note:
                # 备用: 评分标签
                m_note = re.search(r'text-yellow-500[^>]*>\s*([^<]*?)\s*</span>', inner)
                if m_note:
                    note = m_note.group(1).strip()

            if title:
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": self._fix_pic(pic),
                    "vod_remarks": note,
                })

        # 回退: 如果没匹配到, 尝试通用列表解析器
        if not videos:
            videos = self._parse_video_list(html)

        return videos

    # ==================== 首页 ====================
    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        try:
            result["class"] = self.cats
            if filter:
                result["filters"] = self._build_filters()

            html = self._req("/")
            if html:
                result["list"] = self._parse_video_list(html)
        except Exception as e:
            print("homeContent error: {0}".format(e))
        return result

    def homeVideoContent(self):
        pass

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg) if pg else 1, "pagecount": 1, "limit": 24, "total": 0}
        try:
            page = int(pg) if pg else 1

            # 构建筛选URL: /filter?classify={tid}&areas={areas}&years={years}&sort_by={sort}&order=desc&page={page}
            params = {"classify": tid}

            if extend:
                if extend.get("area"):
                    params["areas"] = str(extend["area"])
                if extend.get("year"):
                    params["years"] = str(extend["year"])
                if extend.get("sort"):
                    params["sort_by"] = str(extend["sort"])
                    params["order"] = "desc"

            params["page"] = str(page)

            path = "/filter?" + urlencode(params)

            html = self._req(path)
            if html:
                videos = self._parse_video_list(html)
                result["list"] = videos
                result["page"] = page
                result["total"] = len(videos)

                # 解析总页数: 从分页链接中提取最大页码 (注意HTML编码 &amp;)
                page_nums = [int(x) for x in re.findall(r'(?:&amp;|&)[?]?page=(\d+)', html)]
                if not page_nums:
                    page_nums = [int(x) for x in re.findall(r'page=(\d+)', html)]
                if page_nums:
                    result["pagecount"] = max(page_nums)
                else:
                    result["pagecount"] = 1 if len(videos) < 24 else page + 1

        except Exception as e:
            print("categoryContent error: {0}".format(e))
        return result

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            if not key:
                return result
            page = int(pg) if pg else 1
            # URL编码搜索关键词
            path = "/search?q=" + quote(str(key))
            if page > 1:
                path += "&page=" + str(page)
            # 搜索请求带Referer, 避免被反爬拦截
            old_header = self.header
            self.header = dict(self.header)
            self.header["Referer"] = self.host + "/"
            html = self._req(path)
            self.header = old_header
            if html:
                result["list"] = self._parse_search_list(html)
        except Exception as e:
            print("searchContent error: {0}".format(e))
        return result

    # ==================== 详情 ====================
    def detailContent(self, ids):
        result = {}
        try:
            vid = ids[0]
            path = "/play/" + vid
            html = self._req(path)
            if not html:
                return result

            vod = {
                "vod_id": vid,
                "vod_name": "",
                "vod_pic": "",
                "type_name": "",
                "vod_year": "",
                "vod_area": "",
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "",
                "vod_play_url": "",
            }

            # 标题: <h1 class="text-xl font-bold text-white">金特务：本色回归</h1>
            m = re.search(r'<h1[^>]*class="[^"]*font-bold[^"]*"[^>]*>([^<]*)</h1>', html)
            if m:
                vod["vod_name"] = m.group(1).strip()

            # 海报图片: video-player data-poster
            m = re.search(r'data-poster="([^"]*)"', html)
            if m:
                vod["vod_pic"] = self._fix_pic(m.group(1))

            # 详细信息: grid-cols-3 结构
            # <div class="col-span-1 text-gray-500">导演</div>
            # <div class="col-span-2 text-gray-300">李胜英</div>
            detail_pattern = re.compile(
                r'<div class="col-span-1 text-gray-500">([^<]*)</div>\s*<div class="col-span-2 text-gray-300">([^<]*)</div>'
            )
            for m in detail_pattern.finditer(html):
                key = m.group(1).strip()
                val = m.group(2).strip()

                if key == "导演":
                    vod["vod_director"] = val
                elif key == "主演":
                    vod["vod_actor"] = val
                elif key == "类型":
                    vod["type_name"] = val
                elif key == "地区":
                    vod["vod_area"] = val
                elif key == "上映":
                    vod["vod_year"] = val[:4] if val[:4].isdigit() else val

            # 剧情简介: <p class="text-xs text-gray-300 leading-relaxed">...</p>
            m = re.search(r'剧情简介[\s\S]*?<p class="text-xs text-gray-300 leading-relaxed">([\s\S]*?)</p>', html)
            if m:
                vod["vod_content"] = m.group(1).strip()

            # 备注: 集数信息 "全10集"
            m = re.search(r'全(\d+)集', html)
            if m:
                vod["vod_remarks"] = "全" + m.group(1) + "集"
            else:
                # 可能是电影
                m = re.search(r'<p class="text-sm text-gray-400 mt-1">([^<]*)</p>', html)
                if m:
                    vod["vod_remarks"] = m.group(1).strip()

            # 提取 userlink (WASM签名必需)
            userlink = "0"
            m = re.search(r"userlink:'([^']*)'", html)
            if m:
                userlink = m.group(1)
            if not userlink or userlink == "0":
                m = re.search(r'userlink:\s*"([^"]*)"', html)
                if m:
                    userlink = m.group(1)

            # 播放源和集数
            # 剧集在 episodeManager 的 div 内
            # <div x-data="episodeManager(1, 1, [{ lineName: 'alists', episodeCount: 10 }])">
            #   <a href="/play/ch4alqj33" ... data-line="1" data-episode="1" dataid="35648">1</a>
            #   <a href="/play/ch4alqj3j" ... data-line="1" data-episode="2" dataid="35649">2</a>

            # 先提取 episodeManager 区域
            ep_section = ""
            m_ep_section = re.search(r'x-data="episodeManager\([^)]*\)"([\s\S]*?)(?:</div>\s*</div>\s*</div>|<div x-data="(?!episodeManager))', html)
            if m_ep_section:
                ep_section = m_ep_section.group(1)
            else:
                # 备用: 从 "选集" 标题到 "相关推荐" 之间
                m_start = re.search(r'<h2[^>]*>选集</h2>', html)
                m_end = re.search(r'<h2[^>]*>相关推荐</h2>', html)
                if m_start and m_end:
                    ep_section = html[m_start.end():m_end.start()]
                elif m_start:
                    ep_section = html[m_start.end():m_start.end() + 5000]

            episodes = []
            seen_eps = set()

            if ep_section:
                # 匹配剧集链接 (属性顺序不固定)
                ep_pattern = re.compile(
                    r'<a[^>]*href="/play/([a-z0-9]+)"[^>]*>([\s\S]*?)</a>'
                )

                for m in ep_pattern.finditer(ep_section):
                    play_id = m.group(1)
                    full_tag = m.group(0)
                    inner = m.group(2)

                    # 提取 dataid
                    m_dataid = re.search(r'dataid="(\d+)"', full_tag)
                    dataid = m_dataid.group(1) if m_dataid else ""

                    # 提取集号 (data-episode)
                    m_ep = re.search(r'data-episode="(\d+)"', full_tag)
                    ep_num = int(m_ep.group(1)) if m_ep else 0

                    # 提取线路 (data-line)
                    m_line = re.search(r'data-line="(\d+)"', full_tag)
                    line = int(m_line.group(1)) if m_line else 1

                    # 从显示文本中提取集号
                    m_text = re.search(r'<span[^>]*x-show="!isEpisodeActive[^"]*"[^>]*>\s*(\d+)\s*</span>', inner)
                    if m_text:
                        ep_num = int(m_text.group(1))

                    ep_key = "{0}-{1}".format(line, ep_num)
                    if ep_key in seen_eps:
                        continue
                    seen_eps.add(ep_key)

                    episodes.append({
                        "play_id": play_id,
                        "dataid": dataid,
                        "line": line,
                        "ep_num": ep_num,
                        "name": "第{0}集".format(ep_num) if ep_num > 0 else "正片",
                    })

            # 构建播放列表
            if episodes:
                # 按线路分组
                lines = {}
                for ep in episodes:
                    line = ep["line"]
                    if line not in lines:
                        lines[line] = []
                    lines[line].append(ep)

                # 排序每条线路的集数
                for line in lines:
                    lines[line].sort(key=lambda x: x["ep_num"])

                play_from_list = []
                play_url_list = []

                for line in sorted(lines.keys()):
                    eps = lines[line]
                    line_name = "线路{0}".format(line) if len(lines) > 1 else "4K影视"

                    # 格式: 集名$dataid|play_id|userlink
                    url_parts = []
                    for ep in eps:
                        url_parts.append("{0}${1}|{2}|{3}".format(
                            ep["name"], ep["dataid"], ep["play_id"], userlink))

                    play_from_list.append(line_name)
                    play_url_list.append("#".join(url_parts))

                vod["vod_play_from"] = "$$$".join(play_from_list)
                vod["vod_play_url"] = "$$$".join(play_url_list)
            else:
                # 单集 (电影)
                md = re.search(r'dataid="(\d+)"', html)
                dataid = md.group(1) if md else ""
                vod["vod_play_from"] = "4K影视"
                vod["vod_play_url"] = "正片${0}|{1}|{2}".format(dataid, vid, userlink)

            result["list"] = [vod]
        except Exception as e:
            print("detailContent error: {0}".format(e))
        return result

    # ==================== WASM 签名播放 ====================
    _WASM_MODULE = "./nbmovie_wasm_bg.js"

    def _wasm_init(self):
        """延迟初始化 wasmtime 引擎、模块、链接器"""
        if self._wasm_ready:
            return True
        if not self._wasm_file:
            # 检查所有可能的位置
            _script_dir = os.path.dirname(os.path.abspath(__file__))
            for p in [
                os.path.join(_script_dir, "nbmovie_wasm_bg.d5d51939.wasm"),
                os.path.join(_script_dir, "nbmovie_wasm_bg.wasm"),
                "/data/user/work/nbmovie_wasm_bg.d5d51939.wasm",
            ]:
                if os.path.exists(p):
                    self._wasm_file = p
                    break
        if not self._wasm_file:
            # 尝试下载
            _script_dir = os.path.dirname(os.path.abspath(__file__))
            save_path = os.path.join(_script_dir, "nbmovie_wasm_bg.d5d51939.wasm")
            self._wasm_file = self._download_wasm(save_path)
            if not self._wasm_file:
                return False
        try:
            import wasmtime
        except ImportError:
            print("wasmtime not installed, will use sniffing fallback")
            return False
        try:
            self._wasm_engine = wasmtime.Engine()
            self._wasm_module = wasmtime.Module.from_file(self._wasm_engine, self._wasm_file)
            self._wasm_linker = wasmtime.Linker(self._wasm_engine)
            self._wasm_linker.allow_shadowing = True

            i32 = wasmtime.ValType.i32()
            f64 = wasmtime.ValType.f64()
            M = self._WASM_MODULE

            # __wbg_now: () -> f64 (当前毫秒时间戳, 签名必需)
            self._wasm_linker.define_func(M, "__wbg_now_16f0c993d5dd6c27",
                wasmtime.FuncType([], [f64]),
                lambda: float(time.time() * 1000))

            # 静态访问器: () -> i32 (返回0=无window/document)
            ret_i32 = wasmtime.FuncType([], [i32])
            for n in [
                "__wbg_static_accessor_GLOBAL_8adb955bd33fac2f",
                "__wbg_static_accessor_GLOBAL_THIS_ad356e0db91c7913",
                "__wbg_static_accessor_WINDOW_bb9f1ba69d61b386",
                "__wbg_static_accessor_SELF_f207c857566db248",
            ]:
                self._wasm_linker.define_func(M, n, ret_i32, lambda: 0)

            # (i32) -> i32: instanceof / is_undefined / clone_ref / document
            i32_i32 = wasmtime.FuncType([i32], [i32])
            for n in [
                "__wbg___wbindgen_is_undefined_52709e72fb9f179c",
                "__wbg_instanceof_Window_23e677d2c6843922",
                "__wbg_instanceof_HtmlMetaElement_07f78901e9785572",
                "__wbindgen_object_clone_ref",
                "__wbg_document_c0320cd4183c6d9b",
            ]:
                self._wasm_linker.define_func(M, n, i32_i32, lambda a0: 0)

            # (i32) -> (): drop_ref
            self._wasm_linker.define_func(M, "__wbindgen_object_drop_ref",
                wasmtime.FuncType([i32], []), lambda a0: None)

            # (i32, i32, i32) -> i32: getElementById
            self._wasm_linker.define_func(M, "__wbg_getElementById_d1f25d287b19a833",
                wasmtime.FuncType([i32, i32, i32], [i32]),
                lambda a0, a1, a2: 0)

            # (i32, i32) -> (): content
            self._wasm_linker.define_func(M, "__wbg_content_4373268a6f34e443",
                wasmtime.FuncType([i32, i32], []),
                lambda a0, a1: None)

            # (i32, i32) -> !: throw
            def _throw(a0, a1):
                raise Exception("WASM throw")
            self._wasm_linker.define_func(M, "__wbg___wbindgen_throw_6ddd609b62940d55",
                wasmtime.FuncType([i32, i32], []), _throw)

            self._wasm_ready = True
            return True
        except Exception as e:
            print("wasmtime init error: {0}".format(e))
            self._wasm_engine = None
            return False

    def _build_play_url(self, dataid, play_id, userlink, quality="1080"):
        """用 Python wasmtime 直接运行 WASM 生成签名URL (无需Node.js)"""
        if not self._wasm_init():
            return None
        try:
            import wasmtime
            store = wasmtime.Store(self._wasm_engine)
            instance = self._wasm_linker.instantiate(store, self._wasm_module)
            exports = instance.exports(store)
            memory = exports["memory"]
            build_fn = exports["build_play_url"]
            malloc_fn = exports["__wbindgen_export"]
            stack_fn = exports["__wbindgen_add_to_stack_pointer"]
            free_fn = exports["__wbindgen_export3"]

            def _write_str(s):
                buf = str(s).encode('utf-8')
                ptr = malloc_fn(store, len(buf), 1)
                mem = memory.data_ptr(store)
                for i, b in enumerate(buf):
                    mem[ptr + i] = b
                return ptr, len(buf)

            def _read_str(ptr, length):
                mem = memory.data_ptr(store)
                return bytes(mem[ptr:ptr + length]).decode('utf-8', errors='replace')

            retptr = stack_fn(store, -16)
            try:
                p0, l0 = _write_str(dataid)
                p1, l1 = _write_str(play_id)
                p2, l2 = _write_str(quality)
                p3, l3 = _write_str(userlink)
                build_fn(store, retptr, p0, l0, p1, l1, p2, l2, p3, l3)
                mem = memory.data_ptr(store)
                r0 = struct.unpack_from('<i', bytes(mem[retptr:retptr+4]))[0]
                r1 = struct.unpack_from('<i', bytes(mem[retptr+4:retptr+8]))[0]
                result = _read_str(r0, r1)
                free_fn(store, r0, r1, 1)
                return result
            finally:
                stack_fn(store, 16)
        except Exception as e:
            print("WASM build_play_url error: {0}".format(e))
            return None

    def _encode_video_url(self, url):
        """URL编码视频地址路径中的中文等非ASCII字符"""
        if not url:
            return url
        parsed = urlparse(url)
        encoded_path = quote(parsed.path, safe='/')
        return urlunparse((parsed.scheme, parsed.netloc, encoded_path,
                           parsed.params, parsed.query, parsed.fragment))

    def _sniff_result(self, play_id):
        """构建嗅探模式返回值: 兜底方案, TVBox打开播放页自动嗅探"""
        return {
            "parse": 1,
            "jx": 0,
            "url": self.host + "/play/" + play_id,
            "header": json.dumps({"User-Agent": self.ua, "Referer": self.host + "/"}),
        }

    def _get_userlink(self, play_id):
        """从播放页HTML获取userlink (WASM签名k参数需要)"""
        try:
            html = self._req("/play/" + play_id)
            if html:
                m = re.search(r"userlink:'([^']*)'", html)
                if m:
                    return m.group(1)
                m = re.search(r'userlink:\s*"([^"]*)"', html)
                if m:
                    return m.group(1)
        except:
            pass
        return "0"

    def playerContent(self, flag, id, vipFlags):
        """返回直链给ExoPlayer播放 (parse=0), WASM签名失败时回退嗅探"""
        result = {"parse": 0, "playUrl": "", "url": "", "header": "", "jx": 0}
        try:
            # id格式: 集名$dataid|play_id|userlink
            data = id.split("$")[-1] if "$" in id else id
            if "|" not in data:
                # 无dataid参数，回退嗅探播放页
                return self._sniff_result(data)

            parts = data.split("|")
            dataid, play_id = parts[0], parts[1]
            userlink = parts[2] if len(parts) > 2 else "0"

            # userlink为0时从播放页获取
            if not userlink or userlink == "0":
                userlink = self._get_userlink(play_id)

            # 1. WASM签名获取API路径 (Python wasmtime, 无需Node.js)
            signed = self._build_play_url(dataid, play_id, userlink)
            if not signed:
                print("WASM sign failed, sniffing: /play/{0}".format(play_id))
                return self._sniff_result(play_id)

            # 2. 请求API获取视频直链 (M3U8或MP4)
            try:
                rsp = self.fetch(self.host + signed, headers=self.header)
                api = json.loads(rsp.text if hasattr(rsp, 'text') else rsp)
                if api.get("code") == 200 and api.get("data"):
                    qu = api["data"].get("quality_urls", [])
                    if qu:
                        # 取第一个可用画质 (跳过VIP锁定的)
                        video_url = ""
                        for q in qu:
                            if q.get("locked") or q.get("isvip"):
                                continue
                            url = q.get("url", "")
                            if url and url != "1" and url != "0":
                                video_url = url
                                break
                        # 如果全部锁定，取第一个有URL的
                        if not video_url:
                            for q in qu:
                                url = q.get("url", "")
                                if url and url != "1" and url != "0":
                                    video_url = url
                                    break
                        if video_url:
                            # M3U8和MP4都可以用parse=0直接播放
                            result["url"] = video_url
                            result["header"] = json.dumps({
                                "User-Agent": self.ua,
                                "Referer": self.host + "/",
                            })
                            return result
            except Exception as e:
                print("API error: {0}".format(e))

            # 3. API失败, 回退嗅探播放页
            print("API failed, sniffing: /play/{0}".format(play_id))
            return self._sniff_result(play_id)

        except Exception as e:
            print("playerContent error: {0}".format(e))
            pid = str(id).split("$")[-1].split("|")[1] if "|" in str(id) else str(id)
            return self._sniff_result(pid)

    # ==================== 辅助 ====================
    def isVideo(self, url):
        return False