# -*- coding: utf-8 -*-
# 农民影视 - www.nmdvd.top
# 苹果CMS + wp01模板，PC端检测UA跳404，必须用移动端UA
import re
import sys
import json
import base64
import hashlib
import urllib.parse

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def getName(self):
        return "农民影视"

    def init(self, extend=""):
        self.host = "https://www.nmdvd.top"
        self.ua = "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Referer": self.host,
        }
        # 主分类（苹果CMS tid）
        self.cats = [
            {"type_name": "电影", "type_id": "20"},
            {"type_name": "剧集", "type_id": "21"},
            {"type_name": "动漫", "type_id": "22"},
            {"type_name": "综艺", "type_id": "23"},
            {"type_name": "短剧", "type_id": "24"},
        ]
        # 子分类（用于筛选切换tid）
        self.sub_cats = {
            "20": [
                {"n": "全部", "v": "20"},
                {"n": "动作片", "v": "26"},
                {"n": "喜剧片", "v": "27"},
                {"n": "爱情片", "v": "28"},
                {"n": "科幻片", "v": "29"},
                {"n": "恐怖片", "v": "30"},
                {"n": "剧情片", "v": "31"},
                {"n": "战争片", "v": "32"},
                {"n": "动画片", "v": "33"},
            ],
            "21": [
                {"n": "全部", "v": "21"},
                {"n": "国产剧", "v": "34"},
                {"n": "港台剧", "v": "35"},
                {"n": "日韩剧", "v": "36"},
                {"n": "欧美剧", "v": "37"},
                {"n": "泰国剧", "v": "38"},
            ],
            "22": [
                {"n": "全部", "v": "22"},
            ],
            "23": [
                {"n": "全部", "v": "23"},
            ],
            "24": [
                {"n": "全部", "v": "24"},
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
            # 筛选数据
            for tid, opts in self.sub_cats.items():
                result["filters"][tid] = [
                    {"key": "class", "name": "类型", "value": opts}
                ]
            # 首页推荐（ajax接口，各分类取前6条）
            seen = set()
            for cat in self.cats:
                tid = cat["type_id"]
                url = f"{self.host}/index.php/ajax/data?mid=1&tid={tid}&page=1"
                html = self.fetch_html(url)
                if html:
                    data = json.loads(html)
                    for v in data.get("list", [])[:6]:
                        vid = str(v.get("vod_id", ""))
                        if vid and vid not in seen:
                            seen.add(vid)
                            result["list"].append({
                                "vod_id": vid,
                                "vod_name": v.get("vod_name", ""),
                                "vod_pic": v.get("vod_pic", ""),
                                "vod_remarks": v.get("vod_remarks", ""),
                            })
        except Exception as e:
            print(f'homeContent error: {e}')
        return result

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 10, "total": 0}
        try:
            # 类型筛选通过切换子分类tid实现
            real_tid = extend.get("class", tid) if extend else tid
            url = f"{self.host}/index.php/ajax/data?mid=1&tid={real_tid}&page={pg}"
            html = self.fetch_html(url)
            if html:
                data = json.loads(html)
                if data.get("code") == 1:
                    for v in data.get("list", []):
                        result["list"].append({
                            "vod_id": str(v.get("vod_id", "")),
                            "vod_name": v.get("vod_name", ""),
                            "vod_pic": v.get("vod_pic", ""),
                            "vod_remarks": v.get("vod_remarks", ""),
                        })
                    result["pagecount"] = data.get("pagecount", 1)
                    result["total"] = data.get("total", 0)
                    result["limit"] = data.get("limit", 10)
        except Exception as e:
            print(f'categoryContent error: {e}')
        return result

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            detail_html = self.fetch_html(f"{self.host}/vod/{vod_id}.html")
            if not detail_html:
                return result

            # 标题
            h1_match = re.search(r'<h3 class="title">([^<]+)</h3>', detail_html)
            vod_name = h1_match.group(1).strip() if h1_match else ""

            # 封面
            pic_match = re.search(r'data-original="([^"]+)"', detail_html)
            vod_pic = pic_match.group(1) if pic_match else ""

            # 剧情描述（修复：匹配 <span class="detail-sketch">）
            vod_content = ""
            content_match = re.search(r'<span class="detail-sketch">(.*?)</span>', detail_html, re.S)
            if content_match:
                vod_content = re.sub(r'<[^>]+>', '', content_match.group(1)).strip()

            # 导演
            vod_director = ""
            director_match = re.search(r'<p[^>]*>导演[:：](.*?)</p>', detail_html, re.S)
            if director_match:
                vod_director = re.sub(r'<[^>]+>', '', director_match.group(1)).strip()

            # 主演
            vod_actor = ""
            actor_match = re.search(r'<p[^>]*>主演[:：](.*?)</p>', detail_html, re.S)
            if actor_match:
                vod_actor = re.sub(r'<[^>]+>', '', actor_match.group(1)).strip()

            # 年份
            vod_year = ""
            year_match = re.search(r'<p[^>]*>年份[:：](\d{4})</p>', detail_html, re.S)
            if year_match:
                vod_year = year_match.group(1)

            # 地区
            vod_area = ""
            area_match = re.search(r'<p[^>]*>地区[:：](.*?)</p>', detail_html, re.S)
            if area_match:
                vod_area = re.sub(r'<[^>]+>', '', area_match.group(1)).strip()

            # 备注
            vod_remarks = ""
            remarks_match = re.search(r'<span class="pic-text[^"]*">([^<]*)</span>', detail_html)
            if remarks_match:
                vod_remarks = remarks_match.group(1).strip()

            # 播放列表
            play_from = []
            play_url = []

            # 线路名称: <a href="#playlist{sid}" data-toggle="tab">线路名</a>
            line_tabs = re.findall(
                r'<a\s+href="#playlist(\d+)"\s+data-toggle="tab">([^<]+)</a>',
                detail_html
            )
            line_map = {sid: name.strip() for sid, name in line_tabs}

            # 按 playlist 块提取选集（修复：只匹配单个块）
            for sid_str, line_name in line_map.items():
                playlist_block = re.search(
                    r'<div[^>]*id="playlist' + sid_str + r'"[^>]*>(.*?)</div>',
                    detail_html, re.S
                )
                if playlist_block:
                    eps = re.findall(
                        r'href="/play/(\d+)-(\d+)-(\d+)\.html"[^>]*>([^<]+)</a>',
                        playlist_block.group(1)
                    )
                    urls = []
                    for ep_id, ep_sid, ep_nid, ep_name in eps:
                        ep_name = ep_name.strip()
                        if not ep_name:
                            continue
                        urls.append(f"{ep_name}${ep_id}-{ep_sid}-{ep_nid}")
                    if urls:
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
            import urllib.parse
            wd = urllib.parse.quote(key)
            # 使用 ajax/data 接口搜索，绕过搜索页的人机验证
            url = f"{self.host}/index.php/ajax/data?mid=1&wd={wd}&page={pg}"
            html = self.fetch_html(url)
            if html:
                data = json.loads(html)
                if data.get("code") == 1:
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

    def playerContent(self, flag, pid, vipFlags):
        result = {}
        try:
            # 1. 获取播放页提取 player_aaaa
            play_page = self.fetch_html(f"{self.host}/play/{pid}.html")
            if not play_page:
                result["parse"] = 1
                result["url"] = f"{self.host}/play/{pid}"
                result["header"] = {"User-Agent": self.ua, "Referer": self.host}
                return result

            block_start = play_page.find('var player_aaaa=')
            if block_start < 0:
                result["parse"] = 1
                result["url"] = f"{self.host}/play/{pid}"
                result["header"] = {"User-Agent": self.ua, "Referer": self.host}
                return result

            block_end = play_page.find('</script>', block_start)
            block = play_page[block_start:block_end]
            url_match = re.search(r'"url":"([^"]+)"', block)
            enc_match = re.search(r'"encrypt":"?([^",}]+)"?', block)

            if not url_match:
                result["parse"] = 1
                result["url"] = f"{self.host}/play/{pid}"
                result["header"] = {"User-Agent": self.ua, "Referer": self.host}
                return result

            original_vid = url_match.group(1).replace('\\/', '/').strip()
            encrypt = int(enc_match.group(1)) if enc_match else 0

            # 2. 调用 api.php 获取加密数据并解密
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            api_url = f"{self.host}/jx/api.php"
            data = urllib.parse.urlencode({"vid": original_vid}).encode('utf-8')
            req = urllib.request.Request(api_url, data=data, headers={
                "User-Agent": self.ua,
                "Referer": f"{self.host}/play/{pid}.html",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            })
            try:
                with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                    api_resp = resp.read().decode('utf-8', errors='ignore')
                    api_data = json.loads(api_resp)
                    if str(api_data.get("code")) == "200":
                        info = api_data.get("data", {})
                        cipher = info.get("url") or info.get("vid") or ""
                        urlmode = int(str(info.get("urlmode", "0")) or 0)

                        # 根据 urlmode 选择解密方式尝试
                        candidates = []
                        if urlmode in (1, 0):
                            candidates.append(self.decode1(cipher))
                        if urlmode in (2, 0):
                            candidates.append(self.decode2(cipher))
                        candidates.extend([cipher, urllib.parse.unquote(cipher)])

                        for u in candidates:
                            if u and u.startswith("http"):
                                result["parse"] = 0
                                result["url"] = u
                                result["header"] = {"User-Agent": self.ua, "Referer": self.host}
                                return result
            except Exception as e:
                print(f'api.php error: {e}')

            # 3. fallback: 尝试直接解密 original_vid
            candidates = [self.decode1(original_vid), self.decode2(original_vid), original_vid, urllib.parse.unquote(original_vid)]
            for u in candidates:
                if u and u.startswith("http"):
                    result["parse"] = 0
                    result["url"] = u
                    result["header"] = {"User-Agent": self.ua, "Referer": self.host}
                    return result

            # 4. 最终 fallback: WebView
            result["parse"] = 1
            result["url"] = f"{self.host}/play/{pid}"
            result["header"] = {"User-Agent": self.ua, "Referer": self.host}

        except Exception as e:
            print(f'playerContent error: {e}')
            result["parse"] = 1
            result["url"] = f"{self.host}/play/{pid}"
            result["header"] = {"User-Agent": self.ua, "Referer": self.host}
        return result

    # ==================== 解密辅助方法 ====================

    def decode1(self, cipher):
        try:
            raw = base64.b64decode(self._fix_b64(cipher))
            key = hashlib.md5(b"#tips").hexdigest().encode("utf-8")
            s2 = bytearray(raw[i] ^ key[i % len(key)] for i in range(len(raw)))
            s2_str = self._fix_b64(s2.decode("utf-8", errors="ignore"))
            return urllib.parse.unquote(base64.b64decode(s2_str).decode("utf-8", errors="ignore"))
        except:
            return ""

    def decode2(self, cipher):
        try:
            raw = base64.b64decode(self._fix_b64(cipher)).decode("utf-8", errors="ignore")
            m_map = "PXhw7UT1B0a9kQDKZsjIASmOezxYG4CHo5Jyfg2b8FLpEvRr3WtVnlqMidu6cN"
            return urllib.parse.unquote("".join(m_map[(m_map.find(c) + 59) % 62] if m_map.find(c) != -1 else c for c in raw[1::3]).strip())
        except:
            return ""

    def _fix_b64(self, s):
        s = re.sub(r"[^A-Za-z0-9+/=]", "", str(s).strip())
        return s + "=" * (-len(s) % 4)

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
        """解析视频列表（HTML模式，用于搜索）"""
        items = []
        try:
            blocks = re.findall(
                r'<a\s+class="stui-vodlist__thumb[^"]*"\s+href="/vod/(\d+)\.html"[^>]*title="([^"]+)"[^>]*data-original="([^"]+)"[^>]*>(.*?)</a>',
                html, re.S
            )
            seen = set()
            for vod_id, vod_name, vod_pic, block in blocks:
                if vod_id in seen:
                    continue
                seen.add(vod_id)
                rem_match = re.search(r'<span class="pic-text[^"]*">([^<]*)</span>', block)
                vod_remarks = rem_match.group(1) if rem_match else ""
                items.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": vod_remarks,
                })
        except Exception as e:
            print(f'parse_list error: {e}')
        return items