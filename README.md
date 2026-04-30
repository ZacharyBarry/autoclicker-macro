# AutoClicker Pro

![Project Demo](demo.gif)

A multi-threaded Python desktop automation tool featuring a standard auto-clicker and an advanced macro recorder with a custom, syntax-highlighted script editor.

## ✨ Features
* **Advanced Macro Recorder:** Records complex sequences of mouse movements, clicks, and keystrokes globally.
* **Custom Scripting Engine:** Macros are compiled into a custom, human-readable script format (e.g., `WAIT`, `MOVE`, `KEY_DOWN`, `WAIT_PIXEL`).
* **Integrated IDE:** Built-in script editor featuring live syntax highlighting, line numbers, and file I/O for saving and loading macro profiles.
* **Dynamic Playback:** Supports adjustable playback speeds, scheduled executions, and infinite or bounded looping.
* **Pixel Color Detection:** Includes logic to pause macro execution until a specific pixel on the screen matches a target RGB value.
* **Thread-Safe UI:** Built with Tkinter, utilizing asynchronous threading to ensure the GUI remains responsive during intense macro execution. 

## 🛠️ Built With
* **Python 3**
* **Tkinter:** Frontend GUI
* **pynput:** Global hardware event hooking and simulation
* **mss & Pillow:** High-speed screen capture and pixel color extraction

## 🚀 Quick Start

1. Clone the repository:
`git clone https://github.com/ZacharyBarry/autoclicker-macro.git`

2. Install the required dependencies:
`pip install pynput mss Pillow`

3. Run the application:
`python main.py`
