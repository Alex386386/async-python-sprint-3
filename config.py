import argparse

from aiologger import Logger
from aiologger.formatters.base import Formatter
from aiologger.handlers.files import AsyncFileHandler

from constants import BASE_DIR, LOG_FORMAT, PORT


async def configure_server_logging() -> Logger:
    log_format = LOG_FORMAT
    formatter = Formatter(fmt=log_format)
    logger = Logger.with_default_handlers(name="server", level="INFO",
                                          formatter=formatter)
    log_dir = BASE_DIR / 'logs'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / 'server.log'
    file_handler = AsyncFileHandler(filename=str(log_file), mode="a")
    file_handler.formatter = formatter
    logger.add_handler(file_handler)
    return logger


async def configure_client_logging() -> Logger:
    log_format = LOG_FORMAT
    formatter = Formatter(fmt=log_format)
    logger = Logger.with_default_handlers(name="client", level="INFO",
                                          formatter=formatter)
    log_dir = BASE_DIR / 'logs'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / 'client.log'
    file_handler = AsyncFileHandler(filename=str(log_file), mode="a")
    file_handler.formatter = formatter
    logger.add_handler(file_handler)
    return logger


def server_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Streem server.')
    parser.add_argument('-H', '--host', type=str, default='127.0.0.1',
                        help='Host to run the server on.')
    parser.add_argument('-p', '--port', type=int, default=PORT,
                        help='Port to run the server on.')
    return parser


def client_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Streem client.')
    parser.add_argument('username', type=str,
                        help='Username to connect to the server.')
    parser.add_argument('-H', '--host', type=str, default='127.0.0.1',
                        help='Host to connect to.')
    parser.add_argument('-p', '--port', type=int, default=PORT,
                        help='Port to connect to.')
    return parser
