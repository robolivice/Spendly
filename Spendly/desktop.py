import webview
from app import app

webview.create_window("Expense Tracker", app, width=1000, height=700)
webview.start()