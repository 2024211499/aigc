import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

import psycopg2
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(project_root, ".env"))

def init_database():
    pg_host = os.getenv("PG_HOST", "localhost")
    pg_port = int(os.getenv("PG_PORT", 5432))
    pg_db = os.getenv("PG_DB", "aigc_memory")
    pg_user = os.getenv("PG_USER", "postgres")
    pg_password = os.getenv("PG_PASSWORD", "")
    
    try:
        conn = psycopg2.connect(
            host=pg_host,
            port=pg_port,
            dbname="postgres",
            user=pg_user,
            password=pg_password,
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{pg_db}';")
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute(f"CREATE DATABASE {pg_db};")
            print(f"✅ 数据库 {pg_db} 创建成功")
        else:
            print(f"ℹ️ 数据库 {pg_db} 已存在")
        
        cursor.close()
        conn.close()
        
        conn = psycopg2.connect(
            host=pg_host,
            port=pg_port,
            dbname=pg_db,
            user=pg_user,
            password=pg_password,
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            print("✅ pgvector 扩展已启用")
        except psycopg2.Error as e:
            if "vector" in str(e):
                print("⚠️ pgvector 扩展不可用，将使用普通存储模式")
            else:
                raise
        
        cursor.close()
        conn.close()
        
        print("\n✅ 数据库初始化完成！")
        
    except psycopg2.Error as e:
        print(f"\n❌ 数据库初始化失败: {e}")
        print("\n请确保:")
        print("1. PostgreSQL 已安装并运行")
        print("2. pgvector 扩展已安装（可选）")
        print("3. .env 中的数据库配置正确")

if __name__ == "__main__":
    init_database()
