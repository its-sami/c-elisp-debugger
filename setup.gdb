# config stuff
set python print-stack full
set print frame-arguments all

# check for cleanup
source cleanup.py

# important modules
define load
  echo loading $arg0...\n
  source $arg0
end

load lisp_types.py
load lisp_functions.py
load backtrace.py
load breakpoints.py
load nav_frame.py
load nav_manager.py
load commands.py

# main module
load main.py

echo all loaded!\n
