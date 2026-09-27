# -*- coding: utf-8 -*-
# 千千影视 - www.qqys01.com
# by TRAE
# 飞飞CMS + MX主题
import re
import sys
import json
from urllib.parse import quote

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def getName(self):
        return "千千影视"

    def init(self, extend=""):
        self.host = "https://www.qqys01.com"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Referer": self.host,
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
            result["class"] = [
                {"type_name": "电影", "type_id": "1"},
                {"type_name": "连续剧", "type_id": "2"},
                {"type_name": "综艺", "type_id": "3"},
                {"type_name": "动漫", "type_id": "4"},
                {"type_name": "短剧", "type_id": "5"},
            ]
            if filter:
                result["filters"] = self._build_filters()
            html = self.fetch_html(self.host + "/")
            if html:
                result["list"] = self.parse_list(html)
        except Exception as e:
            print(f'homeContent error: {e}')
        return result

    def homeVideoContent(self):
        pass

    def _build_filters(self):
        """构建筛选器配置"""
        years = [{"n": "全部", "v": ""}]
        for y in range(2026, 2009, -1):
            years.append({"n": str(y), "v": str(y)})

        areas = [
            {"n": "全部", "v": ""},
            {"n": "大陆", "v": "大陆"}, {"n": "港台", "v": "港台"},
            {"n": "美国", "v": "美国"}, {"n": "法国", "v": "法国"},
            {"n": "英国", "v": "英国"}, {"n": "日本", "v": "日本"},
            {"n": "韩国", "v": "韩国"}, {"n": "泰国", "v": "泰国"},
            {"n": "印度", "v": "印度"}, {"n": "其他", "v": "其他"},
        ]

        sorts = [
            {"n": "时间", "v": "time"},
            {"n": "人气", "v": "hits"},
            {"n": "评分", "v": "score"},
        ]

        movie_class = [
            {"n": "全部", "v": ""},
            {"n": "动作", "v": "动作"}, {"n": "喜剧", "v": "喜剧"},
            {"n": "爱情", "v": "爱情"}, {"n": "科幻", "v": "科幻"},
            {"n": "恐怖", "v": "恐怖"}, {"n": "剧情", "v": "剧情"},
            {"n": "战争", "v": "战争"}, {"n": "冒险", "v": "冒险"},
            {"n": "奇幻", "v": "奇幻"}, {"n": "犯罪", "v": "犯罪"},
            {"n": "武侠", "v": "武侠"}, {"n": "警匪", "v": "警匪"},
            {"n": "动画", "v": "动画"},
        ]

        tv_class = [
            {"n": "全部", "v": ""},
            {"n": "剧情", "v": "剧情"}, {"n": "喜剧", "v": "喜剧"},
            {"n": "爱情", "v": "爱情"}, {"n": "科幻", "v": "科幻"},
            {"n": "恐怖", "v": "恐怖"}, {"n": "战争", "v": "战争"},
            {"n": "冒险", "v": "冒险"}, {"n": "奇幻", "v": "奇幻"},
            {"n": "犯罪", "v": "犯罪"}, {"n": "武侠", "v": "武侠"},
            {"n": "悬疑", "v": "悬疑"}, {"n": "惊悚", "v": "惊悚"},
            {"n": "古装", "v": "古装"}, {"n": "历史", "v": "历史"},
            {"n": "家庭", "v": "家庭"}, {"n": "都市", "v": "都市"},
            {"n": "运动", "v": "运动"}, {"n": "偶像", "v": "偶像"},
            {"n": "言情", "v": "言情"}, {"n": "灾难", "v": "灾难"},
            {"n": "纪录片", "v": "纪录片"},
        ]

        return {
            "1": [
                {"key": "class", "name": "类型", "value": movie_class},
                {"key": "area", "name": "地区", "value": areas},
                {"key": "sort", "name": "排序", "value": sorts},
                {"key": "year", "name": "年份", "value": years},
            ],
            "2": [
                {"key": "class", "name": "类型", "value": tv_class},
                {"key": "area", "name": "地区", "value": areas},
                {"key": "sort", "name": "排序", "value": sorts},
                {"key": "year", "name": "年份", "value": years},
            ],
            "3": [
                {"key": "area", "name": "地区", "value": areas},
                {"key": "sort", "name": "排序", "value": sorts},
                {"key": "year", "name": "年份", "value": years},
            ],
            "4": [
                {"key": "area", "name": "地区", "value": areas},
                {"key": "sort", "name": "排序", "value": sorts},
                {"key": "year", "name": "年份", "value": years},
            ],
            "5": [
                {"key": "area", "name": "地区", "value": areas},
                {"key": "sort", "name": "排序", "value": sorts},
                {"key": "year", "name": "年份", "value": years},
            ],
        }

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": pg, "pagecount": 999, "limit": 72, "total": 999999}
        try:
            # URL格式: /vodshow/{tid}-{area}-{sort}-{class}-{lang}-{letter}---{page}---{year}.html
            area = ""
            sort = ""
            cls = ""
            lang = ""
            letter = ""
            year = ""

            if extend:
                a = extend.get("area", "")
                if a and a != "全部":
                    area = quote(a)
                s = extend.get("sort", "")
                if s:
                    sort = s
                c = extend.get("class", "")
                if c and c != "全部":
                    cls = quote(c)
                y = extend.get("year", "")
                if y and y != "全部":
                    year = y

            # 拼接: tid-area-sort-class-lang-letter---page---year.html
            segments = [tid, area, sort, cls, lang, letter]
            url = f"{self.host}/vodshow/{'-'.join(segments)}---{pg}---{year}.html"
            print(f'qqys01 category url: {url}')
            html = self.fetch_html(url)
            if html:
                result["list"] = self.parse_list(html)
        except Exception as e:
            print(f'categoryContent error: {e}')
        return result

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            data = self.parse_detail(vod_id)
            if data:
                result["list"] = [data]
        except Exception as e:
            print(f'detailContent error: {e}')
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            wd = quote(key)
            url = f"{self.host}/vodsearch/{wd}-------------.html"
            html = self.fetch_html(url)
            if html:
                result["list"] = self.parse_search_list(html)
        except Exception as e:
            print(f'searchContent error: {e}')
        return result

    def playerContent(self, flag, pid, vipFlags):
        result = {}
        try:
            # pid格式: {id}-{sid}-{nid}
            parts = pid.split("-")
            play_url = f"{self.host}/vodplay/{parts[0]}-{parts[1]}-{parts[2]}.html"
            # 飞飞CMS播放器通过iframe加载，parse=""空解析=直接播放
            # 必须用WebView加载播放页
            result["parse"] = 1
            result["url"] = play_url
            result["header"] = {"User-Agent": self.ua, "Referer": self.host + "/"}
        except Exception as e:
            print(f'playerContent error: {e}')
            result["parse"] = 0
            result["url"] = ""
        return result

    def localProxy(self, params):
        return self.Mlocal(params)

    # ==================== 工具方法 ====================

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
        """解析视频列表"""
        items = []
        try:
            # MX主题: <a href="/voddetail{id}.html" title="名称" class="module-poster-item...">
            # href和title之间可能有换行和class属性
            blocks = re.findall(
                r'<a\s+href="/voddetail(\d+)\.html"[^>]*?title="([^"]+)"[^>]*>(.*?)</a>',
                html, re.S
            )
            seen = set()
            for vod_id, vod_name, block in blocks:
                if vod_id in seen:
                    continue
                seen.add(vod_id)
                pic_match = re.search(r'data-original="([^"]+)"', block)
                vod_pic = pic_match.group(1) if pic_match else ""
                remarks_match = re.search(r'<div class="module-item-note">([^<]*)</div>', block)
                vod_remarks = remarks_match.group(1) if remarks_match else ""
                items.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": vod_remarks,
                })
        except Exception as e:
            print(f'parse_list error: {e}')
        return items

    def parse_search_list(self, html):
        """解析搜索结果列表（卡片式布局）"""
        items = []
        try:
            # 搜索页: module-card-item, 标题在<strong>中, 封面在data-original, 备注在module-item-note
            blocks = re.findall(
                r'<div class="module-card-item[^"]*">(.*?)</div>\s*</div>\s*</div>',
                html, re.S
            )
            for block in blocks:
                # ID和链接
                id_match = re.search(r'href="/voddetail(\d+)\.html"', block)
                if not id_match:
                    continue
                vod_id = id_match.group(1)
                # 标题
                name_match = re.search(r'<strong>([^<]+)</strong>', block)
                vod_name = name_match.group(1).strip() if name_match else ""
                # 封面
                pic_match = re.search(r'data-original="([^"]+)"', block)
                vod_pic = pic_match.group(1) if pic_match else ""
                # 备注
                rem_match = re.search(r'<div class="module-item-note">([^<]*)</div>', block)
                vod_remarks = rem_match.group(1) if rem_match else ""
                items.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": vod_remarks,
                })
        except Exception as e:
            print(f'parse_search_list error: {e}')
        return items

    def parse_detail(self, vod_id):
        """解析详情页"""
        try:
            detail_html = self.fetch_html(f"{self.host}/voddetail{vod_id}.html")
            if not detail_html:
                return None

            # 标题
            h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', detail_html, re.S)
            vod_name = h1_match.group(1).strip() if h1_match else ""

            # 封面
            pic_match = re.search(r'data-original="([^"]+)"', detail_html)
            vod_pic = pic_match.group(1) if pic_match else ""

            # 简介
            vod_content = ""
            content_match = re.search(r'class="module-info-introduction-content[^"]*"[^>]*>(.*?)</div>', detail_html, re.S)
            if content_match:
                vod_content = re.sub(r'<[^>]+>', '', content_match.group(1)).strip()
            if not vod_content:
                meta_match = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]+)"', detail_html)
                if meta_match:
                    vod_content = meta_match.group(1).strip()

            # 导演
            vod_director = ""
            director_match = re.search(r'导演[：:]</span>.*?<div[^>]*class="[^"]*module-info-item-content[^"]*"[^>]*>(.*?)</div>', detail_html, re.S)
            if director_match:
                directors = re.findall(r'>([^<]+)<', director_match.group(1))
                vod_director = ",".join([d.strip() for d in directors if d.strip() and d.strip() != "/"])

            # 主演
            vod_actor = ""
            actor_match = re.search(r'主演[：:]</span>.*?<div[^>]*class="[^"]*module-info-item-content[^"]*"[^>]*>(.*?)</div>', detail_html, re.S)
            if actor_match:
                actors = re.findall(r'>([^<]+)<', actor_match.group(1))
                vod_actor = ",".join([a.strip() for a in actors if a.strip() and a.strip() != "/"])

            # 年份
            vod_year = ""
            year_match = re.search(r'年份[：:]</span>.*?<div[^>]*class="[^"]*module-info-item-content[^"]*"[^>]*>(.*?)</div>', detail_html, re.S)
            if year_match:
                y = re.search(r'(\d{4})', year_match.group(1))
                if y:
                    vod_year = y.group(1)

            # 地区
            vod_area = ""
            area_match = re.search(r'地区[：:]</span>.*?<div[^>]*class="[^"]*module-info-item-content[^"]*"[^>]*>(.*?)</div>', detail_html, re.S)
            if area_match:
                areas = re.findall(r'>([^<]+)<', area_match.group(1))
                vod_area = ",".join([a.strip() for a in areas if a.strip() and a.strip() != "/"])

            # 备注
            vod_remarks = ""
            remarks_match = re.search(r'class="pic-text[^"]*"[^>]*>([^<]*)</span>', detail_html)
            if remarks_match:
                vod_remarks = remarks_match.group(1).strip()

            # 播放列表
            play_from = []
            play_url = []

            # 线路名称 - 按顺序
            line_names = re.findall(r'data-dropdown-value="([^"]+)"', detail_html)

            # 选集 - 按module-play-list-content块分割，每个块对应一条线路
            sections = re.findall(
                r'class="module-play-list-content[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
                detail_html, re.S
            )
            for i, sec in enumerate(sections):
                eps = re.findall(
                    r'href="/vodplay/(\d+)-(\d+)-(\d+)\.html"[^>]*><span>([^<]*)</span>',
                    sec
                )
                if eps:
                    line_name = line_names[i].strip() if i < len(line_names) else f"线路{i+1}"
                    urls = [f"{n}${eid}-{sid}-{nid}" for eid, sid, nid, n in eps]
                    play_from.append(line_name)
                    play_url.append("#".join(urls))

            return {
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
            }
        except Exception as e:
            print(f'parse_detail error: {e}')
        return None