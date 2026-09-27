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
import sys, re, json, time, hashlib, base64, urllib.parse, os

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
    # 预生成的验证cookie (有效期约24小时, 过期后需ddddocr刷新)
    # 生成时间: 2026-09-07, 格式: sign-sessid
    _HARDCODED_SIGN = '4082b45592d3b242be80f2ff63ed1f99-3beb12d102ac62159e68129b1d6296f726cc98ba1b4c2592630f24b2f123b783-1788811945'
    _HARDCODED_SESSID = 'ecj4ht7n7u279om2k8ac09sv3k'
    _cached_sign = ''
    _cached_sessid = ''
    # cookie持久化: 验证通过后保存, 下次直接复用, 避免每次OCR
    COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pipilv_cookie.json')

    def _load_cookies(self):
        """从本地加载已验证的cookie"""
        try:
            with open(self.COOKIE_FILE, 'r') as f:
                data = json.load(f)
                if data.get('sign') and time.time() - data.get('ts', 0) < 86400:
                    return data
        except:
            pass
        return None

    def _save_cookies(self):
        """保存验证后的cookie到本地"""
        try:
            sign = self._cached_sign or self._HARDCODED_SIGN
            sessid = self._cached_sessid or self._HARDCODED_SESSID
            if self.s:
                for c in self.s.cookies:
                    if c.name == 'captcha_login_sign': sign = c.value
                    elif c.name == 'PHPSESSID': sessid = c.value
            if sign:
                with open(self.COOKIE_FILE, 'w') as f:
                    json.dump({'sign': sign, 'sessid': sessid, 'ts': time.time()}, f)
        except:
            pass

    def _cookie_str(self):
        """返回Cookie头值: 优先用缓存/验证后的, 其次用硬编码"""
        sign = self._cached_sign or self._HARDCODED_SIGN
        sessid = self._cached_sessid or self._HARDCODED_SESSID
        if self.s:
            for c in self.s.cookies:
                if c.name == 'captcha_login_sign': sign = c.value
                elif c.name == 'PHPSESSID': sessid = c.value
        return 'captcha_login_sign=%s; PHPSESSID=%s' % (sign, sessid)

    def init(self, extend=''):
        self._verified = False
        self._verify_time = 0
        # 加载缓存cookie (优先于硬编码)
        cached = self._load_cookies()
        if cached:
            self._cached_sign = cached['sign']
            self._cached_sessid = cached.get('sessid', '')
        if requests:
            self.s = requests.Session()
            self.s.mount('https://', HTTPAdapter(max_retries=1))
            self.s.verify = False
            # 设置cookie到session
            self.s.cookies.set('captcha_login_sign', self._cached_sign or self._HARDCODED_SIGN, domain='www.pipilv.top', path='/')
            self.s.cookies.set('PHPSESSID', self._cached_sessid or self._HARDCODED_SESSID, domain='www.pipilv.top', path='/')
            # 测试cookie是否有效
            try:
                r = self.s.get(self.HOST + '/', headers=self._hd(), timeout=self.TIMEOUT)
                if r.status_code == 200 and '系统安全验证' not in r.text and len(r.content) > 5000:
                    self._verified = True
                    self._verify_time = time.time()
            except:
                pass
        # cookie有效就不需要OCR; 无效且有ddddocr才验证
        if not self._verified and ddddocr:
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
                        self._save_cookies()  # 持久化cookie, 下次免OCR
                        return True
            except:
                continue
        return False

    # ======================== HTTP
    def _hd(self, ref=None):
        h = {'User-Agent': self.UA, 'Accept': '*/*', 'Accept-Language': 'zh-CN,zh;q=0.9',
             'Referer': ref or self.HOST + '/'}
        # 始终带上Cookie头 (Spider.fetch不管理cookie, 需手动传)
        h['Cookie'] = self._cookie_str()
        return h

    def fetch(self, url, ref=None):
        """GET请求，自动处理验证码 (支持requests和TVBox内置两种HTTP客户端)"""
        h = self._hd(ref)
        # 方式1: requests session (如果可用)
        if self.s:
            for attempt in range(2):
                try:
                    r = self.s.get(url, headers=h, timeout=self.TIMEOUT)
                    if '系统安全验证' in r.text:
                        self._verified = False
                        if ddddocr and self._ensure_verified():
                            h['Cookie'] = self._cookie_str()
                            continue
                        # cookie过期且无ddddocr: 尝试Spider.fetch兜底
                        break
                    if r.status_code == 200 and len(r.content) > 200:
                        return r.text
                    if r.status_code == 404:
                        return ''
                except:
                    pass
        # 方式2: TVBox内置Spider.fetch (不依赖requests, 用Cookie头)
        try:
            rsp = super().fetch(url, headers=h)
            if rsp is not None:
                txt = getattr(rsp, 'text', '') or ''
                if '系统安全验证' not in txt and len(txt) > 200:
                    return txt
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
    def _cards_panel(self, html, by='day'):
        """分类页: 按日/周/月榜提取对应panel的卡片"""
        # 日/周/月榜对应panel1/panel2/panel3, 但ID都叫panel1
        # 实际是按出现顺序: 第1个=日榜(active), 第2个=周榜, 第3个=月榜
        panel_idx = {'day': 0, 'week': 1, 'month': 2}.get(by, 0)
        # 按module-main tab-list分割
        panels = re.split(r'class="module-main tab-list', html)
        if len(panels) > panel_idx + 1:
            return self._cards(panels[panel_idx + 1])
        return self._cards(html)

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

        # 模式2: module-card-item (搜索页) - 标题在strong里，图片在poster的a标签
        if len(out) < 10:
            # 按卡片起始标记分割，取每张卡片的内容块
            parts = re.split(r'class="module-card-item module-item"', html)
            for block in parts[1:]:
                # 截取到下一个卡片或限制长度
                block = block[:1500]
                # 提取ID
                id_m = re.search(r'href="/v/(\d+)\.html"', block, re.I)
                if not id_m: continue
                vid = id_m.group(1)
                if vid in seen: continue
                # 名称从 <strong> 或 alt 中取
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
                    {"key": "by", "name": "排序", "value": [
                        {"n": "日榜", "v": "day"},
                        {"n": "周榜", "v": "week"},
                        {"n": "月榜", "v": "month"},
                    ]},
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
        url = f'{self.HOST}/type/{tid}' + (f'-{page}.html' if page > 1 else '.html')
        html = self.fetch(url)
        # 站点日/周/月榜都在同一HTML的panel1/2/3中
        # 通过extend的by参数选择不同panel
        by = (extend.get('by', '') if extend else '') or 'day'
        cards = self._cards_panel(html, by)
        # 站点分页实际无效(所有页返回相同内容), 只返回第1页
        pagecount = 1 if page == 1 else 1
        return {'list': cards, 'page': page, 'pagecount': 1,
                'limit': 30, 'total': len(cards)}

    # ======================== 详情
    def detailContent(self, ids):
        vid = re.sub(r'\D', '', str(ids[0] if isinstance(ids, list) else ids))
        if not vid: return {'list': []}
        h = self.fetch(f'{self.HOST}/v/{vid}.html')
        if not h: return {'list': []}
        v = {
            'vod_id': vid,
            'vod_name': self._first(h, [r'<h1[^>]*>([^<]+)</h1>',
                                        r'<h2[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h2>',
                                        r'<title>([^<\-]+?)(?:\s*[-_–]|详情|在线)', r'<title>([^<]+)']),
            'vod_pic': self._abs(self._first(h, [r'data-original="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
                                                  r'class="[^"]*module-item-pic[^"]*"[^>]*>[\s\S]{0,200}?data-original="([^"]+)"'])),
            'vod_year': self._pick(h, '年份') or self._pick(h, '上映'),
            'vod_area': self._pick(h, '地区'),
            'vod_remarks': self._pick(h, '状态') or self._pick(h, '更新') or self._pick(h, '备注'),
            'vod_actor': self._pick(h, '主演'),
            'vod_director': self._pick(h, '导演') or self._pick(h, '编剧'),
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
            # tag-link 中第二个链接(title非纯数字)通常是地区
            tags = re.findall(r'module-info-tag-link"><a[^>]*title="([^"]+)"', h)
            for t in tags:
                if t and not re.match(r'^\d{4}$', t):
                    v['vod_area'] = t
                    break
        if not v['type_name']:
            # tag-link 有title的取title, 没有的取链接文本
            tags = []
            for m in re.finditer(r'module-info-tag-link">\s*<a[^>]*?(?:title="([^"]*)")?[^>]*>([^<]*)</a>', h):
                t = m.group(1) or m.group(2)
                if t: tags.append(t.strip())
            # 第一个是年份，第二个是地区，后面是类型
            v['type_name'] = ','.join(tags[2:]) if len(tags) > 2 else (tags[-1] if tags else '')
        # 播放源
        pf, pu = self._play_list(h, vid)
        v['vod_play_from'] = pf
        v['vod_play_url'] = pu
        return {'list': [v]} if v['vod_name'] else {'list': []}

    @staticmethod
    def _pick(h, label):
        for lbl in (label, label.upper()):
            # 模式1: <span class="module-info-item-title">导演：</span> 后跟 module-info-item-content
            marker = 'module-info-item-title'
            search_pos = 0
            while True:
                idx = h.find(marker, search_pos)
                if idx < 0:
                    break
                # 查找此marker后的label文本
                tag_end = h.find('>', idx)
                if tag_end < 0:
                    break
                close_end = h.find('</', tag_end)
                if close_end < 0:
                    break
                label_text = re.sub(r'<[^>]+>', '', h[tag_end+1:close_end]).strip()
                # 去掉冒号
                clean_label = re.sub(r'[:：]', '', label_text)
                if clean_label == lbl or label_text.rstrip('：:') == lbl.rstrip('：:'):
                    # 找到内容div
                    content_start = h.find('module-info-item-content">', close_end)
                    if content_start >= 0:
                        content_start += len('module-info-item-content">')
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
                search_pos = idx + len(marker)
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
        # 提取源名称 - div.module-tab-item[tab-item] 中 span 文本 或 data-dropdown-value
        names = []
        for m in re.finditer(r'class="[^"]*module-tab-item[^"]*tab-item[^"]*"[^>]*data-dropdown-value="([^"]+)"', h, re.I):
            names.append(m.group(1).strip())
        if not names:
            for m in re.finditer(r'class="[^"]*tab-item[^"]*"[^>]*>([\s\S]{0,100}?)</', h, re.I):
                nm = self._txt(m.group(1))
                if nm and nm not in ('选择播放源', '更多', '展开', '收起', '选集播放'):
                    names.append(nm)
        if not names:
            # 备选: <a class="tab-item">
            for m in re.finditer(r'<a[^>]*class="[^"]*tab-item[^"]*"[^>]*>([\s\S]{0,100}?)</a>', h, re.I):
                nm = self._txt(m.group(1))
                if nm and nm not in ('选择播放源', '更多', '展开', '收起'):
                    names.append(nm)
        # 分组剧集 - module-play-list-link 中 span 文本为剧集名
        groups, order = {}, []
        for m in re.finditer(r'href="(/play/(\d+)-(\d+)-(\d+)\.html)"[^>]*>([\s\S]{0,80}?)</a>', h, re.I):
            if m.group(2) != vid: continue
            sid, nid = int(m.group(3)), int(m.group(4))
            # 优先从 <span> 取名称
            sp = re.search(r'<span[^>]*>([^<]+)</span>', m.group(5), re.I)
            nm = self._txt(sp.group(1)) if sp else self._txt(m.group(5))
            nm = re.sub(r'\s+', '', nm) or ('第%02d集' % nid)
            if nm in ('立即播放', '立刻播放', '播放', '立即观看', '在线播放') or ('播放' in nm and len(nm) <= 5):
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
        d = self._extract_json(h, 'player_aaaa')
        if d:
            raw = d.get('url', '').replace('\\/', '/').replace('\\u002F', '/')
            # 1. 直链判断
            if self.isVideoFormat(raw):
                return {'parse': 0, 'url': raw, 'header': {'User-Agent': self.UA, 'Referer': self.HOST + '/'}}
            # 2. encrypt=1: unescape解码
            enc = d.get('encrypt', 0)
            if enc == 1 and raw:
                try:
                    decoded = urllib.parse.unquote(raw)
                    if self.isVideoFormat(decoded):
                        return {'parse': 0, 'url': decoded, 'header': {'User-Agent': self.UA, 'Referer': self.HOST + '/'}}
                except: pass
            # 3. encrypt=2: base64decode + unescape
            if enc == 2 and raw:
                try:
                    decoded = urllib.parse.unquote(base64.b64decode(raw).decode('utf-8', 'ignore'))
                    if self.isVideoFormat(decoded):
                        return {'parse': 0, 'url': decoded, 'header': {'User-Agent': self.UA, 'Referer': self.HOST + '/'}}
                except: pass
            # 4. 核心路径: 调用 /lvplayer/api.php 获取加密URL, 用decode2解密
            if raw:
                m3u8 = self._resolve_play(raw, play)
                if m3u8:
                    return {'parse': 0, 'url': m3u8, 'header': {'User-Agent': self.UA, 'Referer': self.HOST + '/'}}
                # fallback: 解析页 webview + click
                parse_url = self.HOST + '/lvplayer/index.php?vid=' + raw
                return {
                    'parse': 1,
                    'url': parse_url,
                    'header': {'User-Agent': self.UA, 'Referer': play, 'Cookie': self._cookie_str()},
                    'click': 'document.querySelector("#start").click()',
                }
        # 兜底: 页面直链
        for p in (r'[?&](?:url|v|m3u8|playurl|src|video)=([^"\'&\s<>]+?\.(?:m3u8|mp4)[^"\'&\s<>]*)',
                  r'(https?:[^"\'\\\s<>]+?\.m3u8[^"\'\\\s<>]*)'):
            url_m = re.search(p, h, re.I)
            if url_m:
                cand = urllib.parse.unquote(url_m.group(1).replace('\\/', '/'))
                if self.isVideoFormat(cand):
                    return {'parse': 0, 'url': cand, 'header': {'User-Agent': self.UA, 'Referer': self.HOST + '/'}}
        return {'parse': 1, 'url': play, 'header': self._hd(play)}

    # ======================== 播放解析: 调用api.php + decode2解密
    def _resolve_play(self, vid, play_url):
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        api_url = self.HOST + '/lvplayer/api.php'
        data = urllib.parse.urlencode({'vid': vid}).encode('utf-8')
        headers = {
            'User-Agent': self.UA,
            'Referer': play_url,
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Cookie': self._cookie_str(),
        }
        # 重试最多8次, 直到获取urlmode=2(可用decode2解密)
        for _ in range(8):
            try:
                req = urllib.request.Request(api_url, data=data, headers=headers)
                with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                    api_resp = resp.read().decode('utf-8', 'ignore')
                info = json.loads(api_resp).get('data', {})
                cipher = info.get('url', '')
                urlmode = int(info.get('urlmode', 0) or 0)
                # decode2 对 urlmode=2 有效
                if urlmode == 2:
                    url = self._decode2(cipher)
                    if url and url.startswith('http'):
                        return url
                # decode1 对 urlmode=1 (密钥可能不同, 也尝试)
                if urlmode == 1:
                    url = self._decode1(cipher)
                    if url and url.startswith('http'):
                        return url
                    # 也试 decode2
                    url = self._decode2(cipher)
                    if url and url.startswith('http'):
                        return url
            except:
                pass
        return ''

    # ======================== 解密辅助
    @staticmethod
    def _fix_b64(s):
        s = re.sub(r'[^A-Za-z0-9+/=]', '', str(s).strip())
        return s + '=' * (-len(s) % 4)

    def _decode1(self, cipher):
        try:
            raw = base64.b64decode(self._fix_b64(cipher))
            key = hashlib.md5(b'#tips').hexdigest().encode('utf-8')
            s2 = bytearray(raw[i] ^ key[i % len(key)] for i in range(len(raw)))
            s2_str = self._fix_b64(s2.decode('utf-8', 'ignore'))
            return urllib.parse.unquote(base64.b64decode(s2_str).decode('utf-8', 'ignore'))
        except:
            return ''

    def _decode2(self, cipher):
        try:
            raw = base64.b64decode(self._fix_b64(cipher)).decode('utf-8', 'ignore')
            m_map = 'PXhw7UT1B0a9kQDKZsjIASmOezxYG4CHo5Jyfg2b8FLpEvRr3WtVnlqMidu6cN'
            return urllib.parse.unquote(''.join(
                m_map[(m_map.find(c) + 59) % 62] if m_map.find(c) != -1 else c
                for c in raw[1::3]
            ).strip())
        except:
            return ''

    # ======================== 配置
    config = {
        "player": {},
        "filter": {
            "1": [{"key": "by", "name": "排序", "value": [{"n": "日榜", "v": "day"}, {"n": "周榜", "v": "week"}, {"n": "月榜", "v": "month"}]}],
            "2": [{"key": "by", "name": "排序", "value": [{"n": "日榜", "v": "day"}, {"n": "周榜", "v": "week"}, {"n": "月榜", "v": "month"}]}],
            "3": [{"key": "by", "name": "排序", "value": [{"n": "日榜", "v": "day"}, {"n": "周榜", "v": "week"}, {"n": "月榜", "v": "month"}]}],
            "4": [{"key": "by", "name": "排序", "value": [{"n": "日榜", "v": "day"}, {"n": "周榜", "v": "week"}, {"n": "月榜", "v": "month"}]}],
        },
    }
    header = {}

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]
