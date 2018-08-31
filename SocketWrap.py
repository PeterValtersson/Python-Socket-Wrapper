from enum import Enum
import pickle
import json
import socket
import numpy as np

LONG_STR_LENGHT = 256
SHORT_STR = 1
LONG_STR = 2
INT = 3
ENUM = 4
NUMPY_ARRAY = 5
FILE = 6
PICKLE = 7
LIST = 8

class InvalidAddressOrPort(Exception)
	def __init__(self, address, port):
		super().__init__("Invalid address or port. Address: {}, Port: {}".format(address, port))

## A wrapper for sockets that automatically resolves what is going to be sent and received.
#
# This class simplifies the send and recv by automatically resolving the type of what is being sent/received.
# As well as handling the size to send and recieve.
class Socket():

	## Constructor
	#
	# @param socket The socket to wrap. If None will create a new
	# @param cleanupCallback Function to call if clean function is called.
	def __init__(self, socket = None, cleanupCallback = lambda:None):
		if socket is None:
			socket = socket(socket.AF_INET, socket.SOCK_STREAM)	
		self.socket = socket
		self.cleanupCallback = cleanupCallback
		try:
			import bluetooth as bt
			if type(self.socket) is bt.BluetoothSocket:
				self.recv_ = self._bluetoothRecv
		except:
			# No bluetooth library
			pass	
	## Overrides recv_ when using bluetooth
	#
	# Since bluetoothSocket does not have recv_into, this is used instead.
	# \see recv_
	def _bluetoothRecv(self, size):
		ret = bytearray(size)
		view = memoryview(ret)
		toRead = size
		while toRead:
			bytes = self.socket.recv(min(toRead, LONG_STR_LENGHT))
			if bytes == b'': raise LHMT_ConnectionLost(self)	
			nbytes = len(bytes)
			view[:nbytes] = bytes
			view = view[nbytes:]
			toRead -= nbytes
		return ret
	
	## Override for base socket
	def connect(self,*args):
		self.socket.connect(*args)
		
	## Override for base socket
	def close(self):
		self.socket.close()
	
	## Override for base socket
	def settimeout(self, *args):
		self.socket.settimeout(*args)
		
	## Override for base socket
	def Delete(self):
		self.listener()
		
	## Send a message. Will send size first followed by the message.
	#
	# Will first send a 32bit integer representing the size, followed immediatly by the message
	# \warning This is intended for internal purposes and should not be used from the outside
	# \exception LHMT_ConnectionLost Connection to socket lost.
	def send(self, msg):
		size = len(msg)
		sent = self.socket.sendall(size.to_bytes(4, 'big'))
		if sent == 0: raise LHMT_ConnectionLost(self)
	
		sent = self.socket.sendall(msg)
		if sent == 0: raise LHMT_ConnectionLost(self)
		return sent
	
	## Receive a message of the given size
	#
	# This method is used internally when receiving messages.
	# \warning This is intended for internal purposes and should not be used from the outside
	# Creates a bytearray and a view to that array, then fills the array using recv_into until the exact number of bytes has been received.
	# \warning Should 
	def recv_(self, size):
		bytes = bytearray(size)
		view = memoryview(bytes)
		toRead = size
		while toRead:
			nbytes = self.socket.recv_into(view, min(toRead, LONG_STR_LENGHT))
			if nbytes == 0: raise LHMT_ConnectionLost(self)	
			view = view[nbytes:]
			toRead -= nbytes
		return bytes
	
	## Receive a message. Will first get the size, followed by the message
	#
	# \warning This is intended for internal purposes and should not be used from the outside
	# \warning Must be matched with a send
	# This method will first wait for the size of the message. This is in the form of a 32bit integer.
	# The message is then received.
	def recv(self):
		size = int.from_bytes(self.recv_(4), 'big')
		return self.recv_(size)
		
	
	## Send the type of the object to the connection
	#
	# This function can also send payloads along with the type (This speeds up some of the communications).
	# The function will first try to dumps using json, this will fail in some cases, ex. when sending a dtype, on fail pickle dumps is used instead
	# \warning This is intended for internal purposes and should not be used from the outside
	# @param type The type of the object
	# @param data Additional data to send, can be the actual value of for example an int or the size of an array. This speeds up communication for small types, by removing the need to send multiple messages.
	def SendType(self, type, data = ()):
		try:
			toSend = json.dumps((type, data)).encode()
		except:
			toSend = pickle.dumps((type, data))
	
		self.send(toSend) 
		
	## Recieve the type of a message
	#
	# This is the first thing that is called when receiving anything from the connection
	# It will first type to using json.loads, if this fails it will revert to pickle.loads
	# \warning This is intended for internal purposes and should not be used from the outside
	def RecvType(self):
		recv = self.recv()
		try:
			return json.loads(recv.decode()) 		
		except:
			return pickle.loads(recv)
			
	## Send a string
	#
	# If the string is less than LONG_STR_LENGHT-100 the string is sent in the payload other wise the string is sent separately. This avoids dumping a long string, which can reduce performance.
	# \warning This is intended for internal purposes and should not be used from the outside
	def SendString(self, msg):	
		with Status_Debug("Sending string"):
			toSend = len(msg)
			printDebug("Length:", toSend)
			if toSend < LONG_STR_LENGHT:
				with Status_Debug("Sending short string"):	self.SendType(SHORT_STR, msg)
			else:
				with Status_Debug("Sending long string"):
					with Status_Debug("Sendning type"): self.SendType(LONG_STR)		
					with Status_Debug("Sending string..."):  self.send(msg.encode())
					
	## Send a numpy array
	#
	# First sends the type, shape and dtype
	# Then sends the array itself
	# \warning This is intended for internal purposes and should not be used from the outside	
	def SendNumpyArray(self, array):
		self.SendType(NUMPY_ARRAY, (array.shape, array.dtype))
		self.send(array.tobytes())
	
	## Recieve a numpy array
	#
	# \warning This is intended for internal purposes and should not be used from the outside	
	# This function constructs a numpy array and files the array with data from the connection
	# @param shape_dtype Tuple containing the shape and dtype (in that order).
	def RecvNumpyArray(self, shape_dtype ):
		shape, dtype = shape_dtype
		bytes = self.recv()
		array = np.frombuffer(bytes, dtype)
		array.shape = shape
		return array
		
	## Send a file
	#
	# First sends the type, size and name.
	# Then sends the file itself. 
	# \warning This is intended for internal purposes and should not be used from the outside	
	# @param file The file to send (assumed to be opened)
	# \warning Will not work with bluetooth, since pyBluez does not have sendfile
	def SendFile(self, file):
		with Status_Info("Sending file"):
			with Status_Debug("Sending type and size"):
				file.seek(0, 2)
				size = file.tell()
				self.SendType(FILE, (size, file.name)) 
				file.seek(0)			
			with Status_Debug("Sending the file"):
				sent = self.socket.sendfile(file, 0)	
				if sent == 0: raise LHMT_ConnectionLost(self)
	
	## Recieve a file
	#
	# \warning This is intended for internal purposes and should not be used from the outside	
	# @param size_name A tuple with the size and name (in that order) of the file
	# @param filename If None(default) the file will be created with the same name in the current working directory.
	def RecvFile(self, size_name, filename = None):
		with Status_Info("Recieving file"):
			print(size_name)
			with Status_Debug("Recieving the file"):
				if filename == None: filename = size_name[1]
				with open(filename, 'wb') as file:
					toRead = size_name[0]
					while toRead:
						bytes = self.socket.recv(min(toRead, LONG_STR_LENGHT))
						if bytes == b'': raise LHMT_ConnectionLost(self)	
						file.write(bytes)
						toRead -= len(bytes)
		return filename
	
	
	## This function will automatically resolve the type of the message and communicate this with the connection and send the message.
	#
	# All types that can be pickled using pickle are supported, however, pickle is slow, therefore a warning is printed each time something is sent using pickle.
	# \warning When sending files, they are assumed to already be opened using f = open(...)
	def Send(self, msg):
		if type(msg) == list or type(msg) == tuple:
			self.SendType(LIST, msg)
		elif isinstance(msg, str):
			self.SendString(msg)
		elif isinstance(msg, int):
			self.SendType(INT, msg)
		elif isinstance(msg, Enum):
			self.SendType(ENUM, msg.value)
		elif type(msg) is np.ndarray:
			self.SendNumpyArray(msg)
		elif type(msg).__name__ == 'BufferedReader':
			self.SendFile(msg)	
		else:
			printWarning("Sending with pickle") # This is slow!
			self.SendType(PICKLE)	
			bytes = pickle.dumps(msg, pickle.HIGHEST_PROTOCOL)
			self.send(bytes)
	
	## Recieve a message from the connection
	#
	# This will automatically resolve the type that has been received and act accordingly.
	# @param *args Any arguments to pass to the internal methods
	# @param **kwargs Any keyword arguments to pass to the internal methods
	def Recv(self, *args, **kwargs):
		type, msg = self.RecvType()
		if type == SHORT_STR:
			return msg
		elif type == LONG_STR:
			return  self.recv().decode()	
		elif type == INT:
			return msg
		elif type == ENUM:
			return LHMT_Commands(msg)
		elif type == NUMPY_ARRAY:
			return self.RecvNumpyArray(msg)
		elif type == LIST:
			return msg
		elif  type == FILE:
			return self.RecvFile(msg, *args, **kwargs)
		elif type == PICKLE:
			bytes = self.recv()
			ret = pickle.loads(bytes)
			return ret
			
	## Send a message and immediatly wait for a response
	# @see Send
	# @see Recv
	def SendRecv(self, msg):
		self.Send(msg)
		return self.Recv()
	
	## Recieve a msg and immediatly respond
	# @see Send
	# @see Recv
	def RecvSend(self, msg):
		ret = self.Recv()
		self.Send(msg)
		return ret


