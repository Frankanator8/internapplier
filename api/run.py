import uvicorn

from .ai_provider import get_server_port
from .constants import SERVER_HOST


def main() -> None:
    uvicorn.run("api.server:app", host=SERVER_HOST, port=get_server_port(), reload=False)


if __name__ == "__main__":
    main()
