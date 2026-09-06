#!/usr/bin/env python3
"""
IPTV 本地 Web 管理界面
端口: 9998
功能: 查看播放列表、手动更新、查看日志、管理自定义源
"""

from flask import Flask, render_template_string, jsonify, request, redirect
import os
import re
import time
import json
import requests as http_requests
from datetime import datetime
from urllib.parse import quote
import threading

app = Flask(__name__)

# 配置
ZB_FILE = os.environ.get("ZB_FILE", "/app/ZB.txt")
CUSTOM_FILE = "/app/custom_sources.json"
LOG_FILE = "/app/logs/cron.log"
UPLOAD_URL = os.environ.get("UPLOAD_URL", "https://iptv-bfo.pages.dev/api/upload")
CF_API_BASE = os.environ.get("CF_API_BASE", "https://iptv-bfo.pages.dev/api")

# 分组定义
GROUP_ORDER = [
    "央视频道", "卫视频道", "电影频道", "儿童频道",
    "体育频道", "纪录频道", "音乐频道", "地方频道",
    "数字频道", "解说频道", "春晚频道", "直播中国", "其他"
]


def get_channel_group(name):
    """频道分组"""
    name_upper = name.upper()
    
    if "CCTV" in name_upper or "中央" in name or "央视" in name or "CGTN" in name_upper:
        return "央视频道"
    if "卫视" in name:
        return "卫视频道"
    if any(kw in name for kw in ["电影", "CHC", "影院", "影视", "影剧"]):
        return "电影频道"
    if any(kw in name for kw in ["卡通", "少儿", "动画", "炫动", "动漫"]):
        return "儿童频道"
    if any(kw in name for kw in ["体育", "足球", "篮球", "台球"]):
        return "体育频道"
    if any(kw in name for kw in ["纪录", "纪实", "科教", "探索", "发现", "地理", "自然"]):
        return "纪录频道"
    if any(kw in name for kw in ["音乐", "MV", "歌曲", "戏曲", "梨园"]):
        return "音乐频道"
    
    local_keywords = [
        "北京", "上海", "天津", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江",
        "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
        "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "台湾",
        "内蒙古", "广西", "西藏", "宁夏", "新疆", "香港", "澳门",
        "郑州", "南阳", "安阳", "洛阳", "新乡", "许昌", "平顶山", "焦作",
        "商丘", "周口", "驻马店", "信阳", "漯河", "濮阳", "鹤壁", "三门峡",
        "石家庄", "唐山", "秦皇岛", "邯郸", "邢台", "保定", "张家口", "承德",
        "沧州", "廊坊", "衡水", "太原", "大同", "长治", "晋城", "运城",
        "济南", "青岛", "烟台", "潍坊", "济宁", "临沂", "德州", "聊城",
        "南京", "苏州", "无锡", "常州", "南通", "扬州", "徐州", "连云港", "淮安",
        "杭州", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "台州", "丽水",
        "合肥", "芜湖", "蚌埠", "马鞍山", "淮南", "安庆", "黄山", "六安", "亳州",
        "福州", "厦门", "莆田", "三明", "泉州", "漳州", "南平", "龙岩", "宁德",
        "南昌", "景德镇", "九江", "赣州", "吉安", "宜春", "抚州", "上饶",
        "武汉", "宜昌", "襄阳", "荆门", "荆州", "黄冈", "咸宁", "恩施",
        "长沙", "株洲", "湘潭", "衡阳", "邵阳", "岳阳", "常德", "张家界", "郴州",
        "广州", "深圳", "珠海", "汕头", "佛山", "东莞", "中山", "惠州", "湛江",
        "南宁", "柳州", "桂林", "梧州", "北海", "玉林", "百色", "河池", "来宾",
        "海口", "三亚", "成都", "绵阳", "德阳", "乐山", "南充", "眉山", "宜宾",
        "贵阳", "遵义", "安顺", "毕节", "铜仁",
        "昆明", "曲靖", "玉溪", "丽江", "大理",
        "西安", "宝鸡", "咸阳", "渭南", "延安", "汉中",
        "兰州", "天水", "张掖", "酒泉", "庆阳",
        "西宁", "银川", "乌鲁木齐", "哈密",
        "长春", "吉林", "四平", "通化", "白山", "松原", "白城", "延边",
        "沈阳", "大连", "鞍山", "抚顺", "丹东", "锦州", "营口",
        "哈尔滨", "齐齐哈尔", "大庆", "牡丹江", "黑河",
        "呼和浩特", "包头", "赤峰", "鄂尔多斯", "呼伦贝尔",
        "拉萨", "日喀则", "林芝",
        "潞州", "BTV", "公共", "都市", "生活", "文化", "民生", "经济", "新闻",
        "综合", "乡村", "国学", "武术", "法制", "文宝", "冬奥", "纪实",
    ]
    for kw in local_keywords:
        if kw in name:
            return "地方频道"
    
    if any(kw in name for kw in ["新视觉", "数码", "汽摩", "四海", "环球", "测试"]):
        return "数字频道"
    if "解说" in name:
        return "解说频道"
    if "春晚" in name:
        return "春晚频道"
    if any(kw in name for kw in ["直播中国", "风景", "景区", "全景", "远眺", "遥望"]):
        return "直播中国"
    
    return "其他"


