#!/usr/bin/python3

import socket
import asyncio
import getpass
import sys
import random
import os
from os import path


class FtpConnection:
    def __init__(self, loop):
        self.loop = loop
        self.FTP_HOST = '192.168.0.109'  # This is example ip. You have to type ip of the computere where the server is running.
        self.FTP_CONTROL_PORT = 25000
        self.control_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    async def connect(self):
        await self.loop.sock_connect(self.control_sock, (self.FTP_HOST, self.FTP_CONTROL_PORT))
        self.successful_connect_msg = await self.loop.sock_recv(self.control_sock, 10000)
        print(self.successful_connect_msg.decode())
        FTP_authentication = FtpAuthentication(self.loop, self.control_sock)
        await FTP_authentication.auth_to_the_server()


class FtpAuthentication:
    def __init__(self, loop, control_sock):
        self.loop = loop
        self.control_sock = control_sock
        self.logged_in = False
        self.username = ''

    async def auth_to_the_server(self):
        self.username = input('Name: ')
        if self.username == 'anonymous':
            self.logged_in = True
        await self.loop.sock_sendall(self.control_sock, self.username.encode())
        self.pass_required_msg = await self.loop.sock_recv(self.control_sock, 10000)
        print(self.pass_required_msg.decode())
        getpass.getpass('Password: ')
        self.login_msg = await self.loop.sock_recv(self.control_sock, 10000)
        print(self.login_msg.decode())
        FTP_commands_receiver = FtpCommandsReceiver(self.loop, self.control_sock, self.username, self.logged_in)
        await FTP_commands_receiver.recieve_data()


