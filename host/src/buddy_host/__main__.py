import uvicorn

from buddy_host.app import create_app
from buddy_host.config import load_config


def main() -> None:
    config = load_config()
    uvicorn.run(create_app(config), host=config.listen_host, port=config.listen_port)


if __name__ == "__main__":
    main()
