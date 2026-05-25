#!/usr/bin/env python3
"""
API 调试脚本 - 检查 API 行为和环境变量
"""
import requests
import json

API_URL = "https://iptv-bfo.pages.dev/api"

def test_status():
    """测试状态端点"""
    print("=" * 50)
    print("测试状态端点")
    print("=" * 50)
    try:
        resp = requests.get(f"{API_URL}/status", timeout=10)
        print(f"状态码: {resp.status_code}")
        print(f"响应: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"错误: {e}")

def test_upload_no_auth():
    """测试不带认证的上传"""
    print("\n" + "=" * 50)
    print("测试不带认证的上传")
    print("=" * 50)
    try:
        resp = requests.post(
            f"{API_URL}/upload",
            json={"test": "data"},
            timeout=10
        )
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.text}")
        if resp.status_code == 401:
            print("✅ 正确拒绝未授权请求")
        else:
            print("❌ 未正确拒绝未授权请求")
    except Exception as e:
        print(f"错误: {e}")

def test_upload_wrong_auth():
    """测试带错误认证的上传"""
    print("\n" + "=" * 50)
    print("测试带错误认证的上传")
    print("=" * 50)
    try:
        resp = requests.post(
            f"{API_URL}/upload",
            json={"test": "data"},
            headers={"Authorization": "Bearer wrong-token"},
            timeout=10
        )
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.text}")
        if resp.status_code == 401:
            print("✅ 正确拒绝错误 Token")
        else:
            print("❌ 未正确拒绝错误 Token")
    except Exception as e:
        print(f"错误: {e}")

def test_upload_correct_auth():
    """测试带正确认证的上传"""
    print("\n" + "=" * 50)
    print("测试带正确认证的上传")
    print("=" * 50)
    API_KEY = "iptv-default-key-2024"
    try:
        resp = requests.post(
            f"{API_URL}/upload",
            json={"test": "data", "source": "test"},
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=10
        )
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.text}")
        if resp.status_code == 200:
            print("✅ 正确接受有效 Token")
        else:
            print("❌ 未正确接受有效 Token")
    except Exception as e:
        print(f"错误: {e}")

def test_cors():
    """测试 CORS 预检请求"""
    print("\n" + "=" * 50)
    print("测试 CORS 预检请求")
    print("=" * 50)
    try:
        resp = requests.options(
            f"{API_URL}/upload",
            headers={
                "Origin": "http://localhost:9998",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization,Content-Type"
            },
            timeout=10
        )
        print(f"状态码: {resp.status_code}")
        print(f"响应头:")
        for key, value in resp.headers.items():
            if key.lower().startswith('access-control'):
                print(f"  {key}: {value}")
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    test_status()
    test_upload_no_auth()
    test_upload_wrong_auth()
    test_upload_correct_auth()
    test_cors()
