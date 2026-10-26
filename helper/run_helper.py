"""Start the Hinglish Edit helper. Double-click 'Start Helper.bat' on Windows, or run: python run_helper.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hinglish_edit.server import serve  # noqa: E402

if __name__ == "__main__":
    try:
        serve(sys.argv[1] if len(sys.argv) > 1 else None)
    except OSError as e:
        print("Could not start:", e)
        print("Is the helper already running in another window?")
        input("Press Enter to close...")
