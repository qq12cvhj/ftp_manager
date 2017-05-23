#coding=utf-8
import os,socket,re,time

class FTP_client():
    def __init__(self):
        self.controlSock = None
        self.connected = False
        self.bufSize = 1024
        self.ipAddress = socket.gethostbyname(socket.gethostname())
        self.dataMode = 'PORT'
    def connect(self,hostAddress,port):
        if self.controlSock != None:
            self.connected = False
            self.controlSock.close()
        self.controlSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.controlSock.connect((hostAddress, port))
        self.connected = True
        self.loggedIn = False



    def parseReply(self):
        if self.controlSock == None:
            return
        try:
            reply = self.controlSock.recv(self.bufSize).decode('ascii')
        except(socket.timeout):
            print("<<对不起，系统超时")
            return
        else:
            if len(reply) > 0:
                print('<< ' + reply.strip().replace('\n', '\n<< '))
                self.status=reply.strip().split()[0]
                return (int(reply[0]), reply)
            else:  #当得到的reply为空时，关闭连接
                self.connected = False
                self.controlSock.close()
                self.controlSock = None
    def userLogin(self):
        if not self.connected:
            return
        else:
            if self.loggedIn :
                self.loggedIn = False
                print("<<您已登录，已帮您退出")
            else:
                pass
            username = input("<<请输入用户名")
            self.controlSock.send(('USER %s\r\n' % username).encode('ascii'))
            if self.parseReply()[0] <= 3:
                password = input("")
                self.controlSock.send(('PASS %s\r\n' % password).encode('ascii'))
                if self.parseReply()[0] <= 3:
                    self.loggedIn = True
                    print("<<恭喜,登录成功\n")
    def pwd(self):
        if not self.connected or not self.loggedIn:
            print("<<对不起，您还没有登录")
            return
        self.controlSock.send(b'PWD\r\n')
        self.parseReply()

    def cwd(self): #更改当前用户的工作目录
        if not self.connected or not self.loggedIn:
            print("<<对不起，您还没有登录")
            return
        path_input = input("请输入您要切换到的工作目录")
        self.controlSock.send(('CWD %s\r\n' % path_input).encode('ascii'))
        self.parseReply()

    def type(self):
        if not self.connected or not self.loggedIn:
            print("<<对不起，您还没有登录")
            return
        else:
            t = input("<<请输入转换的传输格式。如'I'代表二进制传输\n")
            self.controlSock.send(('TYPE %s\r\n' % t).encode('ascii'))
            self.parseReply()

    def pasv(self):
        self.controlSock.send(b'PASV\r\n')
        reply = self.parseReply()
        if reply[0] <= 3:
            m = re.search(r'(\d+),(\d+),(\d+),(\d+),(\d+),(\d+)', reply[1])
            self.dataAddr = (m.group(1) + '.' + m.group(2) + '.' + m.group(3) + '.' + m.group(4),
                             int(m.group(5)) * 256 + int(m.group(6)))
            self.dataMode = 'PASV'
            print("<<成功切换到PASV模式")


    def nlst(self):
        if not self.connected or not self.loggedIn:
            print("<<对不起，您还没有登录")
            return
        if self.dataMode != 'PASV':
            print("<<对不起，请先切换到PASV模式")
            return
        dataSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        dataSock.connect(self.dataAddr)
        self.controlSock.send(b'NLST\r\n')
        time.sleep(0.5) # Wait for connection to set up
        dataSock.setblocking(False) # Set to non-blocking to detect connection close
        while True:
            try:
                data = dataSock.recv(self.bufSize)
                if len(data) == 0:
                    break
                print(data.decode('ascii').strip())
            except (socket.error):
                break
        dataSock.close()
        self.parseReply()


    def retr(self):
        if not self.connected or not self.loggedIn:
            print("<<对不起，您还未登录")
            return
        if self.dataMode != 'PASV': # Currently only PASV is supported
            print("<<对不起，请先切换到PASV模式")
            return
        filename = input("<<请输入文件名")
        dataSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        dataSock.connect(self.dataAddr)
        self.controlSock.send(('RETR %s\r\n' % filename).encode('ascii'))
        fileOut = open(filename, 'wb')
        time.sleep(0.5) # Wait for connection to set up
        dataSock.setblocking(False) # Set to non-blocking to detect connection close
        while True:
            try:
                data = dataSock.recv(self.bufSize)
                if len(data) == 0: # Connection close
                    break
                fileOut.write(data)
            except (socket.error): # Connection closed
                break
        fileOut.close()
        dataSock.close()
        self.parseReply()


    def showFileList_native(self):
        print('\r\n'.join(os.listdir(os.getcwd())))



    def stor(self):
        if not self.connected or not self.loggedIn:
            print("<<对不起，您还未登录")
            return
        if self.dataMode != 'PASV': # Currently only PASV is supported
            print("<<对不起，请先切换到PASV模式")
            return
        filename = input("<<请输入要上传的文件名")
        dataSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        dataSock.connect(self.dataAddr)
        self.controlSock.send(('STOR %s\r\n' % filename).encode('ascii'))
        dataSock.send(open(filename, 'rb').read())
        dataSock.close()
        self.parseReply()
    def help(self):
        if not self.connected or not self.loggedIn:
            print("对不起，您还没有登录")
            return
        self.controlSock.send(b'HELP\r\n')
        self.parseReply()

if __name__ == '__main__':
    c = FTP_client()
    c.controlSock = None
    while True:
        hostAddr = input("<<请输入要连接的主机的ip地址")
        port = int(input("<<请输入要连接的主机的端口号"))
        try:
            c.connect(hostAddress=hostAddr,port=port)
            c.parseReply()
            if c.status == '403':
                print("<<对不起，服务器拒绝了您的连接请求.")
                continue
            break
        except Exception as e:
            print(e)
            print("<<对不起，连接失败,请重新输入")

            continue
    while True:

        print("\n---------这是分割线---------")
        print("1.登录FTP服务器")
        print("2.显示当前的工作目录")
        print("3.切换工作目录")
        print("4.切换数据传输格式")
        print("5.切换到PASV模式")
        print("6.列出当前工作目录下的文件列表")
        print("7.获取文件")
        print("8.列出当前本地文件夹内文件列表")
        print("9.上传文件\t(请输入当前文件夹下文件或文件绝对路径)")
        print("10.退出程序")
        print("11.帮助")
        print("---------这是分割线---------\n")
        sel = input()
        if sel == "1":
            c.userLogin()
        elif sel == "2":
            c.pwd()
        elif sel == "3":
            c.cwd()
        elif sel == "4":
            c.type()
        elif sel == "5":
            c.pasv()
        elif sel == "6":
            c.nlst()
        elif sel == "7":
            c.retr()
        elif sel == "9":
            c.stor()
        elif sel == "8":
            c.showFileList_native()
        elif sel == "10":
            exit(0)
        elif sel == "11":
            c.help()
        else:
            continue




