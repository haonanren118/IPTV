/**
 * IPTV 源管理器 - Cloudflare Worker 版本
 * 
 * 功能：
 * - 从远程 API 获取 IPTV 源列表
 * - 简易测速筛选优质源
 * - 智能分组（央视/卫视/地方台/专业频道/其他）
 * - 生成 M3U8 和 TXT 格式播放列表
 * - KV 缓存 + Cron 定时更新
 */

// ==================== 常量配置 ====================
const API_URL = "https://iptvs.pes.im";
const EPG_URL = "https://epg.zsdc.eu.org/t.xml";
const LOGO_BASE_URL = "https://ghfast.top/https://raw.githubusercontent.com/Jarrey/iptv_logo/main/tv/";
const TOP_N = 5;                  // 选择前 N 个最快源
const SPEED_TEST_TIMEOUT = 8000;  // 测速超时（毫秒）
const MIN_SPEED_MBPS = 1.5;       // 最低速度阈值（MB/s）
const CACHE_TTL = 3600;           // 缓存有效期（秒）

// ==================== 频道分组 ====================
function getChannelGroup(name) {
  const upper = name.toUpperCase();

  // 央视频道
  if (upper.includes("CCTV") || name.includes("中央") || name.includes("央视")) {
    return "央视";
  }

  // 卫视频道
  if (name.includes("卫视")) {
    return "卫视";
  }

  // CGTN 国际频道
  if (upper.includes("CGTN") || name.includes("中国国际")) {
    return "国际频道";
  }

  // 专业频道关键词
  const proKeywords = ["体育", "电影", "电视剧", "财经", "新闻", "综艺", "戏曲", "纪录", "音乐", "动漫", "少儿", "教育", "军事", "农业", "旅游"];
  for (const kw of proKeywords) {
    if (name.includes(kw)) return "专业频道";
  }

  // 地方台（含省市名但不是卫视）
  const localKeywords = [
    "福建", "厦门", "泉州", "福州", "漳州", "莆田", "三明", "南平", "龙岩", "宁德",
    "广州", "深圳", "珠海", "汕头", "佛山", "东莞", "中山", "惠州", "江门", "湛江",
    "成都", "武汉", "南京", "杭州", "苏州", "无锡", "宁波", "青岛", "大连", "沈阳",
    "西安", "郑州", "长沙", "南昌", "合肥", "昆明", "贵阳", "南宁", "海口", "兰州",
    "综合", "乡村振兴", "经济生活", "公共", "都市", "影视", "生活", "文化", "科教"
  ];
  for (const kw of localKeywords) {
    if (name.includes(kw)) return "地方台";
  }

  return "其他";
}

// ==================== 频道名称清洗 ====================
function cleanChannelName(name) {
  name = name.replace(/cctv/gi, "CCTV");
  name = name.replace(/中央/g, "CCTV");
  name = name.replace(/央视/g, "CCTV");
  name = name.replace(/[高清超高HD标清频道\-\s]/g, "");
  name = name.replace(/PLUS|＋/g, "+");
  name = name.replace(/[()（）]/g, "");
  name = name.replace(/CCTV(\d+)台/g, "CCTV$1");

  const nameMap = {
    "CCTV1综合": "CCTV1", "CCTV2财经": "CCTV2", "CCTV3综艺": "CCTV3",
    "CCTV4国际": "CCTV4", "CCTV4中文国际": "CCTV4", "CCTV4欧洲": "CCTV4",
    "CCTV5体育": "CCTV5", "CCTV6电影": "CCTV6", "CCTV7军事": "CCTV7",
    "CCTV7军农": "CCTV7", "CCTV7农业": "CCTV7", "CCTV7国防军事": "CCTV7",
    "CCTV8电视剧": "CCTV8", "CCTV9记录": "CCTV9", "CCTV9纪录": "CCTV9",
    "CCTV10科教": "CCTV10", "CCTV11戏曲": "CCTV11", "CCTV12社会与法": "CCTV12",
    "CCTV13新闻": "CCTV13", "CCTV新闻": "CCTV13", "CCTV14少儿": "CCTV14",
    "CCTV15音乐": "CCTV15", "CCTV16奥林匹克": "CCTV16",
    "CCTV17农业农村": "CCTV17", "CCTV17农业": "CCTV17",
    "CCTV5+体育赛视": "CCTV5+", "CCTV5+体育赛事": "CCTV5+", "CCTV5+体育": "CCTV5+",
  };
  return nameMap[name] || name;
}

