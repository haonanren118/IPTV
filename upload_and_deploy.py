#!/usr/bin/env python3
"""
IPTV 播放列表自动更新脚本（增强版）
优先从远程 API 抓取 IPTV 源（测速选优），异常时自动降级读取本地 ZB.txt
供飞牛 NAS Docker 容器定时运行
"""

import requests
import os
import re
import time
import gc
from urllib.parse import quote, urlparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

# ==================== 配置 ====================
UPLOAD_URL = os.environ.get("UPLOAD_URL", "https://iptv-bfo.pages.dev/api/upload")
ZB_FILE = os.environ.get("ZB_FILE", "/app/ZB.txt")
EPG_URL = os.environ.get("EPG_URL", "https://epg.112114.xyz/pp.xml")
LOGO_BASE_URL = "https://ghfast.top/https://raw.githubusercontent.com/Jarrey/iptv_logo/main/tv/"
UPLOAD_TOKEN = os.environ.get("CF_KV_TOKEN", "") or os.environ.get("API_KEY", "")

# 远程源配置
API_URL = "https://iptvs.pes.im"
TOP_N = 5
MAX_WORKERS = 20
HOST_SPEED_TEST_TIMEOUT = 15
SPEED_TEST_BATCH_SIZE = 60
HSMD_ADDRESS_LIST_FILE = os.environ.get("HSMD_ADDRESS_LIST_FILE", "/app/hsmd_address_list.txt")
ZHGXTV_INTERFACE = "/ZHGXTV/Public/json/live_interface.txt"
HSMDTV_TEST_URI = "/newlive/live/hls/1/live.m3u8"

# 分组定义（按显示顺序）
GROUP_ORDER = [
    "央视频道", "卫视频道", "电影频道", "儿童频道",
    "体育频道", "纪录频道", "音乐频道", "地方频道",
    "数字频道", "解说频道", "春晚频道", "直播中国", "其他"
]


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


# ==================== 远程源抓取逻辑（复用 app.py 核心） ====================

def _get_remaining_timeout(deadline, fallback_timeout):
    if deadline is None:
        return fallback_timeout
    remaining = deadline - time.time()
    return min(fallback_timeout, remaining) if remaining > 0 else 0


def fetch_api_data():
    """从远程 API 获取 IPTV 源列表，带重试"""
    for attempt in range(3):
        try:
            log(f"抓取远程源 (第{attempt+1}次)...")
            response = requests.get(API_URL, timeout=10)
            if response.status_code == 200:
                data = response.json()
                log(f"✅ 远程源获取成功，共 {len(data.get('results', []))} 个源")
                return data
        except Exception as e:
            log(f"⚠️ 远程源获取失败: {e}")
        time.sleep(3)
    return None


def get_ts_url(m3u8_url, deadline=None):
    """解析 m3u8 获取第一个 TS 分片 URL"""
    try:
        request_timeout = _get_remaining_timeout(deadline, 5)
        if request_timeout <= 0:
            return None
        response = requests.get(m3u8_url, timeout=request_timeout)
        if response.status_code != 200:
            return None
        for line in response.text.strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                if line.startswith('http'):
                    return line
                elif line.startswith('/'):
                    base = m3u8_url.split('/')[0] + "//" + m3u8_url.split('/')[2]
                    return base + line
                else:
                    return m3u8_url.rsplit('/', 1)[0] + "/" + line
        return None
    except Exception:
        return None


def get_download_speed(url, deadline=None):
    """测量下载速度 (MB/s)，失败返回 -1"""
    try:
        request_timeout = _get_remaining_timeout(deadline, 10)
        if request_timeout <= 0:
            return -1
        start_time = time.time()
        with requests.get(url, stream=True, timeout=request_timeout) as r:
            r.raise_for_status()
            size = 0
            chunk_size = 8192
            limit_size = 10 * 1024 * 1024
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    size += len(chunk)
                if size > limit_size:
                    break
                if time.time() - start_time > 8:
                    break
                if deadline is not None and time.time() > deadline:
                    break
        duration = time.time() - start_time
        if duration == 0:
            duration = 0.001
        return (size / 1024 / 1024) / duration
    except Exception:
        return -1


