#!/usr/bin/python3

import socket
import asyncio
import os
from os import path
import shutil
import sys


class ftpEchoServer:
    def __init__(self, loop):
        self.loop = loop
        self.HOST = ''
        self.CONTROL_PORT = 25000
        self.control_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.control_sock.bind((self.HOST, self.CONTROL_PORT))
        self.control_sock.listen(1)
        self.control_sock.setblocking(False)
        self.server_ip = socket.gethostbyname(socket.gethostname())
        self.loop.create_task(self.wait_for_connections())
		
    async def wait_for_connections(self):
        while True:
            self.control_conn, self.control_addr = await self.loop.sock_accept(self.control_sock)
            FTP_auth_handler = ftpAuthenticationHandler(self.control_conn, self.loop, self.control_sock, self.server_ip)


class ftpAuthenticationHandler:
    def __init__(self, control_conn, loop, control_sock, ip_addr):
        self.ip_addr = ip_addr
        self.loop = loop
        self.control_sock = control_sock
        self.control_conn = control_conn
        self.logged_in = False
        self.username = ''
        self.permitted_commands = { 
                                      "user": self.user,
                                      "exit": self.exit_before_auth 
                                  }
        self.loop.create_task(self.connected_successful_msg())
		
    async def connected_successful_msg(self):
        successful_msg = b'Connected to the FTP server [' +  self.ip_addr.encode() + b']\n'
        await self.loop.sock_sendall(self.control_conn, successful_msg)
        await self.main_auth_handler()

    async def login_successful(self):
        self.logged_in = True
        self.welcome_msg = b'230-\n'\
                           b'230- -------------------------------------------------------------------------\n'\
	                   b'230- WELCOME!	This server is created by Kamil Szpakowski. You are logged in\n'\
                           b'230-            as anonymous.\n'\
                           b'230- -------------------------------------------------------------------------\n'\
                           b'Remote system type is UNIX.'
        await self.loop.sock_sendall(self.control_conn, self.welcome_msg)
	
    async def main_auth_handler(self):
        self.username = await self.loop.sock_recv(self.control_conn, 10000)
        self.username = self.username.decode()
        await self.loop.sock_sendall(self.control_conn, b'331 Password required for USER.')
        if self.username == 'anonymous':
            await self.login_successful()
            FTP_commands_handler = FtpCommandsHandler(self.control_conn, self.loop, self.username)
            await FTP_commands_handler.execute_command()
        else:
            await self.loop.sock_sendall(self.control_conn, b'530 Please Login with USER and PASS.\nLogin failed.')
            await self.command_auths_handler()
	
    async def command_auths_handler(self):
       while True:
           self.data_from_client = await self.loop.sock_recv(self.control_conn, 10000)
           self.command = self.data_from_client.decode().split(' ')[0]
           if not self.data_from_client:
               break
           try:
               await self.permitted_commands.get(self.command)()
               if self.username == 'anonymous':
                   await self.login_successful()
                   FTP_commands_handler = FtpCommandsHandler(self.control_conn, self.loop, self.username)
                   await FTP_commands_handler.execute_command()
                   break
           except TypeError:
               self.login_failed_msg = b'530 Please Login with USER and PASS.'
               await self.loop.sock_sendall(self.control_conn, self.login_failed_msg)
			
    async def user(self):
        try:
            self.username = self.data_from_client.decode().split(' ')[1]
            if self.username != 'anonymous':
                await self.loop.sock_sendall(self.control_conn, self.login_failed_msg)
        except IndexError:
             await self.loop.sock_sendall(self.control_conn, b'usage: user <username>')

    async def exit_before_auth(self):
        await self.loop.sock_sendall(self.control_conn, b'221 Goodbye.')


