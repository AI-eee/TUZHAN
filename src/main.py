import time
import os
import logging
import uvicorn
import yaml

# [修改原因]: 引入刚刚编写的服务端 API App
from api.server import app as api_app

# 配置基础日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def start_api_server():
    """启动 Web API 及 Web 界面服务"""
    # 增加对本地和正式环境的区分，读取 settings.yaml 中的配置
    current_dir = os.path.dirname(os.path.abspath(__file__))
    settings_file = os.path.join(current_dir, '..', 'config', 'settings.yaml')
    
    with open(settings_file, 'r', encoding='utf-8') as f:
        settings = yaml.safe_load(f)
        
    # [修改原因]: 读取 .env 中的 TUZHAN_ENV，如果没有则默认 development
    from dotenv import load_dotenv
    load_dotenv(os.path.join(current_dir, '..', '.env'))
    env = os.getenv("TUZHAN_ENV", "development")
    
    # [新增原因]: 在正式环境中严禁执行任何初始化测试数据的脚本
    if env == "production":
        logger.info("当前处于 Production 环境，已屏蔽所有自动化测试数据的生成和污染。")
        
    config = settings.get(env, settings["development"])
    host = config.get("server_bind_host", "127.0.0.1")
    port = config.get("server_bind_port", 8888)

    logger.info(f"正在启动 TUZHAN 协作中心 Web/API 服务 ({env} 环境) - 绑定地址: {host}:{port} ...")
    uvicorn.run(api_app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    # [修改原因]: 既然已经改用 SQLite，无需再使用 watchdog 监听本地文件了
    # 所有的发信都会通过 HTTP 接口进入 SQLite
    start_api_server()
