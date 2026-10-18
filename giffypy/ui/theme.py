def apply_theme(window):
    window.setStyleSheet(
        "QWidget{background:#25272b;color:#ddd} QPushButton{padding:6px 10px;background:#3a3d44;border-radius:5px}"
        "QPushButton:disabled{background:#2b2d30;color:#555}"
        "QPushButton:checked{background:#3d8bfd}"
        "#ow,#go,#sa,#cp{color:white;font-weight:bold;font-size:13px}"
        "#ow{background:#d9822b} #go{background:#2ea043} #sa{background:#3d8bfd} #cp{background:#8957e5}"
        "#ow:disabled,#go:disabled,#sa:disabled,#cp:disabled{background:#2b2d30;color:#555}"
        "QGraphicsView{background:#111}"
    )
