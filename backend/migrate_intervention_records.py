"""
数据迁移脚本：合并重复的意图干预记录

由于之前的 bug，同一个 query 可能因为 file_id 不同而创建了多条记录。
此脚本将：
1. 找出所有重复的 query
2. 将最新更新的 reason 和 target 合并到主记录
3. 删除重复的记录

使用方法：
cd backend
.\venv\Scripts\python migrate_intervention_records.py <project_id>
"""
import sys
from loguru import logger
from app.db.database import get_db_session
from app.models import IntentIntervention
from sqlmodel import select

def migrate_interventions(project_id: str) -> None:
    """
    合并项目下重复的意图干预记录
    
    :param project_id: 项目 ID
    """
    logger.info(f"开始迁移项目 {project_id} 的意图干预记录...")
    
    with get_db_session() as session:
        # 1. 获取所有记录
        statement = select(IntentIntervention).where(
            IntentIntervention.project_id == project_id
        )
        all_records = list(session.exec(statement).all())
        logger.info(f"共找到 {len(all_records)} 条记录")
        
        # 2. 按 query 分组
        query_map: dict = {}
        for record in all_records:
            if record.query not in query_map:
                query_map[record.query] = []
            query_map[record.query].append(record)
        
        # 3. 处理重复记录
        merged_count = 0
        deleted_count = 0
        
        for query, records in query_map.items():
            if len(records) <= 1:
                continue
            
            logger.info(f"发现重复 query: {query[:30]}... ({len(records)} 条记录)")
            
            # 选择主记录（优先 is_target_modified=True，其次最新更新的）
            main_record = None
            for r in records:
                if r.is_target_modified:
                    main_record = r
                    break
            
            if main_record is None:
                # 按更新时间排序，取最新的
                records.sort(key=lambda x: x.updated_at or x.created_at, reverse=True)
                main_record = records[0]
            
            logger.info(f"  主记录 ID: {main_record.id}, file_id: {main_record.file_id}")
            
            # 合并其他记录的 reason
            for r in records:
                if r.id == main_record.id:
                    continue
                
                # 如果其他记录有 reason 而主记录没有，则合并
                if r.reason and not main_record.reason:
                    main_record.reason = r.reason
                    logger.info(f"    合并 reason from ID {r.id}")
                    merged_count += 1
                
                # 删除重复记录
                session.delete(r)
                deleted_count += 1
                logger.info(f"    删除重复记录 ID {r.id}")
            
            session.add(main_record)
        
        session.commit()
        logger.success(f"迁移完成: 合并 {merged_count} 条 reason, 删除 {deleted_count} 条重复记录")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法: python migrate_intervention_records.py <project_id>")
        print("例如: python migrate_intervention_records.py proj_12345")
        sys.exit(1)
    
    project_id = sys.argv[1]
    migrate_interventions(project_id)
