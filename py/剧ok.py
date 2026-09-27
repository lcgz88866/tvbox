"""
{
    "key": "剧ok",
    "name": "剧OK",
    "type": 3,
    "api": "./py/剧ok.py",
    "searchable": 1,
    "quickSearch": 1,
    "filterable": 1
}
"""

import re
import urllib.parse
from urllib.parse import quote
import requests
from requests.adapters import HTTPAdapter

requests.packages.urllib3.disable_warnings()

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        pass


class Spider(BaseSpider):
    """
    剧OK / 柯南影视 / 耐看点播 爬虫 (本地占位版 v3)

    目标: 在 TVBox 里至少能看到 4 个长视频分类 + 短剧分类, 而不是"加载没数据".

    历史踩坑:
      - 旧爬虫用 /api/vod + /vdetail/<id>.html, 源站已迁 Next.js, 这两个路径 404/403.
      - 站点全部页面有 IP 级滑块, Python 无法拖动.
      - 站长加上了 /api/config, 含 nav/筛选, 但没有 list/detail 数据接口,
        所以即便白名单绕过, 也拉不出视频列表卡片.

    本版策略:
      - 不再做网络请求 (源站无可用数据).
      - 4 个长视频分类 (电影/电视剧/综艺/动漫) 直接硬编码, 不依赖站点.
      - 不去碰短剧源 (用户上一轮明确说"不需要短剧").
      - 所有接口零网络依赖, 不会因为超时/异常让 TVBox 看不到分类.
      - 列表/详情/搜索全是空, TVBox 看到"加载没数据"属正常 (源头为空).
        但分类一定可见, 这是用户当前能拿到的最大确定性.
    """

    UA = 'Mozilla/5.0 (Linux; Android 12; SM-G977N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'

    # 长视频分类 (与 Next.js navConfig.catId 对齐)
    CATEGORIES = [
        {'type_id': '1', 'type_name': '电影'},
        {'type_id': '2', 'type_name': '电视剧'},
        {'type_id': '3', 'type_name': '综艺'},
        {'type_id': '4', 'type_name': '动漫'},
    ]

    # 每类筛选 (本地硬编码, 不发请求避免 TVBox 卡死)
    FILTER_TYPES_BY_CAT = {
        '1': ['全部', '喜剧', '爱情', '动作', '恐怖', '科幻', '剧情', '犯罪', '惊悚', '战争', '悬疑',
              '动画', '奇幻', '冒险', '家庭', '传记', '历史'],
        '1_areas': ['全部', '大陆', '香港', '台湾', '泰国', '美国', '韩国', '日本', '英国', '印度'],
        '2': ['全部', '剧情', '爱情', '喜剧', '悬疑', '古装', '武侠', '都市', '家庭', '犯罪',
              '战争', '历史', '科幻', '奇幻', '青春', '谍战'],
        '2_areas': ['全部', '大陆', '香港', '台湾', '泰国', '日本', '韩国', '美国', '英国', '新加坡'],
        '3': ['全部', '真人秀', '脱口秀', '选秀', '访谈', '音乐', '搞笑', '游戏', '旅游', '美食'],
        '3_areas': ['全部', '大陆', '香港', '台湾', '日本', '欧美'],
        '4': ['全部', '热血', '搞笑', '恋爱', '冒险', '治愈', '校园', '科幻', '悬疑', '奇幻', '机战'],
        '4_areas': ['全部', '大陆', '日本', '美国'],
    }

    YEAR_LIST = ['全部'] + [str(y) for y in range(2026, 2009, -1)]

    SORTS = [
        {'key': 'by', 'name': '排序', 'value': [
            {'n': '最新', 'v': 'time'},
            {'n': '最热', 'v': 'hits'},
            {'n': '评分', 'v': 'score'},
        ]},
    ]

    # ============================================================
    # 基础
    # ============================================================

    def init(self, extend=""):
        # 不发任何网络请求. Chaquopy 启动期要尽量快.
        self.s = requests.Session()
        self.s.mount('https://', HTTPAdapter(max_retries=1))
        self.s.mount('http://', HTTPAdapter(max_retries=1))
        self.s.verify = False
        return self

    def getName(self):
        return '剧OK'

    def isVideoFormat(self, url):
        if not url:
            return False
        return any(x in url for x in ('.m3u8', '.mp4', '.flv', '.mkv'))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    def localProxy(self, params):
        return [200, 'text/plain', '']

    # ============================================================
    # TVBox 接口
    # ============================================================

    def homeContent(self, filter):
        """首页: 4 个长视频分类硬编码返回. 不发请求, 不依赖网络."""
        res = {
            'class': [
                {'type_id': '1', 'type_name': '电影'},
                {'type_id': '2', 'type_name': '电视剧'},
                {'type_id': '3', 'type_name': '综艺'},
                {'type_id': '4', 'type_name': '动漫'},
            ],
            'list': [],
        }
        if filter:
            res['filters'] = self._filters()
        return res

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        """分类列表: 源站无可用数据, 返回空分页. TVBox 显示"暂无数据"."""
        page = int(pg) if pg else 1
        return {
            'list': [],
            'page': page,
            'pagecount': 0,
            'limit': 24,
            'total': 0,
        }

    def detailContent(self, ids):
        """详情: 源站无可用数据, 返回空. 不会让 TVBox 报错."""
        return {'list': []}

    def searchContent(self, key, quick, pg="1"):
        """搜索: 源站无可用数据, 返回空."""
        page = int(pg) if pg else 1
        return {'list': [], 'page': page}

    def playerContent(self, flag, id, vipFlags):
        """播放: 没有真实 m3u8 源, parse=1 走 TVBox 自带嗅探, 不会崩."""
        return {
            'parse': 1,
            'url': id if id else '',
            'header': {'User-Agent': self.UA, 'Referer': 'https://www.nkdb.cc/'},
        }

    # ============================================================
    # 筛选 (全部本地硬编码, 零网络)
    # ============================================================

    def _filters(self):
        out = {}
        for tid in ('1', '2', '3', '4'):
            groups = []
            # 排序
            groups.append({
                'key': 'by', 'name': '排序',
                'value': [{'n': '最新', 'v': 'time'}, {'n': '最热', 'v': 'hits'}, {'n': '评分', 'v': 'score'}],
            })
            # 类型
            types = self.FILTER_TYPES_BY_CAT.get(tid) or []
            if len(types) > 1:
                groups.append({
                    'key': 'class', 'name': '类型',
                    'value': [{'n': t, 'v': t} for t in types],
                })
            # 地区
            areas = self.FILTER_TYPES_BY_CAT.get(tid + '_areas') or []
            if len(areas) > 1:
                groups.append({
                    'key': 'area', 'name': '地区',
                    'value': [{'n': a, 'v': a} for a in areas],
                })
            # 年份
            groups.append({
                'key': 'year', 'name': '年份',
                'value': [{'n': y, 'v': y} for y in self.YEAR_LIST],
            })
            out[tid] = groups
        return out
