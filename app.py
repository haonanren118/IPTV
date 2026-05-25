from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import time
import os
import sys
import re
import gc
import atexit
import socket
import signal
import subprocess
import threading
from urllib.parse import urlparse, quote
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

VERSION = "1.0.4"

def check_for_updates():
    try:
        response = requests.get("https://iptvs.pes.im/message", timeout=5)
        if response.status_code == 200:
            data = response.json()
            remote_version = data.get("version")
            if remote_version and remote_version > VERSION:
                print(f"New version {remote_version} found! Current version is {VERSION}. Downloading...")
                code_response = requests.get("https://iptvs.pes.im/latest", timeout=10)
                if code_response.status_code == 200:
                    with open(__file__, 'wb') as f:
                        f.write(code_response.content)
                    print("Update successful. Restarting...")
                    os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        print(f"Failed to check for updates: {e}")

# Set Timezone to Asia/Shanghai for Docker environment
if os.name != 'nt':  # Only on Unix-like systems (Docker usually runs Linux)
    os.environ['TZ'] = 'Asia/Shanghai'
    try:
        time.tzset()
    except Exception:
        pass

app = Flask(__name__)

# Constants
API_URL = "https://iptvs.pes.im"
CACHE_FILE = "iptv_sources.m3u8"
TXT_CACHE_FILE = "iptv_sources.txt"
CHANNEL_LIST_FILE = "channel_list.txt"
ADDRESS_LIST_FILE = "address_list.txt"
HSMD_ADDRESS_LIST_FILE = "hsmd_address_list.txt"
ZHGXTV_INTERFACE = "/ZHGXTV/Public/json/live_interface.txt"
TXIPTV_TEST_URI = "/tsfile/live/0001_1.m3u8"
HSMDTV_TEST_URI = "/newlive/live/hls/1/live.m3u8"
MAX_WORKERS = 20
TOP_N = 5
HOST_SPEED_TEST_TIMEOUT = 15
SPEED_TEST_BATCH_SIZE = 60
EPG_URL = "https://epg.zsdc.eu.org/t.xml"
LOGO_BASE_URL = "https://ghfast.top/https://raw.githubusercontent.com/Jarrey/iptv_logo/main/tv/"
APP_PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.pid")


def _read_pid_file():
    try:
        if not os.path.exists(APP_PID_FILE):
            return None
        with open(APP_PID_FILE, "r", encoding="utf-8") as f:
            pid_text = f.read().strip()
            if not pid_text:
                return None
            return int(pid_text)
    except Exception:
        return None


def _write_pid_file(pid):
    with open(APP_PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(pid))


def _cleanup_pid_file():
    try:
        pid_in_file = _read_pid_file()
        if pid_in_file == os.getpid() and os.path.exists(APP_PID_FILE):
            os.remove(APP_PID_FILE)
    except Exception:
        pass


def _is_process_alive(pid):
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _terminate_process(pid):
    if pid is None or pid <= 0:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F", "/T"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


