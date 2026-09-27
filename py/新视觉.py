# -*- coding: utf-8 -*-
"""
新视觉影视 (xingyy.cc) TVBox Python Spider
苹果CMS stui模板, 拼音URL, 多播放源, 直链m3u8

URL规则:
  首页: /
  分类: /dianying/index.html  /tv/index.html  /zy/index.html  /dm/index.html
  子分类: /dongzuo/index.html  /aiqing/index.html  等
  详情: /juqing/zuianzhongxian/  (拼音路径)
  播放: /juqing/zuianzhongxian/play-0-0.html
  搜索: POST /search.php?searchword=xxx
"""

import re
import sys
import json
import time
from urllib.parse import quote

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

    HOST = 'https://www.xingyy.cc'
    UA = 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'

    # 主分类
    CATEGORIES = [
        {'type_id': 'dianying', 'type_name': '电影'},
        {'type_id': 'tv', 'type_name': '电视剧'},
        {'type_id': 'zy', 'type_name': '综艺'},
        {'type_id': 'dm', 'type_name': '动漫'},
    ]

    # 子分类筛选 {tid: {筛选key: [{n, v}, ...]}}
    # 电影子分类: 直接是子分类URL路径
    # 电视剧子分类: 同理
    FILTERS = {
        'dianying': [
            {'key': 'type', 'name': '类型', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '动作片', 'v': 'dongzuo'},
                {'n': '喜剧片', 'v': 'xiju'},
                {'n': '爱情片', 'v': 'aiqing'},
                {'n': '科幻片', 'v': 'kehuan'},
                {'n': '恐怖片', 'v': 'kongbu'},
                {'n': '战争片', 'v': 'zhanzheng'},
                {'n': '剧情片', 'v': 'juqing'},
                {'n': '纪录片', 'v': 'jilu'},
                {'n': '动画片', 'v': 'donghua'},
            ]},
        ],
        'tv': [
            {'key': 'type', 'name': '类型', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '大陆剧', 'v': 'daluju'},
                {'n': '香港剧', 'v': 'xianggang'},
                {'n': '台湾剧', 'v': 'taiwan'},
                {'n': '欧美剧', 'v': 'oumei'},
                {'n': '日本剧', 'v': 'ribenju'},
                {'n': '韩国剧', 'v': 'hanguo'},
                {'n': '海外剧', 'v': 'haiwai'},
                {'n': '泰国剧', 'v': 'taiguoju'},
            ]},
        ],
        'zy': [
            {'key': 'type', 'name': '类型', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '大陆综艺', 'v': 'dalu'},
                {'n': '日韩综艺', 'v': 'hanguozy'},
                {'n': '欧美综艺', 'v': 'omzy'},
            ]},
        ],
        'dm': [
            {'key': 'type', 'name': '类型', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '国产动漫', 'v': 'guochandongman'},
                {'n': '日韩动漫', 'v': 'rihandongman'},
                {'n': '欧美动漫', 'v': 'omeidongman'},
            ]},
        ],
    }

    def init(self, extend=''):
        if requests:
            self.s = requests.Session()
            self.s.mount('https://', HTTPAdapter(max_retries=2))
            self.s.verify = False
        else:
            self.s = None
        return self

    def getName(self):
        return '新视觉影视'

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|ts)(\?|#|$)', url, re.I))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ===================== HTTP =====================

    def _hd(self, ref=None):
        return {
            'User-Agent': self.UA,
            'Referer': ref or self.HOST + '/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }

    def fetch(self, url, ref=None, tries=3):
        if self.s:
            for _ in range(tries):
                try:
                    r = self.s.get(url, headers=self._hd(ref), timeout=15)
                    r.encoding = 'utf-8'
                    if r.status_code == 200 and len(r.text) > 200:
                        return r.text
                except Exception:
                    pass
                time.sleep(1)
            return ''
        try:
            rsp = BaseSpider.fetch(self, url, headers=self._hd(ref))
            if rsp and rsp.text:
                return rsp.text
        except Exception:
            pass
        try:
            import ssl, urllib.request
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers=self._hd(ref))
            with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
                return r.read().decode('utf-8', errors='ignore')
        except Exception:
            return ''

    # ===================== 首页 =====================

    def homeContent(self, filter):
        res = {'class': self.CATEGORIES}
        if filter:
            res['filters'] = self.FILTERS
        # 首页推荐
        res['list'] = self._parse_list('/')
        return res

    def homeVideoContent(self):
        return {'list': self._parse_list('/')}

    # ===================== 分类 =====================

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        extend = extend or {}
        sub_type = extend.get('type', '')

        # 确定URL路径
        if sub_type:
            # 子分类: /{sub_type}/index_{page}.html
            base_path = '/%s/' % sub_type
        else:
            # 主分类: /{tid}/index_{page}.html
            base_path = '/%s/' % tid

        if page == 1:
            url_path = base_path + 'index.html'
        else:
            url_path = base_path + 'index_%d.html' % page

        vlist = self._parse_list(url_path)

        # 估算总页数
        pagecount = 1
        if vlist:
            # 假设每页30条
            pagecount = 50  # 保守估计

        return {
            'list': vlist,
            'page': page,
            'pagecount': pagecount,
            'limit': 30,
            'total': pagecount * 30,
        }

    def _parse_list(self, path):
        """解析列表页卡片"""
        url = self.HOST + path if path.startswith('/') else path
        h = self.fetch(url)
        if not h:
            return []

        videos = []
        seen = set()

        # 标准卡片: <a ... href="/juqing/xxx/" title="xxx" data-original="pic">
        #   + <h4 class="stui-vodlist__title"><a ...>名称</a></h4>
        pattern = re.compile(
            r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*href="(/[^"]+/)"[^>]*title="([^"]*)"[^>]*data-original="([^"]+)"[^>]*>(.*?)</a>',
            re.S
        )
        for m in pattern.finditer(h):
            vpath = m.group(1)
            name = m.group(2).strip()
            pic = m.group(3).strip()
            inner = m.group(4)

            # 用路径作为ID (拼音路径唯一)
            vid = vpath.strip('/')

            if vid in seen or not name:
                continue
            seen.add(vid)

            # 备注: pic-text
            rem_m = re.search(r'class="[^"]*pic-text[^"]*"[^>]*>([^<]+)<', inner)
            remarks = rem_m.group(1).strip() if rem_m else ''

            videos.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': remarks,
            })

        # 兜底: 从h4标题提取
        if not videos:
            items = re.findall(r'<h4[^>]*class="stui-vodlist__title"[^>]*><a[^>]*href="(/[^"]+/)"[^>]*>([^<]+)</a></h4>', h)
            for vpath, name in items:
                vid = vpath.strip('/')
                if vid in seen:
                    continue
                seen.add(vid)
                # 找对应图片
                pic = ''
                pic_m = re.search(r'href="%s"[^>]*data-original="([^"]+)"' % re.escape(vpath), h)
                if pic_m:
                    pic = pic_m.group(1)
                videos.append({
                    'vod_id': vid,
                    'vod_name': name.strip(),
                    'vod_pic': pic,
                    'vod_remarks': '',
                })

        return videos

    # ===================== 详情 =====================

    def detailContent(self, ids):
        vid = ids[0]  # 拼音路径, 如 juqing/zuianzhongxian
        url = '%s/%s/' % (self.HOST, vid)
        h = self.fetch(url)
        if not h:
            return {'list': []}

        # 标题
        name = self._m(h, [
            r'<h3[^>]*>([^<]+)</h3>',
            r'<h1[^>]*>([^<]+)</h1>',
            r'《([^》]+)》',
        ])

        # 封面
        pic = self._m(h, [
            r'data-original="(https?://[^"]+)"',
            r'<img[^>]*src="(https?://[^"]+\.(?:jpg|png|webp)[^"]*)"',
        ])

        # 元数据
        year = self._pick_meta(h, '年份')
        area = self._pick_meta(h, '地区')
        vtype = self._pick_meta(h, '类型')
        director = self._pick_meta(h, '导演')
        actor = self._pick_meta(h, '主演') or self._pick_meta(h, '演员')
        remarks = self._pick_meta(h, '状态') or self._pick_meta(h, '更新')

        # 简介
        content = self._m(h, [
            r'id="originalDesc"[^>]*>(.*?)</div>',
            r'name="description"\s+content="([^"]+)"',
        ])
        if content:
            content = re.sub(r'<[^>]+>', '', content).strip()

        # === 播放源 ===
        # 从 playlistData 提取
        froms, urls = self._parse_play_sources(h)

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

    def _parse_play_sources(self, h):
        """从详情页提取播放源和剧集"""
        froms, urls = [], []

        # 模式1: playlistData 容器
        pd_m = re.search(r'id="playlistData"[^>]*>(.*?)</div>\s*<!--', h, re.S)
        if not pd_m:
            pd_m = re.search(r'id="playlistData"[^>]*>(.*?)</div>', h, re.S)
        if pd_m:
            content = pd_m.group(1)
            # playlist-data-item 格式
            items = re.findall(
                r'class="playlist-data-item"[^>]*data-source-idx="\d+"[^>]*data-source-name="([^"]+)"[^>]*>(.*?)</div>',
                content, re.S
            )
            if not items:
                items = re.findall(
                    r'data-source-idx="\d+"[^>]*data-source-name="([^"]+)"[^>]*>(.*?)</div>',
                    content, re.S
                )

            for name, eps_html in items:
                eps = re.findall(r'<li[^>]*><a[^>]*title="([^"]+)"[^>]*href="([^"]+)"', eps_html)
                if not eps:
                    eps = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', eps_html)
                    eps = [(t.strip(), u) for u, t in eps]
                if eps:
                    clean_name = name.strip()
                    clean_name = clean_name.replace('&nbsp;', '').replace('&#160;', '')
                    froms.append(clean_name)
                    urls.append('#'.join('%s$%s' % (t.strip(), u) for t, u in eps))

        # 模式2: 直接提取所有 play- 链接按 vfrom 分组
        if not froms:
            all_eps = re.findall(r'href="(/[^"]*play-(\d+)-(\d+)\.html)"[^>]*>([^<]+)<', h)
            src_map = {}
            for full_url, vfrom, vpart, title in all_eps:
                vfrom = int(vfrom)
                if vfrom not in src_map:
                    src_map[vfrom] = []
                src_map[vfrom].append((full_url, title.strip()))

            for src in sorted(src_map.keys()):
                froms.append('线路%d' % (src + 1))
                urls.append('#'.join('%s$%s' % (t, u) for u, t in src_map[src]))

        return froms, urls

    # ===================== 搜索 =====================

    def searchContent(self, key, quick, pg='1'):
        page = int(pg) if pg else 1
        # 搜索页有安全验证, 从分类页兜底搜索
        results = []
        seen = set()
        key_lower = key.lower()

        # 遍历首页和各主分类页
        for path in ['/', '/dianying/index.html', '/tv/index.html', '/zy/index.html', '/dm/index.html']:
            try:
                vlist = self._parse_list(path)
                for v in vlist:
                    if key_lower in v['vod_name'].lower():
                        if v['vod_id'] not in seen:
                            seen.add(v['vod_id'])
                            results.append(v)
                if len(results) >= 30:
                    break
            except Exception:
                continue

        return {'list': results[:30], 'page': page}

    # ===================== 播放 =====================

    def playerContent(self, flag, id, vipFlags):
        play = id if id.startswith('http') else self.HOST + id
        h = self.fetch(play, play.rsplit('/', 1)[0] + '/')

        if not h:
            return {'parse': 1, 'url': play, 'header': self._hd(play)}

        # 从 JS 变量提取: var now = "https://...m3u8"
        now_m = re.search(r'var\s+now\s*=\s*["\']([^"\']+)["\']', h)
        if now_m:
            real_url = now_m.group(1).strip()
            if real_url and self.isVideoFormat(real_url):
                return {'parse': 0, 'url': real_url, 'header': {'User-Agent': self.UA, 'Referer': self.HOST + '/'}}

        # 找 pn (播放源名称)
        pn_m = re.search(r'var\s+pn\s*=\s*["\']([^"\']+)["\']', h)
        pn = pn_m.group(1) if pn_m else ''

        # 找iframe
        ifr = re.search(r'<iframe[^>]*src="([^"]+)"', h)
        if ifr:
            iframe_url = ifr.group(1)
            return {'parse': 1, 'url': iframe_url, 'header': self._hd(play)}

        # 兜底: 返回播放页
        return {'parse': 1, 'url': play, 'header': self._hd(play)}

    def localProxy(self, params):
        return [200, 'text/plain', '']

    # ===================== 工具 =====================

    @staticmethod
    def _m(text, pats):
        for p in pats:
            m = re.search(p, text, re.S)
            if m:
                return m.group(1).strip()
        return ''

    @staticmethod
    def _pick_meta(h, label):
        """提取元数据: 年份/地区/类型/导演/主演/状态"""
        # 主演特殊: id="actorValue"
        if label == '主演':
            m = re.search(r'id="actorValue"[^>]*>(.*?)</span>', h, re.S)
            if m:
                val = re.sub(r'<[^>]+>', '', m.group(1))
                val = val.replace('&nbsp;', ' ').replace('&#160;', ' ').strip()
                val = re.sub(r'\s+', ' ', val)
                if val:
                    return val

        # 格式: <span class="text-muted">年份：</span><a href=...>2026</a>
        # 或: <span class="text-muted">年份：</span>2026
        pattern = r'<span[^>]*class="[^"]*text-muted[^"]*"[^>]*>%s[：:]\s*</span>\s*(?:<a[^>]*>)?([^<\n]+)' % label
        m = re.search(pattern, h)
        if m:
            val = m.group(1).strip()
            if val and len(val) < 100:
                return val

        # 格式2: 直接 "标签：值"
        m = re.search(r'%s[：:]\s*([^<\n]+)' % label, h)
        if m:
            val = m.group(1).strip()
            if val and len(val) < 100:
                return val

        return ''