class FtpCommandsReceiver:
    def __init__(self, loop, control_sock, username, logged_in):
        self.loop = loop
        self.control_sock = control_sock
        self.send_mode = 'ascii'
        self.home_dir = os.getcwd()
        self.current_dir = self.home_dir
        self.commands_to_handle = {
                                      'ascii': self.ascii_mode,
                                      'binary': self.binary_mode,
                                      'ls': self.create_data_connection,
                                      'dir': self.create_data_connection,
                                      'lcd': self.change_local_dir,
                                      'get': self.download_file,
                                      'recv': self.download_file,
                                      'type': self.change_send_mode,
                                      'append': self.upload_file,
                                      'put': self.upload_file,
                                      'help': self.help,
                                      'exit': self.exit_handler,
                                      'bye': self.exit_handler
                                  }
        self.permitted_commands = { 
                                      'user': self.USER,
                                      'help': self.help,
                                      'exit': self.exit_handler,
                                      'bye': self.exit_handler
                                  }
        self.username = username
        self.logged_in = logged_in

    def ascii_mode(self):
	    self.send_mode = 'ascii'

    def binary_mode(self):
	    self.send_mode = 'binary'

    async def create_port_command(self):
        ip_addr = self.FTP_DATA_HOST.replace('.', ',')
        first_port = str(self.FTP_DATA_PORT // 256)
        second_port = str(self.FTP_DATA_PORT % 256)
        self.PORT_command = b'PORT ' + ip_addr.encode() + b',' + first_port.encode() + b',' + second_port.encode()
        await self.loop.sock_sendall(self.control_sock, self.PORT_command)

    async def get_port_command_info(self):
        self.port_command_info = await self.loop.sock_recv(self.control_sock, 10000)
        print(self.port_command_info.decode())

    async def create_data_connection(self):
        self.FTP_DATA_PORT = random.randint(1025, 65535)
        self.FTP_DATA_HOST = '192.168.0.108'  # This is example ip. You have to type the ip address of your computer where client is running.
        self.data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.data_sock.bind((self.FTP_DATA_HOST, self.FTP_DATA_PORT))
        self.data_sock.listen(1)
        self.data_sock.setblocking(False) 
        await self.create_port_command()
        await self.get_port_command_info()
        self.data_conn, self.data_addr = await self.loop.sock_accept(self.data_sock)
        if self.command == 'ls':
            await self.recv_data_through_data_conn()

    async def recv_data_through_data_conn(self):
        self.received_secret_data = await self.loop.sock_recv(self.data_conn, 10000)
        print(self.received_secret_data.decode())
        self.data_conn.close()

    def change_send_mode(self):
        try:
            self.arg = self.data_to_send.split(' ')[1]
            if self.arg == 'ascii':
                self.send_mode = self.arg
            elif self.arg == 'binary':
                self.send_mode = self.arg
        except IndexError:
            pass # If client types other mode than ascii or binary then the server will send error msg.

    def change_local_dir(self):
        try:
            self.arg = self.data_to_send.split(' ')[1]
            if os.path.isdir(self.arg):
                if self.arg[0] == '/':
                    self.current_dir = os.path.abspath(self.arg)
                    os.chdir(self.current_dir)
                    print('Local directory now ' + self.current_dir)
                else:
                    self.current_dir = os.path.abspath(os.path.join(self.current_dir, self.arg))
                    print('Local directory now ' + self.current_dir)
            elif not os.path.isdir(self.arg):
                print('local: ' + self.arg + ': No such file or directory')
        except IndexError:
            print('Local directory now ' + self.current_dir)

    async def upload_file(self):
        await self.create_data_connection()
        try:
            filename = self.data_to_send.split(' ')[1]
            if os.path.isfile(filename):
                if self.send_mode == 'ascii':	
                    file_to_send = open(filename, 'r')
                    try:
                        file_content = file_to_send.read()
                        await self.loop.sock_sendall(self.data_sock, file_content.encode())
                    except UnicodeError:
                        error_msg = 'local: Using ascii mode to upload binary file.'
                        print(error_msg)
                else:
                    file_to_send = open(filename, 'rb')
                    file_content = file_to_send.read()
                    await self.loop.sock_sendall(self.data_conn, file_content)
                self.data_conn.close()
            elif not os.path.isfile(filename):
                print('local: 550 ' + filename + ': No such file or directory.')
                self.data_conn.close()
        except IndexError:
            self.data_conn.close()

    async def recv_file(self, new_local_file):
        while True:
            file_content = await self.loop.sock_recv(self.data_conn, 10000)
			
            if not file_content:
                break
			
            if self.send_mode == 'ascii':
                new_local_file.write(file_content.decode())
            else:
                new_local_file.write(file_content)

    def download_file_error_handler(self, exception, path):
        handler = {
                      'PermissionError': 'local: ' + path + ': Permission denied',
                      'IsADirectoryError': 'local: ' + path + 'Is a directory',
                      'FileNotFoundError': 'local: 550 ' + path + ': No such file or directory'
                  }

        return handler.get(exception)

    async def download_file(self):
        await self.create_data_connection()
        try:
            path = self.data_to_send.split(' ')[1]
            try:
                path = self.data_to_send.split(' ')[2]
            except IndexError:
                pass # When client doesn't type second arg then the path to save the downloaded file is in the first arg.
            if self.send_mode == 'ascii':
                try:
                    new_text_file = open(path, 'w')
                    await self.recv_file(new_text_file)
                except Exception as e:
                    error_msg = self.download_file_error_handler(type(e).__name__, path)
                    print(error_msg)
            elif self.send_mode == 'binary':
                try:
                    new_binary_file = open(path, 'wb')
                    await self.recv_file(new_binary_file)
                except Exception as e:
                    error_msg = self.download_file_error_handler(type(e).__name__, path)
                    print(error_msg)
            self.data_conn.close()
        except IndexError:
            self.data_conn.close()

    async def USER(self):
        try:
            self.username = self.data_to_send.split(' ')[1]
            if self.username == 'anonymous':
                self.logged_in = True
        except IndexError:
            self.username = ''

    async def recieve_data(self):
        while True:
            self.data_to_send = input('ftp> ')
            self.command = self.data_to_send.split(' ')[0]
            if self.data_to_send == '':
                continue
            await self.loop.sock_sendall(self.control_sock, self.data_to_send.encode())
            try:
                if self.logged_in:
                    await self.commands_to_handle.get(self.command)()
                else:
                    await self.permitted_commands.get(self.command)()
            except TypeError:
                pass # When TypeError raises it means that client doesn't have to handle this command.
            try:
                if self.command == 'help':
                    continue
                else:
                    self.received_data = await self.loop.sock_recv(self.control_sock, 10000)
                    print(self.received_data.decode())
            except OSError:
                sys.exit()
            if not self.received_data:
                break
        print('Connection closed by the server')
        self.control_sock.close()

    async def get_and_print_exit_msg(self):
        exit_msg = await self.loop.sock_recv(self.control_sock, 10000)
        print(exit_msg.decode())

    async def exit_handler(self):
        await self.get_and_print_exit_msg()
        self.loop.stop()
        self.control_sock.close()

    def help_command_handler(self, arg):
        all_permitted_commands = {
                                     'append': '\t\t send one file',
                                     'pwd': '\t\t print working directory on remote machine',
                                     'ascii': '\t\t set ascii transfer type',
                                     'quit': '\t\t terminate ftp session and exit',
                                     'binary': '\t\t set binary transfer type',
                                     'recv': '\t\t receive file',
                                     'bye': '\t\t terminate ftp session and exit',
                                     'rename': '\t\t rename file',
                                     'cd': '\t\t change remote working directory',
                                     'rmdir': '\t\t remove directory on the remote machine',
                                     'cdup': '\t\t change remote working directory to parent directory',
                                     'size': '\t\t show size of remote file',
                                     'delete': '\t\t delete remote file',
                                     'type': '\t\t set file transfer type',
                                     'dir': '\t\t list contents of remote directory',
                                     'user': '\t\t send new user information',
                                     'exit': '\t\t terminate ftp session and exit',
                                     '?': '\t\t print local help information',
                                     'get': '\t\t receive file',
                                     'help': '\t\t print local help information',
                                     'lcd': '\t\t change local working directory',
                                     'ls': '\t\t list contents of remote directory',
                                     'mkdir': '\t\t make directory on the remote machine',
                                     'mode': '\t\t set file transfer mode',
                                     'put': '\t\t send one file'
                                 }
        return arg + all_permitted_commands.get(arg)
 
    def help(self):
        try:
            arg = self.data_to_send.split(' ')[1]
            help_msg = self.help_command_handler(arg)
            print(help_msg)
        except IndexError:
            print('Some commands may be abbrivated. Commands are:\n')
            print('append\t\tpwd\nascii\t\tquit\nbinary\t\trecv\nbye\t\trename\ncd\t\trmdir\ncdup\t\tsize')
            print('delete\t\ttype\ndir\t\tuser\nexit\t\t?\nget\t\thelp\nlcd\t\tls\nmkdir\t\tmode\nput')


if __name__ == '__main__':
	loop = asyncio.get_event_loop()
	FTP_connection = FtpConnection(loop)
	task = loop.create_task(FTP_connection.connect())
	loop.run_forever()
