#!/usr/bin/env python3
"""
IPTV 播放列表生成器
从 iptvs.pes.im 获取源列表，测速筛选，生成 m3u8/txt 播放列表文件
供 GitHub Actions 调用，生成后上传到 Cloudflare KV
"""

import requests
import time
import re
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from urllib.parse import urlparse, quote

# ==================== 配置 ====================
API_URL = "https://iptvs.pes.im"
EPG_URL = "https://epg.zsdc.eu.org/t.xml"
LOGO_BASE_URL = "https://ghfast.top/https://raw.githubusercontent.com/Jarrey/iptv_logo/main/tv/"
TOP_N = 5
HOST_SPEED_TEST_TIMEOUT = 15
SPEED_TEST_BATCH_SIZE = 60
MAX_WORKERS = 20
MIN_SPEED_MBPS = 1.5
HSMDTV_TEST_URI = "/newlive/live/hls/1/live.m3u8"


# ==================== 频道分组 ====================
def get_channel_group(name):
    name_upper = name.upper()
    if "CCTV" in name_upper or "中央" in name or "央视" in name:
        return "央视"
    if "卫视" in name:
        return "卫视"
    if "CGTN" in name_upper or "中国国际" in name:
        return "国际频道"
    pro_keywords = ["体育", "电影", "电视剧", "财经", "新闻", "综艺", "戏曲", "纪录",
                    "音乐", "动漫", "少儿", "教育", "军事", "农业", "旅游"]
    for kw in pro_keywords:
        if kw in name:
            return "专业频道"
    local_keywords = [
        "福建", "厦门", "泉州", "福州", "漳州", "莆田", "三明", "南平", "龙岩", "宁德",
        "广州", "深圳", "珠海", "汕头", "佛山", "东莞", "中山", "惠州", "江门", "湛江",
        "成都", "武汉", "南京", "杭州", "苏州", "无锡", "宁波", "青岛", "大连", "沈阳",
        "西安", "郑州", "长沙", "南昌", "合肥", "昆明", "贵阳", "南宁", "海口", "兰州",
        "综合", "乡村振兴", "经济生活", "公共", "都市", "影视", "生活", "文化", "科教",
    ]
    for kw in local_keywords:
        if kw in name:
            return "地方台"
    return "其他"


# ==================== 频道名称清洗 ====================
def clean_channel_name(name):
    name = name.replace("cctv", "CCTV")
    name = name.replace("中央", "CCTV")
    name = name.replace("央视", "CCTV")
    for rep in ["高清", "超高", "HD", "标清", "频道", "-", " ", "PLUS", "＋", "(", ")", "（", "）"]:
        name = name.replace(rep, "+" if rep in ("PLUS", "＋") else "")
    name = re.sub(r"CCTV(\d+)台", r"CCTV\1", name)
    name_map = {
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
        "CCTV01": "CCTV1", "CCTV02": "CCTV2", "CCTV03": "CCTV3", "CCTV04": "CCTV4",
        "CCTV05": "CCTV5", "CCTV06": "CCTV6", "CCTV07": "CCTV7", "CCTV08": "CCTV8", "CCTV09": "CCTV9",
    }
    return name_map.get(name, name)


# ==================== 频道排序 ====================
def channel_sort_key(name):
    name_upper = name.upper()
    if "CCTV" in name_upper:
        match = re.search(r"CCTV(\d+)", name_upper)
        if match:
            return (0, int(match.group(1)))
        if "5+" in name_upper:
            return (0, 5.5)
        return (0, 999)
    if "卫视" in name:
        return (1, name)
    return (2, name)


# ==================== 工具函数 ====================
def build_logo_url(name):
    return f"{LOGO_BASE_URL}{quote(name, safe='')}.png"


def build_m3u8_entry(name, url):
    group = get_channel_group(name)
    logo = build_logo_url(name)
    return f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}\n{url}'


def get_remaining_timeout(deadline, fallback):
    if deadline is None:
        return fallback
    remaining = deadline - time.time()
    return min(fallback, remaining) if remaining > 0 else 0


def get_ts_url(m3u8_url, deadline=None):
    try:
        timeout = get_remaining_timeout(deadline, 5)
        if timeout <= 0:
            return None
        resp = requests.get(m3u8_url, timeout=timeout)
        if resp.status_code != 200:
            return None
        for line in resp.text.strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                if line.startswith('http'):
                    return line
                elif line.startswith('/'):
                    base = m3u8_url.split('/')[0] + "//" + m3u8_url.split('/')[2]
                    return base + line
                else:
                    return m3u8_url.rsplit('/', 1)[0] + "/" + line
    except Exception:
        pass
    return None


