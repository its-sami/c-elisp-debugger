# config stuff
set python print-stack full
set print frame-arguments all

# check for cleanup
source cleanup.py

# important modules
echo loading lisp_types.py...\n
source lisp_types.py

echo loading lisp_functions.py...\n
source lisp_functions.py

echo loading breakpoints.py...\n
source breakpoints.py

echo loading nav_frame.py...\n
source nav_frame.py

echo loading nav_manager.py...\n
source nav_manager.py

echo loading commands.py...\n
source commands.py

# main module
echo loading main.py...\n
source main.py
echo all loaded!\n
