#!/usr/bin/python3

import socket
import asyncio
import getpass
import sys

class FtpConnection:
	def __init__(self, loop):
		self.loop = loop
		self.FTP_HOST = '127.0.0.1'
		self.FTP_CONTROL_PORT = 26000
		self.FTP_DATA_PORT = 26001
		self.control_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

	async def connect(self):
		await self.loop.sock_connect(self.control_sock, (self.FTP_HOST, self.FTP_CONTROL_PORT))
		await self.loop.sock_connect(self.data_sock, (self.FTP_HOST, self.FTP_DATA_PORT))
		self.successful_connect_msg = await self.loop.sock_recv(self.control_sock, 10000)
		print(self.successful_connect_msg.decode())
		FTP_authentication = FtpAuthentication(self.loop, self.control_sock)

class FtpAuthentication:
	def __init__(self, loop, control_sock):
		self.loop = loop
		self.control_sock = control_sock
		self.looged_in = False
		self.loop.create_task(self.auth_to_the_server())

	async def auth_to_the_server(self):
		self.server_login = input('Name: ')
		await self.loop.sock_sendall(self.control_sock, self.server_login.encode())
		self.pass_required_msg = await self.loop.sock_recv(self.control_sock, 10000)
		print(self.pass_required_msg.decode())
		getpass.getpass('Password: ')
		self.login_msg = await self.loop.sock_recv(self.control_sock, 10000)
		print(self.login_msg.decode())
		FTP_commands_receiver = FtpCommandsReceiver(self.loop, self.control_sock)

class FtpCommandsReceiver:
	def __init__(self, loop, control_sock):
		self.loop = loop
		self.control_sock = control_sock
		self.loop.create_task(self.recieve_data())
		self.commands_to_handle = {
					      'exit': self.exit_handler
					  }

	async def recieve_data(self):
		while True:
			self.data_to_send = input('ftp> ')
			if self.data_to_send == '':
				continue
			await self.loop.sock_sendall(self.control_sock, self.data_to_send.encode())
			try:
				await self.commands_to_handle.get(self.data_to_send)()
			except TypeError:
				pass
			self.received_data = await self.loop.sock_recv(self.control_sock, 10000)
			print(self.received_data.decode())
			if not self.received_data:
				break
		print('Connection closed by the server')
		self.control_sock.close()

	async def exit_handler(self):
		self.loop.stop()

if __name__ == '__main__':
	loop = asyncio.get_event_loop()
	FTP_connection = FtpConnection(loop)
	task = loop.create_task(FTP_connection.connect())
	loop.run_forever()
