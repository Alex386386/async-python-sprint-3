import asyncio
import json
import os
import time
from asyncio import StreamReader, StreamWriter

from aiologger import Logger

from config import configure_server_logging, server_arg_parser
from constants import HOST, PORT


class Server:
    def __init__(self, logger: Logger) -> None:
        self.connections: dict = {}
        self.logger: Logger = logger
        self.message_list: list = []
        self.channels: dict = {}
        self.channels_message: dict = {}
        self.usernames: dict = {}
        self.addresses: dict = {}
        if os.path.exists('server_state.json'):
            self.load_state_from_file()

    async def handle_client(self, reader: StreamReader,
                            writer: StreamWriter) -> None:
        address = writer.get_extra_info('peername')
        self.connections[address] = writer
        await self.logger.info(f'Start serving {address}')

        while True:
            data = await reader.read(1000)
            my_address = writer.get_extra_info('peername')

            if not data:
                await self.logger.info(f'Connection {address} lost')
                if my_address in self.connections:
                    del self.connections[my_address]
                writer.close()
                break

            try:
                message = data.decode('UTF-8')
            except UnicodeDecodeError:
                my_address = writer.get_extra_info('peername')
                await self.logger.info(f'Unacceptable type of message.')
                self.connections[my_address].write(
                    b'This message has unacceptable type!\n')
                await self.connections[my_address].drain()
                continue

            if message.strip() == '':
                continue

            if my_address not in self.usernames:
                if self.message_list and message.strip() not in self.usernames.values():
                    last_messages = ''.join(
                        message[0] for message in self.message_list[-20:])
                    writer.write(last_messages.encode())
                    await writer.drain()

                if self.message_list and message.strip() in self.usernames.values():
                    last_messages_rev = []
                    for message_text in self.message_list[::-1]:
                        if message_text[2] == message.strip():
                            break
                        last_messages_rev.append(message_text[0])
                    last_messages = ''.join(
                        text for text in list(reversed(last_messages_rev)))
                    writer.write(last_messages.encode())
                    await writer.drain()
                self.usernames[my_address] = message.strip()
                self.addresses[message.strip()] = my_address
                continue

            channel_name = message.split()[0]
            if 'quit' in message.strip():
                await self.logger.info(
                    f'Connection {my_address} closed by client')
                if my_address in self.connections:
                    del self.connections[my_address]
                writer.write(b'SERVER_SHUTDOWN\n')
                await writer.drain()
                writer.close()
                break

            elif message.startswith('/'):
                await self.command_received(message[1:], my_address)

            elif channel_name in self.channels.keys():
                channel_name, message_text = message.split(' ', 1)

                if message_text.startswith('/'):
                    message = message.split(' ', 1)[1].strip()
                    await self.command_received(message[1:], my_address, channel_name)
                    continue

                send_text = f'{self.usernames[my_address]}: ' + message_text
                send_time = time.time()
                name = self.usernames[my_address]
                self.channels_message[channel_name].append(
                    (send_text, send_time, name,))
                for address in self.channels[channel_name]:
                    if address != my_address:
                        self.connections[address].write(send_text.encode())
                        await self.connections[address].drain()

            elif channel_name not in self.channels.keys():
                name = self.usernames[my_address]
                send_text = f"{name}: {message}"
                for client_address, client_writer in self.connections.items():
                    if not any(client_address in addresslist for addresslist in self.channels.values()):
                        if client_address != my_address:
                            client_writer.write(send_text.encode())
                            await client_writer.drain()
                send_time = time.time()
                self.message_list.append((send_text, send_time, name,))

    async def command_received(self,
                               command: str,
                               address: str,
                               channel_name: str = None) -> None:
        writer = self.connections[address]

        if command.startswith('join '):
            channel_name = command.split(' ', 1)[1].strip()
            if channel_name in self.channels:
                self.channels[channel_name].append(address)

                if self.channels_message[channel_name]:
                    last_messages_rev = []
                    for message_text in reversed(
                            self.channels_message[channel_name]):
                        if message_text[2] == self.usernames[address]:
                            break
                        last_messages_rev.append(message_text[0])
                    last_messages = f'Вы подключились к чату {channel_name}\n' + ''.join(
                        text for text in list(reversed(last_messages_rev)))
                    writer.write(last_messages.encode())

                elif not self.channels_message[channel_name]:
                    last_messages = f'Вы подключились к чату {channel_name}\n'
                    writer.write(last_messages.encode())
                await writer.drain()
            else:
                writer.write(b'Channel does not exist\n')
                await writer.drain()

        elif command.startswith('leave '):
            channel_name = command.split(' ', 1)[1].strip()
            if channel_name in self.channels and address in self.channels[
                channel_name]:
                self.channels[channel_name].remove(address)
                last_messages_rev = []
                name = self.usernames[address]
                for message_text in self.message_list[::-1]:
                    if message_text[2] == name:
                        break
                    last_messages_rev.append(message_text[0])
                last_messages = ''.join(
                    text for text in list(reversed(last_messages_rev)))
                writer.write(last_messages.encode())
                await writer.drain()
            else:
                writer.write(b'You are not in this channel\n')
                await writer.drain()

        elif command.startswith('create '):
            channel_name = command.split(' ', 1)[1].strip()
            if channel_name not in self.channels:
                self.channels[channel_name] = [address]
                self.channels_message[channel_name] = []
                writer.write(
                    f'Вы подключились к чату {channel_name}\n'.encode())
                await writer.drain()
            else:
                writer.write(b'Channel already exists\n')
                await writer.drain()

        elif command.startswith('private '):
            recipient, message = command.split(' ', 2)[1:]
            if recipient.strip() in self.addresses:
                message_text = f'{self.usernames[address]}: ' + f'(private) {message}'
                self.connections[self.addresses[recipient]].write(
                    message_text.encode())
                await self.connections[self.addresses[recipient]].drain()
            else:
                writer.write(b'There is no user with such name.\n')
                await writer.drain()

        elif command.startswith('invite '):
            username = command.split(' ', 1)[1].strip()
            if username in self.addresses:
                user_address = self.addresses[username]
                message = f'Вы приглашены в группу ({channel_name})\n'
                end_of_message = f'Для вступления введите команду "/join {channel_name}"\n'
                send_text = message + end_of_message
                self.connections[user_address].write(send_text.encode())
                await self.connections[user_address].drain()
            else:
                writer.write(b'There is no user with such name.\n')
                await writer.drain()

    async def remove_old_messages(self) -> None:
        while True:
            await self.logger.info('Checking the messages time.')
            current_time = time.time()
            self.message_list = [(msg, timestamp, _) for (msg, timestamp, _) in
                                 self.message_list if
                                 current_time - timestamp < 60 * 60]
            if self.channels_message:
                for channel, channel_msg in self.channels_message.items():
                    current_time = time.time()
                    self.channels_message[channel] = [(msg, timestamp, _) for
                                                      (msg, timestamp, _) in
                                                      channel_msg if
                                                      current_time - timestamp < 60 * 60]
            await asyncio.sleep(60)

    async def save_state_to_file(self):
        data_to_save = {
            "message_list": self.message_list,
            "channels": {str(channel): [] for channel in self.channels.keys()},
            "channels_message": {str(channel): messages for channel, messages
                                 in self.channels_message.items()},
            "usernames": {str(address): username for address, username in
                          self.usernames.items()}
        }
        with open('server_state.json', 'w') as file:
            json.dump(data_to_save, file)

    def load_state_from_file(self):
        with open('server_state.json', 'r') as file:
            data_loaded = json.load(file)
        self.message_list = data_loaded["message_list"]
        self.channels = {channel: [] for channel in
                         data_loaded["channels"].keys()}
        self.channels_message = {channel: messages for channel, messages
                                 in data_loaded["channels_message"].items()}
        self.usernames = {eval(address): username for address, username in
                          data_loaded["usernames"].items()}


async def main(host: str = HOST, port: int = PORT) -> None:
    server_logger = await configure_server_logging()
    server = Server(server_logger)
    cleanup_task = asyncio.create_task(server.remove_old_messages())
    server_coro = await asyncio.start_server(server.handle_client, host, port)

    try:
        async with server_coro:
            await server_coro.serve_forever()
    except asyncio.CancelledError:
        cleanup_task.cancel()
        server_logger.info('Server shutting down...')
        for transport in server.connections.values():
            transport.write(b'SERVER_SHUTDOWN\n')
            transport.close()
        server_logger.info('Server stopped')
    finally:
        server_logger.info('logger finished its work')
        await server.save_state_to_file()
        await server_logger.shutdown()


if __name__ == '__main__':
    parser = server_arg_parser()
    args = parser.parse_args()
    try:
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        pass
