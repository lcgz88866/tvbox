# -*- coding: utf-8 -*-
"""
{
    "key": "VidHub视频库",
    "name": "VidHub视频库",
    "type": 3,
    "api": "./py/vidhub.py",
    "searchable": 1,
    "quickSearch": 1,
    "filterable": 1
}
"""

import sys
import re
import json
from urllib.parse import quote, unquote

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

    HOST = 'https://vidhub2.top'

    # 主分类
    CATEGORIES = [
        {'type_id': '1', 'type_name': '电影'},
        {'type_id': '2', 'type_name': '电视剧'},
        {'type_id': '3', 'type_name': '综艺'},
        {'type_id': '4', 'type_name': '动漫'},
    ]

    # 子类型筛选 (URL编码值)
    CLASSES = {
        '1': [
            ('喜剧', '%E5%96%9C%E5%89%A7'), ('爱情', '%E7%88%B1%E6%83%85'),
            ('恐怖', '%E6%81%90%E6%80%96'), ('动作', '%E5%8A%A8%E4%BD%9C'),
            ('科幻', '%E7%A7%91%E5%B9%BB'), ('剧情', '%E5%89%A7%E6%83%85'),
            ('战争', '%E6%88%98%E4%BA%89'), ('警匪', '%E8%AD%A6%E5%8C%AA'),
            ('犯罪', '%E7%8A%AF%E7%BD%AA'), ('动画', '%E5%8A%A8%E7%94%BB'),
            ('奇幻', '%E5%A5%87%E5%B9%BB'), ('武侠', '%E6%AD%A6%E4%BE%A0'),
            ('冒险', '%E5%86%92%E9%99%A9'), ('枪战', '%E6%9E%AA%E6%88%98'),
            ('悬疑', '%E6%82%AC%E7%96%91'), ('惊悚', '%E6%83%8A%E6%82%9A'),
            ('经典', '%E7%BB%8F%E5%85%B8'), ('青春', '%E9%9D%92%E6%98%A5'),
            ('文艺', '%E6%96%87%E8%89%BA'), ('微电影', '%E5%BE%AE%E7%94%B5%E5%BD%B1'),
            ('古装', '%E5%8F%A4%E8%A3%85'), ('历史', '%E5%8E%86%E5%8F%B2'),
            ('运动', '%E8%BF%90%E5%8A%A8'), ('农村', '%E5%86%9C%E6%9D%91'),
            ('儿童', '%E5%84%BF%E7%AB%A5'), ('网络电影', '%E7%BD%91%E7%BB%9C%E7%94%B5%E5%BD%B1'),
        ],
        '2': [
            ('古装', '%E5%8F%A4%E8%A3%85'), ('言情', '%E8%A8%80%E6%83%85'),
            ('武侠', '%E6%AD%A6%E4%BE%A0'), ('偶像', '%E5%81%B6%E5%83%8F'),
            ('家庭', '%E5%AE%B6%E5%BA%AD'), ('喜剧', '%E5%96%9C%E5%89%A7'),
            ('战争', '%E6%88%98%E4%BA%89'), ('校园', '%E6%A0%A1%E5%9B%AD'),
            ('悬疑', '%E6%82%AC%E7%96%91'), ('犯罪', '%E7%8A%AF%E7%BD%AA'),
            ('奇幻', '%E5%A5%87%E5%B9%BB'), ('剧情', '%E5%89%A7%E6%83%85'),
            ('历史', '%E5%8E%86%E5%8F%B2'), ('短剧', '%E7%9F%AD%E5%89%A7'),
        ],
        '3': [
            ('选秀', '%E9%80%89%E7%A7%80'), ('情感', '%E6%83%85%E6%84%9F'),
            ('音乐', '%E9%9F%B3%E4%B9%90'), ('都市', '%E9%83%BD%E5%B8%82'),
            ('体育', '%E4%BD%93%E8%82%B2'), ('旅游', '%E6%97%85%E6%B8%B8'),
            ('美食', '%E7%BE%8E%E9%A3%9F'), ('访谈', '%E8%AE%BF%E8%B0%88'),
            ('纪实', '%E7%BA%AA%E5%AE%9E'), ('游戏', '%E6%B8%B8%E6%88%8F'),
        ],
        '4': [
            ('热血', '%E7%83%AD%E8%A1%80'), ('格斗', '%E6%A0%BC%E6%96%97'),
            ('恋爱', '%E6%81%8B%E7%88%B1'), ('校园', '%E6%A0%A1%E5%9B%AD'),
            ('搞笑', '%E6%90%9E%E7%AC%91'), ('玄幻', '%E7%8E%84%E5%B9%BB'),
            ('冒险', '%E5%86%92%E9%99%A9'), ('魔法', '%E9%AD%94%E6%B3%95'),
            ('机战', '%E6%9C%BA%E6%88%98'), ('科幻', '%E7%A7%91%E5%B9%BB'),
            ('治愈', '%E6%B2%BB%E6%84%88'), ('推理', '%E6%8E%A8%E7%90%86'),
            ('历史', '%E5%8E%86%E5%8F%B2'), ('运动', '%E8%BF%90%E5%8A%A8'),
            ('战斗', '%E6%88%98%E6%96%97'), ('古装', '%E5%8F%A4%E8%A3%85'),
        ],
    }

    AREAS = [
        ('大陆', '%E5%A4%A7%E9%99%86'), ('香港', '%E9%A6%99%E6%B8%AF'),
        ('台湾', '%E5%8F%B0%E6%B9%BE'), ('美国', '%E7%BE%8E%E5%9B%BD'),
        ('法国', '%E6%B3%95%E5%9B%BD'), ('英国', '%E8%8B%B1%E5%9B%BD'),
        ('日本', '%E6%97%A5%E6%9C%AC'), ('韩国', '%E9%9F%A9%E5%9B%BD'),
        ('德国', '%E5%BE%B7%E5%9B%BD'), ('泰国', '%E6%B3%B0%E5%9B%BD'),
        ('印度', '%E5%8D%B0%E5%BA%A6'), ('其他', '%E5%85%B6%E4%BB%96'),
    ]

    YEARS = [str(y) for y in range(2026, 2012, -1)]

    def init(self, extend=''):
        if requests:
            self.s = requests.Session()
            self.s.verify = False
            self.s.headers.update({
                'User-Agent': 'Mozilla/5.0 (Linux; Android 12; SM-G977N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            })
            requests.packages.urllib3.disable_warnings()
            try:
                self.s.get(self.HOST, timeout=20)
            except Exception:
                pass

    def getName(self):
        return 'VidHub视频库'

    def isVideoFormat(self, url):
        return False

    def _hd(self, referer=None):
        h = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 12; SM-G977N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        }
        if referer:
            h['Referer'] = referer
        return h

    def fetch(self, url, referer=None):
        try:
            if not hasattr(self, 's') or self.s is None:
                if requests:
                    self.s = requests.Session()
                    self.s.verify = False
                    requests.packages.urllib3.disable_warnings()
                else:
                    return ''
            r = self.s.get(url, headers=self._hd(referer), timeout=20)
            if r.status_code == 200:
                r.encoding = 'utf-8'
                return r.text
        except Exception:
            pass
        return ''

    # ===================== 筛选器 =====================

    def _filters(self):
        """生成筛选器配置"""
        filters = {}
        for cat in self.CATEGORIES:
            tid = cat['type_id']
            arr = [
                {
                    'key': 'class',
                    'name': '类型',
                    'init': '',
                    'value': [{'n': name, 'v': val} for name, val in self.CLASSES.get(tid, [])]
                },
                {
                    'key': 'area',
                    'name': '地区',
                    'init': '',
                    'value': [{'n': name, 'v': val} for name, val in self.AREAS]
                },
                {
                    'key': 'year',
                    'name': '年份',
                    'init': '',
                    'value': [{'n': y, 'v': y} for y in self.YEARS]
                },
                {
                    'key': 'by',
                    'name': '排序',
                    'init': 'time',
                    'value': [
                        {'n': '最新', 'v': 'time'},
                        {'n': '最热', 'v': 'hits'},
                        {'n': '评分', 'v': 'score'},
                    ]
                },
            ]
            filters[tid] = arr
        return filters

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
        # extend 可能是 JSON 字符串
        if extend and isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        extend = extend or {}

        # 构建筛选URL: 12个字段, 11个短横分隔
        # [0]=tid, [1]=area, [2]=by, [3]=class, [4]=letter, [5]=?, [6]=?, [7]=?, [8]=page, [9]=?, [10]=?, [11]=year
        parts = [''] * 12
        parts[0] = str(tid)
        area = extend.get('area', '')
        if area:
            parts[1] = area
        by = extend.get('by', '')
        if by:
            parts[2] = by
        vclass = extend.get('class', '')
        if vclass:
            parts[3] = vclass
        year = extend.get('year', '')
        if year:
            parts[11] = year
        if page > 1:
            parts[8] = str(page)

        url = '%s/vodshow/%s.html' % (self.HOST, '-'.join(parts))
        h = self.fetch(url, referer=self.HOST)
        if not h:
            return {'list': [], 'page': page, 'pagecount': 1, 'limit': 30, 'total': 30}

        vlist, pagecount = self._parse_list_html(h, return_pagecount=True)
        return {
            'list': vlist,
            'page': page,
            'pagecount': pagecount,
            'limit': 72,
            'total': pagecount * 72 if pagecount else 0,
        }

    def _parse_list(self, tid, page):
        """简单列表解析 (首页推荐用)"""
        parts = [''] * 12
        parts[0] = str(tid)
        if page > 1:
            parts[8] = str(page)
        url = '%s/vodshow/%s.html' % (self.HOST, '-'.join(parts))
        h = self.fetch(url, referer=self.HOST)
        if not h:
            return []
        return self._parse_list_html(h)

    def _parse_list_html(self, h, return_pagecount=False):
        """解析列表页HTML"""
        seen, out = set(), []
        # 按 module-item-pic 块提取 vid+name+pic (紧凑匹配避免跨卡片)
        for m in re.finditer(
            r'<div class="module-item-pic">\s*'
            r'<a[^>]*href="/voddetail/(\d+)\.html"\s*title="([^"]+)"[^>]*>.*?'
            r'<img[^>]*data-src="([^"]*)"[^>]*>',
            h, re.S
        ):
            vid = m.group(1)
            name = m.group(2).strip()
            pic = m.group(3)
            if vid in seen:
                continue
            seen.add(vid)

            # 备注: 在卡片内找 module-item-caption
            card_end = h.find('</div>', h.find('</div>', m.end()) + 50)
            card_chunk = h[m.start():m.end() + 500] if m.end() + 500 < len(h) else h[m.start():]
            remarks = ''
            cap_m = re.search(r'module-item-caption[^>]*>(.*?)</div>', card_chunk, re.S)
            if cap_m:
                cap = re.sub(r'<[^>]+>', ' ', cap_m.group(1)).strip()
                remarks = re.sub(r'\s+', ' ', cap)

            out.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': remarks,
            })

        if not return_pagecount:
            return out

        # 翻页: 从页码链接提取最大页码 (通用匹配: 数字+---.html结尾)
        pagecount = 1
        page_nums = re.findall(r'(\d+)---\.html', h)
        if page_nums:
            pagecount = max(int(p) for p in page_nums)

        return out, pagecount

    # ===================== 详情 =====================

    def detailContent(self, ids):
        vid = ids[0]
        url = '%s/voddetail/%s.html' % (self.HOST, vid)
        h = self.fetch(url, referer=self.HOST)
        if not h:
            return {'list': []}

        vod = {
            'vod_id': vid,
            'vod_name': '',
            'vod_pic': '',
            'vod_year': '',
            'vod_area': '',
            'vod_type': '',
            'vod_director': '',
            'vod_actor': '',
            'vod_content': '',
            'vod_play_from': '',
            'vod_play_url': '',
        }

        # 标题
        h1_m = re.search(r'<h1 class="page-title"[^>]*>(.*?)</h1>', h, re.S)
        if h1_m:
            vod['vod_name'] = re.sub(r'<[^>]+>', '', h1_m.group(1)).strip()

        # 封面
        pic_m = re.search(r'class="video-cover"[^>]*>.*?data-src="([^"]+)"', h, re.S)
        if pic_m:
            vod['vod_pic'] = pic_m.group(1)

        # 元数据: 从 video-info-aux 提取类型/地区/年份
        aux_m = re.search(r'class="video-info-aux[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>', h, re.S)
        if aux_m:
            aux = aux_m.group(1)
            # 年份
            year_m = re.search(r'/vodshow/\d+-----------(\d{4})\.html', aux)
            if year_m:
                vod['vod_year'] = year_m.group(1)
            # 地区
            area_m = re.search(r'/vodshow/\d+-(%[^"\\]+)----------', aux)
            if area_m:
                vod['vod_area'] = unquote(area_m.group(1))
            # 类型
            types = re.findall(r'/vodshow/\d+---(%[^"\\]+)--------', aux)
            if types:
                vod['vod_type'] = '/'.join([unquote(t) for t in types])

        # 导演、主演、简介等
        for label, field in [('导演：', 'vod_director'), ('主演：', 'vod_actor')]:
            label_m = re.search(
                r'class="video-info-itemtitle">%s</span>(.*?)(?=class="video-info-itemtitle"|$)' % re.escape(label),
                h, re.S
            )
            if label_m:
                val_html = label_m.group(1)
                # 提取 a 标签文本
                names = re.findall(r'<a[^>]*>([^<]+)</a>', val_html)
                if names:
                    vod[field] = '/'.join(n.strip() for n in names)
                else:
                    vod[field] = re.sub(r'<[^>]+>', '', val_html).strip().strip('/')

        # 简介 - 从"剧情"标签提取
        desc_m = re.search(r'class="video-info-itemtitle">剧情：</span>(.*?)(?=class="video-info-itemtitle"|</div>\s*</div>\s*</div>)', h, re.S)
        if desc_m:
            vod['vod_content'] = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip().strip('&nbsp;').strip()

        # 播放源和剧集
        play_from, play_url = self._parse_play_sources(h, vid)
        vod['vod_play_from'] = play_from
        vod['vod_play_url'] = play_url

        return {'list': [vod]}

    def _parse_play_sources(self, h, vid):
        """提取播放源和剧集"""
        # 播放源名称列表
        src_names = re.findall(r'data-dropdown-value="([^"]+)"[^>]*>.*?<small>(\d+)</small>', h, re.S)

        # 如果没找到 tab, 尝试直接从 glist 块提取
        if not src_names:
            # 找所有 glist-N 块
            glists = re.findall(r'id="(glist-(\d+))"[^>]*>(.*?)(?=id="glist-|<div class="module-blocklist scroll-box|$)', h, re.S)
            src_names = [('线路' + str(i + 1), '0') for i in range(len(glists))]

        if not src_names:
            return '', ''

        from_list, url_list = [], []
        for i, (src_name, _count) in enumerate(src_names):
            src_idx = i + 1  # glist-N 从1开始
            # 找 glist-N 块中的剧集
            glist_m = re.search(
                r'id="glist-%d"[^>]*>(.*?)(?=id="glist-|<div class="module-blocklist scroll-box scroll-box-y"|$)' % src_idx,
                h, re.S
            )
            if not glist_m:
                continue

            block = glist_m.group(1)
            # 提取剧集
            eps = re.findall(
                r'href="(/vodplay/(\d+)-(\d+)-(\d+)\.html)"[^>]*title="([^"]*)"[^>]*>.*?<span[^>]*>(.*?)</span>',
                block, re.S
            )
            if not eps:
                # 备用: 只提取 href 和 span
                eps = re.findall(
                    r'href="(/vodplay/(\d+)-(\d+)-(\d+)\.html)"[^>]*>.*?<span>(.*?)</span>',
                    block, re.S
                )

            if not eps:
                continue

            from_list.append(src_name)
            ep_parts = []
            for ep in eps:
                if len(ep) == 6:
                    url, _vid, _sid, nid, _title, name = ep
                elif len(ep) == 5:
                    url, _vid, _sid, nid, name = ep
                else:
                    continue
                name = re.sub(r'<[^>]+>', '', name).strip()
                if not name:
                    name = '第%s集' % nid
                ep_parts.append('%s$%s' % (name, url))

            url_list.append('#'.join(ep_parts))

        return '$$$'.join(from_list), '$$$'.join(url_list)

    # ===================== 播放 =====================

    def playerContent(self, flag, id, vipFlags):
        play_url = id if id.startswith('http') else self.HOST + id
        h = self.fetch(play_url, referer=self.HOST)
        _hd = {'User-Agent': 'Mozilla/5.0 (Linux; Android 12; SM-G977N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36', 'Referer': self.HOST + '/'}

        # 提取 iframe src
        iframe_m = re.search(r'<iframe[^>]*src="(/player/\?[^"]*)"', h)
        if iframe_m:
            player_path = iframe_m.group(1)
            # 访问 player iframe 页面
            player_url = self.HOST + player_path
            ph = self.fetch(player_url, referer=play_url)
            if ph:
                # 提取 var config = {"url":"..."}
                config_m = re.search(r'var\s+config\s*=\s*(\{.*?\})\s*;', ph, re.S)
                if config_m:
                    try:
                        config = json.loads(config_m.group(1))
                        url = config.get('url', '')
                        if url:
                            return {'parse': 0, 'url': url, 'header': _hd}
                    except (json.JSONDecodeError, KeyError):
                        pass

                # 备用: 直接搜索 m3u8
                m3u8_m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', ph)
                if m3u8_m:
                    return {'parse': 0, 'url': m3u8_m.group(1), 'header': _hd}

        # 兜底: 从播放页直接搜索 m3u8
        m3u8_m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', h)
        if m3u8_m:
            return {'parse': 0, 'url': m3u8_m.group(1), 'header': _hd}

        # 最终兜底
        return {'parse': 1, 'url': play_url, 'header': _hd}

    # ===================== 搜索 =====================

    def searchContent(self, key, quick, pg='1'):
        page = int(pg) if pg else 1
        # vodsearch 有验证码, 用 AJAX suggest API
        url = '%s/index.php/ajax/suggest?mid=1&wd=%s&limit=20&page=%d' % (
            self.HOST, quote(key), page
        )

        h = self.fetch(url, referer=self.HOST)
        if not h:
            return {'list': [], 'page': page}

        try:
            data = json.loads(h)
        except (json.JSONDecodeError, ValueError):
            return {'list': [], 'page': page}

        out = []
        for item in data.get('list', []):
            vid = str(item.get('id', ''))
            name = item.get('name', '').strip()
            pic = item.get('pic', '')
            if vid and name:
                out.append({
                    'vod_id': vid,
                    'vod_name': name,
                    'vod_pic': pic,
                    'vod_remarks': '',
                })

        pagecount = data.get('pagecount', 1)
        return {'list': out, 'page': page}

    def localProxy(self, params):
        return [200, 'text/plain', '', {}]