def test_host_speed(item, fetch_channels=False):
    """测试单个源的速度，返回 (speed, channels)"""
    host = item.get('host')
    match_type = item.get('matchType')
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
                return -1, channels
            json_url = f"http://{host}/iptv/live/1000.json?key=txiptv"
            try:
                request_timeout = _get_remaining_timeout(deadline, 2)
                if request_timeout <= 0:
                    return -1, channels
                response = requests.get(json_url, timeout=request_timeout)
                if response.status_code == 200:
                    json_data = response.json()
                    valid_channel_url = None
                    if 'data' in json_data:
                        for it in json_data['data']:
                            if isinstance(it, dict):
                                name = it.get('name')
                                urlx = it.get('url')
                                if not name or not urlx or ',' in urlx:
                                    continue
                                full_url = urlx if 'http' in urlx else (
                                    f"http://{host}{urlx}" if urlx.startswith('/') else f"http://{host}/{urlx}"
                                )
                                if fetch_channels:
                                    channels.append({'name': name, 'url': full_url})
                                if not valid_channel_url:
                                    valid_channel_url = full_url
                    if valid_channel_url and not timed_out():
                        ts_url = get_ts_url(valid_channel_url, deadline=deadline)
                        if ts_url:
                            speed = get_download_speed(ts_url, deadline=deadline)
            except Exception:
                speed = -1

        elif match_type == 'hsmdtv':
            if timed_out():
                return -1, channels
            test_url = f"http://{host}{HSMDTV_TEST_URI}"
            ts_url = get_ts_url(test_url, deadline=deadline)
            if ts_url:
                speed = get_download_speed(ts_url, deadline=deadline)

        elif match_type == 'jsmpeg':
            if timed_out():
                return -1, channels
            json_url = f"http://{host}/streamer/list"
            try:
                request_timeout = _get_remaining_timeout(deadline, 2)
                if request_timeout <= 0:
                    return -1, channels
                response = requests.get(json_url, timeout=request_timeout)
                if response.status_code == 200:
                    json_data = response.json()
                    valid_channel_url = None
                    for it in json_data:
                        name = it.get('name', '').strip()
                        key = it.get('key', '').strip()
                        if not name or not key:
                            continue
                        full_url = f"http://{host}/hls/{key}/index.m3u8"
                        if fetch_channels:
                            channels.append({'name': name, 'url': full_url})
                        if not valid_channel_url:
                            valid_channel_url = full_url
                    if valid_channel_url and not timed_out():
                        ts_url = get_ts_url(valid_channel_url, deadline=deadline)
                        if ts_url:
                            speed = get_download_speed(ts_url, deadline=deadline)
            except Exception:
                speed = -1

        elif match_type == 'zhgxtv':
            if timed_out():
                return -1, channels
            interface_url = f"http://{host}{ZHGXTV_INTERFACE}"
            request_timeout = _get_remaining_timeout(deadline, 5)
            if request_timeout <= 0:
                return -1, channels
            target_response = requests.get(interface_url, timeout=request_timeout)
            if target_response.status_code == 200:
                content = target_response.content.decode('utf-8', errors='ignore')
                valid_channel_url = None
                for line in content.split('\n'):
                    line = line.strip()
                    if ',' in line:
                        parts = line.split(',', 2)
                        if len(parts) >= 2:
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
                                if fetch_channels:
                                    channels.append({'name': name, 'url': full_url})
                                if not valid_channel_url:
                                    valid_channel_url = full_url
                            except Exception:
                                continue
                if valid_channel_url and not timed_out():
                    ts_url = get_ts_url(valid_channel_url, deadline=deadline)
                    if ts_url:
                        speed = get_download_speed(ts_url, deadline=deadline)
    except Exception:
        speed = -1

    return speed, channels