## Construct and connect a SocketHandler
def Connect(ip, port, callback = lambda: None):
	sock = SocketHandler(socket.socket(socket.AF_INET, socket.SOCK_STREAM),callback)
	sock.settimeout(2)
	sock.connect((ip, port))
	sock.settimeout(None)
	return sock
		
from threading import Lock
from threading import Thread

## This class fetches images from the server.
#
# This is done on a seperate thread.
class SocketVideoStream:
	def __init__(self,streamSocket):	
		self.socket = streamSocket
		
		self.lock = Lock()
		self.image = np.zeros(16).reshape(4,4).astype(np.uint8)
		self.running = False
		self.width = 0
		self.height = 0

	def start(self):
		if not self.running:
			self.running = True
			def Update():		
				try:
					while self.running:
						self.image = self.socket.SendRecv(LHMT_Commands.CAMERA_SEND_IMAGE)
				except LHMT_ConnectionLost as e:
					PrintException()
					self.stopped = True
					self.running = False
					with Status("Cleaning up"): e.socket.Delete()
					
				except:
					PrintException()
					self.stopped = True
					self.running = False
				self.stopped = True
			self.t = Thread(target=Update, args=())
			self.t.daemon = True
			self.t.start()
			
		return self	

	def read(self):
		return self.image.copy()
	def GetSize(self):
		return (self.width, self.height)
		
	def stop(self):
		if self.running:
			self.stopped = False
			self.running = False
			while not self.stopped:
				time.sleep(0.1)
	def Resize(self, width, height):
		if not (self.width == width and self.height == height):
			with Status("Telling server to resizing camera"):
				self.running = False
				self.t.join()
				self.width = width
				self.height = height
				self.socket.Send(LHMT_Commands.SET_RESOLUTION)
				self.socket.Send((width, height))
				self.start()
	def SetExposureTime(self, exptime):
		pass
		
	def SyncThread(*a):
		pass	

