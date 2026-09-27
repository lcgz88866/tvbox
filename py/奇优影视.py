"""
{
    "key": "奇优影院",
    "name": "奇优影院",
    "type": 3,
    "api": "./py/qiyou.py",
    "searchable": 1,
    "quickSearch": 1,
    "filterable": 1
}
"""

import re
import sys
import json
import time
from urllib.parse import quote, unquote, urlparse

try:
    import requests
    from requests.adapters import HTTPAdapter
    requests.packages.urllib3.disable_warnings()
except ImportError:
    requests = None

sys.path.append('..')

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        pass


class Spider(BaseSpider):

    HOST = 'http://www.qiyou03.com'
    UA = 'Mozilla/5.0 (Linux; Android 12; SM-G977N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'

    CATEGORIES = [
        {'type_id': '1', 'type_name': '电影'},
        {'type_id': '2', 'type_name': '电视剧'},
        {'type_id': '3', 'type_name': '动漫'},
        {'type_id': '4', 'type_name': '综艺'},
        # {'type_id': '6', 'type_name': '伦理'},
    ]

    def init(self, extend=''):
        if requests:
            self.s = requests.Session()
            self.s.mount('https://', HTTPAdapter(max_retries=2))
            self.s.verify = False
        else:
            self.s = None
        return self

    def getName(self):
        return '奇优影院'

    def isVideoFormat(self, url):
        return any(x in url for x in ('.m3u8', '.mp4', '.flv', '.mkv'))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ===================== HTTP =====================

    def _hd(self, ref=None):
        return {
            'User-Agent': self.UA,
            'Referer': ref or self.HOST + '/',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }

    def fetch(self, url, ref=None, tries=4):
        """GET请求, requests优先, 回退urllib"""
        if self.s:
            for _ in range(tries):
                try:
                    r = self.s.get(url, headers=self._hd(ref), timeout=20)
                    if r.status_code == 200 and len(r.text) > 200:
                        return r.text
                except Exception:
                    pass
                time.sleep(1)
            return ''
        # 回退: TVBox内置fetch
        try:
            rsp = BaseSpider.fetch(self, url, headers=self._hd(ref))
            if rsp and rsp.text:
                return rsp.text
        except Exception:
            pass
        # 最终: urllib
        try:
            import ssl, urllib.request
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers=self._hd(ref))
            with urllib.request.urlopen(req, context=ctx, timeout=20) as r:
                return r.read().decode('utf-8', errors='ignore')
        except Exception:
            return ''

    # ===================== 首页 =====================

    def homeContent(self, filter):
        res = {'class': self.CATEGORIES}
        if filter:
            res['filters'] = self._filters()
        # 首页推荐 - 取电影第1页
        res['list'] = self._parse_list('1', 1)
        return res

    def homeVideoContent(self):
        return {'list': self._parse_list('1', 1)}

    # ===================== 分类 =====================

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        vlist, pagecount = self._parse_list(tid, page, return_pagecount=True)
        return {
            'list': vlist,
            'page': page,
            'pagecount': pagecount,
            'limit': 25,
            'total': pagecount * 25,
        }

    def _parse_list(self, tid, page, return_pagecount=False):
        """解析分类列表页"""
        if page == 1:
            url = '%s/list/%s.html' % (self.HOST, tid)
        else:
            url = '%s/list/%s_%d.html' % (self.HOST, tid, page)
        h = self.fetch(url)
        if not h:
            return [] if not return_pagecount else ([], 1)

        seen, out = set(), []
        # 按卡片块提取: 每个<li>是一个卡片, 内部包含图片和标题
        for li in re.findall(r'<li[^>]*class="[^"]*col[^"]*"[^>]*>(.*?)</li>', h, re.S):
            vid_m = re.search(r'href="(/view/(\d+)\.html)"', li)
            if not vid_m:
                continue
            vid = vid_m.group(2)
            if vid in seen:
                continue
            seen.add(vid)

            # 标题: title属性或h4文本
            name = ''
            title_m = re.search(r'title="([^"]+)"', li)
            if title_m:
                name = title_m.group(1).strip()
            if not name:
                h4_m = re.search(r'<h4[^>]*class="title[^"]*"[^>]*><a[^>]*>([^<]+)</a>', li)
                if h4_m:
                    name = h4_m.group(1).strip()

            # 封面图
            pic = ''
            pic_m = re.search(r'data-original="(https?://[^"]+)"', li)
            if pic_m:
                pic = pic_m.group(1)

            # 备注: pic-text
            remarks = ''
            rem_m = re.search(r'class="[^"]*pic-text[^"]*"[^>]*>([^<]+)<', li)
            if rem_m:
                remarks = rem_m.group(1).strip()

            if vid and name:
                out.append({
                    'vod_id': vid,
                    'vod_name': name,
                    'vod_pic': pic,
                    'vod_remarks': remarks,
                })

        if not return_pagecount:
            return out

        # 总页数: 从 "1/516" 格式提取
        pagecount = 1
        pc_m = re.search(r'(\d+)\s*/\s*(\d+)', h)
        if pc_m:
            pagecount = int(pc_m.group(2))
        else:
            # 找最大页码链接
            pages = re.findall(r'href="/list/%s[_/-](\d+)\.html"' % tid, h)
            if pages:
                pagecount = max(int(p) for p in pages if p.isdigit())
        return out, pagecount

    # ===================== 详情 =====================

    def detailContent(self, ids):
        vid = ids[0]
        h = self.fetch('%s/view/%s.html' % (self.HOST, vid))
        if not h:
            return {'list': []}

        # 标题
        name = self._m(h, [
            r'<h1[^>]*>([^<]+)</h1>',
            r'<title>《([^》]+)》',
            r'<title>([^<\-|]+)\s*[|\-]',
        ])
        # 封面
        pic = self._m(h, [
            r'data-original="(https?://[^"]+)"',
            r'<img[^>]*src="(https?://[^"]+)"[^>]*alt="[^"]*封面',
            r'property="og:image"\s+content="([^"]+)"',
        ])

        # 元数据 (格式: <span class="text-muted">类型：</span>电视剧)
        vtype = self._pick_text(h, '类型')
        area = self._pick_text(h, '地区')
        year = self._pick_text(h, '年份')
        director = self._pick_text(h, '导演')
        actor = self._pick_text(h, '主演') or self._pick_text(h, '演员')
        remarks = self._pick_text(h, '状态') or self._pick_text(h, '更新')

        # 简介
        content = self._pick_text(h, '简介')
        if not content:
            raw = self._m(h, [
                r'property="og:description"\s+content="([^"]+)"',
                r'name="description"\s+content="([^"]+)"',
                r'class="desc[^"]*"[^>]*>.*?</span>\s*(.*?)\s*<a',
            ])
            if raw:
                content = re.sub(r'<[^>]+>', '', raw).strip()

        # === 播放源名称 ===
        names = self._src_names(h)

        # === 播放源剧集 ===
        blocks = self._play_blocks(h)

        # 对齐
        froms, urls = [], []
        for i, eps in enumerate(blocks):
            nm = names[i].strip() if i < len(names) and names[i] else '线路%d' % (i + 1)
            froms.append(nm)
            urls.append('#'.join('%s$%s' % (t.strip(), u) for u, t in eps))

        return {'list': [{
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_year': year,
            'vod_area': area,
            'vod_remarks': remarks,
            'vod_actor': actor,
            'vod_director': director,
            'vod_content': content,
            'type_name': vtype,
            'vod_play_from': '$$$'.join(froms),
            'vod_play_url': '$$$'.join(urls),
        }]}

    def _src_names(self, h):
        """提取播放源名称"""
        names = []

        # 1: tab切换 + href="#downN" 模式
        m = re.findall(r'<a[^>]*href="#down\d+"[^>]*>([^<]+)</a>', h)
        if m:
            names = [n.strip() for n in m if n.strip()]

        # 2: stui-vodlist__head + 播放源N
        if not names:
            m = re.findall(r'播放源\d', h)
            if m:
                names = list(dict.fromkeys(m))

        # 3: stui-pannel__head 区域
        if not names:
            heads = re.findall(r'class="stui-pannel__head[^"]*"[^>]*>(.*?)</div>', h, re.S)
            for hd in heads:
                t = re.sub(r'<[^>]+>', '', hd).strip()
                if t and ('播放' in t or '线路' in t or '下载' in t):
                    names.append(t)

        # 清理
        cleaned = []
        for n in names:
            n = n.replace('&nbsp;', '').replace('&#160;', '')
            n = re.sub(r'\s+', ' ', n).strip()
            if n:
                cleaned.append(n)
        return cleaned

    def _play_blocks(self, h):
        """提取播放源剧集列表 (按id="downN"分组)"""
        blocks = []

        # 1: 按 id="downN" 分组 (每个播放源一个tab-pane)
        downs = re.findall(r'id="down(\d+)"[^>]*>(.*?)</div>', h, re.S)
        if downs:
            for _, content in downs:
                eps = re.findall(r'href="(/play/[\d\-]+\.html)"[^>]*title="([^"]+)"', content)
                if not eps:
                    eps = re.findall(r'href="(/play/[\d\-]+\.html)"[^>]*>([^<]+)<', content)
                if eps:
                    blocks.append(eps)

        # 2: 按 tab-pane 类分组
        if not blocks:
            tab_panes = re.findall(r'class="tab-pane[^"]*"[^>]*>(.*?)</ul>', h, re.S)
            for pane in tab_panes:
                eps = re.findall(r'href="(/play/[\d\-]+\.html)"[^>]*>([^<]+)<', pane)
                if eps:
                    blocks.append(eps)

        # 3: 按 stui-content__playlist 分组
        if not blocks:
            playlists = re.findall(r'class="stui-content__playlist[^"]*"[^>]*>(.*?)</ul>', h, re.S)
            for pl in playlists:
                eps = re.findall(r'href="(/play/[\d\-]+\.html)"[^>]*>([^<]+)<', pl)
                if eps:
                    blocks.append(eps)

        # 4: 兜底: 全部 /play/ 链接按源编号分组
        if not blocks:
            all_eps = re.findall(r'href="(/play/\d+-(\d+)-(\d+)\.html)"[^>]*>([^<]+)<', h)
            src_map = {}
            for full_url, src, ep, title in all_eps:
                src = int(src)
                if src not in src_map:
                    src_map[src] = []
                src_map[src].append((full_url, title.strip()))
            for src in sorted(src_map.keys()):
                blocks.append(src_map[src])

        return blocks

    # ===================== 搜索 =====================

    def searchContent(self, key, quick, pg='1'):
        page = int(pg) if pg else 1
        url = '%s/search.php' % self.HOST

        # POST 请求搜索
        h = ''
        if self.s:
            try:
                r = self.s.post(url, data={'searchword': key}, headers={
                    **self._hd(),
                    'Content-Type': 'application/x-www-form-urlencoded',
                }, timeout=20)
                if r.status_code == 200 and len(r.text) > 500:
                    r.encoding = 'utf-8'
                    h = r.text
            except Exception:
                pass

        # 兜底: GET 方式
        if not h:
            kw = quote(key)
            h = self.fetch('%s?searchword=%s' % (url, kw))

        if not h:
            return {'list': [], 'page': page}

        seen, out = set(), []
        # 搜索页卡片结构: <div class="thumb"><a ...> + <div class="detail">
        # 先按 thumb 块提取
        for thumb in re.findall(r'<div class="thumb">(.*?)</div>\s*<div class="detail">(.*?)</div>', h, re.S):
            thumb_html, detail_html = thumb
            vid_m = re.search(r'href="(/view/(\d+)\.html)"', thumb_html)
            if not vid_m:
                continue
            vid = vid_m.group(2)
            if vid in seen:
                continue
            seen.add(vid)

            name = ''
            title_m = re.search(r'title="([^"]+)"', thumb_html)
            if title_m:
                name = title_m.group(1).strip()
            if not name:
                h3_m = re.search(r'<h3[^>]*class="title[^"]*"[^>]*><a[^>]*>([^<]+)</a>', detail_html)
                if h3_m:
                    name = h3_m.group(1).strip()

            pic = ''
            pic_m = re.search(r'data-original="(https?://[^"]+)"', thumb_html)
            if pic_m:
                pic = pic_m.group(1)

            remarks = ''
            rem_m = re.search(r'class="[^"]*pic-text[^"]*"[^>]*>([^<]+)<', thumb_html)
            if rem_m:
                remarks = rem_m.group(1).strip()

            if vid and name:
                out.append({
                    'vod_id': vid,
                    'vod_name': name,
                    'vod_pic': pic,
                    'vod_remarks': remarks,
                })

        # 兜底: 按 col 卡片块提取 (分类页布局)
        if not out:
            for li in re.findall(r'<li[^>]*class="[^"]*col[^"]*"[^>]*>(.*?)</li>', h, re.S):
                vid_m = re.search(r'href="(/view/(\d+)\.html)"', li)
                if not vid_m:
                    continue
                vid = vid_m.group(2)
                if vid in seen:
                    continue
                seen.add(vid)

                name = ''
                title_m = re.search(r'title="([^"]+)"', li)
                if title_m:
                    name = title_m.group(1).strip()
                if not name:
                    h4_m = re.search(r'<h4[^>]*class="title[^"]*"[^>]*><a[^>]*>([^<]+)</a>', li)
                    if h4_m:
                        name = h4_m.group(1).strip()

                pic = ''
                pic_m = re.search(r'data-original="(https?://[^"]+)"', li)
                if pic_m:
                    pic = pic_m.group(1)

                remarks = ''
                rem_m = re.search(r'class="[^"]*pic-text[^"]*"[^>]*>([^<]+)<', li)
                if rem_m:
                    remarks = rem_m.group(1).strip()

                if vid and name:
                    out.append({
                        'vod_id': vid,
                        'vod_name': name,
                        'vod_pic': pic,
                        'vod_remarks': remarks,
                    })

        return {'list': out, 'page': page}

    # ===================== 播放 =====================

    def playerContent(self, flag, id, vipFlags):
        play = id if id.startswith('http') else self.HOST + id
        h = self.fetch(play)

        # 1. 找iframe
        ifr = re.search(r'<iframe[^>]*src="(https?://[^"]+)"', h)
        if not ifr:
            return {'parse': 1, 'url': play, 'header': self._hd(play)}

        iframe_url = ifr.group(1)

        # 2. 请求iframe页, 提取Url/Sign/From
        p = self.fetch(iframe_url, play)
        url_m = re.search(r'const Url\s*=\s*"([^"]+)"', p)
        sign_m = re.search(r'const Sign\s*=\s*"([^"]+)"', p)
        from_m = re.search(r'const From\s*=\s*"([^"]+)"', p)

        if not url_m or not sign_m:
            return {'parse': 1, 'url': iframe_url, 'header': self._hd(play)}

        Url = url_m.group(1)
        Sign = sign_m.group(1)
        From = from_m.group(1) if from_m else ''

        # 3. 调用 /player/api.php 获取真实地址
        parsed = urlparse(iframe_url)
        api_url = '%s://%s/player/api.php' % (parsed.scheme, parsed.netloc)

        api_params = {'url': Url, 'sign': Sign, 't': From}
        api_hd = self._hd(iframe_url)
        api_hd['X-Requested-With'] = 'XMLHttpRequest'

        real_url = ''
        if self.s:
            try:
                r = self.s.get(api_url, params=api_params, headers=api_hd, timeout=20)
                if r.status_code == 200 and r.text.strip().startswith('{'):
                    j = r.json()
                    if int(j.get('code', 0)) == 200:
                        real_url = j.get('url', '')
                        if real_url:
                            real_url = unquote(real_url)
            except Exception:
                pass

        if real_url and self.isVideoFormat(real_url):
            return {'parse': 0, 'url': real_url, 'header': {'User-Agent': self.UA, 'Referer': parsed.scheme + '://' + parsed.netloc + '/'}}

        return {'parse': 1, 'url': iframe_url, 'header': self._hd(play)}

    def localProxy(self, params):
        return [200, 'text/plain', '']

    # ===================== 工具 =====================

    @staticmethod
    def _m(text, pats):
        """多正则取第一个匹配"""
        for p in pats:
            m = re.search(p, text, re.S)
            if m:
                return m.group(1).strip()
        return ''

    @staticmethod
    def _og(h, prop):
        """从og meta标签提取"""
        m = re.search(r'property="og:%s"\s+content="([^"]+)"' % prop, h)
        return m.group(1).strip() if m else ''

    @staticmethod
    def _pick_text(h, label):
        """从 <span class="text-muted">标签：</span>值 格式提取"""
        # 格式1: <span class="text-muted">标签：</span>值 (值可能在a标签内)
        m = re.search(
            r'<span[^>]*class="[^"]*text-muted[^"]*"[^>]*>%s[：:]\s*</span>\s*(?:<a[^>]*>)?([^<]+)' % label,
            h
        )
        if m:
            val = m.group(1).strip()
            if val:
                return val

        # 格式2: 直接 "标签：值" 在同一行
        m = re.search(
            r'>%s[：:]\s*</(?:span|em)>\s*([^<\n]+)' % label, h
        )
        if m:
            val = m.group(1).strip()
            val = val.split('<span')[0].strip()
            if val:
                return val

        # 格式3: 简介特殊格式 - class="desc"
        if label == '简介':
            m = re.search(r'class="desc[^"]*"[^>]*>.*?<span[^>]*>[^<]*</span>\s*(.*?)\s*(?:<a|<div|</p)', h, re.S)
            if m:
                val = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                if val:
                    return val

        return ''

    @staticmethod
    def _pick(h, label):
        """从<em>标签:</em>value</li>提取"""
        m = re.search(r'>%s[：:]</em>(.*?)</li>' % label, h, re.S)
        if not m:
            m = re.search(r'>%s\s*[：:]\s*</strong>(.*?)</div>' % label, h, re.S)
        if not m:
            m = re.search(r'%s[：:]\s*([^<\n]+)' % label, h)
        if not m:
            return ''
        seg = re.sub(r'<span class="slash">/</span>', ',', m.group(1))
        seg = re.sub(r'<[^>]+>', '', seg).replace('&nbsp;', ',')
        return re.sub(r',+', ',', seg).strip().strip(',')

    @staticmethod
    def _filters():
        """分类筛选: 类型+年份+地区"""
        f = []
        # 留空, 因为分类页筛选URL格式需要根据实际页面调整
        return {'1': f, '2': f, '3': f, '4': f, '6': f}


