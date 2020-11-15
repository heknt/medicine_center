import sched
import time
import os

from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import AuthJWTException
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi_utils.tasks import repeat_every

from app.api import auth, default, profiles, disease_history
from app.main import app
from app.storage.token_storage import RedisTokenStorage
from config import JwtSettings, DEBUG_LOGIN, CLEARED_DIR, DISEASE_HISTORY_STATE_FILES


@AuthJWT.load_config
def get_config():
    return JwtSettings()


@AuthJWT.token_in_denylist_loader
def check_if_token_in_denylist(decrypted_token):
    jti = decrypted_token['jti']
    in_redis = app.state.redis.get_token(jti)
    return in_redis == RedisTokenStorage.TOKEN_VALID_STATE


@app.on_event('startup')
def startup_event():
    if not DEBUG_LOGIN:
        app.state.redis = RedisTokenStorage()


@app.on_event('shutdown')
def shutdown_event():
    if not DEBUG_LOGIN:
        app.state.redis.close()


@app.exception_handler(AuthJWTException)
def authjwt_exception_handler(request: Request, exc: AuthJWTException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )


@app.on_event("startup")
@repeat_every(seconds=600)
async def clean_history_file():
    """
    Clear files that store more than 1 hour in disease history every 10 minute
    """
    files = os.listdir(CLEARED_DIR)

    for file in files:
        time_created = os.path.getctime(CLEARED_DIR + file)
        time_life_file = (time.time() - time_created) // 60

        if file not in DISEASE_HISTORY_STATE_FILES:
            if time_life_file > 3600:
                os.remove(CLEARED_DIR + file)


app.include_router(default.router)
app.include_router(profiles.router)
app.include_router(auth.router, prefix='/auth', tags=['auth'])
app.include_router(disease_history.router, prefix='/history', tags=['history'])
app.mount("/static", StaticFiles(directory="static"), name='static')

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
