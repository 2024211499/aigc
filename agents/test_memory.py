# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.memory_manager import MemoryManager

print("=" * 60)
print("  记忆能力测试")
print("=" * 60)

memory = MemoryManager()

test_session = "test_memory_001"

print("\n1. 保存会话数据...")
test_fragments = ["集合是由确定的、互不相同的对象组成的整体", "集合的表示法有列举法和描述法"]
test_results = {
    "study_plan": {"title": "测试学习计划", "total_time_minutes": 60, "daily_tasks": []},
    "exercises": {"multiple_choice": [], "fill_in": [], "short_answer": []},
    "explanation": {"question": "测试题目", "difficulty": "简单", "steps": [], "summary": "测试总结", "related_concepts": []}
}
memory.save_session(test_session, test_fragments, test_results)
print("   会话数据已保存")

print("\n2. 添加对话历史...")
memory.add_to_history(test_session, "用户", "请帮我生成学习计划")
memory.add_to_history(test_session, "系统", "学习计划已生成")
memory.add_to_history(test_session, "用户", "修改学习计划，增加难度")
memory.add_to_history(test_session, "系统", "学习计划已修改")
print("   已添加4条对话历史")

print("\n3. 保存知识点...")
knowledge_points = ["集合的定义", "列举法", "描述法", "子集", "空集", "属于关系", "包含关系"]
for kp in knowledge_points:
    memory.save_knowledge_point(test_session, kp)
print(f"   已保存{len(knowledge_points)}个知识点")

print("\n4. 保存学习状态...")
memory.save_learning_state(test_session, focus_level=0.8, fatigue_level=0.3, notes="测试学习状态")
print("   学习状态已保存")

print("\n5. 读取会话数据...")
session_data = memory.get_session_data(test_session)
if session_data:
    print(f"   会话ID: {session_data['session_id']}")
    print(f"   片段数量: {len(session_data['fragments'])}")
    print(f"   学习计划: {session_data['study_plan']['title']}")
    print("   会话数据读取成功")
else:
    print("   会话数据读取失败")

print("\n6. 读取对话历史...")
history = memory.get_history(test_session)
if history:
    print(f"   历史消息数量: {len(history)}")
    for msg in history:
        print(f"   {msg['role']}: {msg['content']}")
    print("   对话历史读取成功")
else:
    print("   对话历史读取失败")

print("\n7. 搜索知识点...")
search_results = memory.search_similar_concepts(test_session, "集合", limit=3)
if search_results:
    print(f"   找到{len(search_results)}个相关知识点:")
    for i, concept in enumerate(search_results, 1):
        print(f"   {i}. {concept}")
    print("   知识点搜索成功")
else:
    print("   未找到相关知识点")

print("\n8. 搜索知识点（描述法）...")
search_results2 = memory.search_similar_concepts(test_session, "描述法", limit=3)
if search_results2:
    print(f"   找到{len(search_results2)}个相关知识点:")
    for i, concept in enumerate(search_results2, 1):
        print(f"   {i}. {concept}")
    print("   知识点搜索成功")
else:
    print("   未找到相关知识点")

print("\n" + "=" * 60)
print("  记忆能力测试完成")
print("=" * 60)

memory.close()
