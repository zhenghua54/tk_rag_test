# -*- coding: utf-8 -*-
"""系统基础接口"""
import datetime
from fastapi import APIRouter
from src.api.response import ResponseBuilder

router = APIRouter(
    tags=["基础接口"]
)


@router.get("/health")
async def health_check():
    """健康检查接口"""
    # 使用UTC时间格式化当前时间
    now = datetime.datetime.now(datetime.timezone.utc)
    iso_time = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    return ResponseBuilder.success(data={
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": iso_time
    }).dict()