def fetch_channels_for_source(source):
    """获取指定源的所有频道"""
    match_type = source.get('matchType')
    if match_type in ('txiptv', 'jsmpeg', 'zhgxtv'):
        _, channels = test_host_speed(
            {'host': source.get('host'), 'matchType': match_type},
            fetch_channels=True
        )
        source['channels'] = channels or []


def clean_channel_name(name):
    """清洗和标准化频道名称"""
    name = name.replace("cctv", "CCTV").replace("中央", "CCTV").replace("央视", "CCTV")
    for rep in ["高清", "超高", "HD", "标清", "频道", "-", " ", "PLUS", "＋", "(", ")"]:
        name = name.replace(rep, "" if rep not in ["PLUS", "＋"] else "+")
    name = re.sub(r"CCTV(\d+)台", r"CCTV\1", name)
    name_map = {
        "CCTV1综合": "CCTV1", "CCTV2财经": "CCTV2", "CCTV3综艺": "CCTV3",
        "CCTV4国际": "CCTV4", "CCTV4中文国际": "CCTV4", "CCTV5体育": "CCTV5",
        "CCTV6电影": "CCTV6", "CCTV7军事": "CCTV7", "CCTV7军农": "CCTV7",
        "CCTV7农业": "CCTV7", "CCTV7国防军事": "CCTV7", "CCTV8电视剧": "CCTV8",
        "CCTV9记录": "CCTV9", "CCTV9纪录": "CCTV9", "CCTV10科教": "CCTV10",
        "CCTV11戏曲": "CCTV11", "CCTV12社会与法": "CCTV12", "CCTV13新闻": "CCTV13",
        "CCTV新闻": "CCTV13", "CCTV14少儿": "CCTV14", "CCTV15音乐": "CCTV15",
        "CCTV16奥林匹克": "CCTV16", "CCTV17农业农村": "CCTV17", "CCTV17农业": "CCTV17",
        "CCTV5+体育赛视": "CCTV5+", "CCTV5+体育赛事": "CCTV5+", "CCTV5+体育": "CCTV5+",
    }
    return name_map.get(name, name)


# ==================== 分组 & 排序 & 生成（本地/远程共用） ====================

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
        "石家庄", "唐山", "邯郸", "保定", "张家口", "承德", "沧州", "廊坊",
        "太原", "大同", "长治", "晋城", "运城",
        "济南", "青岛", "烟台", "潍坊", "济宁", "临沂", "德州", "聊城",
        "南京", "苏州", "无锡", "常州", "南通", "扬州", "徐州", "连云港", "淮安",
        "杭州", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "台州", "丽水",
        "合肥", "芜湖", "蚌埠", "马鞍山", "淮南", "安庆", "黄山", "六安", "亳州",
        "福州", "厦门", "莆田", "三明", "泉州", "漳州", "南平", "龙岩", "宁德",
        "南昌", "景德镇", "九江", "赣州", "吉安", "宜春", "抚州", "上饶",
        "武汉", "宜昌", "襄阳", "荆门", "荆州", "黄冈", "咸宁", "恩施",
        "长沙", "株洲", "湘潭", "衡阳", "邵阳", "岳阳", "常德", "张家界", "郴州",
        "广州", "深圳", "珠海", "汕头", "佛山", "东莞", "中山", "惠州", "湛江",
        "南宁", "柳州", "桂林", "梧州", "北海", "玉林",
        "海口", "三亚", "成都", "绵阳", "德阳", "乐山", "南充", "眉山", "宜宾",
        "贵阳", "遵义", "安顺", "毕节", "铜仁",
        "昆明", "曲靖", "玉溪", "丽江", "大理",
        "西安", "宝鸡", "咸阳", "渭南", "延安", "汉中",
        "兰州", "天水", "张掖", "酒泉", "庆阳",
        "西宁", "银川", "乌鲁木齐", "长春", "吉林", "沈阳", "大连", "哈尔滨",
        "呼和浩特", "包头", "拉萨",
        "BTV", "公共", "都市", "生活", "文化", "民生", "经济", "新闻",
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


