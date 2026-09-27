#coding=utf-8
#!/usr/bin/python
# 独播库 (www.dbku.tv) - 苹果CMS V10 (Maccms)
# 模板: myui
# URL规则:
#   分类页: /vodtype/{tid}.html
#   筛选页: /vodshow/{tid}-{area}-{by}-{class}-{lang}-{letter}--------{page}---{year}.html
#   详情页: /voddetail/{id}.html
#   播放页: /vodplay/{id}-{sid}-{nid}.html
#   搜索: AJAX API /index.php/ajax/suggest?mid=1&wd={keyword}&limit={limit}
# 播放: player_data变量, encrypt:2 (base64+url-encode), 含m3u8/mp4直链

import sys
sys.path.append('..')
from base.spider import Spider
import re
import json
import base64
from urllib.parse import quote, unquote


class Spider(Spider):

    def getName(self):
        return "独播库"

    def init(self, extend=""):
        self.host = "https://www.dbku.tv"
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
        """通用请求"""
        url = self.host + path
        try:
            rsp = self.fetch(url, headers=self.header)
            if isinstance(rsp, str):
                return rsp
            if rsp and hasattr(rsp, 'text'):
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
            if isinstance(rsp, str):
                return rsp
            if rsp and hasattr(rsp, 'text'):
                return rsp.text
        except:
            pass
        return ""

    # ==================== 图片URL补全 ====================
    def _fix_pic(self, pic):
        """将相对图片URL转为完整URL"""
        if not pic:
            return ""
        if pic.startswith("http"):
            return pic
        if not pic.startswith("/"):
            pic = "/" + pic
        return self.host + pic

    # ==================== 分类配置 ====================
    cats = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "连续剧", "type_id": "2"},
        {"type_name": "综艺", "type_id": "3"},
        {"type_name": "动漫", "type_id": "4"},
    ]

    def _build_filters(self):
        filters = {}

        # 通用地区
        area_values = [
            {"n": "全部", "v": ""},
            {"n": "大陆", "v": "大陆"},
            {"n": "香港", "v": "香港"},
            {"n": "台湾", "v": "台湾"},
            {"n": "韩国", "v": "韩国"},
            {"n": "日本", "v": "日本"},
            {"n": "英国", "v": "英国"},
            {"n": "法国", "v": "法国"},
            {"n": "加拿大", "v": "加拿大"},
            {"n": "澳大利亚", "v": "澳大利亚"},
        ]

        # 通用语言
        lang_values = [
            {"n": "全部", "v": ""},
            {"n": "国语", "v": "国语"},
            {"n": "英语", "v": "英语"},
            {"n": "粤语", "v": "粤语"},
            {"n": "韩语", "v": "韩语"},
            {"n": "法语", "v": "法语"},
        ]

        # 通用年份
        year_values = [
            {"n": "全部", "v": ""},
            {"n": "2026", "v": "2026"},
            {"n": "2025", "v": "2025"},
            {"n": "2024", "v": "2024"},
            {"n": "2023", "v": "2023"},
            {"n": "2022", "v": "2022"},
            {"n": "2020", "v": "2020"},
            {"n": "2019", "v": "2019"},
        ]

        # 通用排序
        sort_values = [
            {"n": "人气", "v": "人气"},
            {"n": "评分", "v": "评分"},
        ]

        # 电影类型
        movie_class = [
            {"n": "全部", "v": ""},
            {"n": "动作", "v": "动作"},
            {"n": "喜剧", "v": "喜剧"},
            {"n": "爱情", "v": "爱情"},
            {"n": "科幻", "v": "科幻"},
            {"n": "奇幻", "v": "奇幻"},
            {"n": "恐怖", "v": "恐怖"},
            {"n": "悬疑", "v": "悬疑"},
            {"n": "惊悚", "v": "惊悚"},
            {"n": "剧情", "v": "剧情"},
            {"n": "战争", "v": "战争"},
            {"n": "武侠", "v": "武侠"},
            {"n": "动画", "v": "动画"},
            {"n": "冒险", "v": "冒险"},
            {"n": "犯罪", "v": "犯罪"},
            {"n": "警匪", "v": "警匪"},
            {"n": "古装", "v": "古装"},
            {"n": "同性", "v": "同性"},
        ]

        # 连续剧类型
        tv_class = [
            {"n": "全部", "v": ""},
            {"n": "陆剧", "v": "陆剧"},
            {"n": "港剧", "v": "港剧"},
            {"n": "日韩剧", "v": "日韩剧"},
            {"n": "台泰剧", "v": "台泰剧"},
            {"n": "短剧", "v": "短剧"},
            {"n": "剧情", "v": "剧情"},
            {"n": "古装", "v": "古装"},
            {"n": "喜剧", "v": "喜剧"},
            {"n": "爱情", "v": "爱情"},
            {"n": "悬疑", "v": "悬疑"},
            {"n": "惊悚", "v": "惊悚"},
            {"n": "武侠", "v": "武侠"},
            {"n": "科幻", "v": "科幻"},
            {"n": "都市", "v": "都市"},
            {"n": "青春", "v": "青春"},
            {"n": "家庭", "v": "家庭"},
            {"n": "历史", "v": "历史"},
            {"n": "年代", "v": "年代"},
            {"n": "穿越", "v": "穿越"},
        ]

        # 综艺类型
        variety_class = [
            {"n": "全部", "v": ""},
            {"n": "真人秀", "v": "真人秀"},
            {"n": "选秀", "v": "选秀"},
            {"n": "音乐", "v": "音乐"},
            {"n": "搞笑", "v": "搞笑"},
            {"n": "情感", "v": "情感"},
            {"n": "竞技", "v": "竞技"},
            {"n": "竞演", "v": "竞演"},
            {"n": "美食", "v": "美食"},
            {"n": "旅游", "v": "旅游"},
            {"n": "纪实", "v": "纪实"},
            {"n": "脱口秀", "v": "脱口秀"},
            {"n": "游戏互动", "v": "游戏互动"},
            {"n": "生活", "v": "生活"},
        ]

        # 动漫类型
        anime_class = [
            {"n": "全部", "v": ""},
            {"n": "热血", "v": "热血"},
            {"n": "冒险", "v": "冒险"},
            {"n": "格斗", "v": "格斗"},
            {"n": "科幻", "v": "科幻"},
            {"n": "推理", "v": "推理"},
            {"n": "校园", "v": "校园"},
            {"n": "恋爱", "v": "恋爱"},
            {"n": "少女", "v": "少女"},
            {"n": "机战", "v": "机战"},
            {"n": "武侠", "v": "武侠"},
            {"n": "魔幻", "v": "魔幻"},
            {"n": "爆笑", "v": "爆笑"},
            {"n": "竞技", "v": "竞技"},
            {"n": "动作", "v": "动作"},
        ]

        # 子分类
        tv_sub = [
            {"n": "全部", "v": "2"},
            {"n": "陆剧", "v": "13"},
            {"n": "港剧", "v": "20"},
            {"n": "日韩剧", "v": "15"},
            {"n": "台泰剧", "v": "14"},
            {"n": "短剧", "v": "21"},
        ]

        common = [
            {"key": "area", "name": "地区", "value": area_values},
            {"key": "by", "name": "排序", "value": sort_values},
            {"key": "class", "name": "类型", "value": None},
            {"key": "lang", "name": "语言", "value": lang_values},
            {"key": "year", "name": "年份", "value": year_values},
        ]

        for tid, class_list in [("1", movie_class), ("2", tv_class), ("3", variety_class), ("4", anime_class)]:
            fl = []
            # 连续剧有子分类
            if tid == "2":
                fl.append({"key": "sub", "name": "分类", "value": tv_sub})
            for item in common:
                if item["key"] == "class":
                    fl.append({"key": "class", "name": "类型", "value": class_list})
                else:
                    fl.append(item)
            filters[tid] = fl

        return filters

    # ==================== 通用视频列表解析 ====================
    def _parse_video_list(self, html):
        """解析视频列表 (myui-vodlist__thumb格式)
        HTML结构:
        <a class="myui-vodlist__thumb ..." href="/voddetail/{id}.html" title="{title}" data-original="{pic}">
          <span class="play hidden-xs"></span>
          <span class="pic-tag pic-tag-top"><span class="tag">6.1分</span></span>
          <span class="pic-text text-right">正片</span>
        </a>
        """
        videos = []
        seen_ids = set()

        # 匹配完整的<a>...</a>元素，提取id和title，以及内部内容
        # 注意: myui-vodlist__thumb链接中不会嵌套<a>标签，可以用非贪婪匹配
        pattern = re.compile(
            r'<a[^>]*class="myui-vodlist__thumb[^"]*"[^>]*href="/voddetail/(\d+)\.html"[^>]*title="([^"]*)"[^>]*>([\s\S]*?)</a>',
            re.MULTILINE
        )
        pattern2 = re.compile(
            r'<a[^>]*href="/voddetail/(\d+)\.html"[^>]*title="([^"]*)"[^>]*class="myui-vodlist__thumb[^"]*"[^>]*>([\s\S]*?)</a>',
            re.MULTILINE
        )
        # 通用匹配: 不限class顺序
        pattern3 = re.compile(
            r'<a[^>]*href="/voddetail/(\d+)\.html"[^>]*title="([^"]*)"[^>]*>([\s\S]*?)</a>',
            re.MULTILINE
        )

        for pat in [pattern, pattern2, pattern3]:
            for m in pat.finditer(html):
                vid = m.group(1)
                title = m.group(2).strip()
                if vid in seen_ids:
                    continue
                seen_ids.add(vid)

                # 合并整个<a>标签(含属性)和内部内容
                full_tag = m.group(0)
                inner = m.group(3)

                # 图片 (优先data-original)
                pic = ""
                m_pic = re.search(r'data-original="([^"]*)"', full_tag)
                if m_pic:
                    pic = m_pic.group(1)
                if not pic:
                    m_pic = re.search(r'src="([^"]*)"', full_tag)
                    if m_pic:
                        pic = m_pic.group(1)
                if pic in ("/static/img/loading.png", "/static/img/loading-square.gif", "/static/img/loading-wide.gif"):
                    pic = ""

                # 备注: <span class="pic-text text-right">正片</span>
                note = ""
                m_note = re.search(r'pic-text[^>]*>\s*([^<]*?)\s*</span>', full_tag)
                if m_note:
                    note = m_note.group(1).strip()
                if not note:
                    # 尝试从tag中提取: <span class="tag">6.1分</span>
                    m_tag = re.search(r'class="tag"[^>]*>\s*([^<]*?)\s*</span>', inner)
                    if m_tag:
                        note = m_tag.group(1).strip()

                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": self._fix_pic(pic),
                    "vod_remarks": note,
                })

        return videos

    def _parse_search_list(self, html):
        """解析搜索结果 (同样使用myui-vodlist__thumb格式)"""
        return self._parse_video_list(html)

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
        result = {"list": [], "page": int(pg) if pg else 1, "pagecount": 1, "limit": 30, "total": 0}
        try:
            page = int(pg) if pg else 1

            # 处理子分类
            actual_tid = tid
            if extend and extend.get("sub"):
                actual_tid = str(extend["sub"])

            # 构建筛选URL: /vodshow/{tid}-{area}-{by}-{class}-{lang}-{letter}--------{page}---{year}.html
            # URL格式分析: 11个字段, 用-分隔
            # {tid}-{area}-{by}-{class}-{lang}-{letter}--------{page}---{year}
            # 索引:         0     1     2      3      4      5      6 7 8 9 10
            # 注意末尾有两个段(10和11), 其中page在位置9, year在位置11

            # 从实际页面观察到的格式:
            # /vodshow/1--------{page}---.html  (无筛选, 有分页)
            # /vodshow/1-----------{year}.html   (有年份, 第1页)
            # /vodshow/1-{area}----------.html   (有地区)
            # /vodshow/1--{by}---------.html      (有排序)
            # /vodshow/1---{class}--------.html  (有类型)
            # /vodshow/1----{lang}-------.html    (有语言)

            # 12段, 用11个-分隔: tid-area-by-class-lang-letter-{6}-{7}-{page}-{9}-{10}-{year}
            # 实际URL: /vodshow/1--------1---.html (12字段, page在索引8, year在索引11)

            fields = [""] * 12
            fields[0] = actual_tid

            if extend:
                if extend.get("area"):
                    fields[1] = quote(extend["area"])
                if extend.get("by"):
                    fields[2] = quote(extend["by"])
                if extend.get("class"):
                    fields[3] = quote(extend["class"])
                if extend.get("lang"):
                    fields[4] = quote(extend["lang"])

            fields[8] = str(page)

            if extend and extend.get("year"):
                fields[11] = str(extend["year"])

            path = "/vodshow/" + "-".join(fields) + ".html"

            html = self._req(path)
            if html:
                videos = self._parse_video_list(html)
                result["list"] = videos
                result["page"] = page
                result["total"] = len(videos)
                # 判断分页
                if len(videos) >= 24:
                    result["pagecount"] = page + 1
                else:
                    result["pagecount"] = page
                result["limit"] = len(videos) if len(videos) > 0 else 30
        except Exception as e:
            print("categoryContent error: {0}".format(e))
        return result

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            if not key:
                return result
            page = int(pg) if pg else 1
            # 使用全页搜索 (带图片和备注)
            # URL格式: /vodsearch/-------------.html?wd={keyword}
            # 分页: 搜索页可能不支持分页参数，第1页足够
            path = "/vodsearch/-------------.html?wd={0}".format(quote(key))
            html = self._req(path)
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

            html = self._req("/voddetail/{0}.html".format(vid))
            if not html:
                return result

            # 标题
            vod_name = ""
            m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            if m:
                vod_name = m.group(1).strip()

            # 图片
            vod_pic = ""
            m = re.search(r'myui-content__thumb[^>]*data-original="([^"]*)"', html)
            if m:
                vod_pic = self._fix_pic(m.group(1))
            if not vod_pic:
                m = re.search(r'data-original="([^"]*)"', html)
                if m:
                    vod_pic = self._fix_pic(m.group(1))

            # 基本信息
            vod_year = ""
            vod_area = ""
            vod_director = ""
            vod_actor = ""
            vod_remarks = ""
            vod_content = ""
            vod_class = ""

            # 提取信息项: <span class="text-muted[ hidden-xs]">标签：</span>后面跟着值
            # 值可能在<a>标签、<span>标签中或直接文本
            # 使用位置定位法: 找到每个label后，取其</span>到下一个text-muted span之间的内容
            # 注意: text-muted可能有额外class如 hidden-xs
            label_pattern = re.compile(
                r'<span class="text-muted[^"]*">\s*([^：<]+)[：:]\s*</span>'
            )
            for m_label in label_pattern.finditer(html):
                label = m_label.group(1).strip()
                # 取label结束位置后的内容
                start = m_label.end()
                # 找到下一个text-muted span的位置 (匹配各种class变体)
                next_label = html.find('<span class="text-muted', start)
                # 也可能在</p>处结束
                next_p = html.find('</p>', start)
                # 取最近的结束位置
                ends = [x for x in [next_label, next_p] if x > 0]
                if ends:
                    end = min(ends)
                else:
                    end = start + 300
                value_raw = html[start:end]
                # 去除HTML标签和清理
                value = re.sub(r'<[^>]+>', '', value_raw)
                value = value.replace('&nbsp;', ' ').replace('&amp;', '&').strip()
                # 去除末尾的逗号
                value = value.rstrip('，,')
                # 去除"详情"等链接文字
                value = re.sub(r'详情\s*$', '', value).strip()
                if not value or value == "/":
                    continue
                if "分类" in label or "类型" in label:
                    if not vod_class:
                        vod_class = value
                elif "更新" in label:
                    vod_remarks = value
                elif "主演" in label or "演员" in label:
                    if not vod_actor:
                        vod_actor = value
                elif "导演" in label:
                    if not vod_director:
                        vod_director = value
                elif "年份" in label:
                    vod_year = value
                elif "地区" in label:
                    vod_area = value
                elif "简介" in label:
                    if not vod_content:
                        vod_content = value

            # 从面包屑获取分类
            if not vod_class:
                m = re.search(r'/vodshow/(\d+)-*[^"]*">([^<]+)</a>', html)
                if m:
                    vod_class = m.group(2).strip()

            # 从标签提取年份
            if not vod_year:
                tags = re.findall(r'/vodshow/\d+-----------(\d{4})\.html', html)
                if tags:
                    vod_year = tags[0]

            # 从pic-text提取备注 (如果更新时间为空，尝试从pic-text提取)
            if not vod_remarks:
                m = re.search(r'pic-text[^>]*>\s*([^<]*?)\s*</span>', html)
                if m:
                    vod_remarks = m.group(1).strip()

            # 简介 (如果上面没有提取到)
            if not vod_content:
                m = re.search(r'class="content[^"]*"[^>]*>\s*<p[^>]*>([\s\S]*?)</p>', html)
                if m:
                    vod_content = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if not vod_content:
                m = re.search(r'sketch content[^>]*>([\s\S]*?)</div>', html)
                if m:
                    vod_content = re.sub(r'<[^>]+>', '', m.group(1)).strip()

            # ==================== 播放源和分集 ====================
            play_from_list = []
            play_url_list = []

            # 提取所有播放链接
            # 格式: <a href="/vodplay/{vid}-{sid}-{nid}.html" ...>第N集</a>
            all_eps = re.findall(
                r'<a[^>]*href="(/vodplay/(\d+)-(\d+)-(\d+)\.html)"[^>]*>\s*([^<]*)</a>',
                html
            )

            if all_eps:
                # 按sid分组
                sources = {}
                source_order = []
                for ep_url, vid_str, sid, nid, ep_name in all_eps:
                    sid_key = sid
                    if sid_key not in sources:
                        sources[sid_key] = []
                        source_order.append(sid_key)
                    sources[sid_key].append((ep_url, ep_name.strip()))

                # 提取播放源名称
                # 尝试从页面中提取tab名称
                tab_names = re.findall(
                    r'<a[^>]*href="#playtab\d+"[^>]*>([\s\S]*?)</a>',
                    html
                )
                if not tab_names:
                    tab_names = re.findall(
                        r'data-toggle="tab"[^>]*>\s*<[^>]*>([^<]+)',
                        html
                    )

                for i, sid in enumerate(source_order):
                    eps = sources[sid]
                    if not eps:
                        continue

                    src_name = "独播库{0}".format(i + 1)
                    if i < len(tab_names):
                        name = re.sub(r'<[^>]+>', '', tab_names[i]).strip()
                        if name:
                            src_name = name

                    play_from_list.append(src_name)
                    ep_list = []
                    for ep_url, ep_name in eps:
                        ep_list.append("{0}${1}".format(ep_name, ep_url))
                    play_url_list.append("#".join(ep_list))

            # 如果没有播放链接但有播放列表块
            if not play_from_list:
                # 尝试从ul.myui-content__list中提取
                blocks = re.findall(
                    r'<ul[^>]*class="myui-content__list[^"]*"[^>]*>([\s\S]*?)</ul>',
                    html
                )
                for i, block in enumerate(blocks):
                    eps = re.findall(
                        r'<a[^>]*href="(/vodplay/\d+-\d+-\d+\.html)"[^>]*>\s*([^<]*)</a>',
                        block
                    )
                    if not eps:
                        continue
                    src_name = "线路{0}".format(i + 1)
                    play_from_list.append(src_name)
                    ep_list = []
                    for ep_url, ep_name in eps:
                        ep_list.append("{0}${1}".format(ep_name.strip(), ep_url))
                    play_url_list.append("#".join(ep_list))

            vod = {
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_year": vod_year,
                "vod_area": vod_area,
                "vod_class": vod_class,
                "vod_director": vod_director,
                "vod_actor": vod_actor,
                "vod_remarks": vod_remarks,
                "vod_content": vod_content,
                "vod_play_from": "$$$".join(play_from_list),
                "vod_play_url": "$$$".join(play_url_list),
            }
            result["list"] = [vod]
        except Exception as e:
            print("detailContent error: {0}".format(e))
        return result

    # ==================== 播放 ====================
    def _decrypt_url(self, encrypted, encrypt_type):
        """解密播放URL (encrypt:2 = base64+url-encode)"""
        try:
            if encrypt_type == 2:
                # base64解码 -> URL unquote
                decoded = base64.b64decode(encrypted).decode('utf-8')
                url = unquote(decoded)
                return url
            elif encrypt_type == 1:
                # 直接url-encode
                return unquote(encrypted)
            elif encrypt_type == 0:
                # 无加密
                return encrypted
        except:
            pass
        return encrypted

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

            # 提取player_data变量 (注意: 不是player_aaaa)
            m = re.search(r'player_data\s*=\s*(\{[\s\S]*?\})\s*[;<]', html)
            if m:
                raw = m.group(1)
                try:
                    data = json.loads(raw)
                except:
                    # 尝试提取单个字段
                    data = {}

                # 提取url
                url = ""
                m_url = re.search(r'"url"\s*:\s*"([^"]*)"', raw)
                if m_url:
                    url = m_url.group(1)

                # 提取encrypt
                encrypt = 0
                m_enc = re.search(r'"encrypt"\s*:\s*(\d+)', raw)
                if m_enc:
                    encrypt = int(m_enc.group(1))

                # 提取from
                from_type = ""
                m_from = re.search(r'"from"\s*:\s*"([^"]*)"', raw)
                if m_from:
                    from_type = m_from.group(1)

                # 解密URL
                if url and encrypt > 0:
                    url = self._decrypt_url(url, encrypt)

                if url:
                    headers = {
                        "User-Agent": self.ua,
                        "Referer": self.host + play_url_part,
                    }

                    if ".m3u8" in url or ".mp4" in url:
                        # 直链视频，直接播放
                        result["parse"] = 0
                        result["jx"] = 0
                        result["url"] = url
                    else:
                        # 其他外链，走嗅探
                        result["parse"] = 1
                        result["jx"] = 1
                        result["url"] = url

                    result["header"] = json.dumps(headers)
                    return result

            # 尝试player_aaaa (兼容旧模板)
            m2 = re.search(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\});', html)
            if m2:
                raw = m2.group(1)
                m_url = re.search(r'"url"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
                if m_url:
                    url = m_url.group(1).replace("\\/", "/")
                    try:
                        url = url.encode().decode("unicode_escape")
                    except:
                        pass

                    headers = {
                        "User-Agent": self.ua,
                        "Referer": self.host + play_url_part,
                    }

                    if ".m3u8" in url or ".mp4" in url:
                        result["parse"] = 0
                        result["jx"] = 0
                        result["url"] = url
                    else:
                        result["parse"] = 1
                        result["jx"] = 1
                        result["url"] = url

                    result["header"] = json.dumps(headers)
                    return result

            # 没有找到player_data，嗅探模式
            result["parse"] = 1
            result["jx"] = 1
            result["url"] = self.host + play_url_part
            result["header"] = json.dumps({"User-Agent": self.ua})
        except Exception as e:
            print("playerContent error: {0}".format(e))
        return result
