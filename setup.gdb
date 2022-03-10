# config stuff
set python print-stack full
set print frame-arguments all

# check for cleanup
source cleanup.py

# important modules
define load-script
  echo loading $arg0...\n
  source $arg0
end

load-script lisp_types.py
load-script lisp_functions.py
load-script variable_lookup.py
load-script backtrace.py
load-script breakpoints.py
load-script nav_frame.py
load-script nav_manager.py
load-script commands.py

# main module
load-script main.py

echo all loaded!\n