if __name__ == "__main__":
	class Data():
		def __init__(self):
			self.a = 1
			self.b = "Test"
			self.c = 2.3
	class Test():
		def __init__(self, bluetooth = False):
			if bluetooth:
				import bluetooth as bt
				listener = bt.BluetoothSocket(bt.RFCOMM)
				listener.bind(("00:1A:7D:DA:71:0D", 3))	
			else:
				listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				listener.bind(("127.0.0.1", 8080))
				
			listener.listen(1)
			self.client = None
			def Run():
				self.client, addr = listener.accept()
			from threading import Thread
			thread = Thread(target = Run)
			thread.start()

			if bluetooth:
				self.connection = bt.BluetoothSocket(bt.RFCOMM)
				self.connection.connect(("00:1A:7D:DA:71:0D", 3))
			else:
				self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				self.connection.connect(("127.0.0.1", 8080))
			import time
			time.sleep(2)
			assert self.connection is not None
			assert self.client is not None
			self.connection = SocketHandler(self.connection)
			self.client = SocketHandler(self.client)
			
		def SendInt(self):
			with Status_Info("Connection -> Client"):
				self.connection.Send(1337)
				int = self.client.Recv()
				assert int == 1337
				self.connection.Send(9321)
				int = self.client.Recv()
				assert int == 9321
			with Status_Info("Client -> Connection"):
				self.client.Send(1337)
				int = self.connection.Recv()
				assert int == 1337
				self.client.Send(9321)
				int = self.connection.Recv()
				assert int == 9321
		def SendShortString(self):
			with Status_Info("Connection -> Client"):
				self.connection.Send("Test")
				s = self.client.Recv()
				assert s == "Test"
				self.connection.Send("AnotherTest")
				s = self.client.Recv()
				assert s == "AnotherTest"
			with Status_Info("Client -> Connection"):
				self.client.Send("Test")
				s = self.connection.Recv()
				assert s == "Test"
				self.client.Send("AnotherTest")
				s = self.connection.Recv()
				assert s == "AnotherTest"
		def SendLongString(self):
			import string
			import random
			msg = ''.join([random.choice(string.ascii_letters + string.digits) for x in range(10000)])
			with Status_Info("Connection -> Client"):
				self.connection.Send(msg)
				s = self.client.Recv()
				assert s == msg
				
			with Status_Info("Client -> Connection"):
				self.client.Send(msg)
				s = self.connection.Recv()
				assert s == msg
		def SendNumpyArray(self):
			with Status_Info("Small int"):
				array = np.array([[1,2,3],[4,5,6]])
				self.connection.Send(array)
				recv = self.client.Recv()
				assert np.array_equal(recv, array) == True
			with Status_Info("Large float"):
				array = np.random.rand(3280, 1024)
				self.client.Send(array)
				recv = self.connection.Recv()
				assert np.array_equal(recv, array) == True
		def SendList(self):
			with Status_Info("List"):
				import random
				list = random.sample(range(0, 10000), 10000)
				self.connection.Send(list)
				recv = self.client.Recv()
				for i in range(0, 10000):
					assert recv[i] == list[i]
			with Status_Info("Tuple"):
				tuple = (1,2,3,4,2,2,2.3, "Test")
				self.client.Send(tuple)
				recv = self.connection.Recv()
				for i, v in enumerate(tuple):
					assert recv[i] == v
		def SendClass(self):		
			data = Data()
			self.connection.Send(data)
			recv = self.client.Recv()
			assert recv.a == data.a
			assert recv.b == data.b
			assert recv.c == data.c
		def SendFile(self):
			with open("Test.txt", "w") as f:
				f.write("Test")
			with open("Test.txt", "rb") as f:
				self.connection.Send(f)
			filename = self.client.Recv(filename = "Test2.txt")
			assert filename == "Test2.txt"
			with open("Test.txt", "r") as f1:
				with open("Test2.txt", "r") as f2:
					f1.readline() == f2.readline()
			os.remove("Test.txt")
			os.remove("Test2.txt")
		def SendEnum(self):
			self.connection.Send(LHMT_Commands.SEND_LOG)
			recv = self.client.Recv()
			assert recv == LHMT_Commands.SEND_LOG
	#with Status_Info("Normal socket"):
	with Status_Info("Initiating test"): test = Test()
	with Status_Info("SendInt"): test.SendInt()
	with Status_Info("SendShortStr"): test.SendShortString()
	with Status_Info("SendLongStr"): test.SendLongString()
	with Status_Info("SendNumpyArray"): test.SendNumpyArray()
	with Status_Info("SendList"): test.SendList()
	with Status_Info("SendClass"): test.SendClass()
	with Status_Info("SendFile"): test.SendFile()
	with Status_Info("SendEnum"): test.SendEnum()
	'''with Status_Info("Bluetooth socket"):
		with Status_Info("Initiating test"): test = Test(bluetooth = True)
		with Status_Info("SendInt"): test.SendInt()
		with Status_Info("SendShortStr"): test.SendShortString()
		with Status_Info("SendLongStr"): test.SendLongString()
		with Status_Info("SendNumpyArray"): test.SendNumpyArray()
		with Status_Info("SendList"): test.SendList()
		with Status_Info("SendClass"): test.SendClass()
		with Status_Info("SendFile"): test.SendFile()'''