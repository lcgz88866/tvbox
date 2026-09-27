import sys
import urllib.parse
import re
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "两个BT影视"

    def init(self, extend=""):
        self.host = 'https://www.bttwo.life'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Referer': self.host
        }
        # 预加载筛选ID映射
        self._filter_ids = None

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def _load_filter_ids(self):
        """加载筛选ID映射"""
        if self._filter_ids is not None:
            return
            
        print("[两个BT] 加载筛选ID映射...")
        
        # 默认映射（兜底）
        self._filter_ids = {
            'areas': {
                '全部': '', '美国': '5', '日本': '11', '韩国': '12', '中国大陆': '52',
                '中国香港': '14', '中国台湾': '21', '法国': '6', '英国': '30', '加拿大': '32',
                '德国': '18', '意大利': '19', '西班牙': '24', '俄罗斯': '16', '印度': '34',
                '澳大利亚': '22', '泰国': '33', '其他': '78'
            },
            'types': {
                '全部': '', '剧情': '1', '悬疑': '2', '恐怖': '3', '惊悚': '4',
                '喜剧': '5', '爱情': '6', '犯罪': '9', '动作': '10', '动画': '11',
                '奇幻': '12', '科幻': '14', '历史': '15', '战争': '16', '冒险': '18',
                '家庭': '19', '纪录': '20', '传记': '28', '运动': '30', '武侠': '31'
            },
            'years': {
                '全部': '', '2026': '1', '2025': '3', '2024': '4', '2023': '56',
                '2022': '13', '2021': '2', '2020': '6', '2019': '8', '2018': '9',
                '2010-2014': '11', '2000-2009': '12', '1990-1999': '13', '1980-1989': '14',
                '1970-1979': '15', '1960-1969': '16', '1950-1959': '17', '1940-1949': '18',
                '1930-1939': '19', '1920-1929': '20'
            }
        }
        
        # 尝试从网站动态获取（可选）
        try:
            html = self.fetch(f'{self.host}/filter?classify=3', headers=self.headers).text
            
            # 提取地区ID
            area_matches = re.findall(r'href="\?classify=\d+&amp;areas=(\d+)"[^>]*>([^<]+)</a>', html)
            for vid, vn in area_matches:
                name = vn.strip()
                if name.lower() == 'unknown':
                    name = '其他'
                self._filter_ids['areas'][name] = vid
                
            # 提取类型ID
            type_matches = re.findall(r'href="\?classify=\d+&amp;(?:areas=\d+&amp;)?types=(\d+)"[^>]*>([^<]+)</a>', html)
            for vid, vn in type_matches:
                name = vn.strip()
                self._filter_ids['types'][name] = vid
                
            # 提取年份ID
            year_matches = re.findall(r'href="\?classify=\d+&amp;(?:areas=\d+&amp;)?years=(\d+)"[^>]*>([^<]+)</a>', html)
            for vid, vn in year_matches:
                name = vn.strip()
                self._filter_ids['years'][name] = vid
                
            print(f"[两个BT] 筛选ID加载完成: 地区{len(self._filter_ids['areas'])}, 类型{len(self._filter_ids['types'])}, 年份{len(self._filter_ids['years'])}")
        except Exception as e:
            print(f"[两个BT] 动态加载筛选ID失败，使用默认映射: {e}")

    def homeContent(self, filter):
        self._load_filter_ids()
        result = {}
        result['class'] = [
            {'type_id': '1', 'type_name': '电影'},
            {'type_id': '2', 'type_name': '电视剧'},
            {'type_id': '3', 'type_name': '动漫'}
        ]
        result['filters'] = self._get_filters()
        return result

    def homeVideoContent(self):
        try:
            rsp = self.fetch(self.host, headers=self.headers)
            return {'list': self._parse_videos_from_html(rsp.text)[:30]}
        except Exception as e:
            print(f'homeVideoContent 错误: {e}')
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            self._load_filter_ids()
            
            # 构建筛选参数（将中文转换为数字ID）
            params = []
            
            # classify参数：1=电影, 2=电视剧, 3=动漫
            classify_map = {'1': '1', '2': '2', '3': '3'}
            classify = classify_map.get(tid, '1')
            params.append(f"classify={classify}")
            
            # 地区筛选
            if extend.get('area'):
                area_name = extend['area']
                area_id = self._filter_ids['areas'].get(area_name, '')
                if area_id:
                    params.append(f"areas={area_id}")
            
            # 类型筛选
            if extend.get('type'):
                type_name = extend['type']
                type_id = self._filter_ids['types'].get(type_name, '')
                if type_id:
                    params.append(f"types={type_id}")
            
            # 年份筛选
            if extend.get('year'):
                year_name = extend['year']
                year_id = self._filter_ids['years'].get(year_name, '')
                if year_id:
                    params.append(f"years={year_id}")
            
            # 分页参数
            if str(pg) != '1':
                params.append(f"page={pg}")
            
            # 构建URL
            url = f"{self.host}/filter"
            if params:
                url += "?" + "&".join(params)
            
            print(f'[两个BT] 分类请求: {url}')
            
            rsp = self.fetch(url, headers=self.headers)
            return {
                'list': self._parse_videos_from_html(rsp.text),
                'page': int(pg),
                'pagecount': 9999,
                'limit': 20
            }
        except Exception as e:
            print(f'categoryContent 错误: {e}')
            return {'list': []}

    def detailContent(self, ids):
        try:
            vid = ids[0]
            detail_url = f"{self.host}{vid}" if str(vid).startswith('/') else f"{self.host}/play/{vid}"
            
            rsp = self.fetch(detail_url, headers=self.headers)
            doc = self.html(rsp.text)
            
            # 修复标题提取逻辑 - 按优先级尝试不同的选择器
            title = "未知"
            
            # 1. 首先尝试h1标题（最常见）
            title_nodes = doc.xpath('//h1[contains(@class,"text-lg")]/text()')
            if title_nodes and title_nodes[0].strip():
                title = title_nodes[0].strip()
            else:
                # 2. 尝试h2标题
                title_nodes = doc.xpath('//h2[contains(@class,"text-xl")]/text()')
                if title_nodes and title_nodes[0].strip():
                    title = title_nodes[0].strip()
                else:
                    # 3. 尝试title标签
                    title_nodes = doc.xpath('//title/text()')
                    if title_nodes and title_nodes[0].strip():
                        title = title_nodes[0].strip()
                        # 清理title中的网站后缀
                        title = re.sub(r'\s*-\s*两个BT.*$', '', title)
                        title = re.sub(r'\s*\|\s*两个BT.*$', '', title)
                    else:
                        # 4. 尝试meta标签
                        meta_nodes = doc.xpath('//meta[@property="og:title"]/@content')
                        if meta_nodes and meta_nodes[0].strip():
                            title = meta_nodes[0].strip()
            
            # 最终清理标题
            title = title.strip()
            # 移除多余的空格和特殊字符
            title = re.sub(r'\s+', ' ', title)
            # 移除常见的网站后缀
            title = re.sub(r'\s*-\s*两个BT.*$', '', title)
            title = re.sub(r'\s*\|\s*两个BT.*$', '', title)
            title = re.sub(r'\s*-\s*TwoBT.*$', '', title)
            title = re.sub(r'\s*\|\s*TwoBT.*$', '', title)
            
            print(f'[两个BT] 提取标题: {title}')
            
            img_nodes = doc.xpath('//div[contains(@class,"movie-poster")]//img/@src | //div[contains(@class,"movie-poster")]//img/@data-src | //meta[@property="og:image"]/@content')
            pic = ""
            for img in img_nodes:
                if "placeholder" not in img.lower():
                    pic = img
                    break
            if not pic and img_nodes:
                pic = img_nodes[0]
                
            remarks_nodes = doc.xpath('//span[contains(text(),"共") and contains(text(),"集")]/text()')
            remarks = remarks_nodes[0].strip() if remarks_nodes else ""
            
            director_nodes = doc.xpath('//div[text()="导演"]/following-sibling::div[1]/text()')
            director = director_nodes[0].strip() if director_nodes else ""
            
            actor_nodes = doc.xpath('//div[text()="主演"]/following-sibling::div[1]/text()')
            actor = actor_nodes[0].strip() if actor_nodes else ""
            
            # 剧情简介: <h3>剧情简介</h3> 后跟 <p class="text-xs text-gray-300...">内容</p>
            # 使用正则更可靠 (h3和p是兄弟节点, xpath parent::div 可能不稳定)
            html_text = rsp.text
            content = ""
            plot_m = re.search(r'剧情简介.*?<p[^>]*>(.*?)</p>', html_text, re.DOTALL)
            if plot_m:
                content = re.sub(r'<[^>]+>', '', plot_m.group(1)).strip()
                content = re.sub(r'\s+', ' ', content)
            
            # 选集: <a href="/play/xxx" ... class="episode-link" ... data-episode="N" ...>
            # 选集链接特征: 有 data-episode 属性, 有 episode-link class
            # 注意: 不要用core_id过滤, 因为各集URL路径不同 (如 ch4elboyk / ch4elboz0)
            episodes = []
            seen_hrefs = set()
            
            # 策略1: 精确匹配有 data-episode 属性的选集链接
            ep_matches = re.findall(
                r'<a[^>]*href="(/play/[^"]+)"[^>]*data-line="(\d+)"[^>]*data-episode="(\d+)"[^>]*>(.*?)</a>',
                html_text, re.DOTALL
            )
            
            for href, line_num, ep_num, inner_html in ep_matches:
                if href in seen_hrefs:
                    continue
                seen_hrefs.add(href)
                
                # 从内部HTML提取集名 (在<span>标签内, 通常是数字或"正片")
                name_m = re.search(r'<span[^>]*>(.*?)</span>', inner_html, re.DOTALL)
                if name_m:
                    name = re.sub(r'<[^>]+>', '', name_m.group(1)).strip()
                else:
                    name = re.sub(r'<[^>]+>', '', inner_html).strip()
                
                if not name:
                    name = f"第{ep_num}集"
                elif name.isdigit():
                    name = f"第{int(name):02d}集"
                
                episodes.append(f"{name}${href}")
            
            # 策略2: 如果策略1无结果, 尝试更宽松的匹配 (只匹配 episode-link class)
            if not episodes:
                ep_matches2 = re.findall(
                    r'<a[^>]*href="(/play/[^"]+)"[^>]*class="[^"]*episode-link[^"]*"[^>]*>(.*?)</a>',
                    html_text, re.DOTALL
                )
                for href, inner_html in ep_matches2:
                    if href in seen_hrefs:
                        continue
                    seen_hrefs.add(href)
                    name_m = re.search(r'<span[^>]*>(.*?)</span>', inner_html, re.DOTALL)
                    if name_m:
                        name = re.sub(r'<[^>]+>', '', name_m.group(1)).strip()
                    else:
                        name = re.sub(r'<[^>]+>', '', inner_html).strip()
                    if not name:
                        name = f"第{len(episodes)+1}集"
                    episodes.append(f"{name}${href}")
            
            # 提取线路信息 (episodeManager 中的 lineName)
            line_names = re.findall(r'lineName:\s*[\'"]([^\'"]+)[\'"]', html_text)
            if line_names and len(line_names) > 1:
                # 多线路: 按线路分组 (目前网站通常只有1条线路"alists")
                play_from = "$$$".join(line_names)
            else:
                play_from = '两个BT'
            
            return {
                'list': [{
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remarks,
                    'vod_director': director,
                    'vod_actor': actor,
                    'vod_content': content,
                    'vod_play_from': play_from,
                    'vod_play_url': '#'.join(episodes) if episodes else f"正片${vid}"
                }]
            }
        except Exception as e:
            print(f'detailContent 错误: {e}')
            return {'list': []}

    def searchContent(self, key, quick, pg="1"):
        try:
            url = f"{self.host}/search?q={urllib.parse.quote(key)}"
            if pg != "1":
                url += f"&page={pg}"
            rsp = self.fetch(url, headers=self.headers)
            return {
                'list': self._parse_search_from_html(rsp.text),
                'page': int(pg),
                'pagecount': 9999,
                'limit': 20
            }
        except Exception as e:
            print(f'searchContent 错误: {e}')
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        # WASM 播放器直连
        play_url = id if id.startswith('http') else self.host + id
        return {'parse': 1, 'url': play_url, 'header': self.headers}

    def localProxy(self, param):
        return [200, "video/MP2T", ""]

    def _parse_videos_from_html(self, html_text):
        """用正则从HTML中提取视频列表(不依赖xpath,兼容性更好)"""
        videos = []
        seen_ids = set()
        # 匹配每个 movie-card 区块: <div ... data-vod-id="xxx" ...> ... </div>(到下一个data-vod-id或section结尾)
        cards = re.findall(
            r'<div[^>]*data-vod-id="([^"]+)"[^>]*>(.*?)(?=<div[^>]*data-vod-id="|</section>|<section)',
            html_text, re.DOTALL
        )
        for vid, card_html in cards:
            v_id = f"/play/{vid}"
            if v_id in seen_ids:
                continue
            seen_ids.add(v_id)

            # 标题: h3 > a[title] > img[alt]
            name = "未知"
            m = re.search(r'<h3[^>]*>([^<]+)</h3>', card_html)
            if m:
                name = m.group(1).strip()
            else:
                m = re.search(r'<a[^>]*title="([^"]+)"', card_html)
                if m:
                    name = m.group(1).strip()
                else:
                    m = re.search(r'<img[^>]*alt="([^"]+)"', card_html)
                    if m:
                        name = m.group(1).strip()
            name = re.sub(r'\s+', ' ', name).strip()

            # 图片: data-src(跳过placeholder) > src(跳过placeholder)
            v_pic = ""
            imgs = re.findall(r'(?:data-src|data-original|src)="([^"]+)"', card_html)
            for img in imgs:
                if 'placeholder' not in img.lower():
                    v_pic = img
                    break
            if not v_pic and imgs:
                v_pic = imgs[0]
            # 反转义HTML实体
            v_pic = v_pic.replace('&amp;', '&')

            # 备注: bg-gradient-to-t 的 span (集数信息)
            v_remarks = ""
            m = re.search(r'<span[^>]*class="[^"]*bg-gradient-to-t[^"]*"[^>]*>([^<]+)</span>', card_html)
            if m:
                v_remarks = m.group(1).strip()

            videos.append({
                'vod_id': v_id,
                'vod_name': name,
                'vod_pic': v_pic,
                'vod_remarks': v_remarks
            })
        return videos

    def _parse_search_from_html(self, html_text):
        """解析搜索结果页（结构为 <div class="group relative"> 卡片，无 data-vod-id）"""
        videos = []
        seen = set()
        # 按卡片起始位置切分，确保所有结果块都被捕获（最后一个块可能不以 </section> 结尾）
        starts = [m.start() for m in re.finditer(r'<div class="group relative"[^>]*>', html_text)]
        if not starts:
            return videos
        blocks = [html_text[starts[i]:starts[i + 1]] for i in range(len(starts) - 1)]
        blocks.append(html_text[starts[-1]:])
        for b in blocks:
            m = re.search(r'href="(/play/[^"]+)"', b)
            if not m:
                continue
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)

            # 标题: <h3> 优先，其次 img alt
            name = ''
            nm = re.search(r'<h3[^>]*>\s*(.*?)\s*</h3>', b, re.S)
            if nm:
                name = re.sub(r'<[^>]+>', '', nm.group(1)).strip()
            if not name:
                nm = re.search(r'<img[^>]*alt="([^"]+)"', b)
                if nm:
                    name = nm.group(1).strip()
            name = re.sub(r'\s+', ' ', name).strip()

            # 图片: data-src 优先(跳过 placeholder)，其次 data-original/src
            pic = ''
            for attr in ('data-src', 'data-original', 'src'):
                im = re.search(r'<img[^>]*%s="([^"]+)"' % attr, b)
                if im:
                    val = im.group(1).strip()
                    if 'placeholder' not in val.lower():
                        pic = val
                        break
            if not pic:
                im = re.search(r'<img[^>]*src="([^"]+)"', b)
                if im:
                    pic = im.group(1).strip()
            pic = pic.replace('&amp;', '&')

            # 备注: 年份徽标（搜索卡片无集数信息）
            remarks = ''
            ym = re.search(r'absolute top-2 left-2[^>]*>\s*([^<]+?)\s*<', b)
            if ym:
                remarks = ym.group(1).strip()

            videos.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': remarks
            })
        return videos

    def _get_filters(self):
        """生成筛选器配置（使用中文名称，但实际会使用数字ID）"""
        # 从映射中提取选项
        areas = [{'n': k, 'v': k} for k in self._filter_ids['areas'].keys()]
        types = [{'n': k, 'v': k} for k in self._filter_ids['types'].keys()]
        years = [{'n': k, 'v': k} for k in self._filter_ids['years'].keys()]

        # 排序：全部放在第一位，其余按名称排序
        areas.sort(key=lambda x: (x['v'] != '', x['n']))
        types.sort(key=lambda x: (x['v'] != '', x['n']))

        # 年份按降序排列（最新年份在前）
        def year_sort_key(item):
            if item['v'] == '':
                return (-1, 0)  # "全部"排第一
            # 提取年份起始数字用于排序
            m = re.match(r'(\d+)', item['n'])
            start_year = int(m.group(1)) if m else 0
            return (0, -start_year)  # 降序：年份越大越靠前
        years.sort(key=year_sort_key)
        
        base = [
            {'key': 'area', 'name': '地区', 'value': areas},
            {'key': 'type', 'name': '类型', 'value': types},
            {'key': 'year', 'name': '年份', 'value': years}
        ]
        return {'1': base, '2': base, '3': base}