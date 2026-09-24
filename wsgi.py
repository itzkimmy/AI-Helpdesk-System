"""WSGI entry point for production deployment with Gunicorn."""

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402

application = create_app()

if __name__ == '__main__':
    application.run()
