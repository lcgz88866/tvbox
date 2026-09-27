#coding=utf-8
#!/usr/bin/python
# 绿色影视 (lvsc168.com) - PHP影视CMS
# 列表: /frim/{type_id}-{page}.html (第1页可省略-0)
# 详情: /movie/{vod_id}.html
# 播放: /play/{vod_id}-{line}-{episode}.html -> 分享链接 -> m3u8
# 搜索: /search.php?searchword={keyword}
# 筛选: /search.php?searchtype=5&tid={id}&area={area}&year={year}&order={order}&page={page}
import sys
sys.path.append('..')
from base.spider import Spider
import json
import re
import base64
from urllib.parse import quote, urljoin

class Spider(Spider):

    def getName(self):
        return "绿色影视"

    def init(self, extend=""):
        self.host = "https://www.lvsc168.com"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.header = {
            "User-Agent": self.ua,
            "Referer": self.host + "/",
        }

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

    def _fetch_html(self, url):
        """获取页面HTML"""
        try:
            rsp = self.fetch(url, headers=self.header)
            return rsp.text
        except Exception as e:
            print("_fetch_html error: {0}".format(e))
            return ""

    def _strip_html(self, text):
        """去除HTML标签"""
        if not text:
            return ""
        return re.sub(r'<[^>]+>', '', text).strip()

    # ==================== 分类配置 ====================
    cats = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "电视剧", "type_id": "2"},
        {"type_name": "综艺", "type_id": "3"},
        {"type_name": "动漫", "type_id": "4"},
        {"type_name": "短剧", "type_id": "26"},
        {"type_name": "动作片", "type_id": "5"},
        {"type_name": "爱情片", "type_id": "6"},
        {"type_name": "科幻片", "type_id": "7"},
        {"type_name": "恐怖片", "type_id": "8"},
        {"type_name": "战争片", "type_id": "9"},
        {"type_name": "喜剧片", "type_id": "10"},
        {"type_name": "纪录片", "type_id": "11"},
        {"type_name": "剧情片", "type_id": "12"},
        {"type_name": "大陆剧", "type_id": "13"},
        {"type_name": "港台剧", "type_id": "14"},
        {"type_name": "欧美剧", "type_id": "15"},
        {"type_name": "日韩剧", "type_id": "16"},
        {"type_name": "泰剧", "type_id": "27"},
    ]

    # extend key -> URL参数名 的映射
    _filter_key_map = {
        "area": "area",
        "year": "year",
        "by": "order",
    }

    def _build_filters(self):
        """构建筛选器"""
        filters = {}
        # 通用筛选器
        common = [
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""},
                {"n": "大陆", "v": "大陆"},
                {"n": "香港", "v": "香港"},
                {"n": "台湾", "v": "台湾"},
                {"n": "日本", "v": "日本"},
                {"n": "韩国", "v": "韩国"},
                {"n": "欧美", "v": "欧美"},
                {"n": "泰国", "v": "泰国"},
                {"n": "其他", "v": "其他"},
            ]},
            {"key": "year", "name": "年份", "value": [
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
                {"n": "更早", "v": "2017"},
            ]},
            {"key": "by", "name": "排序", "value": [
                {"n": "最新", "v": "time"},
                {"n": "最热", "v": "hit"},
                {"n": "推荐", "v": "commend"},
            ]},
        ]
        for cat in self.cats:
            filters[cat["type_id"]] = common
        return filters

    # ==================== 首页 ====================
    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        try:
            result["class"] = self.cats
            if filter:
                result["filters"] = self._build_filters()

            # 首页推荐: 电影分类第1页
            html = self._fetch_html(self.host + "/frim/1.html")
            if html:
                result["list"] = self._parse_list(html)
        except Exception as e:
            print("homeContent error: {0}".format(e))
        return result

    def homeVideoContent(self):
        pass

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
        try:
            page = int(pg) if int(pg) >= 1 else 1

            # 判断是否有筛选条件
            has_filter = False
            if extend:
                for v in extend.values():
                    if v:
                        has_filter = True
                        break

            if has_filter:
                # 使用 search.php 筛选
                params = ["searchtype=5", "tid={0}".format(tid), "page={0}".format(page)]
                for k, v in extend.items():
                    if not v:
                        continue
                    field = self._filter_key_map.get(k, k)
                    params.append("{0}={1}".format(field, quote(str(v))))
                url = "{0}/search.php?{1}".format(self.host, "&".join(params))
            else:
                # 使用 /frim/{tid}-{page}.html
                if page == 1:
                    url = "{0}/frim/{1}.html".format(self.host, tid)
                else:
                    url = "{0}/frim/{1}-{2}.html".format(self.host, tid, page)

            html = self._fetch_html(url)
            if html:
                result["list"] = self._parse_list(html)
                # 解析分页
                result["pagecount"] = self._parse_pagecount(html)
                result["total"] = result["pagecount"] * result["limit"]
            result["page"] = page
        except Exception as e:
            print("categoryContent error: {0}".format(e))
        return result

    def _parse_list(self, html):
        """解析列表页视频项"""
        videos = []
        try:
            # 格式: <a class="myui-vodlist__thumb lazyload" href="/movie/{id}.html" title="{name}" data-original="{pic}">
            #          <span class="pic-tag pic-tag-top">{score}</span>
            #          <span class="pic-text text-right">{remarks}</span>
            #        </a>
            pattern = r'<a[^>]*class="myui-vodlist__thumb[^"]*"[^>]*href="/movie/(\d+)\.html"[^>]*title="([^"]*)"[^>]*data-original="([^"]*)"[^>]*>(.*?)</a>'
            for m in re.finditer(pattern, html, re.S):
                vod_id = m.group(1)
                vod_name = m.group(2)
                vod_pic = m.group(3)
                inner = m.group(4)

                # 提取备注
                remarks = ""
                remarks_m = re.search(r'class="pic-text[^"]*"[^>]*>([^<]+)<', inner)
                if remarks_m:
                    remarks = remarks_m.group(1).strip()

                # 图片URL处理: /img.php?url={actual_url}
                if vod_pic.startswith("/img.php?url="):
                    vod_pic = vod_pic.replace("/img.php?url=", "")
                elif vod_pic.startswith("/"):
                    vod_pic = self.host + vod_pic

                videos.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": remarks,
                })
        except Exception as e:
            print("_parse_list error: {0}".format(e))
        return videos

    def _parse_pagecount(self, html):
        """解析总页数"""
        try:
            # 找分页链接中的最大页码
            # 格式: /frim/1-633.html 或 search.php?page=633
            pages = re.findall(r'(?:/frim/\d+-(\d+)\.html|page=(\d+))', html)
            max_page = 1
            for p in pages:
                for num in p:
                    if num:
                        max_page = max(max_page, int(num))
            return max_page
        except:
            return 1

    # ==================== 详情 ====================
    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            url = "{0}/movie/{1}.html".format(self.host, vod_id)
            html = self._fetch_html(url)
            if html:
                detail = self._parse_detail(html, vod_id)
                if detail:
                    result["list"].append(detail)
        except Exception as e:
            print("detailContent error: {0}".format(e))
        return result

    def _parse_detail(self, html, vod_id):
        """解析详情页"""
        try:
            # 标题
            vod_name = ""
            title_m = re.search(r'<title>《([^》]+)》', html)
            if title_m:
                vod_name = title_m.group(1)
            if not vod_name:
                title_m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
                if title_m:
                    vod_name = title_m.group(1).strip()

            # 封面图
            vod_pic = ""
            pic_m = re.search(r'<img[^>]*class="[^"]*lazyload[^"]*"[^>]*data-original="([^"]+)"', html)
            if pic_m:
                vod_pic = pic_m.group(1)
                if vod_pic.startswith("/img.php?url="):
                    vod_pic = vod_pic.replace("/img.php?url=", "")
                elif vod_pic.startswith("/"):
                    vod_pic = self.host + vod_pic

            # 分类
            type_name = ""
            # 从标题中提取，格式: 《xxx》... - 大陆剧 - 绿色影视
            type_m = re.search(r'-\s*([^-\s]+)\s*-\s*绿色影视', html)
            if type_m:
                type_name = type_m.group(1).strip()

            # 信息字段: <span class="text-muted">字段：</span> 后面跟 <a> 或文本
            # 注意: 分类/地区/年份在同一个<p>中，用<span class="text-muted">分隔
            # 所以提取时要在下一个 <span class="text-muted 或 </p> 处停止
            def extract_field(label):
                # 匹配: <span class="text-muted">label：</span> 后面的内容
                # 停止条件: </p> 或 <p 或 <span class="split-line 或 下一个 <span class="text-muted
                pattern = r'<span class="text-muted[^"]*">\s*' + label + r'[：:]\s*</span>\s*(.*?)(?:</p>|<p|<span class="split-line"|<span class="text-muted")'
                m = re.search(pattern, html, re.S)
                if m:
                    content = m.group(1)
                    # 优先提取a标签中的文本(主演/导演/地区/年份等都是a标签)
                    links = re.findall(r'<a[^>]*>([^<]+)</a>', content)
                    if links:
                        texts = [l.strip() for l in links if l.strip() and l.strip() != '..']
                        return ', '.join(texts)
                    # 如果没有a标签，直接取文本
                    return self._strip_html(content).replace('&nbsp;', ' ').strip()
                return ""

            vod_year = extract_field("年份")
            vod_area = extract_field("地区")
            vod_actor = extract_field("主演")
            vod_director = extract_field("导演")
            vod_lang = extract_field("语言")

            # 状态/备注: 优先从标题旁的font标签提取(如"已完结"/"更新至XX集")
            # h1 class 可能是 "title text-fff" 等多种形式
            vod_remarks = ""
            font_m = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>.*?<font[^>]*>([^<]+)</font>', html, re.S)
            if font_m:
                vod_remarks = font_m.group(1).strip()
            if not vod_remarks:
                vod_remarks = extract_field("状态")
            if not vod_remarks:
                vod_remarks = extract_field("更新")

            # 简介
            vod_content = ""
            # 先找 sketch 区域
            sketch_m = re.search(r'<span class="sketch[^"]*"[^>]*>(.*?)(?:<a|</span)', html, re.S)
            if sketch_m:
                vod_content = self._strip_html(sketch_m.group(1))
            # 如果没有，找完整简介
            if not vod_content:
                content_m = re.search(r'id="jq"[^>]*>(.*?)</div>', html, re.S)
                if content_m:
                    vod_content = self._strip_html(content_m.group(1))
            # 兜底
            if not vod_content:
                vod_content = extract_field("简介")

            # 播放源
            # 线路名称: <a href="#playlist{n}" ...>name</a>
            # 播放链接: <a href="/play/{id}-{line}-{ep}.html">第XX集</a>
            play_from_list = []
            play_url_list = []

            # 找线路名称
            tab_pattern = r'<a[^>]*href="#playlist(\d+)"[^>]*>([^<]+)</a>'
            tabs = re.findall(tab_pattern, html)

            # 找每个playlist的集数
            for playlist_id, playlist_name in tabs:
                # 找 playlist{id} 中的播放链接
                # 注意: playlist中的line编号不一定是playlist_id
                # 实际链接格式: /play/{vod_id}-{line}-{ep}.html
                # line编号需要从实际链接中提取

                # 找该playlist区域内的播放链接
                playlist_pattern = r'id="playlist' + playlist_id + r'"[^>]*>(.*?)</ul>'
                playlist_m = re.search(playlist_pattern, html, re.S)
                if not playlist_m:
                    playlist_pattern = r'id="playlist' + playlist_id + r'"[^>]*>(.*?)</div>'
                    playlist_m = re.search(playlist_pattern, html, re.S)

                if playlist_m:
                    playlist_html = playlist_m.group(1)
                    # 提取播放链接
                    ep_pattern = r'<a[^>]*href="/play/' + vod_id + r'-(\d+)-(\d+)\.html"[^>]*>([^<]+)</a>'
                    episodes = re.findall(ep_pattern, playlist_html)

                    if episodes:
                        # 使用第一个链接的line编号
                        line_num = episodes[0][0]
                        ep_list = []
                        for line, ep, ep_name in episodes:
                            play_id = "{0}-{1}-{2}".format(vod_id, line, ep)
                            ep_list.append("{0}${1}".format(ep_name.strip(), play_id))
                        if ep_list:
                            play_from_list.append(playlist_name.strip())
                            play_url_list.append("#".join(ep_list))

            # 如果没有找到tab，尝试直接找所有播放链接
            if not play_from_list:
                all_links = re.findall(r'<a[^>]*href="/play/' + vod_id + r'-(\d+)-(\d+)\.html"[^>]*>([^<]+)</a>', html)
                if all_links:
                    # 按line分组
                    lines = {}
                    for line, ep, ep_name in all_links:
                        if line not in lines:
                            lines[line] = []
                        play_id = "{0}-{1}-{2}".format(vod_id, line, ep)
                        lines[line].append("{0}${1}".format(ep_name.strip(), play_id))

                    for line in sorted(lines.keys()):
                        play_from_list.append("线路{0}".format(int(line) + 1))
                        play_url_list.append("#".join(lines[line]))

            return {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "type_name": type_name,
                "vod_year": vod_year,
                "vod_area": vod_area,
                "vod_lang": vod_lang,
                "vod_remarks": vod_remarks,
                "vod_actor": vod_actor,
                "vod_director": vod_director,
                "vod_content": vod_content,
                "vod_play_from": "$$$".join(play_from_list),
                "vod_play_url": "$$$".join(play_url_list),
            }
        except Exception as e:
            print("_parse_detail error: {0}".format(e))
            return None

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            page = int(pg) if int(pg) >= 1 else 1
            url = "{0}/search.php?searchword={1}&page={2}".format(self.host, quote(key), page)
            html = self._fetch_html(url)
            if html:
                result["list"] = self._parse_list(html)
        except Exception as e:
            print("searchContent error: {0}".format(e))
        return result

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "playUrl": "", "jx": 0, "url": "", "header": ""}
        try:
            # id格式: {vod_id}-{line}-{episode}
            play_url = "{0}/play/{1}.html".format(self.host, id)
            html = self._fetch_html(play_url)
            if not html:
                return result

            # 提取 var now=base64decode("xxx")，允许空值
            now_m = re.search(r'var\s+now\s*=\s*base64decode\(["\']([^"\']*)["\']', html)
            if not now_m or not now_m.group(1):
                # var now 为空，该线路无播放源
                return result

            share_b64 = now_m.group(1)
            share_url = base64.b64decode(share_b64).decode('utf-8')

            # 情况1: 分享链接本身就是 m3u8 直链
            if '.m3u8' in share_url:
                result["parse"] = 0
                result["url"] = share_url
                result["header"] = json.dumps({
                    "User-Agent": self.ua,
                    "Referer": self.host + "/",
                })
                return result

            # 情况2: 分享链接是页面，访问获取 m3u8
            share_html = self._fetch_html(share_url)
            if not share_html:
                return result

            from urllib.parse import urlparse
            parsed = urlparse(share_url)
            cdn_host = "{0}://{1}".format(parsed.scheme, parsed.netloc)

            # 2a: 提取 var main = "xxx" (m3u8相对路径)
            main_m = re.search(r'var\s+main\s*=\s*["\']([^"\']+)', share_html)
            if main_m:
                main_path = main_m.group(1).replace('\\/', '/').replace('\\', '')
                m3u8_url = cdn_host + main_path
                result["parse"] = 0
                result["url"] = m3u8_url
                result["header"] = json.dumps({
                    "User-Agent": self.ua,
                    "Referer": cdn_host + "/",
                })
                return result

            # 2b: 直接搜索页面中的完整 m3u8 链接
            m3u8_matches = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', share_html)
            if m3u8_matches:
                m3u8_url = m3u8_matches[0]
                result["parse"] = 0
                result["url"] = m3u8_url
                result["header"] = json.dumps({
                    "User-Agent": self.ua,
                    "Referer": cdn_host + "/",
                })
                return result

            # 2c: 搜索相对路径的 m3u8 (如 /xxx/xxx.m3u8)
            rel_m = re.search(r'["\'](/[^"\']*\.m3u8[^"\']*)["\']', share_html)
            if rel_m:
                m3u8_url = cdn_host + rel_m.group(1)
                result["parse"] = 0
                result["url"] = m3u8_url
                result["header"] = json.dumps({
                    "User-Agent": self.ua,
                    "Referer": cdn_host + "/",
                })
                return result

            # 情况3: 第三方平台链接(如爱奇艺/优酷等)，无法提取直链，走嗅探兜底
            result["parse"] = 1
            result["url"] = share_url

        except Exception as e:
            print("playerContent error: {0}".format(e))
        return result

    # ==================== 配置 ====================
    config = {
        "player": {},
        "filter": {}
    }
    header = {}

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]