def channel_sort_key(name):
    """频道排序：CCTV 数字优先，然后卫视，然后其他"""
    name_upper = name.upper()
    if "CCTV" in name_upper:
        match = re.search(r"CCTV(\d+)", name_upper)
        if match:
            return (0, int(match.group(1)))
        if "5+" in name_upper or "5PLUS" in name_upper:
            return (0, 5.5)
        return (0, 999)
    if "CGTN" in name_upper:
        return (1, name)
    if "卫视" in name:
        return (2, name)
    return (3, name)


def build_logo_url(name):
    return f"{LOGO_BASE_URL}{quote(name, safe='')}.png"


def build_m3u8_entry(name, url, group_title=None):
    if group_title is None:
        group_title = get_channel_group(name)
    logo_url = build_logo_url(name)
    return f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo_url}" group-title="{group_title}",{name}\n{url}'


# ==================== 远程源：抓取 + 测速 + 生成 ====================

def fetch_remote_sources():
    """
    从远程 API 抓取 IPTV 源，测速选优，返回 (m3u8_content, txt_content)
    失败返回 None
    """
    data = fetch_api_data()
    if not data or not isinstance(data, dict) or "results" not in data:
        return None

    result = data["results"]
    if not result:
        return None

    # 并行测速
    results_with_speed = []
    total_hosts = len(result)
    completed_hosts = 0
    valid_hosts = 0
    log(f"开始测速 {total_hosts} 个源...")

    for i in range(0, len(result), SPEED_TEST_BATCH_SIZE):
        batch = result[i:i + SPEED_TEST_BATCH_SIZE]
        executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        try:
            future_to_item = {executor.submit(test_host_speed, item): item for item in batch}
            future_start_time = {future: time.time() for future in future_to_item}
            pending = set(future_to_item.keys())

            while pending:
                done, _ = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
                for future in done:
                    pending.discard(future)
                    item = future_to_item[future]
                    try:
                        speed, _ = future.result()
                        if speed > 0:
                            valid_hosts += 1
                            results_with_speed.append({
                                'host': item['host'],
                                'matchType': item['matchType'],
                                'source': item.get('source', 'N/A'),
                                'speed': speed,
                                'channels': []
                            })
                    except Exception:
                        pass
                    finally:
                        completed_hosts += 1
                        if completed_hosts % 10 == 0 or completed_hosts == total_hosts:
                            log(f"测速进度: {completed_hosts}/{total_hosts} (有效: {valid_hosts})")

                now = time.time()
                timed_out_futures = [
                    f for f in list(pending)
                    if now - future_start_time.get(f, now) > HOST_SPEED_TEST_TIMEOUT
                ]
                for f in timed_out_futures:
                    pending.discard(f)
                    f.cancel()
                    completed_hosts += 1
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    log(f"测速完成: {valid_hosts}/{total_hosts} 个有效源")

    # 筛选速度 > 1.5 MB/s 的源
    valid_results = [r for r in results_with_speed if r['speed'] > 1.5]
    valid_results.sort(key=lambda x: x['speed'], reverse=True)

    # 确保每种类型至少选一个
    final_sources = []
    selected_hosts = set()
    for m in ['txiptv', 'hsmdtv', 'zhgxtv', 'jsmpeg']:
        for res in valid_results:
            if res['matchType'] == m and res['host'] not in selected_hosts:
                final_sources.append(res)
                selected_hosts.add(res['host'])
                break

    # 填充剩余（按速度排序）
    for res in valid_results:
        if len(final_sources) >= TOP_N:
            break
        if res['host'] not in selected_hosts:
            final_sources.append(res)
            selected_hosts.add(res['host'])

    final_sources.sort(key=lambda x: x['speed'], reverse=True)

    if len(final_sources) < 3:
        log(f"⚠️ 有效源不足 ({len(final_sources)} < 3)，放弃远程源")
        return None

    log(f"选中 Top {len(final_sources)} 源:")
    for idx, src in enumerate(final_sources):
        log(f"  源{idx+1}: {src['host']} ({src['matchType']}) {src['speed']:.2f}MB/s")

    # 抓取频道
    all_entries = []
    for idx, source in enumerate(final_sources):
        log(f"抓取频道: 源{idx+1} {source['host']} ({source['matchType']})...")
        fetch_channels_for_source(source)

        match_type = source['matchType']
        channels = source.get('channels', [])

        if match_type == 'hsmdtv':
            # hsmdtv 需要从 hsmd_address_list.txt 生成频道
            entries = process_hsmdtv_channels(source['host'], idx)
        elif channels:
            for ch in channels:
                name = clean_channel_name(ch['name'])
                group = get_channel_group(name)
                all_entries.append({
                    'name': name, 'url': ch['url'], 'group': group,
                    'content': build_m3u8_entry(name, ch['url'], group),
                    'index': idx
                })
            continue
        else:
            continue

        all_entries.extend(entries)

    if not all_entries:
        log("⚠️ 远程源未抓取到任何频道")
        return None

    log(f"远程源共抓取到 {len(all_entries)} 条频道记录")

    # 按频道名分组（同名频道保留多个源）
    grouped = {}
    for entry in all_entries:
        name = entry['name']
        if name not in grouped:
            grouped[name] = []
        grouped[name].append(entry)

    # 排序频道名
    unique_names = sorted(grouped.keys(), key=channel_sort_key)

    # 生成 M3U8
    update_time = time.strftime("%Y/%m/%d %H:%M:%S")
    m3u8_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"', f"#EXT-X-UPDATED: {update_time}"]
    for name in unique_names:
        entries_list = sorted(grouped[name], key=lambda x: x['index'])
        for entry in entries_list:
            m3u8_lines.append(entry['content'])

    # 生成 TXT
    txt_lines = []
    for name in unique_names:
        entries_list = sorted(grouped[name], key=lambda x: x.get('index', 999))
        group = entries_list[0]['group']
        txt_lines.append(f"{name},{entries_list[0]['url']},{group}")

    m3u8_content = "\n".join(m3u8_lines)
    txt_content = "\n".join(txt_lines)

    del results_with_speed, valid_results, final_sources, all_entries, grouped
    gc.collect()

    return m3u8_content, txt_content


