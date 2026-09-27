#coding=utf-8
#!/usr/bin/python
# MXVOD 明星影院 (https://mxvod.us) - 苹果CMS V10 (Maccms)
# 模板: mxone
# URL规则:
#   分类页: /vodtype/{slug}.html        (slug: dianying/dianshiju/zongyi/dongman/duanju/tiyu/dianyingjieshuo)
#   搜索:   /vodsearch/-------------.html?wd={keyword}   (13个dash + wd 参数)
#   详情/播放(合一): /vodplay/{id}-{from}-{nid}.html
#   说明: 本站无独立 voddetail 页, 列表卡片直接链到 vodplay; 列表页为单页(无服务端分页控件)
# 播放: player_aaaa 变量, encrypt:0 (无加密), url 为转义后的 m3u8 直链
#
# 本文件参照 dbku.py 模板结构改写: 保留类结构/方法签名/_req/_req_play/_fix_pic 等封装,
# 仅把站点相关部分适配为 mxvod.us 的真实形态(module-item 列表、vodplay 详情、player_aaaa 播放)。

import sys
sys.path.append('..')
from base.spider import Spider
import re
import json
import base64
from urllib.parse import quote, unquote
from lxml import etree


class Spider(Spider):

    def getName(self):
        return "MXVOD"

    def init(self, extend=""):
        self.host = "https://mxvod.us"
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
        """通用请求, 返回解码后的文本 (优先 UTF-8, 失败回退 GBK)"""
        url = self.host + path
        try:
            rsp = self.fetch(url, headers=self.header)
            if isinstance(rsp, str):
                return rsp
            if rsp and hasattr(rsp, 'text'):
                return rsp.text
            if rsp and hasattr(rsp, 'content'):
                try:
                    return rsp.content.decode('utf-8')
                except:
                    return rsp.content.decode('gbk', 'ignore')
        except:
            pass
        return ""

    def _req_play(self, path):
        """请求播放页, 带 Referer"""
        url = self.host + path
        headers = dict(self.header)
        headers["Referer"] = self.host + "/"
        try:
            rsp = self.fetch(url, headers=headers)
            if isinstance(rsp, str):
                return rsp
            if rsp and hasattr(rsp, 'text'):
                return rsp.text
            if rsp and hasattr(rsp, 'content'):
                try:
                    return rsp.content.decode('utf-8')
                except:
                    return rsp.content.decode('gbk', 'ignore')
        except:
            pass
        return ""

    # ==================== 工具 ====================
    def _fix_pic(self, pic):
        """将相对图片URL转为完整URL, 过滤占位图"""
        if not pic:
            return ""
        if pic.startswith("http"):
            return pic
        if not pic.startswith("/"):
            pic = "/" + pic
        return self.host + pic

    def _unescape(self, s):
        """解码 Unicode 转义(\\uXXXX)与反斜杠转义 (player_aaaa / vod_data 字段用)"""
        if not s:
            return ""
        try:
            return s.encode('utf-8').decode('unicode_escape')
        except:
            return s.replace('\\/', '/').replace('\\"', '"')

    def _field(self, html, name):
        """从 player_aaaa.vod_data 中提取转义字段"""
        m = re.search(r'"%s"\s*:\s*"((?:[^"\\]|\\.)*)"' % name, html)
        if m:
            return self._unescape(m.group(1))
        return ""

    # ==================== 分类配置 ====================
    # 顶层分类使用 slug (导航/搜索均使用 slug, 比数字 id 更稳)
    cats = [
        {"type_name": "电影", "type_id": "dianying"},
        {"type_name": "电视剧", "type_id": "dianshiju"},
        {"type_name": "综艺", "type_id": "zongyi"},
        {"type_name": "动漫", "type_id": "dongman"},
        {"type_name": "短剧", "type_id": "duanju"},

    ]

    def _build_filters(self):
        """基础筛选(地区/语言/年份/排序). 注意: 本站无 vodshow 筛选路由, 仅作展示, 不强制生效"""
        filters = {}
        area_values = [
            {"n": "全部", "v": ""},
            {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"},
            {"n": "韩国", "v": "韩国"}, {"n": "日本", "v": "日本"}, {"n": "美国", "v": "美国"},
            {"n": "英国", "v": "英国"}, {"n": "泰国", "v": "泰国"},
        ]
        lang_values = [
            {"n": "全部", "v": ""},
            {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"},
            {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"},
        ]
        year_values = [
            {"n": "全部", "v": ""},
            {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"},
            {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"},
        ]
        sort_values = [
            {"n": "最新", "v": ""},
            {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"},
        ]
        common = [
            {"key": "area", "name": "地区", "value": area_values},
            {"key": "lang", "name": "语言", "value": lang_values},
            {"key": "year", "name": "年份", "value": year_values},
            {"key": "by", "name": "排序", "value": sort_values},
        ]
        for c in self.cats:
            filters[c["type_id"]] = common
        return filters

    # ==================== 通用视频列表解析 (module-item 结构) ====================
    def _parse_video_list(self, html):
        """解析视频列表 (mxone 模板的 module-item 容器)
        HTML结构:
        <div class="module-item">
          <div class="module-item-pic">
            <a class="module-item-title" href="/vodplay/{id}-{from}-{nid}.html" title="{title}">
              <img data-original="{pic}" src="{loading.gif}" ...>
            </a>
          </div>
          <div class="video-info">
            <span class="video-subname">{remarks}</span>
          </div>
        </div>
        """
        if not html:
            return []
        try:
            tree = etree.HTML(html)
        except:
            return []
        videos = []
        seen_ids = set()
        # 兼容两种容器: 分类/首页用 module-item, 搜索结果页用 module-search-item
        items = tree.xpath(
            '//div[contains(concat(" ", normalize-space(@class), " "), " module-item ") '
            'or contains(concat(" ", normalize-space(@class), " "), " module-search-item ")]'
        )
        for it in items:
            # 标题: 优先 module-item-title (短标题), 否则用第一个 vodplay 链接
            title_a = it.xpath('.//a[contains(@class, "module-item-title")]')
            if title_a and title_a[0].text:
                title = title_a[0].text.strip()
                href = title_a[0].get('href', '') or ''
            else:
                # 回退: 卡片内第一个指向 /vodplay/ 的链接
                a = it.xpath('.//a[contains(@href, "/vodplay/")]')
                if not a:
                    continue
                href = a[0].get('href', '') or ''
                # 标题
                title = (a[0].text or '').strip()
                if not title:
                    title = (a[0].get('title') or '').strip()
                # 清洗搜索页 "立刻播放"/"免费观看" 等动作前缀
                for pre in ('立刻播放', '免费观看', '在线观看', '播放'):
                    if title.startswith(pre):
                        title = title[len(pre):].strip()

            m = re.search(r'/vodplay/(\d+)', href)
            if not m:
                continue
            vid = m.group(1)
            if vid in seen_ids:
                continue
            seen_ids.add(vid)

            # 图片 (优先 data-src, 其次 data-original, 过滤占位 loading 图)
            pic = ""
            img = it.xpath('.//img')
            if img:
                pic = img[0].get('data-src') or img[0].get('data-original') or img[0].get('src') or ''
                if pic and ('loading' in pic.lower() or 'logo' in pic.lower()):
                    pic = ""

            # 备注 (video-subname / pic-text)
            note = ""
            rem = it.xpath('.//*[contains(@class, "video-subname")]')
            if rem and rem[0].text:
                note = rem[0].text.strip()
            if not note:
                rp = it.xpath('.//*[contains(@class, "pic-text")]')
                if rp and rp[0].text:
                    note = rp[0].text.strip()

            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self._fix_pic(pic),
                "vod_remarks": note,
            })
        return videos

    def _parse_search_list(self, html):
        """搜索结果同样使用 module-item 格式"""
        return self._parse_video_list(html)

    # ==================== 线路与选集解析 ====================
    def _parse_play_sources(self, html, vid):
        """解析 vodplay 页的播放线路与选集
        页面结构 (mxone):
          线路切换: div.module-player-tab 内若干 .tab-item
            未选中: <a class="module-tab-item tab-item" href="/vodplay/{vid}-{from}-1.html">
                      <span data-dropdown-value="线路名">线路名</span><small>集数</small>
                    </a>
            当前选中: <div class="module-tab-item tab-item selected" data-dropdown-value="线路名">
          选集列表: 每条线路一个 div.module-player-list
            线路 from 来自排序按钮 to="#sort-item-{from}"
            选集链接仅存在于 div.scroll-content 内:
              <a href="/vodplay/{vid}-{from}-{nid}.html" title="播放{片名}{集名}"><span>{集名}</span></a>
            注意: 排序下拉(module-sorttab .sort-item)内是一份镜像链接, 不能计入, 否则选集重复
        返回: [(from, 线路名, [(nid, 集名, url), ...]), ...] (按页面线路顺序)
        """
        try:
            tree = etree.HTML(html)
        except:
            return []

        # ---- 1. 线路名映射 from -> name ----
        name_map = {}
        selected_name = ""
        tab = tree.xpath('//div[contains(@class,"module-player-tab")]')
        for node in (tab[0].xpath('.//*[contains(@class,"tab-item")]') if tab else []):
            cls = (node.get('class') or '').split()
            name = (node.get('data-dropdown-value') or '').strip()
            if not name:
                sp = node.xpath('.//span[@data-dropdown-value]')
                if sp:
                    name = (sp[0].get('data-dropdown-value') or '').strip()
            if 'selected' in cls:
                selected_name = name
            m = re.search(r'/vodplay/\d+-(\d+)-\d+\.html', node.get('href') or '')
            if name and m:
                name_map[m.group(1)] = name

        # ---- 2. 逐条线路解析选集 (仅取 scroll-content, 跳过排序下拉镜像) ----
        sources = []
        for box in tree.xpath('//div[contains(@class,"module-player-list")]'):
            frm = ""
            to_nodes = box.xpath('.//*[@to]')
            if to_nodes:
                mto = re.search(r'sort-item-(\d+)', to_nodes[0].get('to') or '')
                if mto:
                    frm = mto.group(1)

            eps = []
            seen_nid = set()
            for a in box.xpath('.//div[contains(@class,"scroll-content")]'
                               '//a[contains(@href,"/vodplay/")]'):
                href = a.get('href') or ''
                m = re.search(r'/vodplay/(\d+)-(\d+)-(\d+)\.html', href)
                if not m or m.group(1) != str(vid):
                    continue
                ep_from, nid = m.group(2), m.group(3)
                if not frm:
                    frm = ep_from
                if nid in seen_nid:
                    continue
                seen_nid.add(nid)
                # 集名: <span> 文本 (当前播放集内可能还有 playon 等装饰节点, 只取 span)
                sp = a.xpath('.//span')
                ep_name = (sp[0].text or '').strip() if sp and sp[0].text else ''
                if not ep_name:
                    # 兜底: title="播放{片名}{集名}"
                    title = (a.get('title') or '').strip()
                    ep_name = re.sub(r'^播放', '', title) or str(nid)
                eps.append((nid, ep_name, href))

            if frm and eps:
                sources.append([frm, eps])

        # ---- 3. 选中线路 (无 href 的 div.tab-item) 名称补全 ----
        if selected_name:
            for box in tree.xpath('//div[contains(@class,"module-player-list")'
                                  ' and contains(@class,"selected")]'):
                to_nodes = box.xpath('.//*[@to]')
                if to_nodes:
                    mto = re.search(r'sort-item-(\d+)', to_nodes[0].get('to') or '')
                    if mto:
                        name_map.setdefault(mto.group(1), selected_name)

        # ---- 4. 组装 (名称缺失时给序号兜底) ----
        result = []
        for i, (frm, eps) in enumerate(sources):
            name = name_map.get(frm) or "MXVOD线路{0}".format(i + 1)
            result.append((frm, name, eps))
        return result

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
        # 本站列表页为单页(无服务端分页控件), page 参数仅作占位
        result = {"list": [], "page": int(pg) if pg else 1, "pagecount": 1, "limit": 30, "total": 0}
        try:
            page = int(pg) if pg else 1
            path = "/vodtype/{0}.html".format(tid)
            html = self._req(path)
            if html:
                videos = self._parse_video_list(html)
                result["list"] = videos
                result["page"] = page
                result["total"] = len(videos)
                result["limit"] = len(videos) if videos else 30
                # 单页: 若一页满 30 条默认还有下一页(实际本站多为单页)
                result["pagecount"] = 2 if len(videos) >= 30 else 1
        except Exception as e:
            print("categoryContent error: {0}".format(e))
        return result

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            if not key:
                return result
            # 13个dash占位 + wd 参数 (与本站搜索表单 action 一致)
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

            # 抓详情/播放合一页 (默认播放源1, 第1集)
            html = self._req("/vodplay/{0}-1-1.html".format(vid))
            if not html:
                return result

            # ---- 标题 ----
            vod_name = self._field(html, "vod_name")
            if not vod_name:
                m = re.search(r'<title>([^<]+)</title>', html)
                if m:
                    vod_name = m.group(1).split('-')[0].strip()

            # ---- 图片 (第一个 /upload/vod/ 图片, 排除 logo) ----
            vod_pic = ""
            imgs = re.findall(r'src="(/upload/vod/[^"]+\.(?:jpg|webp|png))"', html)
            up = [i for i in imgs if 'logo' not in i]
            if up:
                vod_pic = self._fix_pic(up[0])
            if not vod_pic:
                vod_pic = self._fix_pic(self._field(html, "vod_pic"))

            # ---- 基本信息 (优先 vod_data 转义字段) ----
            vod_actor = self._field(html, "vod_actor")
            vod_director = self._field(html, "vod_director")
            vod_class = self._field(html, "vod_class")
            vod_year = self._field(html, "vod_year")
            if not vod_year:
                # 主影片年份: 优先信息区首个 video-class (侧边推荐为 2025/2026, 主片在前)
                m = re.search(r'video-class">\s*(\d{4})', html)
                if m:
                    vod_year = m.group(1)
            if not vod_year:
                m = re.search(r'<title>[^<]*?(\d{4})', html)
                if m:
                    vod_year = m.group(1)
            vod_area = self._field(html, "vod_area")
            vod_lang = self._field(html, "vod_lang")
            vod_remarks = self._field(html, "vod_remarks")

            # ---- 简介 (JSON-LD description 优先, 兜底 HTML 容器) ----
            vod_content = self._field(html, "vod_content")
            if not vod_content:
                m = re.search(r'"description"\s*:\s*"([^"]+)"', html)
                if m:
                    vod_content = m.group(1)
            if not vod_content:
                for cls in ['content', 'detail-content', 'vod-content', 'sketch', 'introduced', 'desc']:
                    m = re.search(r'class="[^"]*%s[^"]*"[^>]*>([\s\S]*?)</(?:div|p)>' % cls, html)
                    if m:
                        txt = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                        if len(txt) > 20:
                            vod_content = txt
                            break

            # ---- 播放源与分集 (DOM 解析: 线路名取 player-tab, 选集取 scroll-content) ----
            play_from_list = []
            play_url_list = []
            for _, src_name, eps in self._parse_play_sources(html, vid):
                play_from_list.append(src_name)
                play_url_list.append("#".join(
                    "{0}${1}".format(ep_name, ep_url) for _, ep_name, ep_url in eps
                ))

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
    # ==================== 播放 ====================
    def _extract_json_obj(self, html, var_name):
        """提取 var {var_name} = {...} 的完整对象文本
        用字符串感知的花括号配对, 避免嵌套对象/转义引号导致的截断
        """
        m = re.search(r'var\s+%s\s*=\s*' % re.escape(var_name), html)
        if not m:
            return ""
        try:
            start = html.index('{', m.end())
        except ValueError:
            return ""
        depth = 0
        in_str = False
        esc = False
        j = start
        while j < len(html):
            ch = html[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        return html[start:j + 1]
            j += 1
        return ""

    def _decode_js_url(self, s):
        """还原 JS 字符串中的 URL (\\/ -> /, 反转义引号, 处理 \\uXXXX)"""
        if not s:
            return ""
        u = s.replace('\\/', '/').replace('\\"', '"')
        if '\\u' in u:
            try:
                u = u.encode('utf-8').decode('unicode_escape')
            except:
                pass
        return u

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "playUrl": "", "url": "", "header": "", "jx": 0}
        try:
            # id格式: 集名$播放路径 (如 "1$/vodplay/225914-1-1.html")
            play_url_part = id.split("$")[-1] if "$" in id else id
            if not play_url_part.startswith("/"):
                play_url_part = "/" + play_url_part

            html = self._req_play(play_url_part)
            if not html:
                return result

            # 播放数据变量 (苹果CMS 常见 player_aaaa, 部分模板用 player_data)
            raw = ""
            for var in ("player_aaaa", "player_data", "player"):
                raw = self._extract_json_obj(html, var)
                if raw:
                    break

            url = ""
            if raw:
                # 优先取顶层 url (注意: 嵌套的 vod_data 里没有 url 字段, 但用 key 顺序更稳)
                m_url = re.search(r'"url"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
                if m_url:
                    url = self._decode_js_url(m_url.group(1))

                encrypt = 0
                m_enc = re.search(r'"encrypt"\s*:\s*(\d+)', raw)
                if m_enc:
                    encrypt = int(m_enc.group(1))
                if url and encrypt > 0:
                    url = self._decrypt_url(url, encrypt)

            # 兜底1: 页面里直接出现 m3u8/mp4 直链
            if not url:
                m_direct = re.search(
                    r'["\'](https?:\\?/\\?/[^"\']+?\.(?:m3u8|mp4)[^"\']*)["\']', html
                )
                if m_direct:
                    url = self._decode_js_url(m_direct.group(1))

            if url:
                headers = {
                    "User-Agent": self.ua,
                    "Referer": self.host + play_url_part,
                }
                if ".m3u8" in url or ".mp4" in url:
                    result["parse"] = 0
                    result["jx"] = 0
                else:
                    # 其他外链, 交给嗅探
                    result["parse"] = 1
                    result["jx"] = 1
                result["url"] = url
                result["header"] = json.dumps(headers)
                return result

            # 兜底2: 嗅探模式
            result["parse"] = 1
            result["jx"] = 1
            result["url"] = self.host + play_url_part
            result["header"] = json.dumps({"User-Agent": self.ua})
        except Exception as e:
            print("playerContent error: {0}".format(e))
        return result

    # ==================== URL 解密 ====================
    def _decrypt_url(self, encrypted, encrypt_type):
        """解密播放URL (encrypt:2 = base64+url-encode, 1 = url-encode, 0 = 无加密)"""
        try:
            if encrypt_type == 2:
                decoded = base64.b64decode(encrypted).decode('utf-8')
                return unquote(decoded)
            elif encrypt_type == 1:
                return unquote(encrypted)
            elif encrypt_type == 0:
                return encrypted
        except:
            pass
        return encrypted