def _can_bind_port(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def takeover_previous_instance(bind_host, bind_port):
    current_pid = os.getpid()
    old_pid = _read_pid_file()
    if old_pid and old_pid != current_pid and _is_process_alive(old_pid):
        print(f"Detected previous instance PID={old_pid}, stopping it...")
        _terminate_process(old_pid)

    for _ in range(20):
        if _can_bind_port(bind_host, bind_port):
            return True
        time.sleep(0.5)

    return _can_bind_port(bind_host, bind_port)


def _get_remaining_timeout(deadline, fallback_timeout):
    if deadline is None:
        return fallback_timeout
    remaining = deadline - time.time()
    if remaining <= 0:
        return 0
    return min(fallback_timeout, remaining)

global_m3u8_content = ""
global_txt_content = ""
last_run_time = "Never"
is_running = False
scheduled_task_lock = threading.Lock()


def print_speed_test_progress(completed, total, success_count):
    if total <= 0:
        return
    bar_width = 30
    ratio = completed / total
    filled = int(bar_width * ratio)
    bar = "=" * filled + "-" * (bar_width - filled)
    percent = ratio * 100
    print(f"\r测速进度 [{bar}] {completed}/{total} ({percent:5.1f}%) 有效源: {success_count}", end="", flush=True)


def build_logo_url(channel_name):
    return f"{LOGO_BASE_URL}{quote(channel_name, safe='')}.png"


def get_channel_group(name):
    """
    根据频道名称智能分组
    返回: 央视、卫视、地方台、其他
    """
    name_upper = name.upper()
    
    # 央视频道 (CCTV1-17, CCTV5+, CCTV新闻等)
    if "CCTV" in name_upper or "中央" in name or "央视" in name:
        return "央视"
    
    # 卫视频道列表
    satellite_keywords = [
        "卫视", "湖南", "浙江", "江苏", "东方", "北京", "山东", "广东", "深圳",
        "四川", "湖北", "河南", "河北", "安徽", "福建", "江西", "辽宁", "吉林",
        "黑龙江", "陕西", "山西", "贵州", "云南", "广西", "重庆", "天津", "上海",
        "甘肃", "内蒙古", "宁夏", "青海", "新疆", "西藏", "海南", "东南", "海峡",
        "厦门", "南方", "旅游", "教育", "少儿", "动漫", "音乐", "体育", "电影",
        "电视剧", "财经", "新闻", "综艺", "戏曲", "纪录", "国际", "军事", "农业"
    ]
    
    # 检查是否包含卫视关键词
    for keyword in satellite_keywords:
        if keyword in name:
            # 卫视频道
            if "卫视" in name:
                return "卫视"
            # 专业频道
            if keyword in ["体育", "电影", "电视剧", "财经", "新闻", "综艺", "戏曲", "纪录", "音乐", "动漫", "少儿", "教育", "国际", "军事", "农业", "旅游"]:
                return "专业频道"
    
    # 地方台（包含省份/城市名但不是卫视）
    province_keywords = [
        "福建", "厦门", "泉州", "福州", "漳州", "莆田", "三明", "南平", "龙岩", "宁德",
        "广州", "深圳", "珠海", "汕头", "佛山", "东莞", "中山", "惠州", "江门", "湛江",
        "成都", "武汉", "南京", "杭州", "苏州", "无锡", "宁波", "青岛", "大连", "沈阳",
        "西安", "郑州", "长沙", "南昌", "合肥", "昆明", "贵阳", "南宁", "海口", "兰州"
    ]
    
    for keyword in province_keywords:
        if keyword in name and "卫视" not in name:
            return "地方台"
    
    # CGTN 国际频道
    if "CGTN" in name_upper or "中国国际" in name:
        return "国际频道"
    
    # 默认分类
    return "其他"


def build_m3u8_entry(name, url, group_title=None):
    """
    构建 M3U8 条目
    如果未指定 group_title，则自动根据频道名称分组
    """
    if group_title is None:
        group_title = get_channel_group(name)
    logo_url = build_logo_url(name)
    return f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo_url}" group-title="{group_title}",{name}\n{url}'

