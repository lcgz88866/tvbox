# -*- coding: utf-8 -*-
# 66影视 (6v666.com) TVBox Python Spider
# 帝国CMS (EmpireCMS), 纯HTML解析, 无API
# 5个分类, 子分类筛选, 多播放源, iframe播放器解析(artplayer+hls.js)

import re
import sys
import json
import ssl
import urllib.parse
import urllib.request

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


class Spider(Spider):

    HOST = "https://6v666.com"
    # iframe播放器域名
    PLAYER_HOST = "https://play.phimgood.com"
    UA = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

    # 主分类 (type_id为URL路径段)
    CATEGORIES = [
        {"type_name": "电影", "type_id": "dy"},
        {"type_name": "电视剧", "type_id": "dsj"},
        {"type_name": "动漫", "type_id": "dmjj"},
        {"type_name": "综艺", "type_id": "zyjm"},
        {"type_name": "短剧", "type_id": "duanju"},
    ]

    # 子分类 (v为子分类URL路径段, 拼接为 /{tid}/{v}/)
    SUB_CATS = {
        "dy": [
            {"n": "全部", "v": ""},
            {"n": "动作片", "v": "bangumi"},
            {"n": "喜剧片", "v": "tvplay"},
            {"n": "爱情片", "v": "aqp"},
            {"n": "科幻片", "v": "khp"},
            {"n": "剧情片", "v": "jqp"},
            {"n": "恐怖片", "v": "kbp"},
            {"n": "战争片", "v": "zzp"},
            {"n": "纪录片", "v": "jlp"},
            {"n": "动画片", "v": "donghuapian"},
        ],
        "dsj": [
            {"n": "全部", "v": ""},
            {"n": "国剧", "v": "dlj"},
            {"n": "日韩剧", "v": "rhj"},
            {"n": "欧美剧", "v": "omj"},
        ],
        "dmjj": [
            {"n": "全部", "v": ""},
            {"n": "动漫", "v": "dongman"},
        ],
    }

    def getName(self):
        return "66影视"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": self.UA,
            "Referer": self.HOST,
        }
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

    # ===== HTTP =====

    def _fetch_html(self, url, timeout=15):
        """获取HTML页面 (优先TVBox fetch, 失败则回退urllib)"""
        # 优先使用 TVBox 自带的 fetch
        if hasattr(self, 'fetch') and callable(getattr(self, 'fetch', None)):
            try:
                rsp = self.fetch(url, headers=self.headers)
                if rsp and rsp.text and len(rsp.text) > 100:
                    return rsp.text
            except Exception:
                pass
            # fetch失败, 回退到urllib
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=timeout) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception:
            return ""

    def _post_html(self, url, data, timeout=15):
        """POST请求 (带cookie跟随重定向)"""
        try:
            import http.cookiejar
            cj = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(cj),
                urllib.request.HTTPSHandler(context=self._ssl_ctx)
            )
            post_data = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=post_data, headers={
                "User-Agent": self.UA,
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": self.HOST,
            })
            resp = opener.open(req, timeout=timeout)
            return resp.read().decode('utf-8', errors='ignore')
        except Exception:
            return ""

    # ===== 首页 =====

    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        result["class"] = self.CATEGORIES
        for cat in self.CATEGORIES:
            tid = cat["type_id"]
            filters = []
            if tid in self.SUB_CATS:
                filters.append({
                    "key": "cateId",
                    "name": "类型",
                    "value": self.SUB_CATS[tid],
                })
            result["filters"][tid] = filters
        return result

    def homeVideoContent(self):
        result = {"list": []}
        html = self._fetch_html(self.HOST + "/")
        if html:
            items = self._parse_cards(html)
            result["list"] = items[:30]
        return result

    # ===== 分类 =====

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 30, "total": 0}
        try:
            extend = extend or {}
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except (json.JSONDecodeError, ValueError):
                    extend = {}

            cate_id = extend.get("cateId", "") if isinstance(extend, dict) else ""

            # 健壮的页码处理
            try:
                page = int(pg) if pg else 1
                if page < 1:
                    page = 1
            except (ValueError, TypeError):
                page = 1

            # 构造分类URL
            # 子分类: /{tid}/{cateId}/  主分类: /{tid}/
            # 分页: 第1页无后缀, 第2+页 /{tid}/index_{page}.html 或 /{tid}/{cateId}/index_{page}.html
            if cate_id:
                base_path = f"/{tid}/{cate_id}"
            else:
                base_path = f"/{tid}"

            if page <= 1:
                url = f"{self.HOST}{base_path}/"
            else:
                url = f"{self.HOST}{base_path}/index_{page}.html"

            html = self._fetch_html(url)
            if not html:
                return result

            # 解析卡片
            items = self._parse_cards(html)

            # 提取总页数 (从"尾页"链接)
            pagecount = 1
            pc_m = re.search(r'href="[^"]*index_(\d+)\.html"[^>]*>尾页', html)
            if pc_m:
                pagecount = int(pc_m.group(1))
            else:
                # 没有尾页链接, 检查是否有下一页
                next_m = re.search(r'href="[^"]*index_(\d+)\.html"[^>]*>下一页', html)
                if next_m:
                    # 有下一页, 当前页至少有2页
                    pagecount = page + 1
                elif items:
                    pagecount = page

            # 去重
            seen = set()
            unique = []
            for v in items:
                if v["vod_id"] not in seen:
                    seen.add(v["vod_id"])
                    unique.append(v)
            items = unique

            result["list"] = items
            result["page"] = page
            result["pagecount"] = max(1, pagecount)
            result["limit"] = 30
            result["total"] = pagecount * 30  # 估算
        except Exception:
            pass
        return result

    def _parse_cards(self, html):
        """解析视频卡片 (link-hover 结构)
        帝国CMS卡片: <a class="link-hover" href="/dy/tvplay/24976.html" title="夜王">
          <img class="lazy" data-original="图片" ...>
          <p class="name">标题</p>
          <p class="other"><i>状态</i></p>
        </a>
        """
        items = []
        try:
            # 匹配 link-hover 的 a 标签 (兼容属性顺序)
            pattern = r'<a\s+class="link-hover"\s+href="([^"]+)"\s+title="([^"]*)"[^>]*>(.*?)</a>'
            matches = re.findall(pattern, html, re.DOTALL)

            # 备用: href 在 class 前面
            if not matches:
                pattern = r'<a\s+href="([^"]+)"\s+title="([^"]*)"\s+class="link-hover"[^>]*>(.*?)</a>'
                matches = re.findall(pattern, html, re.DOTALL)

            # 再备用: title 在 href 前面
            if not matches:
                pattern = r'<a\s+class="link-hover"\s+title="([^"]*)"\s+href="([^"]+)"[^>]*>(.*?)</a>'
                matches = [(m[1], m[0], m[2]) for m in re.findall(pattern, html, re.DOTALL)]

            for href, title_attr, inner in matches:
                # 去掉前导斜杠, 作为vod_id
                vod_id = href.lstrip('/')

                # 标题: 优先title属性, 其次class="name"
                name = title_attr.strip() if title_attr else ""
                if not name:
                    name_m = re.search(r'<p\s+class="name">([^<]+)</p>', inner)
                    if name_m:
                        name = name_m.group(1).strip()

                # 封面图: data-original 优先, 其次 src
                pic = re.search(r'data-original="([^"]+)"', inner)
                if not pic:
                    pic = re.search(r'src="([^"]+)"', inner)

                # 状态/备注
                remarks = re.search(r'<p\s+class="other">.*?<i>([^<]*)</i>', inner, re.DOTALL)

                if vod_id and name:
                    items.append({
                        "vod_id": vod_id,
                        "vod_name": name,
                        "vod_pic": pic.group(1) if pic else "",
                        "vod_remarks": remarks.group(1).strip() if remarks else "",
                    })
        except Exception:
            pass
        return items

    # ===== 详情 =====

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = ids[0]
            html = self._fetch_html(f"{self.HOST}/{vod_id}")
            if not html:
                return result

            # 标题: h1.title 最后一个a标签文本, 或 title 标签
            title = ""
            h1_m = re.search(r'<h1[^>]*class="title"[^>]*>(.*?)</h1>', html, re.DOTALL)
            if h1_m:
                a_tags = re.findall(r'<a[^>]*>([^<]+)</a>', h1_m.group(1))
                if a_tags:
                    title = a_tags[-1].strip()
            if not title:
                title_m = re.search(r'<title>([^<]+)</title>', html)
                if title_m:
                    title = re.split(r'[-]+', title_m.group(1))[0].strip()

            # 封面图: ct-l 下的 img src
            pic = re.search(r'<div\s+class="ct-l"[^>]*>.*?<img[^>]+src="([^"]+)"', html, re.DOTALL)
            if not pic:
                pic = re.search(r'<img[^>]+src="(https?://[^"]+)"[^>]+alt=""', html)

            # 元数据: 从 ◎字段名: 值 格式提取
            year, area, vtype, director, actor, content = self._parse_metadata(html)

            # 播放源和剧集
            play_from, play_url = self._parse_play_sources(html)

            vod = {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic.group(1) if pic else "",
                "vod_actor": actor,
                "vod_director": director,
                "vod_year": year,
                "vod_area": area,
                "vod_remarks": "",
                "vod_content": content,
                "type_name": vtype,
                "vod_play_from": play_from,
                "vod_play_url": play_url,
            }
            result["list"].append(vod)
        except Exception:
            pass
        return result

    def _parse_metadata(self, html):
        """从详情页HTML提取元数据 (◎字段名: 值 格式)"""
        year = ""
        area = ""
        vtype = ""
        director = ""
        actor = ""
        content = ""

        try:
            # 提取ct mb clearfix区域内的所有div文本
            ct_m = re.search(r'<div\s+class="ct\s+mb\s+clearfix"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL)
            if ct_m:
                block = ct_m.group(1)
            else:
                # 备用: 查找所有包含◎的div
                block = html

            # 将HTML转为文本行
            text = re.sub(r'<[^>]+>', '\n', block)
            text = text.replace('&nbsp;', ' ')
            # 归一化全角空格
            text = re.sub(r'\u3000+', ' ', text)
            lines = [l.strip() for l in text.split('\n') if l.strip()]

            # 解析 ◎字段名: 值
            fields = {}
            current_field = None
            current_value = ""
            for line in lines:
                m = re.match(r'◎(.+?)[:：]\s*(.*)', line)
                if m:
                    if current_field:
                        fields[current_field] = current_value.strip()
                    current_field = m.group(1).strip()
                    current_value = m.group(2).strip()
                elif current_field and not line.startswith('◎'):
                    # 续行 (演员列表等)
                    current_value += " " + line
            if current_field:
                fields[current_field] = current_value.strip()

            # 映射字段
            for k, v in fields.items():
                k_clean = k.replace(' ', '').replace('\u3000', '')
                if k_clean.startswith('年') and not year:
                    ym = re.search(r'(\d{4})', v)
                    if ym:
                        year = ym.group(1)
                elif k_clean.startswith('产') and not area:
                    area = v.split('/')[0].strip()
                elif k_clean.startswith('类') and not vtype:
                    vtype = v
                elif k_clean.startswith('导') and not director:
                    director = v
                elif k_clean.startswith('主') and not actor:
                    actor = v.replace(' / ', ',').replace('/', ',').strip()

            # 提取简介: ◎简　　介 后的内容 (可能没有冒号, 内容在后续div中)
            intro_m = re.search(r'◎简.*?</div>(.*?)(?:<hr|<table|◎[^简]|class="playfrom)', block, re.DOTALL)
            if intro_m:
                intro_text = re.sub(r'<[^>]+>', ' ', intro_m.group(1))
                intro_text = intro_text.replace('&nbsp;', ' ').strip()
                intro_text = re.sub(r'\s+', ' ', intro_text).strip()
                if intro_text:
                    content = intro_text[:200] + ("..." if len(intro_text) > 200 else "")
        except Exception:
            pass

        return year, area, vtype, director, actor, content

    def _parse_play_sources(self, html):
        """解析播放源和剧集列表
        帝国CMS结构:
        - 播放源名称: <li><i class="playerico"></i> 视频播列表一</li>
        - 剧集链接: <a href="/e/DownSys/play/?classid=X&id=Y&pathidN=Z&bf=W">第01集</a>
        - bf参数区分播放源 (0=源1, 1=源2, ...)
        """
        try:
            # 播放源名称
            source_names = re.findall(r'</i>\s*([^<]+?)\s*</li>', html)
            # 过滤出播放源名称 (包含"播放"的)
            source_names = [s.strip() for s in source_names if '播放' in s or '线路' in s or '视频' in s]

            # 所有播放链接
            play_links = re.findall(
                r'href\s*=\s*"(/e/DownSys/play/\?[^"]+)"[^>]*>\s*([^<]*)\s*</a>',
                html, re.DOTALL
            )

            # 按bf参数分组
            source_map = {}
            for url, name in play_links:
                bf_m = re.search(r'bf=(\d+)', url)
                if bf_m:
                    bf = int(bf_m.group(1))
                    if bf not in source_map:
                        source_map[bf] = []
                    ep_name = name.strip()
                    if not ep_name:
                        # 尝试从title属性获取
                        ep_name = "播放"
                    source_map[bf].append(f"{ep_name}${self.HOST}{url}")

            # 构建播放源列表
            play_from_list = []
            play_url_list = []
            for i, bf in enumerate(sorted(source_map.keys())):
                if i < len(source_names):
                    source_name = source_names[i]
                else:
                    source_name = f"播放源{bf + 1}"
                play_from_list.append(source_name)
                play_url_list.append("#".join(source_map[bf]))

            # 提取磁力下载链接 (作为额外播放源)
            magnet_episodes = self._parse_magnet_links(html)
            if magnet_episodes:
                play_from_list.append("磁力下载")
                play_url_list.append("#".join(magnet_episodes))

            return "$$$".join(play_from_list), "$$$".join(play_url_list)
        except Exception:
            return "", ""

    def _parse_magnet_links(self, html):
        """从详情页提取磁力链接
        结构: <a href="magnet:?xt=urn:btih:...&dn=...">文件名.mkv</a>
        返回格式: ["文件名$magnet:?...", ...]
        """
        episodes = []
        try:
            # 匹配磁力链接 (注意HTML中 & 可能被转义为 &amp;)
            magnet_links = re.findall(
                r'<a[^>]+href\s*=\s*"(magnet:\?[^"]+)"[^>]*>(.*?)</a>',
                html, re.DOTALL | re.IGNORECASE
            )
            for url, name in magnet_links:
                # 清理名称
                name_clean = re.sub(r'<[^>]+>', '', name).strip()
                if not name_clean:
                    name_clean = "磁力下载"
                # 还原HTML实体 &amp; -> &
                url_clean = url.replace('&amp;', '&').replace('&#38;', '&')
                episodes.append(f"{name_clean}${url_clean}")
        except Exception:
            pass
        return episodes

    # ===== 搜索 =====

    def searchContent(self, key, quick, pg="1"):
        result = {"list": []}
        try:
            # 帝国CMS搜索: POST到/e/search/index.php, 302重定向到结果页
            html = self._post_html(
                f"{self.HOST}/e/search/index.php",
                {
                    'keyboard': key,
                    'show': 'title,zhuyan',
                    'tempid': '1',
                }
            )
            if html and len(html) > 1000:
                items = self._parse_cards(html)
                if items:
                    result["list"] = items[:30]
                    return result

            # 降级: GET方式 (帝国CMS部分配置支持)
            if not result["list"]:
                wd = urllib.parse.quote(key)
                url = f"{self.HOST}/e/search/index.php?keyboard={wd}&show=title,zhuyan&tempid=1"
                html = self._fetch_html(url)
                if html and len(html) > 1000:
                    items = self._parse_cards(html)
                    result["list"] = items[:30]
        except Exception:
            pass
        return result

    # ===== 播放 =====

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "header": "", "url": "", "playUrl": ""}
        try:
            # 提取播放页URL
            if "$" in id:
                play_url = id.split("$")[-1]
            else:
                play_url = id

            # 磁力链接直接返回
            if play_url.startswith("magnet:"):
                result["url"] = play_url
                result["parse"] = 0
                return result

            # 获取播放页HTML
            html = self._fetch_html(play_url)
            if not html:
                return result

            # 方式1: 提取iframe src
            iframe_m = re.search(r'<iframe[^>]*src="(https?://[^"]+)"', html)
            if iframe_m:
                iframe_src = iframe_m.group(1)

                # 获取iframe播放器页面
                iframe_html = self._fetch_html(iframe_src)
                if iframe_html:
                    # 提取视频URL (const url = "/xxx/index.m3u8?sign=xxx")
                    url_m = re.search(r'const\s+url\s*=\s*"([^"]+)"', iframe_html)
                    if url_m:
                        video_path = url_m.group(1)
                        if video_path.startswith('http'):
                            video_url = video_path
                        else:
                            domain_m = re.match(r'(https?://[^/]+)', iframe_src)
                            if domain_m:
                                video_url = domain_m.group(1) + video_path
                            else:
                                video_url = self.PLAYER_HOST + video_path

                        result["url"] = video_url
                        result["parse"] = 0
                        result["header"] = json.dumps({
                            "User-Agent": self.UA,
                            "Referer": iframe_src,
                        })
                        return result

                    # 备用: 尝试从video/source标签提取
                    video_m = re.search(r'<(?:source|video)[^>]+src="([^"]+)"', iframe_html)
                    if video_m:
                        result["url"] = video_m.group(1)
                        result["parse"] = 0
                        return result

                # 最终降级: 返回iframe src, 让解析器处理
                result["url"] = iframe_src
                result["parse"] = 1
                return result

            # 方式2: Flash内嵌播放器 (flashvars.a = m3u8地址)
            # 播放列表二、四使用此格式: var flashvars={f:'m3u8.swf', a:'https://.../index.m3u8', ...};
            flash_m = re.search(r"a\s*:\s*['\"](https?://[^'\"]+\.m3u8[^'\"]*)['\"]", html)
            if flash_m:
                video_url = flash_m.group(1)
                result["url"] = video_url
                result["parse"] = 0
                result["header"] = json.dumps({
                    "User-Agent": self.UA,
                    "Referer": play_url,
                })
                return result
        except Exception:
            pass
        return result

    # ===== 工具 =====

    def _clean_text(self, text):
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        text = re.sub(r'\u3000+', ' ', text)
        text = text.strip()
        if len(text) > 200:
            text = text[:200] + "..."
        return text


