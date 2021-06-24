from bokeh.plotting import figure
from bokeh.io import output_file, show, export_png
from bokeh.io.webdriver import create_chromium_webdriver

import hashlib

def sha256sum(filename):
    h  = hashlib.sha256()
    b  = bytearray(128*1024)
    mv = memoryview(b)
    with open(filename, 'rb', buffering=0) as f:
        for n in iter(lambda : f.readinto(mv), 0):
            h.update(mv[:n])
    return h.hexdigest()

def generate_plot(filename):
    p = figure(plot_width=400, plot_height=400)

    p.circle([1, 2, 3, 4, 5], [6, 7, 2, 4, 5], size=15, line_color="navy", 
    fill_color="orange", fill_alpha=0.5)

    # --no-sandbox is required per https://stackoverflow.com/q/50642308
    # Maybe look into https://github.com/Zenika/alpine-chrome at some point
    driver = create_chromium_webdriver(['--no-sandbox'])
    export_png(p, filename=filename, webdriver=driver)
    # get_screenshot_as_png

generate_plot("plot.png")
hash = sha256sum("plot.png")
assert hash == "ed2ffa2348560a7254753fe0ff70e811e3a0d1879c1609aeeb32efeb2feecc35"

print("All good! 🙌")