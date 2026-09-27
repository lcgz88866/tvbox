# -*- coding: utf-8 -*-
# 麦田影院 - www.mtyy1.cc
# 苹果CMS V10 + ds6模板，player_data直接返回m3u8
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
        return "麦田影院"

    def init(self, extend=""):
        self.host = "https://www.mtyy1.cc"
        self.ua = "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Referer": self.host,
        }
        self.cats = [
            {"type_name": "电影", "type_id": "1"},
            {"type_name": "电视剧", "type_id": "2"},
            {"type_name": "综艺", "type_id": "3"},
            {"type_name": "动漫", "type_id": "4"},
            {"type_name": "短剧", "type_id": "26"},
        ]
        # 各分类共用筛选
        self._type_opts = [
            {"n": "全部", "v": ""},
            {"n": "科幻", "v": "科幻"},
            {"n": "剧情", "v": "剧情"},
            {"n": "惊悚", "v": "惊悚"},
            {"n": "爱情", "v": "爱情"},
            {"n": "古装", "v": "古装"},
            {"n": "动作", "v": "动作"},
            {"n": "悬疑", "v": "悬疑"},
            {"n": "犯罪", "v": "犯罪"},
            {"n": "谍战", "v": "谍战"},
            {"n": "历史", "v": "历史"},
            {"n": "喜剧", "v": "喜剧"},
            {"n": "奇幻", "v": "奇幻"},
            {"n": "家庭", "v": "家庭"},
            {"n": "青春", "v": "青春"},
            {"n": "冒险", "v": "冒险"},
            {"n": "纪录", "v": "纪录"},
            {"n": "动画", "v": "动画"},
            {"n": "人物", "v": "人物"},
            {"n": "文化", "v": "文化"},
            {"n": "其他", "v": "其他"},
        ]
        self._area_opts = [
            {"n": "全部", "v": ""},
            {"n": "中国大陆", "v": "中国大陆"},
            {"n": "中国香港", "v": "中国香港"},
            {"n": "中国台湾", "v": "中国台湾"},
            {"n": "美国", "v": "美国"},
            {"n": "日本", "v": "日本"},
            {"n": "韩国", "v": "韩国"},
            {"n": "泰国", "v": "泰国"},
            {"n": "英国", "v": "英国"},
            {"n": "法国", "v": "法国"},
            {"n": "德国", "v": "德国"},
            {"n": "意大利", "v": "意大利"},
            {"n": "印度", "v": "印度"},
            {"n": "马来西亚", "v": "马来西亚"},
        ]
        self._year_opts = [
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
            {"n": "2014", "v": "2014"},
            {"n": "2013", "v": "2013"},
            {"n": "2012", "v": "2012"},
            {"n": "2011", "v": "2011"},
            {"n": "2010", "v": "2010"},
        ]

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

    def fetch_html(self, url):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            print(f'fetch_html error: {e}')
            return ""

    def fetch_json(self, url):
        try:
            html = self.fetch_html(url)
            if html:
                return json.loads(html)
        except Exception as e:
            print(f'fetch_json error: {e}')
        return None

    def _parse_vod_list(self, html):
        """解析分类页列表（vodtype/vodshow页面通用），自动去重"""
        items = []
        seen = set()
        # 匹配 public-list-exp 块，提取vod_id, vod_name, vod_pic, vod_remarks
        blocks = re.findall(
            r'<a[^>]*class="public-list-exp"[^>]*href="/voddetail/(\d+)\.html"[^>]*title="([^"]*)"[^>]*>'
            r'.*?data-src="([^"]*)"'
            r'.*?<span[^>]*class="[^"]*public-list-prb[^"]*"[^>]*>(.*?)</span>',
            html, re.S
        )
        for vod_id, vod_name, vod_pic, vod_remarks in blocks:
            if vod_id not in seen:
                seen.add(vod_id)
                items.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name.strip(),
                    "vod_pic": vod_pic,
                    "vod_remarks": re.sub(r'<[^>]+>', '', vod_remarks).strip(),
                })
        return items

    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        try:
            result["class"] = self.cats
            # 筛选器
            for cat in self.cats:
                tid = cat["type_id"]
                result["filters"][tid] = [
                    {"key": "class", "name": "类型", "value": self._type_opts},
                    {"key": "area", "name": "地区", "value": self._area_opts},
                    {"key": "year", "name": "年份", "value": self._year_opts},
                ]
            # 首页推荐：各分类vodtype第1页各取6条
            seen = set()
            for cat in self.cats:
                tid = cat["type_id"]
                html = self.fetch_html(f"{self.host}/vodtype/{tid}.html")
                if html:
                    for item in self._parse_vod_list(html)[:6]:
                        vid = item["vod_id"]
                        if vid not in seen:
                            seen.add(vid)
                            result["list"].append(item)
        except Exception as e:
            print(f'homeContent error: {e}')
        return result

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        result = {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
        try:
            # vodshow页面是JS动态渲染，改用vodtype页面获取数据
            html = self.fetch_html(f"{self.host}/vodtype/{tid}.html")
            if html:
                all_items = self._parse_vod_list(html)
                # 客户端筛选
                area = ""
                cls = ""
                year = ""
                if extend:
                    area = extend.get("area", "")
                    cls = extend.get("class", "")
                    year = extend.get("year", "")
                if area or cls or year:
                    # vodshow页面是JS渲染无法筛选，用AJAX API兜底
                    all_items = self._fetch_filtered(tid, page, area, cls, year)
                # 客户端分页
                per_page = 20
                total = len(all_items)
                start = (page - 1) * per_page
                end = start + per_page
                result["list"] = all_items[start:end]
                result["total"] = total
                result["pagecount"] = (total + per_page - 1) // per_page if total > 0 else 1
        except Exception as e:
            print(f'categoryContent error: {e}')
        return result

    def _fetch_filtered(self, tid, page, area, cls, year):
        """用AJAX API获取筛选后的列表（按type_id客户端过滤）"""
        items = []
        try:
            max_pages = 10  # 最多翻10页找匹配
            for p in range(1, max_pages + 1):
                url = f"{self.host}/index.php/ajax/data?mid=1&page={p}"
                data = self.fetch_json(url)
                if not data or data.get("code") != 1:
                    break
                for v in data.get("list", []):
                    if str(v.get("type_id", "")) != str(tid):
                        continue
                    if area and v.get("vod_area", "") != area:
                        continue
                    if cls and cls not in (v.get("vod_class", "") or ""):
                        continue
                    if year and str(v.get("vod_year", "")) != str(year):
                        continue
                    items.append({
                        "vod_id": str(v.get("vod_id", "")),
                        "vod_name": v.get("vod_name", ""),
                        "vod_pic": v.get("vod_pic", ""),
                        "vod_remarks": v.get("vod_remarks", ""),
                    })
                if len(items) >= 20:
                    break
        except Exception as e:
            print(f'_fetch_filtered error: {e}')
        return items

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            detail_html = self.fetch_html(f"{self.host}/voddetail/{vod_id}.html")
            if not detail_html:
                return result

            # 标题：从<title>中提取，格式 "影片名...-麦田影院"
            vod_name = ""
            title_m = re.search(r'<title>([^<]+)', detail_html)
            if title_m:
                title_raw = title_m.group(1).strip()
                name_part = title_raw.split('-')[0].strip()
                vod_name = re.sub(r'(电影|电视剧|综艺|动漫|短剧)?(免费观看|全集|完整版|在线观看|高清).*', '', name_part).strip()

            # 封面
            vod_pic = ""
            pic_m = re.search(r'data-src="([^"]+)"', detail_html)
            if pic_m:
                vod_pic = pic_m.group(1)
            else:
                pic_m2 = re.search(r'<meta property="og:image" content="([^"]+)"', detail_html)
                if pic_m2:
                    vod_pic = pic_m2.group(1)

            # 简介
            vod_content = ""
            content_m = re.search(r'<li[^>]*><em[^>]*>简介[：:]</em>(.*?)</li>', detail_html, re.S)
            if content_m:
                vod_content = re.sub(r'<[^>]+>', '', content_m.group(1)).strip()

            # 导演
            vod_director = ""
            director_m = re.search(r'<li[^>]*><em[^>]*>导演[：:]</em>(.*?)</li>', detail_html, re.S)
            if director_m:
                dirs = re.findall(r'>([^<]+)</a>', director_m.group(1))
                vod_director = ",".join(dirs) if dirs else re.sub(r'<[^>]+>', '', director_m.group(1)).strip()

            # 演员
            vod_actor = ""
            actor_m = re.search(r'<li[^>]*><em[^>]*>主演[：:]</em>(.*?)</li>', detail_html, re.S)
            if actor_m:
                acts = re.findall(r'>([^<]+)</a>', actor_m.group(1))
                vod_actor = ",".join(acts) if acts else re.sub(r'<[^>]+>', '', actor_m.group(1)).strip()

            # 年份
            vod_year = ""
            year_m = re.search(r'<li[^>]*><em[^>]*>年份[：:]</em>(\d{4})</li>', detail_html, re.S)
            if year_m:
                vod_year = year_m.group(1)

            # 地区
            vod_area = ""
            area_m = re.search(r'<li[^>]*><em[^>]*>地区[：:]</em>(.*?)</li>', detail_html, re.S)
            if area_m:
                vod_area = re.sub(r'<[^>]+>', '', area_m.group(1)).strip()

            # 备注（状态）
            vod_remarks = ""
            state_m = re.search(r'<li[^>]*><em[^>]*>状态[：:]</em>(.*?)</li>', detail_html, re.S)
            if state_m:
                vod_remarks = re.sub(r'<[^>]+>', '', state_m.group(1)).strip()

            # 播放列表
            play_from = []
            play_url = []

            # 提取线路名称（从 anthology-tab 中的 swiper-slide a 标签）
            line_names = []
            tab_blocks = re.findall(
                r'<div class="anthology-tab[^"]*">(.*?)</div>',
                detail_html, re.S
            )
            for tab_html in tab_blocks:
                names = re.findall(
                    r'<a[^>]*class="[^"]*swiper-slide[^"]*"[^>]*>(.*?)</a>',
                    tab_html, re.S
                )
                for name_raw in names:
                    name = re.sub(r'<[^>]+>', '', name_raw).strip()
                    name = name.replace('&nbsp;', ' ').strip()
                    if name:
                        line_names.append(name)

            # 提取各线路的集数（按 anthology-list-box 顺序对应）
            boxes = re.findall(
                r'<div class=["\']anthology-list-box[^"\']*["\']>(.*?)</div>\s*</div>',
                detail_html, re.S
            )

            # 线路优先级排序：BF/LZ/MD直接m3u8最稳定, NBY可解码, MT偶尔SSL失败
            priority = {"BF源": 1, "LZ源": 2, "MD源": 3, "NB源": 4, "MT源": 5}
            raw_lines = []
            for idx, line_name in enumerate(line_names):
                urls = []
                if idx < len(boxes):
                    eps = re.findall(
                        r'href="/vodplay/(\d+)-(\d+)-(\d+)\.html"[^>]*>(.*?)</a>',
                        boxes[idx]
                    )
                    for ep_id, ep_sid, ep_nid, ep_name_raw in eps:
                        ep_name = re.sub(r'<[^>]+>', '', ep_name_raw).strip()
                        if not ep_name:
                            ep_name = f"第{ep_nid}集"
                        urls.append(f"{ep_name}${ep_id}-{ep_sid}-{ep_nid}")
                if urls:
                    # 清理线路名（去掉尾部数字如"MT源33"->"MT源"）
                    clean_name = re.sub(r'\d+$', '', line_name).strip()
                    sort_key = priority.get(clean_name, 9)
                    raw_lines.append((sort_key, clean_name, urls))

            # 按优先级排序
            raw_lines.sort(key=lambda x: x[0])
            for _, name, urls in raw_lines:
                play_from.append(name)
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
            wd = urllib.parse.quote(key)
            url = f"{self.host}/index.php/ajax/data?mid=1&wd={wd}&page={pg}"
            data = self.fetch_json(url)
            if data and data.get("code") == 1:
                for v in data.get("list", []):
                    result["list"].append({
                        "vod_id": str(v.get("vod_id", "")),
                        "vod_name": v.get("vod_name", ""),
                        "vod_pic": v.get("vod_pic", ""),
                        "vod_remarks": v.get("vod_remarks", ""),
                    })
                result["pagecount"] = data.get("pagecount", 1)
                result["total"] = data.get("total", 0)
        except Exception as e:
            print(f'searchContent error: {e}')
        return result

    def _decode_nby_url(self, nby_url, referer):
        """通过art.php签名API解码NBY加密URL，返回真实m3u8地址"""
        try:
            encoded = urllib.parse.quote(nby_url)
            # Step 1: 获取签名URL
            step1 = f"{self.host}/static/player/art.php?get_signed_url=1&url={encoded}"
            resp1 = self.fetch_json(step1)
            if not resp1 or "signed_url" not in resp1:
                return ""
            signed_url = resp1["signed_url"]
            # Step 2: 用签名URL换取真实m3u8
            step2 = f"{self.host}/static/player/art.php{signed_url}"
            resp2 = self.fetch_json(step2)
            if resp2 and resp2.get("jmurl", "").startswith("http"):
                return resp2["jmurl"]
        except Exception as e:
            print(f'_decode_nby_url error: {e}')
        return ""

    def playerContent(self, flag, pid, vipFlags):
        result = {}
        try:
            parts = pid.split("-")
            if len(parts) != 3:
                result["parse"] = 1
                result["url"] = f"{self.host}/vodplay/{pid}.html"
                result["header"] = {"User-Agent": self.ua, "Referer": self.host}
                return result

            vid, sid, nid = parts
            play_url = f"{self.host}/vodplay/{vid}-{sid}-{nid}.html"
            html = self.fetch_html(play_url)
            if not html:
                result["parse"] = 1
                result["url"] = play_url
                result["header"] = {"User-Agent": self.ua, "Referer": self.host}
                return result

            m = re.search(r'var player_data=({.*?})\s*</script>', html, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                    url = data.get("url", "")
                    from_val = data.get("from", "")
                    encrypt = data.get("encrypt", 0)

                    # 处理加密URL (encrypt=1: URL编码, encrypt=2: base64+URL编码)
                    if encrypt == 1 and url:
                        url = urllib.parse.unquote(url)
                    elif encrypt == 2 and url:
                        url = urllib.parse.unquote(base64.b64decode(url).decode('utf-8', errors='ignore'))

                    # NBY加密URL: 通过签名API解码
                    if url and url.startswith("NBY-"):
                        decoded = self._decode_nby_url(url, play_url)
                        if decoded:
                            result["parse"] = 0
                            result["url"] = decoded
                            result["header"] = {"User-Agent": self.ua, "Referer": self.host}
                            return result
                        # 解码失败, 回退到播放页解析
                        result["parse"] = 1
                        result["url"] = play_url
                        result["header"] = {"User-Agent": self.ua, "Referer": self.host}
                        return result

                    # 直接m3u8/mp4 URL
                    if url and url.startswith("http"):
                        result["parse"] = 0
                        result["url"] = url
                        result["header"] = {"User-Agent": self.ua, "Referer": self.host}
                        return result
                except Exception as e:
                    print(f'player_data parse error: {e}')

            result["parse"] = 1
            result["url"] = play_url
            result["header"] = {"User-Agent": self.ua, "Referer": self.host}
        except Exception as e:
            print(f'playerContent error: {e}')
            result["parse"] = 1
            result["url"] = f"{self.host}/vodplay/{pid}.html"
            result["header"] = {"User-Agent": self.ua, "Referer": self.host}
        return result

    def localProxy(self, params):
        return [404, "text/plain", b"Not supported"]