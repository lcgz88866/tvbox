# -*- coding: utf-8 -*-
# 骚火电影 - shdy5.us
# maccms V10 二次开发 + 自定义模板，iframe解析播放
import re
import sys
import json
import urllib.parse

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def getName(self):
        return "骚火电影"

    def init(self, extend=""):
        self.host = "https://shdy5.us"
        self.ua = "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Referer": self.host,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        # 主分类
        self.cats = [
            {"type_name": "电影", "type_id": "1"},
            {"type_name": "电视剧", "type_id": "2"},
        ]
        # 子分类筛选
        self.sub_cats = {
            "1": [
                {"n": "全部", "v": "1"},
                {"n": "喜剧", "v": "6"},
                {"n": "爱情", "v": "7"},
                {"n": "恐怖", "v": "8"},
                {"n": "动作", "v": "9"},
                {"n": "科幻", "v": "10"},
                {"n": "战争", "v": "11"},
                {"n": "犯罪", "v": "12"},
                {"n": "动画", "v": "13"},
                {"n": "奇幻", "v": "14"},
                {"n": "剧情", "v": "15"},
                {"n": "冒险", "v": "16"},
                {"n": "悬疑", "v": "17"},
                {"n": "惊悚", "v": "18"},
                {"n": "其它", "v": "19"},
            ],
            "2": [
                {"n": "全部", "v": "2"},
                {"n": "大陆剧", "v": "20"},
                {"n": "港剧", "v": "21"},
                {"n": "韩剧", "v": "22"},
                {"n": "美剧", "v": "23"},
                {"n": "日剧", "v": "24"},
                {"n": "英剧", "v": "25"},
                {"n": "台剧", "v": "26"},
                {"n": "其它", "v": "27"},
            ],
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
            for tid, opts in self.sub_cats.items():
                result["filters"][tid] = [
                    {"key": "class", "name": "类型", "value": opts}
                ]
            # 首页推荐：抓取首页视频列表
            html = self.fetch_html(self.host)
            if html:
                result["list"] = self.parse_list(html)[:24]
        except Exception as e:
            print(f'homeContent error: {e}')
        return result

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 30, "total": 0}
        try:
            # 类型筛选通过切换子分类tid实现
            real_tid = extend.get("class", tid) if extend else tid
            if str(pg) == "1":
                url = f"{self.host}/list/{real_tid}.html"
            else:
                url = f"{self.host}/list/{real_tid}-{pg}.html"
            html = self.fetch_html(url)
            if html:
                result["list"] = self.parse_list(html)
                # 解析分页
                page_match = re.search(r'<span>(\d+)/(\d+)</span>', html)
                if page_match:
                    result["page"] = int(page_match.group(1))
                    result["pagecount"] = int(page_match.group(2))
                else:
                    # 如果有下一页链接则pagecount至少为当前页+1
                    if '下一页' in html:
                        result["pagecount"] = int(pg) + 1
        except Exception as e:
            print(f'categoryContent error: {e}')
        return result

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            detail_html = self.fetch_html(f"{self.host}/movie/{vod_id}.html")
            if not detail_html:
                return result

            # 标题
            title_match = re.search(r'<h1 class="v_title"><a[^>]*>([^<]+)</a>', detail_html)
            vod_name = title_match.group(1).strip() if title_match else ""

            # 封面图（background-image方式）
            vod_pic = ""
            bg_match = re.search(r'class="m_background"\s+style="background-image:url\(([^)]+)\)', detail_html)
            if bg_match:
                vod_pic = bg_match.group(1).strip()

            # 基本信息：地区/年份/类型/导演/主演
            # 实际HTML: <p>大陆 / 2026 / 爱情 / 导演:钟青 / 主演:孟子义,何与,...<a href="#info_more">剧情介绍</a></p>
            vod_area = ""
            vod_year = ""
            vod_director = ""
            vod_actor = ""
            info_match = re.search(r'<section class="grid_box v_info_box">.*?<p>(.*?)</p>', detail_html, re.S)
            if info_match:
                info_raw = info_match.group(1)
                # 去掉HTML标签
                info_text = re.sub(r'<[^>]+>', '', info_raw).strip()
                parts = [p.strip() for p in info_text.split(' / ')]
                if len(parts) >= 1:
                    vod_area = parts[0]
                if len(parts) >= 2:
                    vod_year = parts[1]
                # 导演
                dir_match = re.search(r'导演[:：]\s*(.+?)(?:\s*/\s*主演|$)', info_text)
                if dir_match:
                    vod_director = dir_match.group(1).strip()
                # 主演
                act_match = re.search(r'主演[:：]\s*(.+)', info_text)
                if act_match:
                    vod_actor = act_match.group(1).strip()
                    # 去掉剧情介绍
                    vod_actor = re.sub(r'剧情介绍.*', '', vod_actor).strip()

            # 剧情简介
            # 实际HTML: <p class="p_txt show_part">简介内容<br /><br /><a>推广</a>，由骚火电影...</p>
            vod_content = ""
            content_match = re.search(r'<p class="p_txt[^"]*"[^>]*>(.*?)</p>', detail_html, re.S)
            if content_match:
                content_raw = content_match.group(1)
                # 按br分割，只取第一段剧情
                content_parts = re.split(r'<br\s*/?>', content_raw)
                if content_parts:
                    vod_content = re.sub(r'<[^>]+>', '', content_parts[0]).strip()

            # 备注
            vod_remarks = ""
            rem_match = re.search(r'<div class="v_note">([^<]*)</div>', detail_html)
            if rem_match:
                vod_remarks = rem_match.group(1).strip()

            # 播放列表
            play_from = []
            play_url = []

            # 线路名称
            line_names = re.findall(r'<li[^>]*class="[^"]*current[^"]*"[^>]*>([^<]+)</li>', detail_html)
            # 更通用的提取方式
            from_matches = re.findall(r'<li([^>]*)>([^<]*)</li>', detail_html)
            lines = []
            # 从 from_list 提取
            from_block = re.search(r'<ul class="from_list">(.*?)</ul>', detail_html, re.S)
            if from_block:
                line_items = re.findall(r'<li[^>]*>([^<]+)</li>', from_block.group(1))
                lines = [l.strip() for l in line_items if l.strip()]

            # 剧集列表
            play_block = re.search(r'<ul class="play_list"[^>]*id="play_link">(.*?)</ul>', detail_html, re.S)
            if play_block:
                # 按li分割各线路
                li_blocks = re.findall(r'<li[^>]*>(.*?)</li>', play_block.group(1), re.S)
                for idx, li_block in enumerate(li_blocks):
                    eps = re.findall(r'href="/play/(\d+)-(\d+)-(\d+)\.html"[^>]*>([^<]+)</a>', li_block)
                    if eps:
                        urls = []
                        for ep_id, ep_line, ep_num, ep_name in eps:
                            ep_name = ep_name.strip()
                            urls.append(f"{ep_name}${ep_id}-{ep_line}-{ep_num}")
                        line_name = lines[idx] if idx < len(lines) else f"线路{idx+1}"
                        play_from.append(line_name)
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
            url = f"{self.host}/s----------.html?wd={wd}"
            html = self.fetch_html(url)
            if html:
                result["list"] = self.parse_list(html)
        except Exception as e:
            print(f'searchContent error: {e}')
        return result

    def playerContent(self, flag, pid, vipFlags):
        result = {}
        try:
            # pid 格式: vod_id-line-episode
            play_html = self.fetch_html(f"{self.host}/play/{pid}.html")
            if play_html:
                # 提取 iframe src
                iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', play_html)
                if iframe_match:
                    iframe_url = iframe_match.group(1)
                    result["parse"] = 1
                    result["url"] = iframe_url
                    result["header"] = {"User-Agent": self.ua, "Referer": self.host}
                    return result

            # fallback
            result["parse"] = 1
            result["url"] = f"{self.host}/play/{pid}.html"
            result["header"] = {"User-Agent": self.ua, "Referer": self.host}
        except Exception as e:
            print(f'playerContent error: {e}')
            result["parse"] = 1
            result["url"] = f"{self.host}/play/{pid}.html"
            result["header"] = {"User-Agent": self.ua, "Referer": self.host}
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
            blocks = re.findall(
                r'<div class="v_img">\s*<a\s+href="/movie/(\d+)\.html"\s+title="([^"]+)"[^>]*>\s*<img[^>]+data-original="([^"]+)"',
                html, re.S
            )
            seen = set()
            for vod_id, vod_name, vod_pic in blocks:
                if vod_id in seen:
                    continue
                seen.add(vod_id)
                # 尝试获取备注
                rem_match = re.search(
                    rf'<a href="/movie/{vod_id}\.html"[^>]*>.*?<div class="v_note">([^<]*)</div>',
                    html, re.S
                )
                vod_remarks = rem_match.group(1).strip() if rem_match else ""
                items.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": vod_remarks,
                })
        except Exception as e:
            print(f'parse_list error: {e}')
        return items