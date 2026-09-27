# -*- coding: utf-8 -*-
"""
==========================================================
  西瓜影院 (jsntdl.com) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎)
  框架: maccms + 自定义ds3模板
  更新: 2026-08-18

  URL规则:
    首页: /
    分类页: /xigua/{slug}.html (静态HTML全量返回, 客户端分页)
    筛选页: /xiguasp/{slug}-----------.html (JS动态加载, 不可用)
    详情页: /xgdetail/{vod_id}.html
    播放页: /xgplay/{vod_id}-{sid}-{nid}.html
    搜索: /index.php/ajax/suggest?mid=1&wd={keyword}&limit=20 (JSON)

  主分类 (6个, 对应网站主导航):
    电影(dianying) 电视剧(lianxuju) 综艺(zongyi)
    动漫(dongman) 短剧(duanju) B站(bzshipin)

  筛选器 (从网站xiguasp页data-type/data-val提取):
    电影: 类型(27) + 地区(15) + 排序
    电视剧: 类型(32) + 地区(10) + 排序
    综艺: 类型(14) + 地区(4) + 排序
    动漫: 类型(24) + 地区(4) + 排序
    短剧: 地区(15) + 年份(13) + 排序
    B站: 排序

  播放源:
    lzm3u8 - m3u8直链 (parse=0)
    qiyi/youku/qq - 平台URL (parse=1, 使用站点播放页+click脚本)

  播放逻辑:
    1. 从 /xgplay 页面提取 player_aaaa JSON
    2. encrypt=0: URL直接使用
    3. encrypt=1: unquote(url)
    4. encrypt=2: base64decode + unquote(url)
    5. 直链m3u8/mp4 → parse=0
    6. 平台URL → parse=1, 返回站点播放页URL + click脚本
==========================================================
"""

import sys
sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import types
    base_mod = types.ModuleType('base')
    spider_mod = types.ModuleType('base.spider')
    class Spider:
        pass
    spider_mod.Spider = Spider
    base_mod.spider = spider_mod
    sys.modules['base'] = base_mod
    sys.modules['base.spider'] = spider_mod

import re
import json
import ssl
import base64
import urllib.request
import urllib.parse
from urllib.parse import quote, urlencode
from html import unescape as html_unescape


