# Python-Socket-Wrapper
A wrapper class for the python socket with automatic type deduction for both sending and receiving messages.


I was using python during work and had to use sockets. Seeing as how python should be a high level language I was utterly dumbfounded that python sockets expects you to know how big something is in bytes. I found pythons support for raw data very diffuse but in the end ended up with this.

The main goal of this project has been to hide the raw data from the user and to provide a very simple interface that will automatically send any kind of data.

# Usage

```python
##### Client
import SocketWrap
sock = SocketWrap.Socket()
sock.connect("192.168.4.1", 8080)

sock.send("Hello")
sock.send(5)
sock.send(("Tuple", True))

sock.recv() # 

# Numpy arrays are supported
import numpy as np
array = np.random.rand(3,2)
sock.send(array)

# Anything that can be pickled is suppored (Since Pickle slow, it is only used as a last resort).
class Test:
  def __init__(self):
    self.a = 1
    self.b = "Hello"
    self.c = np.array([1,2,3])
sock.send(Test())

##### Server
import SocketWrap
listener = SocketWrap.Socket()
listener.bind("192.168.4.1", 8080)
listener.listen(1)

client = listener.accept()
print(client.recv()) # Prints 'Hello'
print(client.recv()) # Prints '5'
print(client.recv()) # Prints '("Tuple", True)'

client.send("send and recv and be done in any order.")

# Numpy arrays are supported
numpyArray = client.recv()
testClass = client.recv()
```
