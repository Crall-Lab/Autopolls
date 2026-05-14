from pollinatorcam.ui import app

from werkzeug.debug import DebuggedApplication
app.wsgi_app = DebuggedApplication(app.wsgi_app, True)
app.debug = True

if __name__ == '__main__':
    app.run()