// ==================== 频道排序 ====================
function channelSortKey(name) {
  const upper = name.toUpperCase();
  if (upper.includes("CCTV")) {
    const match = upper.match(/CCTV(\d+)/);
    if (match) return [0, parseInt(match[1])];
    if (upper.includes("5+")) return [0, 5.5];
    return [0, 999];
  }
  if (name.includes("卫视")) return [1, name];
  return [2, name];
}

// ==================== M3U8 条目构建 ====================
function buildM3u8Entry(name, url) {
  const group = getChannelGroup(name);
  const logo = `${LOGO_BASE_URL}${encodeURIComponent(name)}.png`;
  return `#EXTINF:-1 tvg-name="${name}" tvg-logo="${logo}" group-title="${group}",${name}\n${url}`;
}

// ==================== 简易测速 ====================
async function testHostSpeed(host, matchType) {
  let testUrl = "";

  try {
    if (matchType === "txiptv") {
      const jsonUrl = `http://${host}/iptv/live/1000.json?key=txiptv`;
      const resp = await fetch(jsonUrl, { signal: AbortSignal.timeout(3000) });
      if (!resp.ok) return -1;
      const data = await resp.json();
      if (data.data && data.data.length > 0) {
        const item = data.data.find(d => d.url && !d.url.includes(","));
        if (item) {
          testUrl = item.url.startsWith("http") ? item.url : `http://${host}${item.url}`;
        }
      }
    } else if (matchType === "hsmdtv") {
      testUrl = `http://${host}/newlive/live/hls/1/live.m3u8`;
    } else if (matchType === "jsmpeg") {
      const resp = await fetch(`http://${host}/streamer/list`, { signal: AbortSignal.timeout(3000) });
      if (!resp.ok) return -1;
      const data = await resp.json();
      if (data.length > 0 && data[0].key) {
        testUrl = `http://${host}/hls/${data[0].key}/index.m3u8`;
      }
    } else if (matchType === "zhgxtv") {
      const resp = await fetch(`http://${host}/ZHGXTV/Public/json/live_interface.txt`, { signal: AbortSignal.timeout(5000) });
      if (!resp.ok) return -1;
      const text = await resp.text();
      const lines = text.split("\n");
      for (const line of lines) {
        if (line.includes(",")) {
          const parts = line.split(",");
          if (parts.length >= 2 && parts[1].trim()) {
            const urlPart = parts[1].trim();
            testUrl = urlPart.startsWith("http") ? urlPart : `http://${host}${urlPart}`;
            break;
          }
        }
      }
    }

    if (!testUrl) return -1;

    // 下载测速：获取 m3u8 中的第一个 TS 片段
    const m3u8Resp = await fetch(testUrl, { signal: AbortSignal.timeout(SPEED_TEST_TIMEOUT) });
    if (!m3u8Resp.ok) return -1;
    const m3u8Text = await m3u8Resp.text();

    let tsUrl = "";
    for (const line of m3u8Text.split("\n")) {
      const trimmed = line.trim();
      if (trimmed && !trimmed.startsWith("#")) {
        if (trimmed.startsWith("http")) {
          tsUrl = trimmed;
        } else if (trimmed.startsWith("/")) {
          tsUrl = `${new URL(testUrl).origin}${trimmed}`;
        } else {
          tsUrl = testUrl.rsplit("/", 1)[0] + "/" + trimmed;
        }
        break;
      }
    }

    if (!tsUrl) return -1;

    // 下载 TS 片段测速
    const start = Date.now();
    const tsResp = await fetch(tsUrl, { signal: AbortSignal.timeout(SPEED_TEST_TIMEOUT) });
    if (!tsResp.ok) return -1;

    const reader = tsResp.body.getReader();
    let totalBytes = 0;
    const maxBytes = 2 * 1024 * 1024; // 最多下载 2MB

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      totalBytes += value.length;
      if (totalBytes >= maxBytes) break;
      if (Date.now() - start > SPEED_TEST_TIMEOUT) break;
    }

    const duration = (Date.now() - start) / 1000;
    if (duration === 0) return -1;
    return (totalBytes / 1024 / 1024) / duration; // MB/s
  } catch (e) {
    return -1;
  }
}

