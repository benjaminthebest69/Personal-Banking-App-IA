# app.py

import sys
import logging
from gui import PersonalBankingApp

def main():
    """
    Entry point of the Personal Banking App.

    Initializes the application and starts the main event loop.
    Logs any unhandled exceptions and exits gracefully.
    """
    try:
        app = PersonalBankingApp()
        app.mainloop()
    except Exception as e:
        # Obtain the logger instance
        logger = logging.getLogger(__name__)
        # Log the exception with traceback
        logger.exception("Application encountered an unexpected error: %s", e)
        # Exit the application with a non-zero status to indicate an error
        sys.exit(1)

