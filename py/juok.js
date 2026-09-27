/**
 * 剧OK (juok3.top) TVBox JavaScript Spider
 *
 * 无需 JAR 包，使用 FongMi TV 内置 QuickJS 引擎运行。
 * 配置: type=3, api="juok.js"
 *
 * 数据来源:
 *   - 首页:   Next.js RSC 数据 (self.__next_f.push)
 *   - 分类页: /api/filter JSON 接口
 *   - 详情页: Next.js RSC 数据
 *   - 搜索:   /api/search JSON 接口
 *
 * vod_id 统一格式: "catId+videoId" (如 "2+QbJwan7nTG4oNn")
 */

const SITE_URL = "https://juok3.top";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

const CAT_NAME = {
    "1": "电影",
    "2": "电视剧",
    "3": "综艺",
    "4": "动漫"
};

// ==================== 初始化 ====================
function init(ext) {
    // ext 可为 JSON 字符串或对象，预留扩展
}

// ==================== HTTP 请求 ====================
function fetch(url) {
    try {
        let resp = req(url, {
            headers: {
                "User-Agent": UA,
                "Referer": SITE_URL,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9"
            }
        });
        return resp || "";
    } catch (e) {
        return "";
    }
}

// ==================== RSC 数据提取 (首页/详情页用) ====================

function extractNextData(html) {
    if (!html) return "";
    let result = "";
    let pattern = /self\.__next_f\.push\(\[1,"(.*?)"\]\)/g;
    let match;
    while ((match = pattern.exec(html)) !== null) {
        let raw = match[1];
        let colonIdx = raw.indexOf(':');
        let content = (colonIdx > 0 && colonIdx < 10) ? raw.substring(colonIdx + 1) : raw;
        content = content.replace(/\\"/g, '"')
                         .replace(/\\\\/g, '\\')
                         .replace(/\\u0026/g, '&');
        result += content;
    }
    return result;
}

// 从 RSC 提取视频列表 (首页用)
function extractVideoList(rscData) {
    let videos = [];
    if (!rscData) return videos;
    let pattern = /\{"title":"[^"]*","comment":"[^"]*".*?"ent_id":"[^"]*"[^}]*\}/g;
    let match;
    while ((match = pattern.exec(rscData)) !== null) {
        try {
            let jsonStr = match[0];
            let lastEnt = jsonStr.lastIndexOf('"ent_id"');
            if (lastEnt > 0) {
                let end = jsonStr.indexOf('}', lastEnt);
                if (end > 0) jsonStr = jsonStr.substring(0, end + 1);
            }
            videos.push(JSON.parse(jsonStr));
        } catch (e) {}
    }
    return videos;
}

// 从 RSC 提取剧集列表 (详情页用)
function extractEpisodes(rscData) {
    let episodes = [];
    if (!rscData) return episodes;
    // 精确匹配剧集对象
    let pattern = /\{"id":"\d+","playlink_num":"\d+","url":"[^"]+","v_cover":"[^"]*","is_vip":"[01]","api_id":"[^"]*","api_video_id":"[^"]*"\}/g;
    let match;
    while ((match = pattern.exec(rscData)) !== null) {
        try { episodes.push(JSON.parse(match[0])); } catch (e) {}
    }
    // 备选: 宽松匹配
    if (episodes.length === 0) {
        let p2 = /"playlink_num":"(\d+)","url":"([^"]+)".*?"is_vip":"([01])"/g;
        while ((match = p2.exec(rscData)) !== null) {
            episodes.push({
                playlink_num: match[1],
                url: match[2].replace(/\\u0026/g, '&'),
                is_vip: match[3]
            });
        }
    }
    return episodes;
}

// ==================== TVBox 接口实现 ====================