def process_hsmdtv_channels(host, source_index):
    """处理 hsmdtv 源频道"""
    entries = []
    try:
        if not os.path.exists(HSMD_ADDRESS_LIST_FILE):
            log(f"⚠️ {HSMD_ADDRESS_LIST_FILE} 不存在，跳过 hsmdtv 源")
            return entries
        with open(HSMD_ADDRESS_LIST_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = re.search(r'(http://[^\s]+)', line)
            if match:
                url_in_file = match.group(1)
                part_before_url = line.split(url_in_file)[0]
                name = re.sub(r'^\s*\d+\s+', '', part_before_url).strip()
                name = name.replace("（默认频道）", "").strip()
                name = clean_channel_name(name)
                parsed = urlparse(url_in_file)
                new_url = f"http://{host}{parsed.path}"
                group = get_channel_group(name)
                entries.append({
                    'name': name, 'url': new_url, 'group': group,
                    'content': build_m3u8_entry(name, new_url, group),
                    'index': source_index
                })
    except Exception as e:
        log(f"⚠️ 处理 hsmdtv 频道失败: {e}")
    return entries


# ==================== 本地降级：读取 ZB.txt ====================

def fetch_local_sources():
    """
    从 ZB.txt 读取本地频道，返回 (m3u8_content, txt_content)
    失败返回 None
    """
    if not os.path.exists(ZB_FILE):
        log(f"⚠️ 本地文件 {ZB_FILE} 不存在")
        return None

    channels_by_group = {g: {} for g in GROUP_ORDER}

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
            if group not in channels_by_group:
                group = "其他"

            if name not in channels_by_group[group]:
                channels_by_group[group][name] = []
            if url not in channels_by_group[group][name]:
                channels_by_group[group][name].append(url)

    total = sum(len(channels_by_group[g]) for g in GROUP_ORDER)
    if total == 0:
        log("⚠️ ZB.txt 中没有有效频道")
        return None

    log(f"📋 从 ZB.txt 读取到 {total} 个频道（降级模式）")

    update_time = time.strftime("%Y/%m/%d %H:%M:%S")
    m3u8_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"', f"#EXT-X-UPDATED: {update_time}"]

    for group in GROUP_ORDER:
        if not channels_by_group[group]:
            continue
        m3u8_lines.append(f"#EXTINF:-1 group-title=\"{group}\",{group}")
        sorted_names = sorted(channels_by_group[group].keys(), key=channel_sort_key)
        for name in sorted_names:
            logo = build_logo_url(name)
            for url in channels_by_group[group][name]:
                m3u8_lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}')
                m3u8_lines.append(url)

    txt_lines = []
    for group in GROUP_ORDER:
        if not channels_by_group[group]:
            continue
        txt_lines.append(f"{group},#genre#")
        sorted_names = sorted(channels_by_group[group].keys(), key=channel_sort_key)
        for name in sorted_names:
            for url in channels_by_group[group][name]:
                txt_lines.append(f"{name},{url}")
        txt_lines.append("")

    return "\n".join(m3u8_lines), "\n".join(txt_lines)


