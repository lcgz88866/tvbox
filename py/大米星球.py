# -*- coding: utf-8 -*-
# 大米星球爬虫
# 更新: 2026-08-09 - 修复筛选功能 + 详情页演员/导演等元数据提取
import re
import sys
import html
from urllib.parse import quote
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    HOST = 'https://dmxq40.com'
    UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'

    # ==================== 分类配置 ====================
    CATEGORIES = [
        {'type_name': 'Netflix', 'type_id': 'netflix'},
        {'type_name': '电影', 'type_id': '20'},
        {'type_name': '电视剧', 'type_id': '21'},
        {'type_name': '短剧', 'type_id': '36'},
        {'type_name': '动漫', 'type_id': '22'},
        {'type_name': '综艺', 'type_id': '23'},
    ]

    # 地区选项
    AREA_FULL = ['大陆', '香港', '台湾', '美国', '日本', '韩国', '英国', '法国', '德国',
                 '印度', '泰国', '丹麦', '瑞典', '巴西', '加拿大', '俄罗斯', '意大利',
                 '比利时', '爱尔兰', '西班牙', '澳大利亚']
    AREA_DRAMA = ['大陆', '香港', '韩国', '美国', '日本', '法国', '英国', '德国',
                  '台湾', '泰国', '印度', '其他']
    AREA_ANIME = ['大陆', '日本', '欧美', '其他']
    AREA_VARIETY = ['大陆', '韩国', '香港', '台湾', '美国', '其它']

    AREA_MAP = {
        '20': AREA_FULL,
        '21': AREA_FULL,
        '36': AREA_DRAMA,
        '22': AREA_ANIME,
        '23': AREA_VARIETY,
    }

    # 类型选项
    CLASS_MAP = {
        '20': ['Netflix', '仙侠', '剧情', '科幻', '动作', '喜剧', '爱情', '冒险', '儿童',
               '歌舞', '音乐', '奇幻', '动画', '恐怖', '惊悚', '丧尸', '战争', '传记',
               '纪录', '犯罪', '悬疑', '西部', '灾难', '古装', '武侠', '家庭', '短片',
               '校园', '文艺', '运动', '青春', '同性', '励志', '人性', '美食', '女性',
               '治愈', '历史', '真人秀', '脱口秀'],
        '21': ['Netflix', '短剧', '剧情', '网剧', '丧尸', '仙侠', '穿越', '惊悚', '恐怖',
               '言情', '科幻', '动作', '喜剧', '爱情', '偶像', '都市', '军旅', '谍战',
               '罪案', '宫廷', '冒险', '儿童', '歌舞', '音乐', '奇幻', '动画', '战争',
               '传记', '记录', '犯罪', '悬疑', '西部', '灾难', '古装', '武侠', '家庭',
               '短片', '校园', '文艺', '运动', '青春', '同性', '励志', '人性', '美食',
               '女性', '治愈', '历史', '真人秀', '脱口秀'],
        '36': ['古代', '现代', '穿越', '玄幻', '霸总', '英雄救美', '未婚妻', '师姐',
               '绝美', '逆袭', '幻想', '美女', '爱情', '甜宠', '虐恋', '爽剧', '搞笑',
               '情感', '动漫', '萌宝', '抖音', '快手', '都市', '言情', '重生', '乡村', '神医'],
        '22': ['Netflix', '热血', '科幻', '美少女', '魔幻', '经典', '励志', '少儿', '冒险',
               '搞笑', '推理', '恋爱', '治愈', '幻想', '校园', '动物', '机战', '亲子',
               '儿歌', '运动', '悬疑', '怪物', '战争', '益智', '青春', '童话', '竞技',
               '动作', '社会', '友情', '真人版', '电影版', 'OVA版', 'TV版', '新番动画', '完结动画'],
        '23': ['Netflix', '脱口秀', '真人秀', '选秀', '八卦', '访谈', '情感', '生活',
               '晚会', '搞笑', '音乐', '时尚', '游戏', '少儿', '体育', '纪实', '科教',
               '曲艺', '歌舞', '财经', '汽车', '播报', '其他'],
    }

    # 语言选项
    LANG_FULL = ['英语', '法语', '国语', '粤语', '日语', '韩语', '泰语', '德语', '俄语',
                 '闽南语', '丹麦语', '波兰语', '瑞典语', '印地语', '挪威语', '意大利语', '西班牙语']
    LANG_SIMPLE = ['国语', '英语', '粤语', '闽南语', '韩语', '日语', '其它']

    LANG_MAP = {
        '20': LANG_FULL,
        '21': LANG_FULL,
        '36': LANG_SIMPLE,
        '22': LANG_SIMPLE,
        '23': LANG_SIMPLE,
    }

    # 年份选项
    YEAR_FULL = [str(y) for y in range(2026, 1999, -1)] + ['90年代', '80年代', '70年代', '更早']
    YEAR_DRAMA = ['2026', '2025', '2023', '2022', '2021', '2020', '10年代', '00年代', '90年代', '80年代', '更早']

    YEAR_MAP = {
        '20': YEAR_FULL,
        '21': YEAR_FULL,
        '36': YEAR_DRAMA,
        '22': YEAR_FULL,
        '23': YEAR_FULL,
    }

    # 排序选项
    SORT_VALUES = [
        {'n': '时间排序', 'v': 'time'},
        {'n': '人气排序', 'v': 'hits'},
        {'n': '评分排序', 'v': 'score'},
    ]

    def init(self, extend=""):
        self.host = self.HOST
        self.headers = {
            'User-Agent': self.UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
            'Referer': self.host + '/',
        }

    def getName(self):
        return '大米星球'

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    # ==================== 筛选配置 ====================
    def _build_filters(self):
        """构建各分类的筛选器配置"""
        filters = {}
        for cat in self.CATEGORIES:
            cat_id = cat['type_id']
            if cat_id == 'netflix':
                continue  # Netflix没有筛选

            cat_filters = []

            # 类型
            class_values = [{'n': '不限', 'v': ''}]
            for c in self.CLASS_MAP.get(cat_id, []):
                class_values.append({'n': c, 'v': c})
            if len(class_values) > 1:
                cat_filters.append({'key': 'class', 'name': '类型', 'value': class_values})

            # 地区
            area_values = [{'n': '不限', 'v': ''}]
            for a in self.AREA_MAP.get(cat_id, []):
                area_values.append({'n': a, 'v': a})
            if len(area_values) > 1:
                cat_filters.append({'key': 'area', 'name': '地区', 'value': area_values})

            # 语言
            lang_values = [{'n': '不限', 'v': ''}]
            for l in self.LANG_MAP.get(cat_id, []):
                lang_values.append({'n': l, 'v': l})
            if len(lang_values) > 1:
                cat_filters.append({'key': 'lang', 'name': '语言', 'value': lang_values})

            # 年份
            year_values = [{'n': '不限', 'v': ''}]
            for y in self.YEAR_MAP.get(cat_id, []):
                year_values.append({'n': y, 'v': y})
            cat_filters.append({'key': 'year', 'name': '年份', 'value': year_values})

            # 排序
            cat_filters.append({'key': 'sort', 'name': '排序', 'value': self.SORT_VALUES})

            filters[cat_id] = cat_filters
        return filters

    def homeContent(self, filter):
        result = {
            'class': self.CATEGORIES,
            'filters': self._build_filters() if filter else {},
            'list': []
        }
        try:
            html_text = self.fetch(self.host + '/index/home.html', headers=self.headers).text
            result['list'] = self.get_vod_list(html_text)
        except Exception as e:
            print(f'homeContent 错误: {e}')
        return result

    def homeVideoContent(self):
        try:
            html_text = self.fetch(self.host + '/index/home.html', headers=self.headers).text
            return self.get_vod_list(html_text)
        except:
            return []

    def categoryContent(self, tid, pg, filter, extend):
        result = {
            'list': [],
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999
        }
        try:
            page = int(pg) if pg else 1
            extend = extend or {}

            if tid == 'netflix':
                # Netflix: 无筛选, 使用label页
                # 分页格式: /label/netflix.html (第1页), /label/netflix/page/N.html (第2页+)
                if page <= 1:
                    url = f'{self.host}/label/netflix.html'
                else:
                    url = f'{self.host}/label/netflix/page/{page}.html'
            else:
                # 其他分类: 使用vodshow页支持筛选
                # URL格式: /vodshow/{cid}-{area}-{sort}-{class}-{lang}-{empty}-{empty}-{empty}-{page}-{empty}-{empty}-{year}.html
                # 12段(索引0-11): 0:cid 1:area 2:sort 3:class 4:lang 5-7:空 8:page 9-10:空 11:year
                area = extend.get('area', '')
                sort = extend.get('sort', '')
                cls = extend.get('class', '')
                lang = extend.get('lang', '')
                year = extend.get('year', '')

                # URL编码中文值
                area_q = quote(area, safe='') if area else ''
                sort_q = sort if sort else ''
                cls_q = quote(cls, safe='') if cls else ''
                lang_q = quote(lang, safe='') if lang else ''
                year_q = quote(year, safe='') if year else ''

                # 构建12段URL (11个dash分隔)
                segments = [str(tid), area_q, sort_q, cls_q, lang_q, '', '', '', str(page), '', '', year_q]
                url = f'{self.host}/vodshow/' + '-'.join(segments) + '.html'

            html_text = self.fetch(url, headers=self.headers).text
            result['list'] = self.get_vod_list(html_text)

            # 提取总页数
            pagecount = self._extract_pagecount(html_text, tid)
            if pagecount > 0:
                result['pagecount'] = pagecount
        except Exception as e:
            print(f'categoryContent 错误: {e}')
        return result

    def _extract_pagecount(self, html_text, tid):
        """从分页链接中提取总页数"""
        try:
            if tid == 'netflix':
                pages = re.findall(r'/label/netflix/page/(\d+)\.html', html_text)
            else:
                # 从vodshow分页链接中提取页码(position 8)
                page_links = re.findall(r'/vodshow/\d+-[^"]*\.html', html_text)
                pages = []
                for link in page_links:
                    segments = link.replace('/vodshow/', '').replace('.html', '').split('-')
                    while len(segments) < 12:
                        segments.append('')
                    if segments[8] and segments[8].isdigit():
                        pages.append(int(segments[8]))
            if pages:
                return max(pages)
        except:
            pass
        return 0

    def detailContent(self, ids):
        result = {'list': []}
        try:
            url = ids[0] if ids[0].startswith('http') else self.host + ids[0]
            html_text = self.fetch(url, headers=self.headers).text

            vod = {}

            # 标题
            m = re.search(r'<h1[^>]*>([^<]+)</h1>', html_text)
            if m:
                vod['vod_name'] = m.group(1).strip()

            # 海报
            m = re.search(r'data-original="([^"]+)"[^>]*alt="([^"]+)"[^>]*class="module-item-pic"', html_text)
            if not m:
                m = re.search(r'<div class="module-item-pic"[^>]*>.*?<img[^>]+data-original="([^"]+)"', html_text, re.DOTALL)
            if m:
                pic = html.unescape(m.group(1))
                vod['vod_pic'] = pic

            # ====== 元数据提取 ======
            # 从 module-info-tag 提取年份、地区、类型
            tag_links = re.findall(r'module-info-tag-link[^>]*>(.*?)</div>', html_text, re.S)
            if len(tag_links) >= 1:
                year_m = re.search(r'<a[^>]*>([^<]+)</a>', tag_links[0])
                if year_m:
                    vod['vod_year'] = year_m.group(1).strip()
            if len(tag_links) >= 2:
                area_m = re.search(r'<a[^>]*>([^<]+)</a>', tag_links[1])
                if area_m:
                    vod['vod_area'] = area_m.group(1).strip()
            if len(tag_links) >= 3:
                types = re.findall(r'<a[^>]*>([^<]+)</a>', tag_links[2])
                if types:
                    vod['vod_type'] = ' / '.join(t.strip() for t in types)

            # 从 module-info-item 提取导演、主演、备注等
            vod['vod_director'] = self._extract_info_field(html_text, '导演')
            vod['vod_actor'] = self._extract_info_field(html_text, '主演')
            vod['vod_remarks'] = self._extract_info_field(html_text, '备注')
            vod['vod_score'] = self._extract_info_field(html_text, '豆瓣')

            # 从 module-info-item 提取更新时间
            update_text = self._extract_info_field(html_text, '更新')
            if update_text:
                vod['vod_pubdate'] = update_text

            # 简介
            m = re.search(r'<div class="module-info-introduction-content[^"]*"[^>]*>(.*?)</div>', html_text, re.DOTALL)
            if m:
                desc = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                desc = re.sub(r'\s+', ' ', desc)
                vod['vod_content'] = desc[:500] if desc else ''

            # 播放链接
            all_eps = re.findall(r'href="(/vodplay/\d+-(\d+)-(\d+)\.html)"[^>]*><span>([^<]+)</span>', html_text)

            if all_eps:
                source_dict = {}
                for href, source_id, episode, ep_name in all_eps:
                    source_id = str(source_id)
                    if source_id not in source_dict:
                        source_dict[source_id] = []
                    full_url = self.host + href
                    source_dict[source_id].append(f"{ep_name}${full_url}")

                source_names = re.findall(r'data-dropdown-value="([^"]+)"', html_text)

                play_from_list = []
                play_url_list = []
                for i, (sid, episodes) in enumerate(source_dict.items()):
                    if i < len(source_names):
                        name = source_names[i]
                    else:
                        name = f'线路{i+1}'

                    def get_ep_num(x):
                        match = re.search(r'(\d+)', x.split('$')[0])
                        return int(match.group(1)) if match else 0
                    episodes_sorted = sorted(episodes, key=get_ep_num)

                    play_from_list.append(name)
                    play_url_list.append('#'.join(episodes_sorted))

                vod['vod_play_from'] = '$$$'.join(play_from_list)
                vod['vod_play_url'] = '$$$'.join(play_url_list)
            else:
                vod['vod_play_from'] = '大米星球'
                vod['vod_play_url'] = ''

            result['list'].append(vod)
        except Exception as e:
            print(f'detailContent 错误: {e}')
            import traceback
            traceback.print_exc()
        return result

    def _extract_info_field(self, html_text, label):
        """从 module-info-item 中按标签提取元数据 (导演/主演/备注/豆瓣/更新等)

        HTML结构:
        <div class="module-info-item">
          <span class="module-info-item-title">导演：</span>
          <div class="module-info-item-content">
            <a href="...">李公乐</a><span class="slash">/</span>
          </div>
        </div>
        """
        # 方式1: 标准结构 - span标题 + div内容
        pattern = r'%s[：:]\s*</span>\s*<div class="module-info-item-content"[^>]*>(.*?)</div>' % re.escape(label)
        m = re.search(pattern, html_text, re.S)
        if m:
            content = m.group(1)
            # 提取所有<a>标签文本
            values = re.findall(r'<a[^>]*>([^<]+)</a>', content)
            if values:
                return ' / '.join(v.strip() for v in values)
            # 无<a>标签时取纯文本
            text = re.sub(r'<[^>]+>', '', content).strip()
            return text if text else ''

        # 方式2: 备用 - 标签后直接跟文本
        pattern2 = r'%s[：:]\s*([^<\n]+)' % re.escape(label)
        m2 = re.search(pattern2, html_text)
        if m2:
            val = m2.group(1).strip()
            # 过滤掉slash分隔符
            val = re.sub(r'\s*/\s*', ' / ', val).strip(' /')
            return val if val else ''

        return ''

    def searchContent(self, key, quick, pg="1"):
        result = {
            'list': [],
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999
        }
        try:
            if int(pg) == 1:
                url = f'{self.host}/vodsearch/{quote(key)}-------------.html'
            else:
                url = f'{self.host}/vodsearch/{quote(key)}-------------.html?page={pg}'

            html_text = self.fetch(url, headers=self.headers).text
            result['list'] = self.get_search_list(html_text)
        except Exception as e:
            print(f'searchContent 错误: {e}')
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {'parse': 0, 'url': '', 'header': {}}
        try:
            play_url = id if id.startswith('http') else self.host + id
            result['url'] = play_url
            result['parse'] = 1
            result['header'] = {'Referer': self.host + '/'}
        except Exception as e:
            print(f'playerContent 错误: {e}')
        return result

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    def get_vod_list(self, html_text):
        """通用列表提取 - 分类页/首页"""
        videos = []
        seen = set()

        # 提取所有链接
        hrefs = re.findall(r'href="(/voddetail/\d+\.html)"', html_text)

        # 提取所有图片
        pics = re.findall(r'data-original="([^"]+)"', html_text)
        pics = [html.unescape(p) for p in pics]

        # 提取所有标题
        titles = re.findall(r'module-poster-item-title[^>]*>([^<]+)<', html_text)

        # 提取副标题（备注）
        notes = re.findall(r'class="module-item-note"[^>]*>([^<]+)<', html_text)

        min_len = min(len(hrefs), len(pics), len(titles))
        for i in range(min_len):
            href = hrefs[i]
            pic = pics[i]
            title = titles[i].strip()
            remark = notes[i].strip() if i < len(notes) else ''

            m = re.search(r'/voddetail/(\d+)\.html', href)
            if not m:
                continue
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)

            full_url = self.host + href
            if title:
                videos.append({
                    'vod_id': full_url,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remark
                })

        return videos

    def get_search_list(self, html_text):
        """搜索结果页提取"""
        videos = []
        seen = set()

        # 分割成单个卡片
        cards = re.split(r'(?=<div class="module-card-item module-item">)', html_text)

        for card in cards:
            if '<div class="module-card-item' not in card:
                continue

            # 提取详情链接
            detail_links = re.findall(r'href="(/voddetail/\d+\.html)"[^>]+class="[^"]*module-card-item-poster"', card)
            if not detail_links:
                detail_links = re.findall(r'<a href="(/voddetail/\d+\.html)" class="module-card-item-poster"', card)

            if not detail_links:
                continue
            href = detail_links[0]

            # 提取图片
            pics = re.findall(r'data-original="([^"]+)"', card)
            pic = html.unescape(pics[0]) if pics else ''

            # 提取标题 - 从strong标签，并清理<em>标签
            titles = re.findall(r'<strong>(.*?)</strong>', card, re.DOTALL)
            if titles:
                title = re.sub(r'<[^>]+>', '', titles[0]).strip()
            else:
                title = ''

            # 提取副标题
            notes = re.findall(r'class="module-item-note"[^>]*>([^<]+)<', card)
            remark = notes[0].strip() if notes else ''

            # 提取分类
            classes = re.findall(r'class="module-card-item-class"[^>]*>([^<]+)<', card)
            cat = classes[0].strip() if classes else ''

            # 如果备注为空，用分类代替
            if not remark and cat:
                remark = cat

            # 提取ID
            m = re.search(r'/voddetail/(\d+)\.html', href)
            if not m:
                continue
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)

            full_url = self.host + href
            if title:
                videos.append({
                    'vod_id': full_url,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remark
                })

        return videos