if __name__ == '__main__':
    s = Spider()
    s.init()

    print("===== 首页分类 =====")
    home = s.homeContent(False)
    for c in home['class']:
        print(f"  {c['type_name']} -> {c['type_id']}")

    print("\n===== 首页推荐 =====")
    hv = s.homeVideoContent()
    print(f"推荐: {len(hv['list'])}条")
    for v in hv['list'][:5]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")
        if v['vod_pic']:
            print(f"    封面: {v['vod_pic'][:60]}...")

    print("\n===== 电视剧第1页 =====")
    cat = s.categoryContent('2', '1', False, {})
    print(f"返回: {len(cat['list'])}条, 总页: {cat['pagecount']}, 总数: {cat['total']}")
    for v in cat['list'][:5]:
        print(f"  [{v['vod_id']}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 电视剧第2页 =====")
    cat2 = s.categoryContent('2', '2', False, {})
    print(f"返回: {len(cat2['list'])}条")
    for v in cat2['list'][:3]:
        print(f"  [{v['vod_id']}] {v['vod_name']}")

    print("\n===== 详情页 (电视剧) =====")
    if cat['list']:
        vid = cat['list'][0]['vod_id']
        detail = s.detailContent([vid])
        if detail['list']:
            v = detail['list'][0]
            print(f"  标题: {v['vod_name']}")
            print(f"  年份: {v['vod_year']}  地区: {v['vod_area']}  类型: {v.get('type_name', '')}")
            print(f"  导演: {v['vod_director']}")
            print(f"  演员: {v['vod_actor'][:80]}")
            print(f"  简介: {v['vod_content'][:80]}")
            print(f"  播放源: {v['vod_play_from']}")
            froms = v['vod_play_from'].split('$$$')
            urls = v['vod_play_url'].split('$$$')
            print(f"  源数: {len(froms)}, URL组数: {len(urls)}")
            for i in range(min(3, len(froms))):
                eps = urls[i].split('#')
                print(f"    源{i+1} [{froms[i]}]: {len(eps)}集, 首={eps[0][:50]}")

            # 播放测试
            if urls:
                first_ep = urls[0].split('#')[0]
                ep_name = first_ep.split('$')[0]
                ep_url = first_ep.split('$')[1] if '$' in first_ep else first_ep
                print(f"\n  播放测试: {ep_name} ({ep_url})")
                play = s.playerContent('', ep_url, [])
                print(f"  Parse: {play['parse']}")
                print(f"  URL: {play.get('url', '')[:100]}")

    print("\n===== 搜索 (战狼) =====")
    sr = s.searchContent('战狼', False)
    print(f"结果: {len(sr['list'])}条")
    for v in sr['list'][:5]:
        print(f"  [{v['vod_id']}] {v['vod_name']}")

    print("\n===== 完成 =====")