def get_download_speed(url, deadline=None):
    try:
        timeout = get_remaining_timeout(deadline, 10)
        if timeout <= 0:
            return -1
        start = time.time()
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            size = 0
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    size += len(chunk)
                if size > 10 * 1024 * 1024:
                    break
                if time.time() - start > 8:
                    break
                if deadline and time.time() > deadline:
                    break
        duration = time.time() - start
        if duration == 0:
            duration = 0.001
        return (size / 1024 / 1024) / duration
    except Exception:
        return -1


# ==================== 测速 + 获取频道 ====================
def test_host_speed(item):
    """测速单个源，返回 (speed, channels)"""
    host = item.get('host', '')
    match_type = item.get('matchType', '')
    if not host:
        return -1, []

    speed = -1
    channels = []
    deadline = time.time() + HOST_SPEED_TEST_TIMEOUT

    def timed_out():
        return time.time() > deadline

    try:
        if match_type == 'txiptv':
            if timed_out():
                return -1, []
            json_url = f"http://{host}/iptv/live/1000.json?key=txiptv"
            timeout = get_remaining_timeout(deadline, 3)
            if timeout <= 0:
                return -1, []
            resp = requests.get(json_url, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                valid_url = None
                if 'data' in data:
                    for d in data['data']:
                        if not isinstance(d, dict):
                            continue
                        name = d.get('name')
                        urlx = d.get('url')
                        if not name or not urlx or ',' in urlx:
                            continue
                        full_url = urlx if 'http' in urlx else f"http://{host}{'/' if not urlx.startswith('/') else ''}{urlx}"
                        channels.append({'name': name, 'url': full_url})
                        if not valid_url:
                            valid_url = full_url
                if valid_url and not timed_out():
                    ts_url = get_ts_url(valid_url, deadline)
                    if ts_url:
                        speed = get_download_speed(ts_url, deadline)

        elif match_type == 'hsmdtv':
            if timed_out():
                return -1, []
            test_url = f"http://{host}{HSMDTV_TEST_URI}"
            ts_url = get_ts_url(test_url, deadline)
            if ts_url:
                speed = get_download_speed(ts_url, deadline)

        elif match_type == 'jsmpeg':
            if timed_out():
                return -1, []
            json_url = f"http://{host}/streamer/list"
            timeout = get_remaining_timeout(deadline, 3)
            if timeout <= 0:
                return -1, []
            resp = requests.get(json_url, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                valid_url = None
                for d in data:
                    name = d.get('name', '').strip()
                    key = d.get('key', '').strip()
                    if not name or not key:
                        continue
                    full_url = f"http://{host}/hls/{key}/index.m3u8"
                    channels.append({'name': name, 'url': full_url})
                    if not valid_url:
                        valid_url = full_url
                if valid_url and not timed_out():
                    ts_url = get_ts_url(valid_url, deadline)
                    if ts_url:
                        speed = get_download_speed(ts_url, deadline)

        elif match_type == 'zhgxtv':
            if timed_out():
                return -1, []
            interface_url = f"http://{host}/ZHGXTV/Public/json/live_interface.txt"
            timeout = get_remaining_timeout(deadline, 5)
            if timeout <= 0:
                return -1, []
            resp = requests.get(interface_url, timeout=timeout)
            if resp.status_code == 200:
                valid_url = None
                for line in resp.text.split('\n'):
                    line = line.strip()
                    if ',' not in line:
                        continue
                    parts = line.split(',')
                    if len(parts) < 2:
                        continue
                    name = parts[0].strip()
                    url_part = parts[1].strip()
                    try:
                        if url_part.startswith("http"):
                            p = urlparse(url_part)
                            full_url = f"{p.scheme}://{host}{p.path}"
                            if p.query:
                                full_url += f"?{p.query}"
                        elif url_part.startswith("/"):
                            full_url = f"http://{host}{url_part}"
                        else:
                            full_url = f"http://{host}/{url_part}"
                        channels.append({'name': name, 'url': full_url})
                        if not valid_url:
                            valid_url = full_url
                    except Exception:
                        continue
                if valid_url and not timed_out():
                    ts_url = get_ts_url(valid_url, deadline)
                    if ts_url:
                        speed = get_download_speed(ts_url, deadline)
    except Exception:
        pass

    return speed, channels


# ==================== 主流程 ====================
def main():
    print("=" * 60)
    print("IPTV 播放列表生成器")
    print("=" * 60)

    # 1. 获取源列表
    print("\n[1/4] 获取源列表...")
    results = []
    for attempt in range(3):
        try:
            resp = requests.get(API_URL, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                break
        except Exception as e:
            print(f"  尝试 {attempt+1} 失败: {e}")
        time.sleep(3)

    if not results:
        print("  获取源列表失败，退出")
        sys.exit(1)

    print(f"  获取到 {len(results)} 个源")

    # 2. 并行测速
    print(f"\n[2/4] 测速筛选（最低 {MIN_SPEED_MBPS}MB/s，最多取 {TOP_N} 个）...")
    results_with_speed = []
    total = len(results)
    completed = 0
    valid = 0

    for i in range(0, total, SPEED_TEST_BATCH_SIZE):
        batch = results[i:i + SPEED_TEST_BATCH_SIZE]
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_item = {executor.submit(test_host_speed, item): item for item in batch}
            pending = set(future_to_item.keys())
            while pending:
                done, _ = wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)
                for future in done:
                    pending.discard(future)
                    item = future_to_item[future]
                    try:
                        speed, _ = future.result()
                        if speed > 0:
                            valid += 1
                            results_with_speed.append({
                                'host': item['host'],
                                'matchType': item['matchType'],
                                'source': item.get('source', 'N/A'),
                                'speed': speed,
                            })
                    except Exception:
                        pass
                    completed += 1
                    pct = completed / total * 100
                    print(f"\r  进度: {completed}/{total} ({pct:.0f}%) 有效: {valid}", end="", flush=True)

    print()

    # 3. 筛选优质源
    valid_results = [r for r in results_with_speed if r['speed'] > MIN_SPEED_MBPS]
    valid_results.sort(key=lambda x: x['speed'], reverse=True)

    final_sources = []
    selected_hosts = set()
    required_matches = ['txiptv', 'hsmdtv', 'zhgxtv', 'jsmpeg']

    for m in required_matches:
        for res in valid_results:
            if res['matchType'] == m and res['host'] not in selected_hosts:
                final_sources.append(res)
                selected_hosts.add(res['host'])
                break

    for res in valid_results:
        if len(final_sources) >= TOP_N:
            break
        if res['host'] not in selected_hosts:
            final_sources.append(res)
            selected_hosts.add(res['host'])

    final_sources.sort(key=lambda x: x['speed'], reverse=True)

    if len(final_sources) < 1:
        print("  没有找到可用源，退出")
        sys.exit(1)

    print(f"  选中 {len(final_sources)} 个优质源:")
    for idx, s in enumerate(final_sources):
        print(f"    源{idx+1}: {s['host']} ({s['matchType']}) {s['speed']:.2f}MB/s")

    # 4. 获取频道并生成播放列表
    print(f"\n[3/4] 获取频道列表...")
    all_entries = []

    for idx, source in enumerate(final_sources):
        host = source['host']
        match_type = source['matchType']
        print(f"  获取频道: 源{idx+1} {host} ({match_type})...")
        _, channels = test_host_speed({'host': host, 'matchType': match_type})
        for ch in (channels or []):
            name = clean_channel_name(ch['name'])
            all_entries.append({'name': name, 'url': ch['url'], 'index': idx})

    print(f"  共获取 {len(all_entries)} 个频道条目")

    # 分组去重
    grouped = {}
    for entry in all_entries:
        name = entry['name']
        if name not in grouped:
            grouped[name] = []
        if not any(e['url'] == entry['url'] for e in grouped[name]):
            grouped[name].append(entry)

    # 排序
    sorted_names = sorted(grouped.keys(), key=channel_sort_key)

    # 生成 M3U8
    update_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    m3u8_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"', f"#EXT-X-UPDATED: {update_time}"]
    for name in sorted_names:
        entries = sorted(grouped[name], key=lambda x: x['index'])
        for entry in entries:
            m3u8_lines.append(build_m3u8_entry(entry['name'], entry['url']))
    m3u8_content = "\n".join(m3u8_lines)

    # 生成 TXT
    txt_lines = []
    for name in sorted_names:
        entries = sorted(grouped[name], key=lambda x: x['index'])
        group = get_channel_group(name)
        for entry in entries:
            txt_lines.append(f"{entry['name']},{entry['url']},{group}")
    txt_content = "\n".join(txt_lines)

    # 输出文件
    output_dir = os.environ.get("GITHUB_OUTPUT_DIR", os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(output_dir, exist_ok=True)

    m3u8_path = os.path.join(output_dir, "iptv_sources.m3u8")
    txt_path = os.path.join(output_dir, "iptv_sources.txt")

    with open(m3u8_path, "w", encoding="utf-8") as f:
        f.write(m3u8_content)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(txt_content)

    print(f"\n[4/4] 生成完成!")
    print(f"  M3U8: {m3u8_path} ({len(m3u8_lines)} 行)")
    print(f"  TXT:  {txt_path} ({len(txt_lines)} 行)")
    print(f"  频道数: {len(sorted_names)}")
    print(f"  更新时间: {update_time}")

    # 输出到 GITHUB_OUTPUT（供后续步骤使用）
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"m3u8_path={m3u8_path}\n")
            f.write(f"txt_path={txt_path}\n")
            f.write(f"update_time={update_time}\n")
            f.write(f"channel_count={len(sorted_names)}\n")

    return m3u8_content, txt_content, update_time


if __name__ == "__main__":
    main()
