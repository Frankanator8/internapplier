import uvicorn

from .constants import DEFAULT_SERVER_PORT, SERVER_HOST


def main() -> None:
    uvicorn.run("api.server:app", host=SERVER_HOST, port=DEFAULT_SERVER_PORT, reload=False)


if __name__ == "__main__":
    main()
