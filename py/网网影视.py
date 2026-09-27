# -*- coding: utf-8 -*-
# 网网影视 - vip.wwgz.cn:5200
# by TRAE
# 注意: 必须使用手机UA访问，网站检测桌面UA会跳转404
# 搜索功能: 网站服务器端缺少搜索模板文件，搜索暂不可用
import re
import sys
from urllib.parse import quote

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def getName(self):
        return "网网影视"

    def init(self, extend=""):
        self.host = "https://vip.wwgz.cn:5200"
        self.ua = "Mozilla/5.0 (Linux; Android 10; Pixel 3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"
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
                {"type_name": "电视剧", "type_id": "12"},
                {"type_name": "综艺", "type_id": "3"},
                {"type_name": "动漫", "type_id": "4"},
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
        """构建筛选器配置，key 使用 type_id"""
        years = [{"n": "全部", "v": "0"}]
        for y in range(2026, 2010, -1):
            years.append({"n": str(y), "v": str(y)})

        areas = [
            {"n": "全部", "v": "--"},
            {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"},
            {"n": "韩国", "v": "韩国"}, {"n": "日本", "v": "日本"}, {"n": "美国", "v": "美国"},
            {"n": "英国", "v": "英国"}, {"n": "法国", "v": "法国"}, {"n": "泰国", "v": "泰国"},
            {"n": "印度", "v": "印度"}, {"n": "德国", "v": "德国"}, {"n": "其他", "v": "其他"},
        ]

        return {
            "1": [
                {"key": "class", "name": "类型", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "动作片", "v": "动作片"}, {"n": "喜剧片", "v": "喜剧片"},
                    {"n": "爱情片", "v": "爱情片"}, {"n": "科幻片", "v": "科幻片"},
                    {"n": "恐怖片", "v": "恐怖片"}, {"n": "剧情片", "v": "剧情片"},
                    {"n": "战争片", "v": "战争片"}, {"n": "惊悚片", "v": "惊悚片"},
                    {"n": "奇幻片", "v": "奇幻片"},
                ]},
                {"key": "year", "name": "年份", "value": years},
                {"key": "area", "name": "地区", "value": areas},
            ],
            "12": [
                {"key": "class", "name": "类型", "value": [
                    {"n": "全部", "v": ""},
                    {"n": "国产剧", "v": "国产剧"}, {"n": "港台泰", "v": "港台泰"},
                    {"n": "日韩剧", "v": "日韩剧"}, {"n": "欧美剧", "v": "欧美剧"},
                ]},
                {"key": "year", "name": "年份", "value": years},
                {"key": "area", "name": "地区", "value": areas},
            ],
            "3": [
                {"key": "year", "name": "年份", "value": years},
                {"key": "area", "name": "地区", "value": areas},
            ],
            "4": [
                {"key": "year", "name": "年份", "value": years},
                {"key": "area", "name": "地区", "value": [
                    {"n": "全部", "v": "--"},
                    {"n": "国产", "v": "国产"}, {"n": "日本", "v": "日本"},
                    {"n": "欧美", "v": "欧美"}, {"n": "其他", "v": "其他"},
                ]},
            ],
        }

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": pg, "pagecount": 999, "limit": 90, "total": 999999}
        try:
            # 构建筛选URL
            list_id = tid      # 主分类ID
            year = "0"         # 年份，0=全部
            area = "--"        # 地区，--=全部
            sort = "time"      # 排序

            if extend:
                # 类型筛选：使用子类型ID替换主分类ID
                cls = extend.get("class", "")
                if cls:
                    type_map = {
                        # 电影子类型
                        "动作片": "5", "喜剧片": "6", "爱情片": "7", "科幻片": "8",
                        "恐怖片": "9", "剧情片": "10", "战争片": "11", "惊悚片": "16", "奇幻片": "17",
                        # 电视剧子类型
                        "国产剧": "12", "港台泰": "13", "日韩剧": "14", "欧美剧": "15",
                    }
                    if cls in type_map:
                        list_id = type_map[cls]

                # 年份筛选
                y = extend.get("year", "")
                if y and y not in ["", "0", "全部"]:
                    year = y

                # 地区筛选
                a = extend.get("area", "")
                if a and a not in ["", "--", "全部"]:
                    area = quote(a)

            url = f"{self.host}/index.php?m=vod-list-id-{list_id}-pg-{pg}-order--by-{sort}-class-0-year-{year}-letter--area-{area}-lang-.html"
            print(f'wwgz category url: {url}')
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
            # 网站搜索模板缺失，尝试用关键词搜索
            url = f"{self.host}/index.php?m=vod-search-wd-{quote(key)}.html"
            html = self.fetch_html(url)
            if html and '缺少文件' not in html:
                result["list"] = self.parse_list(html)
        except Exception as e:
            print(f'searchContent error: {e}')
        return result

    def playerContent(self, flag, pid, vipFlags):
        result = {}
        try:
            # pid格式: 加密URL
            real_url = self._decrypt_play_url(pid)
            result["parse"] = 0
            result["url"] = real_url
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

    def _decrypt_play_url(self, enc_url):
        """通过播放器API解密加密URL，获取真实m3u8地址"""
        try:
            apis = [
                "https://api.wwgz.cn:520",
                "https://api.nmvod.me:520",
            ]
            for api in apis:
                url = f"{api}/player/?url={enc_url}"
                html = self.fetch_html(url)
                if html:
                    match = re.search(r'"url":\s*"([^"]+)"', html)
                    if match:
                        play_url = match.group(1)
                        if play_url.startswith("http"):
                            return play_url
        except Exception as e:
            print(f'_decrypt_play_url error: {e}')
        return ""

    def parse_list(self, html):
        """解析视频列表"""
        items = []
        try:
            blocks = re.findall(
                r'<a\s+href="/vod-detail-id-(\d+)\.html"\s+title="([^"]+)"[^>]*>(.*?)</a>',
                html, re.S
            )
            seen = set()
            for vod_id, vod_name, block in blocks:
                if vod_id in seen:
                    continue
                seen.add(vod_id)
                pic_match = re.search(r'data-echo="([^"]+)"', block)
                vod_pic = pic_match.group(1) if pic_match else ""
                remarks_match = re.search(r'<em>([^<]*)</em>', block)
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

    def parse_detail(self, vod_id):
        """解析详情页"""
        try:
            detail_html = self.fetch_html(f"{self.host}/vod-detail-id-{vod_id}.html")
            if not detail_html:
                return None

            # 视频名称 - 从 h1 标签提取
            h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', detail_html)
            vod_name = ""
            if h1_match:
                vod_name = h1_match.group(1).strip()

            # 封面
            pic_match = re.search(r'data-echo="([^"]+)"', detail_html)
            vod_pic = pic_match.group(1) if pic_match else ""

            # 简介 - 从详情页提取
            vod_content = ""
            intro_match = re.search(r'简\s*介[：:]\s*(.*?)(?:</p>|</div>)', detail_html, re.S)
            if intro_match:
                vod_content = re.sub(r'<[^>]+>', '', intro_match.group(1)).strip()
                vod_content = re.sub(r'&nbsp;', '', vod_content).strip()
            # 备选：从meta description提取
            if not vod_content:
                meta_match = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]+)"', detail_html)
                if meta_match:
                    desc = meta_match.group(1)
                    vod_content = desc[:500] if len(desc) > 500 else desc

            # 主演 - 格式: 主演:&nbsp;</span><a>演员1</a>&nbsp;<a>演员2</a>
            vod_actor = ""
            actor_match = re.search(r'主演:&nbsp;</span>(.*?)(?:</div>|导演)', detail_html, re.S)
            if actor_match:
                actors = re.findall(r'>([^<]+)</a>', actor_match.group(1))
                vod_actor = ",".join(actors)

            # 导演
            vod_director = ""
            director_match = re.search(r'导演:&nbsp;</span>(.*?)(?:</div>|更新日期)', detail_html, re.S)
            if director_match:
                directors = re.findall(r'>([^<]+)</a>', director_match.group(1))
                vod_director = ",".join(directors)

            # 年份
            vod_year = ""
            year_match = re.search(r'年代:&nbsp;</span>(.*?)(?:</div>|立即播放)', detail_html, re.S)
            if year_match:
                year_val = re.search(r'>(\d{4})<', year_match.group(1))
                if year_val:
                    vod_year = year_val.group(1)

            # 地区 - 从meta或分类标签提取
            vod_area = ""
            area_match = re.search(r'<a[^>]*href="[^"]*vod-list[^"]*"[^>]*>([^<]+)</a>', detail_html)
            if area_match:
                area_text = area_match.group(1)
                if area_text not in ['电影', '电视剧', '综艺', '动漫', '首页']:
                    vod_area = area_text

            # 状态/更新
            vod_remarks = ""
            status_match = re.search(r'状态:&nbsp;</span>(.*?)(?:</div>|主演)', detail_html, re.S)
            if status_match:
                vod_remarks = re.sub(r'<[^>]+>', '', status_match.group(1)).strip()

            # 从播放页获取线路和选集
            play_html = self.fetch_html(f"{self.host}/vod-play-id-{vod_id}-src-1-num-1.html")
            if not play_html:
                play_html = self.fetch_html(f"{self.host}/vod-play-id-{vod_id}-src-2-num-1.html")

            play_from = []
            play_url = []

            if play_html:
                from_match = re.search(r"mac_from='([^']*)'", play_html)
                url_match = re.search(r"mac_url='([^']*)'", play_html)

                if from_match and url_match:
                    from_str = from_match.group(1)
                    url_str = url_match.group(1)
                    line_names = from_str.split('$$$')
                    line_urls = url_str.split('$$$')

                    for i, line_url in enumerate(line_urls):
                        line_name = line_names[i] if i < len(line_names) else f"线路{i+1}"

                        eps = line_url.split('#')
                        urls = []
                        for ep_idx, ep in enumerate(eps, 1):
                            if '$' in ep:
                                parts = ep.split('$', 1)
                                ep_name = parts[0]
                                enc_url = parts[1] if len(parts) > 1 else ""
                                if enc_url:
                                    urls.append(f"{ep_name}${enc_url}")
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
                "vod_content": vod_content,
                "vod_remarks": vod_remarks,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }
        except Exception as e:
            print(f'parse_detail error: {e}')
        return None