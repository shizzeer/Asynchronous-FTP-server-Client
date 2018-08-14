# Asynchronous-FTP-server-Client

This is my implementation of the FTP protocol. In this project I decided to implement FTP service and FTP client which will be connected to the service. The whole communication between them is based on the low-level TCP sockets. 

## Concurrency problem

But what if a lot of clients will be connected to the server at the same time? One of the solution is to create one thread for one client. Fine, but what if we will have thousands of clients? Then we will have thousands of threads too and this is not a good idea when we want to optimize our program. So I decided to use asyncio library and implement asynchronous FTP server + client. Everything will be on the single thread even if we will have to handle thousands of connects.

## Authorization to the server

Only one account will allow you to connect to the server. This account is anonymous.
![login_into_server](https://user-images.githubusercontent.com/32940567/44101002-a68f441a-9fe6-11e8-8ad2-09718f1dd6f6.png)
![login_into_server2](https://user-images.githubusercontent.com/32940567/44101247-45e4afd2-9fe7-11e8-9d86-bfa3cdec6e51.png)
