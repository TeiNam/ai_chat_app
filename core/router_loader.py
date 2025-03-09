import importlib
import inspect
import logging
import os
import pkgutil
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, FastAPI

logger = logging.getLogger(__name__)


def get_router_modules(package_path: str, package_name: str) -> List[str]:
    """
    지정된 패키지 내의 모든 모듈 이름을 조회합니다.

    Args:
        package_path: 패키지 디렉토리 경로
        package_name: 패키지 이름

    Returns:
        List[str]: 모듈 이름 목록
    """
    return [
        f"{package_name}.{name}"
        for _, name, is_pkg in pkgutil.iter_modules([package_path])
        if not is_pkg and name != "__init__"
    ]


def get_router_from_module(module_name: str) -> Optional[APIRouter]:
    """
    모듈에서 APIRouter 인스턴스를 찾습니다.

    Args:
        module_name: 모듈 이름

    Returns:
        Optional[APIRouter]: 찾은 라우터 또는 None
    """
    try:
        module = importlib.import_module(module_name)

        # 모듈에서 'router' 변수 찾기
        if hasattr(module, "router") and isinstance(module.router, APIRouter):
            return module.router

        # 모듈 내 모든 변수 검사
        for _, obj in inspect.getmembers(module):
            if isinstance(obj, APIRouter):
                return obj

        return None
    except Exception as e:
        logger.error(f"모듈 '{module_name}' 로드 중 오류 발생: {e}")
        return None


def extract_router_info(router: APIRouter) -> Dict[str, Any]:
    """
    라우터에서 태그 및 경로 정보를 추출합니다.

    Args:
        router: APIRouter 인스턴스

    Returns:
        Dict[str, Any]: 라우터 정보
    """
    routes = router.routes
    tags = set()

    # 라우터에 설정된 태그 수집
    for route in routes:
        if hasattr(route, "tags") and route.tags:
            tags.update(route.tags)

    # 태그가 없으면 모듈 이름이나 라우터 이름 사용
    if not tags and hasattr(router, "prefix"):
        # 접두사가 있으면 접두사에서 태그 추출
        prefix = router.prefix or ""
        if prefix.startswith("/"):
            # '/api/users' -> 'users'
            tag = prefix.split("/")[-1] if prefix.split("/")[-1] else "api"
            tags.add(tag)

    return {
        "tags": list(tags) if tags else ["api"],
        "routes_count": len(routes)
    }


def auto_register_routers(app: FastAPI, package_name: str = "api.router", prefix: str = "/api") -> List[Dict[str, Any]]:
    """
    지정된 패키지 내의 모든 라우터를 자동으로 등록합니다.

    Args:
        app: FastAPI 애플리케이션 인스턴스
        package_name: 라우터 모듈이 있는 패키지 이름
        prefix: API 경로 접두사

    Returns:
        List[Dict[str, Any]]: 등록된 라우터 정보 목록
    """
    # 패키지 경로 찾기
    try:
        package = importlib.import_module(package_name)
        package_path = os.path.dirname(package.__file__)
    except (ImportError, AttributeError) as e:
        logger.error(f"패키지 '{package_name}' 로드 실패: {e}")
        return []

    # 모듈 이름 목록 가져오기
    module_names = get_router_modules(package_path, package_name)

    # 등록된 라우터 정보 저장
    registered_routers = []

    # 각 모듈에서 라우터 찾아 등록
    for module_name in module_names:
        router = get_router_from_module(module_name)

        if router:
            # 모듈 이름에서 태그 추출 (router_name_format.py -> name_format)
            module_tag = module_name.split(".")[-1].replace("_router", "")

            # 태그가 없으면 모듈 이름 기반으로 태그 추가
            if not router.tags:
                router.tags = [module_tag]

            # 라우터 등록
            app.include_router(router, prefix=prefix)

            # 라우터 정보 추출 및 저장
            router_info = extract_router_info(router)
            router_info["module"] = module_name
            router_info["name"] = module_tag

            registered_routers.append(router_info)

            logger.info(f"라우터 자동 등록 완료: {module_name} ({router_info['routes_count']} 경로, 태그: {router_info['tags']})")

    return registered_routers