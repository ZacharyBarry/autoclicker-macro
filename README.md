Auto-Clicker Pro 🖱️⚡

Overview & Purpose

Auto-Clicker Pro is an advanced, open-source desktop automation tool featuring a highly customizable auto-clicker and a full-fledged macro recorder. It is designed to help users automate repetitive graphical interface tasks, streamline testing procedures, and execute complex sequences with precision.

Key Features

Dual Functionality: Seamlessly switch between a standard interval-based auto-clicker and a robust macro recorder via a tabbed interface.

Advanced Macro Scripting Engine: Features a built-in text editor with custom syntax highlighting, line numbers, and the ability to load/save macro scripts (.txt).

Smart Pixel Detection: Includes a WAIT_PIXEL command using screen-capturing technology to pause macro execution until a specific pixel color appears on screen.

Global Hotkey Listeners: Set custom keyboard hotkeys to start/stop clicking, record macros, or play them back without needing the application in focus.

Dynamic Playback Controls: Adjust playback speed multipliers, schedule delayed starts, and define exact loop repeat counts.

Responsive UI: Built with Dark/Light mode toggles, an "Always on Top" feature, and real-time status bars and progress tracking.

Technologies Used

Language: Python 3

GUI Framework: Tkinter (with ttk for modern themed widgets)

Input Control: pynput (for global mouse and keyboard listeners/controllers)

Screen Capturing & Image Processing: mss (fast screen grabs) and Pillow (PIL) for precise pixel color detection.

Concurrency: threading module (to ensure the UI remains responsive while intensive clicking or recording loops run in the background).

Setup & Installation Instructions

Ensure Python is installed:
You must have Python 3.x installed on your system.

Clone the repository:

git clone [https://github.com/ZacharyBarry/autoclicker-macro.git](https://github.com/ZacharyBarry/autoclicker-macro.git)
cd autoclicker-macro


Install Required Dependencies:
Install the required external libraries using pip:

pip install pynput mss Pillow


Run the Application:
Execute the python script from your terminal:

python autoclicker.py


Usage

Auto-Clicker: Set your interval, choose whether to click at the current mouse location or specific X/Y coordinates, set your hotkey, and press Start.

Macro Recorder: Click the "Record" button (or use your bound hotkey). Perform your sequence of clicks, mouse movements, and keyboard inputs. Stop recording, edit your script in the editor if necessary, and hit "Play" to watch the automation execute.

My Contribution & Reflection

This was a solo project where I architected and developed the entire application from the ground up.

Challenge & Lesson Learned: One of the primary technical challenges was managing the GUI's main loop alongside global keyboard listeners and infinite clicking loops. Early iterations caused the Tkinter interface to freeze. I solved this by implementing multi-threading with threading.Event() to safely pass stop signals, and utilized Tkinter's .after() method to safely queue UI updates (like the progress bar and status text) from the background threads.

License

All Rights Reserved. This project is provided for portfolio demonstration purposes only. Unauthorized copying, modification, or distribution of the source code is prohibited.
