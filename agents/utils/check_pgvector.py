import os
import psycopg2
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(project_root, ".env"))

conn = psycopg2.connect(
    host=os.getenv("PG_HOST", "localhost"),
    port=int(os.getenv("PG_PORT", 5432)),
    dbname=os.getenv("PG_DB", "aigc_memory"),
    user=os.getenv("PG_USER", "postgres"),
    password=os.getenv("PG_PASSWORD", "postgres")
)
cursor = conn.cursor()

cursor.execute("SELECT * FROM pg_extension WHERE extname = 'vector'")
result = cursor.fetchone()

if result:
    print("[pgvector] 已安装")
else:
    print("[pgvector] 未安装，尝试安装...")
    try:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()
        print("[pgvector] 安装成功")
    except Exception as e:
        print(f"[pgvector] 安装失败: {e}")

cursor.close()
conn.close()
