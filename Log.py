import time
parent = None
import sys, traceback, os


def GetEnumerate(e):
	return enumerate(e)
	
def Timeout(Exception):
	def __init__(self):
		super().__init__("Timeout")
class Status_None:
	def __init__(self, text, total = 0, enumerate = None, steps = 100):
		if type(enumerate) == type(None):
			self.iter = range(0, total).__iter__()
		else:
			self.iter = GetEnumerate(enumerate).__iter__()
	def __enter__(self):
		return self
	def __exit__(self, *args):
		pass
	def __iter__(self):
		return self.iter

## Status with the warning level		
Status_Warning = Status_None

## Status with the info level
Status_Info = Status_None

## Status with debug level
Status_Debug = Status_None

#Status with debug level
Status = Status_None



LogFilePath = ""
LogFile = None
written = 0
Org_Print = print
Printer = print


## Print with info level
printInfo = lambda *a, **kw: None

## Print with warning level
printWarning = print

## Print with debug level
printDebug = lambda *a, **kw: None

## Print with debug level
print = lambda *a, **kw: None

## Only warnings are printed
WARNING_LEVEL = "0"  
## Warnings and info is printed
INFO_LEVEL = "1" 
## Everything is printed (Slow)
DEBUG_LEVEL = "2" 

## Write the log message to the log file
def Print_Log(*args, end = "\n"):
	global written
	toWrite = "".join([repr(v) for v in args])
	
	if toWrite == "\r":
		LogFile.seek(LogFile.tell() - written)
		written = 0
		return
		
	written += LogFile.write(toWrite)
	written += LogFile.write(end)
	if end == "\n":
		written = 0
	
def Print_Both(*args, end = "\n"):
	Org_Print(*args, end = end)
	Print_Log(*args, end = end)

Flush = lambda: None

