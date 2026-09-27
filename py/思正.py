# -*- coding: utf-8 -*-
# 金牌影院 - m.sizhengxt.com
# Next.js + 自定义REST API，需签名验证
import re
import sys
import json
import time
import hashlib

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def getName(self):
        return "金牌影院"

    def init(self, extend=""):
        self.host = "https://m.sizhengxt.com"
        self.api_base = f"{self.host}/mw-movie/anonymous"
        self.sign_key = "cb808529bae6b6be45ecfab29a4889bc"
        self.device_id = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
        self.ua = "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"

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
            # 获取分类列表
            data = self.api_get("/get/filer/type", {})
            if data and data.get("code") == 200:
                for item in data.get("data", []):
                    tid = str(item.get("typeId", ""))
                    tname = item.get("typeName", "")
                    if tid and tname:
                        result["class"].append({"type_id": tid, "type_name": tname})

            # 获取筛选数据
            filter_data = self.api_get("/v1/get/filer/list", {})
            filters_map = {}
            if filter_data and filter_data.get("code") == 200:
                fdata = filter_data.get("data", {})
                for tid, cat in fdata.items():
                    fl = []
                    # 类型
                    type_list = cat.get("typeList", [])
                    if type_list:
                        # 电影类型用 itemText（v_class参数），其他用 itemValue（type参数）
                        is_movie = (tid == "1")
                        type_values = [{"n": "全部", "v": ""}]
                        for t in type_list:
                            val = t.get("itemText", "") if is_movie else t.get("itemValue", "")
                            type_values.append({"n": t.get("itemText", ""), "v": val})
                        fl.append({"key": "type", "name": "类型", "value": type_values})
                    # 地区
                    area_list = cat.get("districtList", [])
                    if area_list:
                        area_values = [{"n": "全部", "v": ""}]
                        for a in area_list:
                            area_values.append({"n": a.get("itemText", ""), "v": a.get("itemText", "")})
                        fl.append({"key": "area", "name": "地区", "value": area_values})
                    # 年份
                    year_list = cat.get("yearList", [])
                    if year_list:
                        year_values = [{"n": "全部", "v": ""}]
                        for y in year_list:
                            year_values.append({"n": y.get("itemText", ""), "v": y.get("itemText", "")})
                        fl.append({"key": "year", "name": "年份", "value": year_values})
                    filters_map[str(tid)] = fl

            for cat in result["class"]:
                tid = cat["type_id"]
                result["filters"][tid] = filters_map.get(tid, [])

            # 首页推荐：取各分类前6条
            seen = set()
            for cat in result["class"]:
                tid = cat["type_id"]
                data = self.api_get("/video/list", {"type1": int(tid), "pageNum": 1, "pageSize": 6})
                if data and data.get("code") == 200:
                    for v in data.get("data", {}).get("list", []):
                        vid = str(v.get("vodId", ""))
                        if vid and vid not in seen:
                            seen.add(vid)
                            result["list"].append({
                                "vod_id": vid,
                                "vod_name": v.get("vodName", ""),
                                "vod_pic": v.get("vodPic", ""),
                                "vod_remarks": v.get("vodRemarks", ""),
                            })
        except Exception as e:
            print(f'homeContent error: {e}')
        return result

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 20, "total": 0}
        try:
            params = {"type1": int(tid), "pageNum": int(pg), "pageSize": 20}
            # 筛选参数处理
            if extend:
                # 类型：电影用 v_class（文本），其他用 type（数字ID）
                type_val = extend.get("type", "")
                if type_val:
                    if type_val.isdigit():
                        params["type"] = int(type_val)
                    else:
                        params["v_class"] = type_val
                # 地区（文本值）
                area_val = extend.get("area", "")
                if area_val:
                    params["area"] = area_val
                # 年份（文本值）
                year_val = extend.get("year", "")
                if year_val:
                    params["year"] = year_val

            data = self.api_get("/video/list", params)
            if data and data.get("code") == 200:
                d = data.get("data", {})
                for v in d.get("list", []):
                    result["list"].append({
                        "vod_id": str(v.get("vodId", "")),
                        "vod_name": v.get("vodName", ""),
                        "vod_pic": v.get("vodPic", ""),
                        "vod_remarks": v.get("vodRemarks", ""),
                    })
                result["pagecount"] = d.get("totalPage", 1)
                result["total"] = d.get("totalCount", 0)
                result["limit"] = d.get("pageSize", 20)
        except Exception as e:
            print(f'categoryContent error: {e}')
        return result

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            data = self.api_get("/video/detail", {"id": int(vod_id)})
            if not data or data.get("code") != 200:
                return result

            v = data.get("data", {})
            vod_name = v.get("vodName", "")
            vod_pic = v.get("vodPic", "")
            vod_content = re.sub(r'<[^>]+>', '', v.get("vodContent", "")).strip()
            vod_director = v.get("vodDirector", "")
            vod_actor = v.get("vodActor", "")
            vod_year = str(v.get("vodYear", ""))
            vod_area = v.get("vodArea", "")
            vod_remarks = v.get("vodRemarks", "")

            # 播放列表：episodeList 中的 nid 用于获取播放地址
            # vod_id 存为 vodId:nid 格式，playerContent 时拆分
            episodes = v.get("episodeList", [])
            if episodes:
                urls = []
                for ep in episodes:
                    nid = ep.get("nid", "")
                    name = ep.get("name", "")
                    if nid:
                        if not name:
                            name = f"第{ep.get('sort', '')}集"
                        urls.append(f"{name}${vod_id}:{nid}")
                if urls:
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
                        "vod_play_from": "金牌影院",
                        "vod_play_url": "#".join(urls),
                    }]
        except Exception as e:
            print(f'detailContent error: {e}')
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            params = {"keyword": key, "pageNum": int(pg), "pageSize": 20}
            data = self.api_get("/video/searchByWord", params)
            if data and data.get("code") == 200:
                d = data.get("data", {})
                # 搜索结果在 result 字段里
                search_data = d.get("result", d)
                for v in search_data.get("list", []):
                    result["list"].append({
                        "vod_id": str(v.get("vodId", "")),
                        "vod_name": v.get("vodName", ""),
                        "vod_pic": v.get("vodPic", ""),
                        "vod_remarks": v.get("vodRemarks", ""),
                    })
                result["pagecount"] = search_data.get("totalPage", 1)
        except Exception as e:
            print(f'searchContent error: {e}')
        return result

    def playerContent(self, flag, pid, vipFlags):
        result = {}
        try:
            # pid 格式: vodId:nid
            parts = pid.split(":")
            if len(parts) != 2:
                result["parse"] = 0
                result["url"] = ""
                return result
            vod_id, nid = parts[0], parts[1]

            data = self.api_get("/v2/video/episode/url", {"clientType": 3, "id": int(vod_id), "nid": int(nid)})
            if data and data.get("code") == 200:
                play_list = data.get("data", {}).get("list", [])
                # 优先取免费的（needLogin=false，480p标清）
                play_url = ""
                for item in play_list:
                    if not item.get("needLogin", True):
                        play_url = item.get("url", "")
                        break
                # 降级：取第一个
                if not play_url and play_list:
                    play_url = play_list[0].get("url", "")

                if play_url:
                    result["parse"] = 0
                    result["url"] = play_url
                    result["header"] = {"User-Agent": self.ua}
                    return result

            result["parse"] = 0
            result["url"] = ""
        except Exception as e:
            print(f'playerContent error: {e}')
            result["parse"] = 0
            result["url"] = ""
        return result

    def localProxy(self, params):
        return self.Mlocal(params)

    # ==================== API 签名与请求 ====================

    def make_sign(self, params):
        """生成签名和时间戳"""
        t = str(int(time.time() * 1000))
        # 过滤空值，按key排序
        sorted_items = sorted([(k, str(v)) for k, v in params.items() if v not in (None, "", 0)])
        # 拼接参数
        param_str = "&".join(f"{k}={v}" for k, v in sorted_items)
        # 追加 key 和 t
        if param_str:
            sign_str = f"{param_str}&key={self.sign_key}&t={t}"
        else:
            sign_str = f"key={self.sign_key}&t={t}"
        # MD5 再 SHA1
        md5_hex = hashlib.md5(sign_str.encode()).hexdigest()
        sign = hashlib.sha1(md5_hex.encode()).hexdigest()
        return sign, t

    def api_get(self, path, params):
        """调用API并返回JSON"""
        try:
            sign, t = self.make_sign(params)
            headers = {
                "sign": sign,
                "t": t,
                "deviceId": self.device_id,
                "authorization": "",
                "client-type": "3",
                "Content-Type": "application/json",
                "User-Agent": self.ua,
            }
            url = f"{self.api_base}{path}"
            res = self.fetch(url, params=params, headers=headers, timeout=15)
            if res:
                if isinstance(res, str):
                    return json.loads(res)
                return res.json()
        except Exception as e:
            print(f'api_get error: {e}')
        return None