#coding=utf-8
#!/usr/bin/python
# 泥视频 (www.nivod.vip) - 苹果CMS V10 (Maccms)
# 模板: mxpro
# URL规则:
#   分类页: /t/{tid}/
#   筛选页: /k/{tid}-{area}-{by}-{class}-{lang}-{letter}-{}-{}-{page}-{}-{}-{year}/
#   详情页: /nivod/{id}/
#   播放页: /niplay/{id}-{sid}-{nid}/
#   搜索: /s/{keyword}----------{page}---/
# 播放: player_aaaa变量中含直链m3u8 (encrypt:0)

import sys
sys.path.append('..')
from base.spider import Spider
import re
import json
from urllib.parse import quote


class Spider(Spider):

    def getName(self):
        return "泥视频"

    def init(self, extend=""):
        self.host = "https://www.nivod.vip"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.header = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
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

    # ==================== 通用请求 ====================
    def _req(self, path):
        """通用请求"""
        url = self.host + path
        try:
            rsp = self.fetch(url, headers=self.header)
            if isinstance(rsp, str):
                return rsp
            if rsp and hasattr(rsp, 'text'):
                return rsp.text
        except:
            pass
        return ""

    def _req_play(self, path):
        """请求播放页，带Referer"""
        url = self.host + path
        headers = dict(self.header)
        headers["Referer"] = self.host + "/"
        try:
            rsp = self.fetch(url, headers=headers)
            if isinstance(rsp, str):
                return rsp
            if rsp and hasattr(rsp, 'text'):
                return rsp.text
        except:
            pass
        return ""

    # ==================== 分类配置 ====================
    cats = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "剧集", "type_id": "2"},
        {"type_name": "综艺", "type_id": "3"},
        {"type_name": "动漫", "type_id": "4"},
    ]

    def _build_filters(self):
        filters = {}

        # 通用地区
        area_values = [
            {"n": "全部", "v": ""},
            {"n": "大陆", "v": "大陆"},
            {"n": "香港", "v": "香港"},
            {"n": "台湾", "v": "台湾"},
            {"n": "日本", "v": "日本"},
            {"n": "韩国", "v": "韩国"},
            {"n": "欧美", "v": "欧美"},
            {"n": "英国", "v": "英国"},
            {"n": "泰国", "v": "泰国"},
            {"n": "其它", "v": "其它"},
        ]

        # 通用语言
        lang_values = [
            {"n": "全部", "v": ""},
            {"n": "国语", "v": "国语"},
            {"n": "英语", "v": "英语"},
            {"n": "粤语", "v": "粤语"},
            {"n": "韩语", "v": "韩语"},
            {"n": "日语", "v": "日语"},
            {"n": "西班牙", "v": "西班牙"},
            {"n": "法语", "v": "法语"},
            {"n": "德语", "v": "德语"},
            {"n": "意大利语", "v": "意大利语"},
            {"n": "泰语", "v": "泰语"},
            {"n": "其它", "v": "其它"},
        ]

        # 通用年份
        year_values = [
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
            {"n": "更早", "v": "更早"},
        ]

        # 通用排序
        sort_values = [
            {"n": "添加时间", "v": "time_add"},
            {"n": "更新时间", "v": "time_update"},
            {"n": "人气排序", "v": "hits"},
            {"n": "评分排序", "v": "score"},
        ]

        # 电影子分类 (tid=1)
        movie_class = [
            {"n": "全部", "v": "1"},
            {"n": "动作片", "v": "6"},
            {"n": "喜剧片", "v": "7"},
            {"n": "爱情片", "v": "8"},
            {"n": "科幻片", "v": "9"},
            {"n": "奇幻片", "v": "10"},
            {"n": "恐怖片", "v": "11"},
            {"n": "剧情片", "v": "12"},
            {"n": "战争片", "v": "20"},
            {"n": "纪录片", "v": "21"},
            {"n": "动画片", "v": "26"},
            {"n": "悬疑片", "v": "22"},
            {"n": "冒险片", "v": "23"},
            {"n": "犯罪片", "v": "24"},
            {"n": "惊悚片", "v": "45"},
            {"n": "歌舞片", "v": "46"},
            {"n": "灾难片", "v": "47"},
            {"n": "网络片", "v": "48"},
        ]

        # 剧集子分类 (tid=2)
        tv_class = [
            {"n": "全部", "v": "2"},
            {"n": "国产剧", "v": "13"},
            {"n": "港台剧", "v": "14"},
            {"n": "日剧", "v": "15"},
            {"n": "韩剧", "v": "33"},
            {"n": "欧美剧", "v": "16"},
            {"n": "泰剧", "v": "34"},
            {"n": "新马剧", "v": "35"},
            {"n": "其他剧", "v": "25"},
        ]

        # 综艺子分类 (tid=3)
        variety_class = [
            {"n": "全部", "v": "3"},
            {"n": "大陆综艺", "v": "27"},
            {"n": "港台综艺", "v": "28"},
            {"n": "日本综艺", "v": "29"},
            {"n": "韩国综艺", "v": "36"},
            {"n": "欧美综艺", "v": "30"},
            {"n": "新马泰综艺", "v": "37"},
            {"n": "其他综艺", "v": "38"},
        ]

        # 动漫子分类 (tid=4)
        anime_class = [
            {"n": "全部", "v": "4"},
            {"n": "国产动漫", "v": "31"},
            {"n": "日本动漫", "v": "32"},
            {"n": "韩国动漫", "v": "39"},
            {"n": "港台动漫", "v": "40"},
            {"n": "新马泰动漫", "v": "41"},
            {"n": "欧美动漫", "v": "42"},
            {"n": "其他动漫", "v": "43"},
        ]

        common = [
            {"key": "class", "name": "类型", "value": None},
            {"key": "area", "name": "地区", "value": area_values},
            {"key": "by", "name": "排序", "value": sort_values},
            {"key": "lang", "name": "语言", "value": lang_values},
            {"key": "year", "name": "年份", "value": year_values},
        ]

        for tid, class_list in [("1", movie_class), ("2", tv_class), ("3", variety_class), ("4", anime_class)]:
            fl = []
            for item in common:
                if item["key"] == "class":
                    fl.append({"key": "class", "name": "类型", "value": class_list})
                else:
                    fl.append(item)
            filters[tid] = fl

        return filters

    # ==================== 图片URL补全 ====================
    def _fix_pic(self, pic):
        """将相对图片URL转为完整URL"""
        if not pic:
            return ""
        if pic.startswith("http"):
            return pic
        if not pic.startswith("/"):
            pic = "/" + pic
        return self.host + pic

    # ==================== 通用视频列表解析 ====================
    def _parse_video_list(self, html):
        """解析视频列表 (分类页/筛选页格式: module-poster-item)"""
        videos = []
        seen_ids = set()

        # 匹配: <a href="/nivod/{id}/" title="{title}" class="module-poster-item module-item">
        pattern = re.compile(
            r'<a[^>]+href="/nivod/(\d+)/"[^>]*title="([^"]*)"[^>]*class="module-poster-item[^"]*"[^>]*>([\s\S]*?)</a>',
            re.MULTILINE
        )
        for m in pattern.finditer(html):
            vid = m.group(1)
            title = m.group(2).strip()
            inner = m.group(3)

            if vid in seen_ids:
                continue
            seen_ids.add(vid)

            # 图片 (优先data-original，否则取src，过滤loading图)
            pic = ""
            m_pic = re.search(r'data-original="([^"]*)"', inner)
            if m_pic:
                pic = m_pic.group(1)
            if not pic or pic == "/loading.png":
                m_pic = re.search(r'src="([^"]*)"', inner)
                if m_pic:
                    pic = m_pic.group(1)
            if pic == "/loading.png":
                pic = ""

            # 备注
            note = ""
            m_note = re.search(r'module-item-note[^>]*>\s*([^<]*?)\s*</div>', inner)
            if m_note:
                note = m_note.group(1).strip()

            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self._fix_pic(pic),
                "vod_remarks": note,
            })

        return videos

    def _parse_search_list(self, html):
        """解析搜索结果列表 (module-card-item格式)"""
        videos = []
        seen_ids = set()

        # 匹配: <div class="module-card-item module-item"> ... </div>
        pattern = re.compile(
            r'<div class="module-card-item module-item">([\s\S]*?)</div>\s*</div>\s*</div>',
            re.MULTILINE
        )

        for m in pattern.finditer(html):
            block = m.group(1)

            # ID和标题
            m_link = re.search(r'href="/nivod/(\d+)/"', block)
            if not m_link:
                continue
            vid = m_link.group(1)
            if vid in seen_ids:
                continue
            seen_ids.add(vid)

            # 标题
            title = ""
            m_title = re.search(r'<strong>([^<]+)</strong>', block)
            if m_title:
                title = m_title.group(1).strip()
            if not title:
                m_title = re.search(r'alt="([^"]*)"', block)
                if m_title:
                    title = m_title.group(1).strip()

            # 图片 (优先data-original，否则取src，过滤loading图)
            pic = ""
            m_pic = re.search(r'data-original="([^"]*)"', block)
            if m_pic:
                pic = m_pic.group(1)
            if not pic or pic == "/loading.png":
                m_pic = re.search(r'src="([^"]*)"', block)
                if m_pic:
                    pic = m_pic.group(1)
            if pic == "/loading.png":
                pic = ""

            # 备注
            note = ""
            m_note = re.search(r'module-item-note[^>]*>\s*([^<]*?)\s*</div>', block)
            if m_note:
                note = m_note.group(1).strip()

            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self._fix_pic(pic),
                "vod_remarks": note,
            })

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
        result = {"list": [], "page": int(pg) if pg else 1, "pagecount": 1, "limit": 36, "total": 0}
        try:
            page = int(pg) if pg else 1

            # 处理子分类: extend中的class值是新tid
            actual_tid = tid
            if extend and extend.get("class"):
                actual_tid = str(extend["class"])

            # 构建筛选URL: /k/{tid}-{area}-{by}-{class}-{lang}-{letter}-{}-{}-{page}-{}-{}-{year}/
            # 12个字段，用11个-分隔
            fields = [""] * 12
            fields[0] = actual_tid  # tid

            if extend:
                if extend.get("area"):
                    fields[1] = extend["area"]
                if extend.get("by"):
                    fields[2] = extend["by"]
                # position 4 is class text (not used, class changes tid)
                if extend.get("lang"):
                    fields[4] = extend["lang"]
                # position 6 is letter (not commonly used)
            fields[8] = str(page)  # page at position 9 (index 8)

            if extend and extend.get("year"):
                fields[11] = extend["year"]

            path = "/k/" + "-".join(fields) + "/"

            html = self._req(path)
            if html:
                videos = self._parse_video_list(html)
                result["list"] = videos
                result["page"] = page
                result["total"] = len(videos)
                # 判断是否有下一页
                if len(videos) >= 30:
                    result["pagecount"] = page + 1
                else:
                    result["pagecount"] = page
                result["limit"] = len(videos) if len(videos) > 0 else 36
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
            # 搜索URL格式: /s/{keyword}----------{page}---/
            path = "/s/{0}----------{1}---/".format(quote(key), page)
            html = self._req(path)
            if html:
                result["list"] = self._parse_search_list(html)
        except Exception as e:
            print("searchContent error: {0}".format(e))
        return result

    # ==================== 详情 ====================
    def detailContent(self, array):
        result = {"list": []}
        try:
            vod_id = array[0]
            vid = str(vod_id)

            html = self._req("/nivod/{0}/".format(vid))
            if not html:
                return result

            # 标题
            vod_name = ""
            m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            if m:
                vod_name = m.group(1).strip()

            # 图片
            vod_pic = ""
            m = re.search(r'module-info-poster[\s\S]*?data-original="([^"]*)"', html)
            if m:
                vod_pic = self._fix_pic(m.group(1))

            # 标签 (年份/地区/类型)
            vod_year = ""
            vod_area = ""
            tags = re.findall(r'module-info-tag-link[^>]*>\s*<a[^>]*title="([^"]*)"', html)
            for i, tag in enumerate(tags):
                tag = tag.strip()
                if not tag:
                    continue
                if i == 0 and re.match(r'\d{4}', tag):
                    vod_year = tag
                elif i == 1:
                    vod_area = tag

            # 导演/编剧/主演/语言/上映/更新/连载
            vod_director = ""
            vod_actor = ""
            vod_remarks = ""
            vod_content = ""
            vod_lang = ""

            info_items = re.findall(
                r'<div class="module-info-item[^"]*">\s*<span class="module-info-item-title">([^<]+)</span>\s*'
                r'<div class="module-info-item-content">([\s\S]*?)</div>\s*</div>',
                html
            )
            for item_title, item_content in info_items:
                item_title = item_title.strip()
                names = re.findall(r'<a[^>]*>([^<]+)</a>', item_content)
                value = " ".join(n.strip() for n in names if n.strip())
                if not value:
                    value = re.sub(r'<[^>]+>', '', item_content).strip()

                if "导演" in item_title:
                    vod_director = value
                elif "主演" in item_title or "演员" in item_title:
                    vod_actor = value
                elif "更新" in item_title:
                    vod_remarks = value
                elif "连载" in item_title or "状态" in item_title:
                    if value:
                        vod_remarks = value
                elif "语言" in item_title:
                    vod_lang = value

            # 简介
            m3 = re.search(r'module-info-introduction-content[^>]*>\s*<p>([\s\S]*?)</p>', html)
            if m3:
                vod_content = re.sub(r'<[^>]+>', '', m3.group(1)).strip()

            # ==================== 播放源和分集 ====================
            play_from_list = []
            play_url_list = []

            # 提取所有播放源名称
            all_sources = re.findall(
                r'module-tab-item[^>]*data-dropdown-value="([^"]*)"',
                html
            )

            # 提取所有播放块
            # 格式: <div class="module-play-list-content ..."> ... </div>
            play_blocks = re.findall(
                r'<div class="module-play-list-content[^"]*">([\s\S]*?)</div>\s*</div>\s*</div>',
                html
            )

            for i, block in enumerate(play_blocks):
                eps = re.findall(
                    r'<a[^>]+href="(/niplay/\d+-(\d+)-(\d+)/)"[^>]*>\s*<span>([^<]*)</span>',
                    block
                )
                if not eps:
                    continue

                src_name = all_sources[i] if i < len(all_sources) else "线路{0}".format(i + 1)
                play_from_list.append(src_name)

                ep_list = []
                for ep_url, ep_sid, nid, ep_name in eps:
                    ep_name = ep_name.strip()
                    ep_list.append("{0}${1}".format(ep_name, ep_url))

                play_url_list.append("#".join(ep_list))

            vod = {
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_year": vod_year,
                "vod_area": vod_area,
                "vod_lang": vod_lang,
                "vod_director": vod_director,
                "vod_actor": vod_actor,
                "vod_remarks": vod_remarks,
                "vod_content": vod_content,
                "vod_play_from": "$$$".join(play_from_list),
                "vod_play_url": "$$$".join(play_url_list),
            }
            result["list"] = [vod]
        except Exception as e:
            print("detailContent error: {0}".format(e))
        return result

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "playUrl": "", "url": "", "header": "", "jx": 0}
        try:
            # id格式: 集名$播放路径
            play_url_part = id.split("$")[-1] if "$" in id else id
            if not play_url_part.startswith("/"):
                play_url_part = "/" + play_url_part

            html = self._req_play(play_url_part)
            if not html:
                return result

            m = re.search(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\});', html)
            if m:
                raw = m.group(1)
                m2 = re.search(r'"url"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
                if m2:
                    url = m2.group(1).replace("\\/", "/")
                    try:
                        url = url.encode().decode("unicode_escape")
                    except:
                        pass

                    headers = {
                        "User-Agent": self.ua,
                        "Referer": self.host + play_url_part,
                    }

                    if ".m3u8" in url or ".mp4" in url:
                        # 直链视频，直接播放
                        result["parse"] = 0
                        result["jx"] = 0
                        result["url"] = url
                    else:
                        # 其他外链，走嗅探
                        result["parse"] = 1
                        result["jx"] = 1
                        result["url"] = url

                    result["header"] = json.dumps(headers)
                    return result

            # 没有player_aaaa，嗅探模式
            result["parse"] = 1
            result["jx"] = 1
            result["url"] = self.host + play_url_part
            result["header"] = json.dumps({"User-Agent": self.ua})
        except Exception as e:
            print("playerContent error: {0}".format(e))
        return result