# ==================== 上传到 CF KV ====================

def upload_to_cf_kv(m3u8_content, txt_content, update_time, source="local"):
    if not UPLOAD_TOKEN:
        log("⚠️ Token 为空! 未读取到 CF_KV_TOKEN 或 API_KEY 环境变量")
        return False
    try:
        payload = {
            "m3u8": m3u8_content,
            "txt": txt_content,
            "last_update": update_time,
            "source": source,
        }
        headers = {"Content-Type": "application/json"}
        if UPLOAD_TOKEN:
            headers["Authorization"] = f"Bearer {UPLOAD_TOKEN}"
        log(f"上传到 CF KV ({UPLOAD_URL}) [source={source}]...")
        resp = requests.post(UPLOAD_URL, json=payload, headers=headers, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            log(f"✅ 上传成功! 更新时间: {data.get('last_update', update_time)}")
            return True
        else:
            log(f"❌ 上传失败: HTTP {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        log(f"❌ 上传异常: {e}")
        return False


# ==================== 主流程 ====================

def main():
    log("=" * 50)
    log("IPTV 播放列表自动更新（远程优先 + 本地降级）")
    log("=" * 50)

    m3u8_content = None
    txt_content = None
    data_source = None

    # 第一步：尝试远程抓取
    try:
        result = fetch_remote_sources()
        if result:
            m3u8_content, txt_content = result
            data_source = "remote"
    except Exception as e:
        log(f"❌ 远程抓取异常: {e}")

    # 第二步：远程失败，降级到 ZB.txt
    if not m3u8_content:
        log("⚠️ 远程源获取失败，降级使用本地 ZB.txt...")
        try:
            result = fetch_local_sources()
            if result:
                m3u8_content, txt_content = result
                data_source = "local"
        except Exception as e:
            log(f"❌ 本地读取异常: {e}")

    # 第三步：都没有数据，退出
    if not m3u8_content:
        log("❌ 远程源和本地 ZB.txt 均无数据，本次更新跳过")
        return False

    log(f"📊 数据来源: {'远程源' if data_source == 'remote' else '本地 ZB.txt'}")
    log(f"   M3U8: {len(m3u8_content)} 字节, TXT: {len(txt_content)} 字节")

    # 第四步：上传到 CF KV
    update_time = time.strftime("%Y/%m/%d %H:%M:%S")
    source_label = "local"  # NAS 上传统一用 local 标识
    success = upload_to_cf_kv(m3u8_content, txt_content, update_time, source_label)

    if success:
        log(f"🎉 更新完成! [{data_source}]")
    else:
        log(f"💔 更新失败")

    return success


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