if __name__ == '__main__':
    s = Spider()
    s.init()

    print("===== 首页分类 =====")
    home = s.homeContent(True)
    for c in home['class']:
        print(f"  {c['type_name']} -> {c['type_id']}")

    print("\n===== 首页推荐 =====")
    hv = s.homeVideoContent()
    print(f"推荐: {len(hv['list'])}条")
    for v in hv['list'][:5]:
        print(f"  [{v['vod_id'][:30]}] {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 电影分类 =====")
    cat = s.categoryContent('dianying', '1', True, {})
    print(f"返回: {len(cat['list'])}条")
    for v in cat['list'][:3]:
        print(f"  {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 动作片分类 =====")
    cat2 = s.categoryContent('dianying', '1', True, {'type': 'dongzuo'})
    print(f"返回: {len(cat2['list'])}条")
    for v in cat2['list'][:3]:
        print(f"  {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 电视剧分类 =====")
    cattv = s.categoryContent('tv', '1', True, {})
    print(f"返回: {len(cattv['list'])}条")
    for v in cattv['list'][:3]:
        print(f"  {v['vod_name']} - {v['vod_remarks']}")

    print("\n===== 详情页 (电影) =====")
    if cat['list']:
        vid = cat['list'][0]['vod_id']
        detail = s.detailContent([vid])
        if detail['list']:
            v = detail['list'][0]
            print(f"  标题: {v['vod_name']}")
            print(f"  年份: {v['vod_year']}  地区: {v['vod_area']}  类型: {v.get('type_name', '')}")
            print(f"  导演: {v['vod_director']}")
            print(f"  演员: {v['vod_actor'][:60]}")
            print(f"  简介: {v['vod_content'][:60]}")
            print(f"  播放源: {v['vod_play_from']}")
            froms = v['vod_play_from'].split('$$$')
            urls = v['vod_play_url'].split('$$$')
            print(f"  源数: {len(froms)}, URL组数: {len(urls)}")
            for i in range(min(2, len(froms))):
                eps = urls[i].split('#')
                print(f"    源{i+1} [{froms[i]}]: {len(eps)}集, 首={eps[0][:50]}")

            # 播放测试
            if urls:
                first = urls[0].split('#')[0]
                ep_name = first.split('$')[0]
                ep_url = first.split('$')[1] if '$' in first else first
                print(f"\n  播放测试: {ep_name}")
                play = s.playerContent('', ep_url, [])
                print(f"  Parse: {play['parse']}")
                print(f"  URL: {play.get('url', '')[:100]}")

    print("\n===== 搜索 (战狼) =====")
    sr = s.searchContent('战狼', False)
    print(f"结果: {len(sr['list'])}条")
    for v in sr['list'][:5]:
        print(f"  {v['vod_name']}")

    print("\n===== 完成 =====")