class FtpCommandsHandler:
    def __init__(self, control_conn, loop, username):
        self.control_conn = control_conn
        self.loop = loop
        self.send_mode = 'ascii'
        self.username = username
        self.home_dir = '/'
        os.chdir(self.home_dir)
        self.current_path = self.home_dir
        self.cwd = self.home_dir
        self.ftp_commands = {
                                'ascii': self.ascii_mode,
                                'binary': self.binary_mode,
                                'type': self.change_send_mode,
                                'user': self.change_user,
                                'pwd': self.pwd,
                                'cd': self.change_working_dir,
                                'cwd': self.change_working_dir,
                                'cdup': self.cdup,
                                'mode': self.mode,
                                'mkdir': self.make_dir,
                                'mkd': self.make_dir,
                                'delete': self.delete_file,
                                'dele': self.delete_file,
                                'rmdir': self.remove_dir,
                                'ls': self.list_dir,
                                'dir': self.list_dir,
                                'size': self.get_size,
                                'get': self.send_file_to_local,
                                'recv': self.send_file_to_local,
                                'append': self.recv_file,
                                'put': self.recv_file,
                                'lcd': self.lcd,
                                'exit': self.exit,
                                'bye': self.exit
                            }

    async def execute_command(self):
        while True:
            self.command_with_args = await self.loop.sock_recv(self.control_conn, 10000)
            self.command = self.command_with_args.decode().split(' ')[0]
            try:
                self.arg = self.command_with_args.decode().split(' ')[1]
            except IndexError:
                self.arg = ''
            try:
                await self.ftp_commands.get(self.command)()
            except TypeError:
                if self.command != 'help':
                    await self.loop.sock_sendall(self.control_conn, b'?Invalid command')
            if not self.command:
                break
        self.control_conn.close()

    async def ascii_mode(self):
        self.send_mode = 'ascii'
        await self.loop.sock_sendall(self.control_conn, b'200 TYPE set to A.')

    async def binary_mode(self):
        self.send_mode = 'binary'
        await self.loop.sock_sendall(self.control_conn, b'200 TYPE set to I.')

    async def recv_port_command(self):
        self.port_command = await self.loop.sock_recv(self.control_conn, 10000)
        self.FTP_DATA_HOST = '.'.join(self.port_command.decode().split(' ')[1].split(',')[:-2])
        print(self.FTP_DATA_HOST)
        first_port = int(self.port_command.decode().split(' ')[1].split(',')[-2])
        second_port = int(self.port_command.decode().split(' ')[1].split(',')[-1])
        self.FTP_DATA_PORT = first_port * 256 + second_port
        await self.loop.sock_sendall(self.control_conn, b'200 PORT command successful.\n150 Opening data connection')

    async def create_data_connection(self):
        await self.recv_port_command()
        self.data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(self.FTP_DATA_HOST)
        print(self.FTP_DATA_PORT)
        await self.loop.sock_connect(self.data_sock, (self.FTP_DATA_HOST, self.FTP_DATA_PORT))
					
    def get_file_permission(self, path_to_list):
        file_permission = oct(os.stat(path_to_list).st_mode)[-3:]

        possible_perms = { 
                             '0': '---',
                             '1': '--x',
                             '2': '-w-',
                             '3': '-wx',
                             '4': 'r--',
                             '5': 'r-x',
                             '6': 'rw-',
                             '7': 'rwx'
                         }

        return ''.join(possible_perms.get(digit) for digit in file_permission)

    async def items_to_list(self, files, path):
        data_to_send = []
        for f in files:
             path_to_list = os.path.join(path, f)
             file_permission = self.get_file_permission(path_to_list)
             number_of_hard_links = os.stat(path_to_list).st_nlink
             size = os.stat(path_to_list).st_size
             m_time = time.strftime("%b %d %H:%M", time.gmtime(os.stat(path_to_list).st_mtime))
             if os.path.isdir(path_to_list):
                 data_to_send.extend(('d'+file_permission, str(number_of_hard_links), str(size), m_time, f, '\r\n'))
             else:
                 data_to_send.extend((file_permission, str(number_of_hard_links), str(size), m_time, f, '\r\n'))

        await self.loop.sock_sendall(self.data_sock, '\t'.join(data_to_send).encode())
        await self.loop.sock_sendall(self.control_conn, b'226 Transfer complete')
        self.data_sock.close()

    async def list_dir(self):
        await self.create_data_connection()
        if os.path.exists(self.arg):
            path_to_list = os.path.join(self.arg)
            files = os.listdir(path_to_list)
            await self.items_to_list(files, path_to_list)
        else:
            if not self.arg:
                path_to_list = os.path.join(self.cwd)
                files = os.listdir(path_to_list)
                await self.items_to_list(files, path_to_list)
            else:
                await self.loop.sock_sendall(self.control_conn, b'550 ' + self.arg.encode() + b': No such file or directory.')

    async def save_file_content(self, new_server_file):
        while True:
            file_content = await self.loop.sock_recv(self.data_sock, 10000)
			
            if not file_content:
                break

            if self.send_mode == 'ascii':
                new_server_file.write(file_content.decode())
            else:
                new_server_file.write(file_content)

    def recv_file_error_handler(self, exception, path):
        handler = {
		              'IsADirectoryError': b'remote: ' + path.encode() + b': Is a directory.\n',
                      'PermissionError': b'remote: ' + path.encode() + b': Permission denied.\n',
                      'FileNotFoundError': b'remote: 550 ' + path.encode() + b': No such file or directory.\n'
                  }
		
        return handler.get(exception)
				 
    async def recv_file(self):
        await self.create_data_connection()
        if self.arg:
            path = self.arg
            try:
                path = self.command_with_args.decode().split(' ')[2]
            except IndexError:
                pass
            if self.send_mode == 'ascii':
                try:
                    new_server_file = open(path, 'w')
                    await self.save_file_content(new_server_file)
                except Exception as e:
                    error_msg = self.recv_file_error_handler(type(e).__name__, path)
                    await self.loop.sock_sendall(self.control_conn, error_msg)
            else:
               try:
                   new_server_file = open(path, 'wb')
                   await self.save_file_content(new_server_file)
               except Exception as e:
                   error_msg = self.recv_file_error_handler(type(e).__name__, path)
                   await self.loop.sock_sendall(self.control_conn, error_msg)
            await self.loop.sock_sendall(self.control_conn, b'226 Transfer complete.')
            self.data_sock.close()
        else:
            await self.loop.sock_sendall(self.control_conn, b'usage: append <filename>\n226 Transfer complete.')
            self.data_sock.close()

    async def send_text_file(self, path_to_file):
        text_file_to_send = open(path_to_file, 'r')
        try:
            text_file_content = text_file_to_send.read()
            await self.loop.sock_sendall(self.data_sock, text_file_content.encode())
        except UnicodeDecodeError:
            self.data_sock.close()
            type_error_msg = b'551 type error: Sending binary file when type is A.\n'
            await self.loop.sock_sendall(self.control_conn, type_error_msg)

    async def send_binary_file(self, path_to_file):
        binary_file_to_send = open(path_to_file, 'rb')
        binary_file_content = binary_file_to_send.read()
        await self.loop.sock_sendall(self.data_sock, binary_file_content)

    async def send_file_to_local(self):
        await self.create_data_connection()
        if not self.arg:
            await self.loop.sock_sendall(self.control_conn, b'usage: get <filename>\n226 Transfer complete')
            self.data_sock.close()
        elif os.path.isfile(self.arg):
            path_to_file = os.path.join(self.arg)
            if self.send_mode == 'ascii':
                await self.send_text_file(path_to_file)
            else:
                await self.send_binary_file(path_to_file)
            await self.loop.sock_sendall(self.control_conn, b'226 Transfer complete')
            self.data_sock.close()
        elif not os.path.isfile(self.arg):
            await self.loop.sock_sendall(self.control_conn, b'remote: 550 '+self.arg.encode()+b': No such file or directory.\n')
            await self.loop.sock_sendall(self.control_conn, b'226 Transfer complete.')
            self.data_sock.close()

    async def get_size(self):
        if not self.arg:
            await self.loop.sock_sendall(self.control_conn, b'usage: size <filename>')
        elif os.path.exists(self.arg):
            path_to_get_size = os.path.join(self.arg)
            if os.path.isfile(path_to_get_size):
                file_size = os.stat(path_to_get_size).st_size
                await self.loop.sock_sendall(self.control_conn, b'213 ' + str(file_size).encode())
            else:
                await self.loop.sock_sendall(self.control_conn, b'550 ' + path_to_get_size.encode() + b': not a regular file.')
        elif not os.path.exists(self.arg):
            await self.loop.sock_sendall(self.control_conn, b'550 ' + self.arg.encode() + b': No such file or directory.')

    async def delete_file(self):
        if not self.arg:
            await self.loop.sock_sendall(self.control_conn, b'usage: delete or dele <filename>')
        else:
            if os.path.isfile(self.arg):
                try:
                    os.remove(self.arg)
                    await self.loop.sock_sendall(self.control_conn, b'250 ' + self.command.encode() + b' command successful.')
                except PermissionError:
                    await self.loop.sock_sendall(self.control_conn, b'550 ' + self.arg.encode() + b': Permission denied')
            else:
                await self.loop.sock_sendall(self.control_conn, b'550 ' + self.arg.encode() + b': No such file or directory.')	

    async def remove_dir(self):
        if not self.arg:
            await self.loop.sock_sendall(self.control_conn, b'usage: rmdir <dirname>')
        else:
            if os.path.isdir(self.arg):
                try:
                    shutil.rmtree(self.arg)
                    await self.loop.sock_sendall(self.control_conn, b'250 ' + self.command.encode() + b' command successful.')
                except PermissionError:
                    await self.loop.sock_sendall(self.control_conn, b'550 ' + self.arg.encode() + b': Permission denied')
            else:
                await self.loop.sock_sendall(self.control_conn, b'550 ' + self.arg.encode() + b': No such file or directory.')

    async def make_dir(self):
        if not self.arg:
             await self.loop.sock_sendall(self.control_conn, b'usage: mkdir or mkd <dir>')
        else:
            if not os.path.exists(self.arg):
                try:
                    os.makedirs(self.arg)
                    await self.loop.sock_sendall(self.control_conn, b'257 MKD command successful.')
                except PermissionError:
                    await self.loop.sock_sendall(self.control_conn, b'550 ' + self.arg.encode() + b': Permission denied')
            else:
                await self.loop.sock_sendall(self.control_conn, b'550 ' + self.arg.encode() + b': Directory already exists.')

    async def mode(self):
        await self.loop.sock_sendall(self.control_conn, b'We only support stream mode, sorry.')

    async def cdup(self):
        if not os.path.samefile(self.current_path, '/'):
            self.cwd = self.current_path = os.path.abspath(os.path.join(self.current_path, '..'))
            await self.loop.sock_sendall(self.control_conn, b'250 CDUP command successful.')
        else:
            await self.loop.sock_sendall(self.control_conn, b'451 ' + self.current_path.encode() + b': Invalid argument')

    async def change_working_dir(self):
        if self.arg and os.path.isdir(os.path.join(self.current_path, self.arg)):
            new_dir = self.arg
            if self.arg[0] == '/':
                self.cwd = self.current_path = os.path.abspath(new_dir)
                os.chdir(self.cwd)
                await self.loop.sock_sendall(self.control_conn, b'250 CWD command successful.')
            elif self.arg[0] != '/':
                self.cwd = self.current_path = os.path.abspath(os.path.join(self.current_path, new_dir))
                os.chdir(self.cwd)
                await self.loop.sock_sendall(self.control_conn, b'250 CWD command successful.')
            else:
                await self.loop.sock_sendall(self.control_conn, b'250 CWD command successful.')
        elif self.arg and not os.path.isdir(self.arg):
            await self.loop.sock_sendall(self.control_conn, b'550 ' + self.arg.encode() + b': No such file or directory.')
        elif not self.arg:
            self.cwd = '/'
            await self.loop.sock_sendall(self.control_conn, b'250 CWD command successful.')

    async def pwd(self):
        if self.arg:
            await self.loop.sock_sendall(self.control_conn, b'usage: pwd')
        else:
            await self.loop.sock_sendall(self.control_conn, b'257 \"' + self.cwd.encode() + b'\" is you working directory.')

    async def change_send_mode(self):
        if self.arg:
            if self.arg == 'ascii':
                self.send_mode = self.arg
                await self.loop.sock_sendall(self.control_conn, b'200 TYPE set to A.')
            elif self.arg == 'binary':
                self.send_mode = self.arg
                await self.loop.sock_sendall(self.control_conn, b'200 TYPE set to I.')
            else:
                await self.loop.sock_sendall(self.control_conn, self.arg.encode() + b': ' + b'unknown mode')
        else:
            await self.loop.sock_sendall(self.control_conn, b'Using ' + self.send_mode.encode() + b' for transfer files.')

    async def lcd(self):
        await self.loop.sock_sendall(self.control_conn, b'200 Command okay.')

    async def change_user(self):
        if not self.arg:
            await self.loop.sock_sendall(self.control_conn, b'usage: user <username>')
        elif self.username == 'anonymous':
            await self.loop.sock_sendall(self.control_conn, b'503 You are already logged in!\nLogin failed.')

    async def exit(self):
        await self.loop.sock_sendall(self.control_conn, b'221 Goodbye.')

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    FTP_echo = ftpEchoServer(loop)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.close()
