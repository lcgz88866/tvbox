# -*- coding: utf-8 -*-
"""
tvbox 插件 - 蛋挞TV（兼容基类修正版）
站点: https://www.dantatv.cc
"""
import json
import sys
from base64 import b64encode, b64decode

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def init(self, extend=""):
        self.host = "https://www.dantatv.cc"
        pass

    def getName(self):
        return "蛋挞TV"

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def localProxy(self, param):
        pass

    def destroy(self):
        pass

    def fetch(self, url, params=None, cookies=None, headers=None, timeout=5, verify=False, stream=False, allow_redirects=True):
        import requests as _r
        import urllib3 as _u
        _u.disable_warnings()
        rsp = _r.get(url, params=params, cookies=cookies, headers=headers, timeout=timeout, verify=verify, stream=stream, allow_redirects=allow_redirects)
        rsp.encoding = 'utf-8'
        return rsp

    def post(self, url, params=None, data=None, json=None, cookies=None, headers=None, timeout=5, verify=False, stream=False, allow_redirects=True):
        import requests as _r
        import urllib3 as _u
        _u.disable_warnings()
        rsp = _r.post(url, params=params, data=data, json=json, headers=headers, timeout=timeout, verify=verify, stream=stream, allow_redirects=allow_redirects)
        rsp.encoding = 'utf-8'
        return rsp

    # ---------- 辅助函数 ----------
    def getheader(self, content_type=None):
        headers = {
            'Unique-Origin': 'B9A378A8C39BDA1277D2D6185FCE2695',
            'User-Agent': 'okhttp/4.1.0/luob.app',
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip',
        }
        if content_type:
            headers['Content-Type'] = content_type
        return headers

    def e64(self, text):
        try:
            text_bytes = text.encode('utf-8')
            encoded_bytes = b64encode(text_bytes)
            return encoded_bytes.decode('utf-8')
        except Exception as e:
            print(f"Base64编码错误: {str(e)}")
            return ""

    def d64(self, encoded_text):
        try:
            encoded_bytes = encoded_text.encode('utf-8')
            decoded_bytes = b64decode(encoded_bytes)
            return decoded_bytes.decode('utf-8')
        except Exception as e:
            print(f"Base64解码错误: {str(e)}")
            return ""

    # ---------- 筛选项构造 ----------
    def _opt(self, name, value):
        return {"n": name, "v": value}

    def _filter(self, key, name, values):
        return {"key": key, "name": name, "value": [self._opt(n, v) for n, v in values]}

    def _common_filters(self, class_values):
        """地区/年份/排序 通用筛选项 + 指定类型的类型筛选项
        取值均来自接口真实返回数据，地区用短词以便模糊匹配（传"中国"可命中"中国大陆"）。
        """
        area_values = [
            ("全部", ""), ("中国", "中国"), ("内地", "内地"), ("香港", "香港"),
            ("台湾", "台湾"), ("美国", "美国"), ("韩国", "韩国"), ("日本", "日本"),
            ("英国", "英国"), ("法国", "法国"), ("泰国", "泰国"), ("印度", "印度"),
        ]
        year_values = [
            ("全部", ""), ("2026", "2026"), ("2025", "2025"), ("2024", "2024"),
            ("2023", "2023"), ("2022", "2022"), ("2021", "2021"), ("2020", "2020"),
            ("2019", "2019"), ("2018", "2018"), ("2017", "2017"), ("2016", "2016"),
            ("2015", "2015"),
        ]
        sort_values = [
            ("最新", "vod_time"), ("最热", "vod_hits"), ("评分", "vod_score"),
        ]
        filters = []
        if class_values:
            filters.append(self._filter("class", "类型", class_values))
        filters.append(self._filter("area", "地区", area_values))
        filters.append(self._filter("year", "年份", year_values))
        filters.append(self._filter("sort", "排序", sort_values))
        return filters

    # ---------- 首页（固定分类 + 筛选） ----------
    def homeContent(self, filter):
        classes = [
            {"type_name": "剧集", "type_id": "1"},
            {"type_name": "电影", "type_id": "2"},
            {"type_name": "动漫", "type_id": "3"},
            {"type_name": "短剧", "type_id": "4"},
            {"type_name": "综艺", "type_id": "5"},
            {"type_name": "少儿", "type_id": "30"},
        ]

        # 以下类型取值均为接口 vodClass 字段真实存在的标签（经 API 采样验证）
        juji_class = [
            ("全部", ""), ("古装", "古装"), ("武侠", "武侠"), ("都市", "都市"),
            ("言情", "言情"), ("青春", "青春"), ("悬疑", "悬疑"), ("罪案", "罪案"),
            ("战争", "战争"), ("军旅", "军旅"), ("历史", "历史"), ("民国", "民国"),
            ("励志", "励志"), ("穿越", "穿越"), ("科幻", "科幻"), ("奇幻", "奇幻"),
            ("家庭", "家庭"), ("爱情", "爱情"), ("喜剧", "喜剧"), ("运动", "运动"),
        ]
        dianying_class = [
            ("全部", ""), ("动作", "动作"), ("喜剧", "喜剧"), ("爱情", "爱情"),
            ("科幻", "科幻"), ("悬疑", "悬疑"), ("恐怖", "恐怖"), ("惊悚", "惊悚"),
            ("灾难", "灾难"), ("战争", "战争"), ("犯罪", "犯罪"), ("古装", "古装"),
            ("武侠", "武侠"), ("奇幻", "奇幻"), ("动画", "动画"), ("歌舞", "歌舞"),
            ("纪录片", "纪录片"), ("传记", "传记"), ("历史", "历史"), ("枪战", "枪战"),
            ("冒险", "冒险"), ("家庭", "家庭"),
        ]
        dongman_class = [
            ("全部", ""), ("热血", "热血"), ("搞笑", "搞笑"), ("恋爱", "恋爱"),
            ("校园", "校园"), ("奇幻", "奇幻"), ("科幻", "科幻"), ("治愈", "治愈"),
            ("悬疑", "悬疑"), ("推理", "推理"), ("竞技", "竞技"), ("励志", "励志"),
            ("古装", "古装"), ("古风", "古风"), ("战斗", "战斗"), ("萌系", "萌系"),
            ("日常", "日常"), ("玄幻", "玄幻"), ("仙侠", "仙侠"), ("漫画改", "漫画改"),
            ("原创", "原创"), ("泡面", "泡面"), ("异能", "异能"), ("逆袭", "逆袭"),
        ]
        duanju_class = [
            ("全部", ""), ("都市", "都市"), ("穿越", "穿越"), ("重生", "重生"),
            ("豪门", "豪门"), ("总裁", "总裁"), ("虐恋", "虐恋"), ("玄幻", "玄幻"),
            ("武侠", "武侠"), ("离婚", "离婚"), ("复仇", "复仇"), ("古风", "古风"),
            ("爱情", "爱情"), ("现代", "现代"), ("刑侦", "刑侦"), ("家庭伦理", "家庭伦理"),
        ]
        zongyi_class = [
            ("全部", ""), ("真人秀", "真人秀"), ("脱口秀", "脱口秀"), ("音乐", "音乐"),
            ("美食", "美食"), ("旅行", "旅行"), ("情感", "情感"), ("竞技", "竞技"),
            ("访谈", "访谈"), ("萌宠", "萌宠"), ("文化", "文化"), ("搞笑", "搞笑"),
            ("说唱", "说唱"), ("益智", "益智"), ("职场", "职场"), ("慢生活", "慢生活"),
            ("推理", "推理"), ("游戏", "游戏"), ("运动", "运动"),
        ]
        shaoer_class = [
            ("全部", ""), ("动画", "动画"), ("益智", "益智"), ("科普", "科普"),
            ("儿歌", "儿歌"), ("冒险", "冒险"), ("神话传说", "神话传说"), ("机甲", "机甲"),
            ("早教", "早教"), ("英语", "英语"), ("诗词", "诗词"), ("侦探", "侦探"),
            ("动物", "动物"), ("校园", "校园"), ("科幻", "科幻"), ("魔幻", "魔幻"),
            ("搞笑", "搞笑"), ("英雄", "英雄"), ("亲子", "亲子"),
        ]

        filters = {
            "1": self._common_filters(juji_class),
            "2": self._common_filters(dianying_class),
            "3": self._common_filters(dongman_class),
            "4": self._common_filters(duanju_class),
            "5": self._common_filters(zongyi_class),
            "30": self._common_filters(shaoer_class),
        }
        return {"class": classes, "filters": filters}

    # ---------- 首页推荐视频 ----------
    def homeVideoContent(self):
        url = f"{self.host}/api/index"
        headers = self.getheader()
        try:
            resp = self.fetch(url, headers=headers)
            data = resp.json()
            vod_list = []
            seen = set()
            for group in data.get('data', []) or []:
                for item in group.get('vodList', []) or []:
                    vid = str(item.get('vodId', ''))
                    if not vid or vid in seen:
                        continue
                    seen.add(vid)
                    vod_list.append(self._vod_to_common(item))
        except Exception as e:
            print(f"首页推荐请求失败: {e}")
            vod_list = []
        return {'list': vod_list}

    # ---------- 分类页（POST请求改用 self.post） ----------
    def categoryContent(self, tid, pg, filter, extend=None):
        if extend is None:
            extend = {}
        # 排序字段支持由筛选项控制，默认按最新
        sort_field = extend.get('sort', '') or 'vod_time'
        body = {
            "typeId1": int(tid),
            "pageNum": int(pg),
            "pageSize": 12,
            "sortField": sort_field,
            "vodClass": extend.get('class', ''),
            "vodArea": extend.get('area', ''),
            "vodYear": extend.get('year', '')
        }
        url = f"{self.host}/api/search/type"
        headers = self.getheader(content_type='application/json')
        try:
            # 使用基类的 post 方法（若基类无 post，可改为 requests.post 自行实现）
            resp = self.post(url, headers=headers, data=json.dumps(body).encode('utf-8'))
            data = resp.json()
            vod_list = [self._vod_to_common(item) for item in data.get('data', [])]
        except Exception as e:
            print(f"分类页请求失败: {e}")
            vod_list = []
        return {
            'list': vod_list,
            'page': pg,
            'pagecount': 9999,
            'limit': 12,
            'total': 999999
        }

    # ---------- 详情页 ----------
    def detailContent(self, ids):
        vod_id = ids[0]
        url = f"{self.host}/api/vod/play?vodId={vod_id}"
        headers = self.getheader()
        try:
            resp = self.fetch(url, headers=headers)
            data = resp.json()
            vod = data.get('data', {}).get('dantaVod', {})
        except Exception as e:
            print(f"详情请求失败: {e}")
            return {'list': []}

        if not vod:
            return {'list': []}

        info = {
            'vod_id': vod.get('vodId'),
            'vod_name': vod.get('vodName'),
            'vod_pic': self._fix_pic(vod.get('vodPic')),
            'vod_actor': vod.get('vodActor'),
            'vod_director': vod.get('vodDirector'),
            'vod_content': vod.get('vodContent') or vod.get('vodBlurb'),
            'vod_area': vod.get('vodArea'),
            'vod_year': vod.get('vodYear'),
            'vod_remarks': vod.get('vodRemarks'),
            'vod_lang': vod.get('vodLang'),
            'vod_class': vod.get('vodClass'),
        }

        sources = vod.get('sources', [])

        # ===== 播放线路智能排序 =====
        # 优先级: 1.含直链(m3u8/mp4)的线路优先 2.线路名称优先级(常用名称排前) 3.集数多的排前
        LINE_PRIORITY = [
            '夸克', 'UC', '阿里', '迅雷', '百度', '网盘',
            '蓝光', '高清', '超清', 'HD', '1080', '4K',
            '线路1', '线路2', '线路3',
            '默认', '备用',
        ]
        # 反向优先级 (排后面)
        LINE_DEPRIORITIZE = ['解析', '嗅探', '无源', '失效', '测试']

        def _sort_key(src):
            name = (src.get('collectName') or src.get('vodPlayFrom') or '').lower()
            raw_url = src.get('vodPlayUrl', '')

            # 1. 含直链的排最前
            has_direct = self.is_direct(raw_url)

            # 2. 线路名称优先级
            priority = 99
            for i, keyword in enumerate(LINE_PRIORITY):
                kw = keyword.lower()
                if kw in name:
                    priority = i
                    break

            # 3. 被降级的排后面
            deprio = 0
            for kw in LINE_DEPRIORITIZE:
                if kw.lower() in name:
                    deprio = 1
                    break

            # 4. 集数越多越靠前 (作为同优先级内的排序)
            ep_count = raw_url.count('#') + 1 if raw_url else 0

            return (
                0 if has_direct else 1,   # 直链优先
                deprio,                    # 降级项排后
                priority,                  # 名称优先级
                -ep_count,                 # 集数多的排前
            )

        sources_sorted = sorted(sources, key=_sort_key)

        vod_play_from = []
        vod_play_url = []
        for idx, src in enumerate(sources_sorted):
            collect_id = src.get('collectId')
            raw_url = src.get('vodPlayUrl', '')
            if not raw_url:
                continue

            items = raw_url.split('#')
            encoded_items = []
            for part in items:
                if '$' not in part:
                    continue
                name, link = part.split('$', 1)
                payload = {"collectId": collect_id, "url": link}
                enc = self.e64(json.dumps(payload, ensure_ascii=False))
                encoded_items.append(f"{name}${enc}")

            if encoded_items:
                line_name = src.get('collectName') or src.get('vodPlayFrom') or f"线路{idx+1}"
                vod_play_from.append(line_name)
                vod_play_url.append('#'.join(encoded_items))

        info['vod_play_from'] = '$$$'.join(vod_play_from)
        info['vod_play_url'] = '$$$'.join(vod_play_url)
        return {'list': [info]}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        url = f"{self.host}/api/search/keyword"
        params = {"keyword": key, "pageNum": pg, "pageSize": 10}
        headers = self.getheader()
        try:
            resp = self.fetch(url, headers=headers, params=params)
            data = resp.json()
            vod_list = [self._vod_to_common(item) for item in data.get('data', [])]
        except Exception as e:
            print(f"搜索失败: {e}")
            vod_list = []
        return {'list': vod_list, 'page': pg}

    # ---------- 播放解析 ----------
    def playerContent(self, flag, id, vipFlags):
        try:
            payload = json.loads(self.d64(id))
            collect_id = payload.get('collectId')
            raw_url = payload.get('url')
            if not collect_id or not raw_url:
                raise ValueError("缺少参数")
        except:
            return {
                'parse': 1,
                'url': '',
                'header': {'User-Agent': 'okhttp/4.1.0/luob.app'}
            }

        # 已是一条可直接播放的音视频直链(m3u8/mp4 等)时, 直接返回, 无需再次解析
        if self.is_direct(raw_url):
            return {
                'parse': 0,
                'url': raw_url,
                'header': {'User-Agent': 'okhttp/4.1.0/luob.app'}
            }

        parse_url = f"{self.host}/api/vod/parse"
        params = {"collectId": collect_id, "url": raw_url}
        headers = self.getheader()
        try:
            resp = self.fetch(parse_url, headers=headers, params=params)
            if resp.status_code == 200:
                result = resp.json()
                if result.get('code') == 200:
                    final_url = result.get('data') or result.get('url')
                    if final_url:
                        return {
                            'parse': 0,
                            'url': final_url,
                            'header': {'User-Agent': 'okhttp/4.1.0/luob.app'}
                        }
        except Exception as e:
            print(f"解析失败: {e}")

        return {
            'parse': 1,
            'url': raw_url,
            'header': {'User-Agent': 'okhttp/4.1.0/luob.app'}
        }

    def is_direct(self, url):
        low = (url or '').lower()
        for ext in ('.m3u8', '.mp4', '.flv', '.mkv', '.ts', '.mp3'):
            if ext in low:
                return True
        return False

    # ---------- 内部辅助：字段映射 ----------
    def _vod_to_common(self, item):
        remark = item.get('vodRemarks', '')
        color = item.get('vodColor')
        if color:
            remark = f"[{color}] {remark}" if remark else color

        return {
            'vod_id': item.get('vodId'),
            'vod_name': item.get('vodName'),
            'vod_pic': self._fix_pic(item.get('vodPic')),
            'vod_remarks': remark,
            'vod_year': item.get('vodYear'),
            'vod_area': item.get('vodArea'),
            'vod_actor': item.get('vodActor'),
            'vod_director': item.get('vodDirector'),
            'vod_lang': item.get('vodLang'),
            'vod_class': item.get('vodClass'),
        }

    def _fix_pic(self, pic):
        """补全相对路径图片"""
        if pic and pic.startswith('/'):
            return self.host + pic
        return pic