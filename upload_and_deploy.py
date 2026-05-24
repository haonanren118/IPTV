#!/usr/bin/env python3
"""
IPTV 播放列表自动更新脚本
从 ZB.txt 读取频道数据，按分组格式生成 m3u8/txt，上传到 Cloudflare KV
供飞牛 NAS Docker 容器定时运行
"""

import requests
import os
import re
import time
from urllib.parse import quote

# ==================== 配置 ====================
UPLOAD_URL = os.environ.get("UPLOAD_URL", "https://iptv-bfo.pages.dev/api/upload")
ZB_FILE = os.environ.get("ZB_FILE", "/app/ZB.txt")
EPG_URL = os.environ.get("EPG_URL", "https://epg.112114.xyz/pp.xml")
LOGO_BASE_URL = "https://ghfast.top/https://raw.githubusercontent.com/Jarrey/iptv_logo/main/tv/"
UPLOAD_TOKEN = os.environ.get("UPLOAD_TOKEN", "")  # CF Pages 上传认证 Token

# 分组定义（按显示顺序）
GROUP_ORDER = [
    "央视频道", "卫视频道", "电影频道", "儿童频道",
    "体育频道", "纪录频道", "音乐频道", "地方频道",
    "数字频道", "解说频道", "春晚频道", "直播中国", "其他"
]


def log(msg):
    """带时间戳的日志输出"""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


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

    # 地方频道
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


def channel_sort_key(name):
    """频道排序：CCTV 数字优先，然后卫视，然后其他"""
    name_upper = name.upper()
    if "CCTV" in name_upper:
        match = re.search(r"CCTV(\d+)", name_upper)
        if match:
            return (0, int(match.group(1)))
        if "4K" in name_upper:
            return (0, 4.5)
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


def main():
    log("=" * 50)
    log("IPTV 播放列表自动更新")
    log("=" * 50)

    # 1. 读取 ZB.txt
    if not os.path.exists(ZB_FILE):
        log(f"错误: 找不到文件 {ZB_FILE}")
        return False

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
    log(f"读取到 {total} 个频道")

    # 2. 生成 M3U8
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

    m3u8_content = "\n".join(m3u8_lines)

    # 3. 生成 TXT (分组格式)
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

    txt_content = "\n".join(txt_lines)

    log(f"M3U8: {len(m3u8_lines)} 行, TXT: {len(txt_lines)} 行")

    # 4. 上传到 CF KV
    log(f"上传到 CF KV ({UPLOAD_URL})...")
    try:
        payload = {
            "m3u8": m3u8_content,
            "txt": txt_content,
            "last_update": update_time,
            "source": "local",  # 标识为本地 IPTV 源，写入 CF KV 的 m3u8_local/txt_local
        }
        headers = {"Content-Type": "application/json"}
        if UPLOAD_TOKEN:
            headers["Authorization"] = f"Bearer {UPLOAD_TOKEN}"
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


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
