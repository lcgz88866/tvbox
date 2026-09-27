# -*- coding: utf-8 -*-
"""
{
    "key": "暮色影院",
    "name": "暮色影院",
    "type": 3,
    "api": "./py/msyy.py",
    "searchable": 1,
    "quickSearch": 1,
    "filterable": 1
}
"""

import sys
import re
import json
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

    HOST = 'https://www.msyy.tv'
    API = '/api.php/provide/vod/'
    UA = 'Mozilla/5.0 (Linux; Android 12; SM-G977N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'

    # 主分类 (type_id 为父分类ID, default_t 为默认子分类ID)
    CATEGORIES = [
        {'type_id': '63', 'type_name': '电影', 'default_t': '70'},
        {'type_id': '64', 'type_name': '电视剧', 'default_t': '84'},
        {'type_id': '65', 'type_name': '动漫', 'default_t': '120'},
        {'type_id': '66', 'type_name': '综艺', 'default_t': '97'},
        {'type_id': '67', 'type_name': '短剧', 'default_t': '67'},
        {'type_id': '68', 'type_name': '纪录片', 'default_t': '68'},
    ]

    # 子分类 (用于筛选)
    SUB_CLASSES = {
        '63': [('剧情片', '70'), ('动作片', '71'), ('喜剧片', '73'), ('恐怖片', '75'),
               ('惊悚片', '77'), ('爱情片', '79'), ('科幻片', '81'), ('战争片', '94')],
        '64': [('国产剧', '84'), ('港剧', '85'), ('韩剧', '86'), ('日剧', '87'),
               ('泰剧', '88'), ('台剧', '89'), ('欧美剧', '90')],
        '65': [('欧美动漫', '117'), ('日韩动漫', '118'), ('国产动漫', '120'), ('其他动漫', '123')],
        '66': [('大陆综艺', '97'), ('港台综艺', '98'), ('日韩综艺', '100'), ('欧美综艺', '102')],
        '67': [],
        '68': [],
    }

    YEARS = [str(y) for y in range(2026, 2014, -1)]

    def init(self, extend=''):
        if requests:
            self.s = requests.Session()
            self.s.verify = False
            self.s.headers.update({'User-Agent': self.UA})
            requests.packages.urllib3.disable_warnings()

    def getName(self):
        return '暮色影院'

    def isVideoFormat(self, url):
        return False

    def _hd(self):
        return {'User-Agent': self.UA, 'Referer': self.HOST + '/'}

    def _api(self, params):
        """调用maccms API"""
        url = self.HOST + self.API
        try:
            r = self.s.get(url, params=params, headers=self._hd(), timeout=20)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    def _filters(self):
        """生成筛选器"""
        filters = {}
        for cat in self.CATEGORIES:
            tid = cat['type_id']
            arr = [
                {
                    'key': 'class',
                    'name': '类型',
                    'init': cat['default_t'],
                    'value': [{'n': n, 'v': v} for n, v in self.SUB_CLASSES.get(tid, [])]
                },
                {
                    'key': 'year',
                    'name': '年份',
                    'init': '',
                    'value': [{'n': y, 'v': y} for y in self.YEARS]
                },
            ]
            filters[tid] = arr
        return filters

    # ===================== 首页 =====================

    def homeContent(self, filter):
        res = {'class': [{'type_id': c['type_id'], 'type_name': c['type_name']} for c in self.CATEGORIES]}
        if filter:
            res['filters'] = self._filters()
        # 首页推荐 - 用API取最新
        data = self._api({'ac': 'detail', 'pg': 1})
        res['list'] = self._parse_list(data)
        return res

    def homeVideoContent(self):
        data = self._api({'ac': 'detail', 'pg': 1})
        return {'list': self._parse_list(data)}

    # ===================== 分类 =====================

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        extend = extend or {}
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}

        # 确定 t 参数: 优先用筛选的 class, 否则用默认子分类
        t = extend.get('class', '')
        if not t:
            for c in self.CATEGORIES:
                if c['type_id'] == str(tid):
                    t = c['default_t']
                    break
        if not t:
            t = str(tid)

        params = {'ac': 'detail', 'pg': page, 't': t}
        year = extend.get('year', '')
        if year:
            params['year'] = year

        data = self._api(params)

        vlist = self._parse_list(data)
        pagecount = data.get('pagecount', 1)
        total = data.get('total', 0)

        return {
            'list': vlist,
            'page': page,
            'pagecount': pagecount,
            'limit': 40,
            'total': total,
        }

    def _parse_list(self, data):
        """解析API列表数据"""
        out = []
        for item in data.get('list', []):
            out.append({
                'vod_id': str(item.get('vod_id', '')),
                'vod_name': item.get('vod_name', '').strip(),
                'vod_pic': item.get('vod_pic', ''),
                'vod_remarks': item.get('vod_remarks', ''),
            })
        return out

    # ===================== 详情 =====================

    def detailContent(self, ids):
        vid = ids[0]
        data = self._api({'ac': 'detail', 'ids': vid})
        if not data.get('list'):
            return {'list': []}

        v = data['list'][0]
        vod = {
            'vod_id': vid,
            'vod_name': v.get('vod_name', ''),
            'vod_pic': v.get('vod_pic', ''),
            'vod_year': v.get('vod_year', ''),
            'vod_area': v.get('vod_area', ''),
            'vod_type': v.get('vod_class', ''),
            'vod_director': v.get('vod_director', ''),
            'vod_actor': v.get('vod_actor', ''),
            'vod_content': re.sub(r'<[^>]+>', '', v.get('vod_content', '')).strip(),
            'vod_play_from': v.get('vod_play_from', ''),
            'vod_play_url': v.get('vod_play_url', ''),
        }

        return {'list': [vod]}

    # ===================== 播放 =====================

    def playerContent(self, flag, id, vipFlags):
        # maccms API 直接返回 m3u8 直链, 无需解析
        url = id if id.startswith('http') else self.HOST + id
        return {
            'parse': 0,
            'url': url,
            'header': {'User-Agent': self.UA, 'Referer': self.HOST + '/'},
        }

    # ===================== 搜索 =====================

    def searchContent(self, key, quick, pg='1'):
        page = int(pg) if pg else 1

        # 用 API 搜索
        data = self._api({'ac': 'detail', 'wd': key, 'pg': page})
        out = []
        for item in data.get('list', []):
            out.append({
                'vod_id': str(item.get('vod_id', '')),
                'vod_name': item.get('vod_name', '').strip(),
                'vod_pic': item.get('vod_pic', ''),
                'vod_remarks': item.get('vod_remarks', ''),
            })

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
    if '1' in home.get('filters', {}):
        print('  电影筛选: %s' % [f['name'] for f in home['filters']['63']])

    print('\n===== 首页推荐 =====')
    hv = s.homeVideoContent()
    print('推荐: %d条' % len(hv['list']))
    for v in hv['list'][:5]:
        print('  [%s] %s - %s' % (v['vod_id'], v['vod_name'], v['vod_remarks']))
        print('     pic: %s' % v['vod_pic'][:60])

    print('\n===== 电影分类 第1页 =====')
    cat = s.categoryContent('63', '1', False, {})
    print('返回: %d条, 总页: %s, 总数: %s' % (
        len(cat['list']), cat.get('pagecount', 0), cat.get('total', 0)
    ))
    for v in cat['list'][:5]:
        print('  [%s] %s - %s' % (v['vod_id'], v['vod_name'], v['vod_remarks']))

    print('\n===== 电影分类 第2页 =====')
    cat2 = s.categoryContent('63', '2', False, {})
    print('返回: %d条' % len(cat2['list']))
    for v in cat2['list'][:3]:
        print('  [%s] %s' % (v['vod_id'], v['vod_name']))

    print('\n===== 电影分类 筛选(动作片) =====')
    cat3 = s.categoryContent('63', '1', False, {'class': '71'})
    print('返回: %d条, 总页: %s' % (len(cat3['list']), cat3.get('pagecount', 0)))
    for v in cat3['list'][:3]:
        print('  [%s] %s - %s' % (v['vod_id'], v['vod_name'], v['vod_remarks']))

    print('\n===== 电影分类 筛选(2026年) =====')
    cat4 = s.categoryContent('63', '1', False, {'year': '2026'})
    print('返回: %d条, 总页: %s' % (len(cat4['list']), cat4.get('pagecount', 0)))

    print('\n===== 电视剧分类 第1页 =====')
    cat5 = s.categoryContent('64', '1', False, {})
    print('返回: %d条, 总页: %s' % (len(cat5['list']), cat5.get('pagecount', 0)))
    for v in cat5['list'][:3]:
        print('  [%s] %s - %s' % (v['vod_id'], v['vod_name'], v['vod_remarks']))

    print('\n===== 详情页 =====')
    if hv['list']:
        vid = hv['list'][0]['vod_id']
        detail = s.detailContent([vid])
        if detail['list']:
            v = detail['list'][0]
            print('  标题: %s' % v['vod_name'])
            print('  年份: %s  地区: %s  类型: %s' % (v['vod_year'], v['vod_area'], v['vod_type']))
            print('  导演: %s' % v['vod_director'])
            print('  演员: %s' % v['vod_actor'][:60])
            print('  简介: %s' % v['vod_content'][:80])
            print('  播放源: %s' % v['vod_play_from'])
            froms = v['vod_play_from'].split('$$$')
            urls = v['vod_play_url'].split('$$$')
            print('  源数: %d, URL组数: %d' % (len(froms), len(urls)))
            for i in range(min(3, len(froms))):
                eps = urls[i].split('#')
                print('    源%d [%s]: %d集, 首=%s' % (i + 1, froms[i], len(eps), eps[0][:80]))

            # 播放测试
            if froms:
                first_ep = urls[0].split('#')[0]
                ep_name, ep_url = first_ep.split('$', 1)
                print('\n  播放测试: %s' % ep_url[:80])
                play = s.playerContent(froms[0], ep_url, [])
                print('  Parse: %s' % play.get('parse', 0))
                print('  URL: %s' % play.get('url', '')[:80])

    print('\n===== 搜索(战狼) =====')
    search = s.searchContent('战狼', False)
    print('结果: %d条' % len(search['list']))
    for v in search['list'][:5]:
        print('  [%s] %s - %s' % (v['vod_id'], v['vod_name'], v['vod_remarks']))

    print('\n===== 完成 =====')