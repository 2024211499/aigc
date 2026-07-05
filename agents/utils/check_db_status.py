import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

import redis
import psycopg2
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(project_root, ".env"))

print("=" * 60)
print("  数据库状态检查")
print("=" * 60)

# 检查 Redis
try:
    r = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=int(os.getenv("REDIS_DB", 0)),
        password=os.getenv("REDIS_PASSWORD") or None,
        decode_responses=True
    )
    r.ping()
    print("\n[Redis] 连接成功")
    keys = r.keys('*')
    print(f"  键数量: {len(keys)}")
    if keys:
        for key in keys[:5]:
            print(f"  - {key}")
except Exception as e:
    print(f"\n[Redis] 错误: {e}")

# 检查 PostgreSQL
try:
    conn = psycopg2.connect(
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", 5432)),
        dbname=os.getenv("PG_DB", "aigc_memory"),
        user=os.getenv("PG_USER", "postgres"),
        password=os.getenv("PG_PASSWORD", "postgres")
    )
    print("\n[PostgreSQL] 连接成功")
    
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM study_sessions")
    print(f"  study_sessions 记录数: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM conversation_history")
    print(f"  conversation_history 记录数: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM learning_states")
    print(f"  learning_states 记录数: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM knowledge_points")
    print(f"  knowledge_points 记录数: {cursor.fetchone()[0]}")
    
    cursor.close()
    conn.close()
except Exception as e:
    print(f"\n[PostgreSQL] 错误: {e}")

# 检查 ChromaDB
try:
    import chromadb
    chroma_dir = os.path.join(project_root, ".chroma_data")
    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_collection("knowledge_points")
    print(f"\n[ChromaDB] 连接成功")
    print(f"  知识点数量: {collection.count()}")
except Exception as e:
    print(f"\n[ChromaDB] 错误: {e}")

print("\n" + "=" * 60)
print("  所有数据库检查完成")
print("=" * 60)
