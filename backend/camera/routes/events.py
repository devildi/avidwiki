"""
事件管理路由
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from database.db import get_db
from database.models import Event

router = APIRouter()


@router.get("/events")
def list_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    event_type: str = Query(None),
    person_name: str = Query(None),
    camera_id: int = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
):
    """获取事件列表（分页、过滤）"""
    query = db.query(Event)

    # 过滤条件
    if event_type:
        query = query.filter(Event.event_type == event_type)
    if person_name:
        query = query.filter(Event.person_name.contains(person_name))
    if camera_id:
        query = query.filter(Event.camera_id == camera_id)
    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
            query = query.filter(Event.timestamp >= start)
        except ValueError:
            pass
    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
            query = query.filter(Event.timestamp <= end)
        except ValueError:
            pass

    # 总数
    total = query.count()

    # 分页
    events = (
        query
        .order_by(desc(Event.timestamp))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "items": [e.to_dict() for e in events],
    }


@router.get("/events/timeline")
def event_timeline(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    """获取时间线数据（最近 N 小时）"""
    since = datetime.utcnow() - timedelta(hours=hours)
    events = (
        db.query(Event)
        .filter(Event.timestamp >= since)
        .order_by(desc(Event.timestamp))
        .limit(200)
        .all()
    )

    return {
        "hours": hours,
        "total": len(events),
        "items": [e.to_dict() for e in events],
    }


@router.get("/events/stats")
def event_stats(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """获取统计数据"""
    since = datetime.utcnow() - timedelta(days=days)

    # 事件总数
    total_events = db.query(Event).filter(Event.timestamp >= since).count()

    # 按类型统计
    type_stats = (
        db.query(Event.event_type, func.count(Event.id))
        .filter(Event.timestamp >= since)
        .group_by(Event.event_type)
        .all()
    )

    # 按人员统计
    person_stats = (
        db.query(Event.person_name, func.count(Event.id))
        .filter(Event.timestamp >= since)
        .group_by(Event.person_name)
        .order_by(desc(func.count(Event.id)))
        .limit(10)
        .all()
    )

    # 按小时统计（最近24小时）
    hourly_since = datetime.utcnow() - timedelta(hours=24)
    hourly_events = (
        db.query(Event)
        .filter(Event.timestamp >= hourly_since)
        .all()
    )

    hourly_counts = {}
    for e in hourly_events:
        hour = e.timestamp.strftime("%H:00")
        hourly_counts[hour] = hourly_counts.get(hour, 0) + 1

    return {
        "days": days,
        "total_events": total_events,
        "by_type": {t: c for t, c in type_stats},
        "by_person": {p: c for p, c in person_stats},
        "hourly": hourly_counts,
    }


@router.get("/events/{event_id}")
def get_event(event_id: int, db: Session = Depends(get_db)):
    """获取事件详情"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    return event.to_dict()


@router.delete("/events/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    """删除事件"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    db.delete(event)
    db.commit()
    return {"message": "事件已删除"}


from pydantic import BaseModel

class LabelRequest(BaseModel):
    person_id: int

@router.post("/events/{event_id}/label")
def label_event_identity(event_id: int, req: LabelRequest, db: Session = Depends(get_db)):
    """用户对未识别的事件进行手动标注，并提取体态特征让系统自我学习"""
    from database.models import Person
    from core.reid_analyzer import reid_analyzer
    import json

    # 1. 寻找事件
    ev = db.query(Event).filter(Event.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="事件不存在")

    # 2. 寻找标注的目标人员
    person = db.query(Person).filter(Person.id == req.person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="目标标注人员不存在")

    # 3. 如果该事件记录有提取到即时的体态/衣着特征，则让系统自学习并反哺库
    learned = False
    if ev.body_features:
        try:
            new_feat = json.loads(ev.body_features)
            # 融合学习并更新该人员的体态特征
            updated_signature = reid_analyzer.merge_signatures(
                person.body_signature,
                new_feat,
                lr=0.35  # 自我学习率 35%
            )
            person.body_signature = updated_signature
            learned = True
        except Exception as e:
            # 捕获 JSON 解析错误或更新失败，不影响基本标注
            pass

    # 4. 更新当前事件关联的人员身份信息
    ev.person_id = person.id
    ev.person_name = person.name

    db.commit()

    return {
        "message": f"成功将事件标注为「{person.name}」",
        "learned": learned,
        "person_id": person.id,
        "person_name": person.name
    }
