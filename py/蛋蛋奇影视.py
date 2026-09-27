#coding=utf-8
#!/usr/bin/python
import sys
sys.path.append('..')
from base.spider import Spider
import json
import re
import base64
import hashlib
import urllib.parse
from json.decoder import JSONDecoder
from urllib.parse import quote, unquote

class Spider(Spider):

	def getName(self):
		return "蛋蛋奇影视"

	def init(self, extend=""):
		self.host = "https://www.dandanqi.cc"
		self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
		self.mobile_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
		self.header = {
			"User-Agent": self.ua,
			"Referer": self.host + "/",
				}
		self.cookie_header = dict(self.header)
		self.cookie_header["Cookie"] = "accessAuth=ok"

	def isVideoFormat(self, url):
		pass

	def manualVideoCheck(self):
		pass

	# ==================== 网络请求工具 ====================
	def _fetch_html(self, url):
		try:
			rsp = self.fetch(url, headers=self.cookie_header)
			return rsp.text
		except Exception as e:
			print("_fetch_html error: {0}".format(e))
			return ""

	def _post_html(self, url, data):
		try:
			rsp = self.post(url, data=data, headers=self.cookie_header)
			return rsp.text
		except Exception as e:
			print("_post_html error: {0}".format(e))
			return ""

	# ==================== 首页 ====================
	def homeContent(self, filter):
		result = {"class": [], "filters": {}, "list": []}
		try:
			classes = []
			for tid, tname in self.cat_map.items():
				classes.append({"type_name": tname, "type_id": tid})
			result["class"] = classes

			if filter:
				result["filters"] = self._build_filters()

			html = self._fetch_html(self.host)
			if html:
				videos = self._extract_videos_from_html(html)
				result["list"] = videos

		except Exception as e:
			print("homeContent error: {0}".format(e))
		return result

	def homeVideoContent(self):
		pass

	# ==================== 筛选器构建 ====================
	def _build_filters(self):
		"""构建筛选器"""
		filters = {}

		area_list = [
			{"n": "全部", "v": ""},
			{"n": "大陆", "v": "大陆"},
			{"n": "香港", "v": "香港"},
			{"n": "台湾", "v": "台湾"},
			{"n": "美国", "v": "美国"},
			{"n": "法国", "v": "法国"},
			{"n": "英国", "v": "英国"},
			{"n": "日本", "v": "日本"},
			{"n": "韩国", "v": "韩国"},
			{"n": "德国", "v": "德国"},
			{"n": "泰国", "v": "泰国"},
			{"n": "印度", "v": "印度"},
			{"n": "意大利", "v": "意大利"},
			{"n": "西班牙", "v": "西班牙"},
			{"n": "加拿大", "v": "加拿大"},
			{"n": "其他", "v": "其他"},
		]

		year_list = [
			{"n": "全部", "v": ""},
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
			{"n": "2010", "v": "2010"},
		]

		sort_list = [
			{"n": "默认", "v": ""},
			{"n": "按时间", "v": "time"},
			{"n": "按人气", "v": "hits"},
			{"n": "按评分", "v": "score"},
		]

		for tid in ["dianying", "juji", "zongyi", "dongman"]:
			filters[tid] = [
				{"key": "area", "name": "地区", "value": area_list},
				{"key": "year", "name": "年份", "value": year_list},
				{"key": "sort", "name": "排序", "value": sort_list},
			]

		return filters

	# ==================== 分类 ====================
	def _build_show_url(self, tid, pg, extend):
		"""构建筛选URL
		格式: /show/{tid}-{area}-{order}-{class}-{lang}-{letter}-{空}-{空}-{page}-{空}-{空}-{year}.html
		11段，用-分隔
		"""
		page = str(int(pg)) if int(pg) >= 1 else "1"

		area = ""
		year = ""
		order = ""

		if extend:
			area = quote(extend.get("area", "")) if extend.get("area", "") else ""
			year = extend.get("year", "")
			order = quote(extend.get("sort", "")) if extend.get("sort", "") else ""

		# 11段: tid-area-order-class-lang-letter-空-空-page-空-空-year
		parts = [tid, area, order, "", "", "", "", "", page, "", "", year]
		url = "{0}/show/{1}.html".format(self.host, "-".join(parts))
		return url

	def categoryContent(self, tid, pg, filter, extend):
		result = {"list": [], "page": int(pg), "pagecount": 999, "limit": 24, "total": 999999}
		try:
			cat_url = self._build_show_url(tid, pg, extend or {})
			html = self._fetch_html(cat_url)
			if html:
				videos = self._extract_videos_from_html(html)
				result["list"] = videos
			result["page"] = int(pg)
		except Exception as e:
			print("categoryContent error: {0}".format(e))
		return result

	# ==================== 详情 ====================
	def detailContent(self, ids):
		result = {"list": []}
		try:
			vod_id_str = ids[0]
			detail_url = "{0}/detail/{1}.html".format(self.host, vod_id_str)
			html = self._fetch_html(detail_url)
			if not html:
				return result

			detail = self._extract_detail(html, vod_id_str)
			if detail:
				result["list"].append(detail)

		except Exception as e:
			print("detailContent error: {0}".format(e))
		return result

	# ==================== 搜索 ====================
	def searchContent(self, key, quick, pg="1"):
		result = {"list": []}
		try:
			page = int(pg) if int(pg) >= 1 else 1
			search_url = "{0}/search/-------------.html".format(self.host)
			if page > 1:
				search_url = "{0}/search/{1}-------------.html".format(self.host, page)

			post_data = {"wd": key}
			html = self._post_html(search_url, post_data)
			if not html:
				return result

			videos = self._extract_search_videos(html)
			result["list"] = videos

		except Exception as e:
			print("searchContent error: {0}".format(e))
		return result

	# ==================== 播放 ====================
	def playerContent(self, flag, id, vipFlags):
		result = {"parse": 0, "playUrl": "", "jx": 0, "url": "", "header": ""}
		try:
			parts = id.split("-")
			if len(parts) < 3:
				return result

			detail_id = parts[0]
			src_idx = parts[1]
			ep_idx = parts[2]

			play_page_url = "{0}/play/{1}-{2}-{3}.html".format(self.host, detail_id, src_idx, ep_idx)
			html = self._fetch_html(play_page_url)
			if not html:
				return result

			vid = self._extract_player_url(html)
			if not vid:
				return result

			# 通过ddplay API解析并解密真实视频URL
			video_url = self._parse_video(vid)
			if video_url and video_url.startswith("http"):
				result["parse"] = 0
				result["url"] = video_url
				result["header"] = json.dumps({"User-Agent": self.ua, "Referer": self.host + "/"})
				return result

			# 如果API解析失败，回退到ddplay iframe方式
			ddplay_url = "{0}/ddplay/index.php?vid={1}".format(self.host, vid)
			result["parse"] = 1
			result["playUrl"] = ddplay_url
			result["header"] = json.dumps({"User-Agent": self.ua, "Referer": play_page_url})
			return result

		except Exception as e:
			print("playerContent error: {0}".format(e))
		return result

	# ==================== 提取方法 ====================

	def _extract_videos_from_html(self, html):
		"""从HTML中提取视频列表（首页/分类页通用）"""
		videos = []
		try:
			items = re.findall(
				r'<a[^>]*href=["\'](/detail/([^"\'\.]+)\.html)["\'][^>]*title=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*module-poster-item[^"\']*["\'][^>]*>.*?<div[^>]*class=["\']module-item-note["\'][^>]*>([^<]*)</div>.*?<img[^>]*data-original=["\']([^"\']+)["\']',
				html, re.S
			)
			for href, detail_id, title, note, pic in items:
				videos.append({
					"vod_id": detail_id,
					"vod_name": title.strip(),
					"vod_pic": pic,
					"vod_remarks": note.strip()
				})

			if not videos:
				seen = set()
				for m in re.finditer(r'<a[^>]*href=["\'](/detail/([^"\'\.]+)\.html)["\'][^>]*class=["\'][^"\']*module-card-item-poster[^"\']*["\'][^>]*>', html):
					href = m.group(1)
					detail_id = m.group(2)
					if detail_id in seen:
						continue
					seen.add(detail_id)
					segment = html[m.start():m.start()+1200]
					title_m = re.search(r'<a[^>]*href=["\']' + re.escape(href) + r'["\'][^>]*class=["\'][^"\']*module-card-item-title[^"\']*["\'][^>]*>([^<]+)</a>', segment)
					note_m = re.search(r'<div[^>]*class=["\']module-item-note["\'][^>]*>([^<]*)</div>', segment)
					pic_m = re.search(r'data-original=["\']([^"\']+)["\']', segment)
					if not title_m:
						alt_m = re.search(r'alt=["\']([^"\']+)["\']', segment)
						title = alt_m.group(1).strip() if alt_m else ""
					else:
						title = title_m.group(1).strip()
					note = note_m.group(1).strip() if note_m else ""
					pic = pic_m.group(1) if pic_m else ""
					if title:
						videos.append({
							"vod_id": detail_id,
							"vod_name": title,
							"vod_pic": pic,
							"vod_remarks": note
						})
		except Exception as e:
			print("_extract_videos_from_html error: {0}".format(e))
		return videos

	def _extract_search_videos(self, html):
		"""从搜索结果HTML中提取视频"""
		videos = []
		try:
			seen = set()
			for m in re.finditer(r'<a[^>]*href=["\'](/detail/([^"\'\.]+)\.html)["\'][^>]*class=["\'][^"\']*module-card-item-poster[^"\']*["\'][^>]*>', html):
				href = m.group(1)
				detail_id = m.group(2)
				if detail_id in seen:
					continue
				seen.add(detail_id)
				segment = html[m.start():m.start()+1200]
				title = ""
				title_m = re.search(r'<a[^>]*href=["\']' + re.escape(href) + r'["\'][^>]*class=["\'][^"\']*module-card-item-title[^"\']*["\'][^>]*>([^<]+)</a>', segment)
				if title_m:
					title = title_m.group(1).strip()
				else:
					alt_m = re.search(r'alt=["\']([^"\']+)["\']', segment)
					if alt_m:
						title = alt_m.group(1).strip()
				note_m = re.search(r'<div[^>]*class=["\']module-item-note["\'][^>]*>([^<]*)</div>', segment)
				pic_m = re.search(r'data-original=["\']([^"\']+)["\']', segment)
				note = note_m.group(1).strip() if note_m else ""
				pic = pic_m.group(1) if pic_m else ""
				if title:
					videos.append({
						"vod_id": detail_id,
						"vod_name": title,
						"vod_pic": pic,
						"vod_remarks": note
					})
		except Exception as e:
			print("_extract_search_videos error: {0}".format(e))
		return videos

	def _extract_detail(self, html, vod_id):
		"""从详情页HTML提取视频详情"""
		try:
			title = ""
			title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
			if title_match:
				title = title_match.group(1).strip()

			desc = ""
			desc_match = re.search(r'class=["\'][^"\']*module-info-introduction-content["\'][^>]*>(.*?)</div>', html, re.S)
			if desc_match:
				desc = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()

			pic = ""
			cover_match = re.search(r'<img[^>]*class=["\'][^"\']*cover["\'][^>]*src=["\']([^"\']+)["\']', html)
			if cover_match:
				pic = cover_match.group(1)
			if not pic:
				cover_match2 = re.search(r'<img[^>]*class=["\'][^"\']*cover["\'][^>]*data-original=["\']([^"\']+)["\']', html)
				if cover_match2:
					pic = cover_match2.group(1)

			director = ""
			writer = ""
			actor = ""
			vod_year = ""
			vod_area = ""
			vod_remarks = ""
			vod_douban = ""

			for m in re.finditer(r'class=["\'][^"\']*module-info-item-title["\'][^>]*>([^<]+)<', html):
				label = m.group(1).strip().rstrip('：').rstrip(':').strip()
				segment = html[m.end():m.end()+5000]
				content_match = re.search(r'class=["\'][^"\']*module-info-item-content["\'][^>]*>(.*?)</div>', segment, re.S)
				if not content_match:
					continue
				content_html = content_match.group(1)
				names = re.findall(r'<a[^>]*>([^<]+)</a>', content_html)
				pure_text = re.sub(r'<[^>]+>', '', content_html).strip()

				if label == "导演" and names:
					director = ",".join([n.strip() for n in names])
				elif label == "编剧" and names:
					writer = ",".join([n.strip() for n in names])
				elif label == "主演" and names:
					actor = ",".join([n.strip() for n in names])
				elif label == "上映" and pure_text:
					year_m = re.search(r'(\d{4})', pure_text)
					if year_m:
						vod_year = year_m.group(1)
					area_m = re.search(r'\(([^)]+)\)', pure_text)
					if area_m:
						vod_area = area_m.group(1)
				elif label == "更新" and pure_text:
					vod_remarks = pure_text
				elif label == "集数" and pure_text:
					if not vod_remarks:
						vod_remarks = pure_text
				elif label == "豆瓣" and pure_text:
					vod_douban = pure_text

			type_name = ""
			type_tag = re.search(r'<div[^>]*class=["\'][^"\']*module-card-item-class["\'][^>]*>([^<]+)<', html)
			if type_tag:
				type_name = type_tag.group(1).strip()

			play_from, play_url = self._extract_play_info(html, vod_id)

			return {
				"vod_id": vod_id,
				"vod_name": title,
				"vod_pic": pic,
				"type_name": type_name,
				"vod_year": vod_year,
				"vod_area": vod_area,
				"vod_remarks": vod_remarks,
				"vod_actor": actor,
				"vod_director": director,
				"vod_content": desc,
				"vod_play_from": play_from,
				"vod_play_url": play_url,
				"vod_douban_score": vod_douban if vod_douban else ""
			}

		except Exception as e:
			print("_extract_detail error: {0}".format(e))
			return None

	def _extract_play_info(self, html, vod_id):
		"""从详情页HTML提取播放源和集数"""
		try:
			play_from_list = []
			play_url_list = []

			source_tabs = []
			tab_divs = re.findall(
				r'<div[^>]*class=["\'][^"\']*module-tab-item[^"\']*tab-item["\'][^>]*data-dropdown-value=["\']([^"\']+)["\'][^>]*>',
				html
			)
			if tab_divs:
				source_tabs = tab_divs

			all_ep_links = re.findall(
				r'<a[^>]*href=["\'](/play/([^"\']+))["\'][^>]*>(.*?)</a>',
				html, re.S
			)

			source_eps = {}
			for href, href_id, content in all_ep_links:
				text = re.sub(r'<[^>]+>', '', content).strip()
				if text in ["立即播放", "立刻播放", ""]:
					continue
				parts = href_id.split("-")
				if len(parts) >= 3:
					src_idx = parts[-2]
					ep_idx = parts[-1].replace(".html", "")
					if src_idx not in source_eps:
						source_eps[src_idx] = []
					source_eps[src_idx].append((text, href_id))

			for src_idx in sorted(source_eps.keys(), key=lambda x: int(x)):
				episodes = source_eps[src_idx]
				src_name = "线路{0}".format(src_idx)
				if source_tabs and int(src_idx) <= len(source_tabs):
					src_name = source_tabs[int(src_idx) - 1]

				ep_items = []
				for ep_text, href_id in episodes:
					parts = href_id.split("-")
					if len(parts) >= 3:
						ep_idx = parts[-1].replace(".html", "")
						play_id = "{0}-{1}-{2}".format(vod_id, src_idx, ep_idx)
						ep_items.append("{0}${1}".format(ep_text, play_id))

				if ep_items:
					play_from_list.append(src_name)
					play_url_list.append("#".join(ep_items))

			return "$$$".join(play_from_list), "$$$".join(play_url_list)

		except Exception as e:
			print("_extract_play_info error: {0}".format(e))
			return "", ""

	def _extract_player_url(self, html):
		"""从播放页HTML提取player_aaaa中的视频URL"""
		try:
			idx = html.find('var player_aaaa=')
			if idx < 0:
				return ""
			start = idx + len('var player_aaaa=')
			data, _ = JSONDecoder().raw_decode(html, start)
			url = data.get('url', '')
			# 检查是否需要base64解码
			encrypt = str(data.get('encrypt', '0'))
			if encrypt == '2':
				url = base64.b64decode(url).decode('utf-8')
			return url
		except Exception as e:
			print("_extract_player_url error: {0}".format(e))
			return ""

	def _parse_video(self, vid):
		"""通过ddplay解析接口获取并解密真实视频URL
		API返回urlmode=1或urlmode=2，分别用Decode1和Decode2解密
		使用手机UA提高urlmode=2命中率，同时支持两种模式确保100%成功
		"""
		import time
		api_url = "{0}/ddplay/api.php".format(self.host)
		api_header = {
			"User-Agent": self.mobile_ua,
			"Referer": self.host + "/",
			"Cookie": "accessAuth=ok",
			"X-Requested-With": "XMLHttpRequest"
		}
		for attempt in range(5):
			try:
				rsp = self.post(api_url, data={"vid": vid}, headers=api_header)
				if not rsp or rsp.status_code != 200:
					time.sleep(0.5)
					continue

				api_data = json.loads(rsp.text)
				if api_data.get("code") != 200:
					time.sleep(0.5)
					continue

				data_obj = api_data.get("data", {})
				urlmode = data_obj.get("urlmode", 0)
				encrypted_url = data_obj.get("url", "")
				if not encrypted_url:
					time.sleep(0.5)
					continue

				# 根据urlmode选择解密算法
				if urlmode == 1:
					decrypted = self._decode1(encrypted_url)
				else:
					decrypted = self._decode2(encrypted_url)

				if decrypted and decrypted.startswith("http") and "baidu.com" not in decrypted:
					return decrypted

				time.sleep(0.5)
			except Exception as e:
				print("_parse_video error: {0}".format(e))
				time.sleep(0.5)
		return None

	def _decode1(self, encrypted):
		"""Decode1解密(urlmode=1): base64解码 + XOR(md5('test')) + base64解码 + 字符替换"""
		try:
			key = hashlib.md5(b'test').hexdigest()
			key_bytes = key.encode('latin-1')

			# Step 1: base64 decode
			decoded = base64.b64decode(encrypted)

			# Step 2: XOR with md5('test')
			code_bytes = bytearray()
			for i in range(len(decoded)):
				k = i % len(key_bytes)
				code_bytes.append(decoded[i] ^ key_bytes[k])

			# Step 3: XOR结果再base64 decode
			code_str = code_bytes.decode('latin-1')
			decoded_str = base64.b64decode(code_str).decode('utf-8')

			# Step 4: Split by '/'
			parts = decoded_str.split('/')
			if len(parts) < 3:
				return ""

			# Step 5: 解析JSON数组
			array_from_part1 = json.loads(base64.b64decode(parts[1]).decode('utf-8'))
			array_from_part0 = json.loads(base64.b64decode(parts[0]).decode('utf-8'))

			# Step 6: base64 decode parts[2+]
			combined = '/'.join(parts[2:])
			text = base64.b64decode(combined).decode('utf-8')

			# Step 7: 字符替换(deString)
			result = []
			for c in text:
				if c.isalpha() and c in array_from_part0:
					try:
						idx = array_from_part1.index(c)
						result.append(array_from_part0[idx])
					except ValueError:
						result.append(c)
				else:
					result.append(c)

			return ''.join(result)
		except Exception as e:
			print("_decode1 error: {0}".format(e))
			return ""

	def _decode2(self, encrypted):
		"""Decode2解密：先base64解码，再按自定义字符集替换"""
		try:
			step1 = base64.b64decode(encrypted).decode("latin-1")
			charset = "PXhw7UT1B0a9kQDKZsjIASmOezxYG4CHo5Jyfg2b8FLpEvRr3WtVnlqMidu6cN"
			result = []
			for i in range(1, len(step1), 3):
				ch = step1[i]
				idx = charset.find(ch)
				if idx == -1:
					result.append(ch)
				else:
					result.append(charset[(idx + 0x3b) % 0x3e])
			return "".join(result)
		except Exception as e:
			print("_decode2 error: {0}".format(e))
			return ""

	def _find_direct_video(self, html):
		"""直接从播放页HTML查找视频链接"""
		try:
			for pattern in [r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', r'(https?://[^\s"\'<>]+\.flv[^\s"\'<>]*)']:
				m = re.search(pattern, html)
				if m:
					return m.group(1)
		except Exception as e:
			print("_find_direct_video error: {0}".format(e))
		return None

	# ==================== 配置 ====================
	cat_map = {
		"dianying": "电影",
		"juji": "剧集",
		"zongyi": "综艺",
		"dongman": "动漫"
	}

	cats = [
		{"type_name": "电影", "type_id": "dianying"},
		{"type_name": "剧集", "type_id": "juji"},
		{"type_name": "综艺", "type_id": "zongyi"},
		{"type_name": "动漫", "type_id": "dongman"}
	]

	config = {
		"player": {},
	"filter": {}
	}
	header = {}

	def localProxy(self, param):
		return [200, "video/MP2T", "", ""]