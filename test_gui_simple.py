import sys
print(sys.version)
print("Python executable:", sys.executable)
try:
    import PyQt6
    print("PyQt6 version:", PyQt6.__version__)
except:
    print("PyQt6 not installed")
try:
    import PyQt5
    print("PyQt5 version:", PyQt5.__version__)
except:
    print("PyQt5 not installed")