class Spider(Spider):

    HOST = "https://jsntdl.com"
    UA = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # 主分类 (slug格式, 对应网站主导航)
    CATEGORIES = [
        {"type_name": "电影", "type_id": "dianying"},
        {"type_name": "电视剧", "type_id": "lianxuju"},
        {"type_name": "综艺", "type_id": "zongyi"},
        {"type_name": "动漫", "type_id": "dongman"},
        {"type_name": "短剧", "type_id": "duanju"},
        {"type_name": "B站", "type_id": "bzshipin"},
    ]

    # 各分类实际筛选值 (从网站xiguasp页面data-type/data-val提取)
    FILTER_DATA = {
        "dianying": {
            "class": ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪",
                      "犯罪", "伦理", "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑",
                      "惊悚", "经典", "青春", "文艺", "微电影", "古装", "历史", "运动",
                      "农村", "儿童", "网络电影"],
            "area": ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
                     "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
        },
        "lianxuju": {
            "class": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻",
                      "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "悬疑",
                      "谍战", "刑侦", "律政", "都市", "爱情", "仙侠", "武侠", "玄幻",
                      "科幻", "年代", "军旅", "励志", "穿越", "宫斗", "权谋", "其他"],
            "area": ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国",
                     "新加坡", "其他"],
        },
        "zongyi": {
            "class": ["真人秀", "情感", "爱情", "访谈", "旅游", "音乐", "美食", "纪实",
                      "竞技", "曲艺", "生活", "游戏互动", "财经", "求职"],
            "area": ["内地", "港台", "日韩", "欧美"],
        },
        "dongman": {
            "class": ["动作", "玄幻", "亲子", "科幻", "热血", "推理", "搞笑", "冒险",
                      "校园", "机战", "运动", "战争", "少年", "少女", "社会", "原创",
                      "益智", "励志", "动漫", "惊悚", "治愈", "神魔", "武侠", "其他"],
            "area": ["中国", "日本", "欧美", "其他"],
        },
        "duanju": {
            "area": ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
                     "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
            "year": ["2026", "2025", "2024", "2023", "2022", "2021", "2020",
                     "2019", "2018", "2017", "2016", "2015", "2014"],
        },
        "bzshipin": {},
    }

    # 排序选项 (所有分类通用)
    SORT_OPTIONS = [
        {"n": "按最新", "v": "time"},
        {"n": "按最热", "v": "hits"},
        {"n": "按评分", "v": "score"},
    ]

    PER_PAGE = 20

    # 卡片块正则 (匹配整个卡片div)
    CARD_BLOCK_RE = re.compile(
        r'<div class="public-list-box[^"]*">(.*?)</div>\s*</div>\s*</div>',
        re.DOTALL
    )

    # 卡片内链接+图片+标签正则
    CARD_INNER_RE = re.compile(
        r'href="/xgdetail/(\d+)\.html"[^>]*title="([^"]*)"'  # vod_id, title
        r'.*?data-src="([^"]*)"'  # pic
        r'.*?<span class="public-prt[^"]*"[^>]*>([^<]*)</span>'  # class label
        r'.*?<span class="public-list-prb[^"]*"[^>]*>([^<]*)</span>',  # remarks
        re.DOTALL
    )

    # 备用卡片内正则 (无class标签)
    CARD_INNER_RE2 = re.compile(
        r'href="/xgdetail/(\d+)\.html"[^>]*title="([^"]*)"'
        r'.*?data-src="([^"]*)"',
        re.DOTALL
    )

    def init(self, extend=""):
        self.ua = self.UA
        self.host = self.HOST
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/json,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
        }
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

        self._play_header = json.dumps({
            "User-Agent": self.ua,
        })

    def getName(self):
        return "西瓜影院"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|ts)(\?|#|$)', url, re.I))

    def manualVideoCheck(self):
        return False

    def getDependence(self):
        return []

    def action(self, action):
        pass

    def destroy(self):
        pass

    # ===== HTTP辅助 =====

    def _fetch_html(self, url, timeout=15):
        try:
            req = urllib.request.Request(url, headers=self.headers)
            resp = urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx)
            return resp.read().decode('utf-8', errors='replace')
        except:
            return ""

    def _fetch_json(self, url, timeout=10):
        try:
            req = urllib.request.Request(url, headers=self.headers)
            resp = urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx)
            return json.loads(resp.read().decode('utf-8', errors='replace'))
        except:
            return {}

    # ===== 首页 =====

    def homeContent(self, filter):
        result = {}
        classes = []
        for c in self.CATEGORIES:
            classes.append({"type_name": c["type_name"], "type_id": c["type_id"]})
        result["class"] = classes
        result["filters"] = self._get_filters()
        return result

    def homeVideoContent(self):
        """首页推荐 - 电影分类前20条"""
        html = self._fetch_html(self.host + "/xigua/dianying.html")
        videos = self._parse_cards(html)
        return {"list": videos[:20]}

    def _get_filters(self):
        """获取分类筛选器 - 按网站实际数据生成"""
        filters = {}
        for c in self.CATEGORIES:
            tid = c["type_id"]
            fdata = self.FILTER_DATA.get(tid, {})
            filter_list = []

            # 类型 (class)
            if fdata.get("class"):
                filter_list.append({
                    "key": "class",
                    "name": "类型",
                    "value": [{"n": "全部", "v": ""}] +
                             [{"n": v, "v": v} for v in fdata["class"]]
                })

            # 地区 (area)
            if fdata.get("area"):
                filter_list.append({
                    "key": "area",
                    "name": "地区",
                    "value": [{"n": "全部", "v": ""}] +
                             [{"n": v, "v": v} for v in fdata["area"]]
                })

            # 年份 (year) - 仅短剧有
            if fdata.get("year"):
                filter_list.append({
                    "key": "year",
                    "name": "年份",
                    "value": [{"n": "全部", "v": ""}] +
                             [{"n": v, "v": v} for v in fdata["year"]]
                })

            # 排序 (by) - 所有分类通用
            filter_list.append({
                "key": "by",
                "name": "排序",
                "value": self.SORT_OPTIONS,
            })

            filters[tid] = filter_list
        return filters

    # ===== 分类列表 =====

    def _parse_cards(self, html):
        """解析视频卡片, 提取class标签用于客户端筛选
        先按div块分割卡片, 再在每个卡片块内提取字段, 避免跨卡片匹配
        """
        videos = []
        seen = set()

        # 按卡片块分割
        for block_m in self.CARD_BLOCK_RE.finditer(html):
            block = block_m.group(1)
            # 在卡片块内提取字段
            m = self.CARD_INNER_RE.search(block)
            if m:
                vid = m.group(1)
                if vid in seen:
                    continue
                seen.add(vid)
                title = html_unescape(m.group(2))
                pic = m.group(3)
                class_label = html_unescape(m.group(4)).strip()
                remarks = html_unescape(m.group(5)).strip()
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remarks,
                    "_class": class_label,
                })
            else:
                # 备用正则 (无class标签)
                m2 = self.CARD_INNER_RE2.search(block)
                if m2:
                    vid = m2.group(1)
                    if vid in seen:
                        continue
                    seen.add(vid)
                    title = html_unescape(m2.group(2))
                    pic = m2.group(3)
                    videos.append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": "",
                        "_class": "",
                    })
        return videos

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        extend = extend or {}

        # 网站xiguasp页面使用JS动态加载(返回0卡片),
        # 因此始终使用xigua分类页(静态HTML全量返回), 客户端筛选+分页
        slug = tid
        html = self._fetch_html(self.host + f"/xigua/{slug}.html")
        all_videos = self._parse_cards(html)

        # 客户端筛选: 按类型(class)
        # 卡片的 public-prt span 包含类型标签(如"动作"/"喜剧"/"剧情")
        if extend.get("class"):
            filter_class = extend["class"]
            all_videos = [v for v in all_videos if v.get("_class") == filter_class]

        # 移除内部字段_class (不返回给TVBox)
        for v in all_videos:
            v.pop("_class", None)

        # 客户端分页
        start = (page - 1) * self.PER_PAGE
        videos = all_videos[start:start + self.PER_PAGE]
        pagecount = (len(all_videos) + self.PER_PAGE - 1) // self.PER_PAGE if all_videos else 1

        return {
            "list": videos,
            "page": page,
            "pagecount": max(pagecount, 1),
            "limit": self.PER_PAGE,
            "total": len(all_videos),
        }

    # ===== 详情页 =====

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vid = ids[0]
            html = self._fetch_html(self.host + f"/xgdetail/{vid}.html")
            if not html:
                return result

            # === 提取标题 ===
            # 优先从 <title>《标题》 提取
            title_m = re.search(r'<title>《(.*?)》', html)
            if not title_m:
                title_m = re.search(r'<h3 class="slide-info-title[^"]*">([^<]*)</h3>', html)
            vod_name = html_unescape(title_m.group(1).strip()) if title_m else ""

            # === 提取图片 ===
            # detail-pic 区域的 data-src
            pic_m = re.search(r'class="detail-pic"[^>]*>.*?data-src="([^"]+)"', html, re.DOTALL)
            if not pic_m:
                pic_m = re.search(r'data-src="(https?://[^"]*\.(?:jpg|webp|png|jpeg)[^"]*)"', html)
            vod_pic = pic_m.group(1) if pic_m else ""

            # === 提取年份/地区/类型 ===
            # slide-info-remarks spans 按顺序: 年份, 地区, 类型
            remarks_spans = re.findall(
                r'<span class="slide-info-remarks">(.*?)</span>',
                html, re.DOTALL
            )
            remarks_values = []
            for span in remarks_spans:
                m = re.search(r'<a[^>]*>([^<]*)</a>', span)
                if m:
                    val = html_unescape(m.group(1).strip())
                    if val:
                        remarks_values.append(val)
            vod_year = remarks_values[0] if len(remarks_values) > 0 else ""
            vod_area = remarks_values[1] if len(remarks_values) > 1 else ""
            vod_type = remarks_values[2] if len(remarks_values) > 2 else ""

            # === 提取备注 ===
            remarks_m = re.search(
                r'<strong class="r6">备注\s*[:：]\s*</strong>([^<]+)',
                html
            )
            vod_remarks = html_unescape(remarks_m.group(1).strip()) if remarks_m else ""

            # === 提取导演 ===
            # <strong class="r6">导演 :</strong><a>沈严</a><span class="slash">/</span><a>李江明</a>...
            dir_section = re.search(
                r'<strong class="r6">导演\s*[:：]\s*</strong>(.*?)(?:</div>|<div class="slide-info)',
                html, re.DOTALL
            )
            vod_director = ""
            if dir_section:
                directors = re.findall(r'<a[^>]*>([^<]*)</a>', dir_section.group(1))
                vod_director = '/'.join(html_unescape(d.strip()) for d in directors if d.strip())

            # === 提取演员 ===
            act_section = re.search(
                r'<strong class="r6">演员\s*[:：]\s*</strong>(.*?)(?:</div>|<div class="slide-info)',
                html, re.DOTALL
            )
            vod_actor = ""
            if act_section:
                actors = re.findall(r'<a[^>]*>([^<]*)</a>', act_section.group(1))
                vod_actor = '/'.join(html_unescape(a.strip()) for a in actors if a.strip())

            # === 提取简介 ===
            # 优先从 info-parameter 隐藏区的 简介 字段
            content_m = re.search(
                r'<em class="cor4">简介[：:]\s*</em>(.*?)</li>',
                html, re.DOTALL
            )
            vod_content = ""
            if content_m:
                vod_content = re.sub(r'<[^>]+>', '', content_m.group(1)).strip()
                vod_content = html_unescape(vod_content)
            else:
                # 备用: 从 text-content 或 content 区域提取
                content_m2 = re.search(
                    r'class="text-content[^"]*"[^>]*>(.*?)(?:</div>|<div class="text-open)',
                    html, re.DOTALL
                )
                if content_m2:
                    vod_content = re.sub(r'<[^>]+>', '', content_m2.group(1)).strip()
                    vod_content = html_unescape(vod_content)

            # === 提取播放源和剧集 ===
            # 1. 提取播放源tab名称 (按顺序)
            tab_matches = re.findall(
                r'<a class="swiper-slide">(.*?)</a>',
                html, re.DOTALL
            )
            source_names = []
            for tab in tab_matches:
                # 先移除badge span (集数数字), 避免与源名拼接
                tab = re.sub(r'<span class="badge"[^>]*>\d+</span>', '', tab)
                name = re.sub(r'<[^>]+>', '', tab)
                name = html_unescape(name).strip()
                if name:
                    source_names.append(name)

            # 过滤掉下载源 (包含"下载"或"dow"的名称)
            play_source_names = [
                n for n in source_names
                if '下载' not in n and 'dow' not in n.lower()
            ]

            # 2. 提取所有播放链接, 按sid分组
            play_links = re.findall(
                r'href="(/xgplay/' + re.escape(str(vid)) + r'-(\d+)-(\d+)\.html)"[^>]*>(.*?)</a>',
                html, re.DOTALL
            )

            sources = {}
            for url, sid, nid, name in play_links:
                name = re.sub(r'<[^>]+>', '', name).strip()
                if sid not in sources:
                    sources[sid] = []
                sources[sid].append((nid, name, url))

            # 3. 按sid排序, 匹配播放源名称
            play_from = []
            play_url = []

            sorted_sids = sorted(sources.keys(), key=lambda x: int(x))
            for i, sid in enumerate(sorted_sids):
                episodes = sources[sid]
                src_name = (
                    play_source_names[i] if i < len(play_source_names)
                    else f"线路{sid}"
                )

                urls = []
                for nid, name, url in episodes:
                    pid_value = f"{vid}|{sid}|{nid}"
                    urls.append(f"{name}${pid_value}")

                if urls:
                    play_from.append(src_name)
                    play_url.append("#".join(urls))

            result["list"] = [{
                "vod_id": str(vid),
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_director": vod_director,
                "vod_actor": vod_actor,
                "vod_year": vod_year,
                "vod_area": vod_area,
                "vod_content": vod_content,
                "vod_remarks": vod_remarks,
                "type_name": vod_type,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }]
        except Exception as e:
            print(f'detailContent error: {e}')
        return result

    # ===== 播放 =====

    # 站点播放器点击脚本 (用于平台URL, 点击iframe内#start按钮启动播放)
    CLICK_JS = 'document.querySelector("#playleft iframe").contentWindow.document.querySelector("#start").click()'

    def playerContent(self, flag, id, vipFlags):
        result = {}
        try:
            # PID格式: vid|sid|nid
            parts = id.split("|")
            if len(parts) >= 3:
                vid, sid, nid = parts[0], parts[1], parts[2]
                play_url = f"/xgplay/{vid}-{sid}-{nid}.html"
            else:
                return result

            html = self._fetch_html(self.host + play_url, timeout=10)
            if not html:
                return result

            # 提取 player_aaaa JSON
            player_data = self._extract_player_aaaa(html)
            if not player_data:
                return result

            url = player_data.get("url", "")
            encrypt = player_data.get("encrypt", 0)
            from_key = player_data.get("from", "")

            # 解密URL
            if encrypt == 1:
                url = urllib.parse.unquote(url)
            elif encrypt == 2:
                try:
                    url = base64.b64decode(url).decode('utf-8')
                    url = urllib.parse.unquote(url)
                except:
                    pass

            if not url:
                return result

            # 判断播放方式
            if re.search(r'\.(m3u8|mp4|flv|ts)(\?|#|$)', url, re.I):
                # 直链m3u8/mp4 → ExoPlayer直接播放
                result["parse"] = 0
                result["url"] = url
                result["header"] = self._play_header
            else:
                # 平台URL (qq/qiyi/youku等) → 使用站点播放页+点击启动
                # 站点xgplay页会通过MacPlayer创建#playleft iframe,
                # iframe加载artplayer解析器, 点击#start按钮启动播放
                result["parse"] = 1
                result["url"] = self.host + play_url
                result["header"] = self._play_header
                result["click"] = self.CLICK_JS

        except Exception as e:
            print(f'playerContent error: {e}')
        return result

    def _extract_player_aaaa(self, html):
        """提取 player_aaaa JSON数据"""
        try:
            # 找到 var player_aaaa = { ... };
            start_idx = html.find('var player_aaaa')
            if start_idx < 0:
                return {}

            brace_start = html.find('{', start_idx)
            if brace_start < 0:
                return {}

            # 逐字符匹配大括号
            depth = 0
            end = brace_start
            in_string = False
            escape = False
            for i in range(brace_start, len(html)):
                c = html[i]
                if escape:
                    escape = False
                    continue
                if c == '\\':
                    escape = True
                    continue
                if c == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break

            raw_json = html[brace_start:end]
            return json.loads(raw_json)
        except Exception as e:
            # 回退: 用正则提取字段
            url_m = re.search(r'"url"\s*:\s*"((?:[^"\\]|\\.)*)"', html)
            from_m = re.search(r'"from"\s*:\s*"([^"]*)"', html)
            enc_m = re.search(r'"encrypt"\s*:\s*(\d+)', html)
            if url_m:
                return {
                    "url": url_m.group(1),
                    "from": from_m.group(1) if from_m else "",
                    "encrypt": int(enc_m.group(1)) if enc_m else 0,
                }
            return {}

    # ===== 搜索 =====

    def searchContent(self, key, quick, pg="1"):
        key = key.strip()
        if not key:
            return {"list": []}

        page = int(pg) if pg else 1
        params = urlencode({
            "mid": "1",
            "wd": key,
            "limit": "20",
            "page": str(page),
        })

        data = self._fetch_json(self.host + f"/index.php/ajax/suggest?{params}")
        videos = []
        for item in data.get("list", []):
            videos.append({
                "vod_id": str(item.get("id", "")),
                "vod_name": item.get("name", ""),
                "vod_pic": item.get("pic", ""),
                "vod_remarks": "",
            })
        return {"list": videos}


