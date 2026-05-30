#!/usr/bin/env python3
"""
IPTV 播放列表生成器（简化版）
不测速，只从 Cloudflare KV 获取 Docker 上传的播放列表
供 GitHub Actions 调用
"""

import requests
import time
import json
import os
import sys

# ==================== 配置 ====================
CF_API_BASE = "https://iptv-bfo.pages.dev/api"
EPG_URL = "https://epg.zsdc.eu.org/t.xml"


def main():
    print("=" * 60)
    print("IPTV 播放列表生成器（CF KV 模式）")
    print("=" * 60)

    # 从 CF KV 获取播放列表
    print("\n[1/2] 从 Cloudflare KV 获取播放列表...")

    m3u8_content = None
    txt_content = None

    # 尝试获取 M3U8
    for attempt in range(3):
        try:
            resp = requests.get(f"{CF_API_BASE}/iptv", timeout=15)
            if resp.status_code == 200:
                m3u8_content = resp.text
                print(f"  ✅ M3U8 获取成功 ({len(m3u8_content)} 字节)")
                break
            else:
                print(f"  尝试 {attempt+1} 失败: HTTP {resp.status_code}")
        except Exception as e:
            print(f"  尝试 {attempt+1} 失败: {e}")
        time.sleep(2)

    # 尝试获取 TXT
    for attempt in range(3):
        try:
            resp = requests.get(f"{CF_API_BASE}/txt", timeout=15)
            if resp.status_code == 200:
                txt_content = resp.text
                print(f"  ✅ TXT 获取成功 ({len(txt_content)} 字节)")
                break
            else:
                print(f"  尝试 {attempt+1} 失败: HTTP {resp.status_code}")
        except Exception as e:
            print(f"  尝试 {attempt+1} 失败: {e}")
        time.sleep(2)

    # 检查是否获取成功
    if not m3u8_content:
        print("  ❌ M3U8 获取失败，退出")
        sys.exit(1)

    if not txt_content:
        print("  ❌ TXT 获取失败，退出")
        sys.exit(1)

    # 更新时间戳
    print("\n[2/2] 更新播放列表文件...")
    update_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    # 更新 M3U8 中的时间戳
    m3u8_lines = m3u8_content.split('\n')
    for i, line in enumerate(m3u8_lines):
        if line.startswith("#EXT-X-UPDATED:"):
            m3u8_lines[i] = f"#EXT-X-UPDATED: {update_time}"
            break
    else:
        # 如果没有时间戳行，在第二行添加
        if len(m3u8_lines) >= 1 and m3u8_lines[0].startswith('#EXTM3U'):
            m3u8_lines.insert(1, f"#EXT-X-UPDATED: {update_time}")
    m3u8_content = '\n'.join(m3u8_lines)

    # 输出文件
    output_dir = os.environ.get("GITHUB_OUTPUT_DIR", os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(output_dir, exist_ok=True)

    m3u8_path = os.path.join(output_dir, "iptv_sources.m3u8")
    txt_path = os.path.join(output_dir, "iptv_sources.txt")

    with open(m3u8_path, "w", encoding="utf-8") as f:
        f.write(m3u8_content)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(txt_content)

    # 统计频道数
    channel_count = 0
    for line in m3u8_lines:
        if line.startswith('#EXTINF:'):
            channel_count += 1

    print(f"\n✅ 生成完成!")
    print(f"   M3U8: {m3u8_path} ({len(m3u8_content)} 字节)")
    print(f"   TXT:  {txt_path} ({len(txt_content)} 字节)")
    print(f"   频道数: {channel_count}")
    print(f"   更新时间: {update_time}")

    # 输出到 GITHUB_OUTPUT（供后续步骤使用）
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"m3u8_path={m3u8_path}\n")
            f.write(f"txt_path={txt_path}\n")
            f.write(f"update_time={update_time}\n")
            f.write(f"channel_count={channel_count}\n")

    return m3u8_content, txt_content, update_time


if __name__ == "__main__":
    main()
