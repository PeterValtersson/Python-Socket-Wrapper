from enum import Enum
import pickle
import json
import socket as _socket
import numpy as np
from Log import *

LONG_STR_LENGHT = 256
SHORT_STR = 1
LONG_STR = 2
INT = 3
ENUM = 4
NUMPY_ARRAY = 5
FILE = 6
PICKLE = 7
LIST = 8

class InvalidAddressOrPort(Exception):
	def __init__(self, address, port):
		super().__init__("Invalid address or port. Address: {}, Port: {}".format(address, port))
class ConnectionLost(Exception):
	def __init__(self, socket):
		super().__init__("Connection to {}:{} lost".format(socket.address, socket.port))
		self.socket = socket
		
## A wrapper for sockets that automatically resolves what is going to be sent and received.
#
# This class simplifies the send and recv by automatically resolving the type of what is being sent/received.
# As well as handling the size to send and recieve.
class Socket():

	## Constructor
	#
	# @param socket The socket to wrap. If None will create a new socket
	def __init__(self, socket = None):
		if socket is None:
			socket = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
		self.socket = socket
		self.address = None
		self.port = None
		try:
			import bluetooth as bt
			if type(self.socket) is bt.BluetoothSocket:
				self._recv = self._bluetoothRecv
		except:
			# No bluetooth library
			pass	
	## Overrides _recv when using bluetooth
	#
	# Since bluetoothSocket does not have recv_into, this is used instead.
	# \see _recv
	def _bluetoothRecv(self, size):
		ret = bytearray(size)
		view = memoryview(ret)
		toRead = size
		while toRead:
			bytes = self.socket.recv(min(toRead, LONG_STR_LENGHT))
			if bytes == b'': raise ConnectionLost(self)	
			nbytes = len(bytes)
			view[:nbytes] = bytes
			view = view[nbytes:]
			toRead -= nbytes
		return ret
	
	## Bridge to base socket
	def connect(self, address, port):
		self.address = address
		self.port = port
		self.socket.connect((address, port))
		
	## Bridge to base socket
	def close(self):
		self.socket.close()
	
	## Bridge to base socket
	def settimeout(self, *args):
		self.socket.settimeout(*args)
		
	## Bridge to base socket
	def settimeout(self, *args):
		self.socket.settimeout(*args)
	
	## Bridge to base socket
	def bind(self, address, port):
		self.address = address
		self.port = port
		self.socket.bind((address, port))
		
	## Bridge to base socket
	def listen(self, *args):
		self.socket.listen(*args)
		
	## Bridge to base socket
	def accept(self, *args):
		client, address = self.socket.accept(*args)
		printDebug("Connected to", address)
		return Socket(client), address
		
	## Send a message. Will send size first followed by the message.
	#
	# Will first send a 32bit integer representing the size, followed immediatly by the message
	# \warning This is intended for internal purposes and should not be used from the outside
	# \exception ConnectionLost Connection to socket lost.
	def _send(self, msg):
		size = len(msg)
		sent = self.socket.sendall(size.to_bytes(4, 'big'))
		if sent == 0: raise ConnectionLost(self)
	
		sent = self.socket.sendall(msg)
		if sent == 0: raise ConnectionLost(self)
		return sent
	
	## Receive a message of the given size
	#
	# This method is used internally when receiving messages.
	# \warning This is intended for internal purposes and should not be used from the outside
	# Creates a bytearray and a view to that array, then fills the array using recv_into until the exact number of bytes has been received.
	# \warning Should 
	def _recv(self, size):
		bytes = bytearray(size)
		view = memoryview(bytes)
		toRead = size
		while toRead:
			nbytes = self.socket.recv_into(view, min(toRead, LONG_STR_LENGHT))
			if nbytes == 0: raise ConnectionLost(self)	
			view = view[nbytes:]
			toRead -= nbytes
		return bytes
	
	## Receive a message. Will first get the size, followed by the message
	#
	# \warning This is intended for internal purposes and should not be used from the outside
	# \warning Must be matched with a send
	# This method will first wait for the size of the message. This is in the form of a 32bit integer.
	# The message is then received.
	def _recvData(self):
		size = int.from_bytes(self._recv(4), 'big')
		return self._recv(size)
		
	
	## Send the type of the object to the connection
	#
	# This function can also send payloads along with the type (This speeds up some of the communications).
	# The function will first try to dumps using json, this will fail in some cases, ex. when sending a dtype, on fail pickle dumps is used instead
	# \warning This is intended for internal purposes and should not be used from the outside
	# @param type The type of the object
	# @param data Additional data to send, can be the actual value of for example an int or the size of an array. This speeds up communication for small types, by removing the need to send multiple messages.
	def _sendType(self, type, data = ()):
		try: toSend = json.dumps((type, data)).encode()
		except: toSend = pickle.dumps((type, data))
		self._send(toSend) 
		
	## Recieve the type of a message
	#
	# This is the first thing that is called when receiving anything from the connection
	# It will first type to using json.loads, if this fails it will revert to pickle.loads
	# \warning This is intended for internal purposes and should not be used from the outside
	def _recvType(self):
		data = self._recvData()
		try: return json.loads(data.decode()) 		
		except: return pickle.loads(data)
			
	## Send a string
	#
	# If the string is less than LONG_STR_LENGHT-100 the string is sent in the payload otherwise the string is sent separately. This avoids dumping a long string, which can reduce performance.
	# \warning This is intended for internal purposes and should not be used from the outside
	def _sendString(self, msg):	
		with Status_Debug("Sending string"):
			toSend = len(msg)
			printDebug("Length:", toSend)
			if toSend < LONG_STR_LENGHT:
				with Status_Debug("Sending short string"):	self._sendType(SHORT_STR, msg)
			else:
				with Status_Debug("Sending long string"):
					with Status_Debug("Sendning type"): self._sendType(LONG_STR)		
					with Status_Debug("Sending string..."):  self._send(msg.encode())
					
	## Send a numpy array
	#
	# First sends the type, shape and dtype
	# Then sends the array itself
	# \warning This is intended for internal purposes and should not be used from the outside	
	def _sendNumpyArray(self, array):
		self._sendType(NUMPY_ARRAY, (array.shape, array.dtype))
		self._send(array.tobytes())
	
	## Recieve a numpy array
	#
	# \warning This is intended for internal purposes and should not be used from the outside	
	# This function constructs a numpy array and files the array with data from the connection
	# @param shape_dtype Tuple containing the shape and dtype (in that order).
	def _recvNumpyArray(self, shape_dtype ):
		shape, dtype = shape_dtype
		bytes = self._recvData()
		array = np.frombuffer(bytes, dtype)
		array.shape = shape
		return array
		
	## Send a file
	#
	# First sends the type, size and name.
	# Then sends the file itself. 
	# \warning This is intended for internal purposes and should not be used from the outside	
	# @param file The file to send (assumed to be opened)
	# \warning Will not work with bluetooth, since pyBluez does not have sendfile. TODO: Implement replacement
	def _sendFile(self, file):
		with Status_Info("Sending file"):
			with Status_Debug("Sending type and size"):
				file.seek(0, 2)
				size = file.tell()
				self._sendType(FILE, (size, file.name)) 
				file.seek(0)			
			with Status_Debug("Sending the file"):
				sent = self.socket.sendfile(file, 0)	
				if sent == 0: raise ConnectionLost(self)
	
	## Recieve a file
	#
	# \warning This is intended for internal purposes and should not be used from the outside	
	# @param size_name A tuple with the size and name (in that order) of the file
	# @param filename If None(default) the file will be created with the same name in the current working directory.
	def _recvFile(self, size_name, filename = None):
		with Status_Info("Recieving file"):
			print(size_name)
			with Status_Debug("Recieving the file"):
				if filename == None: filename = size_name[1]
				with open(filename, 'wb') as file:
					toRead = size_name[0]
					while toRead:
						bytes = self.socket.recv(min(toRead, LONG_STR_LENGHT))
						if bytes == b'': raise ConnectionLost(self)	
						file.write(bytes)
						toRead -= len(bytes)
		return filename
	
	
	## This function will automatically resolve the type of the message and communicate this with the connection and send the message.
	#
	# All types that can be pickled using pickle are supported, however, pickle can be slow, therefore a warning is printed each time something is sent using pickle.
	# \warning When sending files, they are assumed to already be opened using f = open(...)
	def send(self, msg):
		if type(msg) == list or type(msg) == tuple:
			self._sendType(LIST, msg)
		elif isinstance(msg, str):
			self._sendString(msg)
		elif isinstance(msg, int):
			self._sendType(INT, msg)
		elif isinstance(msg, Enum):
			self._sendType(ENUM, msg)
		elif type(msg) is np.ndarray:
			self._sendNumpyArray(msg)
		elif type(msg).__name__ == 'BufferedReader':
			self._sendFile(msg)	
		else:
			printWarning("Sending with pickle") # This can be slow!
			self._sendType(PICKLE)	
			bytes = pickle.dumps(msg, pickle.HIGHEST_PROTOCOL)
			self._send(bytes)
	
	## Recieve a message from the connection
	#
	# This will automatically resolve the type that has been received and act accordingly.
	# @param *args Any arguments to pass to the internal methods
	# @param **kwargs Any keyword arguments to pass to the internal methods
	def recv(self, *args, **kwargs):
		type, msg = self._recvType()
		if type == SHORT_STR:
			return msg
		elif type == LONG_STR:
			return  self._recvData().decode()	
		elif type == INT:
			return msg
		elif type == ENUM:
			return msg
		elif type == NUMPY_ARRAY:
			return self._recvNumpyArray(msg)
		elif type == LIST:
			return msg
		elif  type == FILE:
			return self._recvFile(msg, *args, **kwargs)
		elif type == PICKLE:
			bytes = self._recvData()
			ret = pickle.loads(bytes)
			return ret
			
	## Send a message and immediatly wait for a response
	# @see send
	# @see recv
	def sendRecv(self, msg):
		self._send(msg)
		return self._recvData()
	
	## Recieve a msg and immediatly respond
	# @see send
	# @see recv
	def recvSend(self, msg):
		ret = self._recvData()
		self._send(msg)
		return ret

