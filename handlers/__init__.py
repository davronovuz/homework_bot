from aiogram import Router

from handlers import common, student, teacher


def setup_routers() -> Router:
    router = Router(name="main")
    router.include_router(common.router)
    router.include_router(teacher.router)
    router.include_router(student.router)
    router.include_router(common.fallback_router)
    return router