def get_standard_channel_map():
    """Returns a dict mapping 'normalized' names to standard names from channel_list.txt."""
    mapping = {}
    try:
        if os.path.exists(CHANNEL_LIST_FILE):
            with open(CHANNEL_LIST_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    std_name = line.strip()
                    if not std_name: continue
                    # Normalize key: remove hyphens, spaces, uppercase
                    key = std_name.replace('-', '').replace(' ', '').upper()
                    # Also handle CCTV1 -> CCTV-1 specifically if standard is CCTV-1
                    # Actually standard name IS the value. Key is normalization.
                    mapping[key] = std_name
    except Exception as e:
        print(f"Error loading channel map: {e}")
    return mapping

def map_to_standard_name(name, mapping):
    """Maps a potentially variant name to a standard one if matches."""
    key = name.replace('-', '').replace(' ', '').upper()
    return mapping.get(key, name)

def fetch_api_data():
    """Fetches JSON data from the API with retry logic."""
    for attempt in range(3):
        try:
            print(f"Fetching API data (Attempt {attempt+1})...")
            response = requests.get(API_URL, timeout=10)
            if response.status_code == 200:
                print("API data fetched successfully.")
                return response.json()
        except Exception as e:
            print(f"API fetch error: {e}")
        time.sleep(5)
    print("API fetch failed after re-tries.")
    return []

def get_download_speed(url, deadline=None):
    """
    Measures download speed of a given URL (usually a TS file).
    Returns speed in MB/s. Returns -1 if failed.
    """
    try:
        request_timeout = _get_remaining_timeout(deadline, 10)
        if request_timeout <= 0:
            return -1

        start_time = time.time()
        # Download first 512KB is usually enough for speed test, but here let's follow ZHGXTV full download logic or chunk
        # ZHGXTV uses content length / time. Let's limit read size to avoid huge files.
        # But TS files are small chunks usually.
        with requests.get(url, stream=True, timeout=request_timeout) as r:
            r.raise_for_status()
            size = 0
            # Read at most 10MB for test to ensure accuracy over longer time
            chunk_size = 8192
            limit_size = 10 * 1024 * 1024
            
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    size += len(chunk)
                # Ensure we download enough data or for enough time
                if size > limit_size:
                    break
                # Or if time exceeds 8 seconds
                if time.time() - start_time > 8:
                    break
                if deadline is not None and time.time() > deadline:
                    break
        
        duration = time.time() - start_time
        if duration == 0: duration = 0.001
        
        speed = (size / 1024 / 1024) / duration # MB/s
        return speed
    except Exception:
        return -1

def get_ts_url(m3u8_url, deadline=None):
    """
    Parses m3u8 to find the first TS segment URL.
    Returns the full TS URL.
    """
    try:
        request_timeout = _get_remaining_timeout(deadline, 5)
        if request_timeout <= 0:
            return None
        response = requests.get(m3u8_url, timeout=request_timeout)
        if response.status_code != 200:
            return None
        
        lines = response.text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                # Handle relative or absolute URLs
                if line.startswith('http'):
                    return line
                elif line.startswith('/'):
                    # Absolute path
                    base = m3u8_url.split('/')[0] + "//" + m3u8_url.split('/')[2]
                    return base + line
                else:
                    # Relative path
                    base = m3u8_url.rsplit('/', 1)[0]
                    return base + "/" + line
        return None
    except:
        return None

def test_host_speed(item, fetch_channels=False):
    """
    Tests speed for a single host item.
    Returns (speed_mb_s, channels)
    """
    host = item.get('host')
    match_type = item.get('matchType')
    
    if not host:
        return -1, None
        
    speed = -1
    channels = []
    deadline = time.time() + HOST_SPEED_TEST_TIMEOUT

    def timed_out():
        return time.time() > deadline

    try:
        if match_type == 'txiptv':
            if timed_out():
                return -1, channels
            # Updated logic to use JSON API like iptv.py
            json_url = f"http://{host}/iptv/live/1000.json?key=txiptv"
            try:
                # Use short timeout for JSON fetch as per iptv.py logic (0.5s there, maybe generic 2s here)
                request_timeout = _get_remaining_timeout(deadline, 2)
                if request_timeout <= 0:
                    return -1, channels
                response = requests.get(json_url, timeout=request_timeout)
                if response.status_code == 200:
                    json_data = response.json()
                    valid_channel_url = None
                    
                    if 'data' in json_data:
                        for item in json_data['data']:
                            if isinstance(item, dict):
                                name = item.get('name')
                                urlx = item.get('url')
                                
                                if not name or not urlx:
                                    continue
                                
                                if ',' in urlx:
                                    continue

                                full_url = ""
                                if 'http' in urlx:
                                    full_url = urlx
                                else:
                                    if urlx.startswith('/'):
                                        full_url = f"http://{host}{urlx}" 
                                    else:
                                        full_url = f"http://{host}/{urlx}"

                                if fetch_channels:
                                    channels.append({'name': name, 'url': full_url})
                                
                                if not valid_channel_url:
                                    valid_channel_url = full_url

                    if valid_channel_url:
                        if timed_out():
                            return -1, channels
                        ts_url = get_ts_url(valid_channel_url, deadline=deadline)
                        if ts_url:
                            speed = get_download_speed(ts_url, deadline=deadline)
                    else:
                        speed = -1
                else:
                    speed = -1
            except Exception as e:
                # print(f"TXIPTV JSON fetch failed for {host}: {e}")
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
            # jsmpeg logic from all-z-j-new.py
            json_url = f"http://{host}/streamer/list"
            try:
                request_timeout = _get_remaining_timeout(deadline, 2)
                if request_timeout <= 0:
                    return -1, channels
                response = requests.get(json_url, timeout=request_timeout)
                if response.status_code == 200:
                    json_data = response.json()
                    valid_channel_url = None
                    for item in json_data:
                        name = item.get('name', '').strip()
                        key = item.get('key', '').strip()
                        if not name or not key:
                            continue
                        
                        full_url = f"http://{host}/hls/{key}/index.m3u8"
                        if fetch_channels:
                            channels.append({'name': name, 'url': full_url})
                        
                        # Use the first valid channel for speed test
                        if not valid_channel_url:
                            valid_channel_url = full_url

                    if valid_channel_url:
                        if timed_out():
                            return -1, channels
                        ts_url = get_ts_url(valid_channel_url, deadline=deadline)
                        if ts_url:
                            speed = get_download_speed(ts_url, deadline=deadline)
                    else:
                        speed = -1
                else:
                    speed = -1
            except Exception as e:
                # print(f"JSMPEG fetch failed for {host}: {e}")
                speed = -1

        elif match_type == 'zhgxtv':
            if timed_out():
                return -1, channels
            # Referencing ZHGXTV.py: Fetch live_interface.txt first
            interface_url = f"http://{host}{ZHGXTV_INTERFACE}"
            request_timeout = _get_remaining_timeout(deadline, 5)
            if request_timeout <= 0:
                return -1, channels
            target_response = requests.get(interface_url, timeout=request_timeout)
            if target_response.status_code == 200:
                content = target_response.content.decode('utf-8', errors='ignore')
                lines = content.split('\n')
                
                valid_channel_url = None
                
                # Parse channels here to save for later use (avoid re-fetching)
                for line in lines:
                    line = line.strip()
                    if ',' in line:
                        parts = line.split(',')
                        if len(parts) >= 2:
                            name = parts[0].strip()
                            url_part = parts[1].strip()
                            
                            # Reconstruct URL as per logic
                            
                            try:
                                full_url = ""
                                if url_part.startswith("http"):
                                    # Parse and replace host
                                    p = urlparse(url_part)
                                    # Reconstruct: scheme + netloc(host) + path + params + query + fragment
                                    # Since we want to use the current 'host' (which is ip:port)
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
                            
                            except Exception as e:
                                print(f"Error parsing line {line}: {e}")
                                continue
                if valid_channel_url:
                    if timed_out():
                        return -1, channels
                    ts_url = get_ts_url(valid_channel_url, deadline=deadline)
                    if ts_url:
                        speed = get_download_speed(ts_url, deadline=deadline)
                else:
                    speed = -1 # No valid channels found
            else:
                speed = -1

    except Exception as e:
        # print(f"Speed test failed for {host}: {e}")
        speed = -1
        
    return speed, channels


def fetch_channels_for_source(source):
    match_type = source.get('matchType')
    if match_type in ('txiptv', 'jsmpeg', 'zhgxtv'):
        _, channels = test_host_speed(
            {
                'host': source.get('host'),
                'matchType': match_type
            },
            fetch_channels=True
        )
        source['channels'] = channels or []

def clean_channel_name(name):
    """Clean and normalize channel name."""
    name = name.replace("cctv", "CCTV")
    name = name.replace("中央", "CCTV")
    name = name.replace("央视", "CCTV")
    for rep in ["高清", "超高", "HD", "标清", "频道", "-", " ", "PLUS", "＋", "(", ")"]:
        name = name.replace(rep, "" if rep not in ["PLUS", "＋"] else "+")
    name = re.sub(r"CCTV(\d+)台", r"CCTV\1", name)
    name_map = {
        "CCTV1综合": "CCTV1", "CCTV2财经": "CCTV2", "CCTV3综艺": "CCTV3", "CCTV4国际": "CCTV4",
        "CCTV4中文国际": "CCTV4", "CCTV4欧洲": "CCTV4", "CCTV5体育": "CCTV5", "CCTV6电影": "CCTV6",
        "CCTV7军事": "CCTV7", "CCTV7军农": "CCTV7", "CCTV7农业": "CCTV7", "CCTV7国防军事": "CCTV7",
        "CCTV8电视剧": "CCTV8", "CCTV9记录": "CCTV9", "CCTV9纪录": "CCTV9", "CCTV10科教": "CCTV10",
        "CCTV11戏曲": "CCTV11", "CCTV12社会与法": "CCTV12", "CCTV13新闻": "CCTV13", "CCTV新闻": "CCTV13",
        "CCTV14少儿": "CCTV14", "CCTV15音乐": "CCTV15", "CCTV16奥林匹克": "CCTV16",
        "CCTV17农业农村": "CCTV17", "CCTV17农业": "CCTV17", "CCTV5+体育赛视": "CCTV5+",
        "CCTV5+体育赛事": "CCTV5+", "CCTV5+体育": "CCTV5+", "CCTV01": "CCTV1", "CCTV02": "CCTV2", "CCTV03": "CCTV3", "CCTV04": "CCTV4",
        "CCTV05": "CCTV5", "CCTV06": "CCTV6", "CCTV07": "CCTV7", "CCTV08": "CCTV8", "CCTV09": "CCTV9"
    }
    name = name_map.get(name, name)
    return name

def process_txiptv_channels(channels, source_label, source_index):
    """Generates m3u8 entries for txiptv source using JSON parsing logic."""
    entries = []
    std_map = get_standard_channel_map()
    
    try:
        if not channels: return []
        for ch in channels:
            name = ch['name']
            url = ch['url']
            
            # Name cleaning 
            name = clean_channel_name(name)
            
            # Standardization
            name = map_to_standard_name(name, std_map)
            
            group = get_channel_group(name)
            entries.append({'name': name, 'url': url, 'group': group, 'content': build_m3u8_entry(name, url, group), 'index': source_index})
            
    except Exception as e:
        print(f"Error processing txiptv channels: {e}")
    return entries

def process_hsmdtv_channels(host, source_label, source_index):
    """Generates m3u8 entries for hsmdtv source using hsmd_address_list.txt."""
    entries = []
    std_map = get_standard_channel_map()
    try:
        if not os.path.exists(HSMD_ADDRESS_LIST_FILE):
             print(f"{HSMD_ADDRESS_LIST_FILE} not found.")
             return []

        with open(HSMD_ADDRESS_LIST_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # Find HTTP URL
            match = re.search(r'(http://[^\s]+)', line)
            if match:
                url_in_file = match.group(1)
                
                # Extract Name: everything before URL
                part_before_url = line.split(url_in_file)[0]
                # Remove ID (digits) at start
                name = re.sub(r'^\s*\d+\s+', '', part_before_url).strip()
                # Clean name
                name = name.replace("（默认频道）", "").strip()
                name = clean_channel_name(name)
                
                # Standardization
                name = map_to_standard_name(name, std_map)
                
                parsed = urlparse(url_in_file)
                new_url = f"http://{host}{parsed.path}"
                
                group = get_channel_group(name)
                entries.append({
                    'name': name,
                    'url': new_url,
                    'group': group,
                    'content': build_m3u8_entry(name, new_url, group),
                    'index': source_index
                })
    except Exception as e:
        print(f"Error processing hsmdtv channels: {e}")
    return entries

def process_zhgxtv_channels(channels, source_label, source_index):
    """Generates m3u8 entries for zhgxtv source."""
    entries = []
    std_map = get_standard_channel_map()
    if not channels: return []
    for ch in channels:
        name = ch['name']
        url = ch['url']
        
        # Cleanup name
        name = clean_channel_name(name)
        
        # Standardization
        name = map_to_standard_name(name, std_map)
        
        group = get_channel_group(name)
        entries.append({'name': name, 'url': url, 'group': group, 'content': build_m3u8_entry(name, url, group), 'index': source_index})
    return entries

def process_jsmpeg_channels(channels, source_label, source_index):
    """Generates m3u8 entries for jsmpeg source."""
    entries = []
    std_map = get_standard_channel_map()
    
    try:
        for ch in channels:
            name = ch['name']
            url = ch['url']
            
            # Clean name
            name = clean_channel_name(name)
            
            # Standardization
            name = map_to_standard_name(name, std_map)
            
            group = get_channel_group(name)
            entries.append({'name': name, 'url': url, 'group': group, 'content': build_m3u8_entry(name, url, group), 'index': source_index})
            
    except Exception as e:
        print(f"Error processing jsmpeg channels: {e}")
    return entries

def channel_sort_key(name):
    """
    Sort key for channel names.
    Order: CCTV-X, CCTV-others, Satellite (卫视), Others.
    """
    name_upper = name.upper()
    
    # CCTV channels
    if "CCTV" in name_upper:
        # Extract number if present
        match = re.search(r"CCTV(\d+)", name_upper)
        if match:
            num = int(match.group(1))
            return (0, num)
        elif "5+" in name_upper:
             return (0, 5.5) # Place between 5 and 6
        else:
            # CCTV News, etc. Place after numbered CCTVs
            return (0, 999)
            
    # Satellite TV (卫视)
    if "卫视" in name:
        return (1, name)
        
    return (2, name)

def scheduled_task():
    global global_m3u8_content, global_txt_content, last_run_time, is_running
    if not scheduled_task_lock.acquire(blocking=False):
        print("Scheduled task skipped: another update is already running.")
        return

    is_running = True
    try:
        check_for_updates()
        print("Executing scheduled task...")
        last_run_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        
        data = fetch_api_data()
        
        if not data or not isinstance(data, dict) or "results" not in data:
            print("No valid data received or 'results' key missing.")
            return

        result = data["results"]
        
        if not result:
            print("No data in result.")
            return

        # Speed test in parallel (batched to reduce memory peak)
        results_with_speed = []
        total_hosts = len(result)
        completed_hosts = 0
        valid_hosts = 0
        print_speed_test_progress(completed_hosts, total_hosts, valid_hosts)
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
                        except Exception as e:
                            print(f"Error testing {item['host']}: {e}")
                        finally:
                            completed_hosts += 1
                            print_speed_test_progress(completed_hosts, total_hosts, valid_hosts)

                    now = time.time()
                    timed_out_futures = [
                        future for future in list(pending)
                        if now - future_start_time.get(future, now) > HOST_SPEED_TEST_TIMEOUT
                    ]

                    for future in timed_out_futures:
                        pending.discard(future)
                        future.cancel()
                        completed_hosts += 1
                        print_speed_test_progress(completed_hosts, total_hosts, valid_hosts)
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

        print()

        # Sort and pick top N
        # Filter by speed limit 2MB/s
        valid_results = [r for r in results_with_speed if r['speed'] > 1.5]
        
        # Sort by speed descending
        valid_results.sort(key=lambda x: x['speed'], reverse=True)
        
        final_sources = []
        selected_hosts = set()
        
        # Ensure at least one from each type if available and fast enough
        required_matches = ['txiptv', 'hsmdtv', 'zhgxtv', 'jsmpeg']
        
        for m in required_matches:
            # Find best for this match type
            for res in valid_results:
                if res['matchType'] == m and res['host'] not in selected_hosts:
                    final_sources.append(res)
                    selected_hosts.add(res['host'])
                    break # Only need one per type for now to ensure diversity
        
        # Fill the rest with optimal speed from remaining
        for res in valid_results:
            if len(final_sources) >= TOP_N:
                break
            if res['host'] not in selected_hosts:
                 final_sources.append(res)
                 selected_hosts.add(res['host'])

        # Re-sort final collection by speed
        final_sources.sort(key=lambda x: x['speed'], reverse=True)
        
        top_sources = final_sources
        
        print(f"Selected top {len(top_sources)} sources.")

        if len(top_sources) < 3:
            print(f"Not enough sources found ({len(top_sources)} < 3).")
            
            # Load from file if empty in memory
            if not global_m3u8_content and os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    global_m3u8_content = f.read()
            if not global_txt_content and os.path.exists(TXT_CACHE_FILE):
                with open(TXT_CACHE_FILE, "r", encoding="utf-8") as f:
                    global_txt_content = f.read()
                    
            update_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            
            if global_m3u8_content:
                lines = global_m3u8_content.split('\n')
                for i, line in enumerate(lines):
                    if line.startswith("#EXT-X-UPDATED:"):
                        lines[i] = f"#EXT-X-UPDATED: {update_time_str}"
                global_m3u8_content = "\n".join(lines)
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    f.write(global_m3u8_content)
                    
            if global_txt_content:
                with open(TXT_CACHE_FILE, "w", encoding="utf-8") as f:
                    f.write(global_txt_content)
            return

        # Collect all entries (phase-2 fetch channels only for selected top sources)
        all_entries = []
        
        for idx, source in enumerate(top_sources):
            speed_str = f"{source['speed']:.2f}MB/s"
            console_label = f"源{idx+1} {speed_str}"
            m3u8_label = f"源{idx+1}"
            print(f"Processing {console_label}: {source['host']} ({source['matchType']}) {source.get('source', 'N/A')}")

            fetch_channels_for_source(source)
            
            if source['matchType'] == 'txiptv':
                entries = process_txiptv_channels(source['channels'], m3u8_label, idx)
                all_entries.extend(entries)
            elif source['matchType'] == 'hsmdtv':
                entries = process_hsmdtv_channels(source['host'], m3u8_label, idx)
                all_entries.extend(entries)
            elif source['matchType'] == 'zhgxtv':
                entries = process_zhgxtv_channels(source['channels'], m3u8_label, idx)
                all_entries.extend(entries)
            elif source['matchType'] == 'jsmpeg':
                entries = process_jsmpeg_channels(source['channels'], m3u8_label, idx)
                all_entries.extend(entries)

        # Group by name
        # We want to keep the order of channel names as much as possible
        grouped_entries = {}
        channel_order = [] 
        
        # Pre-populate order from channel_list.txt if we want specific order for those
        try:
            with open(CHANNEL_LIST_FILE, 'r', encoding='utf-8') as f:
                for l in f.readlines():
                    name = l.strip()
                    if name:
                        grouped_entries[name] = []
                        channel_order.append(name)
        except:
            pass

        for entry in all_entries:
            name = entry['name']
            if name not in grouped_entries:
                grouped_entries[name] = []
            grouped_entries[name].append(entry)

        # Sort the channel names
        # Get all unique channel names
        unique_channel_names = list(grouped_entries.keys())
        
        # Custom sort function
        def sort_channels(name):
            return channel_sort_key(name)
        
        unique_channel_names.sort(key=sort_channels)
        
        channel_order = unique_channel_names

        # Add to m3u8 lines (不添加更新时间频道，只在头部显示更新时间)
        update_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        m3u8_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"', f"#EXT-X-UPDATED: {update_time_str}"]
    
        for name in channel_order:
            entries_list = grouped_entries.get(name, [])
            # Sort by source index to ensure 源1, 源2 order
            entries_list.sort(key=lambda x: x['index'])
            if entries_list:
                for entry in entries_list:
                     m3u8_lines.append(entry['content'])

        global_m3u8_content = "\n".join(m3u8_lines)
        
        # Save to file
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(global_m3u8_content)

        # Generate TXT content (不添加更新时间行)
        txt_lines = []
    
        # Use grouped_entries to iterate channels in order (same order as m3u8)
        unique_names_processed = set()
        
        for name in channel_order:
            if name in unique_names_processed:
                continue
            unique_names_processed.add(name)
            
            entries_list = grouped_entries.get(name, [])
            # Sort by source index
            entries_list.sort(key=lambda x: x.get('index', 999))
            
            for entry in entries_list:
                if 'url' in entry:
                    # 添加分组信息：频道名,URL,分组
                    group = entry.get('group', '其他')
                    txt_lines.append(f"{entry['name']},{entry['url']},{group}")
    
        global_txt_content = "\n".join(txt_lines)
        
        # Save to file
        with open(TXT_CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(global_txt_content)

        print(f"M3U8 and TXT generation complete at {last_run_time}.")
        del results_with_speed, valid_results, final_sources, top_sources, all_entries, grouped_entries, unique_channel_names, txt_lines
        gc.collect()
    finally:
        is_running = False
        scheduled_task_lock.release()

@app.route('/txt')
def get_txt():
    global global_txt_content
    # Try to load from file if memory is empty (after restart)
    if not global_txt_content and os.path.exists(TXT_CACHE_FILE):
        with open(TXT_CACHE_FILE, "r", encoding="utf-8") as f:
            global_txt_content = f.read()

    if not global_txt_content:
        return "Not ready yet. Please wait for the first scan.", 503
        
    return global_txt_content, 200, {'Content-Type': 'text/plain; charset=utf-8'}


@app.route('/')
def status():
    return jsonify({
        "status": "running" if not is_running else "updating",
        "last_run": last_run_time,
        "message": "Visit /iptv for m3u8 playlist, /txt for text playlist."
    })

@app.route('/iptv')
def get_m3u8():
    global global_m3u8_content
    # Try to load from file if memory is empty (after restart)
    if not global_m3u8_content and os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            global_m3u8_content = f.read()

    if not global_m3u8_content:
        return "Not ready yet. Please wait for the first scan.", 503
        
    return global_m3u8_content, 200, {'Content-Type': 'application/vnd.apple.mpegurl'}

@app.route('/forceRetest')
def force_retest():
    global is_running
    if is_running:
         return jsonify({"message": "Update already in progress.", "status": "busy"}), 429
         
    threading.Thread(target=scheduled_task, daemon=True).start()
    return jsonify({"message": "Force retest started in background.", "status": "started"})

# Initial run in background on startup (or trigger manually)
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=scheduled_task, trigger="interval", hours=6)
    scheduler.start()
    
    # Run immediately in a separate thread to not block startup
    threading.Thread(target=scheduled_task, daemon=True).start()

if __name__ == '__main__':
    bind_host = '0.0.0.0'
    bind_port = 5000

    print(f"Starting... - Version: {VERSION}")
    check_for_updates()

    if not takeover_previous_instance(bind_host, bind_port):
        print(f"Port {bind_port} is still in use. Exit startup to avoid duplicate instance.")
        print("检测到新版本更新~请手动重启程序以应用更新~")
        sys.exit(1)

    _write_pid_file(os.getpid())
    atexit.register(_cleanup_pid_file)

    start_scheduler()
    app.run(host=bind_host, port=bind_port)





