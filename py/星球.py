# -*- coding: utf-8 -*-
"""
==========================================================
  兄弟影视 (www.brovod.com) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎)
  更新: 2026-08-07

  URL规则:
    分类/筛选页: /show/{cat}-{area}-{sort}-{class}-{lang}----{page}---{year}/
      字段(12段, 索引0-11):
        0:cat  1:area  2:sort  3:class  4:lang
        5:letter_start  6:letter_end  7:空
        8:page  9:空  10:空  11:year
    详情页: /detail/{vid}/
    播放页: /play/{vid}-{sid}-{nid}/
    搜索页: /ss/------------{keyword}/

  播放解密:
    1. 播放页内 player_aaaa.url 为emoji加密URL
    2. URL编码后 GET https://play.brovod.com/?url={encoded} 获取 dmkey, pbgjz
    3. key = sha256(str(UTC整点时间戳秒) + "cnmdhb")
    4. POST https://play.brovod.com/JX {url, dmkey, pbgjz, key}
    5. 返回 JSON {code:200, cnmdhb:"m3u8地址", url:"mp4地址"}

  配置方式:
  {
    "sites": [{
      "key": "py_brovod",
      "name": "兄弟影视",
      "type": 3,
      "api": "py_brovod",
      "searchable": 1,
      "quickSearch": 0,
      "filterable": 1,
      "ext": "https://your-host/py_brovod.py"
    }]
  }
==========================================================
"""

import sys
sys.path.append('..')

# 本地调试时模拟 base.spider.Spider 基类
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
import hashlib
import datetime
import urllib.request
import urllib.error
from urllib.parse import quote
from html import unescape as html_unescape

try:
    import concurrent.futures
    _HAS_FUTURES = True
except ImportError:
    _HAS_FUTURES = False


