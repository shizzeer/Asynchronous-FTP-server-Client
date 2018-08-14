#!/usr/bin/python3

import socket
import asyncio
import getpass

class FtpConnection:
	def __init__(self, loop):
		self.loop = loop
		self.FTP_HOST = '127.0.0.1'
		self.FTP_PORT = 26000
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

	async def connect(self):
		await self.loop.sock_connect(self.sock, (self.FTP_HOST, self.FTP_PORT))
		self.successful_connect_msg = await self.loop.sock_recv(self.sock, 10000)
		print(self.successful_connect_msg.decode())
		FTP_authentication = FtpAuthentication(self.loop, self.sock)

class FtpAuthentication:
	def __init__(self, loop, sock):
		self.loop = loop
		self.sock = sock
		self.looged_in = False
		self.loop.create_task(self.auth_to_the_server())

	async def auth_to_the_server(self):
		self.server_login = input('Name: ')
		await self.loop.sock_sendall(self.sock, self.server_login.encode())
		self.pass_required_msg = await self.loop.sock_recv(self.sock, 10000)
		print(self.pass_required_msg.decode())
		getpass.getpass('Password: ')
		self.login_msg = await self.loop.sock_recv(self.sock, 10000)
		print(self.login_msg.decode())
		FTP_commands_receiver = FtpCommandsReceiver(self.loop, self.sock)

class FtpCommandsReceiver:
	def __init__(self, loop, sock):
		self.loop = loop
		self.sock = sock
		self.loop.create_task(self.recieve_data())

	async def recieve_data(self):
		while True:
			self.data_to_send = input('ftp> ')
			await self.loop.sock_sendall(self.sock, self.data_to_send.encode())
			self.received_data = await self.loop.sock_recv(self.sock, 10000)
			print(self.received_data.decode())
			if not self.received_data:
				break
		print('Connection closed by the server')
		self.sock.close()

if __name__ == '__main__':
	loop = asyncio.get_event_loop()
	FTP_connection = FtpConnection(loop)
	task = loop.create_task(FTP_connection.connect())
	loop.run_forever()
