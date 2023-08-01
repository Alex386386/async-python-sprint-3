import asyncio
from typing import Optional

import aioconsole
from aiologger import Logger

from config import configure_client_logging, client_arg_parser
from constants import PORT, HOST


class Client:
    def __init__(self,
                 username: str,
                 logger: Logger,
                 server_host: str = HOST,
                 server_port: int = PORT) -> None:
        self.reader, self.writer = None, None
        self.logger = logger
        self.server_host: str = server_host
        self.server_port: int = server_port
        self.connected: bool = False
        self.error_occurred: bool = False
        self.chat_name: Optional[str] = None
        self.username: str = username

    async def connect(self) -> None:
        self.reader, self.writer = await asyncio.open_connection(
            self.server_host, self.server_port)
        self.connected = True
        await self.send(self.username)

    async def send(self, message: str = '') -> None:
        self.writer.write(message.encode() + b'\n')
        await self.writer.drain()

    async def receive(self) -> None:
        while self.connected:
            try:
                data = await self.reader.readline()
                message = data.decode()
                if message == 'SERVER_SHUTDOWN\n':
                    await self.logger.info('Server shutdown.')
                    self.connected = False
                else:
                    print(message.strip())
            except Exception as e:
                self.error_occurred = True
                await self.logger.error(f'An error occurred: {e}')
                await self.disconnect()
                break

    async def disconnect(self) -> None:
        self.writer.close()
        await self.writer.wait_closed()
        await self.logger.info('Server disconnect.')

    async def __aenter__(self) -> 'Client':
        await self.connect()
        await self.logger.info('Server connected.')
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.disconnect()

    def check_message(self, message: str) -> str:
        if message.startswith('/'):
            channel_message = message[1:].split()
            if channel_message[0] == 'invite':
                return f'{self.chat_name} {message}'
            if channel_message[0] == 'create':
                self.chat_name = channel_message[1]
            if channel_message[0] == 'join':
                self.chat_name = channel_message[1]
            if channel_message[0] == 'leave':
                self.chat_name = None
        elif self.chat_name is not None:
            message = f'{self.chat_name} {message}'
        return message


async def main(username: str, host: str = HOST, port: int = PORT) -> None:
    client_logger = await configure_client_logging()
    try:
        async with Client(username, client_logger, host, port) as client:
            await client_logger.info(f'Client {username} started')

            async def handle_input():
                while True:
                    try:
                        message = await aioconsole.ainput()
                    except Exception as e:
                        await client_logger.error(
                            f'Error during the enter: {e}')
                        continue
                    message = client.check_message(message)
                    await client.send(message)

            input_task = asyncio.create_task(handle_input())
            receive_task = asyncio.create_task(client.receive())

            while True:
                if not client.connected or client.error_occurred:
                    input_task.cancel()
                    receive_task.cancel()
                    break
                await asyncio.sleep(0.01)

            if client.error_occurred:
                client_logger.error('An error occurred in the receive task.')
    finally:
        client_logger.info('logger finished its work')
        await client_logger.shutdown()


if __name__ == "__main__":
    parser = client_arg_parser()
    args = parser.parse_args()
    try:
        asyncio.run(main(args.username, args.host, args.port))
    except KeyboardInterrupt:
        pass
