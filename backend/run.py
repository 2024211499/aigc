#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
后端启动入口
用法：python run.py
     python run.py --port 8001 --reload
"""
import sys
import argparse
import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AIGC 学习平台后端")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", default=False)
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════════╗
║         AIGC 智能学习资源生成平台                    ║
║    http://{args.host}:{args.port}                          ║
║    Swagger: http://localhost:{args.port}/docs          ║
╚══════════════════════════════════════════════════╝
""")

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
