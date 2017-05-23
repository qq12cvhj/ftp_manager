#coding=utf-8
#!/usr/bin/env python3
global flag
import socket, sys, os, threading, time, configparser, re
#下面两个是关闭额外开启的一个线程使用的第三方工具代码  _async_raise()和stop_thread()
import  ctypes,inspect
def _async_raise(tid, exctype):
    """raises the exception, performs cleanup if needed"""
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")

    elif res != 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")



def stop_thread(thread):
    _async_raise(thread.ident, SystemExit)


def log(message, clientAddr=None):
    ''' Write log '''
    if clientAddr == None:
        print('\033[92m[%s]\033[0m %s' % (time.strftime(r'%H:%M:%S, %m.%d.%Y'), message))
    else:
        print('\033[92m[%s] %s:%d\033[0m %s' % (
        time.strftime(r'%H:%M:%S, %m.%d.%Y'), clientAddr[0], clientAddr[1], message))


class DataSockListener(threading.Thread):
    ''' Asynchronously accepts data connections '''

    def __init__(self, server):
        super().__init__()
        self.daemon = True  # Daemon
        self.server = server
        self.listenSock = server.dataListenSock

    def run(self):
        self.listenSock.settimeout(1.0)  # Check for every 1 second
        while True:
            try:
                (dataSock, clientAddr) = self.listenSock.accept()
            except (socket.timeout):
                pass
            except (socket.error):  # Stop when socket closes
                break
            else:
                if self.server.dataSock != None:  # Existing data connection not closed, cannot accept
                    dataSock.close()
                    log('Data connection refused from %s:%d.' % (clientAddr[0], clientAddr[1]), self.server.clientAddr)
                else:
                    self.server.dataSock = dataSock
                    log('Data connection accpted from %s:%d.' % (clientAddr[0], clientAddr[1]), self.server.clientAddr)


