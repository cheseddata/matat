import os
from app import create_app

app = create_app('development')

if __name__ == '__main__':
    # Allow operators to override port via PORT env var; default 5050 for
    # local installs (5000 clashes with AirPlay on many Windows laptops).
    port = int(os.environ.get('PORT', 5050))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(debug=debug, host=host, port=port)
