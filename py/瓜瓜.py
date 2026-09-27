#coding=utf-8
#!/usr/bin/python
# 瓜子影视 (www.guaziys.net) - 苹果CMS V10 (Maccms)
# 模板: mizhiady
# API关闭，通过HTML解析获取数据
# 播放: player_aaaa变量中含直链m3u8/mp4
# 播放区用playlist div（非module-play-list-content）
import sys
sys.path.append('..')
from base.spider import Spider
import re
import json
from urllib.parse import quote


class Spider(Spider):

    def getName(self):
        return "瓜子影视"

    def init(self, extend=""):
        self.host = "https://www.guaziys.net"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.header = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
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

    # ==================== 通用请求 ====================
    def _req(self, path):
        url = self.host + path
        try:
            rsp = self.fetch(url, headers=self.header)
            if rsp.status_code == 200:
                return rsp.text
        except:
            pass
        return ""

    def _req_play(self, path):
        url = self.host + path
        headers = dict(self.header)
        headers["Referer"] = self.host + "/"
        try:
            rsp = self.fetch(url, headers=headers)
            if rsp.status_code == 200:
                return rsp.text
        except:
            pass
        return ""

    # ==================== 分类配置 ====================
    cats = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "电视剧", "type_id": "2"},
        {"type_name": "动漫", "type_id": "3"},
        {"type_name": "综艺", "type_id": "4"},
        {"type_name": "短剧", "type_id": "21"},
        {"type_name": "AI漫剧", "type_id": "22"},
    ]

    def _build_filters(self):
        filters = {}
        # 电影/电视剧/动漫/综艺/短剧/AI漫剧 通用筛选
        common = [
            {"key": "class", "name": "类型", "value": [
                {"n": "全部", "v": ""},
                {"n": "动作", "v": "动作"},
                {"n": "喜剧", "v": "喜剧"},
                {"n": "爱情", "v": "爱情"},
                {"n": "科幻", "v": "科幻"},
                {"n": "恐怖", "v": "恐怖"},
                {"n": "剧情", "v": "剧情"},
                {"n": "战争", "v": "战争"},
                {"n": "犯罪", "v": "犯罪"},
                {"n": "奇幻", "v": "奇幻"},
                {"n": "冒险", "v": "冒险"},
                {"n": "悬疑", "v": "悬疑"},
                {"n": "惊悚", "v": "惊悚"},
                {"n": "动画", "v": "动画"},
                {"n": "武侠", "v": "武侠"},
                {"n": "古装", "v": "古装"},
                {"n": "纪录片", "v": "纪录片"},
            ]},
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""},
                {"n": "中国大陆", "v": "中国大陆"},
                {"n": "中国香港", "v": "中国香港"},
                {"n": "中国台湾", "v": "中国台湾"},
                {"n": "美国", "v": "美国"},
                {"n": "韩国", "v": "韩国"},
                {"n": "日本", "v": "日本"},
                {"n": "泰国", "v": "泰国"},
                {"n": "英国", "v": "英国"},
                {"n": "法国", "v": "法国"},
                {"n": "其他", "v": "其他"},
            ]},
            {"key": "year", "name": "年份", "value": [
                {"n": "全部", "v": ""},
                {"n": "2026", "v": "2026"},
                {"n": "2025", "v": "2025"},
                {"n": "2024", "v": "2024"},
                {"n": "2023", "v": "2023"},
                {"n": "2022", "v": "2022"},
                {"n": "2021", "v": "2021"},
                {"n": "2020", "v": "2020"},
                {"n": "2019", "v": "2019"},
                {"n": "2018", "v": "2018"},
                {"n": "更早", "v": "0"},
            ]},
            {"key": "by", "name": "排序", "value": [
                {"n": "最新", "v": "time"},
                {"n": "最热", "v": "hits"},
                {"n": "评分", "v": "score"},
            ]},
        ]
        for tid in ["1", "2", "3", "4", "21", "22"]:
            filters[tid] = common
        return filters

    # ==================== 通用HTML解析 ====================
    def _parse_video_list(self, html):
        """解析视频列表，兼容海报式/卡片式/轮播图"""
        videos = []
        seen_ids = set()

        all_links = re.findall(r'href="(/index\.php/vod/detail/id/(\d+)\.html)"', html)

        for url, vid in all_links:
            vid_str = str(vid)
            if vid_str in seen_ids:
                continue
            seen_ids.add(vid_str)

            title = ""
            pic = ""
            note = ""

            link_pos = html.find('/index.php/vod/detail/id/{0}.html'.format(vid))
            if link_pos >= 0:
                nearby = html[max(0, link_pos - 200):link_pos + 2000]

                # 标题: 优先title属性，其次img alt，再次文本节点
                m = re.search(r'href="/index\.php/vod/detail/id/{0}\.html"[^>]*title="([^"]*)"'.format(vid), html)
                if not m:
                    m = re.search(r'alt="([^"]*)"', nearby)
                if not m:
                    m = re.search(r'title-text[^>]*>([^<]+)', nearby)
                if m:
                    title = m.group(1).strip()

                # 图片
                m = re.search(r'data-original="([^"]*)"', nearby)
                if not m:
                    m = re.search(r'<img[^>]+src="(https?://[^"]+)"', nearby)
                if m:
                    pic = m.group(1)

                # 备注
                m = re.search(r'pic-text[^>]*">([^<]*)', nearby)
                if not m:
                    m = re.search(r'vodlist__tip[^>]*">([^<]*)', nearby)
                if m:
                    note = m.group(1).strip()

            videos.append({
                "vod_id": vid_str,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": note,
            })

        return videos

    # ==================== 首页 ====================
    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        try:
            result["class"] = self.cats
            if filter:
                result["filters"] = self._build_filters()

            html = self._req("/")
            if html:
                result["list"] = self._parse_video_list(html)
        except Exception as e:
            print("homeContent error: {0}".format(e))
        return result

    def homeVideoContent(self):
        pass

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 72, "total": 0}
        try:
            page = int(pg) if pg else 1

            # 统一使用 show 路由(支持翻页):
            # /index.php/vod/show/id/{tid}/page/{page}.html
            # /index.php/vod/show/class/{类型}/area/{地区}/year/{年份}/by/{排序}/id/{分类id}/page/{页码}.html
            has_filter = extend and any(v for v in extend.values() if v)

            if has_filter:
                parts = ["/index.php/vod/show"]
                if extend.get("class"):
                    parts.append("class/{0}".format(quote(str(extend["class"]))))
                if extend.get("area"):
                    parts.append("area/{0}".format(quote(str(extend["area"]))))
                if extend.get("year"):
                    parts.append("year/{0}".format(str(extend["year"])))
                if extend.get("by"):
                    parts.append("by/{0}".format(str(extend["by"])))
                parts.append("id/{0}".format(tid))
                if page > 1:
                    parts.append("page/{0}".format(page))
                path = "/".join(parts) + ".html"
            else:
                if page <= 1:
                    path = "/index.php/vod/show/id/{0}.html".format(tid)
                else:
                    path = "/index.php/vod/show/id/{0}/page/{1}.html".format(tid, page)

            html = self._req(path)
            if html:
                videos = self._parse_video_list(html)
                result["list"] = videos
                result["page"] = page
                result["total"] = len(videos)
                # 从页面分页链接中提取最大页码
                page_links = re.findall(r'/index\.php/vod/show[^"]*?page/(\d+)\.html', html)
                if page_links:
                    max_page = max(int(p) for p in page_links)
                    result["pagecount"] = max_page
                else:
                    # 没有分页链接则判断是否有下一页标记
                    has_next = ">下一页<" in html or ">»<" in html
                    result["pagecount"] = page + 1 if has_next else page
                result["limit"] = len(videos)
        except Exception as e:
            print("categoryContent error: {0}".format(e))
        return result

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            if not key:
                return result
            html = self._req("/index.php/vod/search/wd/{0}.html".format(quote(key)))
            if html:
                result["list"] = self._parse_video_list(html)
        except Exception as e:
            print("searchContent error: {0}".format(e))
        return result

    # ==================== 详情 ====================
    def detailContent(self, array):
        result = {"list": []}
        try:
            vod_id = array[0]
            vid = str(vod_id)

            html = self._req("/index.php/vod/detail/id/{0}.html".format(vid))
            if not html:
                return result

            # 标题
            vod_name = ""
            m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            if m:
                vod_name = m.group(1).strip()

            # 图片
            vod_pic = ""
            m = re.search(r'data-pic="([^"]*)"', html)
            if m:
                vod_pic = m.group(1)
            if not vod_pic:
                m = re.search(r'data-original="(https?://[^"]*)"', html)
                if m:
                    vod_pic = m.group(1)

            # 基本信息
            vod_year = ""
            vod_area = ""
            vod_remarks = ""
            vod_content = ""
            vod_director = ""
            vod_actor = ""
            vod_lang = ""

            # 网站详情页实际结构:
            # <div class="director text-overflow"><div class="name">导演:</div>林玉芬,梁胜权</div>
            # <div class="director text-overflow"><div class="name">主演:</div>白鹿,丞磊</div>
            info_items = re.findall(
                r'<div class="director text-overflow">\s*<div class="name">([^<:]+):</div>\s*([\s\S]*?)\s*</div>',
                html
            )
            for item_title, item_content in info_items:
                item_title = item_title.strip()
                value = re.sub(r'<[^>]+>', '', item_content).strip()
                if value.endswith(","):
                    value = value[:-1].strip()
                if not value or value == "未知":
                    continue
                if item_title == "导演":
                    vod_director = value
                elif item_title in ("主演", "演员"):
                    vod_actor = value
                elif item_title in ("备注", "状态", "更新"):
                    vod_remarks = value

            # 备用: module-info-item格式或其他span标签格式
            if not vod_director or not vod_actor:
                mi = re.findall(
                    r'<div class="module-info-item">\s*<span class="module-info-item-title">([^<]+)</span>\s*'
                    r'<div class="module-info-item-content">([\s\S]*?)</div>\s*</div>',
                    html
                )
                for it, ic in mi:
                    it = it.strip()
                    names = re.findall(r'<a[^>]*>([^<]+)</a>', ic)
                    value = " ".join(n.strip() for n in names if n.strip())
                    if not value:
                        value = re.sub(r'<[^>]+>', '', ic).strip()
                    if "导演" in it:
                        vod_director = value
                    elif "主演" in it or "演员" in it:
                        vod_actor = value
                    elif "更新" in it or "备注" in it or "状态" in it:
                        vod_remarks = value

            # 备用: 纯文本行匹配
            if not vod_director or not vod_actor:
                text_block = re.sub(r'<[^>]+>', '\n', html)
                for line in text_block.split('\n'):
                    line = line.strip()
                    if line.startswith("导演:") or line.startswith("导演 :"):
                        val = line.split(":", 1)[-1].strip()
                        if val and val != "未知":
                            vod_director = val
                    elif line.startswith("主演:") or line.startswith("主演 :"):
                        val = line.split(":", 1)[-1].strip()
                        if val and val != "未知":
                            vod_actor = val

            # 从 other-box 区域提取 年份/语言 等
            # 结构: <div class="item"><div class="item-top">值</div><div class="item-bottom">标签</div></div>
            other_items = re.findall(
                r'<div class="item-top">([^<]+)</div>\s*<div class="item-bottom">([^<]+)</div>',
                html
            )
            for val, label in other_items:
                val = val.strip()
                label = label.strip()
                if not val or val == "未知":
                    continue
                if label in ("上映时间", "年份", "年代"):
                    vod_year = val
                elif label in ("地区", "区域", "国家"):
                    vod_area = val
                elif label in ("语言",):
                    vod_lang = val

            # 从分类标签中提取地区: [国产](link)
            if not vod_area:
                tag_m = re.search(r'vod-show/class/[^"]+">([^<]+)</a>', html)
                if tag_m:
                    vod_area = tag_m.group(1).strip()

            # 简介: 实际结构
            # <div class="vod-content"><div class="title">简介:</div><div class="intro"><div class="wrapper_more">...<div class="wrapper_more_text"><label...><div><p>内容</p>
            m3 = re.search(
                r'class="wrapper_more_text">[\s\S]*?<div><p>([\s\S]*?)</p>',
                html
            )
            if not m3:
                m3 = re.search(
                    r'class="wrapper_more_text">[\s\S]*?<div>([\s\S]*?)</div>\s*</div>\s*</div>',
                    html
                )
            if not m3:
                m3 = re.search(r'class="vod_content[^"]*"[^>]*>([\s\S]*?)</div>\s*</div>', html)
            if not m3:
                m3 = re.search(r'class="sketch[^"]*"[^>]*>\s*<p>([\s\S]*?)</p>', html)
            if not m3:
                m3 = re.search(r'class="sketch[^"]*">([\s\S]*?)</', html)
            if m3:
                vod_content = re.sub(r'<[^>]+>', '', m3.group(1)).strip()
                vod_content = re.sub(r'\s+', ' ', vod_content).strip()

            # 播放源和分集
            play_from_list = []
            play_url_list = []

            # 源名: 从锚点链接 href="#playlist{N}" 中提取线路名称
            # 网站格式: <a href="#playlist2">线路一</a> <a href="#playlist1">线路二</a>
            source_map = {}
            src_links = re.findall(r'<a\s+href="#playlist(\d+)"[^>]*>([^<]+)</a>', html)
            for sid_str, src_name in src_links:
                source_map[int(sid_str)] = src_name.strip()

            # 按playlist id位置分块提取分集
            playlist_positions = []
            for m in re.finditer(r'<div id="playlist(\d+)"', html):
                playlist_positions.append((int(m.group(1)), m.start()))

            block_order = []
            sid_groups = {}
            for i, (sid, pos) in enumerate(playlist_positions):
                end_pos = playlist_positions[i + 1][1] if i + 1 < len(playlist_positions) else len(html)
                block = html[pos:end_pos]
                eps = re.findall(
                    r'<a\s+href="(/index\.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)">([^<]+)</a>',
                    block
                )
                if eps:
                    block_order.append(sid)
                    if sid not in sid_groups:
                        sid_groups[sid] = []
                    for ep_url, ep_name in eps:
                        ep_name = ep_name.strip()
                        if ep_name:
                            sid_groups[sid].append("{0}${1}".format(ep_name, ep_url))
                        else:
                            sid_groups[sid].append(ep_url)

            if not source_map:
                source_map = {sid: "线路{0}".format(i + 1) for i, sid in enumerate(block_order)}

            for i, sid in enumerate(block_order):
                src_name = source_map.get(sid, "线路{0}".format(i + 1))
                play_from_list.append(src_name)
                play_url_list.append("#".join(sid_groups[sid]))

            if not play_from_list:
                play_from_list.append("线路一")
                play_url_list.append("")

            vod = {
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_year": vod_year,
                "vod_area": vod_area,
                "vod_remarks": vod_remarks,
                "vod_actor": vod_actor,
                "vod_director": vod_director,
                "vod_content": vod_content,
                "vod_play_from": "$$$".join(play_from_list),
                "vod_play_url": "$$$".join(play_url_list),
            }
            result["list"].append(vod)
        except Exception as e:
            print("detailContent error: {0}".format(e))
        return result

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "playUrl": "", "url": "", "header": "", "jx": 0}
        try:
            # id格式: 集名$播放路径
            play_url_part = id.split("$")[-1] if "$" in id else id
            if not play_url_part.startswith("/"):
                play_url_part = "/" + play_url_part

            html = self._req_play(play_url_part)
            if not html:
                return result

            m = re.search(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\});', html)
            if m:
                raw = m.group(1)
                m2 = re.search(r'"url"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
                if m2:
                    url = m2.group(1).replace("\\/", "/")
                    try:
                        url = url.encode().decode("unicode_escape")
                    except:
                        pass
                    if ".m3u8" in url or ".mp4" in url:
                        result["parse"] = 0
                    else:
                        result["parse"] = 1
                        result["jx"] = 1
                    headers = {
                        "User-Agent": self.ua,
                        "Referer": self.host + play_url_part,
                    }
                    result["url"] = url
                    result["header"] = json.dumps(headers)
                    return result

            # 没有player_aaaa，嗅探模式
            result["parse"] = 1
            result["jx"] = 1
            result["url"] = self.host + play_url_part
            result["header"] = json.dumps({"User-Agent": self.ua})
        except Exception as e:
            print("playerContent error: {0}".format(e))
        return result


# ==================== 测试入口 ====================
if __name__ == "__main__":
    spider = Spider()
    spider.init()

    print("=" * 60)
    print("1. 首页")
    print("=" * 60)
    home = spider.homeContent(True)
    print("分类: {0} 个".format(len(home.get('class', []))))
    print("视频: {0} 个".format(len(home.get('list', []))))
    for v in home.get("list", [])[:5]:
        print("  [{0}] {1} - {2}".format(v['vod_id'], v['vod_name'], v['vod_remarks']))

    print("\n" + "=" * 60)
    print("2. 分类")
    print("=" * 60)
    cat = spider.categoryContent("1", 1, True, None)
    print("电影 第1页: {0} 个".format(len(cat.get('list', []))))
    for v in cat.get("list", [])[:5]:
        print("  [{0}] {1} - {2}".format(v['vod_id'], v['vod_name'], v['vod_remarks']))

    print("\n" + "=" * 60)
    print("3. 搜索")
    print("=" * 60)
    results = spider.searchContent("吞噬星空", False)
    print("搜索结果: {0} 个".format(len(results.get('list', []))))
    for v in results.get("list", [])[:5]:
        print("  [{0}] {1} - {2}".format(v['vod_id'], v['vod_name'], v['vod_remarks']))

    if results.get("list"):
        print("\n" + "=" * 60)
        print("4. 详情")
        print("=" * 60)
        detail = spider.detailContent([results["list"][0]["vod_id"]])
        if detail["list"]:
            vod = detail["list"][0]
            print("名称: {0}".format(vod['vod_name']))
            print("导演: {0}".format(vod['vod_director']))
            print("主演: {0}".format(vod['vod_actor']))
            print("简介: {0}...".format(vod['vod_content'][:100] if vod['vod_content'] else "(空)"))
            print("播放源: {0}".format(vod['vod_play_from']))
            urls = vod["vod_play_url"].split("$$$")
            for i, u in enumerate(urls):
                eps = u.split("#")
                print("  {0}源: {1}集, 第一集: {2}".format(i + 1, len(eps), eps[0][:80]))

            print("\n" + "=" * 60)
            print("5. 播放")
            print("=" * 60)
            first_ep = urls[0].split("#")[0]
            pc = spider.playerContent("", first_ep, [])
            print("播放URL: {0}".format(pc['url'][:200]))