class FTPServer(threading.Thread):
    ''' FTP server handler '''

    def __init__(self, controlSock, clientAddr):
        super().__init__()
        self.daemon = True  # Daemon
        self.bufSize = 1024
        self.controlSock = controlSock
        self.clientAddr = clientAddr
        self.dataListenSock = None
        self.dataSock = None
        self.dataAddr = '127.0.0.1'
        self.dataPort = None
        self.username = ''
        self.authenticated = False
        self.cwd = os.getcwd()
        self.typeMode = 'Binary'
        self.dataMode = 'PORT'

    def run(self):
        self.controlSock.send(b'220 Service ready for new user.\r\n')
        global send_len
        send_len += len(b'220 Service ready for new user.\r\n')
        while True:
            cmd = self.controlSock.recv(self.bufSize).decode('ascii')
            global recv_len
            recv_len += len(cmd)
            if cmd == '':  # Connection closed
                self.controlSock.close()
                log('Client disconnected.', self.clientAddr)
                break
            log('[' + (self.username if self.authenticated else '') + '] ' + cmd.strip(), self.clientAddr)
            cmdHead = cmd.split()[0].upper()
            if cmdHead == 'QUIT':  # QUIT
                self.controlSock.send(b'221 Service closing control connection. Logged out if appropriate.\r\b')
                send_len += len(b'221 Service closing control connection. Logged out if appropriate.\r\b')
                self.controlSock.close()
                log('Client disconnected.', self.clientAddr)
                break
            elif cmdHead == 'HELP':  # HELP
                self.controlSock.send(b'214 QUIT HELP USER PASS PWD CWD TYPE PASV NLST RETR STOR\r\n')
                send_len += len(b'214 QUIT HELP USER PASS PWD CWD TYPE PASV NLST RETR STOR\r\n')
            elif cmdHead == 'USER':  # USER
                if len(cmd.split()) < 2:
                    self.controlSock.send(b'501 Syntax error in parameters or arguments.\r\n')
                    send_len += len(b'501 Syntax error in parameters or arguments.\r\n')
                else:
                    self.username = cmd.split()[1]
                    self.controlSock.send(b'331 User name okay, need password.\r\n')
                    send_len += len(b'331 User name okay, need password.\r\n')
                    self.authenticated = False
            elif cmdHead == 'PASS':  # PASS
                if self.username == '':
                    self.controlSock.send(b'503 Bad sequence of commands.\r\n')
                    send_len += len(b'503 Bad sequence of commands.\r\n')
                else:
                    if len(cmd.split()) < 2:
                        self.controlSock.send(b'501 Syntax error in parameters or arguments.\r\n')
                        send_len += len(b'501 Syntax error in parameters or arguments.\r\n')
                    else:
                        self.controlSock.send(b'230 User logged in, proceed.\r\n')
                        send_len += len(b'230 User logged in, proceed.\r\n')
                        self.authenticated = True
            elif cmdHead == 'PWD':  # PWD
                if not self.authenticated:
                    self.controlSock.send(b'530 Not logged in.\r\n')
                    send_len += len(b'530 Not logged in.\r\n')
                else:
                    self.controlSock.send(('257 "%s" is the current directory.\r\n' % self.cwd).encode('ascii'))
                    send_len += len(('257 "%s" is the current directory.\r\n' % self.cwd).encode('ascii'))
            elif cmdHead == 'CWD':  # CWD
                if not self.authenticated:
                    self.controlSock.send(b'530 Not logged in.\r\n')
                    send_len += len(b'530 Not logged in.\r\n')
                elif len(cmd.split()) < 2:
                    self.controlSock.send(('250 "%s" is the current directory.\r\n' % self.cwd).encode('ascii'))
                    send_len += len(('250 "%s" is the current directory.\r\n' % self.cwd).encode('ascii'))
                else:
                    programDir = os.getcwd()
                    os.chdir(self.cwd)
                    newDir = cmd.split()[1]
                    try:
                        os.chdir(newDir)
                    except (OSError):
                        self.controlSock.send(
                            b'550 Requested action not taken. File unavailable (e.g., file busy).\r\n')
                        send_len += len(b'550 Requested action not taken. File unavailable (e.g., file busy).\r\n')
                    else:
                        self.cwd = os.getcwd()
                        self.controlSock.send(('250 "%s" is the current directory.\r\n' % self.cwd).encode('ascii'))
                        send_len += len(('250 "%s" is the current directory.\r\n' % self.cwd).encode('ascii'))
                    os.chdir(programDir)
            elif cmdHead == 'TYPE':  # TYPE, currently only I is supported
                if not self.authenticated:
                    self.controlSock.send(b'530 Not logged in.\r\n')
                    send_len += len(b'530 Not logged in.\r\n')
                elif len(cmd.split()) < 2:
                    self.controlSock.send(b'501 Syntax error in parameters or arguments.\r\n')
                    send_len += len(b'501 Syntax error in parameters or arguments.\r\n')
                elif cmd.split()[1] == 'I':
                    self.typeMode = 'Binary'
                    self.controlSock.send(b'200 Type set to: Binary.\r\n')
                    send_len += len(b'200 Type set to: Binary.\r\n')
                else:
                    self.controlSock.send(b'504 Command not implemented for that parameter.\r\n')
                    send_len += len(b'504 Command not implemented for that parameter.\r\n')
            elif cmdHead == 'PASV':  # PASV, currently only support PASV
                if not self.authenticated:
                    self.controlSock.send(b'530 Not logged in.\r\n')
                    send_len += len(b'530 Not logged in.\r\n')
                else:
                    if self.dataListenSock != None:  # Close existing data connection listening socket
                        self.dataListenSock.close()
                    self.dataListenSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
                    self.dataListenSock.bind((self.dataAddr, 0))
                    self.dataPort = self.dataListenSock.getsockname()[1]
                    self.dataListenSock.listen(5)
                    self.dataMode = 'PASV'
                    DataSockListener(self).start()
                    time.sleep(0.5)  # Wait for connection to set up
                    self.controlSock.send(('227 Entering passive mode (%s,%s,%s,%s,%d,%d)\r\n' % (
                    self.dataAddr.split('.')[0], self.dataAddr.split('.')[1], self.dataAddr.split('.')[2],
                    self.dataAddr.split('.')[3], int(self.dataPort / 256), self.dataPort % 256)).encode('ascii'))

                    send_len += len(('227 Entering passive mode (%s,%s,%s,%s,%d,%d)\r\n' % (
                    self.dataAddr.split('.')[0], self.dataAddr.split('.')[1], self.dataAddr.split('.')[2],
                    self.dataAddr.split('.')[3], int(self.dataPort / 256), self.dataPort % 256)).encode('ascii'))

            elif cmdHead == 'NLST':  # NLST
                if not self.authenticated:
                    self.controlSock.send(b'530 Not logged in.\r\n')
                    send_len += len(b'530 Not logged in.\r\n')
                elif self.dataMode == 'PASV' and self.dataSock != None:  # Only PASV implemented
                    self.controlSock.send(b'125 Data connection already open. Transfer starting.\r\n')
                    send_len += len(b'125 Data connection already open. Transfer starting.\r\n')
                    directory = '\r\n'.join(os.listdir(self.cwd)) + '\r\n'
                    self.dataSock.send(directory.encode('ascii'))
                    send_len += len(directory.encode('ascii'))
                    self.dataSock.close()
                    self.dataSock = None
                    self.controlSock.send(
                        b'225 Closing data connection. Requested file action successful (for example, file transfer or file abort).\r\n')
                    send_len += len(
                        b'225 Closing data connection. Requested file action successful (for example, file transfer or file abort).\r\n')
                else:
                    self.controlSock.send(b"425 Can't open data connection.\r\n")
                    send_len += len(b"425 Can't open data connection.\r\n")
            elif cmdHead == 'RETR':
                if not self.authenticated:
                    self.controlSock.send(b'530 Not logged in.\r\n')
                    send_len += len(b'530 Not logged in.\r\n')
                elif len(cmd.split()) < 2:
                    self.controlSock.send(b'501 Syntax error in parameters or arguments.\r\n')
                    send_len += len(b'501 Syntax error in parameters or arguments.\r\n')
                elif self.dataMode == 'PASV' and self.dataSock != None:  # Only PASV implemented
                    programDir = os.getcwd()
                    os.chdir(self.cwd)
                    self.controlSock.send(b'125 Data connection already open; transfer starting.\r\n')
                    send_len += len(b'125 Data connection already open; transfer starting.\r\n')
                    fileName = cmd.split()[1]
                    try:
                        self.dataSock.send(open(fileName, 'rb').read())
                        send_len += len(open(fileName, 'rb').read())
                    except (IOError):
                        self.controlSock.send(
                            b'550 Requested action not taken. File unavailable (e.g., file busy).\r\n')
                        send_len += len(
                            b'550 Requested action not taken. File unavailable (e.g., file busy).\r\n')
                    self.dataSock.close()
                    self.dataSock = None
                    self.controlSock.send(
                        b'225 Closing data connection. Requested file action successful (for example, file transfer or file abort).\r\n')
                    send_len += len(
                        b'225 Closing data connection. Requested file action successful (for example, file transfer or file abort).\r\n')
                    os.chdir(programDir)
                else:
                    self.controlSock.send(b"425 Can't open data connection.\r\n")
                    send_len += len(b"425 Can't open data connection.\r\n")
            elif cmdHead == 'STOR':
                if not self.authenticated:
                    self.controlSock.send(b'530 Not logged in.\r\n')
                    send_len += len(b'530 Not logged in.\r\n')
                elif len(cmd.split()) < 2:
                    self.controlSock.send(b'501 Syntax error in parameters or arguments.\r\n')
                    send_len += len(b'501 Syntax error in parameters or arguments.\r\n')
                elif self.dataMode == 'PASV' and self.dataSock != None:  # Only PASV implemented
                    programDir = os.getcwd()
                    os.chdir(self.cwd)
                    self.controlSock.send(b'125 Data connection already open; transfer starting.\r\n')
                    send_len += len(b'125 Data connection already open; transfer starting.\r\n')
                    fileOut = open(cmd.split()[1], 'wb')
                    time.sleep(0.5)  # Wait for connection to set up
                    self.dataSock.setblocking(False)  # Set to non-blocking to detect connection close
                    while True:
                        try:
                            data = self.dataSock.recv(self.bufSize)
                            recv_len += len(data)
                            if data == b'':  # Connection closed
                                break
                            fileOut.write(data)
                        except (socket.error):  # Connection closed
                            break
                    fileOut.close()
                    self.dataSock.close()
                    self.dataSock = None
                    self.controlSock.send(
                        b'225 Closing data connection. Requested file action successful (for example, file transfer or file abort).\r\n')
                    send_len += len(
                        b'225 Closing data connection. Requested file action successful (for example, file transfer or file abort).\r\n')
                    os.chdir(programDir)
                else:
                    self.controlSock.send(b"425 Can't open data connection.\r\n")
                    send_len += len(b"425 Can't open data connection.\r\n")


