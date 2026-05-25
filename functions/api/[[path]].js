/**
 * IPTV 源管理器 - Cloudflare Pages Functions 版本（纯静态读取）
 *
 * 播放列表由 GitHub Actions 生成并通过 /api/upload 推送到 KV
 * 本文件只负责从 KV 读取数据并返回
 */

const CACHE_TTL = 3600;

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const path = url.pathname.replace(/^\/api/, "");

  const corsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };

  if (request.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const KV = env.iptv || env.IPTV_CACHE;

    // 状态页
    if (path === "/" || path === "/status") {
      const lastUpdate = KV ? await KV.get("last_update") : "N/A";
      return new Response(JSON.stringify({
        status: "running",
        version: "2.0.0",
        platform: "Cloudflare Pages",
        last_update: lastUpdate || "Not yet",
        endpoints: {
          m3u8: "/api/iptv",
          txt: "/api/txt",
        },
      }), {
        headers: { "Content-Type": "application/json", ...corsHeaders },
      });
    }

    // M3U8 播放列表
    if (path === "/iptv" || path === "/iptv.m3u" || path === "/live.m3u8") {
      const content = KV ? await KV.get("m3u8") : null;
      if (!content) {
        return new Response("#EXTM3U\n# 暂无数据，请等待 GitHub Actions 自动更新", {
          headers: {
            "Content-Type": "application/vnd.apple.mpegurl; charset=utf-8",
            "Cache-Control": `public, max-age=60`,
            ...corsHeaders,
          },
        });
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
      const content = KV ? await KV.get("txt") : null;
      if (!content) {
        return new Response("# 暂无数据，请等待 GitHub Actions 自动更新", {
          headers: {
            "Content-Type": "text/plain; charset=utf-8",
            "Cache-Control": `public, max-age=60`,
            ...corsHeaders,
          },
        });
      }
      return new Response(content, {
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
          "Cache-Control": `public, max-age=${CACHE_TTL}`,
          ...corsHeaders,
        },
      });
    }

    // 上传端点：推送播放列表到 KV
    if (path === "/upload") {
      if (request.method !== "POST") {
        return new Response(JSON.stringify({ error: "Method not allowed, use POST" }), {
          status: 405,
          headers: { "Content-Type": "application/json", ...corsHeaders },
        });
      }
      
      // 简单的 API Key 验证（从环境变量读取）
      const apiKey = request.headers.get("X-API-Key");
      const validKey = env.API_KEY || "iptv-default-key-2024";
      if (apiKey !== validKey) {
        return new Response(JSON.stringify({ error: "Unauthorized" }), {
          status: 401,
          headers: { "Content-Type": "application/json", ...corsHeaders },
        });
      }
      
      try {
        const body = await request.json();
        if (!KV) {
          return new Response(JSON.stringify({ error: "KV not bound" }), {
            status: 500,
            headers: { "Content-Type": "application/json", ...corsHeaders },
          });
        }
        const now = new Date().toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" });
        if (body.m3u8) await KV.put("m3u8", body.m3u8);
        if (body.txt) await KV.put("txt", body.txt);
        await KV.put("last_update", body.last_update || now);
        return new Response(JSON.stringify({
          status: "success",
          message: "数据已上传到 KV",
          last_update: body.last_update || now,
        }), {
          headers: { "Content-Type": "application/json", ...corsHeaders },
        });
      } catch (e) {
        return new Response(JSON.stringify({ error: "Invalid JSON body: " + e.message }), {
          status: 400,
          headers: { "Content-Type": "application/json", ...corsHeaders },
        });
      }
    }

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
}