## This class is used to log the status of the program.
#
# This is done in one of two ways, using either the with keyword or for
#
# Example:
#
# with Status("Creating log"):
#
# 	...
# 
# for i in Status("Looping", total = 100):
#
# 	...
class Status_Impl():
	
	## The usage can be modified with the constructor
	# 
	# @param text The message to be logged
	# @param total The upper limit when used as a for loop
	# @param enumerate If this used when Status is used as a for loop the object assinged will be enumerated
	# @param steps The number of iterations of the for loop between each progress print
	def __init__(self, text, total = 0, enumerate = None, steps = None):
		self.enumerate = enumerate

		if type(steps) == type(None): self.steps = max(total // 10, 1)
		else: self.steps = steps	
		if type(enumerate) == type(None):
			self.numIterations = total
		else:
			self.numIterations = len(self.enumerate)		
		self.progress = 0

		global parent
		if parent != None:
			self.numTabs = parent.numTabs + 1
		else:
			self.numTabs = 0
		self.parent = parent
		parent = self
		
		self.text = text
		self.tabs = "--"*self.numTabs 
		self.newline = False
		
	def __enter__(self):
		if self.parent != None and not self.parent.newline:
			Printer("")
			self.parent.newline = True
		
		Printer(self.tabs, end = "--")
		Printer(self.text, end = "... ")
		Flush()
		return self
		
	def __exit__(self, *args):
		global parent
		if self.newline:
			Printer(self.tabs, end = "--")
			Printer(self.text, end = "... ")
		parent = self.parent
		Printer("Done")
		
	def __iter__(self):
		return self.__enter__()
		
	def __next__(self):
		if self.progress >= self.numIterations:
			Printer("\r", end = "")
			self.newline = True
			self.__exit__()
			raise StopIteration
		else:
			if self.progress % self.steps == 0 and not self.newline:
				Printer("\r", end = "")
				Printer(self.tabs, end = "--")
				Printer(self.text, end = "... {:.0%}".format(self.progress / self.numIterations))

			temp = self.progress
			self.progress += 1			
			if type(self.enumerate) == type(None): return temp
			else: return temp, self.enumerate[temp]



## Setups the log.
# 
# \warning This function must be called before any other module is imported, otherwise the logging will be incorrect.
# \warning This funciton overwrites print, default can be found in Org_Print
# @param level The level of the log, see WARNING_LEVEL, INFO_LEVEL, DEBUG_LEVEL
def Status_Importer(*a, p = "True", level = INFO_LEVEL,  **kw):

	
	global Status
	global Status_Warning
	global Status_Info
	global Status_Debug
	
	global printWarning
	global printInfo
	global printDebug
	global print
	global Flush
	global Printer
	def CreateLog():
		global LogFile
		LogFilePath = time.strftime("Logs/Log-%d-%m-%y_%H.%M.%S.log")
		try: os.makedirs("Logs")
		except: pass
		LogFile = open(LogFilePath, 'w')
	
	def PrintStatus(*args):
		global Printer
		global parent
		if parent != None:
			if not parent.newline:
				Printer("")
				parent.newline = True
			Printer(parent.tabs, end = "----")
		else:
			Printer("--", end = "")
		Printer(*args)
	def PrintWarning(*args):
		global Printer
		global parent
		if parent != None:
			if not parent.newline:
				Printer("")
				parent.newline = True
			Printer(parent.tabs, end = "----")
		else:
			Printer("--", end = "")
		Printer("[WARNING]: ", end = "")
		Printer(*args)
	if p == "True":
		Printer = Print_Both
		Flush = sys.stdout.flush
	else:
		Printer = Print_Log
		Flush = lambda: None
	CreateLog()
	if level == DEBUG_LEVEL:
		Status_Warning = Status_Info = Status = Status_Debug = Status_Impl
		print = printInfo = printDebug = PrintStatus
		printWarning = PrintWarning
	elif level == INFO_LEVEL:
		Status_Warning = Status_Info = Status_Impl
		printInfo = PrintStatus
		printWarning = PrintWarning
	elif level == WARNING_LEVEL:
		Status_Warning = Status_Impl
		printWarning = PrintWarning
	
## Prints the latest exception that has occured
def PrintException():
	global Printer
	Printer("\nAn exception has occured!")
	Printer("-"*60)
	exc_type, exc_value, exc_traceback = sys.exc_info()
	formated_lines = traceback.format_exc().splitlines()
	Printer(formated_lines[-1])
	Printer("*****Details******")
	formated = traceback.format_exception(exc_type, exc_value, exc_traceback)
	for l in formated: Printer(l)
	Printer("-"*60)
	return formated_lines[-1]

import sys
argv = {}
i = 0
sargv = sys.argv.copy()
del sargv[0]
for arg in sargv:
	if arg[0] == "-":
		if i+1 >= len(sargv) or sargv[i+1][0] == "-":
			argv[arg[1:]] = True
		else:
			argv[arg[1:]] = sargv[i+1]
	i += 1
Status_Importer(**argv)
		
		
if __name__ == "__main__":
	def Func1():
		for i, j in Status("Writing", enumerate = [1,2]):
			pass
	def Func2():
		for i, j in Status("Writing Measurements", enumerate = ["Enum1"]):
			Func1()
	

	with Status_Info("Test") as s:
		pass
	with Status_Info("Test2"):
		with Status("Test22"):
			print("Hello")
	def Func():
		with Status_Info("Returning"):
			return "Hello"
	
	with Status_Info("Calling"):
		print(Func())
	
	
	printWarning("Start loop testing")
	
	for i in Status("LoopOuter", total = 10000, steps = 1):
		pass
	
	with Status_Info("StatusLoop"):
		for i in Status("LoopOuter", total = 10000):
			pass

	with Status_Info("StatusLoopLoop"):
		for i in Status("Loop1", total = 4):
			for j in Status("Loop2:%d"%i, total = 100000):
				pass
	
	a = ["a", "b","c"]
	for i, v in Status("Enumerate", enumerate = a, steps = 1): 
		print(i, v)
	
	with Status_Info("StatusEnumerate"):
		for i, v in Status("Enumerate", enumerate = a, steps = 1): 
			with Status(v):
				print(i)
	for i in Status_Info("Zero", total = 0):
		print(i)
	
	with Status_Info("Test1"):
		with Status("Test2"):
			print("Hello")
			for i in Status("LoopInner", total = 10000):
				pass
	
	
	
	
	with Status_Info("StatusStatusEnumEnum"):
		with Status("StatusEnumEnum"):
			Func2()

	
	printWarning("PrintWarning")
	printInfo("PrintInfo")
	printDebug("PrintDebug")
	print("PrintDebug as well")
	
	with Status_Warning("This is a warning"):
		pass	
	with Status_Info("This is info"):
		pass
	with Status_Debug("This is debug"):
		pass
	with Status("This is also debug"):
		pass

	
