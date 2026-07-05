import os
import json
from typing import List, Optional, Dict
from datetime import datetime

try:
    import redis
except ImportError:
    redis = None

try:
    import psycopg2
except ImportError:
    psycopg2 = None

try:
    import chromadb
except ImportError:
    chromadb = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(project_root, ".env"))


class MemoryManager:
    def __init__(self):
        self.redis_client = None
        self.pg_conn = None
        self.embedding_client = None
        self.chroma_client = None
        self.chroma_collection = None
        
        self._init_redis()
        self._init_postgresql()
        self._init_embedding_client()
        self._init_chroma()
        
        print("[Memory] Database initialized")
    
    def _init_redis(self):
        try:
            self.redis_client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=int(os.getenv("REDIS_DB", 0)),
                password=os.getenv("REDIS_PASSWORD") or None,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            self.redis_client.ping()
            print("[Redis] Connected")
        except Exception as e:
            print("[Redis] Connection failed: " + str(e))
            self.redis_client = None
    
    def _init_postgresql(self):
        try:
            self.pg_conn = psycopg2.connect(
                host=os.getenv("PG_HOST", "localhost"),
                port=int(os.getenv("PG_PORT", 5432)),
                dbname=os.getenv("PG_DB", "aigc_memory"),
                user=os.getenv("PG_USER", "postgres"),
                password=os.getenv("PG_PASSWORD", "postgres"),
            )
            self._create_tables()
            print("[PostgreSQL] Connected")
        except Exception as e:
            print("[PostgreSQL] Connection failed: " + str(e))
            self.pg_conn = None
    
    def _init_embedding_client(self):
        try:
            self.embedding_client = OpenAI(
                api_key=os.getenv("EMBEDDING_API_KEY", os.getenv("OPENAI_API_KEY")),
                base_url=os.getenv("EMBEDDING_API_BASE", os.getenv("OPENAI_API_BASE")),
            )
            print("[Embedding] Initialized")
        except Exception as e:
            print("[Embedding] Init failed: " + str(e))
            self.embedding_client = None
    
    def _init_chroma(self):
        try:
            chroma_dir = os.path.join(project_root, ".chroma_data")
            os.makedirs(chroma_dir, exist_ok=True)
            
            self.chroma_client = chromadb.PersistentClient(path=chroma_dir)
            self.chroma_collection = self.chroma_client.get_or_create_collection(
                name="knowledge_points",
                metadata={"hnsw:space": "cosine"}
            )
            print("[ChromaDB] Initialized, " + str(self.chroma_collection.count()) + " records")
        except Exception as e:
            print("[ChromaDB] Init failed: " + str(e))
            self.chroma_client = None
            self.chroma_collection = None
    
    def _create_tables(self):
        if not self.pg_conn:
            return
        
        cursor = self.pg_conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_sessions (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(100) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                fragments TEXT,
                study_plan JSONB,
                exercises JSONB,
                explanation JSONB
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(100) NOT NULL,
                role VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_states (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(100) NOT NULL,
                focus_level FLOAT DEFAULT 0.0,
                fatigue_level FLOAT DEFAULT 0.0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_points (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(100) NOT NULL,
                concept TEXT NOT NULL,
                embedding JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        self.pg_conn.commit()
        cursor.close()
    
    def get_embedding(self, text: str) -> List[float]:
        if not self.embedding_client:
            return []
        
        try:
            response = self.embedding_client.embeddings.create(
                model=os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002"),
                input=text,
                timeout=60.0,
            )
            return response.data[0].embedding
        except Exception:
            return []
    
    def save_session(self, session_id: str, fragments: List[str], results: dict):
        if self.redis_client:
            try:
                redis_data = {
                    "session_id": session_id,
                    "fragments": json.dumps(fragments, ensure_ascii=False),
                    "study_plan": json.dumps(results.get("study_plan"), ensure_ascii=False) if results.get("study_plan") else "",
                    "exercises": json.dumps(results.get("exercises"), ensure_ascii=False) if results.get("exercises") else "",
                    "explanation": json.dumps(results.get("explanation"), ensure_ascii=False) if results.get("explanation") else "",
                    "updated_at": datetime.now().isoformat(),
                }
                self.redis_client.hset(f"session:{session_id}", mapping=redis_data)
                self.redis_client.expire(f"session:{session_id}", 86400)
            except Exception as e:
                print(f"[Redis] 保存 session 失败: {e}")
        
        if self.pg_conn:
            try:
                from psycopg2.extras import Json
                cursor = self.pg_conn.cursor()
                cursor.execute("""
                    INSERT INTO study_sessions (session_id, fragments, study_plan, exercises, explanation)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (session_id) DO UPDATE SET
                        fragments = EXCLUDED.fragments,
                        study_plan = EXCLUDED.study_plan,
                        exercises = EXCLUDED.exercises,
                        explanation = EXCLUDED.explanation,
                        created_at = NOW();
                """, (
                    session_id,
                    json.dumps(fragments, ensure_ascii=False),
                    Json(results.get("study_plan")) if results.get("study_plan") else None,
                    Json(results.get("exercises")) if results.get("exercises") else None,
                    Json(results.get("explanation")) if results.get("explanation") else None,
                ))
                self.pg_conn.commit()
                cursor.close()
            except Exception as e:
                print(f"[PostgreSQL] 保存 session 失败: {e}")
    
    def add_to_history(self, session_id: str, role: str, content: str):
        entry = {"role": role, "content": content, "time": datetime.now().isoformat()}
        
        if self.redis_client:
            try:
                history_key = f"history:{session_id}"
                self.redis_client.rpush(history_key, json.dumps(entry, ensure_ascii=False))
                self.redis_client.expire(history_key, 86400)
            except Exception as e:
                print(f"[Redis] 保存历史失败: {e}")
        
        if self.pg_conn:
            try:
                cursor = self.pg_conn.cursor()
                cursor.execute("""
                    INSERT INTO conversation_history (session_id, role, content)
                    VALUES (%s, %s, %s);
                """, (session_id, role, content))
                self.pg_conn.commit()
                cursor.close()
            except Exception as e:
                print(f"[PostgreSQL] 保存历史失败: {e}")
    
    def get_history(self, session_id: str) -> List[dict]:
        if self.redis_client:
            try:
                history_key = f"history:{session_id}"
                history = self.redis_client.lrange(history_key, 0, -1)
                if history:
                    return [json.loads(h) for h in history]
            except Exception as e:
                print(f"[Redis] 读取历史失败: {e}")
        
        if self.pg_conn:
            try:
                cursor = self.pg_conn.cursor()
                cursor.execute("""
                    SELECT role, content, created_at FROM conversation_history
                    WHERE session_id = %s ORDER BY created_at;
                """, (session_id,))
                rows = cursor.fetchall()
                cursor.close()
                return [{"role": r[0], "content": r[1], "time": str(r[2])} for r in rows]
            except Exception as e:
                print(f"[PostgreSQL] 读取历史失败: {e}")
        
        return []
    
    def save_knowledge_point(self, session_id: str, concept: str):
        embedding = self.get_embedding(concept)
        
        if self.chroma_collection and embedding:
            try:
                doc_id = f"{session_id}_{concept}_{datetime.now().timestamp()}"
                self.chroma_collection.add(
                    embeddings=[embedding],
                    documents=[concept],
                    metadatas=[{"session_id": session_id, "concept": concept}],
                    ids=[doc_id]
                )
            except Exception as e:
                print(f"[ChromaDB] 保存知识点失败: {e}")
        
        if self.pg_conn:
            try:
                cursor = self.pg_conn.cursor()
                cursor.execute("""
                    INSERT INTO knowledge_points (session_id, concept, embedding)
                    VALUES (%s, %s, %s);
                """, (session_id, concept, json.dumps(embedding, ensure_ascii=False) if embedding else None))
                self.pg_conn.commit()
                cursor.close()
            except Exception as e:
                print(f"[PostgreSQL] 保存知识点失败: {e}")
    
    def search_similar_concepts(self, session_id: str, query: str, limit: int = 5) -> List[str]:
        if self.chroma_collection and self.embedding_client:
            try:
                query_embedding = self.get_embedding(query)
                if query_embedding:
                    results = self.chroma_collection.query(
                        query_embeddings=[query_embedding],
                        n_results=limit,
                        where={"session_id": session_id}
                    )
                    if results["documents"] and results["documents"][0]:
                        return results["documents"][0]
            except Exception as e:
                print(f"[ChromaDB] 向量搜索失败: {e}")
        
        if self.pg_conn:
            try:
                cursor = self.pg_conn.cursor()
                cursor.execute("""
                    SELECT concept FROM knowledge_points
                    WHERE session_id = %s AND concept ILIKE %s
                    LIMIT %s;
                """, (session_id, f"%{query}%", limit))
                results = cursor.fetchall()
                cursor.close()
                return [r[0] for r in results]
            except Exception as e:
                print(f"[PostgreSQL] 搜索知识点失败: {e}")
        
        return []
    
    def save_learning_state(self, session_id: str, focus_level: float = 0.0, fatigue_level: float = 0.0, notes: str = ""):
        if self.redis_client:
            try:
                state_data = {
                    "focus_level": focus_level,
                    "fatigue_level": fatigue_level,
                    "notes": notes,
                    "updated_at": datetime.now().isoformat(),
                }
                self.redis_client.hset(f"state:{session_id}", mapping=state_data)
                self.redis_client.expire(f"state:{session_id}", 86400)
            except Exception as e:
                print(f"[Redis] 保存状态失败: {e}")
        
        if self.pg_conn:
            try:
                cursor = self.pg_conn.cursor()
                cursor.execute("""
                    INSERT INTO learning_states (session_id, focus_level, fatigue_level, notes)
                    VALUES (%s, %s, %s, %s);
                """, (session_id, focus_level, fatigue_level, notes))
                self.pg_conn.commit()
                cursor.close()
            except Exception as e:
                print(f"[PostgreSQL] 保存状态失败: {e}")
    
    def get_session_data(self, session_id: str) -> Optional[dict]:
        if self.redis_client:
            try:
                session_data = self.redis_client.hgetall(f"session:{session_id}")
                if session_data:
                    return {
                        "session_id": session_data.get("session_id"),
                        "fragments": json.loads(session_data.get("fragments", "[]")),
                        "study_plan": json.loads(session_data.get("study_plan")) if session_data.get("study_plan") else None,
                        "exercises": json.loads(session_data.get("exercises")) if session_data.get("exercises") else None,
                        "explanation": json.loads(session_data.get("explanation")) if session_data.get("explanation") else None,
                    }
            except Exception as e:
                print(f"[Redis] 读取 session 失败: {e}")
        
        if self.pg_conn:
            try:
                cursor = self.pg_conn.cursor()
                cursor.execute("""
                    SELECT fragments, study_plan, exercises, explanation
                    FROM study_sessions WHERE session_id = %s;
                """, (session_id,))
                row = cursor.fetchone()
                cursor.close()
                
                if row:
                    return {
                        "session_id": session_id,
                        "fragments": json.loads(row[0]) if row[0] else [],
                        "study_plan": json.loads(row[1]) if row[1] else None,
                        "exercises": json.loads(row[2]) if row[2] else None,
                        "explanation": json.loads(row[3]) if row[3] else None,
                    }
            except Exception as e:
                print(f"[PostgreSQL] 读取 session 失败: {e}")
        
        return None
    
    def close(self):
        if self.pg_conn:
            self.pg_conn.close()
        if self.redis_client:
            self.redis_client.close()