class Menu():
    def __init__(self):
        self.menus = dict(cp['menus'])
        self.lisn = None
    def printMenu(self):
        print('请选择要进行的操作:')
        for key in self.menus:
            print(key+'.'+self.menus[key])
        self.selectFunc()

    def listen(self):
        while True:
            (controlSock, clientAddr) = listenSock.accept()
            addr = clientAddr[0]
            # print(cp.has_option('whiteIP', addr))
            # print(cp.has_option('blackIP', addr))
            if cp.has_option('whiteIP', addr):
                FTPServer(controlSock, clientAddr).start()
                log("Connection accepted.", clientAddr)

            else:
                log("Connection refused.", clientAddr)

                controlSock.send(b'403 Forbidden.')
                global send_len
                send_len = len(b'403 Forbidden.')
                controlSock.close()
    def selectFunc(self, option=''):
        if option == '':
            option = input()
            option = int(option)
        if option < 0 or option > 6:
            print('请输入正确的选项')
            self.printMenu()
        else:
            if option == 1:
                global flag
                if flag == True:
                    global  send_len
                    global  recv_len
                    send_len = 0
                    recv_len = 0
                    print("请注意,上次服务器运行期间流量已清零")
                    global listenSock
                    listenAddr = socket.gethostname()
                    listenPort = int(cp['basic']['listenport'])
                    listenSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
                    listenSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    listenSock.bind((listenAddr, listenPort))
                    listenSock.listen(int(cp['basic']['maxUser']))
                log('Server started.')
                self.lisn = threading.Thread(target = self.listen,name='listenThread')
                self.lisn.start()
                self.printMenu()
                self.selectFunc()

            elif option == 2:
                if self.lisn != None:
                    print("对不起，请先关闭服务器")
                    return
                listenSock.close()
                print('请输入端口号')
                listenPort = input()
                listenPort = int(listenPort)
                if listenPort < 10000 or listenPort > 20000:
                    print('请输入10000-20000范围的端口号')
                    print('--------------------------')
                    self.selectFunc(2)
                else:
                    cp.set('basic', 'listenPort', str(listenPort))
                    cp.write(open('server.conf', 'w',encoding='utf-8'))
                    cp.write(sys.stdout)
                    print('端口号设置成功')
                    self.printMenu()
                    self.selectFunc()
            elif option == 3:
                if self.lisn != None:
                    print("对不起，请先关闭服务器")
                    return

                listenSock.close()
                print('请输入最大连接数')
                maxUser = input()
                maxUser = int(maxUser)
                if maxUser < 0 or maxUser > 6:
                    print('请输入0-5的数字')
                    print('--------------------------')
                    self.selectFunc(3)
                else:
                    cp.set('basic', 'maxUser', str(maxUser))
                    cp.write(open('server.conf', 'w',encoding='utf-8'))
                    cp.write(sys.stdout)
                    self.printMenu()
                    self.selectFunc()
            elif option == 4:
                if self.lisn != None:
                    print("对不起，请先关闭服务器")
                    return
                listenSock.close()
                print('请输入IP地址')
                addr = input()
                pattern = "^((?:(2[0-4]\d)|(25[0-5])|([01]?\d\d?))\.){3}(?:(2[0-4]\d)|(255[0-5])|([01]?\d\d?))$"
                addr = re.search(pattern, addr, flags=0)
                if addr:
                    addr = addr.group()
                    if cp.has_option('whiteIP', addr):
                        print('该IP已经存在')
                        self.selectFunc(4)
                    else:
                        cp.set('whiteIP', addr, addr)
                        if cp.has_option('blackIP', addr):
                            cp.remove_option('blackIP', addr)
                        cp.write(open('server.conf', 'w',encoding='utf-8'))
                        cp.write(sys.stdout)
                        print('IP添加成功')
                        self.printMenu()
                        self.selectFunc()
                else:
                    print('请输入正确的IP地址')
                    self.selectFunc(4)
            elif option == 5:
                if self.lisn != None:
                    print("对不起，请先关闭服务器")
                    return
                listenSock.close()
                print('请输入要添加至黑名单的IP地址')
                addr = input()
                pattern = "^((?:(2[0-4]\d)|(25[0-5])|([01]?\d\d?))\.){3}(?:(2[0-4]\d)|(255[0-5])|([01]?\d\d?))$"
                addr = re.search(pattern, addr, flags=0)
                if addr:
                    addr = addr.group()
                    if cp.has_option('blackIP', addr):
                        print('该IP已经存在')
                        self.selectFunc(5)
                    else:
                        cp.set('blackIP', addr, addr)
                        if cp.has_option('blackIP', addr):
                            cp.remove_option('blackIP', addr)
                        cp.write(open('server.conf', 'w'))
                        cp.write(sys.stdout)
                        print('IP添加成功')
                        self.printMenu()
                        self.selectFunc()
                else:
                    print('请输入正确的IP地址')
                    self.selectFunc(5)
            elif option == 6:

                print('\n当前上传流量为:',send_len)
                print('当前下载流量为:',recv_len,'\n')
                self.printMenu()
                self.selectFunc()
            elif option == 0:
                if self.lisn == None:
                    log('服务器并未启动')
                    self.printMenu()
                    self.selectFunc()
                else:
                    flag = True
                    stop_thread(self.lisn)
                    listenSock.close()
                    self.lisn = None
                    print('服务器已停止')
                    self.printMenu()
                    self.selectFunc()

if __name__ == '__main__':
    global flag
    flag = False
    cp = configparser.ConfigParser()
    cp.sections()
    cp.read('server.conf',encoding='utf-8')
    #listenAddr = socket.gethostname()
    listenAddr = '127.0.0.1'
    listenPort = int(cp['basic']['listenport'])
    global listenSock
    listenSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    listenSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listenSock.bind((listenAddr, listenPort))
    listenSock.listen(int(cp['basic']['maxUser']))
    global send_len
    global recv_len
    send_len = 0 #发送数据量初始化
    recv_len = 0 #接收数据量初始化
    menu = Menu()
    menu.printMenu()
