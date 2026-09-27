#coding=utf-8
#!/usr/bin/python
import sys
sys.path.append('..')
from base.spider import Spider
import json
import re
import hashlib
import time
import os

class Spider(Spider):

	def getName(self):
		return "大马猴影视"

	def init(self, extend=""):
		self.host = "https://dmhyy.com"
		self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
		self.header = {
			"User-Agent": self.ua,
			"Referer": self.host,
			"x-platform": "web"
		}
		# 签名参数（从JS中提取）
		self.app_id = "cde75dbd61ce274e07e8ce29"
		self.finger = "505a0e62069a061e07698eb4b6327d88"
		self.secret_key = "9b1fccddb6f8e1b385de7e6e736e050144a7f3a208130fff"
		self.app_version = 1
		# type_id -> type_name 映射（API的type_id参数无效，必须用type_name）
		self.type_map = {
			"22": "剧集",
			"23": "电影",
			"24": "动漫",
			"25": "综艺"
		}

	def isVideoFormat(self, url):
		pass

	def manualVideoCheck(self):
		pass

	# ==================== 首页 ====================
	def homeContent(self, filter):
		result = {"class": [], "filters": {}, "list": []}
		try:
			data = self._fetch_json(self.host + "/api.php/web/index/home")
			if data and data.get("code") == 200:
				home_data = data.get("data", {})

				# 分类
				cats = home_data.get("categories", [])
				for cat in cats:
					result["class"].append({
						"type_name": cat.get("type_name", ""),
						"type_id": str(cat.get("type_id", ""))
					})

				# 筛选配置
				if filter and cats:
					filters = {}
					for cat in cats:
						tid = str(cat.get("type_id", ""))
						opts = cat.get("filter_options", {})
						f = []
						if opts.get("class"):
							f.append({
								"key": "class",
								"name": "类型",
								"value": [{"n": "全部", "v": ""}] + [{"n": v, "v": v} for v in opts["class"]]
							})
						if opts.get("area"):
							f.append({
								"key": "area",
								"name": "地区",
								"value": [{"n": "全部", "v": ""}] + [{"n": v, "v": v} for v in opts["area"]]
							})
						if opts.get("year"):
							f.append({
								"key": "year",
								"name": "年份",
								"value": [{"n": "全部", "v": ""}] + [{"n": v, "v": v} for v in opts["year"]]
							})
						filters[tid] = f
					result["filters"] = filters

				# 首页列表（优先 sectionList，备用 categories.videos）
				section_list = home_data.get("sectionList", [])
				if section_list:
					for section in section_list:
						for item in section.get("list", []):
							result["list"].append({
								"vod_id": str(item.get("vod_id", "")),
								"vod_name": item.get("vod_name", ""),
								"vod_pic": item.get("vod_pic", "").replace("\\/", "/"),
								"vod_remarks": item.get("vod_remarks", ""),
							})
				else:
					# 备用：从 categories 的 videos 中提取
					for cat in cats:
						for item in cat.get("videos", []):
							result["list"].append({
								"vod_id": str(item.get("vod_id", "")),
								"vod_name": item.get("vod_name", ""),
								"vod_pic": item.get("vod_pic", "").replace("\\/", "/"),
								"vod_remarks": item.get("vod_remarks", ""),
							})

		except Exception as e:
			print("homeContent error: {0}".format(e))
		return result

	def homeVideoContent(self):
		pass

	# ==================== 分类 ====================
	def categoryContent(self, tid, pg, filter, extend):
		result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 20, "total": 0}
		try:
			page = int(pg) if int(pg) >= 1 else 1
			# API的type_id参数无效，必须用type_name过滤
			type_name = self.type_map.get(str(tid), "")
			params_list = ["page={0}".format(page), "sort=hits"]
			if type_name:
				params_list.append("type_name={0}".format(type_name))

			if extend:
				for key, val in extend.items():
					if val and key != "tid":
						params_list.append("{0}={1}".format(key, val))

			url = self.host + "/api.php/web/filter/vod?" + "&".join(params_list)

			data = self._fetch_json(url)
			if data and data.get("code") == 200:
				items = data.get("data", [])
				result["list"] = []
				for item in items:
					result["list"].append({
						"vod_id": str(item.get("vod_id", "")),
						"vod_name": item.get("vod_name", ""),
						"vod_pic": item.get("vod_pic", "").replace("\\/", "/"),
						"vod_remarks": item.get("vod_remarks", ""),
					})
				result["page"] = page
				result["pagecount"] = data.get("pageCount", 9999) or 9999
				result["limit"] = data.get("limit", 20) or 20
				result["total"] = data.get("total", 999999) or 999999
		except Exception as e:
			print("categoryContent error: {0}".format(e))
		return result

	# ==================== 详情 ====================
	def detailContent(self, ids):
		result = {"list": []}
		try:
			vod_id = ids[0]

			# 详情接口（需要 x-platform: web 头才能返回 vod_play_url）
			detail_url = self.host + "/api.php/web/vod/get_detail?vod_id={0}".format(vod_id)
			data = self._fetch_json(detail_url)
			if not data or data.get("code") != 200 or not data.get("data"):
				return result

			item = data["data"][0]
			content = self._clean_html(item.get("vod_content", ""))
			remarks = item.get("vod_remarks", "")

			# 解析播放源
			play_from_str = item.get("vod_play_from", "")
			play_url_str = item.get("vod_play_url", "")
			vodplayer = data.get("vodplayer", [])

			play_from = ""
			play_url = ""
			if play_from_str and play_url_str:
				play_from, play_url = self._build_play_sources(
					vod_id, play_from_str, play_url_str, vodplayer
				)

			vod = {
				"vod_id": str(vod_id),
				"vod_name": item.get("vod_name", ""),
				"vod_pic": item.get("vod_pic", "").replace("\\/", "/"),
				"type_name": item.get("type_name", ""),
				"vod_year": str(item.get("vod_year", "")),
				"vod_area": item.get("vod_area", ""),
				"vod_lang": item.get("vod_lang", ""),
				"vod_remarks": remarks,
				"vod_actor": item.get("vod_actor", ""),
				"vod_director": item.get("vod_director", ""),
				"vod_content": content,
				"vod_play_from": play_from,
				"vod_play_url": play_url
			}
			result["list"].append(vod)
		except Exception as e:
			print("detailContent error: {0}".format(e))
		return result

	def _build_play_sources(self, vod_id, play_from_str, play_url_str, vodplayer):
		"""解析播放源列表，返回 (play_from, play_url)"""
		try:
			sources_from = [s.strip() for s in play_from_str.split("$$$") if s.strip()]
			sources_url = [s.strip() for s in play_url_str.split("$$$") if s.strip()]

			# 构建 vodplayer 映射 (from -> player_info)
			player_map = {}
			if vodplayer and isinstance(vodplayer, list):
				for p in vodplayer:
					frm = p.get("from", "")
					if frm:
						player_map[frm] = p

			play_from_list = []
			play_url_list = []
			src_idx = 0
			for i in range(min(len(sources_from), len(sources_url))):
				src_code = sources_from[i]
				src_urls = sources_url[i]

				# 检查平台支持
				p_info = player_map.get(src_code, {})
				platforms = p_info.get("display_platforms", "")
				if platforms and "web" not in platforms.lower():
					continue

				src_idx += 1
				# 显示名称：优先使用 vodplayer 的 show 字段
				show_name = p_info.get("show", "") or src_code

				# 解析剧集列表
				episodes = src_urls.split("#")
				ep_items = []
				for ep_idx, ep in enumerate(episodes, 1):
					parts = ep.split("$", 1)
					if len(parts) == 2:
						ep_title = parts[0].strip()
						# play_id 格式: vod_id-src_idx-ep_idx
						play_id = "{0}-{1}-{2}".format(vod_id, src_idx, ep_idx)
						ep_items.append("{0}${1}".format(ep_title, play_id))
					elif len(parts) == 1 and parts[0].strip():
						ep_title = "第{0}集".format(ep_idx)
						play_id = "{0}-{1}-{2}".format(vod_id, src_idx, ep_idx)
						ep_items.append("{0}${1}".format(ep_title, play_id))

				if ep_items:
					play_from_list.append(show_name)
					play_url_list.append("#".join(ep_items))

			return "$$$".join(play_from_list), "$$$".join(play_url_list)
		except Exception as e:
			print("_build_play_sources error: {0}".format(e))
			return "", ""

	# ==================== 搜索 ====================
	def searchContent(self, key, quick, pg="1"):
		result = {"list": []}
		try:
			page = int(pg) if int(pg) >= 1 else 1
			url = self.host + "/api.php/web/search/index?wd={0}&page={1}".format(key, page)
			data = self._fetch_json(url)
			if data and data.get("code") == 200:
				videos = []
				for item in data.get("data", []):
					videos.append({
						"vod_id": str(item.get("vod_id", "")),
						"vod_name": item.get("vod_name", ""),
						"vod_pic": item.get("vod_pic", "").replace("\\/", "/"),
						"vod_remarks": item.get("vod_remarks", ""),
						"type_name": item.get("type_name", "")
					})
				result = {"list": videos}
		except Exception as e:
			print("searchContent error: {0}".format(e))
		return result

	# ==================== 播放 ====================
	def playerContent(self, flag, id, vipFlags):
		result = {"parse": 0, "playUrl": "", "jx": 0, "url": "", "header": ""}
		try:
			# id 格式: vod_id-src_idx-ep_idx
			parts = id.split("-")
			if len(parts) >= 3:
				vod_id = parts[0]
				src_idx = int(parts[1])
				ep_idx = int(parts[2])
			else:
				return result

			# 重新获取详情，提取 episode URL、vodFrom 和 player_info
			episode_url, vod_from, p_info = self._get_episode_info(vod_id, src_idx, ep_idx)
			if not episode_url:
				return result

			# 通过 decode/url 获取播放URL
			decoded_url = self._decode_play_url(episode_url, vod_from)
			if decoded_url:
				# afterParse 处理：某些源需要特殊 UA/header
				play_url, req_header = self._apply_after_parse(p_info, decoded_url, vod_from)
				result["url"] = play_url
				result["header"] = req_header
				return result

			# 备用：如果是直链m3u8，直接返回
			if episode_url.startswith("http") and (".m3u8" in episode_url or ".mp4" in episode_url):
				result["url"] = episode_url
				result["header"] = json.dumps({"User-Agent": self.ua, "Referer": self.host})
				return result

		except Exception as e:
			print("playerContent error: {0}".format(e))
		return result

	def _apply_after_parse(self, p_info, url, vod_from):
		"""根据 vodplayer 配置处理 afterParse（特殊 UA/header）"""
		try:
			# 默认 headers
			req_headers = {"User-Agent": self.ua, "Referer": self.host}

			if not p_info:
				return url, json.dumps(req_headers)

			after_parse_status = p_info.get("after_parse_status", 0)
			after_parse_features = p_info.get("after_parse_features", "")
			after_parse_ua = p_info.get("after_parse_user_agent", "")
			after_parse_headers = p_info.get("after_parse_headers", "")

			# 检查是否需要 afterParse
			need_after_parse = (str(after_parse_status) == "1") and (
				bool(after_parse_ua.strip()) or bool(after_parse_headers.strip())
			)

			# 检查 URL 是否匹配 features
			if need_after_parse and after_parse_features:
				features = [f.strip().lower() for f in after_parse_features.split(",") if f.strip()]
				if features:
					url_lower = url.lower()
					if not any(f in url_lower for f in features):
						need_after_parse = False

			if not need_after_parse:
				return url, json.dumps(req_headers)

			# 需要 afterParse：直接返回解码URL，但使用特殊 UA 和 headers
			if after_parse_ua:
				req_headers["User-Agent"] = after_parse_ua
			if after_parse_headers:
				for line in after_parse_headers.split("\n"):
					if ":" in line:
						k, v = line.split(":", 1)
						req_headers[k.strip()] = v.strip()

			return url, json.dumps(req_headers)

		except Exception as e:
			print("_apply_after_parse error: {0}".format(e))
			return url, json.dumps({"User-Agent": self.ua, "Referer": self.host})

	def _get_episode_info(self, vod_id, src_idx, ep_idx):
		"""从详情接口获取指定集数的播放URL、源代码和player_info"""
		try:
			detail_url = self.host + "/api.php/web/vod/get_detail?vod_id={0}".format(vod_id)
			data = self._fetch_json(detail_url)
			if not data or data.get("code") != 200 or not data.get("data"):
				return None, None, None

			item = data["data"][0]
			play_from_str = item.get("vod_play_from", "")
			play_url_str = item.get("vod_play_url", "")
			vodplayer = data.get("vodplayer", [])

			if not play_from_str or not play_url_str:
				return None, None, None

			sources_from = [s.strip() for s in play_from_str.split("$$$") if s.strip()]
			sources_url = [s.strip() for s in play_url_str.split("$$$") if s.strip()]

			# 构建 vodplayer 映射
			player_map = {}
			if vodplayer and isinstance(vodplayer, list):
				for p in vodplayer:
					frm = p.get("from", "")
					if frm:
						player_map[frm] = p

			# 遍历源，跳过不支持 web 的，找到第 src_idx 个有效源
			valid_idx = 0
			for i in range(min(len(sources_from), len(sources_url))):
				src_code = sources_from[i]
				src_urls = sources_url[i]

				p_info = player_map.get(src_code, {})
				platforms = p_info.get("display_platforms", "")
				if platforms and "web" not in platforms.lower():
					continue

				valid_idx += 1
				if valid_idx != src_idx:
					continue

				# 找到目标源，解析剧集
				episodes = src_urls.split("#")
				if ep_idx < 1 or ep_idx > len(episodes):
					return None, None, None

				ep = episodes[ep_idx - 1]
				parts = ep.split("$", 1)
				if len(parts) == 2:
					return parts[1].strip(), src_code, p_info
				elif len(parts) == 1:
					return parts[0].strip(), src_code, p_info
				return None, None, None

			return None, None, None
		except Exception as e:
			print("_get_episode_info error: {0}".format(e))
			return None, None, None

	def _decode_play_url(self, episode_url, vod_from):
		"""通过站内 decode/url 接口获取播放URL"""
		try:
			# 生成签名（时间戳使用毫秒，与JS Date.now()一致）
			timestamp = int(time.time() * 1000)
			nonce = os.urandom(16).hex()
			param_str = "finger={0}&id={1}&nonce={2}&sk={3}&time={4}&v={5}".format(
				self.finger, self.app_id, nonce, self.secret_key, timestamp, self.app_version
			)
			sign = hashlib.sha256(param_str.encode('utf-8')).hexdigest().upper()

			# protobuf 编码（Field 1 = episode_url, Field 2 = vod_from）
			protobuf_data = (
				self._pb_str(1, episode_url) +
				self._pb_str(2, vod_from or "") +
				self._pb_varint(3, timestamp) +
				self._pb_str(4, nonce) +
				self._pb_str(5, sign) +
				self._pb_str(6, self.app_id) +
				self._pb_varint(7, self.app_version)
			)

			# POST 请求 headers
			req_headers = dict(self.header)
			req_headers["Content-Type"] = "application/x-protobuf"
			req_headers["Accept"] = "application/x-protobuf"

			decode_api = self.host + "/api.php/web/decode/url"

			# 尝试多种方式发送POST请求
			result = None

			# 方式1：使用 self.fetch（data参数触发POST）
			try:
				rsp = self.fetch(decode_api, headers=req_headers, data=protobuf_data, method='post')
				if rsp and rsp.content:
					result = self._parse_pb_response(rsp.content)
			except Exception as e1:
				print("_decode_play_url fetch error: {0}".format(e1))

			# 方式2：如果方式1失败或结果无效，使用 urllib.request
			if not result or result.get("code") != 1:
				try:
					import urllib.request as ur
					import ssl as ssl_mod
					ctx = ssl_mod.create_default_context()
					ctx.check_hostname = False
					ctx.verify_mode = ssl_mod.CERT_NONE
					req = ur.Request(decode_api, data=protobuf_data, headers=req_headers, method='POST')
					with ur.urlopen(req, timeout=15, context=ctx) as response:
						resp_data = response.read()
					if resp_data:
						result = self._parse_pb_response(resp_data)
				except Exception as e2:
					print("_decode_play_url urllib error: {0}".format(e2))

			# 方式3：如果仍然失败，尝试 requests
			if (not result or result.get("code") != 1):
				try:
					import requests as req_lib
					rsp = req_lib.post(decode_api, headers=req_headers, data=protobuf_data, timeout=15)
					if rsp.content:
						result = self._parse_pb_response(rsp.content)
				except Exception as e3:
					print("_decode_play_url requests error: {0}".format(e3))

			if result and result.get("code") == 1 and result.get("url"):
				return result["url"]
			else:
				print("_decode_play_url failed: vod_from={0}, result={1}".format(
					vod_from, json.dumps(result, ensure_ascii=False) if result else "None"))

		except Exception as e:
			print("_decode_play_url error: {0}".format(e))
		return None

	def _pb_varint(self, field, value):
		"""protobuf varint编码"""
		value = int(value)
		tag = (field << 3) | 0
		result = bytearray()
		while tag > 0x7f:
			result.append((tag & 0x7f) | 0x80)
			tag >>= 7
		result.append(tag)
		while value > 0x7f:
			result.append((value & 0x7f) | 0x80)
			value >>= 7
		result.append(value)
		return bytes(result)

	def _pb_str(self, field, value):
		"""protobuf length-delimited string编码"""
		tag = (field << 3) | 2
		result = bytearray()
		while tag > 0x7f:
			result.append((tag & 0x7f) | 0x80)
			tag >>= 7
		result.append(tag)
		encoded = value.encode('utf-8')
		length = len(encoded)
		while length > 0x7f:
			result.append((length & 0x7f) | 0x80)
			length >>= 7
		result.append(length)
		result.extend(encoded)
		return bytes(result)

	def _parse_pb_response(self, data):
		"""解析protobuf响应"""
		result = {}
		try:
			i = 0
			while i < len(data):
				tag = data[i]
				field_num = tag >> 3
				wire_type = tag & 0x07
				i += 1
				if wire_type == 2:
					length = 0
					shift = 0
					while i < len(data):
						b = data[i]
						length |= (b & 0x7f) << shift
						i += 1
						if not (b & 0x80):
							break
						shift += 7
					value = data[i:i+length].decode('utf-8', errors='replace')
					i += length
					if field_num == 1:
						result["code"] = int(value) if value.isdigit() else value
					elif field_num == 2:
						result["msg"] = value
					elif field_num == 3:
						result["url"] = value
				elif wire_type == 0:
					value = 0
					shift = 0
					while i < len(data):
						b = data[i]
						value |= (b & 0x7f) << shift
						i += 1
						if not (b & 0x80):
							break
						shift += 7
					if field_num == 1:
						result["code"] = value
		except Exception as e:
			print("_parse_pb_response error: {0}".format(e))
		return result

	# ==================== 工具方法 ====================
	def _fetch_json(self, url):
		try:
			rsp = self.fetch(url, headers=self.header)
			return json.loads(rsp.text)
		except Exception as e:
			print("_fetch_json error: {0}".format(e))
			return None

	def _clean_html(self, text):
		if not text:
			return ""
		text = re.sub(r'<[^>]+>', '', text)
		text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
		text = text.strip()
		return text

	cats = [
		{"type_name": "剧集", "type_id": "22"},
		{"type_name": "电影", "type_id": "23"},
		{"type_name": "动漫", "type_id": "24"},
		{"type_name": "综艺", "type_id": "25"},
	]

	config = {
		"player": {},
		"filter": {}
	}
	header = {}

	def localProxy(self, param):
		return [200, "video/MP2T", "", ""]