if __name__ == "__main__":
	class Data():
		def __init__(self):
			self.a = 1
			self.b = "Test"
			self.c = 2.3
	class TestEnum(Enum):
		A = 1
		B = 2
		C = 3
	class Test():
		def __init__(self):

			listener = Socket()
			listener.bind("127.0.0.1", 8080)
			listener.listen(1)
			
			self.client = None
			def Run():
				self.client, addr = listener.accept()
			from threading import Thread
			thread = Thread(target = Run)
			thread.daemon = True
			thread.start()

			self.connection = Socket()
			self.connection.connect("127.0.0.1", 8080)
			import time
			time.sleep(2)
			assert self.client is not None

			
		def SendInt(self):
			with Status_Info("Connection -> Client"):
				self.connection.send(1337)
				int = self.client.recv()
				assert int == 1337
				self.connection.send(9321)
				int = self.client.recv()
				assert int == 9321
			with Status_Info("Client -> Connection"):
				self.client.send(1337)
				int = self.connection.recv()
				assert int == 1337
				self.client.send(9321)
				int = self.connection.recv()
				assert int == 9321
		def SendShortString(self):
			with Status_Info("Connection -> Client"):
				self.connection.send("Test")
				s = self.client.recv()
				assert s == "Test"
				self.connection.send("AnotherTest")
				s = self.client.recv()
				assert s == "AnotherTest"
			with Status_Info("Client -> Connection"):
				self.client.send("Test")
				s = self.connection.recv()
				assert s == "Test"
				self.client.send("AnotherTest")
				s = self.connection.recv()
				assert s == "AnotherTest"
		def SendLongString(self):
			import string
			import random
			msg = ''.join([random.choice(string.ascii_letters + string.digits) for x in range(10000)])
			with Status_Info("Connection -> Client"):
				self.connection.send(msg)
				s = self.client.recv()
				assert s == msg
				
			with Status_Info("Client -> Connection"):
				self.client.send(msg)
				s = self.connection.recv()
				assert s == msg
		def SendNumpyArray(self):
			with Status_Info("Small int"):
				array = np.array([[1,2,3],[4,5,6]])
				self.connection.send(array)
				recv = self.client.recv()
				assert np.array_equal(recv, array) == True
			with Status_Info("Large float"):
				array = np.random.rand(3280, 1024)
				self.client.send(array)
				recv = self.connection.recv()
				assert np.array_equal(recv, array) == True
		def SendList(self):
			with Status_Info("List"):
				import random
				list = random.sample(range(0, 10000), 10000)
				self.connection.send(list)
				recv = self.client.recv()
				for i in range(0, 10000):
					assert recv[i] == list[i]
			with Status_Info("Tuple"):
				tuple = (1,2,3,4,2,2,2.3, "Test")
				self.client.send(tuple)
				recv = self.connection.recv()
				for i, v in enumerate(tuple):
					assert recv[i] == v
		def SendClass(self):		
			data = Data()
			self.connection.send(data)
			recv = self.client.recv()
			assert recv.a == data.a
			assert recv.b == data.b
			assert recv.c == data.c
		def SendFile(self):
			with open("Test.txt", "w") as f:
				f.write("Test")
			with open("Test.txt", "rb") as f:
				self.connection.send(f)
			filename = self.client.recv(filename = "Test2.txt")
			assert filename == "Test2.txt"
			with open("Test.txt", "r") as f1:
				with open("Test2.txt", "r") as f2:
					f1.readline() == f2.readline()
			os.remove("Test.txt")
			os.remove("Test2.txt")
		def SendEnum(self):
			self.connection.send(TestEnum.A)
			recv = self.client.recv()
			assert recv == TestEnum.A
	#with Status_Info("Normal socket"):
	with Status_Info("Initiating test"): test = Test()
	with Status_Info("SendInt"): test.SendInt()
	with Status_Info("SendShortStr"): test.SendShortString()
	with Status_Info("SendLongStr"): test.SendLongString()
	with Status_Info("_sendNumpyArray"): test.SendNumpyArray()
	with Status_Info("SendList"): test.SendList()
	with Status_Info("SendClass"): test.SendClass()
	with Status_Info("_sendFile"): test.SendFile()
	with Status_Info("SendEnum"): test.SendEnum()
	'''with Status_Info("Bluetooth socket"):
		with Status_Info("Initiating test"): test = Test(bluetooth = True)
		with Status_Info("SendInt"): test.SendInt()
		with Status_Info("SendShortStr"): test.SendShortString()
		with Status_Info("SendLongStr"): test.SendLongString()
		with Status_Info("_sendNumpyArray"): test._sendNumpyArray()
		with Status_Info("SendList"): test.SendList()
		with Status_Info("SendClass"): test.SendClass()
		with Status_Info("_sendFile"): test._sendFile()'''