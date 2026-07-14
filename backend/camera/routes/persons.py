"""
人员管理路由
"""
import os
import shutil
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import desc

import config
from database.db import get_db
from database.models import Person, Event
from core.pipeline import pipeline_manager

router = APIRouter()


@router.get("/persons")
def list_persons(db: Session = Depends(get_db)):
    """获取已注册人员列表"""
    persons = db.query(Person).filter(Person.is_active == True).order_by(Person.name).all()
    return {"items": [p.to_dict() for p in persons]}


@router.post("/persons")
async def create_person(
    name: str = Form(...),
    department: str = Form(""),
    role: str = Form(""),
    face_image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """注册新人员（含人脸照片上传）"""
    # 保存照片
    ext = os.path.splitext(face_image.filename)[1] or ".jpg"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    import uuid
    unique_suffix = uuid.uuid4().hex[:8]
    filename = f"face_{timestamp}_{unique_suffix}{ext}"
    filepath = config.FACES_DIR / filename

    try:
        with open(filepath, "wb") as f:
            content = await face_image.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"照片保存失败: {e}")

    # 创建数据库记录
    person = Person(
        name=name,
        department=department,
        role=role,
        face_image_path=str(filepath),
    )
    db.add(person)
    db.commit()
    db.refresh(person)

    # 注册人脸特征
    registered = False
    for pipeline in pipeline_manager.pipelines.values():
        success = pipeline.face_recognizer.register_face(
            person.id, name, str(filepath)
        )
        if success:
            registered = True
        break  # 只需在一个管道中注册（共享识别器）

    if not registered:
        # 即使特征提取失败也保留记录，可以后续重试
        return {
            "person": person.to_dict(),
            "face_registered": False,
            "message": "人员已创建，但人脸特征提取失败，请上传清晰的正面照片重试"
        }

    return {
        "person": person.to_dict(),
        "face_registered": True,
        "message": "注册成功"
    }


@router.get("/persons/{person_id}")
def get_person(person_id: int, db: Session = Depends(get_db)):
    """获取人员详情"""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="人员不存在")
    return person.to_dict()


@router.put("/persons/{person_id}")
async def update_person(
    person_id: int,
    name: str = Form(None),
    department: str = Form(None),
    role: str = Form(None),
    face_image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    """更新人员信息"""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="人员不存在")

    if name is not None:
        person.name = name
    if department is not None:
        person.department = department
    if role is not None:
        person.role = role

    # 更新照片
    if face_image:
        ext = os.path.splitext(face_image.filename)[1] or ".jpg"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        import uuid
        unique_suffix = uuid.uuid4().hex[:8]
        filename = f"face_{timestamp}_{unique_suffix}{ext}"
        filepath = config.FACES_DIR / filename

        with open(filepath, "wb") as f:
            content = await face_image.read()
            f.write(content)

        person.face_image_path = str(filepath)

        # 重新注册人脸
        for pipeline in pipeline_manager.pipelines.values():
            pipeline.face_recognizer.register_face(
                person.id, person.name, str(filepath)
            )
            break

    person.updated_at = datetime.utcnow()
    db.commit()

    return {"person": person.to_dict(), "message": "更新成功"}


@router.delete("/persons/{person_id}")
def delete_person(person_id: int, db: Session = Depends(get_db)):
    """删除人员"""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="人员不存在")

    # 注销人脸
    for pipeline in pipeline_manager.pipelines.values():
        pipeline.face_recognizer.unregister_face(person_id)
        break

    person.is_active = False
    db.commit()

    return {"message": f"人员 {person.name} 已删除"}


@router.get("/persons/{person_id}/events")
def person_events(
    person_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """获取某人的事件记录"""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="人员不存在")

    events = (
        db.query(Event)
        .filter(Event.person_id == person_id)
        .order_by(desc(Event.timestamp))
        .limit(limit)
        .all()
    )

    return {
        "person": person.to_dict(),
        "events": [e.to_dict() for e in events],
    }
