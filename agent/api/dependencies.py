from __future__ import annotations

from fastapi import HTTPException, Request

from agent.services.agent_write_actions import AgentWriteActionService
from agent.services.camera_management import CameraManagementService
from agent.services.chat_service import ChatService
from agent.services.knowledge_service import KnowledgeService
from agent.services.learning_service import LearningService
from agent.services.perception_service import PerceptionService
from agent.services.rectification_task_service import RectificationTaskService


def get_perception_service(request: Request) -> PerceptionService:
    return request.app.state.perception_service


def get_camera_management_service(request: Request) -> CameraManagementService:
    return request.app.state.camera_management_service


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


def get_write_action_service(request: Request) -> AgentWriteActionService:
    return request.app.state.agent_write_action_service


def get_knowledge_service(request: Request) -> KnowledgeService:
    service = request.app.state.knowledge_service
    if service is None or service.retriever is None:
        raise HTTPException(status_code=503, detail="knowledge retrieval is disabled")
    return service


def get_learning_service(request: Request) -> LearningService:
    return request.app.state.learning_service


def get_rectification_task_service(request: Request) -> RectificationTaskService:
    return request.app.state.rectification_task_service
