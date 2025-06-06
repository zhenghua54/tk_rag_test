# -*- coding: utf-8 -*-
"""系统基础接口"""
from fastapi import APIRouter
from config.settings import Config
from src.api.response import ResponseBuilder

router = APIRouter(prefix=Config.API_PREFIX)

@router.get("/health")
async def health_check():
    """健康检查接口"""
    return ResponseBuilder.success(data={
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": "2025-06-04T10:00:00Z"
    }).dict()