// ==================== 获取频道列表 ====================
async function fetchChannels(host, matchType) {
  const channels = [];

  try {
    if (matchType === "txiptv") {
      const resp = await fetch(`http://${host}/iptv/live/1000.json?key=txiptv`, { signal: AbortSignal.timeout(5000) });
      if (!resp.ok) return channels;
      const data = await resp.json();
      if (data.data) {
        for (const item of data.data) {
          if (!item.name || !item.url || item.url.includes(",")) continue;
          const fullUrl = item.url.startsWith("http") ? item.url : `http://${host}${item.url}`;
          channels.push({ name: cleanChannelName(item.name), url: fullUrl });
        }
      }
    } else if (matchType === "jsmpeg") {
      const resp = await fetch(`http://${host}/streamer/list`, { signal: AbortSignal.timeout(5000) });
      if (!resp.ok) return channels;
      const data = await resp.json();
      for (const item of data) {
        if (!item.name || !item.key) continue;
        channels.push({ name: cleanChannelName(item.name), url: `http://${host}/hls/${item.key}/index.m3u8` });
      }
    } else if (matchType === "zhgxtv") {
      const resp = await fetch(`http://${host}/ZHGXTV/Public/json/live_interface.txt`, { signal: AbortSignal.timeout(5000) });
      if (!resp.ok) return channels;
      const text = await resp.text();
      for (const line of text.split("\n")) {
        if (!line.includes(",")) continue;
        const parts = line.split(",");
        if (parts.length < 2) continue;
        const name = cleanChannelName(parts[0].trim());
        let urlPart = parts[1].trim();
        const fullUrl = urlPart.startsWith("http")
          ? urlPart.replace(/^https?:\/\/[^\/]+/, `http://${host}`)
          : `http://${host}${urlPart.startsWith("/") ? "" : "/"}${urlPart}`;
        channels.push({ name, url: fullUrl });
      }
    }
  } catch (e) {
    // 静默失败
  }

  return channels;
}

// ==================== 主更新逻辑 ====================
async function updatePlaylist(env) {
  console.log("开始更新播放列表...");

  // 1. 获取源列表
  let results = [];
  try {
    const resp = await fetch(API_URL, { signal: AbortSignal.timeout(15000) });
    if (resp.ok) {
      const data = await resp.json();
      results = data.results || [];
    }
  } catch (e) {
    console.error("获取 API 数据失败:", e.message);
  }

  if (!results.length) {
    console.log("无源数据，跳过更新");
    return;
  }

  // 2. 并发测速（CF Worker 限制并发数）
  const batchSize = 10;
  const testedHosts = [];

  for (let i = 0; i < results.length; i += batchSize) {
    const batch = results.slice(i, i + batchSize);
    const promises = batch.map(item =>
      testHostSpeed(item.host, item.matchType).then(speed => ({
        host: item.host,
        matchType: item.matchType,
        source: item.source || "N/A",
        speed,
      }))
    );
    const batchResults = await Promise.all(promises);
    testedHosts.push(...batchResults.filter(r => r.speed > 0));
  }

  // 3. 筛选优质源
  const validHosts = testedHosts.filter(r => r.speed > MIN_SPEED_MBPS);
  validHosts.sort((a, b) => b.speed - a.speed);

  // 确保每种类型至少一个
  const selected = [];
  const usedHosts = new Set();
  const requiredTypes = ["txiptv", "hsmdtv", "zhgxtv", "jsmpeg"];

  for (const type of requiredTypes) {
    const found = validHosts.find(r => r.matchType === type && !usedHosts.has(r.host));
    if (found) {
      selected.push(found);
      usedHosts.add(found.host);
    }
  }

  for (const r of validHosts) {
    if (selected.length >= TOP_N) break;
    if (!usedHosts.has(r.host)) {
      selected.push(r);
      usedHosts.add(r.host);
    }
  }

  selected.sort((a, b) => b.speed - a.speed);
  console.log(`已选择 ${selected.length} 个优质源`);

  if (selected.length < 1) {
    console.log("可用源不足，跳过更新");
    return;
  }

  // 4. 获取频道列表
  const allEntries = [];
  for (const source of selected) {
    console.log(`获取频道: ${source.host} (${source.matchType}) ${source.speed.toFixed(2)}MB/s`);
    const channels = await fetchChannels(source.host, source.matchType);
    for (const ch of channels) {
      allEntries.push(ch);
    }
  }

  // 5. 分组去重
  const grouped = new Map();
  for (const entry of allEntries) {
    const key = entry.name;
    if (!grouped.has(key)) {
      grouped.set(key, []);
    }
    // 避免重复 URL
    if (!grouped.get(key).some(e => e.url === entry.url)) {
      grouped.get(key).push(entry);
    }
  }

  // 6. 排序频道
  const sortedNames = [...grouped.keys()].sort((a, b) => {
    const ka = channelSortKey(a);
    const kb = channelSortKey(b);
    if (ka[0] !== kb[0]) return ka[0] - kb[0];
    if (typeof ka[1] === "number" && typeof kb[1] === "number") return ka[1] - kb[1];
    return String(ka[1]).localeCompare(String(kb[1]));
  });

  // 7. 生成 M3U8
  const now = new Date().toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" });
  const m3u8Lines = [
    `#EXTM3U x-tvg-url="${EPG_URL}"`,
    `#EXT-X-UPDATED: ${now}`,
  ];

  for (const name of sortedNames) {
    const entries = grouped.get(name);
    for (const entry of entries) {
      m3u8Lines.push(buildM3u8Entry(entry.name, entry.url));
    }
  }

  const m3u8Content = m3u8Lines.join("\n");

  // 8. 生成 TXT
  const txtLines = [];
  for (const name of sortedNames) {
    const entries = grouped.get(name);
    const group = getChannelGroup(name);
    for (const entry of entries) {
      txtLines.push(`${entry.name},${entry.url},${group}`);
    }
  }

  const txtContent = txtLines.join("\n");

  // 9. 保存到 KV
  if (env.IPTV_CACHE) {
    await env.IPTV_CACHE.put("m3u8", m3u8Content);
    await env.IPTV_CACHE.put("txt", txtContent);
    await env.IPTV_CACHE.put("last_update", now);
    console.log("播放列表已保存到 KV");
  }

  return { m3u8: m3u8Content, txt: txtContent, lastUpdate: now };
}