function homeContent(filter) {
    let classes = [];
    for (let tid in CAT_NAME) {
        classes.push({ type_id: tid, type_name: CAT_NAME[tid] });
    }

    // 筛选器 (type=分类, area=地区, year=年份, sort=排序)
    let filters = {};
    let typeVals = [
        {n:"全部", v:""}, {n:"言情", v:"言情"}, {n:"剧情", v:"剧情"}, {n:"伦理", v:"伦理"},
        {n:"喜剧", v:"喜剧"}, {n:"悬疑", v:"悬疑"}, {n:"都市", v:"都市"}, {n:"偶像", v:"偶像"},
        {n:"古装", v:"古装"}, {n:"军事", v:"军事"}, {n:"警匪", v:"警匪"}, {n:"历史", v:"历史"},
        {n:"励志", v:"励志"}, {n:"神话", v:"神话"}, {n:"谍战", v:"谍战"}, {n:"青春", v:"青春"},
        {n:"家庭", v:"家庭"}, {n:"动作", v:"动作"}, {n:"情景", v:"情景"}, {n:"武侠", v:"武侠"},
        {n:"科幻", v:"科幻"}, {n:"其他", v:"其他"}
    ];
    let areaVals = [
        {n:"全部", v:""}, {n:"大陆", v:"大陆"}, {n:"香港", v:"香港"}, {n:"台湾", v:"台湾"},
        {n:"泰国", v:"泰国"}, {n:"日本", v:"日本"}, {n:"韩国", v:"韩国"}, {n:"美国", v:"美国"},
        {n:"英国", v:"英国"}, {n:"新加坡", v:"新加坡"}
    ];
    let yearVals = [
        {n:"全部", v:""}, {n:"2026", v:"2026"}, {n:"2025", v:"2025"}, {n:"2024", v:"2024"},
        {n:"2023", v:"2023"}, {n:"2022", v:"2022"}, {n:"2021", v:"2021"}, {n:"2020", v:"2020"},
        {n:"2019", v:"2019"}, {n:"2018", v:"2018"}, {n:"2017", v:"2017"}, {n:"2016", v:"2016"},
        {n:"2015", v:"2015"}
    ];
    let sortVals = [
        {n:"按最新", v:"ranklatest"}, {n:"按热度", v:"rankhot"}, {n:"按评分", v:"rankpoint"}
    ];
    for (let tid in CAT_NAME) {
        filters[tid] = [
            {key:"type", name:"类型", value:typeVals},
            {key:"area", name:"地区", value:areaVals},
            {key:"year", name:"年份", value:yearVals},
            {key:"sort", name:"排序", value:sortVals}
        ];
    }

    let list = [];
    try {
        let html = fetch(SITE_URL + "/");
        let rscData = extractNextData(html);
        let videos = extractVideoList(rscData);
        for (let i = 0; i < videos.length; i++) {
            let v = videos[i];
            let remarks = "";
            if (v.upinfo) remarks = "更新至" + v.upinfo + "集";
            list.push({
                vod_id: (v.cat || "2") + "+" + (v.ent_id || ""),
                vod_name: v.title || "",
                vod_pic: v.cover || "",
                vod_remarks: remarks
            });
        }
    } catch (e) {}

    return JSON.stringify({ class: classes, filters: filters, list: list });
}

function homeVideoContent() {
    return JSON.stringify({ list: [] });
}

function categoryContent(tid, pg, filter, extend) {
    let list = [];
    let page = parseInt(pg) || 1;
    let total = 0;
    try {
        let sort = "ranklatest";
        if (extend && extend.sort) sort = extend.sort;
        let url = SITE_URL + "/api/filter?catId=" + tid + "&sort=" + sort + "&page=" + page + "&size=24";
        if (extend) {
            if (extend.type) url += "&type=" + encodeURIComponent(extend.type);
            if (extend.area) url += "&area=" + encodeURIComponent(extend.area);
            if (extend.year) url += "&year=" + encodeURIComponent(extend.year);
        }
        let json = fetch(url);
        let data = JSON.parse(json);
        total = data.total || 0;
        let movies = data.movies || [];
        for (let i = 0; i < movies.length; i++) {
            let m = movies[i];
            let remarks = "";
            if (m.upinfo) remarks = "更新至" + m.upinfo + "集";
            else if (m.total) remarks = m.total + "集";
            list.push({
                vod_id: tid + "+" + (m.id || ""),
                vod_name: m.title || "",
                vod_pic: m.cover || "",
                vod_remarks: remarks
            });
        }
    } catch (e) {}

    let pagecount = total > 0 ? Math.ceil(total / 24) : 9999;
    return JSON.stringify({
        list: list,
        page: page,
        pagecount: pagecount,
        limit: 24,
        total: total
    });
}

