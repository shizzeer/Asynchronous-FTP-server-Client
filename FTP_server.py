#!/usr/bin/python3

import socket
import asyncio

class ftpEchoServer:
	def __init__(self, loop):
		self.loop = loop
		self.HOST = ''
		self.PORT = 26000
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.ip_addr_of_the_server = socket.gethostbyname(socket.gethostname())
		self.sock.bind((self.HOST, self.PORT))
		self.sock.listen(1)
		self.sock.setblocking(False)
		self.loop.create_task(self.wait_for_connections())

	async def wait_for_connections(self):
		while True:
			self.conn, self.addr = await self.loop.sock_accept(self.sock)
			print('Connection from: ', self.addr)
			FTP_auth_handler = ftpAuthenticationHandler(self.conn, self.loop, self.sock, self.ip_addr_of_the_server)
			await FTP_auth_handler.connected_successful_msg()

class ftpAuthenticationHandler:
	def __init__(self, conn, loop, sock, ip_addr):
		self.ip_addr = ip_addr
		self.loop = loop
		self.sock = sock
		self.client = conn
		self.logged_in = False
		self.username = ''
		self.user_command_for_login = { "user": self.user }
		
	async def connected_successful_msg(self):
		successful_msg = b'Connected to the FTP server [' +  self.ip_addr.encode() + b']\n'
		await self.loop.sock_sendall(self.client, successful_msg)
		self.loop.create_task(self.main_auth_handler())

	async def login_successful(self):
		self.logged_in = True
		self.welcome_msg = b'230-\n'\
						           b'230- -------------------------------------------------------------------------\n'\
						           b'230- WELCOME!	This server is created by Kamil Szpakowski. You are logged in\n'\
						           b'230-            as anonymous.\n'\
						           b'230- -------------------------------------------------------------------------'
		await self.loop.sock_sendall(self.client, self.welcome_msg)
	
	async def main_auth_handler(self):
		self.username = await self.loop.sock_recv(self.client, 10000)
		self.username = self.username.decode()
		getting_password_msg = b'331 Password required for USER.'
		await self.loop.sock_sendall(self.client, getting_password_msg)
		if self.username == 'anonymous':
			self.loop.create_task(self.login_successful())
			FTP_commands_handler = ftpCommandsHandler(self.client, self.loop)
		else:
			self.login_failed_msg = b'530 Please Login with USER and PASS.\nLogin failed.'
			await self.loop.sock_sendall(self.client, self.login_failed_msg)
			self.loop.create_task(self.command_auths_handler())
	
	async def command_auths_handler(self):
		while True:
			self.data_from_client = await self.loop.sock_recv(self.client, 10000)
			self.command = self.data_from_client.decode().split(' ')[0]
			try:
				await self.user_command_for_login.get(self.command)()
				if self.username == 'anonymous':
					await self.login_successful()
					FTP_commands_handler = ftpCommandsHandler(self.client, self.loop)
					break
			except TypeError:
				await self.loop.sock_sendall(self.client, self.login_failed_msg)
			
	async def user(self):
		try:
			self.username = self.data_from_client.decode().split(' ')[1]
			if self.username != 'anonymous':
				await self.loop.sock_sendall(self.client, self.login_failed_msg)
		except IndexError:
			await self.loop.sock_sendall(self.client, b'usage: user <username>\n')

class ftpCommandsHandler:
	def __init__(self, conn, loop):
		self.client = conn
		self.loop = loop
		self.ftp_commands = { "user": self.user }
		self.loop.create_task(self.execute_command())

	async def execute_command(self):
		while True:
			self.command = await self.loop.sock_recv(self.client, 10000)
			self.ftp_commands.get(self.command.decode())()

	def user(self):
		print('test')

if __name__ == '__main__':
	loop = asyncio.get_event_loop()
	FTP_echo = ftpEchoServer(loop)
	loop.run_forever()
