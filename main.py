clang = None
embedded = clang is not None

import sys
import tempfile
import os

def find_embedded_zip():
    with open(sys.executable, 'rb') as f:
        data = f.read()
    start = data.find(b'PK\x03\x04')
    if start == -1:
        raise RuntimeError("ZIP not found")
    return data[start:]

if embedded:
    # Extract the embedded ZIP to a temp file
    zip_data = find_embedded_zip()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        tmp.write(zip_data)
        temp_zip_path = tmp.name

    # Add the temp ZIP to sys.path so normal imports work
    sys.path.insert(0, temp_zip_path)

# Now to execute Gum.__main__.main()
from Gum.__main__ import main
try:
    main(clang)
except KeyboardInterrupt:
    pass
finally:
    if clang:
        os.unlink(temp_zip_path)
