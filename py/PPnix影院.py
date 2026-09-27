# -*- coding: utf-8 -*-
# PPnix影院 - www.ppnix.com
# 帝国CMS + ArtPlayer + AES-128加密HLS, IPFS分发
# 播放: localProxy修改m3u8, 将AES key以data URI形式嵌入
import re
import sys
import json
import ssl
import base64
import urllib.parse
import urllib.request

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def getName(self):
        return "PPnix影院"

    def init(self, extend=""):
        self.host = "https://www.ppnix.com"
        self.ua = "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Referer": self.host,
        }
        self.cats = [
            {"type_name": "电影", "type_id": "movie"},
            {"type_name": "电视剧", "type_id": "tv"},
        ]
        # 类型筛选
        self.genre_filters = {
            "movie": ["剧情","喜剧","动作","惊悚","爱情","犯罪","冒险","恐怖","悬疑","奇幻","科幻","动画","战争","历史","传记","家庭","音乐","同性","纪录片","歌舞","古装","运动","灾难","武侠","西部","儿童","短片","黑色电影","戏曲"],
            "tv": ["剧情","犯罪","爱情","悬疑","喜剧","奇幻","惊悚","动作","科幻","古装","冒险","恐怖","动画","历史","战争","同性","西部","武侠","传记","家庭","真人秀","短片","运动","灾难","纪录片","热血","战斗"],
        }
        # 地区筛选
        self.country_filters = {
            "movie": ["美国","英国","日本","法国","中国大陆","中国香港","韩国","德国","加拿大","意大利","西班牙","澳大利亚","台湾","印度","泰国","俄罗斯"],
            "tv": ["美国","中国大陆","韩国","英国","日本","台湾","中国香港","泰国","法国","新加坡","澳大利亚","加拿大"],
        }
        # 年份筛选
        self.year_filters = {
            "movie": ["2026","2025","2024","2023","2022","2021","2020","2019","2018","2017","2016","2015","2014","2013","2012","2011","2010"],
            "tv": ["2026","2025","2024","2023","2022","2021","2020","2019","2018","2017","2016","2015","2014","2013","2012","2011","2010"],
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

    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        try:
            result["class"] = self.cats
            # 构建筛选器
            for cat in self.cats:
                tid = cat["type_id"]
                fl = []
                # 类型
                genre_list = self.genre_filters.get(tid, [])
                if genre_list:
                    genre_values = [{"n": "全部", "v": ""}]
                    for g in genre_list:
                        genre_values.append({"n": g, "v": g})
                    fl.append({"key": "class", "name": "类型", "value": genre_values})
                # 地区
                country_list = self.country_filters.get(tid, [])
                if country_list:
                    area_values = [{"n": "全部", "v": ""}]
                    for c in country_list:
                        area_values.append({"n": c, "v": c})
                    fl.append({"key": "area", "name": "地区", "value": area_values})
                # 年份
                year_list = self.year_filters.get(tid, [])
                if year_list:
                    year_values = [{"n": "全部", "v": ""}]
                    for y in year_list:
                        year_values.append({"n": y, "v": y})
                    fl.append({"key": "year", "name": "年份", "value": year_values})
                result["filters"][tid] = fl
            # 首页推荐
            html = self.fetch_html(f"{self.host}/cn/movie/----.html")
            if html:
                result["list"] = self.parse_list(html)[:24]
        except Exception as e:
            print(f'homeContent error: {e}')
        return result

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 24}
        try:
            # URL格式: /cn/{cat}/{genre}-{country}-{year}-{page0index}-{sort}.html
            # 页码0-indexed: 第1页=0, 第2页=1
            genre = ""
            country = ""
            year = ""
            if extend:
                genre = extend.get("class", "")
                country = extend.get("area", "")
                year = extend.get("year", "")

            page0 = str(int(pg) - 1) if int(pg) > 1 else ""
            # URL编码每个字段
            genre_enc = urllib.parse.quote(genre, safe='') if genre else ""
            country_enc = urllib.parse.quote(country, safe='') if country else ""
            year_enc = year if year else ""

            path = f"{genre_enc}-{country_enc}-{year_enc}-{page0}-"
            url = f"{self.host}/cn/{tid}/{path}.html"

            html = self.fetch_html(url)
            if html:
                result["list"] = self.parse_list(html)
                # 解析分页
                last_pages = re.findall(rf'href="/cn/{tid}/---(\d+)-\.html"', html)
                if last_pages:
                    max_page = max(int(p) for p in last_pages) + 1
                    result["pagecount"] = max_page
                elif result["list"]:
                    result["pagecount"] = int(pg) + 1
        except Exception as e:
            print(f'categoryContent error: {e}')
        return result

    def detailContent(self, ids):
        result = {"list": []}
        try:
            # vod_id格式: {cat}/{id}
            vod_id = ids[0]
            parts = vod_id.split("/")
            if len(parts) != 2:
                return result
            cat, vid = parts[0], parts[1]
            detail_html = self.fetch_html(f"{self.host}/cn/{cat}/{vid}.html")
            if not detail_html:
                return result

            vod_name = ""
            vod_pic = ""
            vod_content = ""
            vod_director = ""
            vod_actor = ""
            vod_year = ""
            vod_area = ""
            vod_remarks = ""
            infoid = ""
            m3u8_eps = []

            # 1. 提取JS变量: classid, infoid, m3u8
            infoid_m = re.search(r'infoid\s*=\s*(\d+)', detail_html)
            if infoid_m:
                infoid = infoid_m.group(1)
            m3u8_m = re.search(r"m3u8\s*=\s*(\[[^\]]+\])", detail_html)
            if m3u8_m:
                m3u8_eps = re.findall(r"""['"]([^'"]+)['"]""", m3u8_m.group(1))

            # 2. 标题和年份
            title_m = re.search(r'<h1 class="product-title">(.*?)</h1>', detail_html, re.S)
            if title_m:
                title_raw = title_m.group(1)
                name_m = re.match(r'\s*([^<\n]+?)\s*<span>\((\d{4})\)</span>', title_raw)
                if name_m:
                    vod_name = name_m.group(1).strip()
                    vod_year = name_m.group(2)
            if not vod_name:
                title_m2 = re.search(r'<h1 class="product-title">\s*([^<\n]+)', detail_html)
                if title_m2:
                    vod_name = title_m2.group(1).strip()

            # 3. 封面图
            pic_m = re.search(r'<img[^>]*class="thumb"[^>]*src="([^"]*)"', detail_html)
            if pic_m:
                vod_pic = pic_m.group(1)

            # 4. 评分（作为备注）
            rate_m = re.search(r'class="rate">([\d.]+)<', detail_html)
            if rate_m:
                vod_remarks = f"评分:{rate_m.group(1)}"

            # 5. 导演
            dir_m = re.search(r'(?:Directors|导演)[：:]\s*<span>(.*?)</span>', detail_html, re.S)
            if dir_m:
                dirs = re.findall(r'>([^<]+)</a>', dir_m.group(1))
                vod_director = ",".join(dirs) if dirs else re.sub(r'<[^>]+>', '', dir_m.group(1)).strip()

            # 6. 演员
            cast_m = re.search(r'(?:Casts|主演)[：:]\s*<span>(.*?)</span>', detail_html, re.S)
            if cast_m:
                casts = re.findall(r'>([^<]+)</a>', cast_m.group(1))
                vod_actor = ",".join(casts) if casts else re.sub(r'<[^>]+>', '', cast_m.group(1)).strip()

            # 7. 类型
            genre_m = re.search(r'(?:Genres|类型)[：:]\s*<span>(.*?)</span>', detail_html, re.S)
            if genre_m:
                genres = re.findall(r'>([^<]+)</a>', genre_m.group(1))
                if genres:
                    vod_remarks = "/".join(genres) + " " + vod_remarks

            # 8. 国家
            country_m = re.search(r'(?:Countries|国家)[：:]\s*<span>(.*?)</span>', detail_html, re.S)
            if country_m:
                countries = re.findall(r'>([^<]+)</a>', country_m.group(1))
                vod_area = ",".join(countries) if countries else re.sub(r'<[^>]+>', '', country_m.group(1)).strip()

            # 9. 简介
            summary_m = re.search(r'(?:Summary|简介)[：:]\s*<span>(.*?)</span>', detail_html, re.S)
            if summary_m:
                vod_content = re.sub(r'<[^>]+>', '', summary_m.group(1)).strip()

            # 10. 播放列表
            play_from = []
            play_url = []
            if infoid and m3u8_eps:
                urls = []
                for ep in m3u8_eps:
                    # 电影: ep=1080P(清晰度), 电视剧: ep=1,2,3...(集数)
                    if cat == "tv":
                        ep_name = f"第{ep}集"
                    else:
                        ep_name = ep
                    urls.append(f"{ep_name}${infoid}:{ep}")
                if urls:
                    play_from.append("PPnix")
                    play_url.append("#".join(urls))

            result["list"] = [{
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_director": vod_director,
                "vod_actor": vod_actor,
                "vod_year": vod_year,
                "vod_area": vod_area,
                "vod_content": vod_content,
                "vod_remarks": vod_remarks,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }]
        except Exception as e:
            print(f'detailContent error: {e}')
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            wd = urllib.parse.quote(key, safe='')
            # 搜索分页格式: /cn/search/{kw}--.html (第1页), /cn/search/{kw}-{N}-.html (第N+1页)
            page0 = str(int(pg) - 1) if int(pg) > 1 else ""
            url = f"{self.host}/cn/search/{wd}-{page0}-.html"
            html = self.fetch_html(url)
            if html:
                result["list"] = self.parse_list(html)
        except Exception as e:
            print(f'searchContent error: {e}')
        return result

    def playerContent(self, flag, pid, vipFlags):
        result = {}
        try:
            # pid格式: infoid:episode
            parts = pid.split(":")
            if len(parts) != 2:
                result["parse"] = 1
                result["url"] = self.host
                return result
            infoid, ep = parts[0], parts[1]

            # 通过localProxy返回修改后的m3u8（AES key以data URI嵌入）
            # FongMi TVBox proxy端点: /proxy (不是/local/proxy), do=py 路由到Python spider
            # URL末尾加 &.m3u8 让FongMi TVBox识别为HLS流
            proxy_url = f"http://127.0.0.1:9978/proxy?do=py&ppnix=1&infoid={infoid}&ep={urllib.parse.quote(ep, safe='')}&.m3u8"
            result["parse"] = 0
            result["url"] = proxy_url
            result["format"] = "application/x-mpegURL"
            result["header"] = {"User-Agent": self.ua, "Referer": self.host}
        except Exception as e:
            print(f'playerContent error: {e}')
            result["parse"] = 1
            result["url"] = self.host
            result["header"] = {"User-Agent": self.ua}
        return result

    def localProxy(self, params):
        try:
            # FongMi TVBox: do=py 路由到 pyLoader, pyLoader调用recent spider的localProxy
            # 业务标识通过 ppnix 参数区分
            if params.get('ppnix') == '1':
                infoid = params.get('infoid', '')
                ep = params.get('ep', '')
                if not infoid or not ep:
                    return [404, 'text/plain', b'Missing params']

                m3u8_url = f"{self.host}/info/m3u8/{infoid}/{ep}.m3u8"
                m3u8_content = self._proxy_fetch(m3u8_url)
                if not m3u8_content:
                    return [404, 'text/plain', b'M3U8 not found']

                # 将 #EXT-X-KEY 中的 URI 替换为 data URI (base64编码的16字节AES key)
                # 原因: key端点返回32字节ASCII文本, 但AES-128只需要前16字节
                # 直接返回原始key会被ExoPlayer误判为AES-256, 导致解密失败
                # data URI方式让ExoPlayer直接拿到正确的16字节raw key
                key_bytes = self._get_aes_key()
                if not key_bytes:
                    return [500, 'text/plain', b'Key fetch failed']

                key_b64 = base64.b64encode(key_bytes).decode('utf-8')
                data_uri = f"data:application/octet-stream;base64,{key_b64}"

                # 替换 URI="../key" 为 data URI
                m3u8_content = m3u8_content.replace('URI="../key"', f'URI="{data_uri}"')

                return [200, 'application/vnd.apple.mpegurl', m3u8_content.encode('utf-8')]

            return [404, 'text/plain', b'Unknown action']
        except Exception as e:
            print(f'localProxy error: {e}')
            return [500, 'text/plain', str(e).encode('utf-8')]

    # ==================== 工具方法 ====================

    def _proxy_fetch(self, url):
        """localProxy专用fetch，使用urllib直接请求(返回文本)"""
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers={
                "User-Agent": self.ua,
                "Referer": self.host,
            })
            with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            print(f'_proxy_fetch error: {e}')
            return ""

    def _get_aes_key(self):
        """获取并缓存AES key (前16个ASCII字符的UTF-8字节, 共16字节)"""
        if not hasattr(self, '_cached_aes_key') or not self._cached_aes_key:
            key_text = self._proxy_fetch(f"{self.host}/info/m3u8/key")
            if key_text:
                # key端点返回32字节ASCII文本(如"ba9bf05693b9fa202d922dd43a08f281")
                # AES-128需要16字节: 取前16个ASCII字符的UTF-8字节
                # 注意: 不是hex解码! 是直接取ASCII字符的字节值
                self._cached_aes_key = key_text.strip()[:16].encode('utf-8')
        return getattr(self, '_cached_aes_key', b'')

    def fetch_html(self, url):
        try:
            res = self.fetch(url, headers=self.headers, timeout=15)
            if res:
                if isinstance(res, str):
                    return res
                return res.text
        except Exception as e:
            print(f'fetch_html error: {e}')
        return ""

    def parse_list(self, html):
        """解析视频列表（li > a.thumbnail结构）"""
        items = []
        try:
            # 匹配列表项: 可选年份和评分
            blocks = re.findall(
                r'<li>\s*<a href="/cn/(movie|tv)/(\d+)\.html"\s+class="thumbnail"[^>]*>[\s\S]*?<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"[^>]*>[\s\S]*?</li>',
                html
            )
            seen = set()
            for cat, vid, pic, name in blocks:
                if vid in seen:
                    continue
                seen.add(vid)
                vod_id = f"{cat}/{vid}"
                # 尝试提取年份
                year_match = re.search(
                    rf'href="/cn/{cat}/{vid}\.html"[^>]*>[\s\S]*?<span class="orange">(\d{{4}})</span>',
                    html
                )
                year = year_match.group(1) if year_match else ""
                # 尝试提取评分
                rate_match = re.search(
                    rf'href="/cn/{cat}/{vid}\.html"[^>]*>[\s\S]*?class="rate">([\d.]+)</span>',
                    html
                )
                if year and rate_match:
                    vod_remarks = f"{year} 评分:{rate_match.group(1)}"
                elif year:
                    vod_remarks = year
                elif rate_match:
                    vod_remarks = f"评分:{rate_match.group(1)}"
                else:
                    vod_remarks = ""
                items.append({
                    "vod_id": vod_id,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": vod_remarks,
                })
        except Exception as e:
            print(f'parse_list error: {e}')
        return items