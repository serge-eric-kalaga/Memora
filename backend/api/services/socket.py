from api.configs.logging import logDebug
import socketio

server = socketio.AsyncServer(
    cors_allowed_origins="*", async_mode="asgi", logger=True, engineio_logger=True
)


@server.event
async def connect(sid, x, y):
    logDebug(f"connect: {sid}")
    print(f"connect: {sid}")
    await server.emit("hello", "world")
