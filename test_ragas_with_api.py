#!/usr/bin/env python3
"""
启动FastAPI服务器并运行RAGAS评估的完整脚本
"""

import asyncio
import subprocess
import time
import signal
import sys
import requests
from pathlib import Path

# 检查依赖
try:
    import httpx
    print("✅ httpx已安装")
except ImportError:
    print("❌ httpx未安装，请运行: pip install httpx")
    sys.exit(1)

class TKRAGServerManager:
    """TK-RAG服务器管理器"""
    
    def __init__(self, host="localhost", port=8080):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.server_process = None
        
    def start_server(self):
        """启动FastAPI服务器"""
        print(f"🚀 启动TK-RAG服务器: {self.base_url}")
        
        # 启动服务器
        cmd = [
            "python", "-m", "uvicorn", 
            "fastapi_app:app",
            "--host", self.host,
            "--port", str(self.port),
            "--reload"
        ]
        
        self.server_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 等待服务器启动
        print("等待服务器启动...")
        max_retries = 30
        for i in range(max_retries):
            try:
                response = requests.get(f"{self.base_url}/health", timeout=2)
                if response.status_code == 200:
                    print(f"✅ 服务器启动成功! ({i+1}秒)")
                    return True
            except requests.exceptions.RequestException:
                pass
            
            time.sleep(1)
            print(f"等待中... ({i+1}/{max_retries})")
        
        print("❌ 服务器启动超时")
        return False
        
    def stop_server(self):
        """停止服务器"""
        if self.server_process:
            print("🛑 停止服务器...")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
                self.server_process.wait()
            print("✅ 服务器已停止")
            
    def test_api(self):
        """测试API连接"""
        try:
            # 测试聊天API
            test_data = {
                "query": "测试查询",
                "session_id": "test_session",
                "permission_ids": [],
                "timeout": 30
            }
            
            response = requests.post(
                f"{self.base_url}/chat/rag_chat",
                json=test_data,
                timeout=10
            )
            
            print(f"API测试结果: HTTP {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"API响应: {result.get('success', False)}")
                return True
            else:
                print(f"API错误: {response.text}")
                return False
                
        except Exception as e:
            print(f"API测试失败: {e}")
            return False

async def run_ragas_evaluation():
    """运行RAGAS评估"""
    print("\n📊 开始RAGAS评估...")
    
    # 导入评估器
    sys.path.append('.')
    from tests.test_ragas_evaluation import RagBenchEvaluator
    
    # 创建评估器（使用API模式）
    evaluator = RagBenchEvaluator(api_base_url="http://localhost:8080")
    
    # 运行评估
    dataset_name = "covidqa"
    sample_size = 5  # 小样本测试
    
    await evaluator.run_complete_evaluation(dataset_name, sample_size)

def main():
    """主函数"""
    print("TK-RAG系统RAGAS评估工具 (API模式)")
    print("="*60)
    
    # 创建服务器管理器
    server_manager = TKRAGServerManager()
    
    try:
        # 启动服务器
        if not server_manager.start_server():
            print("❌ 无法启动服务器，退出评估")
            return
            
        # 测试API
        if not server_manager.test_api():
            print("❌ API测试失败，请检查服务器状态")
            return
            
        print("✅ API测试通过，开始RAGAS评估")
        
        # 运行评估
        asyncio.run(run_ragas_evaluation())
        
    except KeyboardInterrupt:
        print("\n👋 用户中断")
    except Exception as e:
        print(f"❌ 评估过程出错: {e}")
    finally:
        # 停止服务器
        server_manager.stop_server()

if __name__ == "__main__":
    main()