# -*- coding: utf-8 -*-
"""
==========================================================
  凡客影视 / 凡客TV (m.fktv.me) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎)
  更新: 2026-09-19

  站点技术: Next.js (RSC 服务端渲染) + AES 加密 API
  ------------------------------------------------
  列表 / 搜索: 服务端渲染 HTML, 电影数据内嵌在 self.__next_f RSC 中
  详情 / 播放: POST /ysapi/movie/detail (请求与响应均为 AES-128-ECB 加密)
     - 密钥(apiKey): 9ed1a661a6ab787a  (16字节, ECB, PKCS7)
     - 请求体: JSON{deviceId,token,domain,user_agent,...,data:{id,link_id,is_simple}}
     - 响应体: 同密钥 AES 解密后得到 JSON{status,data:{...,links:[{id,name}],playback_v2}}
  播放直链: playback_v2.video_lines 为双线路 (cn=国内线路 /m3c, vip=海外线路 /m3v),
           各自带签名 m3u8 路径, 经本站同源代理 https://m.fktv.me + path 直出
  筛选分页: /channel/filter/year/{y}/language/{l}/position/{slug}/order/{o}/page/{p}
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
import os
import json
import ssl
import time
import base64
import urllib.request
import urllib.error
import urllib.parse
from html import unescape as html_unescape


# ============================================================
#  纯 Python AES-128-ECB 实现 (避免依赖 pycryptodome)
#  已与 pycryptodome 输出逐字节验证一致
# ============================================================
def _gf_mul(a, b):
    p = 0
    a &= 0xFF
    b &= 0xFF
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x1B
        b >>= 1
    return p & 0xFF


def _gf_inv(a):
    if a == 0:
        return 0
    r = 1
    base = a
    e = 254
    while e:
        if e & 1:
            r = _gf_mul(r, base)
        base = _gf_mul(base, base)
        e >>= 1
    return r


def _rotl8(x, n):
    n &= 7
    return ((x << n) | (x >> (8 - n))) & 0xFF


def _sbox_byte(x):
    x = _gf_inv(x)
    return x ^ _rotl8(x, 1) ^ _rotl8(x, 2) ^ _rotl8(x, 3) ^ _rotl8(x, 4) ^ 0x63


_SBOX = [_sbox_byte(i) for i in range(256)]
_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]


def _key_expansion(key):
    Nk = 4
    Nr = 10
    w = [list(key[4 * i:4 * i + 4]) for i in range(Nk)]
    for i in range(Nk, 4 * (Nr + 1)):
        t = list(w[i - 1])
        if i % Nk == 0:
            t = t[1:] + t[:1]
            t = [_SBOX[x] for x in t]
            t[0] ^= _RCON[i // Nk - 1]
        w.append([w[i - Nk][j] ^ t[j] for j in range(4)])
    return w


def _aes_block(block, rk):
    s = [[block[r + 4 * c] for c in range(4)] for r in range(4)]
    Nr = 10

    def ark(st, r):
        for c in range(4):
            for rr in range(4):
                st[rr][c] ^= rk[r * 4 + c][rr]

    ark(s, 0)
    for rnd in range(1, Nr):
        for r in range(4):
            for c in range(4):
                s[r][c] = _SBOX[s[r][c]]
        s[1] = s[1][1:] + s[1][:1]
        s[2] = s[2][2:] + s[2][:2]
        s[3] = s[3][3:] + s[3][:3]
        for c in range(4):
            a = [s[r][c] for r in range(4)]
            s[0][c] = _gf_mul(a[0], 2) ^ _gf_mul(a[1], 3) ^ a[2] ^ a[3]
            s[1][c] = a[0] ^ _gf_mul(a[1], 2) ^ _gf_mul(a[2], 3) ^ a[3]
            s[2][c] = a[0] ^ a[1] ^ _gf_mul(a[2], 2) ^ _gf_mul(a[3], 3)
            s[3][c] = _gf_mul(a[0], 3) ^ a[1] ^ a[2] ^ _gf_mul(a[3], 2)
        ark(s, rnd)
    for r in range(4):
        for c in range(4):
            s[r][c] = _SBOX[s[r][c]]
    s[1] = s[1][1:] + s[1][:1]
    s[2] = s[2][2:] + s[2][:2]
    s[3] = s[3][3:] + s[3][:3]
    ark(s, Nr)
    return bytes(s[r][c] for c in range(4) for r in range(4))


def aes_ecb_encrypt(plain: bytes, key: bytes) -> bytes:
    rk = _key_expansion(key)
    padlen = 16 - (len(plain) % 16) or 16
    plain = plain + bytes([padlen]) * padlen
    return b''.join(_aes_block(plain[i:i + 16], rk) for i in range(0, len(plain), 16))


# 逆 S 盒
_INV_SBOX = [0] * 256
for _i in range(256):
    _INV_SBOX[_SBOX[_i]] = _i


def _inv_shift_rows(s):
    s[1] = s[1][-1:] + s[1][:-1]        # 右移 1
    s[2] = s[2][-2:] + s[2][:-2]        # 右移 2
    s[3] = s[3][-3:] + s[3][:-3]        # 右移 3


def _inv_mix_columns(s):
    for c in range(4):
        a = [s[r][c] for r in range(4)]
        s[0][c] = _gf_mul(a[0], 14) ^ _gf_mul(a[1], 11) ^ _gf_mul(a[2], 13) ^ _gf_mul(a[3], 9)
        s[1][c] = _gf_mul(a[0], 9) ^ _gf_mul(a[1], 14) ^ _gf_mul(a[2], 11) ^ _gf_mul(a[3], 13)
        s[2][c] = _gf_mul(a[0], 13) ^ _gf_mul(a[1], 9) ^ _gf_mul(a[2], 14) ^ _gf_mul(a[3], 11)
        s[3][c] = _gf_mul(a[0], 11) ^ _gf_mul(a[1], 13) ^ _gf_mul(a[2], 9) ^ _gf_mul(a[3], 14)


def _aes_block_decrypt(cipher, rk):
    s = [[cipher[r + 4 * c] for c in range(4)] for r in range(4)]
    Nr = 10

    def ark(st, r):
        for c in range(4):
            for rr in range(4):
                st[rr][c] ^= rk[r * 4 + c][rr]

    ark(s, Nr)
    for rnd in range(Nr - 1, 0, -1):
        _inv_shift_rows(s)
        for r in range(4):
            for c in range(4):
                s[r][c] = _INV_SBOX[s[r][c]]
        ark(s, rnd)                 # 先加轮密钥
        _inv_mix_columns(s)         # 再逆列混合
    _inv_shift_rows(s)
    for r in range(4):
        for c in range(4):
            s[r][c] = _INV_SBOX[s[r][c]]
    ark(s, 0)
    return bytes(s[r][c] for c in range(4) for r in range(4))


def aes_ecb_decrypt(cipher: bytes, key: bytes) -> bytes:
    rk = _key_expansion(key)
    out = b''.join(_aes_block_decrypt(cipher[i:i + 16], rk) for i in range(0, len(cipher), 16))
    # 去除 PKCS7 填充
    if out and 1 <= out[-1] <= 16:
        out = out[:-out[-1]]
    return out


class Spider(Spider):

    HOST = "https://m.fktv.me"
    UA = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    API_BASE = "/ysapi"                       # 实际请求: HOST + /ysapi/{path}
    API_KEY = "9ed1a661a6ab787a"              # AES-128 密钥 (16字节)

    # 导航分类 (来自站点导航栏 channel slug)
    CATEGORIES = [
        {"type_name": "电影", "type_id": "movie"},
        {"type_name": "电视剧", "type_id": "tv"},
        {"type_name": "动漫", "type_id": "comic"},
        {"type_name": "综艺", "type_id": "zy"},
        {"type_name": "短剧", "type_id": "short_tv"},
        {"type_name": "纪录片", "type_id": "jlp"},
        {"type_name": "电影解说", "type_id": "js"},
    ]

    # 筛选选项 (实测 /channel/filter/... 路径式筛选, 年份 1970-2026 全有效)
    FILTER_YEARS = ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
                    "2018", "2017", "2016", "2015", "2010", "2005", "2000", "1995",
                    "1990", "1985", "1980", "1975", "1970"]
    FILTER_LANGS = ["国语", "粤语", "英语", "韩语", "日语", "泰语", "法语", "德语", "其它"]
    FILTER_ORDERS = [("最新", "new"), ("最热", "hot")]

    # 播放线路 (playback_v2.video_lines): cn=国内线路, vip=海外线路
    DEFAULT_LINES = [("cn", "国内线路"), ("vip", "海外线路")]

    def getName(self):
        return "凡客影视"

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

    # ==================== AES 加密 API ====================
    def _api_post(self, path, data):
        """调用 /ysapi/{path}, 请求体与响应体均为 AES-128-ECB 加密
        返回解密后的 JSON dict (含 status / data)
        """
        key = self.API_KEY.encode("utf-8")
        payload = {
            "deviceId": os.urandom(16).hex(),
            "token": "",
            "domain": "m.fktv.me",
            "referer": "",
            "user_agent": self.UA,
            "shareCode": "",
            "channel": "",
            "ip": "",
            "data": data,
        }
        body = base64.b64encode(
            aes_ecb_encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8"), key)
        ).decode("ascii")

        now = time.strftime("%Y-%m-%d %H:%M:%S")
        headers = {
            "version": "1.0",
            "deviceType": "h5",
            "time": now,
            "shareCode": "",
            "channel": "",
            "ip": "",
            "Content-Type": "application/octet-stream",
            "User-Agent": self.UA,
            "Origin": self.HOST,
            "Referer": self.HOST + "/",
        }
        url = self.HOST + self.API_BASE + "/" + path
        req = urllib.request.Request(url, data=body.encode("utf-8"), headers=headers, method="POST")
        try:
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=self._ssl_ctx)
            )
            with opener.open(req, timeout=30) as r:
                resp = r.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:
            try:
                resp = e.read().decode("utf-8", errors="ignore")
            except Exception:
                return {}
        except Exception as e:
            print("api_post error: {0}".format(e))
            return {}

        resp = resp.strip()
        if resp.startswith("{") or resp.startswith("["):
            try:
                return json.loads(resp)
            except Exception:
                return {}
        # 加密响应 -> 解密
        try:
            plain = aes_ecb_decrypt(base64.b64decode(resp), key).decode("utf-8", errors="ignore")
            return json.loads(plain)
        except Exception as e:
            print("api decrypt error: {0}".format(e))
            return {}

    # ==================== HTTP GET (HTML) ====================
    def _fetch(self, url, headers=None, timeout=15, data=None):
        hdr = headers or self.headers
        if not url.isascii():
            url = urllib.parse.quote(url, safe=":/?&=%-._~")
        try:
            req = urllib.request.Request(url, headers=hdr)
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=self._ssl_ctx)
            )
            with opener.open(req, timeout=timeout) as r:
                d = r.read()
                return d.decode("utf-8", errors="ignore") if d else ""
        except urllib.error.HTTPError as e:
            try:
                return e.read().decode("utf-8", errors="ignore")
            except Exception:
                return ""
        except Exception as e:
            print("_fetch error: {0}".format(e))
            return ""

    # ==================== RSC 解析工具 ====================
    @staticmethod
    def _extract_rsc(html):
        """提取 self.__next_f.push([1,"..."]) 中的内嵌 JSON 字符串并还原转义"""
        out = []
        for m in re.finditer(r'self\.__next_f\.push\(\[1,\s*("(?:[^"\\]|\\.)*")', html):
            try:
                out.append(json.loads(m.group(1)))
            except Exception:
                pass
        return "\n".join(out)

    @staticmethod
    def _clean_url(url):
        """清洗站点反爬混淆: CDN 图片 URL 中会随机插入换行/空格字符,
        如 'https://c\\ndn.xxx.com/...', 必须去掉所有空白符才能正常显示"""
        if not url:
            return ""
        return re.sub(r"\s+", "", url)

    @staticmethod
    def _build_poster_map(rsc):
        """从 RSC 构建 id -> img_x_source(海报) 映射"""
        m = {}
        for mid in re.finditer(r'"id":"([0-9a-f]{16})"', rsc):
            vid = mid.group(1)
            if vid in m:
                continue
            window = rsc[mid.end():mid.end() + 1600]
            im = re.search(r'"img_x_source":"([^"]+)"', window)
            if im:
                m[vid] = Spider._clean_url(im.group(1))
        return m

    # ==================== 列表解析 ====================
    def _parse_list(self, html, rsc=None):
        """解析影片列表卡片 (凡客TV: <li class="movieCover"> 或搜索页 <a href="/movie/{id}/{slug}">)
        返回 [{vod_id, vod_name, vod_pic, vod_remarks}]
        """
        if rsc is None:
            rsc = self._extract_rsc(html)
        poster_map = self._build_poster_map(rsc)

        items = []
        seen = set()

        # 优先解析 movieCover 卡片
        card_re = re.compile(r'<li class="movieCover[^"]*">.*?</li>', re.S)
        anchors = []
        for card in card_re.finditer(html):
            am = re.search(r'<a\b[^>]*href="(/movie/([0-9a-f]{16})/([a-z0-9-]+))"[^>]*>', card.group(0))
            if am:
                anchors.append((am.group(0), am.group(2), am.group(3), card.group(0)))

        # 兜底: 直接扫描所有 /movie/{id}/{slug} 链接 (搜索页使用)
        if not anchors:
            for am in re.finditer(
                    r'<a\b[^>]*href="(/movie/([0-9a-f]{16})/([a-z0-9-]+))"[^>]*>', html):
                anchors.append((am.group(0), am.group(2), am.group(3), html[max(0, am.start() - 50):am.end() + 400]))

        for anchor_tag, vid, slug, region in anchors:
            if vid in seen:
                continue
            # 标题
            title = ""
            tm = re.search(r'\btitle="([^"]+)"', anchor_tag)
            if tm:
                title = html_unescape(tm.group(1)).strip()
            if not title:
                sm = re.search(r'<span[^>]*class="[^"]*truncate[^"]*"[^>]*>([^<]+)</span>', region)
                if sm:
                    title = html_unescape(sm.group(1)).strip()
            if not title:
                hm = re.search(r'<h2[^>]*>([^<]+)</h2>', region)
                if hm:
                    title = html_unescape(hm.group(1)).strip()
            if not title:
                continue
            if title in ("更多", "换一换", "立即播放"):
                continue

            seen.add(vid)
            pic = poster_map.get(vid, "")
            # 年份/备注徽标
            remark = ""
            ym = re.search(r'class="left[^"]*">([^<]+)<', region)
            if ym:
                remark = ym.group(1).strip()
            # 分类副标题
            if not remark:
                cm = re.search(r'class="subtitle[^"]*">([^<]+)<', region)
                if cm:
                    remark = cm.group(1).strip()

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
        try:
            classes = [{"type_name": c["type_name"], "type_id": c["type_id"]} for c in self.CATEGORIES]
            result["class"] = classes
            if filter:
                result["filters"] = self._build_filters()

            html = self._fetch(self.HOST + "/")
            if html:
                rsc = self._extract_rsc(html)
                result["list"] = self._parse_list(html, rsc)
        except Exception as e:
            print("homeContent error: {0}".format(e))
        return result

    def _build_filters(self):
        """每个分类提供 年份/语言/排序 筛选 (走 /channel/filter 路径式筛选)"""
        year_values = [{"n": "全部", "v": ""}]
        year_values += [{"n": y, "v": y} for y in self.FILTER_YEARS]
        lang_values = [{"n": "全部", "v": ""}]
        lang_values += [{"n": l, "v": l} for l in self.FILTER_LANGS]
        order_values = [{"n": "综合排序", "v": ""}]
        order_values += [{"n": n_, "v": v} for n_, v in self.FILTER_ORDERS]

        filters = {}
        for c in self.CATEGORIES:
            filters[c["type_id"]] = [
                {"key": "year", "name": "年份", "value": year_values},
                {"key": "language", "name": "语言", "value": lang_values},
                {"key": "order", "name": "排序", "value": order_values},
            ]
        return filters

    def homeVideoContent(self):
        pass

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        """筛选/分页走站点通用筛选路由:
        /channel/filter/year/{y}/language/{l}/position/{tid}/order/{o}/page/{p}
        (各段可省略; 实测分页有效, 每页约 32 条)
        """
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 32, "total": 9999}
        try:
            page = int(pg) if pg and int(pg) >= 1 else 1
            ext = {}
            if isinstance(extend, dict):
                ext = extend
            elif extend:
                try:
                    ext = json.loads(extend)
                except Exception:
                    ext = {}

            segs = []
            year = str(ext.get("year") or "").strip()
            lang = str(ext.get("language") or "").strip()
            order = str(ext.get("order") or "").strip()
            if year:
                segs += ["year", year]
            if lang:
                segs += ["language", urllib.parse.quote(lang, safe="")]
            segs += ["position", str(tid)]
            if order:
                segs += ["order", order]
            segs += ["page", str(page)]

            url = self.HOST + "/channel/filter/" + "/".join(segs)
            html = self._fetch(url)
            if html:
                rsc = self._extract_rsc(html)
                result["list"] = self._parse_list(html, rsc)
            # 翻页策略: 当前页满页(>=30条)则还有下一页
            result["page"] = page
            result["pagecount"] = page + 1 if len(result["list"]) >= 30 else page
        except Exception as e:
            print("categoryContent error: {0}".format(e))
        return result

    # ==================== 详情 ====================
    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            # 直接走 AES API, 无需 slug, 返回完整元数据 + 集数 links
            res = self._api_post("movie/detail", {"id": vod_id, "is_simple": "n"})
            if not res or res.get("status") != "y":
                return result
            d = res.get("data", {})
            if not d:
                return result

            title = d.get("name") or d.get("title") or ""
            pic = self._clean_url(d.get("img_x_source") or d.get("img_y_source") or "")
            actor = d.get("actor") or ""
            director = d.get("director") or ""
            area = d.get("area") or ""
            vod_class = d.get("child_title") or d.get("category") or d.get("categories") or ""
            lang = d.get("language") or ""
            year = str(d.get("release_at") or "").strip()
            score = d.get("score") or ""
            desc = d.get("description") or ""

            # 线路: 从 playback_v2.video_lines 取实际线路列表 (cn=国内线路, vip=海外线路)
            lines = []
            pb = d.get("playback_v2") or {}
            for vl in pb.get("video_lines") or []:
                lk = str(vl.get("line") or "").strip()
                ln = str(vl.get("name") or "").strip()
                if lk:
                    lines.append((lk, ln or lk))
            if not lines:
                lines = list(self.DEFAULT_LINES)

            # 集数 -> 每条线路各生成一份 (播放地址带线路标记 /l/{movie_id}/{link_id}/{line})
            links = d.get("links") or []
            play_from_list = []
            play_url_list = []
            for line_key, line_name in lines:
                episodes = []
                for ep in links:
                    ep_id = ep.get("id", "")
                    ep_name = ep.get("name", "") or "第" + str(len(episodes) + 1) + "集"
                    episodes.append(ep_name + "$/l/" + str(vod_id) + "/" + str(ep_id) + "/" + line_key)
                if episodes:
                    play_from_list.append(line_name)
                    play_url_list.append("#".join(episodes))

            result["list"].append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "type_name": vod_class,
                "vod_year": year,
                "vod_area": area,
                "vod_lang": lang,
                "vod_remarks": score,
                "vod_actor": actor,
                "vod_director": director,
                "vod_content": desc,
                "vod_play_from": "$$$".join(play_from_list),
                "vod_play_url": "$$$".join(play_url_list),
            })
        except Exception as e:
            print("detailContent error: {0}".format(e))
        return result

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            page = int(pg) if int(pg) >= 1 else 1
            # 真实搜索: /channel?keywords=xxx (站点前端搜索即跳转到该地址)
            search_path = "/channel?keywords=" + urllib.parse.quote(key, safe="")
            html = self._fetch(self.HOST + search_path)
            if not html:
                return result
            rsc = self._extract_rsc(html)
            result["list"] = self._parse_list(html, rsc)
        except Exception as e:
            print("searchContent error: {0}".format(e))
        return result

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        """播放: 解析 /l/{movie_id}/{link_id}[/{line}]
        line 为线路标识 (cn=国内线路, vip=海外线路); 调用 AES API 获取 playback_v2,
        按线路选取对应签名 m3u8 (video_lines[i].h264.url), 经本站同源代理直出
        """
        result = {"parse": 0, "playUrl": "", "url": "", "header": "", "jx": 0}
        try:
            play_path = id
            if "$" in play_path:
                play_path = play_path.split("$")[-1]
            play_path = play_path.strip()

            if play_path.startswith("/l/"):
                parts = play_path.split("/")
                # ['', 'l', movie_id, link_id(, line)]
                movie_id = parts[2] if len(parts) > 2 else ""
                link_id = parts[3] if len(parts) > 3 else ""
                line_key = parts[4] if len(parts) > 4 else ""
                if not movie_id or not link_id:
                    return result
                res = self._api_post("movie/detail", {"id": movie_id, "link_id": link_id, "is_simple": "y"})
                if not res or res.get("status") != "y":
                    return result
                pb = res.get("data", {}).get("playback_v2")
                if not pb:
                    return result

                play_url = ""
                # 按请求的线路选取 (找不到时回退默认线路)
                default_line = pb.get("default_line") or ""
                video_lines = pb.get("video_lines") or []
                chosen = None
                for vl in video_lines:
                    if str(vl.get("line") or "") == line_key:
                        chosen = vl
                        break
                if chosen is None and default_line:
                    for vl in video_lines:
                        if str(vl.get("line") or "") == default_line:
                            chosen = vl
                            break
                if chosen is not None:
                    h264 = chosen.get("h264") or {}
                    play_url = h264.get("url") or ""
                    if not play_url:
                        hevc = chosen.get("hevc") or {}
                        play_url = hevc.get("url") or ""
                if not play_url:
                    play_url = pb.get("play_url") or ""

                if not play_url:
                    return result
                if play_url.startswith("/"):
                    play_url = self.HOST + play_url
                result["url"] = play_url
                result["parse"] = 0
            elif play_path.startswith("http"):
                result["url"] = play_path
                result["parse"] = 0
            else:
                if not play_path.startswith("/"):
                    play_path = "/" + play_path
                result["url"] = self.HOST + play_path
                result["parse"] = 0
        except Exception as e:
            print("playerContent error: {0}".format(e))
        return result
