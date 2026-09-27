# -*- coding: utf-8 -*-
"""
皮皮驴 (pipilv.top) — TVBox/CatVod Spider
苹果CMS二开 + mxtheme模板 + 验证码防护

路由:
  首页: /
  分类: /type/<tid>.html  (1=电影 2=电视剧 3=综艺 4=动漫)
  详情: /v/<vod_id>.html
  播放: /play/<vod_id>-<sid>-<nid>.html  (player_aaaa)
  搜索: /search/<keyword>-------------.html
  验证: POST /captcha.php type=verify&check=<code>

特点:
  1. init() 自动识别验证码建立会话 (ddddocr)
  2. 会话过期自动重新验证
  3. 移动端UA (桌面端404)
  4. 图片用 data-original (懒加载, 豆瓣图床)
  5. player_aaaa 用花括号计数精确提取JSON
"""
import sys, re, json, time, hashlib, base64, urllib.parse

sys.path.append('..')
from base.spider import Spider

try:
    import requests
    from requests.adapters import HTTPAdapter
    requests.packages.urllib3.disable_warnings()
except ImportError:
    requests = None

try:
    import ddddocr
    _ocr = None  # lazy init
except ImportError:
    ddddocr = None


class Spider(Spider):
    HOST = 'https://www.pipilv.top'
    UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
    TIMEOUT = 12
    s = None
    _verified = False
    _verify_time = 0

    def init(self, extend=''):
        self._verified = False
        self._verify_time = 0
        if requests:
            self.s = requests.Session()
            self.s.mount('https://', HTTPAdapter(max_retries=1))
            self.s.verify = False
        else:
            self.s = None
        self._ensure_verified()
        return self

    def getName(self): return '皮皮驴'
    def isVideoFormat(self, url): return bool(re.search(r'\.(m3u8|mp4|flv)(\?|$)', str(url), re.I))
    def manualVideoCheck(self): return False
    def destroy(self): return

    # ======================== 验证码
    def _ensure_verified(self):
        """确保会话已通过验证码验证"""
        if self._verified and time.time() - self._verify_time < 1800:
            return True
        if not self.s or not ddddocr:
            return False
        global _ocr
        if _ocr is None:
            _ocr = ddddocr.DdddOcr()
        h = self._hd()
        # 1. 访问首页建立session
        self.s.get(self.HOST + '/', headers=h, timeout=self.TIMEOUT)
        # 2. 多次尝试验证码识别
        for attempt in range(20):
            try:
                # 获取验证码图片
                r = self.s.get(f'{self.HOST}/captcha.php?type=code&r={int(time.time()*1000)}',
                               headers=h, timeout=self.TIMEOUT)
                if not r.content:
                    continue
                # OCR识别
                code = re.sub(r'[^a-zA-Z0-9]', '', _ocr.classification(r.content).strip())
                if len(code) < 3:
                    continue
                # 提交验证
                r2 = self.s.post(f'{self.HOST}/captcha.php',
                                 data=f'type=verify&check={code}',
                                 headers={**h, 'X-Requested-With': 'XMLHttpRequest',
                                          'Content-Type': 'application/x-www-form-urlencoded'},
                                 timeout=self.TIMEOUT)
                if r2.text.strip().startswith('{'):
                    resp = json.loads(r2.text)
                    if resp.get('code') == 1:
                        self._verified = True
                        self._verify_time = time.time()
                        return True
            except:
                continue
        return False

    # ======================== HTTP
    def _hd(self, ref=None):
        return {'User-Agent': self.UA, 'Accept': '*/*', 'Accept-Language': 'zh-CN,zh;q=0.9',
                'Referer': ref or self.HOST + '/'}

    def fetch(self, url, ref=None):
        """GET请求，自动处理验证码"""
        h = self._hd(ref)
        if self.s:
            for attempt in range(2):
                try:
                    r = self.s.get(url, headers=h, timeout=self.TIMEOUT)
                    # 检查是否被验证码拦截
                    if '系统安全验证' in r.text:
                        self._verified = False
                        if self._ensure_verified():
                            continue  # 重新请求
                        return ''
                    if r.status_code == 200 and len(r.content) > 200:
                        return r.text
                    if r.status_code == 404:
                        return ''
                except:
                    pass
        # 宿主fetch兜底
        try:
            rsp = Spider.fetch(self, url, headers=h)
            if rsp is not None:
                return getattr(rsp, 'text', '') or ''
        except:
            pass
        return ''

    @staticmethod
    def _txt(s):
        if not s: return ''
        s = re.sub(r'<script[\s\S]*?</script>', ' ', s, flags=re.I)
        s = re.sub(r'<style[\s\S]*?</style>', ' ', s, flags=re.I)
        s = re.sub(r'<[^>]+>', ' ', s)
        s = re.sub(r'&(?:nbsp|#160);?', ' ', s)
        s = re.sub(r'&(amp|quot|lt|gt|#39|apos);', lambda m: {'amp': '&', 'quot': '"', 'lt': '<', 'gt': '>', '#39': "'", 'apos': "'"}[m.group(1)], s)
        return re.sub(r'\s+', ' ', s).strip()

    @staticmethod
    def _first(text, pats):
        for p in pats:
            m = re.search(p, text or '', re.S | re.I)
            if m: return Spider._txt(m.group(1))
        return ''

    @staticmethod
    def _abs(u):
        if not u: return ''
        u = u.strip()
        if u.startswith('//'): return 'https:' + u
        if u.startswith('http'): return u
        return Spider.HOST.rstrip('/') + '/' + u.lstrip('/')

    @staticmethod
    def _int(s, d=1):
        try: return int(re.sub(r'\D', '', str(s)) or d)
        except: return d

    @staticmethod
    def _extract_json(html, var_name):
        """用花括号计数精确提取JS变量中的JSON对象"""
        idx = html.find(var_name)
        if idx < 0: return None
        # 找到第一个 {
        brace_start = html.find('{', idx)
        if brace_start < 0: return None
        # 花括号计数
        depth = 0
        in_str = False
        escape = False
        for i in range(brace_start, min(len(html), brace_start + 100000)):
            c = html[i]
            if escape:
                escape = False
                continue
            if c == '\\':
                escape = True
                continue
            if c == '"' and not escape:
                in_str = not in_str
                continue
            if in_str:
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    raw = html[brace_start:i + 1]
                    try:
                        return json.loads(raw)
                    except:
                        return None
        return None

    @staticmethod
    def _extract_intro(html):
        """提取剧情简介（处理div嵌套）"""
        marker = 'module-info-introduction-content'
        idx = html.find(marker)
        if idx >= 0:
            # 找到第一个 <p> 或内容div的开始
            p_start = html.find('<p', idx)
            if p_start >= 0:
                # 找到p的结束
                p_end = html.find('</p>', p_start)
                if p_end >= 0:
                    return html[p_start:p_end]
        # 兜底: description meta
        m = re.search(r'name="description"\s+content="([^"]+)"', html, re.I)
        if m: return m.group(1)
        return ''

    # ======================== 卡片解析
    def _cards(self, html):
        """解析 mxtheme 卡片（支持 poster-item 和 card-item 两种模板）"""
        if not html: return []
        out, seen = [], set()
        # 模式1: module-poster-item (首页/分类页) - a标签有title属性
        for m in re.finditer(r'<a[^>]*\bhref="(/v/(\d+)\.html)"[^>]*\btitle="([^"]{1,120})"', html, re.I):
            vid = m.group(2)
            if vid in seen: continue
            seen.add(vid)
            name = self._txt(m.group(3))
            if not name: continue
            # 在a标签后500字符范围内找图片和备注
            block = html[m.start():min(len(html), m.end() + 600)]
            pic = self._first(block, [
                r'data-original="([^"]+)"',
                r'data-src="([^"]+)"',
                r'src="((?:https?:)?//[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
            ])
            if pic: pic = self._abs(pic)
            remarks = self._first(block, [
                r'class="[^"]*module-item-note[^"]*"[^>]*>([\s\S]{0,40}?)<',
            ])
            out.append({'vod_id': vid, 'vod_name': name, 'vod_pic': pic, 'vod_remarks': remarks[:12] if remarks else ''})
            if len(out) >= 30: break

        # 模式2: module-card-item (搜索页) - 标题在strong里，图片在另一个a标签
        if len(out) < 10:
            for m in re.finditer(r'class="module-card-item module-item"[^>]*>([\s\S]{0,1500}?)</div>\s*</div>\s*</div>', html, re.I):
                block = m.group(1)
                # 提取ID和名称
                id_m = re.search(r'href="/v/(\d+)\.html"', block, re.I)
                if not id_m: continue
                vid = id_m.group(1)
                if vid in seen: continue
                # 名称从 <strong> 或 title 中取
                name_m = re.search(r'<strong>([^<]+)</strong>', block, re.I)
                if not name_m:
                    name_m = re.search(r'alt="([^"]+)"', block, re.I)
                if not name_m: continue
                name = self._txt(name_m.group(1))
                if not name: continue
                seen.add(vid)
                pic = self._first(block, [
                    r'data-original="([^"]+)"',
                    r'data-src="([^"]+)"',
                    r'src="((?:https?:)?//[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
                ])
                if pic: pic = self._abs(pic)
                remarks = self._first(block, [
                    r'class="[^"]*module-item-note[^"]*"[^>]*>([\s\S]{0,40}?)<',
                ])
                out.append({'vod_id': vid, 'vod_name': name, 'vod_pic': pic, 'vod_remarks': remarks[:12] if remarks else ''})
                if len(out) >= 30: break
        return out

    # ======================== 首页
    def homeContent(self, filter):
        cats = [
            {'type_id': '1', 'type_name': '电影'},
            {'type_id': '2', 'type_name': '电视剧'},
            {'type_id': '3', 'type_name': '综艺'},
            {'type_id': '4', 'type_name': '动漫'},
        ]
        res = {'class': cats, 'filters': {}}
        if filter:
            for c in cats:
                res['filters'][c['type_id']] = [
                    {"key": "class", "name": "类型", "value": [{"n": "全部", "v": ""}]},
                    {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 2016, -1)]},
                    {"key": "by", "name": "排序", "value": [{"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "评分", "v": "score"}]},
                ]
        html = self.fetch(self.HOST + '/')
        res['list'] = self._cards(html)
        return res

    def homeVideoContent(self):
        html = self.fetch(self.HOST + '/')
        return {'list': self._cards(html)}

    # ======================== 分类
    def categoryContent(self, tid, pg, filter, extend):
        page = self._int(pg, 1)
        # /type/1.html 或 /type/1-2.html (分页) 或 /type/1/class/动作/year/2025.html
        url = f'{self.HOST}/type/{tid}'
        params = []
        if extend:
            for k in ('class', 'area', 'year', 'by'):
                v = extend.get(k, '')
                if v and v != '全部':
                    params.append(f'{k}/{v}')
        if params:
            url += '/' + '/'.join(params)
        url += f'-{page}.html' if page > 1 else '.html'
        html = self.fetch(url)
        cards = self._cards(html)
        # 分页: 检查是否有下一页
        has_next = bool(re.search(rf'/type/{tid}[^"]*-{page+1}\.html', html, re.I))
        return {'list': cards, 'page': page, 'pagecount': page + (1 if has_next else 0),
                'limit': 30, 'total': len(cards) * (page + (1 if has_next else 0))}

    # ======================== 详情
    def detailContent(self, ids):
        vid = re.sub(r'\D', '', str(ids[0] if isinstance(ids, list) else ids))
        if not vid: return {'list': []}
        h = self.fetch(f'{self.HOST}/v/{vid}.html')
        if not h: return {'list': []}
        v = {
            'vod_id': vid,
            'vod_name': self._first(h, [r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h1>',
                                        r'<title>([^<\-]+?)(?:\s*[-_–]|详情|在线)', r'<title>([^<]+)']),
            'vod_pic': self._abs(self._first(h, [r'data-original="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
                                                  r'class="[^"]*module-item-pic[^"]*"[^>]*>[\s\S]{0,200}?data-original="([^"]+)"'])),
            'vod_year': self._pick(h, '年份'),
            'vod_area': self._pick(h, '地区'),
            'vod_remarks': self._pick(h, '状态'),
            'vod_actor': self._pick(h, '主演'),
            'vod_director': self._pick(h, '导演'),
            'vod_content': self._extract_intro(h),
            'type_name': self._pick(h, '类型'),
            'vod_play_from': '', 'vod_play_url': '',
        }
        # 清理
        v['vod_name'] = re.sub(r'\s*[-_–]\s*.*$', '', v['vod_name']).strip()
        v['vod_content'] = re.sub(r'^(?:剧情简介|简介|介绍|剧情)\s*[:：]?\s*', '', self._txt(v['vod_content']))[:800]
        # 从tag提取年份/地区/类型（如果_pick没拿到）
        if not v['vod_year']:
            m = re.search(r'module-info-tag-link">\s*<a[^>]*title="(\d{4})"', h)
            if m: v['vod_year'] = m.group(1)
        if not v['vod_area']:
            m = re.search(r'module-info-tag">\s*<div class="module-info-tag-link">\s*<a[^>]*title="(\d{4})"[^>]*>[^<]*</a>\s*</div>\s*<div class="module-info-tag-link">\s*<a[^>]*title="([^"]+)"', h)
            if m: v['vod_area'] = m.group(2)
        if not v['type_name']:
            types = re.findall(r'module-info-tag-link">\s*<a[^>]*title="([^"]+)"[^>]*>[^<]*</a>', h)
            # 第一个是年份，第二个是地区，后面是类型
            v['type_name'] = ','.join(types[2:]) if len(types) > 2 else (types[0] if types else '')
        # 播放源
        pf, pu = self._play_list(h, vid)
        v['vod_play_from'] = pf
        v['vod_play_url'] = pu
        return {'list': [v]} if v['vod_name'] else {'list': []}

    @staticmethod
    def _pick(h, label):
        for lbl in (label, label.upper()):
            # 模式1: mxtheme - module-info-item-title
            marker = f'class="module-info-item-title">{lbl}'
            idx = h.find(marker)
            if idx < 0:
                marker = f'class="module-info-item-title">{lbl}：'
                idx = h.find(marker)
            if idx >= 0:
                # 找到内容div的开始
                content_start = h.find('module-info-item-content">', idx)
                if content_start >= 0:
                    content_start += len('module-info-item-content">')
                    # 计算嵌套div
                    depth = 1
                    i = content_start
                    while i < len(h) and depth > 0:
                        if h[i:i+5] == '<div ' or h[i:i+5] == '<div>':
                            depth += 1
                        elif h[i:i+6] == '</div>':
                            depth -= 1
                        i += 1
                    content = h[content_start:i-6]
                    seg = re.sub(r'<[^>]+>', '', content).replace('&nbsp;', ',').replace('/', ',').strip()
                    seg = re.sub(r',+', ',', seg).strip(',')
                    if seg: return seg
            # 模式2: 通用
            m = re.search(rf'>\s*{re.escape(lbl)}\s*[:：]\s*</[^>]+>\s*([^<]+)', h, re.S | re.I)
            if not m:
                m = re.search(rf'{re.escape(lbl)}\s*[:：]\s*<[^>]+>\s*([^<]+)', h, re.S | re.I)
            if not m:
                m = re.search(rf'<span[^>]*>\s*{re.escape(lbl)}\s*[:：]?</span>\s*<[^>]+>\s*([^<]+)', h, re.S | re.I)
            if m:
                seg = re.sub(r'<[^>]+>', '', m.group(1)).replace('&nbsp;', ',').strip()
                seg = re.sub(r',+', ',', seg).strip(',')
                if seg: return seg
        return ''

    def _play_list(self, h, vid):
        """解析播放源和剧集: /play/ID-SID-NID.html 分组"""
        # 提取源名称
        names = []
        for m in re.finditer(r'<a[^>]*class="[^"]*tab-item[^"]*"[^>]*>([\s\S]{0,100}?)</a>', h, re.I):
            nm = self._txt(m.group(1))
            if nm and nm not in ('选择播放源', '更多', '展开', '收起'):
                names.append(nm)
        if not names:
            # 备选: 找其他tab模式
            for m in re.finditer(r'class="[^"]*module-tab-item[^"]*"[^>]*>([\s\S]{0,80}?)</', h, re.I):
                nm = self._txt(m.group(1))
                if nm and nm not in ('选择播放源',):
                    names.append(nm)
        # 分组剧集
        groups, order = {}, []
        for m in re.finditer(r'href="(/play/(\d+)-(\d+)-(\d+)\.html)"[^>]*>([\s\S]{0,80}?)</a>', h, re.I):
            if m.group(2) != vid: continue
            sid, nid = int(m.group(3)), int(m.group(4))
            nm = re.sub(r'\s+', '', self._txt(m.group(5))) or ('第%02d集' % nid)
            # 清理非剧集名称（如"立即播放"、"立刻播放"等按钮文字）
            if nm in ('立即播放', '立刻播放', '播放', '立即观看', '在线播放') or '播放' in nm and len(nm) <= 5:
                nm = '第%02d集' % nid
            if sid not in groups:
                groups[sid] = {}
                order.append(sid)
            if nid not in groups[sid]:
                groups[sid][nid] = (nm[:40], m.group(1))
        if not groups: return '', ''
        froms, urls = [], []
        for idx, sid in enumerate(sorted(order)):
            nm = names[idx] if idx < len(names) else '线路%d' % (idx + 1)
            eps = [groups[sid][k] for k in sorted(groups[sid].keys())]
            froms.append(nm)
            urls.append('#'.join('%s$%s' % (t.strip(), self._abs(u)) for t, u in eps))
        return '$$$'.join(froms), '$$$'.join(urls)

    # ======================== 搜索
    def searchContent(self, key, quick, pg='1'):
        page = self._int(pg, 1)
        kw = str(key or '').strip()
        if not kw: return {'list': [], 'page': page}
        # /search/keyword-------------.html (5组连字符分隔参数)
        # 第2页: /search/keyword-------------2.html
        encoded = urllib.parse.quote(kw, safe='')
        if page > 1:
            url = f'{self.HOST}/search/{encoded}-------------{page}.html'
        else:
            url = f'{self.HOST}/search/{encoded}-------------.html'
        h = self.fetch(url)
        cards = self._cards(h)
        return {'list': cards, 'page': page}

    # ======================== 播放
    def playerContent(self, flag, id, vipFlags):
        if self.isVideoFormat(id):
            return {'parse': 0, 'url': id, 'header': {'User-Agent': self.UA, 'Referer': self.HOST + '/'}}
        play = id if str(id).startswith('http') else self.HOST + '/play/' + str(id).replace(f'{self.HOST}/play/', '')
        if not play.endswith('.html'):
            play = self.HOST + '/play/' + re.sub(r'^.*/play/', '', str(id))
        h = self.fetch(play)
        if not h: return {'parse': 1, 'url': play, 'header': self._hd(play)}
        # 用花括号计数提取 player_aaaa
        d = self._extract_json(h, 'player_aaaa')
        if d:
            raw = d.get('url', '').replace('\\/', '/').replace('\\u002F', '/')
            # 1. 直链判断
            if self.isVideoFormat(raw):
                return {'parse': 0, 'url': raw, 'header': {'User-Agent': self.UA, 'Referer': self.HOST + '/'}}
            # 2. base64编码的URL（encrypt=0 但实际是编码的）
            if raw and len(raw) > 30:
                try:
                    decoded = base64.b64decode(raw).decode('utf-8', errors='ignore')
                    if self.isVideoFormat(decoded):
                        return {'parse': 0, 'url': decoded, 'header': {'User-Agent': self.UA, 'Referer': self.HOST + '/'}}
                except: pass
                try:
                    safe = raw.replace('-', '+').replace('_', '/')
                    decoded = base64.b64decode(safe + '==').decode('utf-8', errors='ignore')
                    if self.isVideoFormat(decoded):
                        return {'parse': 0, 'url': decoded, 'header': {'User-Agent': self.UA, 'Referer': self.HOST + '/'}}
                except: pass
            # 3. 解析服务器（from字段为解析源名称，如lzm3u8）
            pf = d.get('from', '')
            if raw and pf:
                # 交给TVBox解析（parse=1），URL直接用播放页URL让TVBox自己取
                return {'parse': 1, 'url': play, 'header': self._hd(play)}
            # 4. 有解析服务器URL
            parse_url = d.get('parse', '') or d.get('parse2', '')
            if raw and parse_url:
                base = '' if parse_url.startswith('http') else self.HOST
                return {'parse': 1, 'url': self._abs(f'{base}{parse_url}?url={raw}'), 'header': self._hd(play)}
            if raw:
                return {'parse': 1, 'url': self._abs(raw), 'header': self._hd(play)}
        # 兜底: 页面直链
        for p in (r'[?&](?:url|v|m3u8|playurl|src|video)=([^"\'&\s<>]+?\.(?:m3u8|mp4)[^"\'&\s<>]*)',
                  r'(https?:[^"\'\\\s<>]+?\.m3u8[^"\'\\\s<>]*)'):
            url_m = re.search(p, h, re.I)
            if url_m:
                cand = urllib.parse.unquote(url_m.group(1).replace('\\/', '/'))
                if self.isVideoFormat(cand):
                    return {'parse': 0, 'url': cand, 'header': {'User-Agent': self.UA, 'Referer': self.HOST + '/'}}
        return {'parse': 1, 'url': play, 'header': self._hd(play)}

    # ======================== 配置
    config = {
        "player": {},
        "filter": {
            "1": [
                {"key": "class", "name": "类型", "value": [{"n": "全部", "v": ""}]},
                {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 2016, -1)]},
                {"key": "by", "name": "排序", "value": [{"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "评分", "v": "score"}]},
            ],
            "2": [
                {"key": "class", "name": "类型", "value": [{"n": "全部", "v": ""}]},
                {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 2016, -1)]},
                {"key": "by", "name": "排序", "value": [{"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "评分", "v": "score"}]},
            ],
            "3": [
                {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 2021, -1)]},
            ],
            "4": [
                {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 2021, -1)]},
            ],
        }
    }
    header = {}

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]
