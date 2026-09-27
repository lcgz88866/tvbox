# -*- coding: utf-8 -*-
"""
==========================================================
  555影院 (www.555k28.com) TVBox Python Spider
  适用: TVBox OK版 / FongMi版 (type=3, Chaquopy引擎)
  更新: 2026-08-08

  URL规则:
    分类/筛选页: /vodshow/{cid}-{area}-{sort}-{class}--------{page}---{year}.html
      字段(12段, 索引0-11):
        0:cid  1:area  2:sort  3:class
        4-7:空  8:page  9-10:空  11:year
    详情页: /voddetail/{vid}.html
    播放页: /vodplay/{vid}-{sid}-{nid}.html
    搜索:   /vodsearch/------------{wd}----------{page}---.html

  播放解密 (encrypt=3):
    1. 播放页内 player_aaaa JSON 含 url, from, encrypt
    2. 自定义Base64还原: o000o→+, oo00o→/, O0O0O→=
    3. AES-CBC解密: key=81f834a7f68d4c52, iv=zkz8scsGXttFVZBb, padding=PKCS7
    4. 解密结果即为 m3u8 播放地址

  配置方式:
  {
    "sites": [{
      "key": "py_555",
      "name": "555影院",
      "type": 3,
      "api": "py_555",
      "searchable": 1,
      "quickSearch": 0,
      "filterable": 1,
      "ext": "https://your-host/py_555.py"
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
import base64
import urllib.request
import urllib.error
from urllib.parse import quote, unquote
from html import unescape as html_unescape


# ==================== AES-CBC 纯Python实现 ====================
# 用于 encrypt=3 解密, 无需外部依赖

# AES S盒 (256 entries, 16 per line)
_SBOX = [
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
]

# AES 逆S盒
_INV_SBOX = [
    0x52,0x09,0x6a,0xd5,0x30,0x36,0xa5,0x38,0xbf,0x40,0xa3,0x9e,0x81,0xf3,0xd7,0xfb,
    0x7c,0xe3,0x39,0x82,0x9b,0x2f,0xff,0x87,0x34,0x8e,0x43,0x44,0xc4,0xde,0xe9,0xcb,
    0x54,0x7b,0x94,0x32,0xa6,0xc2,0x23,0x3d,0xee,0x4c,0x95,0x0b,0x42,0xfa,0xc3,0x4e,
    0x08,0x2e,0xa1,0x66,0x28,0xd9,0x24,0xb2,0x76,0x5b,0xa2,0x49,0x6d,0x8b,0xd1,0x25,
    0x72,0xf8,0xf6,0x64,0x86,0x68,0x98,0x16,0xd4,0xa4,0x5c,0xcc,0x5d,0x65,0xb6,0x92,
    0x6c,0x70,0x48,0x50,0xfd,0xed,0xb9,0xda,0x5e,0x15,0x46,0x57,0xa7,0x8d,0x9d,0x84,
    0x90,0xd8,0xab,0x00,0x8c,0xbc,0xd3,0x0a,0xf7,0xe4,0x58,0x05,0xb8,0xb3,0x45,0x06,
    0xd0,0x2c,0x1e,0x8f,0xca,0x3f,0x0f,0x02,0xc1,0xaf,0xbd,0x03,0x01,0x13,0x8a,0x6b,
    0x3a,0x91,0x11,0x41,0x4f,0x67,0xdc,0xea,0x97,0xf2,0xcf,0xce,0xf0,0xb4,0xe6,0x73,
    0x96,0xac,0x74,0x22,0xe7,0xad,0x35,0x85,0xe2,0xf9,0x37,0xe8,0x1c,0x75,0xdf,0x6e,
    0x47,0xf1,0x1a,0x71,0x1d,0x29,0xc5,0x89,0x6f,0xb7,0x62,0x0e,0xaa,0x18,0xbe,0x1b,
    0xfc,0x56,0x3e,0x4b,0xc6,0xd2,0x79,0x20,0x9a,0xdb,0xc0,0xfe,0x78,0xcd,0x5a,0xf4,
    0x1f,0xdd,0xa8,0x33,0x88,0x07,0xc7,0x31,0xb1,0x12,0x10,0x59,0x27,0x80,0xec,0x5f,
    0x60,0x51,0x7f,0xa9,0x19,0xb5,0x4a,0x0d,0x2d,0xe5,0x7a,0x9f,0x93,0xc9,0x9c,0xef,
    0xa0,0xe0,0x3b,0x4d,0xae,0x2a,0xf5,0xb0,0xc8,0xeb,0xbb,0x3c,0x83,0x53,0x99,0x61,
    0x17,0x2b,0x04,0x7e,0xba,0x77,0xd6,0x26,0xe1,0x69,0x14,0x63,0x55,0x21,0x0c,0x7d,
]

# 轮常量
_RCON = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36]

def _xtime(a):
    return (((a << 1) ^ 0x1b) & 0xff) if (a & 0x80) else (a << 1)

def _mul(a, b):
    r = 0
    for _ in range(8):
        if b & 1:
            r ^= a
        a = _xtime(a)
        b >>= 1
    return r

def _key_expansion(key):
    """AES密钥扩展"""
    Nk = len(key) // 4  # 4 for AES-128
    Nr = Nk + 6         # 10 for AES-128
    w = [list(key[4*i:4*i+4]) for i in range(Nk)]
    for i in range(Nk, 4 * (Nr + 1)):
        temp = list(w[i-1])
        if i % Nk == 0:
            temp = temp[1:] + temp[:1]
            temp = [_SBOX[b] for b in temp]
            temp[0] ^= _RCON[i // Nk - 1]
        elif Nk > 6 and i % Nk == 4:
            temp = [_SBOX[b] for b in temp]
        w.append([w[i-Nk][j] ^ temp[j] for j in range(4)])
    return w

def _add_round_key(state, w, rnd):
    for c in range(4):
        for r in range(4):
            state[4*c+r] ^= w[rnd*4+c][r]

def _sub_bytes(state):
    for i in range(16):
        state[i] = _SBOX[state[i]]

def _inv_sub_bytes(state):
    for i in range(16):
        state[i] = _INV_SBOX[state[i]]

def _shift_rows(state):
    state[1], state[5], state[9], state[13] = state[5], state[9], state[13], state[1]
    state[2], state[6], state[10], state[14] = state[10], state[14], state[2], state[6]
    state[3], state[7], state[11], state[15] = state[15], state[3], state[7], state[11]

def _inv_shift_rows(state):
    state[1], state[5], state[9], state[13] = state[13], state[1], state[5], state[9]
    state[2], state[6], state[10], state[14] = state[10], state[14], state[2], state[6]
    state[3], state[7], state[11], state[15] = state[7], state[11], state[15], state[3]

def _mix_columns(state):
    for c in range(4):
        s0, s1, s2, s3 = state[4*c], state[4*c+1], state[4*c+2], state[4*c+3]
        state[4*c]   = _mul(s0,2) ^ _mul(s1,3) ^ s2 ^ s3
        state[4*c+1] = s0 ^ _mul(s1,2) ^ _mul(s2,3) ^ s3
        state[4*c+2] = s0 ^ s1 ^ _mul(s2,2) ^ _mul(s3,3)
        state[4*c+3] = _mul(s0,3) ^ s1 ^ s2 ^ _mul(s3,2)

def _inv_mix_columns(state):
    for c in range(4):
        s0, s1, s2, s3 = state[4*c], state[4*c+1], state[4*c+2], state[4*c+3]
        state[4*c]   = _mul(s0,14) ^ _mul(s1,11) ^ _mul(s2,13) ^ _mul(s3,9)
        state[4*c+1] = _mul(s0,9) ^ _mul(s1,14) ^ _mul(s2,11) ^ _mul(s3,13)
        state[4*c+2] = _mul(s0,13) ^ _mul(s1,9) ^ _mul(s2,14) ^ _mul(s3,11)
        state[4*c+3] = _mul(s0,11) ^ _mul(s1,13) ^ _mul(s2,9) ^ _mul(s3,14)

def _aes_decrypt_block(block, w):
    """解密单个16字节块"""
    Nr = len(w) // 4 - 1
    state = list(block)
    _add_round_key(state, w, Nr)
    for rnd in range(Nr-1, 0, -1):
        _inv_shift_rows(state)
        _inv_sub_bytes(state)
        _add_round_key(state, w, rnd)
        _inv_mix_columns(state)
    _inv_shift_rows(state)
    _inv_sub_bytes(state)
    _add_round_key(state, w, 0)
    return bytes(state)

def aes_cbc_decrypt(ciphertext, key, iv):
    """AES-CBC解密, 返回bytes"""
    w = _key_expansion(key)
    result = bytearray()
    prev = iv
    for i in range(0, len(ciphertext), 16):
        block = ciphertext[i:i+16]
        decrypted = _aes_decrypt_block(block, w)
        result.extend(bytes(a ^ b for a, b in zip(decrypted, prev)))
        prev = block
    return bytes(result)

def _pkcs7_unpad(data):
    """PKCS7去填充"""
    if not data:
        return data
    pad_len = data[-1]
    if pad_len < 1 or pad_len > 16:
        return data
    if data[-pad_len:] != bytes([pad_len]) * pad_len:
        return data
    return data[:-pad_len]


class Spider(Spider):

    HOST = "https://www.555k28.com"
    UA = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # AES解密参数
    AES_KEY = b"81f834a7f68d4c52"
    AES_IV  = b"zkz8scsGXttFVZBb"

    # ==================== 分类配置 ====================
    CATEGORIES = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "电视剧", "type_id": "2"},
        {"type_name": "综艺", "type_id": "3"},
        {"type_name": "动漫", "type_id": "4"},
        {"type_name": "短剧", "type_id": "13"},
        {"type_name": "纪录片", "type_id": "15"},
        {"type_name": "海外剧", "type_id": "44"},
        {"type_name": "其他", "type_id": "45"},
    ]

    # 各分类的类型(class)选项
    CLASS_MAP = {
        "1": ["动作", "爱情", "恐怖", "科幻", "剧情", "喜剧", "悬疑", "惊悚",
              "犯罪", "战争", "动画", "奇幻", "武侠", "冒险", "灾难", "警匪",
              "枪战", "历史", "经典", "纪录", "其他"],
        "2": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻",
              "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
        "3": ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实",
              "曲艺", "生活", "游戏互动", "财经", "求职"],
        "4": ["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园",
              "动作", "机战", "运动", "战争", "少年", "少女", "社会", "原创",
              "亲子", "益智", "励志", "其他"],
        "13": ["爽文", "反转", "都市", "恋爱", "古装", "穿越", "悬疑", "重生"],
        "15": ["历史", "人物", "美食", "文化", "探索", "社会", "自然", "科技"],
        "44": ["韩剧", "日剧", "美剧", "英剧", "泰剧", "其他"],
        "45": [],
    }

    # 各分类的地区选项
    AREA_MAP = {
        "1": ["中国大陆", "中国香港", "中国台湾", "美国", "日本", "韩国", "泰国",
              "英国", "法国", "德国", "意大利", "印度", "俄罗斯", "加拿大",
              "澳大利亚", "巴西", "丹麦", "瑞典", "其他"],
        "2": ["中国大陆", "中国香港", "中国台湾", "美国", "日本", "韩国", "泰国",
              "英国", "法国", "德国", "意大利", "其他"],
        "3": ["中国大陆", "港台", "日韩", "欧美", "其他"],
        "4": ["中国大陆", "日本", "欧美", "其他"],
        "13": ["中国大陆"],
        "15": ["中国大陆", "美国", "法国", "英国", "其他"],
        "44": ["韩国", "日本", "美国", "英国", "泰国", "其他"],
        "45": [],
    }

    # 排序选项
    SORT_VALUES = [
        {"n": "时间排序", "v": "time"},
        {"n": "人气排序", "v": "hits"},
        {"n": "评分排序", "v": "score"},
    ]

    def getName(self):
        return "555影院"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": self.UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Referer": self.HOST + "/",
        }
        try:
            self._ssl_ctx = ssl.create_default_context()
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        except:
            self._ssl_ctx = None

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
        year_values = [{"n": "不限", "v": ""}]
        for y in range(2026, 1999, -1):
            year_values.append({"n": str(y), "v": str(y)})
        for y in ["90年代", "80年代", "70年代", "更早"]:
            year_values.append({"n": y, "v": y})

        for cat in self.CATEGORIES:
            cat_id = cat["type_id"]
            cat_filters = []

            # 类型
            class_values = [{"n": "不限", "v": ""}]
            for c in self.CLASS_MAP.get(cat_id, []):
                class_values.append({"n": c, "v": c})
            if len(class_values) > 1:
                cat_filters.append({"key": "class", "name": "类型", "value": class_values})

            # 地区
            area_values = [{"n": "不限", "v": ""}]
            for a in self.AREA_MAP.get(cat_id, []):
                area_values.append({"n": a, "v": a})
            if len(area_values) > 1:
                cat_filters.append({"key": "area", "name": "地区", "value": area_values})

            # 年份
            cat_filters.append({"key": "year", "name": "年份", "value": year_values})

            # 排序
            cat_filters.append({"key": "sort", "name": "排序", "value": self.SORT_VALUES})

            filters[cat_id] = cat_filters
        return filters

    # ==================== HTTP ====================
    def _fetch(self, url, timeout=15, referer=None):
        """GET请求, 返回HTML文本
        优先使用TVBox base Spider的fetch方法, 回退到urllib
        """
        if not url.isascii():
            url = quote(url, safe=":/?&=%-._~")
        h = dict(self.headers)
        if referer:
            h["Referer"] = referer

        # 方式1: TVBox base Spider 的 fetch 方法
        try:
            r = self.fetch(url, headers=h)
            if r is not None:
                text = r.text if hasattr(r, 'text') else str(r)
                if text:
                    return text
        except:
            pass

        # 方式2: requests库
        try:
            import requests
            r = requests.get(url, headers=h, verify=False, timeout=timeout)
            return r.text
        except:
            pass

        # 方式3: urllib (本地测试回退)
        try:
            import gzip as gz
            req = urllib.request.Request(url, headers=h)
            if self._ssl_ctx:
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=self._ssl_ctx)
                )
            else:
                opener = urllib.request.build_opener()
            with opener.open(req, timeout=timeout) as resp:
                data = resp.read()
                if len(data) > 2 and data[:2] == b'\x1f\x8b':
                    try:
                        data = gz.decompress(data)
                    except:
                        pass
                return data.decode("utf-8", errors="ignore") if data else ""
        except urllib.error.HTTPError as e:
            try:
                import gzip as gz
                data = e.read()
                if len(data) > 2 and data[:2] == b'\x1f\x8b':
                    try:
                        data = gz.decompress(data)
                    except:
                        pass
                return data.decode("utf-8", errors="ignore")
            except:
                return ""
        except:
            return ""

    def _fetch_json(self, url, timeout=15, referer=None):
        """GET请求, 返回JSON"""
        h = dict(self.headers)
        h["Accept"] = "application/json, text/javascript, */*; q=0.01"
        h["X-Requested-With"] = "XMLHttpRequest"
        if referer:
            h["Referer"] = referer

        # 方式1: TVBox base Spider
        try:
            r = self.fetch(url, headers=h)
            if r is not None:
                return r.json() if hasattr(r, 'json') else json.loads(r.text if hasattr(r, 'text') else str(r))
        except:
            pass

        # 方式2: requests
        try:
            import requests
            r = requests.get(url, headers=h, verify=False, timeout=timeout)
            return r.json()
        except:
            pass

        # 方式3: urllib
        try:
            import gzip as gz
            if not url.isascii():
                url = quote(url, safe=":/?&=%-._~")
            req = urllib.request.Request(url, headers=h)
            if self._ssl_ctx:
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=self._ssl_ctx)
                )
            else:
                opener = urllib.request.build_opener()
            with opener.open(req, timeout=timeout) as r:
                data = r.read()
                if len(data) > 2 and data[:2] == b'\x1f\x8b':
                    try:
                        data = gz.decompress(data)
                    except:
                        pass
                return json.loads(data.decode("utf-8", errors="ignore"))
        except:
            return {}

    # ==================== 播放解密 ====================
    def _decrypt_url(self, enc_url):
        """解密 encrypt=3 的播放URL

        步骤:
        1. 自定义Base64还原: o000o→+, oo00o→/, O0O0O→=
        2. AES-CBC解密: key=81f834a7f68d4c52, iv=zkz8scsGXttFVZBb
        3. PKCS7去填充
        """
        try:
            # 步骤1: 自定义Base64还原
            b64_str = enc_url
            b64_str = b64_str.replace('o000o', '+')
            b64_str = b64_str.replace('oo00o', '/')
            b64_str = b64_str.replace('O0O0O', '=')

            # 步骤2: Base64解码
            # 补齐padding
            pad = 4 - len(b64_str) % 4
            if pad < 4:
                b64_str += '=' * pad
            ciphertext = base64.b64decode(b64_str)

            # 步骤3: AES-CBC解密
            decrypted = aes_cbc_decrypt(ciphertext, self.AES_KEY, self.AES_IV)

            # 步骤4: PKCS7去填充
            decrypted = _pkcs7_unpad(decrypted)

            return decrypted.decode('utf-8', errors='ignore')
        except Exception:
            return ""

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

    def _build_show_url(self, cid, extend, page):
        """构建分类筛选URL
        格式: /vodshow/{cid}-{area}-{sort}-{class}--------{page}---{year}.html
        """
        area = ""
        sort = ""
        cls = ""
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
            year = extend.get("year", "") or ""

        fields = [
            str(cid),
            quote(area, safe="") if area else "",
            sort if sort else "",
            quote(cls, safe="") if cls else "",
            "", "", "", "",
            str(page), "", "",
            year if year else "",
        ]
        return "/vodshow/" + "-".join(fields) + ".html"

    # ==================== 列表解析 ====================
    def _parse_list(self, html):
        """解析视频列表卡片
        支持两种卡片结构:
        1. 分类/首页页 (module-poster-item):
          <a href="/voddetail/vid.html" title="标题" class="module-poster-item module-item">
            <div class="module-item-cover">
              <div class="module-item-note">备注</div>
              <div class="module-item-pic">
                <img data-original="封面URL" alt="标题" ...>
              </div>
            </div>
            <div class="module-poster-item-title">标题</div>
          </a>
        2. 搜索页 (module-card-item-poster):
          <a href="/voddetail/vid.html" class="module-card-item-poster">
            <div class="module-item-cover">
              <div class="module-item-note">已完结</div>
              <div class="module-item-pic">
                <img data-original="封面URL" alt="<em>关键词</em>标题" ...>
              </div>
            </div>
          </a>
        """
        items = []
        seen = set()

        # 匹配 module-poster-item 和 module-card-item-poster 两种卡片
        pattern = re.compile(
            r'<a[^>]*href="/voddetail/(\d+)\.html"[^>]*class="module-(?:poster-item|card-item-poster)[^"]*"[^>]*>(.*?)</a>',
            re.S
        )
        for m in pattern.finditer(html):
            vid = m.group(1)
            if vid in seen:
                continue
            content = m.group(2)
            full_tag = m.group(0)

            # 标题: 优先 title= 属性, 其次 alt= , 最后模块内文本
            title = ""
            tm = re.search(r'title="([^"]+)"', full_tag)
            if tm:
                title = tm.group(1).strip()
            if not title:
                tm = re.search(r'module-poster-item-title[^>]*>([^<]+)<', content)
                if tm:
                    title = tm.group(1).strip()
            if not title:
                tm = re.search(r'alt="([^"]+)"', content)
                if tm:
                    title = tm.group(1).strip()
            if not title:
                tm = re.search(r'module-card-item-title[^>]*>(.*?)</', content, re.S)
                if tm:
                    title = re.sub(r'<[^>]+>', '', tm.group(1)).strip()
            if not title:
                continue

            # 清理 <em></em> 等HTML标签 (搜索结果高亮关键词)
            title = re.sub(r'<[^>]+>', '', title).strip()

            seen.add(vid)

            # 封面
            pic = ""
            pm = re.search(r'data-original="([^"]+)"', content)
            if not pm:
                pm = re.search(r'data-src="([^"]+)"', content)
            if not pm:
                pm = re.search(r'<img[^>]+src="([^"]+)"', content)
            if pm:
                pic_url = pm.group(1)
                if not pic_url.startswith("data:"):
                    pic = self._fix_pic(pic_url)

            # 备注
            remark = ""
            rm = re.search(r'module-item-note[^>]*>([^<]+)<', content)
            if rm:
                remark = rm.group(1).strip()
            if not remark:
                rm = re.search(r'module-item-douban[^>]*>([^<]+)<', content)
                if rm:
                    remark = rm.group(1).strip()

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
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}
        try:
            page = int(pg) if pg else 1
        except:
            page = 1
        if page < 1:
            page = 1
        result["page"] = page

        path = self._build_show_url(tid, extend, page)
        html = self._fetch(self.HOST + path)
        if not html:
            return result

        items = self._parse_list(html)
        result["list"] = items

        # 解析总页数
        page_m = re.search(r'/vodshow/\d+-*--------(\d+)---\.html[^"]*"\s*[^>]*>[^<]*尾页', html)
        if page_m:
            result["pagecount"] = int(page_m.group(1))
            result["limit"] = len(items) if items else 24
            result["total"] = result["pagecount"] * result["limit"]
        else:
            # 检查是否有下一页
            next_m = re.search(r'/vodshow/\d+-*--------' + str(page + 1) + r'---\.html', html)
            if next_m:
                result["pagecount"] = page + 1
            else:
                result["pagecount"] = page

        return result

    # ==================== 详情 ====================
    def detailContent(self, ids):
        vid = ids[0]
        url = self.HOST + "/voddetail/" + str(vid) + ".html"
        html = self._fetch(url)
        if not html:
            return {}

        vod = {"vod_id": vid}

        # 标题
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if m:
            vod["vod_name"] = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        else:
            m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                name = m.group(1).strip()
                name = re.sub(r'[-—]\s*.*$', '', name)
                vod["vod_name"] = name

        # 封面 - 详情页主图
        m = re.search(r'cover-lg[^>]*>\s*<img[^>]*src="([^"]+)"', html)
        if not m:
            m = re.search(r'<img[^>]*referrerPolicy="no-referrer"[^>]*src="([^"]+)"', html)
        if not m:
            m = re.search(r'module-item-pic[^>]*>\s*<img[^>]*data-original="([^"]+)"', html)
        if not m:
            m = re.search(r'module-item-pic[^>]*>\s*<img[^>]*src="([^"]+)"', html)
        if m:
            vod["vod_pic"] = self._fix_pic(m.group(1))

        # 元信息 - 从 module-info-item 提取
        info_items = re.findall(
            r'<div[^>]*class="[^"]*module-info-item[^"]*"[^>]*>(.*?)</div>',
            html, re.S
        )
        for item in info_items:
            text = re.sub(r'<[^>]+>', '', item).strip()
            # 解析 "标签：值" 格式
            if '：' in text:
                label, value = text.split('：', 1)
                label = label.strip()
                value = value.strip().rstrip('/').strip()
                if label == '导演':
                    vod["vod_director"] = value
                elif label == '主演':
                    vod["vod_actor"] = value
                elif label == '编剧':
                    pass  # 编剧不单独处理
                elif label == '更新':
                    vod["vod_year"] = value[:4] if value[:4].isdigit() else ""
                elif label == '备注':
                    vod["vod_remarks"] = value
                elif label == '豆瓣':
                    pass
                elif label == '类型':
                    vod["vod_class"] = value.replace('/', ',').replace('  ', '').strip()

        # 类型 - 从 info-block 提取 (备用)
        if "vod_class" not in vod:
            m = re.search(r'module-info-tag[^>]*>(.*?)</div>', html, re.S)
            if m:
                tags = re.findall(r'>([^<]+)<', m.group(1))
                tags = [t.strip() for t in tags if t.strip() and t.strip() != '/']
                vod["vod_class"] = ','.join(tags)

        # 简介
        m = re.search(r'module-info-content[^>]*>(.*?)</div>', html, re.S)
        if m:
            content = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            vod["vod_content"] = content
        else:
            # 从 meta description 提取
            m = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
            if m:
                desc = m.group(1)
                # 去掉 "xxx剧情:" 前缀
                desc = re.sub(r'^[^:]+剧情[：:]\s*', '', desc)
                vod["vod_content"] = desc

        # 年份 - 从标题旁的数字提取
        if "vod_year" not in vod or not vod["vod_year"]:
            m = re.search(r'<h1[^>]*>.*?(\d{4})\s*</h1>', html, re.S)
            if m:
                vod["vod_year"] = m.group(1)

        # 地区 - 从 info-tag 提取
        if "vod_area" not in vod:
            # 从 meta keywords 或页面内容提取
            m = re.search(r'(中国大陆|中国香港|中国台湾|美国|日本|韩国|泰国|英国|法国|德国)', html)
            if m:
                vod["vod_area"] = m.group(1)

        # ==================== 播放源和集数 ====================
        # 提取播放源名称 (module-tab-item 的 data-dropdown-value)
        source_names = re.findall(
            r'module-tab-item[^>]*data-dropdown-value="([^"]*)"', html
        )

        # 备用: 从 span 中提取线路名称
        if not source_names:
            line_m = re.findall(
                r'<span[^>]*>([^<]*(?:线路|蓝光|高清|超清|极速)[^<]*)</span>',
                html
            )
            for t in line_m:
                t = t.strip()
                if t and len(t) < 30:
                    source_names.append(t)

        # 提取所有播放链接 (按源分组)
        # 每个 module-play-list-content 是一个源
        play_sections = re.findall(
            r'<div class="module-play-list-content[^"]*"[^>]*>(.*?)</div>',
            html, re.S
        )

        play_from_list = []
        play_url_list = []

        for i, section in enumerate(play_sections):
            # 源名称
            if i < len(source_names):
                from_name = source_names[i]
            else:
                from_name = f"线路{i+1}"

            # 集数链接
            ep_links = re.findall(
                r'<a[^>]*href="/vodplay/(\d+)-(\d+)-(\d+)\.html"[^>]*>(.*?)</a>',
                section, re.S
            )

            if not ep_links:
                continue

            episodes = []
            for vid_e, sid, nid, text in ep_links:
                ep_name = re.sub(r'<[^>]+>', '', text).strip()
                if not ep_name:
                    ep_name = f"第{nid}集"
                episodes.append(f"{ep_name}${vid_e}-{sid}-{nid}")

            if episodes:
                play_from_list.append(from_name)
                play_url_list.append("#".join(episodes))

        if play_from_list:
            vod["vod_play_from"] = "$$$".join(play_from_list)
            vod["vod_play_url"] = "$$$".join(play_url_list)

        return {'list': [vod]}

    # ==================== 播放 ====================
    def _safe_url(self, url):
        """对URL中的非ASCII字符进行百分号编码, 保持http结构完整"""
        if not url:
            return url
        try:
            if url.isascii():
                return url
            # 分离 scheme://host 和 path
            m = re.match(r'(https?://[^/]+)(.*)', url)
            if m:
                host = m.group(1)
                path = m.group(2)
                path = quote(path, safe="/:?&=%-._~")
                return host + path
            return quote(url, safe=":/?&=%-._~")
        except:
            return url

    def playerContent(self, flag, id, vipFlags):
        """获取播放地址
        id 格式: vid-sid-nid
        """
        result = {"parse": 0, "header": "", "url": ""}

        try:
            parts = id.split("-")
            if len(parts) < 3:
                return result
            vid, sid, nid = parts[0], parts[1], parts[2]
        except:
            return result

        play_url = self.HOST + f"/vodplay/{vid}-{sid}-{nid}.html"
        html = self._fetch(play_url, referer=self.HOST + "/")
        if not html:
            return result

        # 提取 player_aaaa JSON
        pa_m = re.search(r'player_aaaa\s*=\s*(\{)', html)
        if not pa_m:
            return result

        start = pa_m.start(1)
        depth = 0
        end = start
        for i in range(start, len(html)):
            if html[i] == '{':
                depth += 1
            elif html[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        raw = html[start:end]

        # 提取 url 和 encrypt
        url_m = re.search(r'"url"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
        encrypt_m = re.search(r'"encrypt"\s*:\s*(\d+)', raw)
        from_m = re.search(r'"from"\s*:\s*"([^"]*)"', raw)

        if not url_m:
            return result

        enc_url = url_m.group(1).replace('\\"', '"').replace('\\/', '/').replace('\\u0026', '&')
        encrypt = int(encrypt_m.group(1)) if encrypt_m else 0
        from_val = from_m.group(1) if from_m else ""

        final_url = ""

        if encrypt == 3:
            # AES解密
            final_url = self._decrypt_url(enc_url)
        elif encrypt == 0:
            # 直接URL
            final_url = html_unescape(enc_url)
        elif encrypt == 1:
            # unescape解码
            final_url = unquote(enc_url)
        elif encrypt == 2:
            # base64解码
            try:
                final_url = base64.b64decode(enc_url + '==').decode('utf-8', errors='ignore')
            except:
                pass

        # 如果解密失败, 尝试其他方式
        if not final_url or not final_url.startswith('http'):
            if enc_url.startswith('http'):
                final_url = html_unescape(enc_url)
            else:
                # 尝试 AES 解密作为最后手段
                final_url = self._decrypt_url(enc_url)

        if final_url and final_url.startswith('http'):
            # 对非ASCII URL进行百分号编码 (如含中文的路径)
            final_url = self._safe_url(final_url)
            result["url"] = final_url
            result["parse"] = 0
            # 设置请求头 (防盗链) - header必须是dict对象, 不能是json字符串
            result["header"] = {
                "User-Agent": self.UA,
                "Referer": self.HOST + "/",
            }

        return result

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        """搜索
        URL: /vodsearch/{wd}----------{page}---.html
        返回格式: {'list': [...]}
        """
        result = []
        try:
            page = int(pg) if pg else 1
        except:
            page = 1

        # 构建搜索URL
        wd = quote(key, safe="")
        search_path = f"/vodsearch/{wd}----------{page}---.html"
        html = self._fetch(self.HOST + search_path)

        if not html:
            # 尝试备用搜索URL
            search_path = f"/vodsearch/------------{wd}---{page}---.html"
            html = self._fetch(self.HOST + search_path)

        if not html:
            # 尝试AJAX suggest
            ajax_url = self.HOST + f"/index.php/ajax/suggest?mid=1&wd={wd}&limit=20"
            data = self._fetch_json(ajax_url)
            if data and "list" in data:
                for item in data["list"]:
                    result.append({
                        "vod_id": str(item.get("id", "")),
                        "vod_name": item.get("name", ""),
                        "vod_pic": self._fix_pic(item.get("pic", "")),
                        "vod_remarks": item.get("remarks", ""),
                    })
            return {'list': result}

        # 解析搜索结果 (复用列表解析)
        items = self._parse_list(html)
        if items:
            result = items
        else:
            # 备用解析: 搜索页可能有不同的卡片结构
            pattern = re.compile(
                r'<a[^>]*href="/voddetail/(\d+)\.html"[^>]*title="([^"]*)"[^>]*>(.*?)</a>',
                re.S
            )
            seen = set()
            for m in pattern.finditer(html):
                vid = m.group(1)
                if vid in seen:
                    continue
                title = m.group(2).strip()
                content = m.group(3)

                pic = ""
                pm = re.search(r'data-original="([^"]+)"', content)
                if not pm:
                    pm = re.search(r'<img[^>]+src="([^"]+)"', content)
                if pm:
                    pic_url = pm.group(1)
                    if not pic_url.startswith("data:"):
                        pic = self._fix_pic(pic_url)

                remark = ""
                rm = re.search(r'module-item-note[^>]*>([^<]+)<', content)
                if rm:
                    remark = rm.group(1).strip()

                seen.add(vid)
                result.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                })

        return {'list': result}