// ==================== HTTP 路由处理 ====================
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    // CORS 头
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      // 首页 - 状态信息
      if (path === "/" || path === "/status") {
        const lastUpdate = env.IPTV_CACHE ? await env.IPTV_CACHE.get("last_update") : "N/A";
        return new Response(JSON.stringify({
          status: "running",
          version: "1.0.0",
          platform: "Cloudflare Workers",
          last_update: lastUpdate || "Not yet",
          endpoints: {
            m3u8: "/iptv",
            txt: "/txt",
            force_update: "/forceRetest",
          },
        }), {
          headers: { "Content-Type": "application/json", ...corsHeaders },
        });
      }

      // M3U8 播放列表
      if (path === "/iptv" || path === "/iptv.m3u" || path === "/live.m3u8") {
        let content = env.IPTV_CACHE ? await env.IPTV_CACHE.get("m3u8") : null;
        if (!content) {
          const result = await updatePlaylist(env);
          content = result ? result.m3u8 : "#EXTM3U\n# 暂无数据，请稍后访问";
        }
        return new Response(content, {
          headers: {
            "Content-Type": "application/vnd.apple.mpegurl; charset=utf-8",
            "Cache-Control": `public, max-age=${CACHE_TTL}`,
            ...corsHeaders,
          },
        });
      }

      // TXT 播放列表
      if (path === "/txt" || path === "/iptv.txt") {
        let content = env.IPTV_CACHE ? await env.IPTV_CACHE.get("txt") : null;
        if (!content) {
          const result = await updatePlaylist(env);
          content = result ? result.txt : "# 暂无数据，请稍后访问";
        }
        return new Response(content, {
          headers: {
            "Content-Type": "text/plain; charset=utf-8",
            "Cache-Control": `public, max-age=${CACHE_TTL}`,
            ...corsHeaders,
          },
        });
      }

      // 强制更新
      if (path === "/forceRetest" || path === "/update") {
        const result = await updatePlaylist(env);
        return new Response(JSON.stringify({
          status: "success",
          message: "播放列表已更新",
          last_update: result ? result.lastUpdate : "N/A",
        }), {
          headers: { "Content-Type": "application/json", ...corsHeaders },
        });
      }

      // 404
      return new Response(JSON.stringify({ error: "Not Found" }), {
        status: 404,
        headers: { "Content-Type": "application/json", ...corsHeaders },
      });

    } catch (e) {
      return new Response(JSON.stringify({ error: e.message }), {
        status: 500,
        headers: { "Content-Type": "application/json", ...corsHeaders },
      });
    }
  },

  // Cron Trigger 定时任务
  async scheduled(event, env) {
    console.log(`Cron 触发: ${event.cron}`);
    await updatePlaylist(env);
  },
};
