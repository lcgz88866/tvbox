#coding=utf-8
# GD音乐台 (music.gdstudio.org) - 全网音乐聚合平台
# 需要Playwright绕过Cloudflare防护
# 功能: 搜索、播放、歌词
# 音源: 网易云/QQ/酷我/Tidal/Qobuz/Apple/Spotify等
# 安装依赖: pip install playwright && python3 -m playwright install chromium && python3 -m playwright install-deps chromium
import sys
import os
import json
import time
import threading

# 尝试导入Playwright，没有则提示安装
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_OK = True
except ImportError:
    PLAYWRIGHT_OK = False


class Spider:
    pass

class GDMusicSpider(Spider):

    def getName(self):
        return "GD音乐台"

    def init(self, extend=""):
        self.base_url = "https://music.gdstudio.org"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        
        # 浏览器实例管理（线程安全）
        self._lock = threading.Lock()
        self._playwright = None
        self._browser = None
        self._page = None
        self._last_use = 0
        self._idle_timeout = 120  # 闲置2分钟后关闭浏览器
        
        # 音源列表（网站支持的音源）
        self.sources = [
            ("netease", "网易云", "✔️"),
            ("tencent", "QQ音乐", "✔️"),
            ("kuwo", "酷我", "✔️"),
            ("migu", "咪咕", "✔️"),
            ("tidal", "Tidal", "✔️"),
            ("qobuz", "Qobuz", "✔️"),
            ("apple", "Apple", "✔️"),
            ("spotify", "Spotify", "✔️"),
            ("joox", "JOOX", "✔️"),
            ("bilibili", "B站", "✔️"),
            ("ytmusic", "YouTube", "✔️"),
            ("ximalaya", "喜马拉雅", "✔️"),
        ]
        
        if not PLAYWRIGHT_OK:
            print("[GDMusic] 警告: Playwright未安装，请执行: pip install playwright && python3 -m playwright install chromium")

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def action(self, action):
        pass

    def destroy(self):
        self._close_browser()

    # ==================== 浏览器管理 ====================
    def _ensure_browser(self):
        """确保浏览器实例可用，利用网站JS上下文调用API绕过Cloudflare"""
        with self._lock:
            self._last_use = time.time()
            if self._page is not None:
                try:
                    # 检查页面是否还活着
                    self._page.evaluate("1+1")
                    return self._page
                except:
                    pass
            return self._create_browser()

    def _create_browser(self):
        """创建新的浏览器实例"""
        if not PLAYWRIGHT_OK:
            raise Exception("Playwright未安装")
        
        self._close_browser()
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
            ]
        )
        context = self._browser.new_context(
            user_agent=self.ua,
            viewport={"width": 1280, "height": 720}
        )
        self._page = context.new_page()
        
        # 访问首页加载JS上下文
        self._page.goto(self.base_url, wait_until="networkidle", timeout=30000)
        
        # 关闭弹窗
        try:
            self._page.click("text=同意并继续", timeout=3000)
        except:
            pass
        
        return self._page

    def _close_browser(self):
        """关闭浏览器实例"""
        try:
            if self._page:
                self._page.close()
        except:
            pass
        try:
            if self._browser:
                self._browser.close()
        except:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except:
            pass
        self._page = None
        self._browser = None
        self._playwright = None

    def _eval_js(self, js_code, arg=None):
        """在浏览器页面中执行JS并返回结果，自动重试"""
        last_err = None
        for attempt in range(3):
            try:
                page = self._ensure_browser()
                if arg is not None:
                    return page.evaluate(js_code, arg)
                else:
                    return page.evaluate(js_code)
            except Exception as e:
                last_err = e
                # 出错后重置浏览器
                self._close_browser()
                time.sleep(1)
        raise last_err

    # ==================== API调用 ====================
    def _api_search(self, keyword, source="netease", page=1, count=20):
        """搜索歌曲"""
        js = '''
        (params) => {
            return new Promise((resolve) => {
                var p = JSON.parse(params);
                rem.loadPage = p.page;
                rem.wd = p.keyword;
                rem.source = p.source;
                rem.type = "track";
                var origAjax = $.ajax;
                $.ajax = function(settings) {
                    var origSuccess = settings.success;
                    settings.success = function(data) {
                        resolve(JSON.stringify(data));
                        $.ajax = origAjax;
                    };
                    settings.error = function() {
                        resolve("[]");
                        $.ajax = origAjax;
                    };
                    return origAjax.call(this, settings);
                };
                ajaxSearch("search");
            });
        }
        '''
        param = json.dumps({"keyword": keyword, "source": source, "page": page, "count": count})
        result = self._eval_js(js, param)
        try:
            return json.loads(result)
        except:
            return []

    def _api_url(self, song_id, source, br=320):
        """获取播放链接"""
        js = '''
        (params) => {
            return new Promise((resolve) => {
                var p = JSON.parse(params);
                var song = {id: p.song_id, source: p.source, br: p.br, url_id: p.song_id, pic_id: p.song_id, lyric_id: p.song_id};
                var origAjax = $.ajax;
                $.ajax = function(settings) {
                    var origSuccess = settings.success;
                    settings.success = function(data) {
                        resolve(JSON.stringify(data));
                        $.ajax = origAjax;
                    };
                    settings.error = function() {
                        resolve("{}");
                        $.ajax = origAjax;
                    };
                    return origAjax.call(this, settings);
                };
                ajaxUrl(song, function(s) {
                    resolve(JSON.stringify(s));
                    $.ajax = origAjax;
                });
            });
        }
        '''
        param = json.dumps({"song_id": str(song_id), "source": source, "br": br})
        result = self._eval_js(js, param)
        try:
            return json.loads(result)
        except:
            return {}

    def _api_lyric(self, song_id, source):
        """获取歌词"""
        js = '''
        (params) => {
            return new Promise((resolve) => {
                var p = JSON.parse(params);
                var song = {lyric_id: p.song_id, source: p.source, id: p.song_id};
                var origAjax = $.ajax;
                $.ajax = function(settings) {
                    var origSuccess = settings.success;
                    settings.success = function(data) {
                        resolve(JSON.stringify(data));
                        $.ajax = origAjax;
                    };
                    settings.error = function() {
                        resolve("{}");
                        $.ajax = origAjax;
                    };
                    return origAjax.call(this, settings);
                };
                ajaxLyric(song, function(id, lyric, tlyric) {
                    resolve(JSON.stringify({lyric: lyric || "", tlyric: tlyric || ""}));
                    $.ajax = origAjax;
                });
            });
        }
        '''
        param = json.dumps({"song_id": str(song_id), "source": source})
        result = self._eval_js(js, param)
        try:
            return json.loads(result)
        except:
            return {}

    # ==================== TVBox接口实现 ====================
    def isGD(self):
        return True  # 标记为音乐源

    # 音乐源首页分类
    cats = [
        {"type_name": "网易云音乐", "type_id": "netease"},
        {"type_name": "QQ音乐", "type_id": "tencent"},
        {"type_name": "酷我音乐", "type_id": "kuwo"},
        {"type_name": "咪咕音乐", "type_id": "migu"},
        {"type_name": "Tidal", "type_id": "tidal"},
        {"type_name": "Qobuz", "type_id": "qobuz"},
        {"type_name": "Apple Music", "type_id": "apple"},
        {"type_name": "Spotify", "type_id": "spotify"},
        {"type_name": "JOOX", "type_id": "joox"},
        {"type_name": "B站音乐", "type_id": "bilibili"},
        {"type_name": "YouTube", "type_id": "ytmusic"},
    ]

    def _build_filters(self):
        filters = {}
        for cat in self.cats:
            filters[cat["type_id"]] = [
                {"key": "br", "name": "音质", "value": [
                    {"n": "标准128K", "v": "128"},
                    {"n": "较高192K", "v": "192"},
                    {"n": "高品320K", "v": "320"},
                    {"n": "无损16bit", "v": "740"},
                    {"n": "无损24bit", "v": "999"},
                ]}
            ]
        return filters

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        """获取分类内容 - 展示热门搜索词作为分类页"""
        page = int(pg) if pg else 1
        filters = self._build_filters()
        
        # 分类页展示一些推荐搜索词
        hot_keywords = [
            "周杰伦", "林俊杰", "邓紫棋", "陈奕迅", "薛之谦",
            "毛不易", "李荣浩", "华晨宇", "张学友", "王菲",
            "五月天", "Taylor Swift", "Ed Sheeran", "Adele", "Bruno Mars",
        ]
        
        videos = []
        for i, kw in enumerate(hot_keywords):
            videos.append({
                "vod_id": "search://{0}".format(kw),
                "vod_name": kw,
                "vod_pic": "https://music.gdstudio.org/images/player_cover.png",
                "vod_remarks": "点击搜索",
            })
        
        return {
            "code": 1,
            "msg": "数据列表",
            "page": page,
            "pagecount": 1,
            "limit": len(videos),
            "total": len(videos),
            "list": videos,
            "filters": filters,
        }

    def searchContent(self, key, quick=None):
        """搜索 - 返回歌曲列表"""
        if not key:
            return []
        
        # 默认用网易云搜索
        results = []
        songs = self._api_search(key, source="netease", page=1, count=30)
        
        for song in songs:
            artist = song.get("artist", "")
            if isinstance(artist, list):
                artist = ", ".join(artist)
            
            song_id = str(song.get("id", ""))
            source = song.get("source", "netease")
            album = song.get("album", "")
            
            # 编码ID: source_songid  用于后续获取播放链接
            vod_id = "{0}_{1}".format(source, song_id)
            
            name = song.get("name", "")
            if album:
                name = "{0} - {1}".format(name, album)
            
            results.append({
                "vod_id": vod_id,
                "vod_name": "{0} - {1}".format(name, artist) if artist else name,
                "vod_pic": "https://music.gdstudio.org/images/player_cover.png",
                "vod_remarks": source,
            })
        
        return results

    def detailContent(self, array):
        """获取歌曲详情 - 包含播放链接"""
        vod_id = array[0] if isinstance(array, list) else array
        
        # 解析 source_songid
        parts = vod_id.split("_", 1)
        if len(parts) != 2:
            return {"list": []}
        
        source, song_id = parts
        
        # 获取播放链接
        url_data = self._api_url(song_id, source, br=320)
        play_url = url_data.get("url", "")
        br = url_data.get("br", 0)
        size = url_data.get("size", 0)
        
        # 获取歌词
        lyric_data = self._api_lyric(song_id, source)
        lyric = lyric_data.get("lyric", "")
        
        # 音质信息
        quality_str = ""
        if br:
            if br >= 999:
                quality_str = "24bit无损"
            elif br >= 740:
                quality_str = "16bit无损"
            elif br >= 320:
                quality_str = "320K高品"
            elif br >= 192:
                quality_str = "192K较高"
            else:
                quality_str = "128K标准"
        
        size_str = ""
        if size:
            size_mb = size / 1024 / 1024
            if size_mb >= 1:
                size_str = "{0:.1f}MB".format(size_mb)
            else:
                size_str = "{0:.0f}KB".format(size / 1024)
        
        # 构建播放信息
        play_from = [source]
        play_url_list = []
        if play_url and play_url != "err":
            play_url_list.append(play_url + "${0}".format(quality_str))
        else:
            play_url_list.append("无法获取播放链接${0}".format(quality_str))
        
        vod = {
            "vod_id": vod_id,
            "vod_name": "GD音乐台",
            "vod_pic": "https://music.gdstudio.org/images/player_cover.png",
            "vod_year": quality_str,
            "vod_area": size_str,
            "vod_remarks": source,
            "vod_content": lyric if lyric else "暂无歌词",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(["#".join(play_url_list)]),
        }
        
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags=[]):
        """返回播放链接"""
        # id就是播放链接
        url = id.split("$")[0] if "$" in id else id
        
        headers = {
            "User-Agent": self.ua,
            "Referer": self.base_url + "/",
        }
        
        return {
            "code": 0,
            "msg": "OK",
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": json.dumps(headers),
        }


# ==================== 测试入口 ====================
if __name__ == "__main__":
    spider = GDMusicSpider()
    spider.init()
    
    print("=" * 60)
    print("1. 测试搜索")
    print("=" * 60)
    results = spider.searchContent("周杰伦")
    print("搜索到 {0} 首歌曲".format(len(results)))
    for r in results[:5]:
        print("  {0} [{1}]".format(r["vod_name"], r["vod_remarks"]))
    
    if results:
        print("\n" + "=" * 60)
        print("2. 测试详情/播放")
        print("=" * 60)
        detail = spider.detailContent([results[0]["vod_id"]])
        if detail["list"]:
            vod = detail["list"][0]
            print("音质:", vod["vod_year"])
            print("大小:", vod["vod_area"])
            print("歌词:", vod["vod_content"][:100])
            play_url = vod["vod_play_url"]
            print("播放链接:", play_url[:200])
            
            print("\n" + "=" * 60)
            print("3. 测试playerContent")
            print("=" * 60)
            url_part = play_url.split("#")[0].split("$")[0]
            pc = spider.playerContent("", url_part)
            print("最终URL:", pc["url"][:200])
    
    spider.destroy()