#coding=utf-8
#!/usr/bin/python
# 南瓜影视 (www.nanguays.net) - 苹果CMS V10 (Maccms)
# 模板: mxpro
# API关闭，通过HTML解析获取数据
# 播放: player_aaaa变量中含直链m3u8/mp4
import sys
sys.path.append('..')
from base.spider import Spider
import re
import json
from urllib.parse import quote


class Spider(Spider):

    def getName(self):
        return "南瓜影视"

    def init(self, extend=""):
        self.host = "https://www.nanguays.net"
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
        """请求播放页，带Referer"""
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
        {"type_name": "综艺", "type_id": "3"},
        {"type_name": "动漫", "type_id": "4"},
        {"type_name": "短剧", "type_id": "6"},
        {"type_name": "福利", "type_id": "20"},
    ]

    def _build_filters(self):
        filters = {}
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
            {"key": "by", "name": "排序", "value": [
                {"n": "最新", "v": "time"},
                {"n": "最热", "v": "hits"},
                {"n": "评分", "v": "score"},
            ]},
        ]
        for tid in ["1", "2", "3", "4", "6", "20"]:
            filters[tid] = common
        return filters

    # ==================== 通用HTML解析 ====================
    def _parse_video_list(self, html):
        """通用视频列表解析，兼容三种布局:
        - 海报式: module-poster-item (首页/分类)，链接带title属性
        - 卡片式: module-card-item (搜索结果)，标题在<strong>标签中
        - 轮播图: banner/swiper，标题在v-title>span中
        """
        videos = []
        seen_ids = set()

        # 提取所有详情链接及ID
        all_links = re.findall(r'href="(/index\.php/vod/detail/id/(\d+)\.html)"', html)

        for url, vid in all_links:
            vid_str = str(vid)
            if vid_str in seen_ids:
                continue
            seen_ids.add(vid_str)

            title = ""
            pic = ""
            note = ""

            # 找到该链接在html中的位置
            link_pattern = 'href="/index.php/vod/detail/id/{0}.html"'.format(vid)
            link_pos = html.find(link_pattern)
            if link_pos < 0:
                videos.append({"vod_id": vid_str, "vod_name": "", "vod_pic": "", "vod_remarks": ""})
                continue

            # 截取链接附近的HTML块用于解析
            nearby_start = max(0, link_pos - 200)
            nearby_end = min(len(html), link_pos + 2000)
            nearby = html[nearby_start:nearby_end]

            # 提取标题: 优先 title 属性
            m = re.search(r'href="/index\.php/vod/detail/id/{0}\.html"[^>]*title="([^"]*)"'.format(vid), html)
            if m:
                title = m.group(1).strip()
            else:
                # 轮播图: 标题在 v-title > span 中
                m = re.search(r'class="v-title"[\s\S]*?<span>([^<]+)</span>', nearby)
                if m:
                    title = m.group(1).strip()
                else:
                    # 卡片布局: 标题在 module-card-item-title 内的 <strong> 中
                    m = re.search(r'module-card-item-title[\s\S]*?<strong>([^<]+)</strong>', nearby)
                    if m:
                        title = m.group(1).strip()
                    else:
                        # 海报布局: 标题在 module-poster-item-title 内
                        m = re.search(r'module-poster-item-title[^>]*>\s*([^<]+)\s*</div>', nearby)
                        if m:
                            title = m.group(1).strip()

            # 提取图片: 优先 data-original，其次 banner 的 background url
            m = re.search(r'data-original="([^"]*)"', nearby)
            if m:
                pic = m.group(1)
            else:
                m = re.search(r'background:\s*url\(([^)]+)\)', nearby)
                if m:
                    pic = m.group(1)

            # 提取备注
            m = re.search(r'class="module-item-note"[^>]*>\s*([^<]*?)\s*</div>', nearby)
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

            # 首页推荐列表
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

            # 构建URL参数
            path = "/index.php/vod/type/id/{0}/page/{1}.html".format(tid, page)

            if extend:
                ext_params = {}
                for k, v in extend.items():
                    if v:
                        ext_params[k] = v
                if ext_params:
                    params_str = "/".join("{0}/{1}".format(k, quote(str(v))) for k, v in ext_params.items())
                    path = "/index.php/vod/type/id/{0}/{1}/page/{2}.html".format(tid, params_str, page)

            html = self._req(path)
            if html:
                videos = self._parse_video_list(html)
                result["list"] = videos
                result["page"] = page
                result["total"] = len(videos)
                # 判断是否有下一页
                has_next = "next" in html or ">下一页<" in html or ">»<" in html
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

            # 提取视频信息
            vod_name = ""
            m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            if m:
                vod_name = m.group(1).strip()

            # 提取图片
            vod_pic = ""
            m = re.search(r'data-pic="([^"]*)"', html)
            if m:
                vod_pic = m.group(1)
            if not vod_pic:
                m = re.search(r'module-info-poster[\s\S]*?data-original="([^"]*)"', html)
                if m:
                    vod_pic = m.group(1)
            if not vod_pic:
                m = re.search(r'data-original="(https?://[^"]*)"', html)
                if m:
                    vod_pic = m.group(1)

            # 提取基本信息
            vod_year = ""
            vod_area = ""
            vod_remarks = ""
            vod_content = ""
            vod_director = ""
            vod_actor = ""

            # 提取年份和地区
            tags = re.findall(r'module-info-tag-link[^>]*>\s*<a[^>]*title="([^"]*)"', html)
            for i, tag in enumerate(tags):
                tag = tag.strip()
                if not tag:
                    continue
                if i == 0 and re.match(r'\d{4}', tag):
                    vod_year = tag
                elif i == 1:
                    vod_area = tag

            # 提取所有 module-info-item 块
            info_items = re.findall(
                r'<div class="module-info-item">\s*<span class="module-info-item-title">([^<]+)</span>\s*'
                r'<div class="module-info-item-content">([\s\S]*?)</div>\s*</div>',
                html
            )
            for item_title, item_content in info_items:
                item_title = item_title.strip()
                names = re.findall(r'<a[^>]*>([^<]+)</a>', item_content)
                value = " ".join(n.strip() for n in names if n.strip())
                if not value:
                    value = re.sub(r'<[^>]+>', '', item_content).strip()

                if "导演" in item_title:
                    vod_director = value
                elif "主演" in item_title or "演员" in item_title:
                    vod_actor = value
                elif "连载" in item_title or "备注" in item_title or "状态" in item_title:
                    vod_remarks = value

            # 提取简介
            m3 = re.search(r'module-info-introduction-content[^>]*>\s*<p>([\s\S]*?)</p>', html)
            if m3:
                vod_content = re.sub(r'<[^>]+>', '', m3.group(1)).strip()

            # 提取播放源和分集
            play_from_list = []
            play_url_list = []

            sources = re.findall(r'module-tab-item[^>]*data-dropdown-value="([^"]*)"', html)
            if not sources:
                sources = re.findall(r'线路[^<"]*', html)
                sources = list(set(s.strip() for s in sources if s.strip()))

            # 按 module-play-list-content 块提取分集（每个块对应一个播放源）
            play_blocks = re.findall(
                r'<div class="module-play-list-content[^"]*">([\s\S]*?)</div>\s*</div>\s*</div>',
                html
            )

            # 按块出现顺序记录每个块的sid和分集
            block_order = []  # 按HTML顺序的sid列表
            sid_groups = {}
            for block in play_blocks:
                eps = re.findall(
                    r'<a[^>]+href="(/index\.php/vod/play/id/\d+/sid/(\d+)/nid/(\d+)\.html)"[^>]*>\s*<span>([^<]*)</span>',
                    block
                )
                if eps:
                    sid = int(eps[0][1])
                    block_order.append(sid)
                    if sid not in sid_groups:
                        sid_groups[sid] = []
                    for ep in eps:
                        url, ep_sid, nid, ep_name = ep
                        ep_name = ep_name.strip()
                        if ep_name:
                            sid_groups[sid].append("{0}${1}".format(ep_name, url))
                        else:
                            sid_groups[sid].append(url)

            if not sources:
                sources = ["线路一", "线路二"]
            while len(sources) < len(block_order):
                sources.append("线路{0}".format(len(sources) + 1))

            # 按HTML中出现顺序映射源名和分集
            for i, sid in enumerate(block_order):
                src_name = sources[i] if i < len(sources) else "线路{0}".format(i + 1)
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
        result = {"parse": 0, "playUrl": "", "url": "", "header": ""}
        try:
            # id格式: 集名$URL，取$后面的播放路径
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
                    headers = {
                        "User-Agent": self.ua,
                        "Referer": self.host + play_url_part,
                    }
                    result["url"] = url
                    result["header"] = json.dumps(headers)
                    return result

            # 没有找到player_aaaa，尝试嗅探模式
            result["parse"] = 1
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
    print(f"分类: {len(home.get('class', []))} 个")
    print(f"filters: {list(home.get('filters', {}).keys())}")
    print(f"视频: {len(home.get('list', []))} 个")
    for v in home.get("list", [])[:5]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n" + "=" * 60)
    print("2. 分类")
    print("=" * 60)
    cat = spider.categoryContent("1", 1, True, None)
    print(f"电影 第1页: {len(cat.get('list', []))} 个")
    for v in cat.get("list", [])[:5]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n" + "=" * 60)
    print("3. 搜索")
    print("=" * 60)
    results = spider.searchContent("变形金刚", False)
    print(f"搜索结果: {len(results.get('list', []))} 个")
    for v in results.get("list", [])[:5]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    if results.get("list"):
        print("\n" + "=" * 60)
        print("4. 详情")
        print("=" * 60)
        detail = spider.detailContent([results["list"][0]["vod_id"]])
        if detail["list"]:
            vod = detail["list"][0]
            print(f"名称: {vod['vod_name']}")
            print(f"类型: {vod['vod_year']} {vod['vod_area']}")
            print(f"演员: {vod['vod_actor']}")
            print(f"简介: {(vod['vod_content'] or '')[:100]}")
            print(f"播放源: {vod['vod_play_from']}")
            urls = vod["vod_play_url"].split("$$$")
            for i, u in enumerate(urls[:2]):
                eps = u.split("#")
                print(f"  {i+1}源: {len(eps)}集, 第一集: {eps[0][:100]}")

            print("\n" + "=" * 60)
            print("5. 播放")
            print("=" * 60)
            first_ep = urls[0].split("#")[0].split("$")[0]
            pc = spider.playerContent("", first_ep, [])
            print(f"播放URL: {pc['url'][:200]}")