def load_channels():
    """加载频道列表：优先从 CF KV 读取远程源数据，失败时降级读 ZB.txt"""
    channels = {}
    data_source = "未知"

    # 优先从 CF KV 读取已上传的播放列表（远程源抓取后上传的数据）
    try:
        resp = http_requests.get(f"{CF_API_BASE}/local/txt", timeout=10)
        if resp.status_code == 200 and resp.text.strip():
            text = resp.text.strip()
            if not text.startswith("#") or len(text) > 50:
                data_source = "远程源"
                for line in text.split('\n'):
                    line = line.strip()
                    if not line or line.startswith('#') or ',#genre#' in line:
                        continue
                    if ',' not in line:
                        continue
                    parts = line.split(',', 2)
                    name = parts[0].strip()
                    url = parts[1].strip()
                    group = parts[2].strip() if len(parts) >= 3 else get_channel_group(name)
                    if not name or not url or not url.startswith("http"):
                        continue
                    if group not in channels:
                        channels[group] = {}
                    if name not in channels[group]:
                        channels[group][name] = []
                    if url not in [s["url"] for s in channels[group][name]]:
                        channels[group][name].append({"url": url, "source": "远程源"})
                if channels:
                    print(f"[web_admin] 从 CF KV 加载了频道列表 (来源: {data_source})")
                    return channels
    except Exception as e:
        print(f"[web_admin] 从 CF KV 读取失败: {e}")

    # 降级：读取 ZB.txt
    if os.path.exists(ZB_FILE):
        data_source = "ZB.txt"
        with open(ZB_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("更新时间"):
                    continue
                if "," not in line:
                    continue
                parts = line.split(",", 2)
                name = parts[0].strip()
                url = parts[1].strip()
                if not name or not url or not url.startswith("http"):
                    continue
                group = get_channel_group(name)
                if group not in channels:
                    channels[group] = {}
                if name not in channels[group]:
                    channels[group][name] = []
                if url not in [s["url"] for s in channels[group][name]]:
                    channels[group][name].append({"url": url, "source": "ZB.txt"})
        print(f"[web_admin] 从 ZB.txt 加载了频道列表 (降级模式)")

    # 加载自定义源（追加到列表）
    if os.path.exists(CUSTOM_FILE):
        try:
            with open(CUSTOM_FILE, "r", encoding="utf-8") as f:
                custom = json.load(f)
            for item in custom:
                name = item.get("name", "").strip()
                url = item.get("url", "").strip()
                group = item.get("group", get_channel_group(name))
                if name and url:
                    if group not in channels:
                        channels[group] = {}
                    if name not in channels[group]:
                        channels[group][name] = []
                    channels[group][name].append({"url": url, "source": "自定义"})
        except Exception as e:
            print(f"加载自定义源失败: {e}")

    return channels


def read_logs(lines=50):
    """读取日志文件"""
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        return all_lines[-lines:] if len(all_lines) > lines else all_lines
    except Exception as e:
        return [f"读取日志失败: {e}"]


# HTML 模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IPTV 本地管理</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #333; margin-bottom: 20px; }
        .nav {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .nav-btn {
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            background: #667eea;
            color: white;
            cursor: pointer;
            font-size: 14px;
        }
        .nav-btn:hover { background: #5a67d8; }
        .nav-btn.active { background: #764ba2; }
        .card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-item {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-value { font-size: 24px; font-weight: bold; }
        .stat-label { font-size: 12px; opacity: 0.9; }
        .group-title {
            font-size: 18px;
            font-weight: bold;
            color: #333;
            margin: 20px 0 10px;
            padding-bottom: 5px;
            border-bottom: 2px solid #667eea;
        }
        .channel-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            border-bottom: 1px solid #eee;
        }
        .channel-item:hover { background: #f9f9f9; }
        .channel-name { font-weight: 500; color: #333; }
        .channel-url {
            color: #666;
            font-size: 12px;
            font-family: monospace;
            max-width: 400px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .channel-source {
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 4px;
            background: #e0e0e0;
            color: #666;
        }
        .channel-source.custom { background: #22c55e; color: white; }
        .logs {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 15px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 12px;
            max-height: 500px;
            overflow-y: auto;
            white-space: pre-wrap;
        }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; color: #333; }
        .form-group input, .form-group select {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
        }
        .btn-primary {
            background: #22c55e;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
        }
        .btn-primary:hover { background: #16a34a; }
        .btn-danger {
            background: #ef4444;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }
        .alert {
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 15px;
        }
        .alert-success { background: #d1fae5; color: #065f46; }
        .alert-error { background: #fee2e2; color: #991b1b; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📺 IPTV 本地管理</h1>
        
        <div class="nav">
            <button class="nav-btn active" onclick="showTab('channels')">📋 播放列表</button>
            <button class="nav-btn" onclick="showTab('logs')">📄 更新日志</button>
            <button class="nav-btn" onclick="showTab('custom')">➕ 自定义源</button>
            <button class="nav-btn" onclick="doUpdate()">🔄 立即更新</button>
        </div>
        
        <div id="alert"></div>
        
        <!-- 播放列表 -->
        <div id="channels-tab" class="tab-content">
            <div class="card">
                <div class="stats">
                    <div class="stat-item">
                        <div class="stat-value" id="total-groups">0</div>
                        <div class="stat-label">分组</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value" id="total-channels">0</div>
                        <div class="stat-label">频道</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value" id="total-sources">0</div>
                        <div class="stat-label">源地址</div>
                    </div>
                </div>
                <div id="channels-list"></div>
            </div>
        </div>
        
        <!-- 日志 -->
        <div id="logs-tab" class="tab-content hidden">
            <div class="card">
                <h3 style="margin-bottom: 15px;">更新日志</h3>
                <div class="logs" id="logs-content">加载中...</div>
            </div>
        </div>
        
        <!-- 自定义源 -->
        <div id="custom-tab" class="tab-content hidden">
            <div class="card">
                <h3 style="margin-bottom: 15px;">添加自定义源</h3>
                <form onsubmit="addCustom(event)">
                    <div class="form-group">
                        <label>频道名称</label>
                        <input type="text" id="custom-name" placeholder="如: CCTV-测试" required>
                    </div>
                    <div class="form-group">
                        <label>播放地址 (M3U8/TS)</label>
                        <input type="url" id="custom-url" placeholder="http://..." required>
                    </div>
                    <div class="form-group">
                        <label>分组 (可选)</label>
                        <select id="custom-group">
                            <option value="">自动分组</option>
                            {% for group in groups %}
                            <option value="{{ group }}">{{ group }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <button type="submit" class="btn-primary">添加源</button>
                </form>
            </div>
            
            <div class="card">
                <h3 style="margin-bottom: 15px;">已添加的自定义源</h3>
                <div id="custom-list"></div>
            </div>
        </div>
    </div>
    
    <script>
        let channelsData = {};
        
        function showTab(tab) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tab + '-tab').classList.remove('hidden');
            event.target.classList.add('active');
            
            if (tab === 'channels') loadChannels();
            if (tab === 'logs') loadLogs();
            if (tab === 'custom') loadCustom();
        }
        
        function showAlert(msg, type) {
            const el = document.getElementById('alert');
            el.innerHTML = `<div class="alert alert-${type}">${msg}</div>`;
            setTimeout(() => el.innerHTML = '', 3000);
        }
        
        async function loadChannels() {
            const res = await fetch('/api/channels');
            const data = await res.json();
            channelsData = data.channels;
            
            let totalChannels = 0;
            let totalSources = 0;
            let html = '';
            
            for (const group of data.groups) {
                if (!channelsData[group]) continue;
                const channels = channelsData[group];
                const channelNames = Object.keys(channels);
                
                html += `<div class="group-title">${group} (${channelNames.length}个频道)</div>`;
                
                for (const name of channelNames) {
                    totalChannels++;
                    const sources = channels[name];
                    totalSources += sources.length;
                    
                    for (const src of sources) {
                        const sourceClass = src.source === '自定义' ? 'custom' : '';
                        html += `
                            <div class="channel-item">
                                <div>
                                    <div class="channel-name">${name}</div>
                                    <div class="channel-url" title="${src.url}">${src.url}</div>
                                </div>
                                <span class="channel-source ${sourceClass}">${src.source}</span>
                            </div>
                        `;
                    }
                }
            }
            
            document.getElementById('channels-list').innerHTML = html;
            document.getElementById('total-groups').textContent = Object.keys(channelsData).length;
            document.getElementById('total-channels').textContent = totalChannels;
            document.getElementById('total-sources').textContent = totalSources;
        }
        
        async function loadLogs() {
            const res = await fetch('/api/logs');
            const data = await res.json();
            document.getElementById('logs-content').textContent = data.logs.join('');
        }
        
        async function loadCustom() {
            const res = await fetch('/api/custom');
            const data = await res.json();
            
            if (data.sources.length === 0) {
                document.getElementById('custom-list').innerHTML = '<p style="color: #999;">暂无自定义源</p>';
                return;
            }
            
            let html = '';
            for (const src of data.sources) {
                html += `
                    <div class="channel-item">
                        <div>
                            <div class="channel-name">${src.name}</div>
                            <div class="channel-url">${src.url}</div>
                        </div>
                        <button class="btn-danger" onclick="deleteCustom('${src.name}', '${src.url}')">删除</button>
                    </div>
                `;
            }
            document.getElementById('custom-list').innerHTML = html;
        }
        
        async function addCustom(e) {
            e.preventDefault();
            const name = document.getElementById('custom-name').value;
            const url = document.getElementById('custom-url').value;
            const group = document.getElementById('custom-group').value;
            
            const res = await fetch('/api/custom', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, url, group })
            });
            
            const data = await res.json();
            if (data.success) {
                showAlert('添加成功', 'success');
                document.getElementById('custom-name').value = '';
                document.getElementById('custom-url').value = '';
                loadCustom();
            } else {
                showAlert(data.error || '添加失败', 'error');
            }
        }
        
        async function deleteCustom(name, url) {
            if (!confirm('确定删除这个源吗？')) return;
            
            const res = await fetch('/api/custom', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, url })
            });
            
            const data = await res.json();
            if (data.success) {
                showAlert('删除成功', 'success');
                loadCustom();
            }
        }
        
        async function doUpdate() {
            const btn = event.target;
            btn.textContent = '🔄 更新中...';
            btn.disabled = true;
            
            const res = await fetch('/api/update', { method: 'POST' });
            const data = await res.json();
            
            if (data.success) {
                showAlert('更新成功: ' + data.message, 'success');
            } else {
                showAlert('更新失败: ' + data.error, 'error');
            }
            
            btn.textContent = '🔄 立即更新';
            btn.disabled = false;
        }
        
        // 初始加载
        loadChannels();
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, groups=GROUP_ORDER)


@app.route('/api/channels')
def api_channels():
    channels = load_channels()
    return jsonify({
        "groups": GROUP_ORDER,
        "channels": channels
    })


@app.route('/api/logs')
def api_logs():
    return jsonify({"logs": read_logs(100)})


@app.route('/api/custom', methods=['GET', 'POST', 'DELETE'])
def api_custom():
    if request.method == 'GET':
        sources = []
        if os.path.exists(CUSTOM_FILE):
            try:
                with open(CUSTOM_FILE, "r", encoding="utf-8") as f:
                    sources = json.load(f)
            except:
                pass
        return jsonify({"sources": sources})
    
    elif request.method == 'POST':
        data = request.json
        name = data.get('name', '').strip()
        url = data.get('url', '').strip()
        group = data.get('group', '').strip()
        
        if not name or not url:
            return jsonify({"success": False, "error": "名称和地址不能为空"})
        
        sources = []
        if os.path.exists(CUSTOM_FILE):
            try:
                with open(CUSTOM_FILE, "r", encoding="utf-8") as f:
                    sources = json.load(f)
            except:
                pass
        
        # 检查是否已存在
        for src in sources:
            if src['name'] == name and src['url'] == url:
                return jsonify({"success": False, "error": "该源已存在"})
        
        sources.append({
            "name": name,
            "url": url,
            "group": group,
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        with open(CUSTOM_FILE, "w", encoding="utf-8") as f:
            json.dump(sources, f, ensure_ascii=False, indent=2)
        
        return jsonify({"success": True})
    
    elif request.method == 'DELETE':
        data = request.json
        name = data.get('name')
        url = data.get('url')
        
        if not os.path.exists(CUSTOM_FILE):
            return jsonify({"success": False, "error": "没有自定义源"})
        
        with open(CUSTOM_FILE, "r", encoding="utf-8") as f:
            sources = json.load(f)
        
        sources = [s for s in sources if not (s['name'] == name and s['url'] == url)]
        
        with open(CUSTOM_FILE, "w", encoding="utf-8") as f:
            json.dump(sources, f, ensure_ascii=False, indent=2)
        
        return jsonify({"success": True})


@app.route('/api/update', methods=['POST'])
def api_update():
    """手动触发更新"""
    try:
        # 导入并执行上传脚本
        # 修复：原 timeout=60 太短，upload_and_deploy.py 远程测速一轮 100+ 源
        # 实测耗时 ≥ 2 分钟，必然 TimeoutExpired。这里放宽到 600s（10 分钟）。
        import subprocess
        result = subprocess.run(
            ["python3", "/app/upload_and_deploy.py"],
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode == 0:
            return jsonify({"success": True, "message": "更新完成"})
        else:
            return jsonify({"success": False, "error": result.stderr})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9998, debug=False)



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9998, debug=False)