if __name__ == "__main__":
    import time

    s = Spider()
    s.init()

    # 1. 首页分类
    print("\n===== 首页分类 =====")
    home = s.homeContent(True)
    print(f"分类数: {len(home.get('class', []))}")
    for c in home["class"]:
        print(f"  [{c['type_id']}] {c['type_name']}")

    # 2. 筛选器
    print("\n===== 筛选器 =====")
    filters = home.get("filters", {})
    for tid, fl in filters.items():
        names = [f["name"] for f in fl]
        print(f"  {tid}: {names}")

    # 3. 首页推荐
    print("\n===== 首页推荐 =====")
    rec = s.homeVideoContent()
    print(f"推荐数: {len(rec.get('list', []))}")
    for v in rec["list"][:5]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    # 4. 分类列表
    print("\n===== 分类列表 (电影第1页) =====")
    t0 = time.time()
    cat = s.categoryContent("dianying", "1", True, {})
    print(f"耗时: {time.time()-t0:.2f}s, 返回: {len(cat.get('list', []))}条")
    for v in cat["list"][:5]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    # 5. 分类分页
    print("\n===== 分类分页 (电影第2页) =====")
    cat2 = s.categoryContent("dianying", "2", True, {})
    print(f"返回: {len(cat2.get('list', []))}条, total={cat2.get('total', 'N/A')}")
    for v in cat2["list"][:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']}")

    # 6. 详情页
    print("\n===== 详情页 =====")
    if cat["list"]:
        test_vid = cat["list"][0]["vod_id"]
        detail = s.detailContent([test_vid])
        if detail["list"]:
            vod = detail["list"][0]
            print(f"  标题: {vod['vod_name']}")
            print(f"  年份: {vod['vod_year']}")
            print(f"  地区: {vod['vod_area']}")
            print(f"  类型: {vod.get('type_name', '')}")
            print(f"  备注: {vod['vod_remarks']}")
            print(f"  导演: {vod['vod_director']}")
            print(f"  演员: {str(vod['vod_actor'])[:80]}")
            print(f"  简介: {str(vod['vod_content'])[:80]}")
            play_from = vod["vod_play_from"].split("$$$")
            play_url = vod["vod_play_url"].split("$$$")
            print(f"  播放源: {' / '.join(play_from)}")
            for i, (name, urls) in enumerate(zip(play_from, play_url)):
                eps = urls.split("#")
                print(f"    [{name}] {len(eps)}集, 第1集: {eps[0][:80]}")

    # 7. 播放
    print("\n===== 播放测试 =====")
    if detail["list"]:
        play_url_parts = detail["list"][0]["vod_play_url"].split("$$$")
        for i, src in enumerate(play_url_parts):
            first_ep = src.split("#")[0]
            ep_title, pid_value = first_ep.split("$", 1)
            play = s.playerContent("", pid_value, [])
            print(f"  源{i+1}: parse={play.get('parse', '')}, url={play.get('url', '')[:80]}, click={'有' if play.get('click') else '无'}")

    # 8. 搜索
    print("\n===== 搜索 (九门) =====")
    t0 = time.time()
    search = s.searchContent("九门", False)
    print(f"耗时: {time.time()-t0:.2f}s, 结果: {len(search.get('list', []))}条")
    for v in search["list"][:10]:
        print(f"  [{v['vod_id']}] {v['vod_name']}")

    print("\n===== 全部测试完成 =====")
