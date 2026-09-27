# -*- coding: utf-8 -*-
"""
路飞影视 (lufys.com) — TVBox/CatVod Spider
融合 knvod.py 精简风格 + laisd.py 健壮性

设计: API优先 → HTML兜底 → 多级HTTP降级 → UA轮换 → Cloudflare搜索兜底
"""
import sys, re, json, gzip, zlib, time, hashlib, urllib.parse

sys.path.append('..')
from base.spider import Spider

try:
    import requests
    from requests.adapters import HTTPAdapter
    requests.packages.urllib3.disable_warnings()
except ImportError:
    requests = None

try:
    import ssl, urllib.request
except ImportError:
    ssl = urllib = None


class Spider(Spider):
    HOST = 'https://www.lufys.com'
    UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    UAS = [
        'Mozilla/5.0 (Linux; Android 12; SM-G977N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'okhttp/3.12.13',
    ]
    TIMEOUT = 10
    _uai = 0
    _api_dead = False
    s = None

    def init(self, extend=''):
        self._api_dead = False
        self._uai = 0
        if requests:
            self.s = requests.Session()
            self.s.mount('https://', HTTPAdapter(max_retries=1))
            self.s.verify = False
            # 预热: 获取Cloudflare cookie
            try: self.s.get(self.HOST + '/', headers=self._hd(), timeout=self.TIMEOUT)
            except: pass
        return self

    def getName(self): return '路飞影视'
    def isVideoFormat(self, url): return bool(re.search(r'\.(m3u8|mp4|flv|mkv)(\?|$)', str(url), re.I))
    def manualVideoCheck(self): return False
    def destroy(self): return

    # ======================== HTTP
    def _hd(self, ref=None, ajax=False):
        h = {'User-Agent': self.UA, 'Referer': ref or self.HOST + '/', 'Accept': '*/*', 'Accept-Language': 'zh-CN,zh;q=0.9'}
        if ajax: h['X-Requested-With'] = 'XMLHttpRequest'
        return h

    def _rotate_ua(self):
        self._uai = (self._uai + 1) % len(self.UAS)
        self.UA = self.UAS[self._uai]

    def fetch(self, url, ref=None, tries=2):
        """GET: requests优先(带UA轮换) → 宿主fetch → urllib"""
        if self.s:
            for i in range(tries):
                try:
                    r = self.s.get(url, headers=self._hd(ref), timeout=self.TIMEOUT)
                    if r.status_code == 200 and len(r.content) > 200:
                        return self._decode(r.content)
                    if r.status_code in (403, 429) and i + 1 < tries:
                        self._rotate_ua(); continue
                    if 400 <= r.status_code < 500: return ''
                except: pass
                if i + 1 < tries: time.sleep(0.3 * (i + 1))
        # 宿主fetch
        try:
            rsp = Spider.fetch(self, url, headers=self._hd(ref))
            if rsp is not None:
                t = getattr(rsp, 'text', None)
                if t: return t
                return self._decode(getattr(rsp, 'content', b''))
        except: pass
        # urllib兜底
        if urllib:
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(url, headers=self._hd(ref))
                with urllib.request.urlopen(req, context=ctx, timeout=self.TIMEOUT) as r:
                    return self._decode(r.read())
            except: pass
        return ''

    def _post(self, url, data, ref=None):
        h = self._hd(ref, True)
        h['Content-Type'] = 'application/x-www-form-urlencoded'
        if self.s:
            for i in range(2):
                try:
                    r = self.s.post(url, data=data, headers=h, timeout=self.TIMEOUT)
                    if 400 <= r.status_code < 500: return ''
                    t = getattr(r, 'text', '')
                    if r.status_code == 200 and t.strip().startswith('{'): return t
                except: pass
                if i + 1 < 2: time.sleep(0.3)
        return ''

    @staticmethod
    def _decode(raw):
        if not raw or isinstance(raw, str): return raw or ''
        if raw[:2] == b'\x1f\x8b':
            try: raw = gzip.decompress(raw)
            except: pass
        elif raw[:2] in (b'\x78\x9c', b'\x78\x01'):
            try: raw = zlib.decompress(raw)
            except: pass
        m = re.search(rb'charset=["\']?\s*([\w\-]+)', raw[:3000], re.I)
        enc = 'utf-8'
        if m:
            enc = m.group(1).decode('ascii', 'ignore')
            if enc.lower().startswith('gb'): enc = 'gb18030'
        for e in (enc, 'utf-8', 'gb18030'):
            try:
                t = raw.decode(e)
                if t.count('\ufffd') < 5: return t
            except: continue
        return raw.decode('utf-8', 'ignore')

    # ======================== 工具
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
        """多正则逐个尝试，返回首个命中"""
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
    def _pick(h, label):
        for lbl in (label, label.upper()):
            m = re.search(r'>%s[：:]\s*</em>(.*?)</li>' % re.escape(lbl), h, re.S | re.I)
            if not m:
                m = re.search(r'>%s\s*[：:]\s*</strong>(.*?)</div>' % re.escape(lbl), h, re.S | re.I)
            if m:
                seg = re.sub(r'<span class="slash">/</span>', ',', m.group(1))
                seg = re.sub(r'<[^>]+>', '', seg).replace('&nbsp;', ',')
                seg = re.sub(r',+', ',', seg).strip().strip(',')
                if seg: return seg
        return ''

    # ======================== API (苹果CMS签名)
    def _apikey(self, t):
        return hashlib.md5(('DS%d%s' % (t, '')).encode()).hexdigest()

    def _vodapi(self, tid, page, ext=None):
        """POST /index.php/api/vod 取列表JSON; 失败返回{}"""
        if self._api_dead: return {}
        t = int(time.time())
        d = {'type': str(tid), 'class': '', 'area': '', 'lang': '', 'version': '', 'state': '', 'letter': '', 'page': str(page), 'time': str(t), 'key': self._apikey(t)}
        if ext:
            for k in ('class', 'area', 'lang', 'year', 'version', 'state', 'letter', 'by'):
                if ext.get(k): d[k] = str(ext[k])
        txt = self._post(self.HOST + '/index.php/api/vod', d)
        if not txt or not txt.strip().startswith('{'):
            self._api_dead = True  # API已关闭，后续不再尝试
            return {}
        try:
            j = json.loads(txt)
            return j if isinstance(j, dict) and j.get('list') else {}
        except: return {}

    @staticmethod
    def _vodlist(arr):
        return [{'vod_id': str(v.get('vod_id', '')), 'vod_name': v.get('vod_name', ''),
                 'vod_pic': v.get('vod_pic', '').replace('\\/', '/'), 'vod_remarks': v.get('vod_remarks', '')}
                for v in arr if v.get('vod_id')]

    # ======================== 首页
    def homeContent(self, filter):
        cls = self.cats
        res = {'class': cls}
        if filter: res['filters'] = self.config['filter']
        # API优先
        j = self._vodapi('dianshiju', 1)
        res['list'] = self._vodlist(j.get('list', []))
        # API失败 → HTML兜底
        if not res['list']:
            h = self.fetch(self.HOST + '/')
            res['list'] = self._cards(h)
        return res

    def homeVideoContent(self):
        j = self._vodapi('dianying', 1)
        lst = self._vodlist(j.get('list', []))
        if not lst:
            lst = self._cards(self.fetch(self.HOST + '/'))
        return {'list': lst}

    # ======================== 分类
    def categoryContent(self, tid, pg, filter, extend):
        page = self._int(pg, 1)
        result = {'list': [], 'page': page, 'pagecount': 1, 'limit': 30, 'total': 0}
        # API优先
        j = self._vodapi(tid, page, extend)
        if j.get('list'):
            return {'list': self._vodlist(j['list']), 'page': page,
                    'pagecount': self._int(j.get('pagecount'), 1),
                    'limit': self._int(j.get('limit'), 30),
                    'total': self._int(j.get('total'), 0)}
        # HTML兜底: /type/dianying 或 /type/dianshiju/guochangju
        sub = extend.get('class', '') if extend else ''
        url = '%s/type/%s' % (self.HOST, tid)
        if sub: url = '%s/type/%s/%s' % (self.HOST, tid, sub)
        if extend:
            params = ['%s/%s' % (k, urllib.parse.quote(str(extend[k])))
                      for k in ('area', 'year', 'by') if extend.get(k) and extend[k] != '全部']
            if params: url += '/' + '/'.join(params)
        h = self.fetch(url)
        cards = self._cards(h)
        result['list'] = cards
        result['total'] = len(cards)
        result['pagecount'] = page + (1 if len(cards) >= 20 else 0)
        return result

    # ======================== 卡片解析
    def _cards(self, html):
        if not html: return []
        out, seen = [], set()
        for m in re.finditer(r'<a[^>]*\bhref="(/watch/(\d+))"[^>]*\btitle="([^"]{1,120})"', html, re.I):
            vid = m.group(2)
            if vid in seen: continue
            seen.add(vid)
            name = self._txt(m.group(3))
            if not name or re.match(r'^\d+$', name): continue
            # 扩大搜索范围: lazy图片的data-src可能距a标签较远
            start = max(0, m.start() - 50)
            end = min(len(html), m.end() + 600)
            block = html[start:end]
            pic = self._first(block, [
                r'data-src="([^"]+\.(?:jpg|jpeg|png|webp|gif)[^"]*)"',
                r'data-original="([^"]+)"',
                r'src="((?:https?:)?//[^"]+\.(?:jpg|jpeg|png|webp|gif)[^"]*)"',
            ])
            if pic and pic.startswith('data:'):  # 排除base64占位图
                pic = self._first(block, [r'data-src="([^"]+)"', r'data-original="([^"]+)"'])
            if pic: pic = self._abs(pic)
            remarks = self._first(block, [
                r'class="[^"]*(?:public-list-prb|pic-text|remarks|note|status|score|label)[^"]*"[^>]*>([\s\S]{0,40}?)<',
                r'<span[^>]*class="[^"]*(?:tag|badge)[^"]*"[^>]*>([\s\S]{0,30}?)</span>',
            ])
            out.append({'vod_id': vid, 'vod_name': name, 'vod_pic': pic, 'vod_remarks': remarks[:12] if remarks else ''})
            if len(out) >= 30: break
        return out

    # ======================== 详情
    def detailContent(self, ids):
        vid = re.sub(r'\D', '', str(ids[0] if isinstance(ids, list) else ids))
        if not vid: return {'list': []}
        h = self.fetch('%s/watch/%s' % (self.HOST, vid))
        if not h: return {'list': []}
        v = {
            'vod_id': vid,
            'vod_name': self._first(h, [r"<h1[^>]*class='slide-title'[^>]*>([^<]+)</h1>", r'<h1[^>]*>([^<]+)</h1>', r'<title>([^<\-]+?)(?:\s*[-_–]|</title>)']),
            'vod_pic': self._abs(self._first(h, [
                r'class="[^"]*detail-pic[^"]*"[^>]*>[\s\S]{0,300}?data-src="([^"]+)"',
                r'data-src="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
            ])),
            'vod_year': self._pick(h, '年份'), 'vod_area': self._pick(h, '地区'),
            'vod_remarks': self._pick(h, '状态') or self._pick(h, '备注'),
            'vod_actor': self._pick(h, '主演') or self._pick(h, '演员'),
            'vod_director': self._pick(h, '导演'),
            'vod_content': self._first(h, [r'id="height_limit"[^>]*>([\s\S]{0,3000}?)</div>']) or
                           self._first(h, [r'name="description"\s+content="([^"]+)"']) or '',
            'type_name': self._pick(h, '类型'),
            'vod_play_from': '', 'vod_play_url': '',
        }
        # 清理标题后缀
        for s in (' - 免费在线观看', ' - 路飞影视', '_高清完整版 - 路飞影视'):
            if v['vod_name'].endswith(s): v['vod_name'] = v['vod_name'][:-len(s)].strip()
        v['vod_name'] = re.sub(r'\s*[-_–]\s*免费.*$', '', v['vod_name']).strip()
        v['vod_content'] = re.sub(r'^(?:剧情简介|简介|介绍|剧情)\s*[:：]?\s*', '', self._txt(v['vod_content']))[:800]

        pf, pu = self._play_list(h, vid)
        v['vod_play_from'] = pf
        v['vod_play_url'] = pu
        return {'list': [v]} if v['vod_name'] else {'list': []}

    def _play_list(self, h, vid):
        """解析播放源和剧集: watch-play/ID-SID-NID 分组"""
        # 提取所有 <a class="swiper-slide"> 的文本作为源名
        # 导航栏的 swiper-slide 在 <li> 上不在 <a> 上，所以不会误匹配
        names = []
        for sm in re.finditer(r'<a[^>]*class="swiper-slide"[^>]*>([\s\S]{0,300}?)</a>', h, re.I):
            raw = sm.group(1)
            # 去掉 <i>/<em> 图标和 <span> 徽章，只留文本
            name = re.sub(r'<[^>]+>', '', raw).replace('&nbsp;', '').strip()
            name = re.sub(r'\s+', ' ', name).strip()
            # 去掉末尾的集数数字 (badge里的28等)
            name = re.sub(r'\s*\d+\s*$', '', name).strip()
            if name:
                names.append(name)
        groups, order = {}, []
        for m in re.finditer(r'href="(/watch-play/(\d+)-(\d+)-(\d+)[^"]*)"[^>]*>([\s\S]{0,80}?)</a>', h, re.I):
            if m.group(2) != vid: continue
            sid, nid = int(m.group(3)), int(m.group(4))
            nm = re.sub(r'\s+', '', self._txt(m.group(5))) or ('第%d集' % nid)
            if sid not in groups: groups[sid] = {}; order.append(sid)
            if nid not in groups[sid]: groups[sid][nid] = (nm[:40], m.group(1))
        if not groups: return '', ''
        froms, urls = [], []
        for idx, sid in enumerate(sorted(order)):
            nm = names[idx] if idx < len(names) and names[idx] else '线路%d' % (idx + 1)
            eps = [groups[sid][k] for k in sorted(groups[sid].keys())]
            froms.append(nm)
            urls.append('#'.join('%s$%s' % (t.strip(), self._abs(u)) for t, u in eps))
        return '$$$'.join(froms), '$$$'.join(urls)

    # ======================== 搜索
    def searchContent(self, key, quick, pg='1'):
        page = self._int(pg, 1)
        kw = str(key or '').strip()
        if not kw: return {'list': [], 'page': page}
        # 方案1: 正常搜索
        url = '%s/search?wd=%s' % (self.HOST, urllib.parse.quote(kw, safe=''))
        h = self.fetch(url)
        if h and 'Just a moment' not in h:
            cards = self._cards(h)
            if cards:
                filtered = [c for c in cards if kw in c.get('vod_name', '')]
                return {'list': filtered or cards, 'page': page}
        # 方案2: Cloudflare 403 → 首页+分类页嗅探兜底
        out = []
        for c in self._cards(self.fetch(self.HOST + '/')):
            if kw in c.get('vod_name', ''): out.append(c)
        for tid in ('dianying', 'dianshiju', 'zongyi', 'dongman', 'duanju'):
            if len(out) >= 10: break
            for c in self._cards(self.fetch('%s/type/%s' % (self.HOST, tid))):
                if kw in c.get('vod_name', '') and c['vod_id'] not in [s['vod_id'] for s in out]:
                    out.append(c)
        return {'list': out, 'page': page}

    # ======================== 播放
    def playerContent(self, flag, id, vipFlags):
        if self.isVideoFormat(id):
            return {'parse': 0, 'url': id, 'header': {'User-Agent': self.UA, 'Referer': self.HOST + '/'}}
        play = id if str(id).startswith('http') else self.HOST + '/watch-play/' + str(id)
        h = self.fetch(play)
        if not h: return {'parse': 1, 'url': play, 'header': self._hd(play)}
        # player_aaaa 贪婪匹配完整JSON
        m = (re.search(r'player_aaaa\s*=\s*(\{.*\})\s*;?\s*</script>', h, re.S) or
             re.search(r'player_aaaa\s*=\s*(\{.*\})\s*;', h, re.S))
        if m:
            try:
                d = json.loads(m.group(1))
                raw = d.get('url', '').replace('\\/', '/').replace('\\u002F', '/')
                if self.isVideoFormat(raw):
                    return {'parse': 0, 'url': raw, 'header': {'User-Agent': self.UA, 'Referer': self.HOST + '/'}}
                parse_url = d.get('parse', '') or d.get('parse2', '')
                if raw and parse_url:
                    base = '' if parse_url.startswith('http') else self.HOST
                    return {'parse': 1, 'url': self._abs('%s%s?url=%s' % (base, parse_url, raw)), 'header': self._hd(play)}
                if raw: return {'parse': 1, 'url': self._abs(raw), 'header': self._hd(play)}
            except: pass
            url_m = re.search(r'"url"\s*:\s*"((?:[^"\\]|\\.)*)"', m.group(1))
            if url_m:
                cand = url_m.group(1).replace('\\/', '/').replace('\\u002F', '/')
                if self.isVideoFormat(cand):
                    return {'parse': 0, 'url': cand, 'header': {'User-Agent': self.UA, 'Referer': self.HOST + '/'}}
        # 兜底: 页面直链
        for p in (r'[?&](?:url|v|m3u8|playurl|src|video)=([^"\'&\s<>]+?\.(?:m3u8|mp4)[^"\'&\s<>]*)',
                  r'(https?:[^"\'\\\s<>]+?\.m3u8[^"\'\\\s<>]*)',
                  r'(https?:[^"\'\\\s<>]+?\.mp4[^"\'\\\s<>]*)'):
            url_m = re.search(p, h, re.I)
            if url_m:
                cand = urllib.parse.unquote(url_m.group(1).replace('\\/', '/').replace('\\u002F', '/'))
                if self.isVideoFormat(cand):
                    return {'parse': 0, 'url': cand, 'header': {'User-Agent': self.UA, 'Referer': self.HOST + '/'}}
        return {'parse': 1, 'url': play, 'header': self._hd(play)}

    # ======================== 配置
    cats = [
        {'type_id': 'dianying', 'type_name': '电影'},
        {'type_id': 'dianshiju', 'type_name': '电视剧'},
        {'type_id': 'zongyi', 'type_name': '综艺'},
        {'type_id': 'dongman', 'type_name': '动漫'},
        {'type_id': 'duanju', 'type_name': '短剧'},
    ]
    config = {
        "player": {},
        "filter": {
            "dianying": [
                {"key": "class", "name": "类型", "value": [
                    {"n": "全部", "v": ""}, {"n": "动作片", "v": "dongzuopian"},
                    {"n": "喜剧片", "v": "xijupian"}, {"n": "爱情片", "v": "aiqingpian"},
                    {"n": "科幻片", "v": "kehuanpian"}, {"n": "恐怖片", "v": "kongbupian"},
                    {"n": "剧情片", "v": "juqingpian"},
                ]},
                {"key": "area", "name": "地区", "value": [
                    {"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "港台", "v": "港台"},
                    {"n": "美国", "v": "美国"}, {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"}, {"n": "其他", "v": "其他"},
                ]},
                {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 2016, -1)]},
                {"key": "by", "name": "排序", "value": [{"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "评分", "v": "score"}]},
            ],
            "dianshiju": [
                {"key": "class", "name": "类型", "value": [
                    {"n": "全部", "v": ""}, {"n": "国产剧", "v": "guochangju"},
                    {"n": "欧美剧", "v": "oumeiju"}, {"n": "日本剧", "v": "ribenju"},
                    {"n": "韩国剧", "v": "hanguoju"}, {"n": "海外剧", "v": "haiwaiju"},
                ]},
                {"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "港台", "v": "港台"}, {"n": "美国", "v": "美国"}, {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"}, {"n": "其他", "v": "其他"}]},
                {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 2016, -1)]},
                {"key": "by", "name": "排序", "value": [{"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "评分", "v": "score"}]},
            ],
            "zongyi": [
                {"key": "class", "name": "类型", "value": [{"n": "全部", "v": ""}, {"n": "大陆综艺", "v": "daluzongyi"}, {"n": "欧美综艺", "v": "oumeizongyi"}, {"n": "日韩综艺", "v": "rihanzongyi"}]},
                {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 2021, -1)]},
            ],
            "dongman": [
                {"key": "class", "name": "类型", "value": [{"n": "全部", "v": ""}, {"n": "国产动漫", "v": "guochandongman"}, {"n": "日韩动漫", "v": "rihandongman"}, {"n": "欧美动漫", "v": "oumeidongman"}, {"n": "海外动漫", "v": "haiwaidongman"}]},
                {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 2021, -1)]},
            ],
            "duanju": [
                {"key": "class", "name": "类型", "value": [{"n": "全部", "v": ""}, {"n": "神豪短剧", "v": "shenhaoduanju"}, {"n": "重生短剧", "v": "chongshengduanju"}, {"n": "复仇短剧", "v": "fuchouduanju"}, {"n": "穿越短剧", "v": "chuanyueduanju"}]},
            ],
        }
    }
    header = {}

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]
