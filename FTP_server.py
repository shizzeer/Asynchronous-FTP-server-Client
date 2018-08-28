#!/usr/bin/python3

import socket
import asyncio

class ftpEchoServer:
	def __init__(self, loop):
		self.loop = loop
		self.HOST = ''
		self.create_control_connection()
		self.create_data_connection()
		self.ip_addr_of_the_server = socket.gethostbyname(socket.gethostname())
		self.loop.create_task(self.wait_for_connections())

	def create_control_connection(self):
		self.CONTROL_PORT = 26000
		self.control_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		print(self.control_sock)
		self.control_sock.bind((self.HOST, self.CONTROL_PORT))
		self.control_sock.listen(1)
		self.control_sock.setblocking(False)

	def create_data_connection(self):
		self.DATA_PORT = 26001
		self.data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		print(self.data_sock)
		self.data_sock.bind((self.HOST, self.DATA_PORT))
		self.data_sock.listen(1)
		self.data_sock.setblocking(False)

	async def wait_for_connections(self):
		while True:
			self.control_conn, self.control_addr = await self.loop.sock_accept(self.control_sock)
			self.data_conn, self.data_addr = await self.loop.sock_accept(self.data_sock)
			print('Control connection from: ', self.control_addr)
			print('Data connection from: ', self.data_addr)
			FTP_auth_handler = ftpAuthenticationHandler(self.control_conn, self.loop, self.control_sock, self.data_sock, self.ip_addr_of_the_server)
			await FTP_auth_handler.connected_successful_msg()

class ftpAuthenticationHandler:
	def __init__(self, control_conn, loop, control_sock, data_sock, ip_addr):
		self.ip_addr = ip_addr
		self.loop = loop
		self.control_sock = control_sock
		self.data_sock = data_sock
		self.control_client = control_conn
		self.logged_in = False
		self.username = ''
		self.user_command_for_login = { "user": self.user }
		
	async def connected_successful_msg(self):
		successful_msg = b'Connected to the FTP server [' +  self.ip_addr.encode() + b']\n'
		await self.loop.sock_sendall(self.control_client, successful_msg)
		self.loop.create_task(self.main_auth_handler())

	async def login_successful(self):
		self.logged_in = True
		self.welcome_msg = b'230-\n'\
						   b'230- -------------------------------------------------------------------------\n'\
						   b'230- WELCOME!	This server is created by Kamil Szpakowski. You are logged in\n'\
						   b'230-            as anonymous.\n'\
						   b'230- -------------------------------------------------------------------------'
		await self.loop.sock_sendall(self.control_client, self.welcome_msg)
	
	async def main_auth_handler(self):
		self.username = await self.loop.sock_recv(self.control_client, 10000)
		self.username = self.username.decode()
		getting_password_msg = b'331 Password required for USER.'
		await self.loop.sock_sendall(self.control_client, getting_password_msg)
		if self.username == 'anonymous':
			self.loop.create_task(self.login_successful())
			FTP_commands_handler = ftpCommandsHandler(self.control_client, self.loop, self.username)
		else:
			self.login_failed_msg = b'530 Please Login with USER and PASS.\nLogin failed.'
			await self.loop.sock_sendall(self.control_client, self.login_failed_msg)
			self.loop.create_task(self.command_auths_handler())
	
	async def command_auths_handler(self):
		while True:
			self.data_from_client = await self.loop.sock_recv(self.control_client, 10000)
			self.command = self.data_from_client.decode().split(' ')[0]
			try:
				await self.user_command_for_login.get(self.command)()
				if self.username == 'anonymous':
					await self.login_successful()
					FTP_commands_handler = ftpCommandsHandler(self.control_client, self.loop, self.username)
					break
			except TypeError:
				await self.loop.sock_sendall(self.control_client, self.login_failed_msg)
			
	async def user(self):
		try:
			self.username = self.data_from_control_sock.decode().split(' ')[1]
			if self.username != 'anonymous':
				await self.loop.sock_sendall(self.control_client, self.login_failed_msg)
		except IndexError:
			await self.loop.sock_sendall(self.control_client, b'usage: user <username>')

class ftpCommandsHandler:
	def __init__(self, conn, loop, username):
		self.client = conn
		self.loop = loop
		self.send_mode = 'ascii'
		self.username = username
		self.ftp_commands = {
					'type': self.change_send_mode,
					'user': self.change_user,
					'exit': self.exit
				     }
		self.loop.create_task(self.execute_command())

	async def execute_command(self):
		while True:
			self.command = await self.loop.sock_recv(self.client, 10000)
			try:
				self.arg = self.command.decode().split(' ')[1]
			except IndexError:
				self.arg = ''
			try:
				self.loop.create_task(self.ftp_commands.get(self.command.decode().split(' ')[0])())
			except TypeError:
				await self.loop.sock_sendall(self.client, b'?Invalid command')
			if not self.command:
				break
		print('Connection closed')
		self.client.close()

	async def change_send_mode(self):
		try:
			if self.arg == 'ascii':
				self.send_mode = self.arg
				await self.loop.sock_sendall(self.client, b'200 TYPE set to A.')
			elif self.arg == 'binary':
				self.send_mode = self.arg
				await self.loop.sock_sendall(self.client, b'200 TYPE set to I.')
			else:
				await self.loop.sock_sendall(self.client, self.arg.encode() + b': ' + 'unknown mode')
		except IndexError:
			await self.loop.sock_sendall(self.client, b'Using ' + self.send_mode.encode() + b' for transfer files.')

	async def change_user(self):
		if not self.arg:
			await self.loop.sock_sendall(self.client, b'usage: user <username>')
		elif self.username == 'anonymous':
			await self.loop.sock_sendall(self.client, b'503 You are already logged in!\nLogin failed.')

	async def exit(self):
		await self.loop.sock_sendall(self.client, b'221 Goodbye.')
		print('Connection closed')
		self.client.close()

if __name__ == '__main__':
	loop = asyncio.get_event_loop()
	FTP_echo = ftpEchoServer(loop)
	try:
		loop.run_forever()
	except KeyboardInterrupt:
		loop.close()