# ===================== 测试 =====================

if __name__ == '__main__':
    s = Spider()
    s.init()

    print('===== 首页分类 =====')
    home = s.homeContent(True)
    for c in home['class']:
        print('  %s -> %s' % (c['type_name'], c['type_id']))
    print('  筛选器: %d 个分类' % len(home.get('filters', {})))

    print('\n===== 首页推荐 =====')
    hv = s.homeVideoContent()
    print('推荐: %d条' % len(hv['list']))
    for v in hv['list'][:5]:
        print('  [%s] %s - %s' % (v['vod_id'], v['vod_name'], v['vod_remarks']))
        print('     pic: %s' % v['vod_pic'][:60])

    print('\n===== 电影分类 第1页 =====')
    cat = s.categoryContent('1', '1', True, {})
    print('返回: %d条, 总页: %s, 总数: %s' % (
        len(cat['list']), cat.get('pagecount', 0), cat.get('total', 0)
    ))
    for v in cat['list'][:5]:
        print('  [%s] %s - %s' % (v['vod_id'], v['vod_name'], v['vod_remarks']))

    print('\n===== 电影分类 第2页 =====')
    cat2 = s.categoryContent('1', '2', False, {})
    print('返回: %d条' % len(cat2['list']))
    for v in cat2['list'][:3]:
        print('  [%s] %s' % (v['vod_id'], v['vod_name']))

    print('\n===== 电视剧分类 第1页 =====')
    cat3 = s.categoryContent('2', '1', False, {})
    print('返回: %d条, 总页: %s' % (len(cat3['list']), cat3.get('pagecount', 0)))
    for v in cat3['list'][:5]:
        print('  [%s] %s - %s' % (v['vod_id'], v['vod_name'], v['vod_remarks']))

    print('\n===== 详情页 (电视剧) =====')
    if cat3['list']:
        vid = cat3['list'][0]['vod_id']
        detail = s.detailContent([vid])
        if detail['list']:
            v = detail['list'][0]
            print('  标题: %s' % v['vod_name'])
            print('  年份: %s  地区: %s  类型: %s' % (v['vod_year'], v['vod_area'], v['vod_type']))
            print('  导演: %s' % v['vod_director'])
            print('  演员: %s' % v['vod_actor'][:80])
            print('  简介: %s' % v['vod_content'][:80])
            print('  播放源: %s' % v['vod_play_from'])
            froms = v['vod_play_from'].split('$$$')
            urls = v['vod_play_url'].split('$$$')
            print('  源数: %d, URL组数: %d' % (len(froms), len(urls)))
            for i in range(min(3, len(froms))):
                eps = urls[i].split('#')
                print('    源%d [%s]: %d集, 首=%s' % (i + 1, froms[i], len(eps), eps[0][:50]))

            # 播放测试
            if froms:
                first_ep = urls[0].split('#')[0]
                ep_name, ep_url = first_ep.split('$', 1)
                print('\n  播放测试: %s (%s)' % (ep_name, ep_url))
                play = s.playerContent(froms[0], ep_url, [])
                print('  Parse: %s' % play.get('parse', 0))
                print('  URL: %s' % play.get('url', '')[:100])

    print('\n===== 详情页 (电影) =====')
    if hv['list']:
        vid = hv['list'][0]['vod_id']
        detail = s.detailContent([vid])
        if detail['list']:
            v = detail['list'][0]
            print('  标题: %s' % v['vod_name'])
            print('  播放源: %s' % v['vod_play_from'])
            froms = v['vod_play_from'].split('$$$')
            urls = v['vod_play_url'].split('$$$')
            for i in range(min(3, len(froms))):
                eps = urls[i].split('#')
                print('    源%d [%s]: %d集' % (i + 1, froms[i], len(eps)))
                for ep in eps[:2]:
                    print('      %s' % ep[:50])

            if froms:
                first_ep = urls[0].split('#')[0]
                ep_name, ep_url = first_ep.split('$', 1)
                print('\n  播放测试: %s' % ep_url)
                play = s.playerContent(froms[0], ep_url, [])
                print('  Parse: %s' % play.get('parse', 0))
                print('  URL: %s' % play.get('url', '')[:100])

    print('\n===== 搜索 (战狼) =====')
    search = s.searchContent('战狼', False)
    print('结果: %d条' % len(search['list']))
    for v in search['list'][:5]:
        print('  [%s] %s' % (v['vod_id'], v['vod_name']))
        print('     pic: %s' % v['vod_pic'][:60])

    print('\n===== 完成 =====')
