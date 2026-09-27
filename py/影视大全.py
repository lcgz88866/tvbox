# -*- coding: utf-8 -*-
# 影视大全 - www.iysdq.tv
# by TRAE (修复版)
import re
import sys
import json
from urllib.parse import quote

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def getName(self):
        return "影视大全"

    def init(self, extend=""):
        self.host = "https://www.iysdq.tv"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        self.headers = {"User-Agent": self.ua}

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
                {"type_name": "电视剧", "type_id": "2"},
                {"type_name": "综艺", "type_id": "3"},
                {"type_name": "动漫", "type_id": "4"},
                {"type_name": "短剧", "type_id": "5"},
            ]
            
            # ========== 添加筛选条件 ==========
            # 地区筛选
            area_filter = {
                "key": "area",
                "name": "地区",
                "value": [
                    {"n": "全部", "v": ""},
                    {"n": "大陆", "v": "大陆"},
                    {"n": "香港", "v": "香港"},
                    {"n": "台湾", "v": "台湾"},
                    {"n": "美国", "v": "美国"},
                    {"n": "韩国", "v": "韩国"},
                    {"n": "日本", "v": "日本"},
                    {"n": "泰国", "v": "泰国"},
                    {"n": "印度", "v": "印度"},
                    {"n": "英国", "v": "英国"},
                    {"n": "法国", "v": "法国"},
                    {"n": "德国", "v": "德国"},
                    {"n": "俄罗斯", "v": "俄罗斯"},
                    {"n": "意大利", "v": "意大利"},
                    {"n": "西班牙", "v": "西班牙"},
                    {"n": "加拿大", "v": "加拿大"},
                    {"n": "其他", "v": "其他"},
                ]
            }
            
            # 年份筛选
            year_filter = {
                "key": "year",
                "name": "年份",
                "value": [
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
                    {"n": "2010-2014", "v": "2010-2014"},
                    {"n": "2000-2009", "v": "2000-2009"},
                    {"n": "更早", "v": "更早"},
                ]
            }
            
            # 语言筛选
            lang_filter = {
                "key": "lang",
                "name": "语言",
                "value": [
                    {"n": "全部", "v": ""},
                    {"n": "国语", "v": "国语"},
                    {"n": "粤语", "v": "粤语"},
                    {"n": "英语", "v": "英语"},
                    {"n": "韩语", "v": "韩语"},
                    {"n": "日语", "v": "日语"},
                    {"n": "法语", "v": "法语"},
                    {"n": "德语", "v": "德语"},
                    {"n": "泰语", "v": "泰语"},
                    {"n": "其他", "v": "其他"},
                ]
            }
            
            # 排序筛选
            by_filter = {
                "key": "by",
                "name": "排序",
                "value": [
                    {"n": "最新", "v": "time"},
                    {"n": "最热", "v": "hits"},
                    {"n": "评分", "v": "score"},
                ]
            }
            
            # 为每个分类添加筛选
            for c in result["class"]:
                tid = c["type_id"]
                result["filters"][tid] = [area_filter, year_filter, lang_filter, by_filter]
            
            # 获取首页内容
            html = self.fetch_html(self.host + "/")
            if html:
                result["list"] = self.parse_list(html)
        except Exception as e:
            print(f'homeContent error: {e}')
        return result

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": pg, "pagecount": 999, "limit": 90, "total": 999999}
        try:
            # 构建筛选URL
            # URL格式: /vodtype/{tid}-{pg}.html?area=xxx&year=xxx&lang=xxx&by=xxx
            url = f"{self.host}/vodtype/{tid}-{pg}.html"
            params = {}
            if extend:
                if "area" in extend and extend["area"]:
                    params["area"] = extend["area"]
                if "year" in extend and extend["year"]:
                    params["year"] = extend["year"]
                if "lang" in extend and extend["lang"]:
                    params["lang"] = extend["lang"]
                if "by" in extend and extend["by"]:
                    params["by"] = extend["by"]
            
            if params:
                query = "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
                url += "?" + query
            
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
            html = self.fetch_html(f"{self.host}/voddetail/{vod_id}.html")
            if html:
                data = self.parse_detail(html, vod_id)
                if data:
                    result["list"] = [data]
        except Exception as e:
            print(f'detailContent error: {e}')
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            url = f"{self.host}/vodsearch/-------------.html?wd={quote(key)}"
            html = self.fetch_html(url)
            if html:
                result["list"] = self.parse_list(html)
        except Exception as e:
            print(f'searchContent error: {e}')
        return result

    def playerContent(self, flag, pid, vipFlags):
        result = {}
        try:
            url = self.parse_play(pid)
            result["parse"] = 0
            result["url"] = url
            result["header"] = {"User-Agent": self.ua}
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
            # 先尝试首页结构（public-list-exp）
            blocks = re.findall(
                r'<a class="public-list-exp" href="/voddetail/(\d+)\.html"[^>]*>(.*?)</a>',
                html, re.S
            )
            if blocks:
                for vod_id, block in blocks:
                    name_match = re.search(r'title="([^"]*)"', block)
                    vod_name = name_match.group(1) if name_match else ""
                    pic_match = re.search(r'data-src="([^"]*)"', block)
                    vod_pic = pic_match.group(1) if pic_match else ""
                    remarks_match = re.search(r'public-list-prb[^>]*>([^<]*)</span>', block)
                    vod_remarks = remarks_match.group(1) if remarks_match else ""
                    items.append({
                        "vod_id": vod_id,
                        "vod_name": vod_name,
                        "vod_pic": vod_pic,
                        "vod_remarks": vod_remarks,
                    })
            else:
                # 分类页结构：通过href+title提取，然后去重
                seen = set()
                blocks = re.findall(
                    r'href="/voddetail/(\d+)\.html"[^>]*title="([^"]*)"',
                    html
                )
                for vod_id, vod_name in blocks:
                    if vod_id in seen:
                        continue
                    seen.add(vod_id)
                    # 查找对应的封面和备注
                    block_match = re.search(
                        r'href="/voddetail/' + vod_id + r'\.html"[^>]*title="' + re.escape(vod_name) + r'".*?(?=<a |</div>\s*<div|</a>\s*<a)',
                        html, re.S
                    )
                    block = block_match.group(0) if block_match else ""
                    pic_match = re.search(r'data-src="([^"]*)"', block)
                    vod_pic = pic_match.group(1) if pic_match else ""
                    remarks_match = re.search(r'public-list-prb[^>]*>([^<]*)</span>', block)
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

    def parse_detail(self, html, vod_id):
        """解析详情页"""
        try:
            # 影片名称
            name_match = re.search(r'<h1[^>]*>(.*?)</h1>', html)
            if not name_match:
                name_match = re.search(r'<h3[^>]*class="[^"]*this-title[^"]*"[^>]*>(.*?)</h3>', html)
            vod_name = name_match.group(1).strip() if name_match else ""
            vod_name = re.sub(r'<[^>]+>', '', vod_name)

            # 影片封面
            pic_match = re.search(r'<img[^>]*class="[^"]*lazy[^"]*"[^>]*data-src="([^"]*)"', html)
            if not pic_match:
                pic_match = re.search(r'<img[^>]*data-src="([^"]*)"', html)
            vod_pic = pic_match.group(1) if pic_match else ""

            # 导演
            director_match = re.search(r'导演[：:]\s*<a[^>]*>([^<]*)</a>', html)
            vod_director = director_match.group(1) if director_match else ""

            # 主演
            actor_match = re.search(r'主演[：:]\s*(.*?)</div>', html, re.S)
            vod_actor = ""
            if actor_match:
                actors = re.findall(r'<a[^>]*>([^<]*)</a>', actor_match.group(1))
                vod_actor = ",".join(actors)

            # 年份
            year_match = re.search(r'年份[：:]\s*<a[^>]*>([^<]*)</a>', html)
            vod_year = year_match.group(1) if year_match else ""

            # 地区
            area_match = re.search(r'地区[：:]\s*<a[^>]*>([^<]*)</a>', html)
            vod_area = area_match.group(1) if area_match else ""

            # 语言
            lang_match = re.search(r'语言[：:]\s*<a[^>]*>([^<]*)</a>', html)
            vod_lang = lang_match.group(1) if lang_match else ""

            # 类型/分类
            type_match = re.search(r'类型[：:]\s*(.*?)</div>', html, re.S)
            vod_type = ""
            if type_match:
                types = re.findall(r'<a[^>]*>([^<]*)</a>', type_match.group(1))
                vod_type = ",".join(types)

            # ========== 修复剧情描述提取 ==========
            vod_content = ""
            
            # 尝试多种方式提取简介
            # 方式1: class包含cor3的div
            content_match = re.search(r'<div[^>]*class="[^"]*cor3[^"]*"[^>]*>(.*?)</div>', html, re.S)
            if content_match:
                vod_content = re.sub(r'<[^>]+>', '', content_match.group(1)).strip()
            
            # 方式2: 剧情简介标签
            if not vod_content:
                content_match = re.search(r'剧情简介[：:]</[^>]*>(.*?)</div>', html, re.S)
                if content_match:
                    vod_content = re.sub(r'<[^>]+>', '', content_match.group(1)).strip()
            
            # 方式3: 包含"简介"文本的div
            if not vod_content:
                content_match = re.search(r'简介[：:]</[^>]*>(.*?)</div>', html, re.S)
                if content_match:
                    vod_content = re.sub(r'<[^>]+>', '', content_match.group(1)).strip()
            
            # 方式4: 通用剧情文本匹配
            if not vod_content:
                content_match = re.search(r'剧情介绍[：:]</[^>]*>(.*?)</div>', html, re.S)
                if content_match:
                    vod_content = re.sub(r'<[^>]+>', '', content_match.group(1)).strip()
            
            # 方式5: 备用 - 查找包含较长文本的特定div
            if not vod_content:
                # 查找class为detail-content或类似的长文本区域
                content_match = re.search(r'<div[^>]*class="[^"]*detail[^"]*content[^"]*"[^>]*>(.*?)</div>', html, re.S)
                if content_match:
                    vod_content = re.sub(r'<[^>]+>', '', content_match.group(1)).strip()
            
            # 清理简介中的多余空白
            vod_content = re.sub(r'\s+', ' ', vod_content).strip()

            # 线路名
            line_map = {}
            line_matches = re.findall(
                r'<a[^>]*class="[^"]*swiper-slide[^"]*"[^>]*>(.*?)</a>',
                html
            )
            for i, line_html in enumerate(line_matches):
                line_name = re.sub(r'<[^>]+>', '', line_html).strip()
                # 去掉末尾的数字
                line_name = re.sub(r'\d+$', '', line_name).strip()
                line_map[i] = line_name

            # 各线路选集
            play_from = []
            play_url = []
            playlist_boxes = re.findall(
                r'<div class="anthology-list-box[^"]*">(.*?)</div>\s*(?=<div class="anthology-list-box|<div class="anthology-list-dow|</div>)',
                html, re.S
            )
            for i, box in enumerate(playlist_boxes):
                line_name = line_map.get(i, f"线路{i+1}")
                eps = re.findall(
                    r'href="/vodplay/(\d+)-(\d+)-(\d+)\.html">([^<]*)</a>',
                    box
                )
                urls = []
                for ep_vid, ep_line, ep_num, ep_name in eps:
                    urls.append(f"{ep_name}${ep_vid}-{ep_line}-{ep_num}")
                if urls:
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
                "vod_lang": vod_lang,
                "vod_type": vod_type,
                "vod_content": vod_content,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }
        except Exception as e:
            print(f'parse_detail error: {e}')
        return None

    def parse_play(self, pid):
        """解析播放页获取真实播放地址"""
        try:
            info = pid.split("-")
            if len(info) < 3:
                return ""
            vod_id, line_id, ep_num = info[0], info[1], info[2]
            url = f"{self.host}/vodplay/{vod_id}-{line_id}-{ep_num}.html"
            html = self.fetch_html(url)
            if not html:
                return ""
            # 从 player_aaaa 变量中提取 url
            match = re.search(r'var player_aaaa=(\{.*\})</script>', html, re.S)
            if match:
                data = json.loads(match.group(1))
                return data.get("url", "")
            # 备选：直接搜索 m3u8/mp4 链接
            match2 = re.search(r'(https?://[^"\'\s]+\.(?:m3u8|mp4)[^"\'\s]*)', html)
            if match2:
                return match2.group(1)
        except Exception as e:
            print(f'parse_play error: {e}')
        return ""