class Spider(Spider):

    HOST = "https://www.brovod.com"
    PLAY_HOST = "https://play.brovod.com"
    UA = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # 分类配置
    CATEGORIES = [
        {"type_name": "电影", "type_id": "Movies"},
        {"type_name": "剧集", "type_id": "TV"},
        {"type_name": "综艺", "type_id": "Shows"},
        {"type_name": "动漫", "type_id": "Anime"},
        {"type_name": "短剧", "type_id": "Snaps"},
        {"type_name": "纪录片", "type_id": "Documentaries"},
    ]

    # 各分类的类型(class)选项
    CLASS_MAP = {
        "Movies": ["喜剧", "爱情", "恐怖", "动作", "科幻", "灾难", "剧情", "战争",
                   "警匪", "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚"],
        "TV": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻",
               "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
        "Shows": ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实",
                  "曲艺", "生活", "游戏互动", "财经", "求职"],
        "Anime": ["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园",
                  "动作", "机战", "运动", "战争", "少年", "少女", "社会", "原创",
                  "亲子", "益智", "励志", "其他"],
        "Snaps": ["爽文", "反转", "都市", "恋爱", "古装", "穿越", "悬疑", "重生"],
        "Documentaries": ["BBC", "Discovery", "历史", "人物", "美食", "节日"],
    }

    # 各分类的地区选项
    AREA_MAP = {
        "Movies": ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
                   "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
        "TV": ["大陆", "香港", "台湾", "美国", "韩国", "日本", "泰国", "英国", "其他"],
        "Shows": ["大陆", "港台", "日韩", "欧美", "日本", "其他"],
        "Anime": ["大陆", "日本", "欧美", "其他"],
        "Snaps": ["大陆"],
        "Documentaries": ["大陆", "美国", "法国", "英国", "其他"],
    }

    # 语言选项 (通用)
    LANG_VALUES = [
        {"n": "全部", "v": ""},
        {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"},
        {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"},
        {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"},
        {"n": "法语", "v": "法语"}, {"n": "德语", "v": "德语"},
        {"n": "其它", "v": "其它"},
    ]

    # 排序选项
    SORT_VALUES = [
        {"n": "按最新", "v": "time"},
        {"n": "按人气", "v": "hits"},
        {"n": "按评分", "v": "score"},
    ]

    def getName(self):
        return "兄弟影视"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": self.UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.HOST + "/",
        }
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

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

    # ==================== 筛选配置 ====================
    def _build_filters(self):
        filters = {}
        year_values = [{"n": "全部", "v": ""}]
        for y in range(2026, 2014, -1):
            year_values.append({"n": str(y), "v": str(y)})

        for cat in self.CATEGORIES:
            cat_id = cat["type_id"]
            class_values = [{"n": "全部", "v": ""}]
            for c in self.CLASS_MAP.get(cat_id, []):
                class_values.append({"n": c, "v": c})

            area_values = [{"n": "全部", "v": ""}]
            for a in self.AREA_MAP.get(cat_id, []):
                area_values.append({"n": a, "v": a})

            filters[cat_id] = [
                {"key": "class", "name": "类型", "value": class_values},
                {"key": "area", "name": "地区", "value": area_values},
                {"key": "year", "name": "年份", "value": year_values},
                {"key": "lang", "name": "语言", "value": self.LANG_VALUES},
                {"key": "sort", "name": "排序", "value": self.SORT_VALUES},
            ]
        return filters

    # ==================== HTTP ====================
    def _fetch(self, url, timeout=15):
        """GET请求, 返回HTML文本"""
        if not url.isascii():
            url = quote(url, safe=":/?&=%-._~")
        try:
            req = urllib.request.Request(url, headers=self.headers)
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=self._ssl_ctx)
            )
            with opener.open(req, timeout=timeout) as r:
                data = r.read()
                return data.decode("utf-8", errors="ignore") if data else ""
        except urllib.error.HTTPError as e:
            try:
                return e.read().decode("utf-8", errors="ignore")
            except:
                return ""
        except Exception:
            return ""

    def _post_json(self, url, data, referer=None, timeout=15):
        """POST请求 (jQuery风格: JSON字符串体 + form-urlencoded Content-Type)"""
        try:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            h = {
                "User-Agent": self.UA,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": referer or (self.PLAY_HOST + "/"),
            }
            req = urllib.request.Request(url, data=body, headers=h, method="POST")
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=self._ssl_ctx)
            )
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", errors="ignore"))
        except Exception:
            return {}

    # ==================== 工具 ====================
    def _fix_pic(self, pic):
        if not pic:
            return ""
        pic = html_unescape(pic)
        if pic.startswith("http"):
            return pic
        if pic.startswith("//"):
            return "https:" + pic
        if not pic.startswith("/"):
            pic = "/" + pic
        return self.HOST + pic

    def _build_show_url(self, cat, extend, page):
        """构建分类筛选URL
        字段(12段): cat, area, sort, class, lang, "", "", "", page, "", "", year
        """
        area = ""
        sort = ""
        cls = ""
        lang = ""
        year = ""
        if extend:
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except:
                    extend = {}
            area = extend.get("area", "") or ""
            sort = extend.get("sort", "") or ""
            cls = extend.get("class", "") or ""
            lang = extend.get("lang", "") or ""
            year = extend.get("year", "") or ""

        fields = [
            str(cat), quote(area, safe=""), sort, quote(cls, safe=""),
            quote(lang, safe=""), "", "", "", str(page), "", "", year
        ]
        return "/show/" + "-".join(fields) + "/"

    # ==================== 列表解析 ====================
    def _parse_list(self, html):
        """解析视频列表卡片
        卡片结构:
          <a class="public-list-exp" href="/detail/vid" title="标题">
            <img ... data-src="封面URL" />
            <span class="public-list-prb ...">备注</span>
          </a>
        也兼容首页轮播:
          <a href="/detail/vid">
            <h3 class="slide-info-title">标题</h3>
            <span class="slide-info-remarks">备注</span>
          </a>
        """
        items = []
        seen = set()
        # 匹配所有含 /detail/ 链接的 <a> 标签
        pattern = re.compile(
            r'<a[^>]*href="(/detail/[^"]+)"[^>]*>(.*?)</a>',
            re.S
        )
        for m in pattern.finditer(html):
            vid_path = m.group(1)
            full_tag = m.group(0)
            content = m.group(2)
            # 提取vid
            vid_m = re.match(r'/detail/([^/]+)/', vid_path)
            if not vid_m:
                continue
            vid = vid_m.group(1)
            if vid in seen:
                continue

            # 标题: 优先 title= 属性, 其次 alt= (去封面图后缀), 再次各class
            title = ""
            tm = re.search(r'title="([^"]+)"', full_tag)
            if tm:
                title = tm.group(1).strip()
            if not title:
                tm = re.search(r'slide-info-title[^>]*>([^<]+)<', content)
                if tm:
                    title = tm.group(1).strip()
            if not title:
                tm = re.search(r'time-title[^>]*>([^<]+)<', content)
                if tm:
                    title = tm.group(1).strip()
            if not title:
                # 搜索页: alt="标题封面图"
                tm = re.search(r'alt="([^"]+)封面图"', content)
                if tm:
                    title = tm.group(1).strip()
            if not title:
                # 搜索页: thumb-txt 内的链接文本 (在a标签外的兄弟元素中)
                # 扩大搜索范围到a标签后500字符
                end_pos = m.end()
                after_text = html[end_pos:end_pos + 500]
                tm = re.search(r'thumb-txt[^>]*>\s*<a[^>]*>([^<]+)<', after_text)
                if tm:
                    title = tm.group(1).strip()
            if not title:
                continue

            seen.add(vid)

            # 封面
            pic = ""
            pm = re.search(r'data-src="([^"]+)"', content)
            if not pm:
                pm = re.search(r'data-original="([^"]+)"', content)
            if not pm:
                pm = re.search(r'background-image:\s*url\([\'"]([^\'"]+)[\'"]\)', content)
            if not pm:
                pm = re.search(r'<img[^>]+src="([^"]+)"', content)
            if pm:
                pic_url = pm.group(1)
                # 跳过 base64 占位图
                if not pic_url.startswith("data:"):
                    pic = self._fix_pic(pic_url)

            # 备注
            remark = ""
            rm = re.search(r'public-list-prb[^>]*>([^<]+)<', content)
            if rm:
                remark = rm.group(1).strip()
            if not remark:
                remarks = re.findall(r'slide-info-remarks[^>]*>([^<]+)<', content)
                if remarks:
                    remark = " ".join(r.strip() for r in remarks if r.strip())

            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return items

    # ==================== 首页 ====================
    def homeContent(self, filter):
        result = {}
        classes = []
        for c in self.CATEGORIES:
            classes.append({"type_name": c["type_name"], "type_id": c["type_id"]})
        result["class"] = classes
        result["filters"] = self._build_filters()
        html = self._fetch(self.HOST + "/")
        if html:
            result["list"] = self._parse_list(html)
        return result

    def homeVideoContent(self):
        result = {"list": []}
        html = self._fetch(self.HOST + "/")
        if html:
            result["list"] = self._parse_list(html)[:24]
        return result

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 30, "total": 0}
        try:
            page = int(pg) if pg else 1
        except:
            page = 1
        if page < 1:
            page = 1
        result["page"] = page

        path = self._build_show_url(tid, extend, page)
        html = self._fetch(self.HOST + path, )
        if not html:
            return result

        items = self._parse_list(html)
        result["list"] = items
        result["limit"] = len(items)

        # 分页: 查找总页数
        page_m = re.search(r'(\d+)\s*/\s*(\d+)\s*页', html)
        if page_m:
            result["pagecount"] = int(page_m.group(2))
            result["total"] = int(page_m.group(2)) * len(items)
        else:
            # 如果有下一页链接, 设大值; 否则当前页
            next_m = re.search(
                r'href="(/show/' + re.escape(tid) + r'[^"]*-' + str(page + 1) + r'---/)"',
                html
            )
            result["pagecount"] = 9999 if next_m else page
            result["total"] = 9999 if next_m else len(items)
        return result

    # ==================== 源可播放性检测 ====================
    def _is_source_playable(self, first_ep_path):
        """快速测试单个源是否可播放 (只测第一集)
        返回 True/False
        """
        try:
            play_url = self.HOST + first_ep_path
            html = self._fetch(play_url, timeout=8)
            if not html:
                return False
            m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', html, re.S)
            if not m:
                return False
            player = json.loads(m.group(1))
            emoji_url = player.get("url", "")
            if not emoji_url:
                return False
            # 直接URL视为可播放
            if emoji_url.startswith("http") and (".m3u8" in emoji_url or ".mp4" in emoji_url):
                return True
            # 完整解密测试
            encoded_url = quote(emoji_url, safe="")
            play_page_url = self.PLAY_HOST + "/?url=" + encoded_url
            play_html = self._fetch(play_page_url, timeout=8)
            if not play_html:
                return False
            dmkey = ""
            m = re.search(r'"dmkey"\s*:\s*"([^"]+)"', play_html)
            if m:
                dmkey = m.group(1)
            if not dmkey:
                return False
            pbgjz = ""
            m = re.search(r'"pbgjz"\s*:\s*"([^"]*)"', play_html)
            if m:
                pbgjz = m.group(1)
            # 生成key
            now = datetime.datetime.now(datetime.timezone.utc)
            hour_start = now.replace(minute=0, second=0, microsecond=0)
            ts_sec = int(hour_start.timestamp())
            key = hashlib.sha256((str(ts_sec) + "cnmdhb").encode("utf-8")).hexdigest()
            # POST解密
            post_data = {"url": encoded_url, "pbgjz": pbgjz, "dmkey": dmkey, "key": key}
            result = self._post_json(self.PLAY_HOST + "/JX", post_data, referer=play_page_url, timeout=8)
            return bool(result and result.get("code") == 200 and (result.get("cnmdhb") or result.get("url")))
        except Exception:
            return False

    def _filter_playable_sources(self, play_from_list, play_url_parts):
        """并行测试各源可播放性, 过滤掉不可播放的源
        返回 (filtered_from, filtered_url) 或 None (如果全部不可播放则返回None, 由调用方保留全部)
        """
        if not play_from_list or len(play_from_list) <= 1:
            return None

        # 提取每个源的第一集路径
        first_eps = []
        for part in play_url_parts:
            first_ep = part.split("#")[0] if "#" in part else part
            path = ""
            if "$" in first_ep:
                path = first_ep.split("$")[1]
            first_eps.append(path)

        # 并行测试
        results = [False] * len(play_from_list)
        if _HAS_FUTURES:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_map = {executor.submit(self._is_source_playable, ep): i for i, ep in enumerate(first_eps) if ep}
                for future in concurrent.futures.as_completed(future_map, timeout=30):
                    idx = future_map[future]
                    try:
                        results[idx] = future.result()
                    except Exception:
                        results[idx] = False
        else:
            # 串行回退
            for i, ep in enumerate(first_eps):
                if ep:
                    results[i] = self._is_source_playable(ep)

        # 过滤
        filtered_from = []
        filtered_url = []
        for i, ok in enumerate(results):
            if ok:
                filtered_from.append(play_from_list[i])
                filtered_url.append(play_url_parts[i])

        # 如果全部不可播放, 返回None (保留全部源作为回退)
        if not filtered_from:
            return None
        return filtered_from, filtered_url

    # ==================== 详情 ====================
    def detailContent(self, ids):
        result = {"list": []}
        if not ids:
            return result
        vid = ids[0]
        url = self.HOST + "/detail/" + vid + "/"
        html = self._fetch(url)
        if not html:
            return result

        vod = {
            "vod_id": vid,
            "vod_name": "",
            "vod_pic": "",
            "vod_year": "",
            "vod_area": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_remarks": "",
            "vod_play_from": "",
            "vod_play_url": "",
        }

        # 标题: <h3>标题</h3>
        m = re.search(r'<h3[^>]*>([^<]+)</h3>', html)
        if m:
            vod["vod_name"] = m.group(1).strip()
        if not vod["vod_name"]:
            m = re.search(r'<title>《([^》]+)》', html)
            if m:
                vod["vod_name"] = m.group(1).strip()

        # 封面: 第一个非base64的data-src图片
        for pm in re.finditer(r'data-src="([^"]+)"', html):
            pic_url = pm.group(1)
            if not pic_url.startswith("data:"):
                vod["vod_pic"] = self._fix_pic(pic_url)
                break
        if not vod["vod_pic"]:
            pm = re.search(r'background-image:\s*url\([\'"]([^\'"]+)[\'"]\)', html)
            if pm:
                vod["vod_pic"] = self._fix_pic(pm.group(1))

        # 信息标签: <li><em class="cor4">标签：</em>值</li>
        info_items = re.findall(
            r'<em class="cor4">([^：:]+)[：:]\s*</em>(.*?)(?:</li>|<em)',
            html, re.S
        )
        for label, content in info_items:
            label = label.strip()
            if label in ("主演", "导演"):
                # 从 <a> 标签提取人名, 过滤空值
                names = re.findall(r'>([^<]+)</a>', content)
                names = [n.strip() for n in names if n.strip()]
                text = ", ".join(names)
            else:
                text = re.sub(r'<[^>]+>', '', content).strip()
                text = re.sub(r'\s*&nbsp;\s*', ' ', text).strip()
                text = re.sub(r'\s+', ' ', text).strip()
            if not text or text == "未知":
                continue
            if label == "片名" and not vod["vod_name"]:
                vod["vod_name"] = text
            elif label == "状态":
                vod["vod_remarks"] = text
            elif label == "年份":
                vod["vod_year"] = text
            elif label == "地区":
                vod["vod_area"] = text
            elif label == "主演":
                vod["vod_actor"] = text
            elif label == "导演":
                vod["vod_director"] = text
            elif label == "简介":
                vod["vod_content"] = text

        # 备用: 从 slide-info 提取导演/演员
        if not vod["vod_director"]:
            m = re.search(r'<strong class="r6">导演\s*:</strong>(.*?)(?:</div>|<strong)', html, re.S)
            if m:
                names = [n.strip() for n in re.findall(r'>([^<]+)</a>', m.group(1)) if n.strip()]
                vod["vod_director"] = ", ".join(names)
        if not vod["vod_actor"]:
            m = re.search(r'<strong class="r6">演员\s*:</strong>(.*?)(?:</div>|<strong)', html, re.S)
            if m:
                names = [n.strip() for n in re.findall(r'>([^<]+)</a>', m.group(1)) if n.strip()]
                vod["vod_actor"] = ", ".join(names)

        # 播放源解析
        # 源名称: <a class="swiper-slide">源名</a>
        source_names = []
        for sm in re.finditer(r'<a class="swiper-slide"[^>]*>(.*?)</a>', html, re.S):
            name = re.sub(r'<[^>]+>', '', sm.group(1))
            name = html_unescape(name).strip()  # 解码 &nbsp; 等HTML实体
            # 去除尾部的集数数字 (如 "蓝光①8" -> "蓝光①")
            name = re.sub(r'\d+$', '', name).strip()
            if name:
                source_names.append(name)

        # 各源的剧集列表: anthology-list-box 块
        source_blocks = re.findall(
            r'<div class="anthology-list-box[^"]*">(.*?)</div>\s*</div>',
            html, re.S
        )

        play_from_list = []
        play_url_parts = []
        for i, block in enumerate(source_blocks):
            episodes = re.findall(
                r'href="(/play/[^"]+)"[^>]*>([^<]+)<',
                block
            )
            if not episodes:
                continue
            # 源名称
            src_name = source_names[i] if i < len(source_names) else f"线路{i+1}"
            play_from_list.append(src_name)

            parts = []
            for ep_path, ep_name in episodes:
                ep_name = ep_name.strip()
                if not ep_name:
                    continue
                parts.append(f"{ep_name}${ep_path}")
            if parts:
                play_url_parts.append("#".join(parts))

        # 如果没找到播放源, 尝试直接匹配所有播放链接
        if not play_url_parts:
            all_plays = re.findall(r'href="(/play/[^"]+)"[^>]*>([^<]+)<', html)
            if all_plays:
                parts = []
                for ep_path, ep_name in all_plays:
                    ep_name = ep_name.strip()
                    if ep_name:
                        parts.append(f"{ep_name}${ep_path}")
                if parts:
                    play_from_list.append("默认线路")
                    play_url_parts.append("#".join(parts))

        # 过滤不可播放的线路 (并行测试各源第一集)
        if play_from_list:
            playable = self._filter_playable_sources(play_from_list, play_url_parts)
            if playable:
                play_from_list, play_url_parts = playable

        vod["vod_play_from"] = "$$$".join(play_from_list)
        vod["vod_play_url"] = "$$$".join(play_url_parts)

        result["list"] = [vod]
        return result

    # ==================== 搜索 ====================
    def searchContent(self, key, quick):
        keyword = quote(key)
        # 搜索URL: /ss/{keyword}-------------/  (14段, 关键词在第1段)
        url = self.HOST + "/ss/" + keyword + "-------------/"
        html = self._fetch(url)
        if not html:
            return {"list": []}
        return {"list": self._parse_list(html)}

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        """播放解密:
        1. 访问播放页获取 player_aaaa.url (emoji加密URL)
        2. 访问 play.brovod.com 获取 dmkey, pbgjz
        3. 生成 hourly key
        4. POST 解密获取真实URL
        """
        # 构建播放页URL
        if id.startswith("http"):
            play_url = id
        elif id.startswith("/play/"):
            play_url = self.HOST + id
        else:
            play_url = self.HOST + "/play/" + id + "/"

        # 1. 获取播放页, 提取 player_aaaa
        html = self._fetch(play_url)
        result_url = ""
        if html:
            m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', html, re.S)
            if m:
                try:
                    player = json.loads(m.group(1))
                    emoji_url = player.get("url", "")
                    encrypt = player.get("encrypt", 0)

                    if emoji_url:
                        # 检查是否已经是直接URL
                        if emoji_url.startswith("http") and (".m3u8" in emoji_url or ".mp4" in emoji_url):
                            result_url = emoji_url
                        else:
                            # 2. 获取 dmkey, pbgjz
                            result_url = self._decrypt(emoji_url)
                except (json.JSONDecodeError, KeyError):
                    pass

            # 备用: 直接在播放页搜索m3u8/mp4
            if not result_url:
                m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
                if m:
                    result_url = m.group(1)
            if not result_url:
                m = re.search(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html)
                if m:
                    result_url = m.group(1)

        return {
            "parse": 0,
            "playUrl": "",
            "url": result_url,
            "header": json.dumps({
                "User-Agent": self.UA,
                "Referer": self.PLAY_HOST + "/",
            }),
        }

    def _decrypt(self, emoji_url):
        """emoji URL 解密

        流程:
          1. URL编码 emoji URL
          2. GET play.brovod.com/?url=<encoded> 获取 dmkey, pbgjz
          3. key = sha256(str(UTC整点时间戳秒) + "cnmdhb")
          4. POST play.brovod.com/JX {url, pbgjz, dmkey, key}
          5. 返回 cnmdhb 字段 (m3u8地址)
        """
        # 1. URL编码 emoji URL
        encoded_url = quote(emoji_url, safe="")

        # 2. 获取 dmkey, pbgjz
        play_page_url = self.PLAY_HOST + "/?url=" + encoded_url
        play_html = self._fetch(play_page_url)
        if not play_html:
            return ""

        dmkey = ""
        pbgjz = ""
        m = re.search(r'"dmkey"\s*:\s*"([^"]+)"', play_html)
        if m:
            dmkey = m.group(1)
        m = re.search(r'"pbgjz"\s*:\s*"([^"]*)"', play_html)
        if m:
            pbgjz = m.group(1)

        if not dmkey:
            return ""

        # 3. 生成 key = sha256(str(UTC整点时间戳秒) + "cnmdhb")
        now = datetime.datetime.now(datetime.timezone.utc)
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        ts_sec = int(hour_start.timestamp())
        key_base = str(ts_sec) + "cnmdhb"
        key = hashlib.sha256(key_base.encode("utf-8")).hexdigest()

        # 4. POST 解密
        post_data = {
            "url": encoded_url,
            "pbgjz": pbgjz,
            "dmkey": dmkey,
            "key": key,
        }
        result = self._post_json(self.PLAY_HOST + "/JX", post_data, referer=play_page_url)
        if result and result.get("code") == 200:
            # 优先返回 cnmdhb 字段 (m3u8地址), 回退到 url 字段
            return result.get("cnmdhb", "") or result.get("url", "")
        return ""

    def localProxy(self, param):
        action = {
            'url': '',
            'header': '',
            'param': '',
            'type': 'string',
            'after': ''
        }
        return [200, "video/MP2T", action, ""]