if __name__ == "__main__":
    s = Spider()
    s.init()

    print("===== 首页分类 =====")
    home = s.homeContent(True)
    print(f"分类数: {len(home['class'])}")
    for c in home["class"]:
        print(f"  {c['type_name']} -> {c['type_id']}")
        filters = home["filters"].get(c["type_id"], [])
        for f in filters:
            print(f"    筛选: {f['name']} ({len(f['value'])}项)")
            for v in f["value"][:3]:
                print(f"      {v['n']} -> {v['v']}")
            if len(f["value"]) > 3:
                print(f"      ... 共{len(f['value'])}项")

    print("\n===== 首页推荐 =====")
    hv = s.homeVideoContent()
    print(f"推荐数: {len(hv['list'])}")
    for v in hv["list"][:5]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 分类列表 (电影第1页) =====")
    cat = s.categoryContent("dy", "1", True, {})
    print(f"返回: {len(cat['list'])}条, 页数: {cat['pagecount']}")
    for v in cat["list"][:5]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 分类列表 (电影第2页) =====")
    cat2 = s.categoryContent("dy", "2", True, {})
    print(f"返回: {len(cat2['list'])}条, 页数: {cat2['pagecount']}")
    for v in cat2["list"][:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 分类列表 (电影-动作片第1页) =====")
    cat3 = s.categoryContent("dy", "1", True, {"cateId": "bangumi"})
    print(f"返回: {len(cat3['list'])}条, 页数: {cat3['pagecount']}")
    for v in cat3["list"][:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 分类列表 (电视剧-国剧第1页) =====")
    cat4 = s.categoryContent("dsj", "1", True, {"cateId": "dlj"})
    print(f"返回: {len(cat4['list'])}条, 页数: {cat4['pagecount']}")
    for v in cat4["list"][:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 分类列表 (综艺第1页) =====")
    cat5 = s.categoryContent("zyjm", "1", True, {})
    print(f"返回: {len(cat5['list'])}条, 页数: {cat5['pagecount']}")
    for v in cat5["list"][:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 详情页 + 播放 =====")
    if hv["list"]:
        vid = hv["list"][0]["vod_id"]
        detail = s.detailContent([vid])
        if detail["list"]:
            vod = detail["list"][0]
            print(f"  标题: {vod['vod_name']}")
            print(f"  年份: {vod['vod_year']}  地区: {vod['vod_area']}  类型: {vod.get('type_name', '')}")
            print(f"  导演: {vod['vod_director']}")
            print(f"  演员: {vod['vod_actor'][:80]}")
            print(f"  简介: {vod['vod_content'][:100]}")
            print(f"  播放源: {vod['vod_play_from'][:80]}")
            first_ep = vod["vod_play_url"].split("#")[0]
            play = s.playerContent("", first_ep, [])
            print(f"  播放URL: {play.get('url', '')[:100]}")
            print(f"  Parse: {play.get('parse')}")
        else:
            print("  详情页解析失败")

    print("\n===== 搜索 (战) =====")
    search = s.searchContent("战", False)
    print(f"结果: {len(search['list'])}条")
    for v in search["list"][:5]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 测试完成 =====")