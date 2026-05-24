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
      const lastLocalUpdate = KV ? await KV.get("local_last_update") : "N/A";
      return new Response(JSON.stringify({
        status: "running",
        version: "2.1.0",
        platform: "Cloudflare Pages",
        last_update: lastUpdate || "Not yet",
        local_last_update: lastLocalUpdate || "Not yet",
        endpoints: {
          m3u8: "/api/iptv",
          txt: "/api/txt",
          local_m3u8: "/api/local/m3u8",
          local_txt: "/api/local/txt",
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

    // ========== 本地 IPTV 源（飞牛 NAS 上传）==========

    // 本地 M3U8 播放列表
    if (path === "/local/m3u8" || path === "/local.m3u8" || path === "/local/live.m3u8") {
      const content = KV ? await KV.get("m3u8_local") : null;
      if (!content) {
        return new Response("#EXTM3U\n# 暂无本地源数据，请等待 NAS 上传", {
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

    // 本地 TXT 播放列表
    if (path === "/local/txt" || path === "/local/txt") {
      const content = KV ? await KV.get("txt_local") : null;
      if (!content) {
        return new Response("# 暂无本地源数据，请等待 NAS 上传", {
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

    // 合并播放列表（公网 + 本地 IPTV）
    if (path === "/all/m3u8" || path === "/merged.m3u8") {
      const publicM3u8 = KV ? await KV.get("m3u8") : null;
      const localM3u8 = KV ? await KV.get("m3u8_local") : null;
      let merged = "#EXTM3U\n";
      if (publicM3u8) {
        merged += "\n# ====== 公网源（GitHub Actions 自动扫描测速） ======\n";
        merged += publicM3u8.replace(/^#EXTM3U\s*\n/, "");
      }
      if (localM3u8) {
        merged += "\n# ====== 四川电信 IPTV（本地源） ======\n";
        merged += localM3u8.replace(/^#EXTM3U\s*\n/, "").replace(/x-tvg-url="[^"]*"/, '');
      }
      return new Response(merged, {
        headers: {
          "Content-Type": "application/vnd.apple.mpegurl; charset=utf-8",
          "Cache-Control": `public, max-age=${CACHE_TTL}`,
          ...corsHeaders,
        },
      });
    }

    // 上传端点：飞牛 NAS / GitHub Actions 调用，推送播放列表到 KV（需 Token 认证）
    if (path === "/upload") {
      if (request.method !== "POST") {
        return new Response(JSON.stringify({ error: "Method not allowed, use POST" }), {
          status: 405,
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

        // Token 认证：防止未授权写入
        const expectedToken = env.UPLOAD_TOKEN || "";
        if (expectedToken) {
          const authHeader = request.headers.get("Authorization") || "";
          const token = authHeader.replace("Bearer ", "").trim();
          if (!token || token !== expectedToken) {
            return new Response(JSON.stringify({ error: "Unauthorized" }), {
              status: 401,
              headers: { "Content-Type": "application/json", ...corsHeaders },
            });
          }
        }
        const now = new Date().toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" });
        // 区分数据来源：公网源(GitHub Actions) vs 本地源(NAS)
        const source = (body.source || "public").toLowerCase();
        if (source === "local") {
          // NAS 本地 IPTV 源 → 写入 local keys
          if (body.m3u8) await KV.put("m3u8_local", body.m3u8);
          if (body.txt) await KV.put("txt_local", body.txt);
          await KV.put("local_last_update", body.last_update || now);
        } else {
          // GitHub Actions 公网源 → 写入标准 keys（默认，向后兼容）
          if (body.m3u8) await KV.put("m3u8", body.m3u8);
          if (body.txt) await KV.put("txt", body.txt);
          await KV.put("last_update", body.last_update || now);
        }
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