function detailContent(ids) {
    let list = [];
    try {
        let vodId = ids[0];
        let parts = vodId.split("+");
        let catId = parts[0];
        let videoId = parts.length > 1 ? parts[1] : vodId;

        let url = SITE_URL + "/detail/" + catId + "/" + videoId;
        let html = fetch(url);
        let rscData = extractNextData(html);

        let vodInfo = { vod_id: vodId };

        // 标题
        let titleMatch = rscData.match(/\{"children":"《([^》]+)》/);
        if (titleMatch) vodInfo.vod_name = titleMatch[1];
        // 简介
        let descMatch = rscData.match(/"description","content":"([^"]+)"/);
        if (descMatch) vodInfo.vod_content = descMatch[1];
        // 演员
        let actMatch = rscData.match(/"actList":\[([^\]]+)\]/);
        if (actMatch) vodInfo.vod_actor = actMatch[1].replace(/"/g, "");
        // 导演
        let dirMatch = rscData.match(/"dirList":\[([^\]]+)\]/);
        if (dirMatch) vodInfo.vod_director = dirMatch[1].replace(/"/g, "");
        // 年份
        let yearMatch = rscData.match(/"year":"(\d+)"/);
        if (yearMatch) vodInfo.vod_year = yearMatch[1];
        // 地区
        let areaMatch = rscData.match(/"area":\[([^\]]+)\]/);
        if (areaMatch) vodInfo.vod_area = areaMatch[1].replace(/"/g, "");

        // 剧集列表
        let episodes = extractEpisodes(rscData);
        let playUrls = [];
        for (let i = 0; i < episodes.length; i++) {
            let ep = episodes[i];
            let num = ep.playlink_num || (i + 1);
            let epUrl = ep.url || "";
            playUrls.push("第" + num + "集$" + epUrl);
        }
        vodInfo.vod_play_from = "剧OK";
        vodInfo.vod_play_url = playUrls.join("#");

        list.push(vodInfo);
    } catch (e) {}

    return JSON.stringify({ list: list });
}

function searchContent(key, quick) {
    let list = [];
    try {
        let url = SITE_URL + "/api/search?q=" + encodeURIComponent(key);
        let json = fetch(url);
        let data = JSON.parse(json);
        let results = data.results || [];
        for (let i = 0; i < results.length; i++) {
            let v = results[i];
            let title = (v.titleTxt || v.title || "").replace(/<[^>]+>/g, "");
            let tags = v.tag || [];
            let tagStr = Array.isArray(tags) ? tags.join(" ") : "";
            list.push({
                vod_id: (v.cat_id || "2") + "+" + (v.en_id || ""),
                vod_name: title,
                vod_pic: v.cover || "",
                vod_remarks: ((v.year || "") + " " + tagStr).trim()
            });
        }
    } catch (e) {}

    return JSON.stringify({ list: list });
}

function playerContent(flag, id, vipFlags) {
    // id 即播放链接 (各平台原始链接，需通过 parses 解析)
    return JSON.stringify({
        parse: 1,
        url: id,
        header: "{}"
    });
}

function isVideoFormat(url) {
    return url.indexOf(".m3u8") >= 0 || url.indexOf(".mp4") >= 0;
}

function manualVideoUrl(url) {
    return url;
}
